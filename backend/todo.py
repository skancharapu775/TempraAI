import re
from openai import OpenAI
import os

from fastapi import APIRouter
from google.cloud import firestore
from pydantic import BaseModel
from typing import List
from firebase import db

router = APIRouter()

class TodoItem(BaseModel):
    id: str
    title: str
    completed: bool

@router.get("/get-todos", response_model=List[TodoItem])
def get_todos():
    todos_ref = db.collection("reminders")
    docs = todos_ref.stream()
    
    result = []
    for doc in docs:
        data = doc.to_dict()
        result.append(TodoItem(
            id=doc.id,
            title=data.get("title", ""),
            completed=data.get("completed", False)
        ))
    return result

class TodoHandler:
    def __init__(self):
        self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    async def classify_todo_function(self, message: str) -> str:
        """Classify what todo function the user wants to perform"""
        system_prompt = """
        Classify the user's todo request into one of these categories:
        - "add": User wants to add a new todo
        - "delete": User wants to delete or remove a todo
        - "summarize": User wants to summarize, search, or plan todos
        Return ONLY ONE WORD from the choices above.
        """
        response = self.openai_client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message}
            ],
            max_tokens=20,
            temperature=0.3
        )
        return response.choices[0].message.content.strip().lower()

    async def handle_todo_intent(self, message, pending_changes=None):
        todo_function = await self.classify_todo_function(message)
        if todo_function == "add":
            return await self.add_todo(message, pending_changes)
        elif todo_function == "delete":
            return await self.delete_todo(message, pending_changes)
        elif todo_function == "summarize":
            return await self.summarize_todos(message)
        else:
            # Default to summarize if unclear
            return await self.summarize_todos(message)

    async def add_todo(self, message, pending_changes=None):
        todo_name = await self.extract_todo_name(message)
        reply = f"✅ Todo added: '{todo_name}'"
        result = {
            "type": "todo",
            "action": "add",
            "message": todo_name,
        }
        if pending_changes:
            result.update(pending_changes)
        return reply, result, False

    async def delete_todo(self, message, pending_changes=None):
        # Dummy: extract todo name and reply as deleted
        todo_name = await self.extract_todo_name(message)
        reply = f"🗑️ Todo deleted: '{todo_name}'"
        result = {
            "type": "todo",
            "action": "delete",
            "message": todo_name,
        }
        return reply, result, False

    async def summarize_todos(self, message):
        # Dummy: just reply with a placeholder
        reply = "📋 Here is a summary of your todos: (feature not implemented)"
        result = {
            "type": "todo",
            "action": "summarize",
            "message": "summary_placeholder",
        }
        return reply, result, False

    async def extract_todo_name(self, message):
        prompt = f"Extract the todo name from this message: {message}\nOnly reply with the todo name."
        response = self.openai_client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=30,
            temperature=0
        )
        todo_name = response.choices[0].message.content.strip()
        return todo_name

def create_todo_handler():
    return TodoHandler() 