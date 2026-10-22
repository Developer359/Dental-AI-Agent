import os
import json
import re
import time
import requests
from datetime import datetime, timezone, timedelta
from google import genai
from google.genai import types
from dotenv import load_dotenv

# ─────────────────────────────────────────────
# 1. Load environment
# ─────────────────────────────────────────────
load_dotenv()

LEMINA_API_KEY  = os.getenv("LEMINA_API_KEY")
GEMINI_API_KEY  = os.getenv("GEMINI_API_KEY")
SUPABASE_URL    = os.getenv("SUPABASE_URL")
SUPABASE_KEY    = os.getenv("SUPABASE_KEY")
ALLOWED_NUMBERS = [n.strip() for n in os.getenv("ALLOWED_NUMBERS", "").split(",") if n.strip()]
GEMINI_MODEL    = "gemini-3.1-flash-lite"

# ─────────────────────────────────────────────
# 2. Parse incoming WhatsApp payload
#    Handles both formats:
#      {message: "..."} and {text: {body: "..."}}
# ─────────────────────────────────────────────
raw_payload = os.getenv("EVENT_PAYLOAD", "{}")
try:
    payload = json.loads(raw_payload)
except json.JSONDecodeError:
    payload = {}

print(f"Raw payload keys: {list(payload.keys())}")

sender_phone = str(
    payload.get("from") or payload.get("sender") or payload.get("phone") or ""
).strip()

# Safely extract message body — handles nested {"text": {"body": "..."}} format
def extract_message(p):
    # Try top-level string fields first
    for key in ("message", "body"):
        val = p.get(key)
        if val and isinstance(val, str):
            return val.strip()
    # Handle {"text": {"body": "..."}} nested structure
    text_field = p.get("text")
    if isinstance(text_field, dict):
        body = text_field.get("body")
        if body and isinstance(body, str):
            return body.strip()
    if isinstance(text_field, str):
        return text_field.strip()
    return None

message_body = extract_message(payload)
print(f"sender_phone={sender_phone}, message_body={message_body!r}")

# ─────────────────────────────────────────────
# 3. Authorisation check
# ─────────────────────────────────────────────
is_allowed = any(
    sender_phone.endswith(a) or a.endswith(sender_phone)
    for a in ALLOWED_NUMBERS
)
if not is_allowed:
    print(f"Skipping: {sender_phone} not authorised.")
    exit(0)

if not message_body:
    print("No message body found — skipping.")
    exit(0)

print(f"Authorised trigger from {sender_phone}: {message_body}")

# ─────────────────────────────────────────────
# 4. Conversation state (per phone)
#    Stored in ./chat_history/{phone}.json
# ─────────────────────────────────────────────
HISTORY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chat_history")
os.makedirs(HISTORY_DIR, exist_ok=True)

def _path(phone):
    return os.path.join(HISTORY_DIR, re.sub(r"[^0-9]", "", phone) + ".json")

def load_state(phone):
    p = _path(phone)
    if os.path.exists(p):
        try:
            s = json.load(open(p, encoding="utf-8"))
            s.setdefault("messages", [])
            s.setdefault("draft", {
                "patient_name": None, "appointment_date": None,
                "appointment_time": None, "dental_issue": None
            })
            s["messages"] = s["messages"][-12:]
            return s
        except Exception:
            pass
    return {
        "messages": [],
        "draft": {
            "patient_name": None, "appointment_date": None,
            "appointment_time": None, "dental_issue": None
        }
    }

def save_state(phone, state):
    state["messages"] = state["messages"][-12:]
    json.dump(state, open(_path(phone), "w", encoding="utf-8"), ensure_ascii=False, indent=2)

def clear_state(phone):
    p = _path(phone)
    if os.path.exists(p):
        os.remove(p)
    print(f"State cleared for {phone}")

# ─────────────────────────────────────────────
# 5. Supabase helpers
# ─────────────────────────────────────────────
SB_HDR = {
    "apikey":        SUPABASE_KEY or "",
    "Authorization": f"Bearer {SUPABASE_KEY or ''}",
    "Content-Type":  "application/json",
    "Prefer":        "return=representation",
}

def slot_available(date_str, time_str):
    """Returns True=free, False=taken, None=error"""
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/dental_appointments",
            headers=SB_HDR,
            params={
                "appointment_date": f"eq.{date_str}",
                "appointment_time": f"eq.{time_str}",
                "status": "neq.cancelled",
                "select": "id"
            },
            timeout=10
        )
        print(f"Availability check >> {r.status_code}: {r.text}")
        return len(r.json()) == 0 if r.status_code == 200 else None
    except Exception as e:
        print(f"Availability error: {e}")
        return None

def insert_booking(name, phone, issue, date_str, time_str):
    """Returns (True, booking_id) or (False, error_text)"""
    try:
        r = requests.post(
            f"{SUPABASE_URL}/rest/v1/dental_appointments",
            json={
                "patient_name":     name,
                "phone_number":     phone,
                "dental_issue":     issue,
                "appointment_date": date_str,
                "appointment_time": time_str,
                "status":           "pending"
            },
            headers=SB_HDR,
            timeout=15
        )
        print(f"Insert >> {r.status_code}: {r.text}")
        if r.status_code in [200, 201]:
            data = r.json()
            return True, data[0].get("id", "?") if data else "?"
        return False, r.text
    except Exception as e:
        print(f"Insert error: {e}")
        return False, str(e)

# ─────────────────────────────────────────────
# 6. Load state for this patient
# ─────────────────────────────────────────────
state   = load_state(sender_phone)
draft   = state["draft"]
history = state["messages"]
print(f"State: draft={draft}, turns={len(history)}")

# ─────────────────────────────────────────────
# 7. Build system prompt (compact)
# ─────────────────────────────────────────────
now_pk   = datetime.now(timezone(timedelta(hours=5)))
today    = now_pk.strftime("%Y-%m-%d")
tomorrow = (now_pk + timedelta(days=1)).strftime("%Y-%m-%d")

def val(v): return f'"{v}"' if v else "not yet collected"

missing        = [k for k, v in draft.items() if not v]
collected_str  = " | ".join(f"{k}={val(v)}" for k, v in draft.items() if v) or "nothing yet"
missing_str    = ", ".join(missing) if missing else "ALL COLLECTED"

system_prompt = (
    f"You are a dental clinic WhatsApp assistant. "
    f"Today={today} (tomorrow={tomorrow}). "
    f"Clinic hours: Mon-Sat 09:00-17:00 Pakistan time (UTC+5). Closed Sundays.\n\n"
    f"ALREADY KNOWN for this patient: {collected_str}\n"
    f"STILL MISSING: {missing_str}\n\n"
    f"RULES:\n"
    f"1. Extract booking info from the patient message. "
    f"   Convert dates to YYYY-MM-DD and times to HH:MM:00 (24h, Pakistan time).\n"
    f"2. Ask ONLY for still-missing fields. Never re-ask already-known info.\n"
    f"3. If patient gives partial info (e.g. only date+time), acknowledge and ask for the rest.\n"
    f"4. If patient gives ALL info in one message, extract everything at once.\n"
    f"5. ALWAYS end your reply with this exact tag for any newly extracted fields:\n"
    f'[UPDATE: {{"patient_name":null,"appointment_date":null,"appointment_time":null,"dental_issue":null}}]\n'
    f"   Use null for fields NOT mentioned in THIS message. Do not repeat already-known values.\n"
    f"6. Do NOT say 'booking confirmed' — the system handles that automatically.\n"
    f"7. Keep replies short, warm, and WhatsApp-friendly."
)

# ─────────────────────────────────────────────
# 8. Build Gemini contents using proper types
#    FIX: Use types.Content + types.Part, not raw dicts
# ─────────────────────────────────────────────
gemini_contents = []

# Add conversation history
for msg in history:
    gemini_contents.append(
        types.Content(
            role=msg["role"],
            parts=[types.Part(text=msg["content"])]
        )
    )

# Add current patient message
gemini_contents.append(
    types.Content(
        role="user",
        parts=[types.Part(text=message_body)]
    )
)

# ─────────────────────────────────────────────
# 9. Call Gemini with retry on 503
# ─────────────────────────────────────────────
client = genai.Client(api_key=GEMINI_API_KEY)
ai_reply = None
last_error = None

for attempt in range(3):
    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=gemini_contents,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.3,
            )
        )
        ai_reply = response.text.strip()
        print(f"AI reply (attempt {attempt+1}):\n{ai_reply}")
        break
    except Exception as e:
        last_error = e
        print(f"Gemini error (attempt {attempt+1}): {e}")
        if attempt < 2:
            time.sleep(4)

if ai_reply is None:
    print(f"All Gemini attempts failed: {last_error}")
    ai_reply = (
        "I'm sorry, our assistant is temporarily busy. "
        "Please try again in a moment or call the clinic directly."
    )

# ─────────────────────────────────────────────
# 10. Parse [UPDATE] tag and merge into draft
# ─────────────────────────────────────────────
update_match = re.search(r'\[UPDATE:\s*(\{.*?\})\]', ai_reply, re.DOTALL)
if update_match:
    try:
        updates = json.loads(update_match.group(1))
        for field, value in updates.items():
            if value and field in draft:
                draft[field] = str(value).strip()
                print(f"  Draft << {field} = {draft[field]}")
    except Exception as e:
        print(f"UPDATE parse error: {e}")
    # Strip the tag from the patient-facing reply
    ai_reply = re.sub(r'\[UPDATE:\s*\{.*?\}\]', '', ai_reply, flags=re.DOTALL).strip()

# ─────────────────────────────────────────────
# 11. All 4 fields collected? Check availability
#     and insert booking into Supabase
# ─────────────────────────────────────────────
final_reply  = ai_reply
booking_done = False

if all(draft[k] for k in ["patient_name", "appointment_date", "appointment_time", "dental_issue"]):
    print(f"All fields ready: {draft}")
    avail = slot_available(draft["appointment_date"], draft["appointment_time"])

    if avail is True:
        ok, result = insert_booking(
            name     = draft["patient_name"],
            phone    = sender_phone,
            issue    = draft["dental_issue"],
            date_str = draft["appointment_date"],
            time_str = draft["appointment_time"],
        )
        if ok:
            final_reply = (
                f"*Appointment Confirmed!*\n\n"
                f"Name  : {draft['patient_name']}\n"
                f"Date  : {draft['appointment_date']}\n"
                f"Time  : {draft['appointment_time'][:5]} (Pakistan time)\n"
                f"Issue : {draft['dental_issue']}\n\n"
                f"We look forward to seeing you. Reply *cancel* to cancel anytime."
            )
            print(f">>> Booking saved to Supabase. ID={result}")
            booking_done = True
            clear_state(sender_phone)
        else:
            final_reply = (
                "Sorry, something went wrong saving your booking. "
                "Please try again or call the clinic directly."
            )
            print(f">>> Supabase insert FAILED: {result}")

    elif avail is False:
        final_reply = (
            f"Sorry, *{draft['appointment_date']} at {draft['appointment_time'][:5]}* "
            f"is already booked.\n\n"
            f"Please choose a different date or time and I'll check again for you."
        )
        draft["appointment_date"] = None
        draft["appointment_time"] = None
        print(">>> Slot taken — cleared date/time from draft.")

    else:
        final_reply = (
            "Sorry, I couldn't verify availability right now. Please try again in a moment."
        )

# ─────────────────────────────────────────────
# 12. Save conversation state
# ─────────────────────────────────────────────
if not booking_done:
    state["messages"].append({"role": "user",  "content": message_body})
    state["messages"].append({"role": "model", "content": final_reply})
    state["draft"] = draft
    save_state(sender_phone, state)

# ─────────────────────────────────────────────
# 13. Send reply via LeminAI WhatsApp
# ─────────────────────────────────────────────
wa_res = requests.post(
    "https://app.leminai.com/api/v1/messages/service",
    json={"to": sender_phone, "type": "text", "text": {"body": final_reply}},
    headers={
        "Authorization": f"Bearer {LEMINA_API_KEY}",
        "Content-Type":  "application/json"
    },
)
print(f"WhatsApp >> {wa_res.status_code}: {wa_res.text}")