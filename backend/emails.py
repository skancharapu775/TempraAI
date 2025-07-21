import os
import json
import base64
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
# from msgraph.core import GraphClient
from azure.identity import ClientSecretCredential
from openai import OpenAI
from google.cloud import firestore

# Gmail API setup
GMAIL_SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

# Microsoft Graph API setup
MS_GRAPH_SCOPES = ['https://graph.microsoft.com/Mail.ReadWrite']

class EmailService:
    def __init__(self, provider: str = "gmail"):
        self.provider = provider
        self.client = None
        self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        # Do not call setup_gmail() here
        if provider == "outlook":
            self.setup_outlook()
    
    # Remove setup_gmail()
    
    def setup_outlook(self):
        """Setup Microsoft Graph API client"""
        tenant_id = os.getenv("MS_TENANT_ID")
        client_id = os.getenv("MS_CLIENT_ID")
        client_secret = os.getenv("MS_CLIENT_SECRET")
        
        if not all([tenant_id, client_id, client_secret]):
            raise ValueError("Microsoft Graph credentials not configured")
        
        credential = ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret
        )
        # self.client = GraphClient(credential=credential)

    def setup_gmail_with_token(self, access_token: str, refresh_token: str, client_id: str, client_secret: str):
        """Setup Gmail API client using provided OAuth tokens"""
        creds = Credentials(
            token=access_token,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
            scopes=GMAIL_SCOPES
        )
        self.client = build('gmail', 'v1', credentials=creds)

class EmailIntentHandler:
    def __init__(self, email_service: EmailService):
        self.email_service = email_service
        self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    async def classify_email_function(self, message: str) -> str:
        """Classify what email function the user wants to perform"""
        system_prompt = """
        Classify the user's email request into one of these categories:
        
        - "summarize": User wants to summarize recent emails
        - "priority": User wants to see high priority/important emails
        - "organize": User wants to sort emails into folders/labels
        - "search": User wants to search for specific emails
        - "compose": User wants to compose/send a new email
        - "draft": User wants to create or manage email drafts
        - "schedule": User wants to schedule emails for later
        
        Return ONLY ONE WORD from the choices above.
        """
        
        response = self.openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message}
            ],
            max_tokens=20,
            temperature=0.3
        )
        
        return response.choices[0].message.content.strip().lower()
    
    async def handle_email_intent(self, message: str, pending_changes: dict = None) -> Tuple[str, dict, bool]:
        """Main handler for email intents"""
        # First, classify what email function is needed
        email_function = await self.classify_email_function(message)
        
        if email_function == "summarize": # no confirmation
            return await self.summarize_emails(message)
        elif email_function == "priority": # no confirmation
            return await self.get_priority_emails(message)
        elif email_function == "search": # no confirmation
            return await self.search_emails(message)
        elif email_function == "draft": # no confirmation
            return await self.manage_drafts(message)
        elif email_function == "compose": # confirmation
            return await self.compose_email(message, pending_changes)
        elif email_function == "organize": # confirmation
            return await self.organize_emails(message)
        elif email_function == "schedule": # confirmation
            return await self.schedule_email(message, pending_changes)
        else:
            # Default to compose if unclear
            return await self.compose_email(message, pending_changes)
    
    async def summarize_emails(self, message: str) -> Tuple[str, dict, bool]:
        """Summarize recent emails"""
        try:
            # Get recent emails
            emails = await self.get_recent_emails(limit=10)
            
            if not emails:
                return "No recent emails found to summarize.", None, False
            
            # Create summary using OpenAI
            email_texts = []
            for email in emails:
                email_texts.append(f"From: {email.get('from', 'Unknown')}\nSubject: {email.get('subject', 'No subject')}\nSnippet: {email.get('snippet', '')}\n---")
            
            summary_prompt = f"""
            Summarize the following recent emails in a concise, helpful way:
            
            {' '.join(email_texts)}
            
            Provide a summary that includes:
            1. Key themes or topics
            2. Important emails that need attention
            3. Any urgent matters
            4. Overall email volume and patterns
            """
            
            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": summary_prompt}],
                max_tokens=500,
                temperature=0.7
            )
            
            summary = response.choices[0].message.content.strip()
            
            return f"**📧 Email Summary:**\n\n{summary}", {
                "type": "email_summary",
                "summary": summary,
                "email_count": len(emails),
                "emails": emails
            }, False
            
        except Exception as e:
            return f"Sorry, I couldn't summarize your emails: {str(e)}", None, False
    
    async def get_priority_emails(self, message: str) -> Tuple[str, dict, bool]:
        """Get high priority/important emails"""
        try:
            # Get emails marked as important or with priority indicators
            priority_emails = await self.get_priority_emails_list(limit=15)
            
            if not priority_emails:
                return "No high-priority emails found.", None, False
            
            # Format priority emails
            email_list = []
            for i, email in enumerate(priority_emails, 1):
                priority = email.get('priority', 'normal')
                priority_emoji = "🔴" if priority == "high" else "🟡" if priority == "medium" else "🟢"
                
                email_list.append(f"{i}. {priority_emoji} **{email.get('subject', 'No subject')}**")
                email_list.append(f"   From: {email.get('from', 'Unknown')}")
                email_list.append(f"   Date: {email.get('date', 'Unknown')}")
                email_list.append(f"   Snippet: {email.get('snippet', '')[:100]}...")
                email_list.append("")
            
            response_text = f"**🎯 High Priority Emails ({len(priority_emails)} found):**\n\n{''.join(email_list)}"
            
            return response_text, {
                "type": "priority_emails",
                "emails": priority_emails,
                "count": len(priority_emails)
            }, False
            
        except Exception as e:
            return f"Sorry, I couldn't get priority emails: {str(e)}", None, False
    
    async def organize_emails(self, message: str) -> Tuple[str, dict, bool]:
        """Organize emails into folders/labels with confirmation"""
        try:
            system_prompt = """
            You are an assistant that extracts email organization details from the user's inputs. Your job is to identify which folders to create, which existing folders to use, 
            and the criteria for organizing emails. Then, generate a polite confirmation message asking the user to confirm the organization plan.

            REQUIRED FIELDS: criteria, existing_folders
            OPTIONAL FIELDS: created_folders, email_count

            FOLDER EXAMPLES:
            - "Work" - Work-related emails
            - "Personal" - Personal emails  
            - "Projects" - Project-specific emails
            - "Inbox" - Default folder
            - "Archive" - Archived emails
            - "Finance" - Financial emails
            - "Travel" - Travel-related emails

            Reply *only* with valid JSON. Example:
            {
                "created_folders": ["Work Projects", "Personal Finance"],
                "existing_folders": ["Inbox", "Archive"],
                "criteria": "organize work emails into Work Projects folder",
                "email_count": 50,
                "missing_fields": ["criteria"],
                "confirmation_message": "..."
            }
            
            If there are any current known details, merge them with the JSON that you will return.
            """

            user_prompt = f"User message: {message}"
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]

            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=messages,
                max_tokens=300,
                temperature=0.3
            )
            
            try:
                content = response.choices[0].message.content.strip()
                # Debug: Print the raw LLM response
                print(f"LLM raw response for email organize: {content}")
                
                # Clean the response - remove code blocks if present
                if content.startswith('```'):
                    content = content.split('```')[1]  # Remove first code block
                    if content.startswith('json'):
                        content = content[4:]  # Remove 'json' marker
                    content = content.strip()
                
                # Remove any trailing code blocks
                if content.endswith('```'):
                    content = content[:-3].strip()
                
                org_data = json.loads(content)
            except:
                print(f"Error parsing email organize JSON, using fallback")
                org_data = {
                    "created_folders": ["Work", "Personal"],
                    "existing_folders": ["Inbox"],
                    "criteria": "organize emails by type",
                    "email_count": 25,
                    "missing_fields": [],
                    "confirmation_message": "I'll help you organize your emails by creating Work and Personal folders and using your Inbox."
                }
            
            # Ensure we have the required fields
            created_folders = org_data.get("created_folders", [])
            existing_folders = org_data.get("existing_folders", ["Inbox"])
            criteria = org_data.get("criteria", "organize emails")
            email_count = org_data.get("email_count", 25)
            missing_fields = org_data.get("missing_fields", [])
            confirmation_message = org_data.get("confirmation_message", "")
            
            # Only show accept/deny if all required fields are present
            show_accept_deny = len(missing_fields) == 0
            
            # If no confirmation message was provided, create one
            if not confirmation_message:
                confirmation_message = f"📁 **Email Organization Plan**\n\n"
                confirmation_message += f"**Criteria:** {criteria}\n"
                confirmation_message += f"**Estimated emails to organize:** {email_count}\n\n"
                
                if created_folders:
                    confirmation_message += f"**📂 New folders to create:**\n"
                    for folder in created_folders:
                        confirmation_message += f"• {folder}\n"
                    confirmation_message += "\n"
                
                confirmation_message += f"**📁 Existing folders to use:**\n"
                for folder in existing_folders:
                    confirmation_message += f"• {folder}\n"
                
                confirmation_message += f"\nWould you like me to proceed with this organization plan?"
            
            # Return confirmation data
            confirmation_data = {
                "type": "email_organize",
                "created_folders": created_folders,
                "existing_folders": existing_folders,
                "criteria": criteria,
                "email_count": email_count,
                "action": "organize_emails"
            }
            
            return confirmation_message, confirmation_data, show_accept_deny
                
        except Exception as e:
            return f"Sorry, I couldn't organize your emails: {str(e)}", None, False
    
    async def search_emails(self, message: str) -> Tuple[str, dict, bool]:
        """Search for specific emails"""
        try:
            # Extract search query from message
            search_prompt = f"""
            Extract the search query from this message: "{message}"
            
            Return JSON with:
            - "query": the search terms
            - "limit": number of results (default 10)
            - "folder": specific folder to search (optional)
            
            Example: {{"query": "meeting tomorrow", "limit": 5}}
            """
            
            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": search_prompt}],
                max_tokens=200,
                temperature=0.3
            )
            
            try:
                content = response.choices[0].message.content.strip()
                # Debug: Print the raw LLM response
                print(f"LLM raw response for email search: {content}")
                
                # Clean the response - remove code blocks if present
                if content.startswith('```'):
                    content = content.split('```')[1]  # Remove first code block
                    if content.startswith('json'):
                        content = content[4:]  # Remove 'json' marker
                    content = content.strip()
                
                # Remove any trailing code blocks
                if content.endswith('```'):
                    content = content[:-3].strip()
                
                search_data = json.loads(content)
            except:
                print(f"Error parsing email search JSON, using fallback")
                search_data = {"query": message, "limit": 10}
            
            # Perform search
            search_results = await self.search_emails_by_query(
                search_data["query"], 
                limit=search_data.get("limit", 10)
            )
            
            if not search_results:
                return f"No emails found for: **{search_data['query']}**", None, False
            
            # Format results
            results_list = []
            for i, email in enumerate(search_results, 1):
                results_list.append(f"{i}. **{email.get('subject', 'No subject')}**")
                results_list.append(f"   From: {email.get('from', 'Unknown')}")
                results_list.append(f"   Date: {email.get('date', 'Unknown')}")
                results_list.append(f"   Snippet: {email.get('snippet', '')[:100]}...")
                results_list.append("")
            
            response_text = f"**🔍 Search Results for '{search_data['query']}' ({len(search_results)} found):**\n\n{''.join(results_list)}"
            
            return response_text, {
                "type": "email_search",
                "query": search_data["query"],
                "results": search_results,
                "count": len(search_results)
            }, False
            
        except Exception as e:
            return f"Sorry, I couldn't search your emails: {str(e)}", None, False
    
    async def compose_email(self, message: str, pending_changes: dict = None) -> Tuple[str, dict, bool]:
        """Compose a new email"""
        system_prompt = """
        You are an assistant that extracts email details from the user's inputs. Your job is to guess subject, recipient, body content, folder/label, and any attachments from natural text.
        Then, list any missing or unclear fields and generate a polite confirmation message asking the user to confirm or correct.

        REQUIRED FIELDS: subject, recipient, body
        OPTIONAL FIELDS: attachments, folder, priority, action

        FOLDER EXAMPLES:
        - "Work" - Work-related emails
        - "Personal" - Personal emails  
        - "Projects" - Project-specific emails
        - "Inbox" - Default folder
        - "Archive" - Archived emails

        ACTION EXAMPLES:
        - "draft" - Create a draft (default)
        - "send" - Send immediately

        Reply *only* with valid JSON. Example:
        {
        "subject": "...",
        "recipient": "...",   // email address or name
        "body": "...",        // email body content
        "attachments": [],    // optional list of attachments
        "folder": "Work",     // optional: target folder
        "priority": "normal", // optional: "high", "medium", "low"
        "action": "draft",    // optional: "draft" or "send"
        "missing_fields": ["recipient", ...], // only include required fields that are missing
        "confirmation_message": "..."
        }
        If there are any current known details, merge them with the JSON that you will return.
        """

        user_prompt = f"User message: {message}"
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        if pending_changes:
            messages.append({
                "role": "assistant",
                "content": f"Current known details (JSON): {json.dumps(pending_changes)}"
            })

        response = self.openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            temperature=0.4
        )

        content = response.choices[0].message.content.strip()
        
        try:
            # Debug: Print the raw LLM response
            print(f"LLM raw response for email compose: {content}")
            
            # Clean the response - remove code blocks if present
            if content.startswith('```'):
                content = content.split('```')[1]  # Remove first code block
                if content.startswith('json'):
                    content = content[4:]  # Remove 'json' marker
                content = content.strip()
            
            # Remove any trailing code blocks
            if content.endswith('```'):
                content = content[:-3].strip()
            
            data = json.loads(content)
            data["type"] = "email_compose"
            print(f"Email compose proposal: {data}")
            
            # Only show accept/deny if all required fields are present
            missing_fields = data.get("missing_fields", [])
            show_accept_deny = len(missing_fields) == 0
            
            # Format current details for display
            current_details = self.format_email_details(data)
            confirmation_message = data["confirmation_message"]
            
            if current_details:
                confirmation_message += f"\n\n---\n**📋 Current Details:**\n{current_details}\n---"
            
            return confirmation_message, data, show_accept_deny
        except Exception as e:
            print(f"Error parsing email compose JSON: {e}")
            print(f"Raw content that failed to parse: {repr(content)}")
            return f"Sorry, I couldn't parse the email details. Could you please provide the email information again?", None, False

    async def send_email_immediately(self, subject: str, recipient: str, body: str, attachments: List[str] = None) -> str:
        """Send an email immediately (not as draft)"""
        try:
            if self.email_service.provider == "gmail":
                return await self.send_gmail_email(subject, recipient, body, attachments)
            else:
                # For Outlook, you'd implement similar logic
                raise NotImplementedError("Outlook immediate sending not implemented yet")
        except Exception as e:
            print(f"Error sending email immediately: {e}")
            raise e
    
    async def manage_drafts(self, message: str) -> Tuple[str, dict, bool]:
        """Manage email drafts"""
        try:
            # Get existing drafts
            drafts = await self.get_drafts()
            
            if not drafts:
                return "No email drafts found.", None, False
            
            # Format drafts list
            drafts_list = []
            for i, draft in enumerate(drafts, 1):
                drafts_list.append(f"{i}. **{draft.get('subject', 'No subject')}**")
                drafts_list.append(f"   To: {draft.get('to', 'No recipient')}")
                drafts_list.append(f"   Created: {draft.get('date', 'Unknown')}")
                drafts_list.append("")
            
            response_text = f"**📝 Email Drafts ({len(drafts)} found):**\n\n{''.join(drafts_list)}"
            
            return response_text, {
                "type": "email_drafts",
                "drafts": drafts,
                "count": len(drafts)
            }, False
            
        except Exception as e:
            return f"Sorry, I couldn't get your drafts: {str(e)}", None, False
    
    async def schedule_email(self, message: str, pending_changes: dict = None) -> Tuple[str, dict, bool]:
        """Schedule an email for later sending"""
        system_prompt = """
        Extract email scheduling details from the user's input. Include:
        - subject, recipient, body (required)
        - scheduled_time (when to send)
        - folder (optional)
        
        Return JSON with all details and confirmation message.
        """
        
        user_prompt = f"User message: {message}"
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        if pending_changes:
            messages.append({
                "role": "assistant",
                "content": f"Current known details (JSON): {json.dumps(pending_changes)}"
            })

        response = self.openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            temperature=0.4
        )

        content = response.choices[0].message.content.strip()
        
        try:
            # Debug: Print the raw LLM response
            print(f"LLM raw response for email schedule: {content}")
            
            # Clean the response - remove code blocks if present
            if content.startswith('```'):
                content = content.split('```')[1]  # Remove first code block
                if content.startswith('json'):
                    content = content[4:]  # Remove 'json' marker
                content = content.strip()
            
            # Remove any trailing code blocks
            if content.endswith('```'):
                content = content[:-3].strip()
            
            data = json.loads(content)
            data["type"] = "email_schedule"
            
            # Only show accept/deny if all required fields are present
            missing_fields = data.get("missing_fields", [])
            show_accept_deny = len(missing_fields) == 0
            
            confirmation_message = data["confirmation_message"]
            if data.get("scheduled_time"):
                confirmation_message += f"\n\n📅 **Scheduled for:** {data['scheduled_time']}"
            
            return confirmation_message, data, show_accept_deny
        except Exception as e:
            print(f"Error parsing email schedule JSON: {e}")
            print(f"Raw content that failed to parse: {repr(content)}")
            return f"Sorry, I couldn't parse the scheduling details: {str(e)}", None, False

    # Helper methods for email operations
    async def get_recent_emails(self, limit: int = 10) -> List[Dict]:
        """Get recent emails"""
        if self.email_service.provider == "gmail":
            return await self.get_gmail_recent_emails(limit)
        else:
            return await self.get_outlook_recent_emails(limit)
    
    async def get_priority_emails_list(self, limit: int = 15) -> List[Dict]:
        """Get priority emails"""
        if self.email_service.provider == "gmail":
            return await self.get_gmail_priority_emails(limit)
        else:
            return await self.get_outlook_priority_emails(limit)
    
    async def create_folder(self, folder_name: str) -> str:
        """Create a new folder/label"""
        if self.email_service.provider == "gmail":
            return await self.create_gmail_label(folder_name)
        else:
            return await self.create_outlook_folder(folder_name)
    
    async def auto_organize_emails(self) -> Dict:
        """Auto-organize emails based on content"""
        # This would implement smart categorization
        return {"count": 0, "folders": 0}
    
    async def search_emails_by_query(self, query: str, limit: int = 10) -> List[Dict]:
        """Search emails by query"""
        if self.email_service.provider == "gmail":
            return await self.search_gmail_emails(query, limit)
        else:
            return await self.search_outlook_emails(query, limit)
    
    async def get_email_by_id(self, email_id: str) -> Dict:
        """Get full email content by ID"""
        if self.email_service.provider == "gmail":
            return await self.get_gmail_email_by_id(email_id)
        else:
            return await self.get_outlook_email_by_id(email_id)
    
    async def get_drafts(self) -> List[Dict]:
        """Get email drafts"""
        if self.email_service.provider == "gmail":
            return await self.get_gmail_drafts()
        else:
            return await self.get_outlook_drafts()
    
    def format_email_details(self, data: Dict) -> str:
        """Format email details for display"""
        details = []
        
        if data.get("subject"):
            details.append(f"**Subject:** {data['subject']}")
        if data.get("recipient"):
            details.append(f"**To:** {data['recipient']}")
        if data.get("body"):
            body_preview = data['body'][:100] + "..." if len(data['body']) > 100 else data['body']
            details.append(f"**Body:** {body_preview}")
        if data.get("folder"):
            details.append(f"**Folder:** {data['folder']}")
        if data.get("priority"):
            details.append(f"**Priority:** {data['priority']}")
        if data.get("attachments"):
            details.append(f"**Attachments:** {len(data['attachments'])} file(s)")
        
        return "\n".join(details)

    # Gmail-specific methods
    async def get_gmail_recent_emails(self, limit: int) -> List[Dict]:
        """Get recent emails from Gmail"""
        try:
            results = self.email_service.client.users().messages().list(
                userId='me', 
                maxResults=limit,
                labelIds=['INBOX']
            ).execute()
            
            messages = results.get('messages', [])
            emails = []
            
            for msg in messages:
                msg_detail = self.email_service.client.users().messages().get(
                    userId='me', id=msg['id'], format='metadata'
                ).execute()
                
                headers = msg_detail['payload']['headers']
                subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No subject')
                sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown')
                date = next((h['value'] for h in headers if h['name'] == 'Date'), 'Unknown')
                
                emails.append({
                    'id': msg['id'],
                    'subject': subject,
                    'from': sender,
                    'date': date,
                    'snippet': msg_detail.get('snippet', '')
                })
            
            return emails
        except Exception as e:
            print(f"Error getting Gmail emails: {e}")
            return []
    
    async def get_gmail_priority_emails(self, limit: int) -> List[Dict]:
        """Get priority emails from Gmail"""
        try:
            results = self.email_service.client.users().messages().list(
                userId='me', 
                maxResults=limit,
                labelIds=['IMPORTANT', 'INBOX']
            ).execute()
            
            return await self.get_gmail_recent_emails(limit)
        except Exception as e:
            print(f"Error getting Gmail priority emails: {e}")
            return []
    
    async def create_gmail_label(self, label_name: str) -> str:
        """Create a new Gmail label"""
        try:
            label_data = {
                'name': label_name,
                'labelListVisibility': 'labelShow',
                'messageListVisibility': 'show'
            }
            response = self.email_service.client.users().labels().create(
                userId='me', body=label_data
            ).execute()
            return response['id']
        except Exception as e:
            print(f"Error creating Gmail label: {e}")
            return None
    
    async def search_gmail_emails(self, query: str, limit: int) -> List[Dict]:
        """Search Gmail emails"""
        try:
            results = self.email_service.client.users().messages().list(
                userId='me', 
                maxResults=limit,
                q=query
            ).execute()
            
            messages = results.get('messages', [])
            emails = []
            
            for msg in messages:
                msg_detail = self.email_service.client.users().messages().get(
                    userId='me', id=msg['id'], format='metadata'
                ).execute()
                
                headers = msg_detail['payload']['headers']
                subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No subject')
                sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown')
                date = next((h['value'] for h in headers if h['name'] == 'Date'), 'Unknown')
                
                emails.append({
                    'id': msg['id'],
                    'subject': subject,
                    'from': sender,
                    'date': date,
                    'snippet': msg_detail.get('snippet', '')
                })
            
            return emails
        except Exception as e:
            print(f"Error searching Gmail emails: {e}")
            return []
    
    async def get_gmail_email_by_id(self, email_id: str) -> Dict:
        """Get full Gmail email content by ID"""
        try:
            msg_detail = self.email_service.client.users().messages().get(
                userId='me', id=email_id, format='full'
            ).execute()
            
            headers = msg_detail['payload']['headers']
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No subject')
            sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown')
            date = next((h['value'] for h in headers if h['name'] == 'Date'), 'Unknown')
            
            # Extract body content
            body = self._extract_email_body(msg_detail['payload'])
            
            return {
                'id': email_id,
                'subject': subject,
                'from': sender,
                'date': date,
                'body': body,
                'snippet': msg_detail.get('snippet', '')
            }
        except Exception as e:
            print(f"Error getting Gmail email by ID: {e}")
            return None
    
    def _extract_email_body(self, payload: Dict) -> str:
        """Extract email body from Gmail payload"""
        try:
            if 'body' in payload and payload['body'].get('data'):
                # Simple text email
                return base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8')
            elif 'parts' in payload:
                # Multipart email
                for part in payload['parts']:
                    if part.get('mimeType') == 'text/plain':
                        if part['body'].get('data'):
                            return base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                    elif part.get('mimeType') == 'text/html':
                        if part['body'].get('data'):
                            # For HTML emails, return a simple text version
                            html_content = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                            # Simple HTML to text conversion (you might want to use a proper HTML parser)
                            return html_content.replace('<br>', '\n').replace('<p>', '\n').replace('</p>', '\n')
            return "No readable content found"
        except Exception as e:
            print(f"Error extracting email body: {e}")
            return "Error reading email content"
    
    async def get_gmail_drafts(self) -> List[Dict]:
        """Get Gmail drafts"""
        try:
            results = self.email_service.client.users().drafts().list(
                userId='me'
            ).execute()
            
            drafts = results.get('drafts', [])
            draft_list = []
            
            for draft in drafts:
                draft_detail = self.email_service.client.users().drafts().get(
                    userId='me', id=draft['id']
                ).execute()
                
                message = draft_detail['message']
                headers = message['payload']['headers']
                subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No subject')
                to = next((h['value'] for h in headers if h['name'] == 'To'), 'No recipient')
                
                draft_list.append({
                    'id': draft['id'],
                    'subject': subject,
                    'to': to,
                    'date': draft_detail.get('internalDate', 'Unknown')
                })
            
            return draft_list
        except Exception as e:
            print(f"Error getting Gmail drafts: {e}")
            return []

    async def create_gmail_draft(self, subject: str, recipient: str, body: str, attachments: List[str] = None) -> str:
        """Create a Gmail draft"""
        try:
            # Create the email message
            message = MIMEMultipart()
            message['to'] = recipient
            message['subject'] = subject
            
            # Add body
            text_part = MIMEText(body, 'plain')
            message.attach(text_part)
            
            # Add attachments if any
            if attachments:
                for attachment_path in attachments:
                    if os.path.exists(attachment_path):
                        with open(attachment_path, 'rb') as f:
                            attachment = MIMEText(f.read(), 'base64')
                            attachment.add_header('Content-Disposition', 'attachment', filename=os.path.basename(attachment_path))
                            message.attach(attachment)
            
            # Encode the message
            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
            
            # Create draft
            draft = self.email_service.client.users().drafts().create(
                userId='me',
                body={'message': {'raw': raw_message}}
            ).execute()
            
            return draft['id']
        except Exception as e:
            print(f"Error creating Gmail draft: {e}")
            raise e

    async def send_gmail_email(self, subject: str, recipient: str, body: str, attachments: List[str] = None) -> str:
        """Send a Gmail email"""
        try:
            # Create the email message
            message = MIMEMultipart()
            message['to'] = recipient
            message['subject'] = subject
            
            # Add body
            text_part = MIMEText(body, 'plain')
            message.attach(text_part)
            
            # Add attachments if any
            if attachments:
                for attachment_path in attachments:
                    if os.path.exists(attachment_path):
                        with open(attachment_path, 'rb') as f:
                            attachment = MIMEText(f.read(), 'base64')
                            attachment.add_header('Content-Disposition', 'attachment', filename=os.path.basename(attachment_path))
                            message.attach(attachment)
            
            # Encode the message
            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
            
            # Send email
            sent_message = self.email_service.client.users().messages().send(
                userId='me',
                body={'raw': raw_message}
            ).execute()
            
            return sent_message['id']
        except Exception as e:
            print(f"Error sending Gmail email: {e}")
            raise e

    async def move_emails_to_folder(self, email_ids: List[str], folder_name: str) -> bool:
        """Move emails to a specific folder/label"""
        try:
            # First, get or create the label
            label_id = await self.get_or_create_gmail_label(folder_name)
            
            # Add the label to the emails
            self.email_service.client.users().messages().modify(
                userId='me',
                body={'addLabelIds': [label_id]},
                id=','.join(email_ids)
            ).execute()
            
            return True
        except Exception as e:
            print(f"Error moving emails to folder: {e}")
            return False

    async def get_or_create_gmail_label(self, label_name: str) -> str:
        """Get existing label or create new one"""
        try:
            # First, try to find existing label
            labels = self.email_service.client.users().labels().list(userId='me').execute()
            
            for label in labels.get('labels', []):
                if label['name'].lower() == label_name.lower():
                    return label['id']
            
            # If not found, create new label
            return await self.create_gmail_label(label_name)
        except Exception as e:
            print(f"Error getting/creating Gmail label: {e}")
            raise e

    async def delete_gmail_draft(self, draft_id: str) -> bool:
        """Delete a Gmail draft"""
        try:
            self.email_service.client.users().drafts().delete(
                userId='me', id=draft_id
            ).execute()
            return True
        except Exception as e:
            print(f"Error deleting Gmail draft: {e}")
            return False

    async def update_gmail_draft(self, draft_id: str, subject: str = None, recipient: str = None, body: str = None) -> bool:
        """Update a Gmail draft"""
        try:
            # Get current draft
            draft = self.email_service.client.users().drafts().get(
                userId='me', id=draft_id
            ).execute()
            
            message = draft['message']
            headers = message['payload']['headers']
            
            # Update headers if provided
            if subject:
                for header in headers:
                    if header['name'] == 'Subject':
                        header['value'] = subject
                        break
                else:
                    headers.append({'name': 'Subject', 'value': subject})
            
            if recipient:
                for header in headers:
                    if header['name'] == 'To':
                        header['value'] = recipient
                        break
                else:
                    headers.append({'name': 'To', 'value': recipient})
            
            # Update body if provided
            if body:
                # This is a simplified version - in practice, you'd need to handle MIME parts properly
                message['payload']['body']['data'] = base64.urlsafe_b64encode(body.encode('utf-8')).decode('utf-8')
            
            # Update the draft
            self.email_service.client.users().drafts().update(
                userId='me', id=draft_id, body=draft
            ).execute()
            
            return True
        except Exception as e:
            print(f"Error updating Gmail draft: {e}")
            return False

    # Outlook-specific methods
    async def get_outlook_recent_emails(self, limit: int) -> List[Dict]:
        """Get recent emails from Outlook"""
        try:
            response = self.email_service.client.get(f"/me/messages?$top={limit}&$orderby=receivedDateTime desc")
            messages = response.json()['value']
            
            emails = []
            for msg in messages:
                emails.append({
                    'id': msg['id'],
                    'subject': msg.get('subject', 'No subject'),
                    'from': msg.get('from', {}).get('emailAddress', {}).get('address', 'Unknown'),
                    'date': msg.get('receivedDateTime', 'Unknown'),
                    'snippet': msg.get('bodyPreview', '')
                })
            
            return emails
        except Exception as e:
            print(f"Error getting Outlook emails: {e}")
            return []
    
    async def get_outlook_priority_emails(self, limit: int) -> List[Dict]:
        """Get priority emails from Outlook"""
        try:
            response = self.email_service.client.get(f"/me/messages?$top={limit}&$filter=importance eq 'high'&$orderby=receivedDateTime desc")
            messages = response.json()['value']
            
            emails = []
            for msg in messages:
                emails.append({
                    'id': msg['id'],
                    'subject': msg.get('subject', 'No subject'),
                    'from': msg.get('from', {}).get('emailAddress', {}).get('address', 'Unknown'),
                    'date': msg.get('receivedDateTime', 'Unknown'),
                    'snippet': msg.get('bodyPreview', ''),
                    'priority': msg.get('importance', 'normal')
                })
            
            return emails
        except Exception as e:
            print(f"Error getting Outlook priority emails: {e}")
            return []
    
    async def create_outlook_folder(self, folder_name: str) -> str:
        """Create a new Outlook folder"""
        try:
            folder_data = {
                "displayName": folder_name,
                "parentFolderId": "inbox"
            }
            response = self.email_service.client.post("/me/mailFolders", json=folder_data)
            return response.json()['id']
        except Exception as e:
            print(f"Error creating Outlook folder: {e}")
            return None
    
    async def search_outlook_emails(self, query: str, limit: int) -> List[Dict]:
        """Search Outlook emails"""
        try:
            response = self.email_service.client.get(f"/me/messages?$search=\"{query}\"&$top={limit}")
            messages = response.json()['value']
            
            emails = []
            for msg in messages:
                emails.append({
                    'id': msg['id'],
                    'subject': msg.get('subject', 'No subject'),
                    'from': msg.get('from', {}).get('emailAddress', {}).get('address', 'Unknown'),
                    'date': msg.get('receivedDateTime', 'Unknown'),
                    'snippet': msg.get('bodyPreview', '')
                })
            
            return emails
        except Exception as e:
            print(f"Error searching Outlook emails: {e}")
            return []
    
    async def get_outlook_email_by_id(self, email_id: str) -> Dict:
        """Get full Outlook email content by ID"""
        try:
            response = self.email_service.client.get(f"/me/messages/{email_id}")
            msg = response.json()
            
            headers = msg['headers']
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No subject')
            sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown')
            date = next((h['value'] for h in headers if h['name'] == 'Date'), 'Unknown')
            
            # Extract body content
            body = self._extract_outlook_email_body(msg['body'])
            
            return {
                'id': email_id,
                'subject': subject,
                'from': sender,
                'date': date,
                'body': body,
                'snippet': msg.get('bodyPreview', '')
            }
        except Exception as e:
            print(f"Error getting Outlook email by ID: {e}")
            return None
    
    def _extract_outlook_email_body(self, payload: Dict) -> str:
        """Extract email body from Outlook payload"""
        try:
            if 'content' in payload:
                # Simple text email
                return payload['content']
            elif 'parts' in payload:
                # Multipart email
                for part in payload['parts']:
                    if part.get('contentType') == 'text/plain':
                        if part['content'].get('data'):
                            return base64.urlsafe_b64decode(part['content']['data']).decode('utf-8')
                    elif part.get('contentType') == 'text/html':
                        if part['content'].get('data'):
                            # For HTML emails, return a simple text version
                            html_content = base64.urlsafe_b64decode(part['content']['data']).decode('utf-8')
                            # Simple HTML to text conversion (you might want to use a proper HTML parser)
                            return html_content.replace('<br>', '\n').replace('<p>', '\n').replace('</p>', '\n')
            return "No readable content found"
        except Exception as e:
            print(f"Error extracting Outlook email body: {e}")
            return "Error reading email content"
    
    async def get_outlook_drafts(self) -> List[Dict]:
        """Get Outlook drafts"""
        try:
            response = self.email_service.client.get("/me/messages?$filter=isDraft eq true")
            messages = response.json()['value']
            
            drafts = []
            for msg in messages:
                drafts.append({
                    'id': msg['id'],
                    'subject': msg.get('subject', 'No subject'),
                    'to': msg.get('toRecipients', [{}])[0].get('emailAddress', {}).get('address', 'No recipient'),
                    'date': msg.get('createdDateTime', 'Unknown')
                })
            
            return drafts
        except Exception as e:
            print(f"Error getting Outlook drafts: {e}")
            return []

# Factory function to create email handler
def create_email_handler(provider: str = "gmail", access_token: str = None, refresh_token: str = None, client_id: str = None, client_secret: str = None) -> EmailIntentHandler:
    """Create an email handler for the specified provider, using OAuth tokens for Gmail"""
    email_service = EmailService(provider)
    if provider == "gmail":
        if not all([access_token, refresh_token, client_id, client_secret]):
            raise ValueError("Gmail requires access_token, refresh_token, client_id, and client_secret")
        email_service.setup_gmail_with_token(access_token, refresh_token, client_id, client_secret)
    return EmailIntentHandler(email_service) 