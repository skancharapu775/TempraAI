import json
from typing import Any, Callable, Dict, Tuple, List
from emails import create_email_handler
from scheduling import create_schedule_handler
import requests
import os

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

async def add_todo(title: str, due_date: str = None, **kwargs):
    msg = f"[Todo] '{title}'"
    if due_date:
        msg += f" (due {due_date})"
    return f"Added todo: {msg}"

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

# --- Tool-Calling Agent ---

async def tool_calling_agent(
    client: Any,
    message: str,
    tools: List[Tool],
    max_steps: int = 8,
    system_prompt: str = None,
    conversation_history: List[dict] = None,
    **kwargs
) -> Tuple[str, dict, bool]:
    """
    Advanced tool-calling agent loop. The LLM can:
    - See the user message and available tools
    - Call tools one at a time, receiving the result after each call
    - Decide what to do next (call another tool, ask user, or finish)
    """
    tool_map = {tool.name: tool for tool in tools}
    history = conversation_history[:] if conversation_history else []
    tool_results = {}
    steps = 0
    done = False
    last_tool_result = None
    
    if not system_prompt:
        system_prompt = (
            """You are an advanced assistant with access to the following tools. 
You may call one tool at a time, and after each call you will see the result as a JSON block.
Use the tool result to plan your next step. For example, if you search emails and receive a list of emails, analyze their content and, if you find any todos, call add_todo for each one. 
If you are done, reply with a final message to the user. 
If you need more clarification, ask the user. 
You do NOT need to ask the user for access_token or refresh_token. These will be provided automatically to any tool that needs them.
If you repeat the same tool call and arguments more than twice, stop and ask the user for clarification.

When you want to use a tool, reply with a JSON object like:
{"tool": "tool_name", "args": {...}}
When you are done, reply with:
{"final": "your final message to the user"}
If you need more information from the user, reply with:
{"final": "Could you clarify..."}

Examples:
User: Read my email and add the todos you can find.
Assistant: {"tool": "search_email", "args": {"query": "is:unread"}}
(after seeing the result)
Assistant: {"tool": "add_todo", "args": {"title": "Follow up with John"}}
(when done)
Assistant: {"final": "I've read your emails and added the todos I found to your list."}
"""
        )
    
    # Compose tool descriptions for the LLM
    tool_list_str = "\n".join([f"- {tool.name}: {tool.description}" for tool in tools])
    
    # Track repeated tool calls
    last_tool_call = None
    repeat_count = 0
    while not done and steps < max_steps:
        steps += 1
        messages = [
            {"role": "system", "content": system_prompt + "\n\nAvailable tools:\n" + tool_list_str}
        ]
        messages.extend(history)
        messages.append({"role": "user", "content": message})
        
        # Ask LLM what to do next
        response = client.chat.completions.create(
            model="gpt-4",
            messages=messages,
            max_tokens=400,
            temperature=0.2
        )
        content = response.choices[0].message.content.strip()
        print(f"[AGENT DEBUG] LLM raw output: {content}")
        try:
            if content.startswith("{"):
                action = json.loads(content)
            else:
                action = {"final": content}
        except Exception:
            action = {"final": content}
        
        if "final" in action:
            return action["final"], {"steps": steps, "tool_results": tool_results}, False
        elif "tool" in action:
            tool_name = action["tool"]
            args = action.get("args", {})
            tool = tool_map.get(tool_name)
            # Check for repeated tool calls
            tool_call_signature = (tool_name, json.dumps(args, sort_keys=True))
            if tool_call_signature == last_tool_call:
                repeat_count += 1
            else:
                repeat_count = 0
            last_tool_call = tool_call_signature
            if repeat_count >= 3:
                return "I'm stuck repeating the same tool call. Could you clarify your request?", {"steps": steps, "tool_results": tool_results}, False
            if not tool:
                last_tool_result = f"Unknown tool: {tool_name}"
            else:
                try:
                    for cred_key in ["access_token", "refresh_token"]:
                        if cred_key in tool.parameters.get("properties", {}) and cred_key not in args and cred_key in kwargs:
                            args[cred_key] = kwargs[cred_key]
                    result = await tool.func(**args)
                    last_tool_result = result
                    tool_results[tool_name] = result
                except Exception as e:
                    last_tool_result = f"Error calling tool {tool_name}: {e}"
            # Feed tool result as structured JSON
            try:
                tool_result_json = json.dumps(last_tool_result) if not isinstance(last_tool_result, str) else last_tool_result
            except Exception:
                tool_result_json = str(last_tool_result)
            history.append({"role": "assistant", "content": f"TOOL RESULT:\n{tool_result_json}"})
        else:
            return content, {"steps": steps, "tool_results": tool_results}, False
    return "Sorry, I couldn't complete your request in time.", {"steps": steps, "tool_results": tool_results}, False

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
    description="Add a todo item with a title and optional due date (YYYY-MM-DD).",
    func=add_todo,
    parameters={
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "The title of the todo item"},
            "due_date": {"type": "string", "description": "Due date in YYYY-MM-DD format (optional)"}
        },
        "required": ["title"]
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

# Example tools list for agent usage:
tools = [reminder_tool, todo_tool, search_email_tool, search_google_tool, search_calendar_tool, add_calendar_event_tool] 