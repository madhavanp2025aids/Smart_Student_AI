#!/usr/bin/env python3
"""Test the Groq-powered chatbot"""

import urllib.request
import json
import time

def test_chat(message):
    """Send a message to the chat endpoint"""
    req = urllib.request.Request(
        'http://127.0.0.1:5000/chat',
        data=json.dumps({'message': message}).encode(),
        headers={'Content-Type': 'application/json'}
    )
    try:
        response = urllib.request.urlopen(req, timeout=10)
        result = json.loads(response.read())
        return result
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    print("Testing Groq-powered Chatbot")
    print("=" * 50)
    
    # Test 1: Quick greeting
    print("\n1. Testing quick greeting:")
    result = test_chat("hello")
    print(f"Q: hello")
    print(f"A: {result['reply']}")
    print(f"Emoji: {result['emoji']}")
    
    # Test 2: Programming question (should use Groq)
    print("\n2. Testing programming question:")
    result = test_chat("What is Python programming?")
    print(f"Q: What is Python programming?")
    print(f"A: {result['reply'][:150]}...")
    print(f"Emoji: {result['emoji']}")
    
    # Test 3: Math question (should use Groq)
    print("\n3. Testing math question:")
    result = test_chat("Explain what is calculus")
    print(f"Q: Explain what is calculus")
    print(f"A: {result['reply'][:150]}...")
    print(f"Emoji: {result['emoji']}")
    
    print("\n" + "=" * 50)
    print("✓ Chatbot is working!")
