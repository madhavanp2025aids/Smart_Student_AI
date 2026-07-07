#!/usr/bin/env python3
"""Test script for chatbot endpoints"""

import time
import json

# Give the server time to start
time.sleep(1)

# Test using pure Python without external requests library
import urllib.request
import urllib.error

def test_chat_endpoint():
    """Test the /chat endpoint"""
    print("\n[Test 1] Testing /chat endpoint...")
    
    try:
        data = json.dumps({"message": "hello"}).encode('utf-8')
        req = urllib.request.Request(
            'http://localhost:5000/chat',
            data=data,
            headers={'Content-Type': 'application/json'}
        )
        
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode('utf-8'))
            print(f"✓ /chat endpoint works!")
            print(f"  Response: {result['reply'][:100]}...")
            print(f"  Emoji: {result['emoji']}")
            return True
    except Exception as e:
        print(f"✗ /chat endpoint failed: {e}")
        return False

def test_chat_stream_endpoint():
    """Test the /chat_stream endpoint"""
    print("\n[Test 2] Testing /chat_stream endpoint...")
    
    try:
        data = json.dumps({"message": "What is Python?"}).encode('utf-8')
        req = urllib.request.Request(
            'http://localhost:5000/chat_stream',
            data=data,
            headers={'Content-Type': 'application/json'}
        )
        
        with urllib.request.urlopen(req, timeout=10) as response:
            print(f"✓ /chat_stream endpoint connected!")
            
            # Read streaming response
            response_data = response.read().decode('utf-8')
            lines = response_data.strip().split('\n')
            
            print(f"  Received {len(lines)} chunks")
            for i, line in enumerate(lines[:3]):  # Show first 3 lines
                try:
                    data = json.loads(line)
                    if 'emoji' in data:
                        print(f"  Emoji: {data['emoji']}")
                    elif 'chunk' in data:
                        print(f"  Chunk {i}: {data['chunk'][:50]}...")
                except:
                    pass
            
            return True
    except Exception as e:
        print(f"✗ /chat_stream endpoint failed: {e}")
        return False

def test_career_endpoint():
    """Test the /career endpoint"""
    print("\n[Test 3] Testing /career endpoint...")
    
    try:
        data = json.dumps({"skills": ["python"]}).encode('utf-8')
        req = urllib.request.Request(
            'http://localhost:5000/career',
            data=data,
            headers={'Content-Type': 'application/json'}
        )
        
        with urllib.request.urlopen(req, timeout=5) as response:
            result = json.loads(response.read().decode('utf-8'))
            careers = result.get('careers', [])
            print(f"✓ /career endpoint works! Found {len(careers)} careers")
            if careers:
                print(f"  First career: {careers[0]['name']}")
            return True
    except Exception as e:
        print(f"✗ /career endpoint failed: {e}")
        return False

def test_study_endpoint():
    """Test the /study endpoint"""
    print("\n[Test 4] Testing /study endpoint...")
    
    try:
        data = json.dumps({
            "noise": "silent",
            "focus": "medium", 
            "subject": "analytical",
            "lighting": "bright",
            "temperature": "moderate"
        }).encode('utf-8')
        req = urllib.request.Request(
            'http://localhost:5000/study',
            data=data,
            headers={'Content-Type': 'application/json'}
        )
        
        with urllib.request.urlopen(req, timeout=5) as response:
            result = json.loads(response.read().decode('utf-8'))
            recs = result.get('recommendations', [])
            print(f"✓ /study endpoint works! Found {len(recs)} recommendations")
            return True
    except Exception as e:
        print(f"✗ /study endpoint failed: {e}")
        return False

if __name__ == "__main__":
    print("="*60)
    print("Testing Smart Student AI Chatbot Endpoints")
    print("="*60)
    
    results = []
    results.append(("Chat Endpoint", test_chat_endpoint()))
    results.append(("Chat Stream Endpoint", test_chat_stream_endpoint()))
    results.append(("Career Endpoint", test_career_endpoint()))
    results.append(("Study Endpoint", test_study_endpoint()))
    
    print("\n" + "="*60)
    print("Test Summary:")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! Chatbot is working properly.")
    else:
        print(f"\n⚠ {total - passed} test(s) failed. Please check the errors above.")
