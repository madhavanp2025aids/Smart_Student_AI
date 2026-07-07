#!/usr/bin/env python3
"""Test Ollama connection and available models"""

import sys

try:
    import ollama
    print("✓ ollama library found\n")
except ImportError:
    print("✗ ollama library NOT found")
    sys.exit(1)

# Test connection
print("Testing Ollama connection...")
try:
    models_response = ollama.list()
    print(f"✓ Connected to Ollama server\n")
    
    # List available models
    models = models_response.get('models', [])
    if models:
        print(f"Available models ({len(models)}):")
        for model in models:
            model_name = model.get('name', 'unknown')
            print(f"  - {model_name}")
            
        # Check for neural-chat
        model_names = [m.get('name', '').split(':')[0] for m in models]
        if 'neural-chat' in model_names:
            print(f"\n✓ neural-chat model IS installed - ready to use")
        else:
            print(f"\n⚠ neural-chat model NOT installed")
            if model_names:
                print(f"  Available: {', '.join(set(model_names))}")
                print(f"  To install: ollama pull neural-chat")
    else:
        print("✗ No models installed")
        
except Exception as e:
    print(f"✗ Failed to connect to Ollama: {e}")
    print("  Make sure Ollama is running with: ollama serve")
