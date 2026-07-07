#!/usr/bin/env python3
"""Comprehensive chatbot functionality test"""

import urllib.request
import json

print("="*60)
print("COMPREHENSIVE CHATBOT TEST")
print("="*60)

# Test 1: Check home page
print('\n[Test 1] Home page...')
try:
    req = urllib.request.Request('http://localhost:5000/')
    with urllib.request.urlopen(req, timeout=5) as response:
        if response.status == 200:
            print('✓ Home page accessible')
except Exception as e:
    print(f'✗ Home page error: {e}')

# Test 2: Check chatbot page
print('[Test 2] Chatbot page...')
try:
    req = urllib.request.Request('http://localhost:5000/chatbot_page')
    with urllib.request.urlopen(req, timeout=5) as response:
        content = response.read().decode('utf-8')
        if 'sendMessage' in content and 'chatbox' in content:
            print('✓ Chatbot page loads correctly')
        else:
            print('⚠ Chatbot page missing JS functions')
except Exception as e:
    print(f'✗ Chatbot page error: {e}')

# Test 3: Chat with different topics
print('\n[Test 3] Testing various question types...')
topics = [
    ('hello', 'greeting'),
    ('What is Python?', 'programming'),
    ('How to study math?', 'study'),
    ('Tell me about Data Science', 'career'),
]

for question, question_type in topics:
    print(f'  [{question_type}] "{question}"')
    try:
        data = json.dumps({'message': question}).encode()
        req = urllib.request.Request('http://localhost:5000/chat', 
                                     data=data, 
                                     headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read())
            if 'reply' in result and result['reply']:
                reply_preview = result['reply'][:60]
                emoji = result.get('emoji', '✨')
                print(f'    ✓ {emoji} Response: {reply_preview}...')
            else:
                print(f'    ✗ Empty response')
    except Exception as e:
        print(f'    ✗ Error: {e}')

# Test 4: Test career endpoint
print('\n[Test 4] Career endpoint...')
try:
    data = json.dumps({'skills': ['python', 'problem solving']}).encode()
    req = urllib.request.Request('http://localhost:5000/career',
                                 data=data,
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=5) as response:
        result = json.loads(response.read())
        careers = result.get('careers', [])
        if careers:
            print(f'✓ Found {len(careers)} career matches')
            for c in careers[:2]:
                print(f'  - {c["name"]}')
        else:
            print('⚠ No careers found')
except Exception as e:
    print(f'✗ Error: {e}')

# Test 5: Test study endpoint
print('\n[Test 5] Study endpoint...')
try:
    data = json.dumps({
        'noise': 'silent',
        'focus': 'medium',
        'subject': 'programming',
        'lighting': 'bright',
        'temperature': 'moderate'
    }).encode()
    req = urllib.request.Request('http://localhost:5000/study',
                                 data=data,
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=5) as response:
        result = json.loads(response.read())
        recs = result.get('recommendations', [])
        if recs:
            print(f'✓ Found {len(recs)} study recommendations')
        else:
            print('⚠ No recommendations found')
except Exception as e:
    print(f'✗ Error: {e}')

print("\n" + "="*60)
print("✅ CHATBOT TESTS COMPLETE!")
print("="*60)
