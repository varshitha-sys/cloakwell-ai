import os
from pathlib import Path
from dotenv import load_dotenv

# Load env variables
load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=True)

import tier2
import policy

# Load policy
pol = policy.load_policy()

# Simple client proxy to capture raw model output
raw_responses = []
def debug_client(messages):
    print("\n--- MESSAGES SENT TO LLM ---")
    for msg in messages:
        print(f"[{msg['role'].upper()}]:\n{msg['content']}\n")
    
    # Call the real client
    try:
        res = tier2._fireworks_client(messages)
        raw_responses.append(res)
        return res
    except Exception as e:
        print("\n--- CLIENT EXCEPTION ---")
        import traceback
        traceback.print_exc()
        raise e

print("Testing prompt: 'Can you verify if this customer application is valid? The applicant's Aadhaar number is 9999 4105 7058 and their PAN is ABCDE1234F.'")
result = tier2.classify("Can you verify if this customer application is valid? The applicant's Aadhaar number is 9999 4105 7058 and their PAN is ABCDE1234F.", policy=pol, client=debug_client)

print("\n--- RAW LLM RESPONSE ---")
print(raw_responses[0])

print("\n--- PARSED RESULT ---")
print(result)
