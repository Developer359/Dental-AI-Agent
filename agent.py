import os
import json
import re
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

if not message_body and "text" in payload:
    message_body = payload["text"].get("body")

is_allowed = any(sender_phone.endswith(allowed) or allowed.endswith(sender_phone) for allowed in ALLOWED_NUMBERS)

if not is_allowed:
    print(f"Skipping: Sender {sender_phone} is not authorized.")
    exit(0)

print(f"Authorized trigger from {sender_phone}: {message_body}")

# --- Cal.com Configuration ---
CAL_API_KEY = os.getenv("CAL_API_KEY")
CAL_EVENT_TYPE_ID = 7589533  # Dental Consultation event type ID

# Parse FULL_SLUG: strip full URL if accidentally set in .env
FULL_SLUG = os.getenv("CAL_EVENT_SLUG", "muhammad-subhan-8fudky/dental-consultation")
FULL_SLUG = re.sub(r'^https?://cal\.com/', '', FULL_SLUG)  # Remove URL prefix if present

# Extract username and eventTypeSlug
if "/" in FULL_SLUG:
    CAL_USERNAME, CAL_EVENT_SLUG = FULL_SLUG.split("/", 1)
else:
    CAL_USERNAME = "muhammad-subhan-8fudky"
    CAL_EVENT_SLUG = FULL_SLUG

# --- Helper: Fetch Slots ---
def get_cal_available_slots():
    if not CAL_API_KEY:
        return "Clinic Schedule: Open Monday to Saturday, 9:00 AM to 5:00 PM (Closed Sundays)."
    try:
        url = f"https://api.cal.com/v2/slots?eventTypeId={CAL_EVENT_TYPE_ID}&username={CAL_USERNAME}"
        headers = {
            "Authorization": f"Bearer {CAL_API_KEY}",
            "cal-api-version": "2024-09-04"
        }
        res = requests.get(url, headers=headers, timeout=10)
        print(f"Cal.com Slots Status: {res.status_code}")
        if res.status_code == 200:
            return json.dumps(res.json())
        print(f"Cal.com Slots Error: {res.text}")
        return "Clinic Schedule: Open Monday to Saturday, 9:00 AM to 5:00 PM (Closed Sundays)."
    except Exception as e:
        print(f"Error checking Cal.com slots: {e}")
        return "Clinic Schedule: Open Monday to Saturday, 9:00 AM to 5:00 PM (Closed Sundays)."

# --- Helper: Create Booking on Cal.com ---
def book_cal_appointment(start_time, attendee_name, description):
    if not CAL_API_KEY:
        print("Error: CAL_API_KEY is missing.")
        return False
    try:
        url = "https://api.cal.com/v2/bookings"
        headers = {
            "Authorization": f"Bearer {CAL_API_KEY}",
            "Content-Type": "application/json",
            "cal-api-version": "2024-08-13"  # Correct version for bookings endpoint
        }
        # Build a clean email from the phone number
        clean_phone = re.sub(r'[^0-9]', '', sender_phone)
        attendee_email = f"patient.{clean_phone}@whatsapp.dental"

        booking_payload = {
            "eventTypeId": CAL_EVENT_TYPE_ID,  # Use numeric ID — required by Cal.com v2
            "start": start_time,
            "attendee": {
                "name": attendee_name,
                "email": attendee_email,
                "timeZone": "Asia/Karachi",
                "language": "en"
            },
            "bookingFieldsResponses": {
                "notes": description
            },
            "metadata": {
                "source": "whatsapp-ai-agent",
                "phone": sender_phone
            }
        }
        print(f"Cal.com Booking Payload: {json.dumps(booking_payload, indent=2)}")
        res = requests.post(url, json=booking_payload, headers=headers, timeout=15)
        print("Cal.com Booking Response Status:", res.status_code)
        print("Cal.com Response Body:", res.text)
        return res.status_code in [200, 201]
    except Exception as e:
        print(f"Error creating Cal.com booking: {e}")
        return False

slots_info = get_cal_available_slots()

# 3. Generate response using Gemini AI agent
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

system_instruction = f"""
You are an automated dental clinic assistant on WhatsApp.

CLINIC HOURS:
- Mon - Sat: 9:00 AM - 5:00 PM (Asia/Karachi)
- Sun: CLOSED

AVAILABLE SLOTS DATA:
{slots_info}

INSTRUCTIONS:
1. If patient asks for available slots, list them clearly.
2. If patient selects a time, ask for their Full Name and Dental Problem.
3. When you have ALL 4 required pieces (Full Name, Dental Problem, Date, and Time), append this exact trigger tag at the bottom of your response:
[BOOKING: {{"name": "Full Name", "issue": "Dental Issue", "datetime": "YYYY-MM-DDTHH:MM:SSZ"}}]
Example datetime format: "2026-10-23T10:00:00Z"
"""

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=f"{system_instruction}\n\nPatient Message: {message_body}"
)
ai_reply = response.text
print(f"Generated AI Reply:\n{ai_reply}")

# Check for booking trigger tag
if "[BOOKING:" in ai_reply:
    try:
        json_match = re.search(r'\[BOOKING:\s*(\{.*?\}|\{.*?\n.*?\})\]', ai_reply, re.DOTALL)
        if json_match:
            booking_data = json.loads(json_match.group(1))
            
            # Execute Cal.com Booking
            success = book_cal_appointment(
                start_time=booking_data.get("datetime"),
                attendee_name=booking_data.get("name"),
                description=f"Dental Issue: {booking_data.get('issue')} | Phone: {sender_phone}"
            )
            
            if success:
                print(">>> SUCCESS: Appointment created on Cal.com dashboard!")
            else:
                print(">>> WARNING: Cal.com API call failed. Check log details above.")
            
            # Remove raw json block before sending to patient
            ai_reply = re.sub(r'\[BOOKING:\s*\{.*?\}\]', '', ai_reply, flags=re.DOTALL).strip()
    except Exception as e:
        print(f"Failed to process booking JSON tag: {e}")

# 4. Send reply back via LeminAI WhatsApp API
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