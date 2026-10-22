<div align="center">

# 🦷 Dental AI Agent

### WhatsApp-Powered Dental Appointment Booking with AI

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Gemini AI](https://img.shields.io/badge/Gemini-3.1_Flash_Lite-4285F4?style=for-the-badge&logo=google&logoColor=white)](https://ai.google.dev)
[![Supabase](https://img.shields.io/badge/Supabase-Database-3ECF8E?style=for-the-badge&logo=supabase&logoColor=white)](https://supabase.com)
[![GitHub Actions](https://img.shields.io/badge/GitHub_Actions-Serverless-2088FF?style=for-the-badge&logo=github-actions&logoColor=white)](https://github.com/features/actions)
[![WhatsApp](https://img.shields.io/badge/WhatsApp-Messaging-25D366?style=for-the-badge&logo=whatsapp&logoColor=white)](https://whatsapp.com)

> **A fully serverless, AI-powered dental clinic assistant that automatically handles WhatsApp appointment bookings — no server required, runs 100% free on GitHub Actions.**

</div>

---

## 📋 Table of Contents

- [What is This Project?](#-what-is-this-project)
- [How It Works](#-how-it-works)
- [Architecture](#-architecture)
- [Conversation Flow](#-conversation-flow)
- [Project Structure](#-project-structure)
- [Prerequisites](#-prerequisites)
- [Complete Setup Guide](#-complete-setup-guide)
  - [1. Supabase Database](#1-supabase-database-setup)
  - [2. LeminAI WhatsApp](#2-leminai-whatsapp-setup)
  - [3. Google Gemini AI](#3-google-gemini-ai-setup)
  - [4. GitHub Repository & Secrets](#4-github-repository--secrets)
  - [5. Connecting LeminAI to GitHub](#5-connecting-leminai-webhook-to-github)
- [GitHub Actions Workflow Explained](#-github-actions-workflow-explained)
- [Environment Variables Reference](#-environment-variables-reference)
- [How the Agent Logic Works](#-how-the-agent-logic-works)
- [Testing](#-testing)
- [Troubleshooting](#-troubleshooting)

---

## 🦷 What is This Project?

**Dental AI Agent** is a **zero-server WhatsApp chatbot** for dental clinics. When a patient sends a WhatsApp message, the AI automatically:

1. ✅ **Understands natural language** — "Book me next Monday at 9am" works perfectly
2. ✅ **Remembers the conversation** — collects info across multiple messages without asking twice
3. ✅ **Checks availability** — queries Supabase to see if the slot is free before confirming
4. ✅ **Books the appointment** — saves directly to Supabase database
5. ✅ **Replies instantly** — sends a confirmation back via WhatsApp

**No monthly server cost.** Runs entirely on GitHub Actions (free tier = 2,000 minutes/month).

---

## ⚙️ How It Works
<img src="flow.png" alt="Flow Diagram" width="800" height="500">

### Step-by-Step Flow

```
1. Patient sends WhatsApp message
         ↓
2. LeminAI receives the message
   and fires a webhook to GitHub
         ↓
3. GitHub Actions wakes up
   and runs agent.py
         ↓
4. agent.py reads conversation
   history from chat_history/
   and calls Gemini AI
         ↓
5. Gemini extracts booking info
   and returns structured [UPDATE] tag
         ↓
6. If all 4 fields collected:
   → Check Supabase for conflicts
   → Insert booking if slot is free
         ↓
7. Send WhatsApp reply to patient
   via LeminAI API
```

### Required Information to Book
The agent collects exactly **4 fields** — and only asks for what is still missing:

| Field | Example |
|-------|---------|
| **Patient Name** | Muhammad Rahman |
| **Appointment Date** | 2026-10-28 (understands "next Wednesday") |
| **Appointment Time** | 09:00:00 (understands "9am", "3pm") |
| **Dental Issue** | Toothache, broken tooth, cavity, etc. |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   PATIENT (WhatsApp)                    │
└────────────────────────┬────────────────────────────────┘
                         │ WhatsApp Message
                         ▼
┌─────────────────────────────────────────────────────────┐
│              LeminAI (WhatsApp Gateway)                 │
│  • Receives WhatsApp messages                           │
│  • Fires repository_dispatch webhook to GitHub          │
│  • Sends AI reply back to patient                       │
└────────────────────────┬────────────────────────────────┘
                         │ repository_dispatch event
                         ▼
┌─────────────────────────────────────────────────────────┐
│              GitHub Actions (Serverless)                │
│  Trigger: repository_dispatch [whatsapp_message]        │
│  • Spins up ubuntu-latest runner                        │
│  • Sets up Python 3.12                                  │
│  • Installs dependencies                                │
│  • Runs agent.py with secrets injected                  │
└────────────────────────┬────────────────────────────────┘
                         │ Runs agent.py
                         ▼
┌─────────────────────────────────────────────────────────┐
│                   agent.py (Brain)                      │
│                                                         │
│  ┌──────────────┐    ┌────────────────┐                 │
│  │ Conversation │    │  Google Gemini │                 │
│  │   History    │───▶│ 3.1 Flash Lite │                 │
│  │ (JSON files) │    │   (NLP/AI)     │                 │
│  └──────────────┘    └───────┬────────┘                 │
│                              │ [UPDATE] tag              │
│                              ▼                          │
│                    ┌─────────────────┐                  │
│                    │    Supabase     │                  │
│                    │  (PostgreSQL)   │                  │
│                    │ Check & Book    │                  │
│                    └─────────────────┘                  │
└─────────────────────────────────────────────────────────┘
```
<img width="1058" height="529" alt="image" src="https://github.com/user-attachments/assets/0e09f536-fbf9-406c-9473-050b53517daa" />

---

## 💬 Conversation Flow

The agent is smart — it **remembers partial information** across multiple messages:

### Example 1: Patient gives all info at once
```
Patient : "Book me Wednesday October 28th at 9am, my name is Ahmed, I have toothache"
Agent   : ✅ Appointment Confirmed!
          Name  : Ahmed
          Date  : 2026-10-28
          Time  : 09:00 (Pakistan time)
          Issue : toothache
```

### Example 2: Patient gives info across multiple messages
```
Patient : "I want to book tomorrow at 10am"
Agent   : "Got it! 2026-10-23 at 10:00am noted. What is your name and dental issue?"

Patient : "Sara, I have a cavity"
Agent   : ✅ Appointment Confirmed!
          Name  : Sara
          Date  : 2026-10-23
          Time  : 10:00 (Pakistan time)
          Issue : cavity
```

### Example 3: Slot already booked
```
Patient : "Book me Monday at 9am, I'm Ali, broken tooth"
Agent   : "❌ Monday at 09:00 is already booked.
           Please choose a different date or time."
```

---

## 📁 Project Structure

```
Dental-AI-Agent/
│
├── agent.py                    # Main AI agent logic
├── .env                        # Local environment variables (never commit!)
├── .gitignore                  # Excludes .env and chat_history/
├── banner.png                  # README banner image
├── flow.png                    # Architecture flow diagram
│
├── chat_history/               # Auto-created, gitignored
│   └── 923369013306.json       # Per-patient conversation state
│
└── .github/
    └── workflows/
        └── Agent.yml           # GitHub Actions workflow
```

### `agent.py` — What each section does

| Section | Lines | Purpose |
|---------|-------|---------|
| Load environment | 1–21 | Reads API keys from env vars |
| Parse payload | 23–60 | Extracts phone number and message from WhatsApp webhook |
| Auth check | 62–70 | Only processes messages from allowed numbers |
| Conversation state | 72–115 | Load/save per-patient JSON history |
| Supabase helpers | 117–160 | Check availability + insert booking |
| Build prompt | 162–195 | Constructs compact system prompt with known/missing info |
| Gemini call | 197–235 | Calls AI with 3 retries on 503 errors |
| Parse UPDATE tag | 237–248 | Extracts structured booking data from AI response |
| Book appointment | 250–290 | Validates, checks Supabase, inserts row |
| Send reply | 292–310 | Sends final message back via LeminAI |

---

## 📦 Prerequisites

Before starting, you need accounts on these platforms (all free):

| Service | Purpose | Free Tier |
|---------|---------|-----------|
| [GitHub](https://github.com) | Hosts code + runs agent | 2,000 min/month free |
| [Supabase](https://supabase.com) | PostgreSQL database | 500MB free |
| [LeminAI](https://leminai.com) | WhatsApp gateway + webhook | Free tier available |
| [Google AI Studio](https://aistudio.google.com) | Gemini AI API | Free tier available |

---

## 🚀 Complete Setup Guide

### 1. Supabase Database Setup

**a) Create a Supabase project**
1. Go to [supabase.com](https://supabase.com) → **New Project**
2. Note your **Project URL** (e.g. `https://xxxxxyyyyy.supabase.co`)

**b) Create the appointments table**

Go to **SQL Editor** and run this SQL:

```sql
CREATE TABLE IF NOT EXISTS dental_appointments (
    id               UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    patient_name     TEXT NOT NULL,
    phone_number     TEXT NOT NULL,
    dental_issue     TEXT NOT NULL,
    appointment_date DATE NOT NULL,
    appointment_time TIME NOT NULL,
    status           TEXT DEFAULT 'pending',
    created_at       TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);
```

**c) Get your API key**
1. Go to **Project Settings** → **API**
2. Copy the **Secret key** (`sb_secret_...`) — this is your `SUPABASE_KEY`
3. Copy the **Project URL** — this is your `SUPABASE_URL`

> ⚠️ Use the **Secret key**, not the anon/public key. The secret key has full database access.

---

### 2. LeminAI WhatsApp Setup

**a) Create a LeminAI account**
1. Sign up at [leminai.com](https://leminai.com)
2. Connect your WhatsApp Business number
3. Go to **API Settings** → copy your **API Key** → this is your `LEMINA_API_KEY`

**b) Configure the Webhook**

In LeminAI webhook settings, set the URL to trigger GitHub Actions:

```
https://api.github.com/repos/YOUR_USERNAME/YOUR_REPO/dispatches
```

With these headers:
```
Authorization: Bearer YOUR_GITHUB_PAT_TOKEN
Content-Type: application/json
```

And this body template:
```json
{
  "event_type": "whatsapp_message",
  "client_payload": {
    "from": "{{sender_phone}}",
    "text": {
      "body": "{{message_body}}"
    }
  }
}
```

> See [Section 5](#5-connecting-leminai-webhook-to-github) for the full LeminAI → GitHub connection guide.

---

### 3. Google Gemini AI Setup

1. Go to [aistudio.google.com](https://aistudio.google.com)
2. Click **Get API Key** → **Create API Key**
3. Copy the key → this is your `GEMINI_API_KEY`

> **Free tier**: 15 requests per minute, limited daily quota. For production use, add billing at [console.cloud.google.com](https://console.cloud.google.com).

---

### 4. GitHub Repository & Secrets

**a) Fork or create the repository**
```bash
git clone https://github.com/YOUR_USERNAME/Dental-AI-Agent.git
cd Dental-AI-Agent
```

**b) Add GitHub Secrets**

Go to your repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

Add each of these:

| Secret Name | Value | Where to get it |
|-------------|-------|----------------|
| `GEMINI_API_KEY` | `AIza...` | Google AI Studio |
| `LEMINA_API_KEY` | `lmn_sk_...` | LeminAI dashboard |
| `SUPABASE_URL` | `https://xxx.supabase.co` | Supabase Project Settings |
| `SUPABASE_KEY` | `sb_secret_...` | Supabase Project Settings → API |
| `ALLOWED_NUMBERS` | `923369013306,03369013306` | Your WhatsApp numbers (comma-separated) |

> ⚠️ `ALLOWED_NUMBERS` is a security filter — only these phone numbers will be processed. Add both formats (with and without country code) for safety.

**c) Create a GitHub Personal Access Token (PAT)**

This is needed for LeminAI to trigger GitHub Actions:

1. GitHub → **Settings** (your profile) → **Developer settings** → **Personal access tokens** → **Fine-grained tokens**
2. Click **Generate new token**
3. Set permissions: **Repository permissions** → **Actions** → **Read and Write**
4. Copy the token — you'll use it in LeminAI webhook config

---

### 5. Connecting LeminAI Webhook to GitHub

This is the critical link that makes everything work:

**In LeminAI:**
1. Go to **Automations** or **Webhooks** section
2. Create a new automation triggered on **incoming message**
3. Set the action to **HTTP Request** with:

```
Method: POST
URL: https://api.github.com/repos/YOUR_USERNAME/Dental-AI-Agent/dispatches

Headers:
  Authorization: Bearer ghp_YOUR_GITHUB_PAT_TOKEN
  Content-Type: application/json
  Accept: application/vnd.github+json
  X-GitHub-Api-Version: 2022-11-28

Body:
{
  "event_type": "whatsapp_message",
  "client_payload": {MESSAGE_PAYLOAD_FROM_LEMIN}
}
```

Once connected, every WhatsApp message → LeminAI → GitHub → agent.py runs automatically.

---

### Local Development Setup

For testing locally:

```bash
# Clone the repo
git clone https://github.com/Developer359/Dental-AI-Agent.git
cd Dental-AI-Agent

# Install dependencies
pip install requests google-genai python-dotenv

# Create your .env file
cp .env.example .env
# Edit .env and fill in your keys

# Test with a simulated message
$env:EVENT_PAYLOAD = '{"from":"923369013306","text":{"body":"Book me tomorrow at 10am, name Ali, cavity"}}'
python agent.py
```

---

## 🔧 GitHub Actions Workflow Explained

**File:** `.github/workflows/Agent.yml`

```yaml
name: Dental AI Agent WhatsApp Responder
```
> The display name shown in the GitHub Actions tab.

---

```yaml
on:
  repository_dispatch:
    types: [whatsapp_message]
```
> **Trigger**: The workflow runs ONLY when an external system (LeminAI) sends a POST request to the GitHub API with `event_type: "whatsapp_message"`. This is how a WhatsApp message wakes up the agent. No schedule, no push — purely event-driven.

---

```yaml
jobs:
  run-agent:
    runs-on: ubuntu-latest
```
> **Job definition**: Creates a fresh Ubuntu Linux virtual machine for every single message. Each run is isolated — no state between runs (state is handled by `chat_history/*.json` files in the repo).

---

```yaml
    steps:
      - name: Checkout Code
        uses: actions/checkout@v4
```
> **Step 1 — Checkout**: Downloads the latest version of your repository code (including `agent.py`) onto the runner. Uses the official GitHub `checkout` action v4.

---

```yaml
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
```
> **Step 2 — Python**: Installs Python 3.12 on the runner using the official `setup-python` action v5. Version 3.12 is specified for compatibility with the `google-genai` SDK type hints.

---

```yaml
      - name: Install Dependencies
        run: |
          pip install requests google-genai python-dotenv
```
> **Step 3 — Dependencies**: Installs the 3 required Python packages:
> - `requests` — for Supabase REST API and LeminAI WhatsApp API calls
> - `google-genai` — official Google Gemini AI Python SDK
> - `python-dotenv` — loads `.env` file for local dev (no effect in Actions since env vars are injected via secrets)

---

```yaml
      - name: Run Dental AI Agent
        env:
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
          LEMINA_API_KEY: ${{ secrets.LEMINA_API_KEY }}
          ALLOWED_NUMBERS: ${{ secrets.ALLOWED_NUMBERS }}
          EVENT_PAYLOAD: ${{ toJson(github.event.client_payload) }}
        run: |
          python agent.py
```
> **Step 4 — Run Agent**: The main step. Four important things:
>
> - `GEMINI_API_KEY` — injected from GitHub Secrets (never visible in logs)
> - `LEMINA_API_KEY` — injected from GitHub Secrets
> - `ALLOWED_NUMBERS` — comma-separated whitelist of allowed phone numbers
> - `EVENT_PAYLOAD` — **this is the WhatsApp message data**, passed from `github.event.client_payload` (what LeminAI sent in the webhook body). `toJson()` converts it to a JSON string that `agent.py` reads with `os.getenv("EVENT_PAYLOAD")`.

> ⚠️ Note: `SUPABASE_URL` and `SUPABASE_KEY` must also be added as GitHub Secrets if you want Supabase to work in GitHub Actions (add them to the `env:` block or the workflow file).

---

## 🔑 Environment Variables Reference

Add these to your `.env` file for local dev, and as **GitHub Secrets** for production:

```env
# Google Gemini AI
GEMINI_API_KEY=AIzaSy...

# LeminAI WhatsApp Gateway
LEMINA_API_KEY=lmn_sk_...

# Supabase Database
SUPABASE_URL=https://xxxxxyyyyy.supabase.co
SUPABASE_KEY=sb_secret_...

# Security: only these phone numbers are processed (comma-separated)
# Add both local and international formats
ALLOWED_NUMBERS=03369013306,923369013306
```

> 🔒 The `.env` file is listed in `.gitignore` and will **never** be committed to the repository.

---

## 🧠 How the Agent Logic Works

### Smart Partial Booking Memory

Every patient's conversation state is stored in `chat_history/{phone}.json`:

```json
{
  "messages": [
    {"role": "user",  "content": "I want to book tomorrow at 10am"},
    {"role": "model", "content": "Got it! Could you share your name and issue?"}
  ],
  "draft": {
    "patient_name":     null,
    "appointment_date": "2026-10-23",
    "appointment_time": "10:00:00",
    "dental_issue":     null
  }
}
```

On the next message, the agent:
1. Loads the existing draft (date + time already known)
2. Builds a prompt that says `STILL MISSING: patient_name, dental_issue`
3. Only asks for the missing pieces

### The [UPDATE] Tag System

The AI always ends its reply with a structured tag:

```
[UPDATE: {"patient_name":"Ahmed","appointment_date":null,"appointment_time":null,"dental_issue":"toothache"}]
```

The Python code extracts this, merges non-null values into the draft, then removes the tag before sending the reply to the patient.

### Availability Check Logic

Before confirming any booking:

```python
# Query Supabase for conflicts
SELECT id FROM dental_appointments
WHERE appointment_date = '2026-10-28'
  AND appointment_time = '09:00:00'
  AND status != 'cancelled'
```

- **0 rows** → slot is free → proceed with booking
- **1+ rows** → slot is taken → tell patient, clear date/time, ask them to pick again

---

## 🧪 Testing

### Test with a real WhatsApp message payload

```bash
# Simulate the exact format LeminAI sends
$env:EVENT_PAYLOAD = '{
  "from": "923369013306",
  "text": {"body": "Book me Wednesday at 9am, name Ahmed, toothache"}
}'
python agent.py
```

### Expected output
```
Raw payload keys: ['from', 'text']
sender_phone=923369013306, message_body='Book me Wednesday at 9am...'
Authorised trigger from 923369013306: Book me Wednesday...
State: draft={all None}, turns=0
AI reply: ...
  Draft << patient_name = Ahmed
  Draft << appointment_date = 2026-10-30
  Draft << appointment_time = 09:00:00
  Draft << dental_issue = toothache
All fields ready: {...}
Availability check >> 200: []
Insert >> 201: [{"id": "abc-123", ...}]
>>> Booking saved to Supabase. ID=abc-123
WhatsApp >> 200: {"data": {"message_id": ...}}
```

### Verify in Supabase

Go to your Supabase dashboard → **Table Editor** → `dental_appointments` — the row should appear instantly.

---

## 🛠️ Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| `403 Forbidden` from GitHub | Bad PAT token in LeminAI | Regenerate PAT with `Actions: Read & Write` permission |
| `ValidationError: 26 errors` | Old `google-genai` version | Run `pip install --upgrade google-genai` |
| `503 UNAVAILABLE` from Gemini | Model overloaded | Agent retries 3x automatically; try again if persistent |
| `429 RESOURCE_EXHAUSTED` | Free tier daily quota hit | Add billing to Google Cloud project |
| Message body is `None` | Wrong payload format | Check LeminAI webhook body template matches expected format |
| Booking not in Supabase | `SUPABASE_URL`/`SUPABASE_KEY` not in GitHub Secrets | Add both as repository secrets |
| Agent processes unknown numbers | `ALLOWED_NUMBERS` misconfigured | Add both `03xx` and `923xx` formats |
| `chat_history/` keeps growing | Normal operation | Files auto-delete after successful booking |

---

## 📊 Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Language | Python 3.12 | Agent logic |
| AI Model | Gemini 3.1 Flash Lite | Natural language understanding |
| Database | Supabase (PostgreSQL) | Appointment storage + availability check |
| WhatsApp | LeminAI | Message gateway + webhook |
| CI/CD | GitHub Actions | Serverless execution |
| State | JSON files (per phone) | Multi-turn conversation memory |

---

## 📄 License

MIT License — free to use, modify, and distribute.

---

<div align="center">

**Made with ❤️ for dental clinics that want smart automation without the server bill.**

[![GitHub Stars](https://img.shields.io/github/stars/Developer359/Dental-AI-Agent?style=social)](https://github.com/Developer359/Dental-AI-Agent)

</div>
