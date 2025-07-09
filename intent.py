from openai import OpenAI
import os

# Client message: change for testing
MESSAGE = "Hello, schedule me an event tomorrow from 9-5"

def main():
    # Initialize OpenAI client with the new API
    intent = get_intent(MESSAGE)
    print(intent)

def get_intent(message):

    # Get API key from environment variable
    api_key = os.getenv("OPENAI_API_KEY")

    # make sure you run -> export OPENAI_API_KEY="key"
    if not api_key:
        print("OPENAI_API_KEY environment variable not set")
        return

    client = OpenAI(api_key=api_key)

    role = '''
        Based on the intent of the message return one of these: "Schedule", "Remind", "Miscalleneous"
    '''

    # Make OpenAI API call using the new syntax
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
        {"role": "system", "content": role},
        {"role": "user", "content": message}
        ],
        max_tokens=20,
        temperature=0.3
    )
        
    # Extract the suggested price from the response
    content = response.choices[0].message.content.strip()
    return content
        
    

if __name__ == "__main__":
    main()