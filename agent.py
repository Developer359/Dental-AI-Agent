import os
import json
import re
import requests
from datetime import datetime, timezone, timedelta
from google import genai
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

# ─────────────────────────────────────────────
# 2. Parse incoming payload
# ─────────────────────────────────────────────
raw_payload = os.getenv("EVENT_PAYLOAD", "{}")
try:
    payload = json.loads(raw_payload)
except json.JSONDecodeError:
    payload = {}

sender_phone = str(
    payload.get("from") or payload.get("sender") or payload.get("phone") or ""
).strip()
message_body = payload.get("message") or payload.get("text") or payload.get("body")
if not message_body and "text" in payload:
    message_body = payload["text"].get("body")

is_allowed = any(
    sender_phone.endswith(a) or a.endswith(sender_phone) for a in ALLOWED_NUMBERS
)
if not is_allowed:
    print(f"Skipping: {sender_phone} not authorised.")
    exit(0)

print(f"Trigger from {sender_phone}: {message_body}")

# ─────────────────────────────────────────────
# 3. Conversation state (per phone)
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
            s.setdefault("draft", {"patient_name": None, "appointment_date": None,
                                   "appointment_time": None, "dental_issue": None})
            s["messages"] = s["messages"][-12:]   # keep last 12 turns
            return s
        except Exception:
            pass
    return {"messages": [], "draft": {"patient_name": None, "appointment_date": None,
                                      "appointment_time": None, "dental_issue": None}}

def save_state(phone, state):
    state["messages"] = state["messages"][-12:]
    json.dump(state, open(_path(phone), "w", encoding="utf-8"), ensure_ascii=False, indent=2)

def clear_state(phone):
    p = _path(phone)
    if os.path.exists(p):
        os.remove(p)
    print(f"State cleared for {phone}")

# ─────────────────────────────────────────────
# 4. Supabase helpers
# ─────────────────────────────────────────────
SB_HDR = {
    "apikey":        SUPABASE_KEY or "",
    "Authorization": f"Bearer {SUPABASE_KEY or ''}",
    "Content-Type":  "application/json",
    "Prefer":        "return=representation",
}

def slot_available(date_str, time_str):
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/dental_appointments",
            headers=SB_HDR,
            params={"appointment_date": f"eq.{date_str}",
                    "appointment_time": f"eq.{time_str}",
                    "status": "neq.cancelled",
                    "select": "id"},
            timeout=10
        )
        print(f"Availability check >> {r.status_code}: {r.text}")
        return len(r.json()) == 0 if r.status_code == 200 else None
    except Exception as e:
        print(f"Availability error: {e}")
        return None

def insert_booking(name, phone, issue, date_str, time_str):
    try:
        r = requests.post(
            f"{SUPABASE_URL}/rest/v1/dental_appointments",
            json={"patient_name": name, "phone_number": phone,
                  "dental_issue": issue, "appointment_date": date_str,
                  "appointment_time": time_str, "status": "pending"},
            headers=SB_HDR, timeout=15
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
# 5. Load state
# ─────────────────────────────────────────────
state   = load_state(sender_phone)
draft   = state["draft"]
history = state["messages"]
print(f"State: draft={draft}, turns={len(history)}")

# ─────────────────────────────────────────────
# 6. Build compact system prompt
# ─────────────────────────────────────────────
now_pk = datetime.now(timezone(timedelta(hours=5)))
today  = now_pk.strftime("%Y-%m-%d")
tomorrow = (now_pk + timedelta(days=1)).strftime("%Y-%m-%d")

def val(v): return f'"{v}"' if v else "unknown"

missing = [k for k, v in draft.items() if not v]
collected_str = " | ".join(
    f"{k}={val(v)}" for k, v in draft.items() if v
) or "nothing yet"
missing_str = ", ".join(missing) if missing else "ALL COLLECTED"

system_prompt = (
    f"You are a dental clinic WhatsApp assistant. Today={today} (tomorrow={tomorrow}). "
    f"Clinic: Mon-Sat 09:00-17:00 Pakistan time (UTC+5). Closed Sundays.\n"
    f"ALREADY KNOWN: {collected_str}\n"
    f"STILL MISSING: {missing_str}\n\n"
    f"Rules:\n"
    f"1. Extract booking info from patient message (date→YYYY-MM-DD, time→HH:MM:00 24h PKT).\n"
    f"2. Ask ONLY for still-missing fields. Never re-ask what is already known.\n"
    f"3. If patient gives partial info (e.g. only date+time), acknowledge it and ask for rest.\n"
    f"4. End your reply with this tag for ANY newly extracted fields:\n"
    f'[UPDATE: {{"patient_name":null,"appointment_date":null,"appointment_time":null,"dental_issue":null}}]\n'
    f"   Use null for fields NOT mentioned in THIS message.\n"
    f"5. Do NOT say 'booking confirmed' — system handles that.\n"
    f"6. Keep replies short and friendly."
)

# ─────────────────────────────────────────────
# 7. Build Gemini conversation
# ─────────────────────────────────────────────
contents = [
    {"role": "user",  "parts": [{"text": system_prompt}]},
    {"role": "model", "parts": [{"text": "Understood. I'll collect missing info and always end with the [UPDATE] tag."}]},
]
for msg in history:
    contents.append({"role": msg["role"], "parts": [{"text": msg["content"]}]})
contents.append({"role": "user", "parts": [{"text": message_body}]})

# ─────────────────────────────────────────────
# 8. Call Gemini
# ─────────────────────────────────────────────
client   = genai.Client(api_key=GEMINI_API_KEY)
response = client.models.generate_content(model="gemini-3.1-flash-lite", contents=contents)
ai_reply = response.text.strip()
print(f"AI reply:\n{ai_reply}")

# ─────────────────────────────────────────────
# 9. Parse [UPDATE] tag → merge into draft
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
    ai_reply = re.sub(r'\[UPDATE:\s*\{.*?\}\]', '', ai_reply, flags=re.DOTALL).strip()

# ─────────────────────────────────────────────
# 10. All 4 fields collected → check & book
# ─────────────────────────────────────────────
final_reply = ai_reply
booking_done = False

if all(draft[k] for k in ["patient_name", "appointment_date", "appointment_time", "dental_issue"]):
    print(f"All fields ready: {draft}")
    avail = slot_available(draft["appointment_date"], draft["appointment_time"])

    if avail is True:
        ok, result = insert_booking(
            name      = draft["patient_name"],
            phone     = sender_phone,
            issue     = draft["dental_issue"],
            date_str  = draft["appointment_date"],
            time_str  = draft["appointment_time"],
        )
        if ok:
            final_reply = (
                f"✅ *Appointment Confirmed!*\n\n"
                f"👤 Name   : {draft['patient_name']}\n"
                f"📅 Date   : {draft['appointment_date']}\n"
                f"⏰ Time   : {draft['appointment_time'][:5]} (Pakistan time)\n"
                f"🦷 Issue  : {draft['dental_issue']}\n\n"
                f"We'll see you at the clinic. Reply *cancel* to cancel anytime."
            )
            print(f">>> Booking saved. ID={result}")
            booking_done = True
            clear_state(sender_phone)
        else:
            final_reply = (
                f"⚠️ Sorry, something went wrong while saving your booking. "
                f"Please try again or call the clinic directly."
            )
            print(f">>> Insert FAILED: {result}")

    elif avail is False:
        final_reply = (
            f"❌ *{draft['appointment_date']} at {draft['appointment_time'][:5]}* is already booked.\n\n"
            f"Please choose a different date or time and I'll check again for you. 😊"
        )
        draft["appointment_date"] = None
        draft["appointment_time"] = None
        print(">>> Slot taken — cleared date/time.")
    else:
        final_reply = "⚠️ Couldn't check availability. Please try again in a moment."

# ─────────────────────────────────────────────
# 11. Save state (skip if booking just cleared it)
# ─────────────────────────────────────────────
if not booking_done:
    state["messages"].append({"role": "user",  "content": message_body})
    state["messages"].append({"role": "model", "content": final_reply})
    state["draft"] = draft
    save_state(sender_phone, state)

# ─────────────────────────────────────────────
# 12. Send WhatsApp reply via LeminAI
# ─────────────────────────────────────────────
wa_res = requests.post(
    "https://app.leminai.com/api/v1/messages/service",
    json={"to": sender_phone, "type": "text", "text": {"body": final_reply}},
    headers={"Authorization": f"Bearer {LEMINA_API_KEY}", "Content-Type": "application/json"},
)
print(f"WhatsApp >> {wa_res.status_code}: {wa_res.text}")