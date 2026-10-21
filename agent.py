import os
import json
import requests
from google import genai
from dotenv import load_dotenv

# 1. Load environment variables
load_dotenv()

# 2. Check allowed numbers
allowed_env = os.getenv("ALLOWED_NUMBERS", "")
ALLOWED_NUMBERS = [num.strip() for num in allowed_env.split(",") if num.strip()]

raw_payload = os.getenv("EVENT_PAYLOAD", "{}")
try:
    payload = json.loads(raw_payload)
except json.JSONDecodeError:
    payload = {}

sender_phone = str(payload.get("from") or payload.get("sender") or payload.get("phone") or "").strip()
message_body = payload.get("message") or payload.get("text") or payload.get("body")

# If message structure is nested (like LeminAI standard format)
if not message_body and "text" in payload:
    message_body = payload["text"].get("body")

is_allowed = any(sender_phone.endswith(allowed) or allowed.endswith(sender_phone) for allowed in ALLOWED_NUMBERS)

if not is_allowed:
    print(f"Skipping: Sender {sender_phone} is not authorized.")
    exit(0)

print(f"Authorized trigger from {sender_phone}: {message_body}")

# 3. Generate response using Gemini AI agent
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=f"You are a helpful dental clinic AI assistant. Respond to this patient message professionally and concisely: {message_body}"
)
ai_reply = response.text
print(f"Generated AI Reply: {ai_reply}")

# 4. Send reply back via LeminAI WhatsApp API immediately
lemina_api_key = os.getenv("LEMINA_API_KEY")
headers = {
    "Authorization": f"Bearer {lemina_api_key}",
    "Content-Type": "application/json"
}

send_payload = {
    "phone": sender_phone,
    "type": "text",
    "message": ai_reply
}

response_api = requests.post(
    "https://api.leminai.com/api/v1/messages/service", 
    json=send_payload, 
    headers=headers
)

print("Sent to WhatsApp status:", response_api.status_code)
print("Response text:", response_api.text)