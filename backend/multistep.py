import json
from typing import Any, Callable, Dict, Tuple, List

"""
Advanced tool-calling agent for multi-step, adaptive LLM workflows.
The LLM is given a list of tools and can call them one at a time, receiving the result after each call and deciding what to do next.
"""

class Tool:
    def __init__(self, name: str, description: str, func: Callable):
        self.name = name
        self.description = description
        self.func = func

    def to_openai_function(self):
        # For OpenAI function calling schema
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {"type": "object", "properties": {}},  # You can expand this for strict schemas
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
            "You are an advanced assistant with access to the following tools. "
            "You may call one tool at a time, and after each call you will see the result. "
            "Continue until the user's request is fully handled. "
            "If you are done, reply with a final message to the user. "
            "If you need clarification, ask the user."
        )
    
    # Compose tool descriptions for the LLM
    tool_list_str = "\n".join([f"- {tool.name}: {tool.description}" for tool in tools])
    
    while not done and steps < max_steps:
        steps += 1
        messages = [
            {"role": "system", "content": system_prompt + "\n\nAvailable tools:\n" + tool_list_str}
        ]
        messages.extend(history)
        if last_tool_result is not None:
            messages.append({
                "role": "tool", "content": f"Result of previous tool call: {last_tool_result}"})
        messages.append({"role": "user", "content": message})
        
        # Ask LLM what to do next
        response = client.chat.completions.create(
            model="gpt-4",
            messages=messages,
            max_tokens=400,
            temperature=0.2
        )
        content = response.choices[0].message.content.strip()
        # Try to parse tool call from LLM output
        try:
            # Expecting: {"tool": "tool_name", "args": {...}} or {"final": "..."}
            if content.startswith("{"):
                action = json.loads(content)
            else:
                # If not JSON, treat as final message
                action = {"final": content}
        except Exception:
            action = {"final": content}
        
        if "final" in action:
            # LLM is done, return the final message
            return action["final"], {"steps": steps, "tool_results": tool_results}, False
        elif "tool" in action:
            tool_name = action["tool"]
            args = action.get("args", {})
            tool = tool_map.get(tool_name)
            if not tool:
                last_tool_result = f"Unknown tool: {tool_name}"
            else:
                try:
                    # Support async tools
                    if hasattr(tool.func, "__call__") and hasattr(tool.func, "__await__"):
                        result = await tool.func(**args)
                    else:
                        result = tool.func(**args)
                    last_tool_result = result
                    tool_results[tool_name] = result
                except Exception as e:
                    last_tool_result = f"Error calling tool {tool_name}: {e}"
        else:
            # If LLM output is not recognized, treat as final
            return content, {"steps": steps, "tool_results": tool_results}, False
        # Add LLM output to history for context
        history.append({"role": "assistant", "content": content})
    # If max steps reached
    return "Sorry, I couldn't complete your request in time.", {"steps": steps, "tool_results": tool_results}, False

# --- Example Tool Registration ---

reminder_tool = Tool(
    name="add_reminder",
    description="Add a reminder with a title, due date (YYYY-MM-DD), and due time (HH:MM).",
    func=add_reminder
)

todo_tool = Tool(
    name="add_todo",
    description="Add a todo item with a title and optional due date (YYYY-MM-DD).",
    func=add_todo
)

# Example tools list for agent usage:
tools = [reminder_tool, todo_tool] 