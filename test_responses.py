#!/usr/bin/env python3
"""Debug chatbot response issue"""

import urllib.request
import json
import time

print("\n" + "="*70)
print("TESTING CHATBOT RESPONSES TO QUESTIONS")
print("="*70 + "\n")

test_questions = [
    "What is Python?",
    "How do I learn programming?",
    "What careers are in tech?",
    "What's a good study strategy?",
    "Explain machine learning",
    "How to debug code?",
    "What is HTML?",
]

for i, question in enumerate(test_questions, 1):
    print(f"[Test {i}] Question: {question}")
    try:
        data = json.dumps({"message": question}).encode()
        req = urllib.request.Request('http://localhost:5000/chat',
                                     data=data,
                                     headers={'Content-Type': 'application/json'})
        start = time.time()
        response = urllib.request.urlopen(req, timeout=15)
        elapsed = time.time() - start
        result = json.loads(response.read())
        
        reply = result.get('reply', '')
        emoji = result.get('emoji', '✨')
        
        if not reply:
            print(f"  ✗ EMPTY RESPONSE")
        elif len(reply) < 10:
            print(f"  ⚠ TOO SHORT: {reply}")
        else:
            print(f"  ✓ Response: {reply[:80]}...")
            print(f"    Emoji: {emoji}")
            print(f"    Time: {elapsed:.2f}s")
    except Exception as e:
        print(f"  ✗ ERROR: {str(e)[:100]}")
    
    print()

print("="*70)
