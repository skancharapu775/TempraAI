import json
from typing import Any, Callable, Dict, Tuple, List
from emails import create_email_handler
from scheduling import create_schedule_handler
import requests
import os
import asyncio
from firebase import db
from uuid import uuid4
import datetime

"""
Advanced tool-calling agent for multi-step, adaptive LLM workflows.
The LLM is given a list of tools and can call them one at a time, receiving the result after each call and deciding what to do next.
"""

class Tool:
    def __init__(self, name: str, description: str, func: Callable, parameters: dict = None):
        self.name = name
        self.description = description
        self.func = func
        self.parameters = parameters or {"type": "object", "properties": {}}

    def to_openai_function(self):
        # For OpenAI function calling schema
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }

# --- Basic Example Tool Functions ---

async def add_reminder(title: str, due_date: str = None, due_time: str = None, **kwargs):
    msg = f"[Reminder] '{title}'"
    if due_date:
        msg += f" on {due_date}"
    if due_time:
        msg += f" at {due_time}"
    return f"Created reminder: {msg}"

async def add_todo(title: str, email: str, due_date: str = None, **kwargs):
    todo_data = {
        "title": title,
        "completed": False,
        "id": str(uuid4())
    }
    if due_date:
        todo_data["due_date"] = due_date
    db.collection("todos").document(email).collection("todos").add(todo_data)
    msg = f"[Todo] '{title}'"
    if due_date:
        msg += f" (due {due_date})"
    return f"✅ Todo added for {email}: {msg}"

async def search_email(query: str, limit: int = 10, access_token: str = None, refresh_token: str = None, **kwargs):
    """Search emails using Gmail API"""
    try:
        # Create email handler with provided credentials
        email_handler = create_email_handler(
            provider="gmail",
            access_token=access_token,
            refresh_token=refresh_token,
            client_id="1090386684531-io9ttj5vpiaj6td376v2vs8t3htknvnn.apps.googleusercontent.com",
            client_secret="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"
        )
        
        # Search emails
        results = await email_handler.search_emails_by_query(query, limit)
        
        if not results:
            return f"No emails found for query: '{query}'"
        
        # Format results
        formatted_results = []
        for i, email in enumerate(results, 1):
            formatted_results.append(f"{i}. Subject: {email.get('subject', 'No subject')}")
            formatted_results.append(f"   From: {email.get('from', 'Unknown')}")
            formatted_results.append(f"   Date: {email.get('date', 'Unknown')}")
            formatted_results.append(f"   Snippet: {email.get('snippet', '')[:100]}...")
            formatted_results.append("")
        
        return f"Found {len(results)} emails for '{query}':\n\n" + "\n".join(formatted_results)
        
    except Exception as e:
        return f"Error searching emails: {str(e)}"

async def search_google(query: str, num_results: int = 5, **kwargs):
    """Search Google using a web search API"""
    try:
        # DuckDuckGo Instant Answer API (free, no API key)
        url = "https://api.duckduckgo.com/"
        params = {
            'q': query,
            'format': 'json',
            'no_html': '1',
            'skip_disambig': '1'
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        results = []
        
        # Get instant answer if available
        if data.get('Abstract'):
            results.append(f"📖 **Instant Answer:** {data['Abstract']}")
            if data.get('AbstractURL'):
                results.append(f"Source: {data['AbstractURL']}")
            results.append("")
        
        # Get related topics
        if data.get('RelatedTopics'):
            results.append("🔍 **Related Information:**")
            for i, topic in enumerate(data['RelatedTopics'][:num_results], 1):
                if isinstance(topic, dict) and topic.get('Text'):
                    results.append(f"{i}. {topic['Text'][:200]}...")
                elif isinstance(topic, str):
                    results.append(f"{i}. {topic[:200]}...")
            results.append("")
        
        # If no results from DuckDuckGo, provide a fallback
        if not results:
            results.append(f"🔍 **Search Results for '{query}':**")
            results.append("No specific results found. Consider:")
            results.append("• Refining your search terms")
            results.append("• Using more specific keywords")
            results.append("• Checking spelling")
        
        return "\n".join(results)
        
    except requests.RequestException as e:
        return f"Error performing web search: Network error - {str(e)}"
    except Exception as e:
        return f"Error performing web search: {str(e)}"

async def search_calendar(query: str, access_token: str = None, refresh_token: str = None, **kwargs):
    """Search Google Calendar for events matching a query string."""
    try:
        schedule_handler = create_schedule_handler(
            access_token=access_token,
            refresh_token=refresh_token,
            client_id="1090386684531-io9ttj5vpiaj6td376v2vs8t3htknvnn.apps.googleusercontent.com",
            client_secret="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"
        )
        # Use the handler's service to list events
        events_result = schedule_handler.schedule_service.client.events().list(
            calendarId='primary',
            q=query,
            maxResults=10,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        events = events_result.get('items', [])
        if not events:
            return f"No calendar events found for query: '{query}'"
        formatted = []
        for i, event in enumerate(events, 1):
            summary = event.get('summary', 'No title')
            start = event.get('start', {}).get('dateTime', event.get('start', {}).get('date', ''))
            end = event.get('end', {}).get('dateTime', event.get('end', {}).get('date', ''))
            formatted.append(f"{i}. {summary}\n   Start: {start}\n   End: {end}")
        return f"Found {len(events)} calendar events for '{query}':\n\n" + "\n\n".join(formatted)
    except Exception as e:
        return f"Error searching calendar: {str(e)}"

async def add_calendar_event(title: str, start_time: str, end_time: str, access_token: str = None, refresh_token: str = None, attendees: list = None, **kwargs):
    """Add a new event to Google Calendar."""
    try:
        schedule_handler = create_schedule_handler(
            access_token=access_token,
            refresh_token=refresh_token,
            client_id="1090386684531-io9ttj5vpiaj6td376v2vs8t3htknvnn.apps.googleusercontent.com",
            client_secret="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"
        )
        event = {
            'summary': title,
            'start': {
                'dateTime': start_time,
                'timeZone': 'America/New_York',
            },
            'end': {
                'dateTime': end_time,
                'timeZone': 'America/New_York',
            },
        }
        if attendees:
            event['attendees'] = [{'email': email} for email in attendees]
        created_event = schedule_handler.schedule_service.client.events().insert(calendarId='primary', body=event).execute()
        return f"Event '{title}' added to calendar from {start_time} to {end_time}. Link: {created_event.get('htmlLink', 'N/A')}"
    except Exception as e:
        return f"Error adding calendar event: {str(e)}"



async def note_email(subject: str, body: str, access_token: str = None, refresh_token: str = None, **kwargs):
    """Send a note email to the user themselves"""
    try:
        # Get user email from kwargs
        user_email = kwargs.get('user_email')
        if not user_email:
            return "Error: user_email is required to send note email"
        
        # Create email handler with provided credentials
        email_handler = create_email_handler(
            provider="gmail",
            access_token=access_token,
            refresh_token=refresh_token,
            client_id="1090386684531-io9ttj5vpiaj6td376v2vs8t3htknvnn.apps.googleusercontent.com",
            client_secret="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"
        )
        
        # Send note email to self
        result = await email_handler.send_gmail_email(
            subject=subject,
            recipient=user_email,
            body=body
        )
        
        return f"📝 Note email sent to yourself ({user_email}):\n\n**Subject:** {subject}\n\n**Body:**\n{body}"
        
    except Exception as e:
        return f"Error sending note email: {str(e)}"

async def get_calendar_events(message: str, access_token: str = None, refresh_token: str = None, **kwargs):
    """Get calendar events for a specific time period based on natural language description."""
    try:
        # Create schedule handler with provided credentials
        schedule_handler = create_schedule_handler(
            access_token=access_token,
            refresh_token=refresh_token,
            client_id="1090386684531-io9ttj5vpiaj6td376v2vs8t3htknvnn.apps.googleusercontent.com",
            client_secret="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"
        )
        
        # Get events using the handler's get_events method
        events = await schedule_handler.get_events(message)
        
        if not events:
            return f"No calendar events found for the specified time period."
        
        # Format the events for display
        formatted_events = []
        for i, event in enumerate(events, 1):
            formatted_events.append(f"{i}. **{event['title']}**")
            formatted_events.append(f"   📅 Start: {event['start_time']}")
            formatted_events.append(f"   📅 End: {event['end_time']}")
            if event.get('attendees'):
                formatted_events.append(f"   👥 Attendees: {', '.join(event['attendees'])}")
            if event.get('location'):
                formatted_events.append(f"   📍 Location: {event['location']}")
            if event.get('description'):
                formatted_events.append(f"   📝 Description: {event['description'][:100]}...")
            formatted_events.append("")
        
        return f"Found {len(events)} calendar events:\n\n" + "\n".join(formatted_events)
        
    except Exception as e:
        return f"Error getting calendar events: {str(e)}"

async def get_email_metadata(limit: int = 10, access_token: str = None, refresh_token: str = None, **kwargs):
    """Get recent email metadata (IDs, subjects, senders) without search query."""
    try:
        # Create email handler with provided credentials
        email_handler = create_email_handler(
            provider="gmail",
            access_token=access_token,
            refresh_token=refresh_token,
            client_id="1090386684531-io9ttj5vpiaj6td376v2vs8t3htknvnn.apps.googleusercontent.com",
            client_secret="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"
        )
        
        # Get recent emails
        emails = await email_handler.get_gmail_recent_emails(limit)
        
        if not emails:
            return "No recent emails found."
        
        # Format the email metadata
        formatted_emails = []
        for i, email in enumerate(emails, 1):
            formatted_emails.append(f"{i}. **{email.get('subject', 'No subject')}**")
            formatted_emails.append(f"   📧 From: {email.get('from', 'Unknown')}")
            formatted_emails.append(f"   📅 Date: {email.get('date', 'Unknown')}")
            formatted_emails.append(f"   🆔 ID: {email.get('id', 'Unknown')}")
            formatted_emails.append(f"   📝 Snippet: {email.get('snippet', '')[:100]}...")
            formatted_emails.append("")
        
        return f"Found {len(emails)} recent emails:\n\n" + "\n".join(formatted_emails)
        
    except Exception as e:
        return f"Error getting email metadata: {str(e)}"

async def get_email_content(email_id: str, access_token: str = None, refresh_token: str = None, **kwargs):
    """Get the full content of an email by its ID."""
    try:
        # Create email handler with provided credentials
        email_handler = create_email_handler(
            provider="gmail",
            access_token=access_token,
            refresh_token=refresh_token,
            client_id="1090386684531-io9ttj5vpiaj6td376v2vs8t3htknvnn.apps.googleusercontent.com",
            client_secret="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"
        )
        
        # Get the full email content
        email = await email_handler.get_gmail_email_by_id(email_id)
        
        if not email:
            return f"Email with ID '{email_id}' not found or could not be retrieved."
        
        # Format the email content
        formatted_email = []
        formatted_email.append(f"**📧 Email Content**")
        formatted_email.append(f"")
        formatted_email.append(f"**Subject:** {email.get('subject', 'No subject')}")
        formatted_email.append(f"**From:** {email.get('from', 'Unknown')}")
        formatted_email.append(f"**Date:** {email.get('date', 'Unknown')}")
        formatted_email.append(f"**ID:** {email.get('id', 'Unknown')}")
        formatted_email.append(f"")
        formatted_email.append(f"**Body:**")
        formatted_email.append(f"{email.get('body', 'No content available')}")
        
        return "\n".join(formatted_email)
        
    except Exception as e:
        return f"Error getting email content: {str(e)}"

# --- Tool-Calling Agent ---

async def select_required_tools(
    client: Any,
    message: str,
    all_tools: List[Tool],
    conversation_history: List[dict] = None
) -> List[Tool]:
    """
    Use LLM to determine which tools are needed for the user's request.
    This reduces token usage by only sending relevant tools to the main agent.
    """
    
    # Create a simple list of tool names and descriptions for selection
    tool_options = []
    for tool in all_tools:
        tool_options.append(f"- {tool.name}: {tool.description}")
    
    tool_list = "\n".join(tool_options)
    
    selection_prompt = f"""You are a tool selector. Based on the user's request, determine which tools are needed to complete the task.

Available tools:
{tool_list}

User request: "{message}"

Instructions:
1. Analyze what the user wants to accomplish
2. Select ONLY the tools that are necessary to complete the task
3. Do not select tools that are not needed
4. Return a JSON array of tool names only

Examples:
- User: "Add a couple reminders to call mom this week" → ["add_reminder"]
- User: "Search my emails for meeting requests and add calendar events for each" → ["search_email", "add_calendar_event"]
- User: "Find todos about project X and create reminders for them" → ["search_google", "add_reminder"]

Return ONLY a JSON array of tool names, like: ["tool1", "tool2"]"""

    messages = [{"role": "user", "content": selection_prompt}]
    
    # Add recent conversation context if available
    if conversation_history:
        recent_history = conversation_history[-2:]  # Only last 2 messages for context
        filtered_history = [
            msg for msg in recent_history
            if msg.get("content") is not None and msg.get("content").strip() != ""
        ]
        messages = filtered_history + messages
    
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",  # Use cheaper model for tool selection
            messages=messages,
            max_tokens=100,
            temperature=0.1
        )
        
        content = response.choices[0].message.content.strip()
        
        # Parse the JSON response
        try:
            # Clean the response - remove code blocks if present
            if content.startswith('```'):
                content = content.split('```')[1]
                if content.startswith('json'):
                    content = content[4:]
                content = content.strip()
            
            if content.endswith('```'):
                content = content[:-3].strip()
            
            selected_tool_names = json.loads(content)
            
            # Filter tools to only include selected ones
            selected_tools = [tool for tool in all_tools if tool.name in selected_tool_names]
            
            print(f"🔧 Tool selection: {selected_tool_names} -> {len(selected_tools)} tools selected")
            print(f"📋 Selected tools: {[tool.name for tool in selected_tools]}")
            return selected_tools
            
        except json.JSONDecodeError as e:
            print(f"Error parsing tool selection JSON: {e}")
            print(f"Raw content: {content}")
            # Fallback: return all tools if parsing fails
            return all_tools
            
    except Exception as e:
        print(f"Error in tool selection: {e}")
        # Fallback: return all tools if selection fails
        return all_tools

async def tool_calling_agent(
    client: Any,
    message: str,
    tools: List[Tool],
    max_steps: int = 3,  # Reduced from 8 to 3 to prevent runaway loops
    system_prompt: str = None,
    conversation_history: List[dict] = None,
    **kwargs
) -> Tuple[str, dict, bool]:
    """
    Advanced tool-calling agent for multi-step, adaptive LLM workflows.
    First selects required tools, then executes the workflow with only those tools.
    """
    
    # Step 1: Select only the required tools for this request
    required_tools = await select_required_tools(client, message, tools, conversation_history)
    
    # Step 2: Execute the agent with only the required tools
    return await execute_tool_calling_agent(
        client=client,
        message=message,
        tools=required_tools,
        max_steps=max_steps,
        system_prompt=system_prompt,
        conversation_history=conversation_history,
        **kwargs
    )

async def execute_tool_calling_agent(
    client: Any,
    message: str,
    tools: List[Tool],
    max_steps: int = 3,  # Reduced from 8 to 3 to prevent runaway loops
    system_prompt: str = None,
    conversation_history: List[dict] = None,
    **kwargs
) -> Tuple[str, dict, bool]:
    """
    Execute the tool-calling agent with the provided tools.
    This is the original agent logic, now separated from tool selection.
    """
    
    # Initialize conversation history
    history = conversation_history or []
    
    # Create tool list string for the prompt
    tool_list_str = ""
    for tool in tools:
        tool_list_str += f"- {tool.name}: {tool.description}\n"
        if tool.parameters and tool.parameters.get("properties"):
            for param_name, param_info in tool.parameters["properties"].items():
                param_desc = param_info.get("description", "")
                param_type = param_info.get("type", "")
                tool_list_str += f"  - {param_name} ({param_type}): {param_desc}\n"
        tool_list_str += "\n"

    if not system_prompt:
        today_str = datetime.datetime.now().strftime('%Y-%m-%d')
        system_prompt = (
            f"Today is {today_str}.\n"
            "You are an advanced assistant with access to the following tools. \n"
            "You may call one tool at a time, and after each call you will see the result. \n"
            "IMPORTANT: After each tool call, analyze the result and decide what to do next:\n"
            "- If the result contains useful information, use it to call another tool or provide a final answer\n"
            "- If the result shows no data found, try a different approach or ask the user for clarification\n"
            "- If you are done, reply with a final message to the user\n"
            "- If you need more clarification, ask the user\n"
            "You do NOT need to ask the user for access_token or refresh_token. These will be provided automatically to any tool that needs them.\n"
            "If you repeat the same tool call and arguments more than twice, stop and ask for clarification.\n"
            "When you want to use a tool, reply with a JSON object like:\n"
            '{"tool": "tool_name", "args": {...}}' + "\n"
            "When you are done, reply with:\n"
            '{"final": "your final message to the user"}' + "\n"
            "If you need more information from the user, reply with:\n"
            '{"final": "Could you clarify..."}' + "\n"
            "For email-related questions, you have two approaches:\n"
            "1. Use get_email_context to get recent emails as context, then analyze them directly\n"
            "2. Use search_email for specific queries, then get_email_content for full analysis\n"
            "Example workflow:\n"
            'User: "What actionable items do I have in my recent emails?"' + "\n"
            "1. Call get_email_context to get recent emails as context\n"
            "2. Analyze the email content directly to identify actionable items\n"
            "3. Use add_todo to create todos for each actionable item found\n"
            "4. Reply with a summary of what was found and created\n"
            "For finding actionable items in emails, use broad search terms like 'meeting', 'deadline', 'review', 'follow up', 'action required', 'please', 'need to', 'should', 'must', etc. Then analyze the full content to identify specific actionable items.\n"
            "Remember: You have access to the user's credentials automatically. Do not ask for them."
        )

    # Agent loop
    done = False
    steps = 0
    last_tool_result = None
    last_tool_call = None
    repeat_count = 0
    
    while not done and steps < max_steps:
        steps += 1
        messages = [
            {"role": "system", "content": system_prompt + "\n\nAvailable tools:\n" + tool_list_str}
        ]
        messages.extend(history)
        messages.append({"role": "user", "content": message})
        
        print(f"DEBUG: Sending {len(messages)} messages to LLM")
        print(f"DEBUG: System prompt length: {len(system_prompt + tool_list_str)} chars")
        print(f"DEBUG: History messages: {len(history)}")
        print(f"DEBUG: User message: {message}")
        
        # Get LLM response
        response = client.chat.completions.create(
            model="gpt-4",
            messages=messages,
            max_tokens=500,
            temperature=0.1
        )
        
        content = response.choices[0].message.content.strip()
        print(f"DEBUG: LLM response (step {steps}): {content}")
        
        # Log the current conversation state
        print(f"DEBUG: Current history length: {len(history)}")
        if history:
            print(f"DEBUG: Last history item: {history[-1]}")
        print(f"DEBUG: Last tool result: {last_tool_result}")
        
        # Parse the response
        try:
            # Try to parse as JSON
            if content.startswith('{') and content.endswith('}'):
                parsed = json.loads(content)
                
                if "final" in parsed:
                    # Agent is done
                    return parsed["final"], {"type": "multistep_complete", "steps": steps}, False
                
                elif "tool" in parsed and "args" in parsed:
                    # Tool call
                    tool_name = parsed["tool"]
                    args = parsed["args"]
                    
                    # Check for repeated tool calls
                    current_call = f"{tool_name}:{json.dumps(args, sort_keys=True)}"
                    print(f"DEBUG: Current call: {current_call}")
                    print(f"DEBUG: Last call: {last_tool_call}")
                    print(f"DEBUG: Repeat count: {repeat_count}")
                    
                    if current_call == last_tool_call:
                        repeat_count += 1
                        print(f"DEBUG: Repeated call detected! Count: {repeat_count}")
                        if repeat_count >= 2:  # Reduced from 3 to 2 for faster detection
                            print(f"DEBUG: Max repeats reached, stopping agent")
                            return "I'm stuck repeating the same tool call. Could you clarify your request?", {"type": "multistep_error", "error": "repeated_tool_call"}, False
                    else:
                        repeat_count = 0
                        last_tool_call = current_call
                        print(f"DEBUG: New call, reset repeat count")
                    
                    # Find and execute the tool
                    tool_found = False
                    for tool in tools:
                        if tool.name == tool_name:
                            tool_found = True
                            try:
                                # Inject credentials if available and tool needs them
                                if "access_token" in kwargs and "refresh_token" in kwargs:
                                    args["access_token"] = kwargs["access_token"]
                                    args["refresh_token"] = kwargs["refresh_token"]
                                
                                # Execute the tool
                                print(f"DEBUG: Executing tool '{tool_name}' with args: {args}")
                                if asyncio.iscoroutinefunction(tool.func):
                                    last_tool_result = await tool.func(**args)
                                else:
                                    last_tool_result = tool.func(**args)
                                
                                print(f"DEBUG: Tool '{tool_name}' returned: {last_tool_result}")
                                
                                # Feed tool result in a clear format
                                try:
                                    if isinstance(last_tool_result, str):
                                        tool_result_text = last_tool_result
                                    else:
                                        tool_result_text = json.dumps(last_tool_result, indent=2)
                                except Exception:
                                    tool_result_text = str(last_tool_result)
                                
                                # Add the tool result to history with clear formatting
                                result_message = f"🔧 Tool '{tool_name}' executed successfully.\n\n📋 Result:\n{tool_result_text}\n\nWhat would you like to do next?"
                                history.append({
                                    "role": "assistant", 
                                    "content": result_message
                                })
                                print(f"DEBUG: Added to history: {result_message[:200]}...")
                                
                                break
                            except Exception as e:
                                error_msg = f"Error executing {tool_name}: {str(e)}"
                                history.append({"role": "assistant", "content": f"ERROR: {error_msg}"})
                                last_tool_result = error_msg
                                break
                    
                    if not tool_found:
                        error_msg = f"Tool '{tool_name}' not found"
                        history.append({"role": "assistant", "content": f"ERROR: {error_msg}"})
                        last_tool_result = error_msg
                
                else:
                    # Invalid JSON format
                    history.append({"role": "assistant", "content": content})
                    last_tool_result = None
            
            else:
                # Not JSON, treat as final response
                return content, {"type": "multistep_complete", "steps": steps}, False
                
        except json.JSONDecodeError:
            # Not valid JSON, treat as final response
            return content, {"type": "multistep_complete", "steps": steps}, False
    
    # Max steps reached
    return "I've reached the maximum number of steps. Could you break this down into smaller tasks?", {"type": "multistep_error", "error": "max_steps_reached"}, False

# --- Example Tool Registration ---

reminder_tool = Tool(
    name="add_reminder",
    description="Add a reminder with a title, due date (YYYY-MM-DD), and due time (HH:MM).",
    func=add_reminder,
    parameters={
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "The title of the reminder"},
            "due_date": {"type": "string", "description": "Due date in YYYY-MM-DD format (optional)"},
            "due_time": {"type": "string", "description": "Due time in HH:MM format (optional)"}
        },
        "required": ["title"]
    }
)

todo_tool = Tool(
    name="add_todo",
    description="Add a todo item with a title, email, and optional due date (YYYY-MM-DD).",
    func=add_todo,
    parameters={
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "The title of the todo item"},
            "email": {"type": "string", "description": "The user's email address (required)"},
            "due_date": {"type": "string", "description": "Due date in YYYY-MM-DD format (optional)"}
        },
        "required": ["title", "email"]
    }
)

search_email_tool = Tool(
    name="search_email",
    description="Search emails using a query string. Requires access_token and refresh_token for Gmail authentication. You do NOT need to ask the user for these tokens; they will be provided automatically.",
    func=search_email,
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query for emails"},
            "limit": {"type": "integer", "description": "Maximum number of results (default 10)"},
            "access_token": {"type": "string", "description": "Gmail access token (provided automatically)"},
            "refresh_token": {"type": "string", "description": "Gmail refresh token (provided automatically)"}
        },
        "required": ["query", "access_token", "refresh_token"]
    }
)

search_google_tool = Tool(
    name="search_google",
    description="Search the web using Google/DuckDuckGo. Provide a search query and optionally specify number of results (default 5).",
    func=search_google,
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query for web search"},
            "num_results": {"type": "integer", "description": "Number of results to return (default 5)"}
        },
        "required": ["query"]
    }
)

search_calendar_tool = Tool(
    name="search_calendar",
    description="Search Google Calendar for events matching a query string. Requires access_token and refresh_token. You do NOT need to ask the user for these tokens; they will be provided automatically.",
    func=search_calendar,
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query for calendar events"},
            "access_token": {"type": "string", "description": "Google Calendar access token (provided automatically)"},
            "refresh_token": {"type": "string", "description": "Google Calendar refresh token (provided automatically)"}
        },
        "required": ["query", "access_token", "refresh_token"]
    }
)

add_calendar_event_tool = Tool(
    name="add_calendar_event",
    description="Add a new event to Google Calendar. Requires title, start_time (ISO 8601), end_time (ISO 8601), and optionally attendees. Requires access_token and refresh_token. You do NOT need to ask the user for these tokens; they will be provided automatically.",
    func=add_calendar_event,
    parameters={
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Event title"},
            "start_time": {"type": "string", "description": "Start time in ISO 8601 format (e.g., 2024-06-10T10:00:00-04:00)"},
            "end_time": {"type": "string", "description": "End time in ISO 8601 format (e.g., 2024-06-10T11:00:00-04:00)"},
            "attendees": {"type": "array", "items": {"type": "string"}, "description": "List of attendee email addresses (optional)"},
            "access_token": {"type": "string", "description": "Google Calendar access token (provided automatically)"},
            "refresh_token": {"type": "string", "description": "Google Calendar refresh token (provided automatically)"}
        },
        "required": ["title", "start_time", "end_time", "access_token", "refresh_token"]
    }
)



note_email_tool = Tool(
    name="note_email",
    description="Send a note email to the user themselves. Useful for reminders, notes, or saving important information.",
    func=note_email,
    parameters={
        "type": "object",
        "properties": {
            "subject": {"type": "string", "description": "Email subject line"},
            "body": {"type": "string", "description": "Email body content"},
            "user_email": {"type": "string", "description": "User's email address to send to"},
            "access_token": {"type": "string", "description": "Gmail access token (provided automatically)"},
            "refresh_token": {"type": "string", "description": "Gmail refresh token (provided automatically)"}
        },
        "required": ["subject", "body", "user_email", "access_token", "refresh_token"]
    }
)

get_calendar_events_tool = Tool(
    name="get_calendar_events",
    description="Get calendar events for a specific time period using natural language. Examples: 'today', 'this week', 'next month', 'July 15th'. Returns a formatted list of events with details like title, start/end times, attendees, location, and description. Requires access_token and refresh_token. You do NOT need to ask the user for these tokens; they will be provided automatically.",
    func=get_calendar_events,
    parameters={
        "type": "object",
        "properties": {
            "message": {"type": "string", "description": "Natural language description of the time period (e.g., 'today', 'this week', 'next month', 'July 15th')"},
            "access_token": {"type": "string", "description": "Google Calendar access token (provided automatically)"},
            "refresh_token": {"type": "string", "description": "Google Calendar refresh token (provided automatically)"}
        },
        "required": ["message", "access_token", "refresh_token"]
    }
)

get_email_metadata_tool = Tool(
    name="get_email_metadata",
    description="Get recent email metadata (IDs, subjects, senders, dates, snippets). Returns the most recent emails from the inbox. Useful for getting a list of recent emails before retrieving full content. Requires access_token and refresh_token. You do NOT need to ask the user for these tokens; they will be provided automatically.",
    func=get_email_metadata,
    parameters={
        "type": "object",
        "properties": {
            "limit": {"type": "integer", "description": "Maximum number of recent emails to return (default 10)"},
            "access_token": {"type": "string", "description": "Gmail access token (provided automatically)"},
            "refresh_token": {"type": "string", "description": "Gmail refresh token (provided automatically)"}
        },
        "required": ["access_token", "refresh_token"]
    }
)

get_email_content_tool = Tool(
    name="get_email_content",
    description="Get the full content of an email by its ID. Use this after getting email metadata to retrieve the complete email body and details. Requires access_token and refresh_token. You do NOT need to ask the user for these tokens; they will be provided automatically.",
    func=get_email_content,
    parameters={
        "type": "object",
        "properties": {
            "email_id": {"type": "string", "description": "The ID of the email to retrieve (obtained from get_email_metadata)"},
            "access_token": {"type": "string", "description": "Gmail access token (provided automatically)"},
            "refresh_token": {"type": "string", "description": "Gmail refresh token (provided automatically)"}
        },
        "required": ["email_id", "access_token", "refresh_token"]
    }
)

# Example tools list for agent usage:
tools = [reminder_tool, todo_tool, search_email_tool, note_email_tool, search_google_tool, search_calendar_tool, add_calendar_event_tool, get_calendar_events_tool, get_email_metadata_tool, get_email_content_tool] 