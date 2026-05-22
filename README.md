# 🏥 Voice AI Agent — Clinical Appointment System

A real-time multilingual voice-based appointment booking system for healthcare clinics. Patients can book, cancel, and reschedule appointments by speaking in **English, Hindi, or Tamil** — entirely through a browser UI with no app install required.

---

## ✨ Features

- 🎤 **Voice input** — speak in any supported language; Whisper transcribes automatically
- 🤖 **AI agent** — LLaMA 3 via Groq understands intent and manages the full booking flow
- 🌐 **Multilingual** — English, Hindi (हिंदी), Tamil (தமிழ்) with auto-detection
- 📅 **Full appointment lifecycle** — book, cancel, reschedule, check availability
- 🔊 **Text-to-speech responses** — Aanya (the AI) speaks back in the patient's language
- 💾 **Persistent memory** — remembers preferred doctor, language, and visit history per patient
- ⚡ **Latency dashboard** — real-time breakdown of STT / language detection / agent / TTS times
- 🖥️ **Zero-install UI** — single `index.html`, open directly in Chrome

---

## 🗂️ Project Structure

```
voice-ai-agent/
│
├── main.py                        # FastAPI app entry point
├── config.py                      # All env vars and constants
├── requirements.txt
│
├── frontend/
│   └── index.html                 # Browser UI (no npm needed)
│
├── agent/
│   ├── reasoning/
│   │   └── groq_agent.py          # Core LLM agent — intent + tool orchestration
│   ├── prompt/
│   │   └── system_prompt.py       # Multilingual prompts with few-shot examples
│   └── tools/
│       └── tool_definitions.py    # Tool registry + execution dispatcher
│
├── services/
│   ├── groq_client.py             # Groq API client singleton
│   ├── speech_to_text/
│   │   └── stt.py                 # Whisper-based multilingual transcription
│   ├── text_to_speech/
│   │   └── tts.py                 # TTS synthesis (gTTS / ElevenLabs)
│   ├── language_detection/
│   │   └── detector.py            # Language detection with session context
│   └── latency_logger.py          # Pipeline timing + logging
│
├── memory/
│   ├── session_memory/
│   │   └── session_store.py       # In-memory conversation state (30 min TTL)
│   └── persistent_memory/
│       └── patient_memory.py      # JSON-based long-term memory per patient
│
├── backend/
│   ├── routes/
│   │   └── websocket.py           # WebSocket endpoint — real-time voice pipeline
│   └── controllers/
│       └── appointment_controller.py
│
└── database/                      # DB models + seed data
```

---

## 🚀 Quick Start

### 1. Clone and install

```bash
git clone https://github.com/your-org/voice-ai-agent.git
cd voice-ai-agent
pip install -r requirements.txt
```

### 2. Set environment variables

Create a `.env` file in the project root:

```env
GROQ_API_KEY=gsk_your_groq_api_key_here
DEFAULT_LANGUAGE=en
LATENCY_TARGET_MS=2000
PERSISTENT_MEMORY_DIR=./memory/persistent_memory/data
```

Get your Groq API key free at [console.groq.com](https://console.groq.com).

### 3. Start the server

```bash
python main.py
```

Server runs at `http://localhost:8000`.

### 4. Open the UI

```bash
# Windows
start frontend/index.html

# Mac
open frontend/index.html

# Linux
xdg-open frontend/index.html
```

Or just double-click `frontend/index.html` in your file explorer.

---

## 🧪 Test Patients (from seed data)

| Phone | Patient | Default Language |
|---|---|---|
| `9876543210` | Rahul Verma | Hindi |
| `9123456789` | Ananya Singh | English |
| `9988776655` | Murugan Raj | Tamil |

Enter any of these phone numbers in the UI and click **Connect**.

---

## 💬 Example Conversations

**English**
```
User:  Book an appointment with a cardiologist tomorrow
Aanya: What time works best for you?
User:  10 AM
Aanya: Your appointment with Dr. Arjun Sharma is confirmed for tomorrow at 10:00 AM at Apollo Hospital.
```

**Hindi**
```
User:  मुझे कल हृदय रोग विशेषज्ञ से मिलना है
Aanya: आपके लिए कौन सा समय सबसे अच्छा रहेगा?
User:  सुबह दस बजे
Aanya: आपकी अपॉइंटमेंट कल सुबह 10:00 बजे डॉ. अर्जुन शर्मा के साथ बुक हो गई है।
```

**Tamil**
```
User:  நாளை மருத்துவரை பார்க்க வேண்டும்
Aanya: நீங்கள் எந்த வகை மருத்துவரை சந்திக்க விரும்புகிறீர்கள்?
User:  இதய நிபுணர்
Aanya: நாளை டாக்டர் அர்ஜுன் சர்மாவுடன் சந்திப்பு உறுதிப்படுத்தப்பட்டது.
```

---

## ⚙️ Configuration (`config.py`)

| Variable | Description | Default |
|---|---|---|
| `GROQ_API_KEY` | Groq API key | required |
| `GROQ_LLM_MODEL` | LLaMA model name | `llama3-8b-8192` |
| `DEFAULT_LANGUAGE` | Fallback language | `en` |
| `LATENCY_TARGET_MS` | Target total pipeline latency | `2000` |
| `PERSISTENT_MEMORY_DIR` | Path for patient JSON memory files | `./memory/persistent_memory/data` |

### Supported Groq models

JSON mode (recommended) works on:
- `llama3-8b-8192` ← default, fastest
- `llama3-70b-8192` ← most accurate
- `llama-3.1-8b-instant`
- `llama-3.3-70b-versatile`
- `mixtral-8x7b-32768`

---

## 🏗️ Architecture

```
Browser (index.html)
       │  WebSocket (JSON + base64 audio)
       ▼
FastAPI WebSocket Handler (websocket.py)
       │
       ├─► STT (Whisper) ──────────────── audio → text + language
       │
       ├─► Language Detector ──────────── text → "en" | "hi" | "ta"
       │
       ├─► Groq Agent (groq_agent.py)
       │       │
       │       ├─ LLM call 1: intent + tool decision
       │       ├─ Tool execution (book / cancel / reschedule)
       │       └─ LLM call 2: natural language response
       │
       ├─► TTS ────────────────────────── text → audio (mp3)
       │
       └─► Response: { text, audio, appointment, latency }
```

### Pipeline latency targets

| Stage | Target |
|---|---|
| STT | < 300 ms |
| Language detection | < 10 ms |
| Agent (2× LLM calls) | < 1200 ms |
| TTS | < 500 ms |
| **Total** | **< 2000 ms** |

---

## 🧠 Memory System

### Session memory (`session_store.py`)
- In-memory Python dict, 30-minute TTL
- Stores conversation history, detected language, slot-filling context
- Automatically pruned on expiry

### Persistent memory (`patient_memory.py`)
- One JSON file per patient in `PERSISTENT_MEMORY_DIR`
- Remembers: preferred doctor, hospital, time slot, last specialty, total visits, language preference
- Used to personalise agent responses on repeat visits
- GDPR-friendly: `delete_patient_memory(patient_id)` removes the file entirely

---

## 🛠️ Available Tools

| Tool | Description |
|---|---|
| `book_appointment` | Books a slot with the requested specialty/date/time |
| `cancel_appointment` | Cancels by appointment ID |
| `reschedule_appointment` | Moves an existing booking to a new slot |
| `check_availability` | Lists open slots for a specialty on a date |

Tools are defined in `agent/tools/tool_definitions.py` and dispatched by `execute_tool()`.

---

## 🧪 Running Tests

```bash
# Memory system
python test_memory.py

# Agent reasoning (requires GROQ_API_KEY)
python test_agent.py

# Full pipeline smoke test
python test_pipeline.py
```

---

## 📦 Requirements

```
fastapi
uvicorn
groq
openai-whisper
gTTS
python-dotenv
```

Install all:
```bash
pip install -r requirements.txt
```

---

## 🔒 Security Notes

- API keys are read from environment variables — never commit `.env` to git
- Patient phone numbers are the only PII stored; memory files are local JSON
- WebSocket connections are per-session with UUID session IDs
- Add HTTPS + WSS in production (nginx reverse proxy recommended)

---

## 📋 Development Phases

| Phase | Description | Status |
|---|---|---|
| 1–3 | Database + appointment engine | ✅ |
| 4–5 | STT (Whisper) + language detection | ✅ |
| 6 | Groq LLM agent + tool calling | ✅ |
| 7 | TTS (gTTS) | ✅ |
| 8 | Session + persistent memory | ✅ |
| 9 | Browser UI | ✅ |
| 10 | Latency logging + TTS caching | 🔜 |

---
UI - 
<img width="1440" height="1082" alt="image" src="https://github.com/user-attachments/assets/fe88d77a-9808-4195-a9aa-5a1c1c895d7b" />


## 🤝 Contributing

1. Fork the repo
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Commit your changes: `git commit -m "Add my feature"`
4. Push and open a pull request

---


## 📄 License

MIT License — see [LICENSE](LICENSE) for details.
