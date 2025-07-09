from openai import OpenAI
import os
from emails import *

# Client message: change for testing
MESSAGE = "Send an email to John Doe to remind him about the meeting tomorrow"

def main():
    client = create_openai_client()
    intent = get_intent(client, MESSAGE)

    if intent == "Email":
        draft_email(client, MESSAGE)

    print(intent)

def create_openai_client():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("OPENAI_API_KEY environment variable not set")
        exit(1)
    return OpenAI(api_key=api_key)

def get_intent(client, message):
    role = '''
        Based on the intent of the message return one of these: "Schedule", "Remind", "Email", "General"
    '''
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
        {"role": "system", "content": role},
        {"role": "user", "content": message}
        ],
        max_tokens=20,
        temperature=0.3
    )
    content = response.choices[0].message.content.strip()
    return content

if __name__ == "__main__":
    main()