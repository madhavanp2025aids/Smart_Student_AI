#!/usr/bin/env python3
"""Diagnostic script to test Ollama connectivity and available models"""

import sys
import time

try:
    import ollama
    print("✓ ollama library imported successfully")
except ImportError as e:
    print(f"✗ Failed to import ollama: {e}")
    sys.exit(1)

# Test 1: Check if Ollama server is running
print("\n[Test 1] Checking Ollama server connection...")
try:
    response = ollama.list()
    print("✓ Connected to Ollama server")
    print(f"  Available models: {len(response['models'])} found")
    
    if response['models']:
        print("\n  Installed models:")
        for model in response['models']:
            print(f"    - {model['name']}")
    else:
        print("  ⚠ No models installed!")
        
except Exception as e:
    print(f"✗ Failed to connect to Ollama server: {e}")
    print("  Make sure Ollama is running (ollama serve)")
    sys.exit(1)

# Test 2: Check for neural-chat model
print("\n[Test 2] Checking for 'neural-chat' model...")
try:
    models = ollama.list()
    model_names = [m['name'] for m in models['models']]
    
    if any('neural-chat' in name for name in model_names):
        print("✓ neural-chat model found")
    else:
        print("✗ neural-chat model NOT found")
        print("  Available models:")
        for name in model_names:
            print(f"    - {name}")
        print("\n  To install neural-chat, run:")
        print("    ollama pull neural-chat")
        
except Exception as e:
    print(f"✗ Error checking models: {e}")

# Test 3: Try a simple chat call
print("\n[Test 3] Testing simple chat call...")
try:
    model = None
    models = ollama.list()
    
    # Find first available model
    if models['models']:
        model = models['models'][0]['name'].split(':')[0]  # Get base model name
        print(f"  Using model: {model}")
        
        response = ollama.chat(
            model=model,
            messages=[{"role": "user", "content": "Hello"}],
            stream=False
        )
        print(f"✓ Chat call successful")
        print(f"  Response: {response['message']['content'][:100]}...")
    else:
        print("✗ No models available to test")
        
except Exception as e:
    print(f"✗ Chat call failed: {e}")
    print("  This may indicate Ollama server is not responding")

print("\n" + "="*50)
print("Diagnosis complete!")
