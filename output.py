import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

# Read data from input.json
if not os.path.exists("input.json"):
    print("Error: input.json not found.")
    exit(1)

with open("input.json", "r") as f:
    data = json.load(f)

sender_phone = data.get("sender")
ai_reply = data.get("ai_reply") # Or your generated AI text variable

if sender_phone and ai_reply:
    lemina_api_key = os.getenv("LEMINA_API_KEY")
    
    headers = {
        "Authorization": f"Bearer {lemina_api_key}",
        "Content-Type": "application/json"
    }
    
    # Correct payload format matching LeminAI documentation
    send_payload = {
        "phone": sender_phone,
        "type": "text",
        "message": ai_reply
    }
    
    # Correct endpoint URL from the API Docs
    response_api = requests.post(
        "https://api.leminai.com/api/v1/messages/service", 
        json=send_payload, 
        headers=headers
    )
    
    print("Sent to WhatsApp status:", response_api.status_code)
    print("Response text:", response_api.text)
else:
    print("Missing sender or reply content.")