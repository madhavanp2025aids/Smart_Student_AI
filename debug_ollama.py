#!/usr/bin/env python3
"""Check exact Ollama model details"""

try:
    import ollama
    import json
    
    result = ollama.list()
    print("Raw Ollama Response:")
    print(json.dumps(result, indent=2, default=str))
    
except Exception as e:
    print(f"Error: {e}")
