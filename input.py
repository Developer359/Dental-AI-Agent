import os
import json
import requests
from google import genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Gemini client
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Read data from input.json created by test-number.py
if not os.path.exists("input.json"):
    print("Error: input.json not found.")
    exit(1)

with open("input.json", "r") as f:
    data = json.load(f)

sender_phone = data.get("sender")
message_body = data.get("message")

if message_body and sender_phone:
    print(f"Processing message for {sender_phone}: {message_body}")

    # Generate response using Gemini AI agent
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=f"You are a helpful dental clinic AI assistant. Respond to this patient message professionally and concisely: {message_body}"
    )
    ai_reply = response.text
    print(f"Generated AI Reply: {ai_reply}")

    # Send reply back via LeminAI WhatsApp API
    lemina_api_key = os.getenv("LEMINA_API_KEY")
    headers = {
        "Authorization": f"Bearer {lemina_api_key}",
        "Content-Type": "application/json"
    }
    send_payload = {
        "to": sender_phone,
        "message": ai_reply
    }
    
    # Send the request to WhatsApp via LeminAI
    response_api = requests.post("https://api.leminai.com/v1/messages", json=send_payload, headers=headers)
    print("Sent to WhatsApp status:", response_api.status_code)
else:
    print("Invalid data inside input.json")