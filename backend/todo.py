import re
from openai import OpenAI
import os

from fastapi import APIRouter
from google.cloud import firestore
from pydantic import BaseModel
from typing import List
from firebase import db
from uuid import uuid4

router = APIRouter()

class TodoItem(BaseModel):
    id: str
    title: str
    completed: bool

class TodoUpdateCompleted(BaseModel):
    id: str
    email: str
    completed: bool

@router.get("/get-todos", response_model=List[TodoItem])
def get_todos(email: str):
    todos_ref = db.collection("todos").document(email).collection("todos")
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

@router.post("/update-todos-completed")
def update_todos_completed(req: TodoUpdateCompleted):
    doc_ref = db.collection("todos").document(req.email).collection("todos").document(req.id)
    doc_ref.update({
        "completed": not req.completed
    })


class TodoHandler:
    def __init__(self):
        self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    async def classify_todo_function(self, message: str) -> str:
        """Classify what todo function the user wants to perform"""
        system_prompt = """
        Classify the user's todo request into one of these categories:
        You may intervene intelligently when confident. For example, if the user says make, then "add". 
        If the user says cancel then "delete". If the user says what do I have to do, then "summarize". etc
        - "add": User wants to add a new todo
        - "delete": User wants to delete or remove a todo
        - "summarize": User wants to summarize, search, or plan todos
        - "collecting": You need more data to 
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

    async def handle_todo_intent(self, message, email, pending_changes=None):
        todo_function = await self.classify_todo_function(message)
        if todo_function == "add":
            return await self.add_todo(message, email, pending_changes)
        elif todo_function == "delete":
            return await self.delete_todo(message, email, pending_changes)
        elif todo_function == "summarize":
            return await self.summarize_todos(message)
        else:
            # Default to summarize if unclear
            return await self.summarize_todos(message)

    async def add_todo(self, message, email, pending_changes=None):
        todo_name = await self.extract_todo_name(message)
        if not todo_name or todo_name.lower() in ["", "none", "todo"]:
            # Not enough info, return collecting state
            reply = "📝 What is the task you'd like to add?"
            return reply, {"type": "todo", "action": "collecting"}, True
        
            
        db.collection("todos").document(email).collection("todos").add({
            "title": todo_name,
            "completed": False,
            "id": str(uuid4())
        })
        result = {
            "type": "todo",
            "action": "add",
            "message": todo_name,
        }
        reply = f"✅ Todo added: '{todo_name}'"
        return reply, result, False

    async def delete_todo(self, message, email, pending_changes=None):
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
        prompt = f"""
        Intervene intelligently, if there is no deliverable, then it is not a todo.
        Extract the todo name from this message: {message}
        Only reply with the todo name
        OR reply with none"""
        response = self.openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=30,
            temperature=0
        )
        todo_name = response.choices[0].message.content.strip()
        return todo_name

def create_todo_handler():
    return TodoHandler() 