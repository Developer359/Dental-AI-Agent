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

# --- Cal.com Slot Checker Function ---
def get_cal_available_slots():
    cal_api_key = os.getenv("CAL_API_KEY")
    cal_event_slug = os.getenv("CAL_EVENT_SLUG", "muhammad-subhan-8fudky/dental-consultation")
    if not cal_api_key:
        return "Clinic Schedule: Open Monday to Saturday, 9:00 AM to 5:00 PM (Closed Sundays)."
    try:
        url = f"https://api.cal.com/v2/slots?eventTypeSlug={cal_event_slug}"
        headers = {
            "Authorization": f"Bearer {cal_api_key}",
            "cal-api-version": "2024-09-04"
        }
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            return json.dumps(res.json())
        return "Clinic Schedule: Open Monday to Saturday, 9:00 AM to 5:00 PM (Closed Sundays)."
    except Exception as e:
        print(f"Error checking Cal.com slots: {e}")
        return "Clinic Schedule: Open Monday to Saturday, 9:00 AM to 5:00 PM (Closed Sundays)."

# Fetch available slots from Cal.com
slots_info = get_cal_available_slots()

# 3. Generate response using Gemini AI agent
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

system_instruction = f"""
You are a professional dental clinic AI assistant.

CLINIC OPERATING HOURS:
- Monday to Saturday: 9:00 AM to 5:00 PM
- Sunday: CLOSED

AVAILABLE CALENDAR SLOTS DATA:
{slots_info}

INSTRUCTIONS FOR INTENT HANDLING:
1. **General Information Query:**
   If the patient is asking general dental questions, clinic location, or general information, answer professionally, concisely, and directly.

2. **Appointment Booking Request:**
   If the patient wants to book an appointment:
   - Step 1: Check available slots above. Tell them available dates/times between Monday-Saturday (9:00 AM to 5:00 PM). Never offer Sundays or times outside 9:00 AM - 5:00 PM.
   - Step 2: Once they select a slot, ask for their **Full Name** and **Dental Issue/Problem**.
   - Step 3: When Full Name, Dental Issue, Date, and Time are provided, confirm that their appointment request is recorded with status **Pending**.

Patient Phone Number: {sender_phone}
"""

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=f"{system_instruction}\n\nPatient Message: {message_body}"
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
    "to": sender_phone,
    "type": "text",
    "text": {
        "body": ai_reply
    }
}

response_api = requests.post(
    "https://app.leminai.com/api/v1/messages/service", 
    json=send_payload, 
    headers=headers
)

print("Sent to WhatsApp status:", response_api.status_code)
print("Response text:", response_api.text)