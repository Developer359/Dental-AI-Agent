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

# --- Cal.com Create Booking Function ---
def book_cal_appointment(start_time, attendee_name, attendee_email, description):
    cal_api_key = os.getenv("CAL_API_KEY")
    cal_event_slug = os.getenv("CAL_EVENT_SLUG", "muhammad-subhan-8fudky/dental-consultation")
    if not cal_api_key:
        return False
    try:
        url = "https://api.cal.com/v2/bookings"
        headers = {
            "Authorization": f"Bearer {cal_api_key}",
            "Content-Type": "application/json",
            "cal-api-version": "2024-09-04"
        }
        booking_payload = {
            "start": start_time,
            "eventTypeId": cal_event_slug,
            "attendee": {
                "name": attendee_name,
                "email": attendee_email,
                "timeZone": "Asia/Karachi"
            },
            "responses": {
                "notes": description
            }
        }
        res = requests.post(url, json=booking_payload, headers=headers, timeout=10)
        print("Cal.com Booking Response:", res.status_code, res.text)
        return res.status_code in [200, 201]
    except Exception as e:
        print(f"Error creating booking: {e}")
        return False

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

INSTRUCTIONS:
1. If the patient asks for available slots, show them valid options.
2. Once they select a slot, ask for their **Full Name** and **Dental Issue/Problem**.
3. Once you have collected the Full Name, Dental Issue, Date, and Time, output a JSON block at the very end of your message in this exact format so the script can book it:
[BOOKING: {{"name": "Full Name", "issue": "Dental Problem", "datetime": "YYYY-MM-DDTHH:MM:SSZ"}}]
Then write a friendly confirmation message to the patient.
"""

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=f"{system_instruction}\n\nPatient Message: {message_body}"
)
ai_reply = response.text
print(f"Generated AI Reply: {ai_reply}")

# Check if Gemini outputted a booking instruction block
if "[BOOKING:" in ai_reply:
    try:
        import re
        json_str = re.search(r'\[BOOKING:\s*(\{.*?\})\]', ai_reply).group(1)
        booking_data = json.loads(json_str)
        
        # Perform actual API booking on Cal.com
        success = book_cal_appointment(
            start_time=booking_data.get("datetime"),
            attendee_name=booking_data.get("name"),
            attendee_email=f"{sender_phone}@whatsapp.com", # placeholder email for WhatsApp user
            description=f"Dental Issue: {booking_data.get('issue')} | Phone: {sender_phone}"
        )
        if success:
            print("Appointment successfully booked in Cal.com!")
        
        # Clean up the AI reply text to remove the raw booking JSON block before sending to WhatsApp
        ai_reply = re.sub(r'\[BOOKING:\s*\{.*?\}]', '', ai_reply).strip()
    except Exception as e:
        print(f"Failed to parse or execute booking block: {e}")

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