import os
from openai import OpenAI
import json

class GoalsHandler:
    def __init__(self):
        self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    async def handle_goal_intent(self, message, pending_changes=None):
        return await self.get_goal_confirmation(message, pending_changes)

    async def get_goal_confirmation(self, message, pending_changes=None):
        """Extract duration and calendar, return confirmation message and show_accept_deny."""
        system_prompt = f"""
        You are an assistant that helps users break down their goals into a week-by-week plan. Your job is to extract the duration (number of weeks to work on the goal) and whether the plan should be built around their calendar (true/false or yes/no) from natural text and any prior context.

        REQUIRED FIELDS: duration, calendar

        Reply *only* with valid JSON. Example:

        "duration": 6, // number of weeks (integer)
        "calendar": true, // true if the plan should be built around the user's calendar, false otherwise
        "missing_fields": ["duration", ...], // only include required fields that are missing
        "confirmation_message": "..."

        If there are any current known details, merge them with the JSON that you will return.
        """
        user_prompt = f"User message: {message}"
        # Robust goal extraction: only extract on first message
        if pending_changes is None:
            goal = await self.extract_goal(message)
        elif "goal" in pending_changes and pending_changes["goal"]:
            goal = pending_changes["goal"]
        else:
            return "Sorry, I lost track of your original goal. Please start over and specify your goal.", None, False
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
            ask = []
            if "duration" in data.get("missing_fields", []):
                ask.append("How many weeks do you want to work on this goal?")
            if "calendar" in data.get("missing_fields", []):
                ask.append("Should the plan be built around your calendar? (yes/no)")
            show_accept_deny = len(data.get("missing_fields", [])) == 0
            if show_accept_deny:
                reply = f"You want to achieve the goal: '{goal}'.\nDuration: {data.get('duration')} weeks. Build around calendar: {data.get('calendar')}.\nClick accept to generate your week-by-week plan."
            else:
                reply = f"You want to achieve the goal: '{goal}'.\n" + " ".join(ask)
            result = {"goal": goal}
            if "duration" in data:
                result["duration"] = data["duration"]
            if "calendar" in data:
                result["calendar"] = data["calendar"]
            result["missing_fields"] = data.get("missing_fields", [])
            result["confirmation_message"] = reply
            result["type"] = "goal"
            return reply, result, show_accept_deny
        except Exception as e:
            return f"Sorry, I couldn't parse the goal details. Could you please provide the information again?", None, False

    async def extract_goal(self, message):
        prompt = f"Extract the main goal from this message: {message}\nOnly reply with the goal statement."
        response = self.openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=60,
            temperature=0
        )
        return response.choices[0].message.content.strip()

    async def generate_week_plan(self, goal, duration, calendar):
        print(f"[GOALS] Generating plan with goal: {goal}, duration: {duration}, calendar: {calendar}")
        system_prompt = (
            """
            You are a productivity assistant. Given a user's goal, a duration in weeks, and whether to build around a calendar, break the goal into actionable subtasks and build a week-by-week plan. For each week, list the subtasks to complete. Also, suggest proactive push notification times for each week or subtask to keep the user on track. If 'calendar' is true, try to spread tasks to avoid calendar conflicts (assume a typical workweek, no actual calendar access).

            Reply ONLY with valid JSON in the following format:
            {
                "goal": "...",
                "duration": <int>,
                "calendar": <true/false>,
                "subtasks": ["...", ...],
                "plan": [
                    {"week": 1, "tasks": ["...", ...], "notifications": ["Monday 9am", ...]},
                    {"week": 2, "tasks": ["...", ...], "notifications": ["Wednesday 10am", ...]},
                    ...
                ]
            }
            """
        )
        prompt = f"Goal: {goal}\nDuration: {duration} weeks\nBuild around calendar: {calendar}"
        response = self.openai_client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            max_tokens=900,  # try increasing this
            temperature=0.4
        )
        content = response.choices[0].message.content.strip()
        print("[GOALS] Raw LLM output for plan:", content)  # <-- Add this line
        try:
            plan = json.loads(content)
            plan_text = "\n".join([
                f"Week {w['week']}: {', '.join(w['tasks'])} (Notifications: {', '.join(w['notifications'])})"
                for w in plan.get('plan', [])
            ])
            return plan, plan_text
        except Exception as e:
            print("[GOALS] JSON decode error:", e)
            return {"goal": goal, "duration": duration, "calendar": calendar, "plan": []}, "Sorry, I couldn't generate a plan."

def create_goals_handler():
    return GoalsHandler() 