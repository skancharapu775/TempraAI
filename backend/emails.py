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

# Gmail API setup
GMAIL_SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

# Microsoft Graph API setup
MS_GRAPH_SCOPES = ['https://graph.microsoft.com/Mail.ReadWrite']

class EmailService:
    def __init__(self, provider: str = "gmail"):
        self.provider = provider
        self.client = None
        self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        if provider == "gmail":
            self.setup_gmail()
        elif provider == "outlook":
            self.setup_outlook()
    
    def setup_gmail(self):
        """Setup Gmail API client"""
        creds = None
        if os.path.exists('gmail_token.json'):
            creds = Credentials.from_authorized_user_file('gmail_token.json', GMAIL_SCOPES)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file('gmail_credentials.json', GMAIL_SCOPES)
                creds = flow.run_local_server(port=0)
            
            with open('gmail_token.json', 'w') as token:
                token.write(creds.to_json())
        
        self.client = build('gmail', 'v1', credentials=creds)
    
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
        
        if email_function == "summarize":
            return await self.summarize_emails(message)
        elif email_function == "priority":
            return await self.get_priority_emails(message)
        elif email_function == "organize":
            return await self.organize_emails(message)
        elif email_function == "search":
            return await self.search_emails(message)
        elif email_function == "compose":
            return await self.compose_email(message, pending_changes)
        elif email_function == "draft":
            return await self.manage_drafts(message)
        elif email_function == "schedule":
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
        """Organize emails into folders/labels"""
        try:
            # Extract organization request from message
            organization_prompt = f"""
            Extract the organization details from this message: "{message}"
            
            Return JSON with:
            - "action": "create_folder", "move_emails", or "auto_organize"
            - "folder_name": name of folder to create or use
            - "criteria": criteria for organizing (if auto_organize)
            - "email_count": number of emails to organize (if specified)
            
            Example: {{"action": "create_folder", "folder_name": "Work Projects"}}
            """
            
            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": organization_prompt}],
                max_tokens=200,
                temperature=0.3
            )
            
            try:
                org_data = json.loads(response.choices[0].message.content.strip())
            except:
                org_data = {"action": "auto_organize", "folder_name": "Organized"}
            
            if org_data["action"] == "create_folder":
                folder_name = org_data.get("folder_name", "New Folder")
                folder_id = await self.create_folder(folder_name)
                
                return f"✅ Created new folder: **{folder_name}**", {
                    "type": "folder_created",
                    "folder_name": folder_name,
                    "folder_id": folder_id
                }, False
            
            elif org_data["action"] == "auto_organize":
                # Auto-organize emails based on content
                organized = await self.auto_organize_emails()
                
                return f"✅ Organized {organized['count']} emails into {organized['folders']} folders", {
                    "type": "emails_organized",
                    "organized_count": organized['count'],
                    "folders_used": organized['folders']
                }, False
            
            else:
                return "I can help you organize emails. Try saying 'Create a Work folder' or 'Organize my emails automatically'", None, False
                
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
                search_data = json.loads(response.choices[0].message.content.strip())
            except:
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
        OPTIONAL FIELDS: attachments, folder, priority

        FOLDER EXAMPLES:
        - "Work" - Work-related emails
        - "Personal" - Personal emails  
        - "Projects" - Project-specific emails
        - "Inbox" - Default folder
        - "Archive" - Archived emails

        Reply *only* with valid JSON. Example:
        {
        "subject": "...",
        "recipient": "...",   // email address or name
        "body": "...",        // email body content
        "attachments": [],    // optional list of attachments
        "folder": "Work",     // optional: target folder
        "priority": "normal", // optional: "high", "medium", "low"
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
            return f"Sorry, I couldn't parse the email details. Could you please provide the email information again?", None, False
    
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
            
            return await self.get_gmail_recent_emails(limit)
        except Exception as e:
            print(f"Error searching Gmail emails: {e}")
            return []
    
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
def create_email_handler(provider: str = "gmail") -> EmailIntentHandler:
    """Create an email handler for the specified provider"""
    email_service = EmailService(provider)
    return EmailIntentHandler(email_service) 