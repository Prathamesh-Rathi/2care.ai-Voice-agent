# ============================================================
# backend/routes/websocket.py  —  Real-time voice pipeline
# ============================================================

import sys
import os
import json
import time
import uuid
import base64
import asyncio
import traceback

sys.path.append(
    os.path.dirname(
        os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))
        )
    )
)

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from config import (
    LATENCY_TARGET_MS,
    DEFAULT_LANGUAGE
)

from services.latency_logger import (
    record_pipeline,
    Timer
)

router = APIRouter()

# ── Active session store (in-memory) ─────────────────────────
active_sessions: dict = {}

# ============================================================
# Module-level imports — fail loudly at startup, not per-request
# ============================================================

# STT
try:
    from services.speech_to_text.stt import (
        transcribe_audio,
        transcribe_multilingual
    )
    stt_available = True
    print("[WS] STT loaded OK")
except Exception as e:
    stt_available = False
    print(f"[WS] STT not available: {e}")

# Language detection
try:
    from services.language_detection.detector import (
        detect_language_with_context
    )
    lang_det_available = True
    print("[WS] Language detector loaded OK")
except Exception as e:
    lang_det_available = False
    print(f"[WS] Language detector not available: {e}")

# Agent — CRITICAL: import at module level so errors are visible
try:
    from agent.reasoning.groq_agent import run_agent
    agent_available = True
    print("[WS] Agent loaded OK")
except Exception as e:
    agent_available = False
    # Print full traceback so the real error is never hidden
    print(f"[WS] *** AGENT FAILED TO LOAD ***")
    traceback.print_exc()

# TTS
try:
    from services.text_to_speech.tts import synthesize_speech
    tts_available = True
    print("[WS] TTS loaded OK")
except Exception as e:
    tts_available = False
    print(f"[WS] TTS not available: {e}")


# ============================================================
# Session Helpers
# ============================================================

def create_session(
    session_id: str,
    patient_id: int = 1,
    language: str = DEFAULT_LANGUAGE
):
    active_sessions[session_id] = {
        "patient_id": patient_id,
        "language": language,
        "context": {},
        "history": [],
        "created_at": time.time()
    }
    return active_sessions[session_id]


def get_session(session_id: str):
    return active_sessions.get(session_id)


def update_session_language(session_id: str, language: str):
    if session_id in active_sessions:
        active_sessions[session_id]["language"] = language


def append_to_history(session_id: str, role: str, message: str):
    if session_id in active_sessions:
        active_sessions[session_id]["history"].append({
            "role": role,
            "content": message
        })


# ============================================================
# WebSocket Endpoint
# ============================================================

@router.websocket("/ws/voice/{patient_phone}")
async def voice_websocket(
    websocket: WebSocket,
    patient_phone: str
):
    await websocket.accept()

    session_id = str(uuid.uuid4())

    # Get/Create Patient
    from backend.controllers.appointment_controller import (
        get_or_create_patient
    )

    patient = get_or_create_patient(patient_phone)

    session = create_session(
        session_id,
        patient_id=patient["id"],
        language=patient.get("language", DEFAULT_LANGUAGE)
    )

    print(
        f"[WS] New session {session_id[:8]}… | "
        f"patient={patient['name']} | phone={patient_phone}"
    )

    # Tell the client if the agent isn't loaded
    if not agent_available:
        await websocket.send_json({
            "type": "warning",
            "message": (
                "AI Agent failed to load — check server logs. "
                "Text input will echo only."
            )
        })

    await websocket.send_json({
        "type": "connected",
        "session_id": session_id,
        "patient": patient["name"],
        "message": "Connected to Voice AI Agent. How can I help you today?"
    })

    # ============================================================
    # Main Loop
    # ============================================================

    try:
        while True:

            raw = await websocket.receive_text()
            pipeline_start = time.time()

            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid JSON."
                })
                continue

            msg_type = msg.get("type", "text")

            # ── Stage 1: Input Processing ─────────────────────

            t0 = time.time()
            user_text = ""
            stt_ms = 0
            detected_lang = None

            # TEXT INPUT
            if msg_type == "text":
                user_text = msg.get("text", "").strip()
                stt_ms = 0
                print(f"[WS][TEXT] {user_text}")

            # AUDIO INPUT
            elif msg_type == "audio":
                if not stt_available:
                    await websocket.send_json({
                        "type": "error",
                        "message": "STT not available. Send type=text."
                    })
                    continue

                try:
                    audio_bytes = base64.b64decode(msg["data"])
                    stt_result = await asyncio.to_thread(
                        transcribe_multilingual, audio_bytes
                    )
                    user_text = stt_result["text"]
                    detected_lang = stt_result.get("language", DEFAULT_LANGUAGE)
                    update_session_language(session_id, detected_lang)
                    stt_ms = int((time.time() - t0) * 1000)
                    print(
                        f"[WS][STT] '{user_text}' | "
                        f"lang={detected_lang} | {stt_ms}ms"
                    )
                except Exception as e:
                    await websocket.send_json({
                        "type": "error",
                        "message": f"STT failed: {e}"
                    })
                    continue

            else:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Unknown type: {msg_type}"
                })
                continue

            if not user_text:
                continue

            # ── Stage 2: Language Detection ───────────────────

            t1 = time.time()

            if not detected_lang:
                if lang_det_available:
                    detected_lang = detect_language_with_context(
                        user_text,
                        session_language=session["language"]
                    )
                else:
                    detected_lang = session["language"]

            lang_ms = int((time.time() - t1) * 1000)
            update_session_language(session_id, detected_lang)
            print(f"[WS][LANG] detected={detected_lang} ({lang_ms}ms)")

            # ── Stage 3: AI Agent ─────────────────────────────

            t2 = time.time()

            if agent_available:
                append_to_history(session_id, "user", user_text)

                try:
                    agent_result = await asyncio.to_thread(
                        run_agent,
                        user_text,
                        session["history"],
                        detected_lang,
                        patient["id"]
                    )
                except Exception as agent_err:
                    # Surface the real error — don't silently fall back
                    print(f"[WS][AGENT] *** RUNTIME ERROR ***")
                    traceback.print_exc()
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Agent error: {agent_err}"
                    })
                    continue

            else:
                agent_result = {
                    "patient_response": (
                        "Agent not ready — check server logs for the "
                        "import error. Your message was: " + user_text
                    ),
                    "intent": "error",
                    "appointment": None
                }

            agent_ms = int((time.time() - t2) * 1000)
            print(
                f"[WS][AGENT] intent={agent_result.get('intent')} "
                f"({agent_ms}ms)"
            )

            response_text = agent_result.get(
                "patient_response", "I didn't understand that."
            )
            append_to_history(session_id, "assistant", response_text)

            # ── Stage 4: TTS ──────────────────────────────────

            t3 = time.time()
            audio_b64 = None
            tts_ms = 0

            if tts_available and response_text:
                try:
                    audio_bytes = await asyncio.to_thread(
                        synthesize_speech, response_text, detected_lang
                    )
                    audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
                    tts_ms = int((time.time() - t3) * 1000)
                except Exception as e:
                    print(f"[WS][TTS] Failed: {e}")

            # ── Latency ───────────────────────────────────────

            latency_record = record_pipeline(
                session_id=session_id,
                patient_id=patient["id"],
                language=detected_lang,
                stt_ms=stt_ms,
                lang_ms=lang_ms,
                agent_ms=agent_ms,
                tts_ms=tts_ms,
                intent=agent_result.get("intent", "unknown"),
                cache_hit=(tts_ms < 20),
            )

            total_ms = latency_record["total_ms"]
            latency_ok = latency_record["within_target"]

            latency_breakdown = {
                "stt_ms": stt_ms,
                "lang_ms": lang_ms,
                "agent_ms": agent_ms,
                "tts_ms": tts_ms,
                "total_ms": total_ms,
                "target_ms": LATENCY_TARGET_MS,
                "within_target": latency_ok,
            }

            print(
                f"[WS][LATENCY] STT={stt_ms}ms LANG={lang_ms}ms "
                f"AGENT={agent_ms}ms TTS={tts_ms}ms TOTAL={total_ms}ms "
                f"{'✓' if latency_ok else '⚠ OVER TARGET'}"
            )

            # ── Send Response ─────────────────────────────────

            await websocket.send_json({
                "type": "response",
                "text": response_text,
                "audio": audio_b64,
                "language": detected_lang,
                "intent": agent_result.get("intent"),
                "appointment": agent_result.get("appointment"),
                "latency": latency_breakdown
            })

    except WebSocketDisconnect:
        print(f"[WS] Session {session_id[:8]}… disconnected.")
        active_sessions.pop(session_id, None)

    except Exception as e:
        print(f"[WS] Unexpected error: {e}")
        traceback.print_exc()
        try:
            await websocket.send_json({
                "type": "error",
                "message": str(e)
            })
        except Exception:
            pass