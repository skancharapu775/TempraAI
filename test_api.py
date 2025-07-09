import requests
import json

# Base URL for your API
BASE_URL = "http://localhost:8000"

def test_health():
    """Test the health endpoint"""
    print("Testing health endpoint...")
    response = requests.get(f"{BASE_URL}/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    print("-" * 50)

def test_classify_intent():
    """Test the intent classification endpoint"""
    print("Testing intent classification...")
    
    test_messages = [
        "Send an email to John about the meeting",
        "Schedule a meeting for tomorrow at 2pm",
        "Remind me to call the client",
        "Hello, how are you?"
    ]
    
    for message in test_messages:
        payload = {"message": message}
        response = requests.post(f"{BASE_URL}/classify-intent", json=payload)
        print(f"Message: {message}")
        print(f"Intent: {response.json()['intent']}")
        print(f"Status: {response.status_code}")
        print("-" * 30)

def test_draft_email():
    """Test the email drafting endpoint"""
    print("Testing email drafting...")
    
    payload = {
        "message": "Remind John about the meeting tomorrow at 2pm",
        "subject": "Meeting Reminder",
        "to": "john@example.com"
    }
    
    response = requests.post(f"{BASE_URL}/draft-email", json=payload)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    print("-" * 50)

def test_root():
    """Test the root endpoint"""
    print("Testing root endpoint...")
    response = requests.get(f"{BASE_URL}/")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    print("-" * 50)

if __name__ == "__main__":
    print("Starting API tests...")
    print("=" * 50)
    
    try:
        test_health()
        test_classify_intent()
        test_draft_email()
        test_root()
        
        print("All tests completed!")
        
    except requests.exceptions.ConnectionError:
        print("Error: Could not connect to the server.")
        print("Make sure the server is running with: python main.py")
    except Exception as e:
        print(f"Error: {e}") 