#!/usr/bin/env python3
"""
Test script for email functionality
"""

import asyncio
import os
from dotenv import load_dotenv
from emails import create_email_handler

load_dotenv()

async def test_email_functions():
    """Test various email functions"""
    
    # Create email handler
    email_handler = create_email_handler("gmail")
    
    # Test cases
    test_cases = [
        "Summarize my recent emails",
        "Show me high priority emails",
        "Create a Work folder",
        "Search for emails about meetings",
        "Compose an email to john@example.com about the project",
        "Show my email drafts",
        "Schedule an email to be sent tomorrow"
    ]
    
    print("🧪 Testing Email Functions\n")
    
    for i, test_message in enumerate(test_cases, 1):
        print(f"Test {i}: {test_message}")
        try:
            reply, pending_changes, show_accept_deny = await email_handler.handle_email_intent(test_message)
            print(f"✅ Reply: {reply[:100]}...")
            print(f"   Pending changes: {pending_changes is not None}")
            print(f"   Show accept/deny: {show_accept_deny}")
        except Exception as e:
            print(f"❌ Error: {str(e)}")
        print()

if __name__ == "__main__":
    asyncio.run(test_email_functions()) 