import os
import json
import requests
from dotenv import load_dotenv

# Load variables from .env file
load_dotenv()

# Read data from input.json
if not os.path.exists("input.json"):
    print("Error: input.json not found.")
    exit(1)

with open("input.json", "r") as f:
    data = json.load(f)

sender_phone = data.get("sender")
ai_reply = data.get("ai_reply") # Expects reply generated from agent.py

if sender_phone and ai_reply:
    lemina_api_key = os.getenv("LEMINA_API_KEY")
    headers = {
        "Authorization": f"Bearer {lemina_api_key}",
        "Content-Type": "application/json"
    }
    send_payload = {
        "to": sender_phone,
        "message": ai_reply
    }
    
    # Send response back to WhatsApp via LeminAI API
    response_api = requests.post("https://api.leminai.com/v1/messages", json=send_payload, headers=headers)
    print("Sent to WhatsApp status:", response_api.status_code)
else:
    print("Missing sender or reply content.")