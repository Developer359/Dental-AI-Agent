import os
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Read allowed numbers from .env / secrets, split by comma
allowed_env = os.getenv("ALLOWED_NUMBERS", "")
ALLOWED_NUMBERS = [num.strip() for num in allowed_env.split(",") if num.strip()]

# Read the event payload coming from GitHub Actions / LeminAI
raw_payload = os.getenv("EVENT_PAYLOAD", "{}")
try:
    payload = json.loads(raw_payload)
except json.JSONDecodeError:
    payload = {}

# Clean up sender phone number for comparison
sender_phone = str(payload.get("from") or payload.get("sender") or payload.get("phone") or "").strip()
message_body = payload.get("message") or payload.get("text") or payload.get("body")

# Check if the incoming sender matches any allowed number
is_allowed = any(sender_phone.endswith(allowed) or allowed.endswith(sender_phone) for allowed in ALLOWED_NUMBERS)

if not is_allowed:
    print(f"Skipping: Sender {sender_phone} is not authorized. Stopping workflow.")
    exit(0)  # Stops completely and ignores

if message_body and sender_phone:
    print(f"Authorized trigger! Saving message from {sender_phone} to input.json")
    
    # Save the payload data into input.json as requested
    input_data = {
        "sender": sender_phone,
        "message": message_body
    }
    with open("input.json", "w") as f:
        json.dump(input_data, f, indent=4)
        
    # Automatically execute input.py to process the AI agent and reply
    os.system("python input.py")
else:
    print("No valid message payload found.")
    exit(0)