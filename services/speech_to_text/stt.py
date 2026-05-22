# ============================================================
# services/speech_to_text/stt.py
# Groq Whisper — Speech-to-Text
# ============================================================

import io
import os
import sys
import time

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from groq import Groq
from config import GROQ_API_KEY, GROQ_WHISPER_MODEL, SUPPORTED_LANGUAGES
from services.speech_to_text.audio_utils import (
    validate_audio,
    detect_audio_format,
    convert_to_wav_bytes,
    get_audio_info,
)


# ── Groq client (module-level singleton) ──────────────────────
_client: Groq = None

def get_groq_client() -> Groq:
    global _client
    if _client is None:
        _client = Groq(api_key=GROQ_API_KEY)
    return _client


# ── Language hint map ─────────────────────────────────────────
# Whisper accepts ISO-639-1 language codes as hints.
# Providing a hint improves accuracy and speed significantly.
WHISPER_LANG_HINTS = {
    "en": "en",
    "hi": "hi",
    "ta": "ta",
}


# ── Core transcription function ───────────────────────────────
def transcribe_audio(audio_bytes: bytes,
                     language_hint: str = None,
                     debug: bool = False) -> str:
    """
    Converts audio bytes → text using Groq Whisper API.

    Args:
        audio_bytes:   Raw audio bytes (WAV, MP3, WebM, etc.)
        language_hint: ISO code hint ('en', 'hi', 'ta').
                       Pass None for auto-detection.
        debug:         If True, prints audio info before calling API.

    Returns:
        Transcribed text string. Empty string on failure.
    """
    t_start = time.time()

    # ── Validate ──────────────────────────────────────────────
    is_valid, error_msg = validate_audio(audio_bytes)
    if not is_valid:
        print(f"[STT] Validation failed: {error_msg}")
        return ""

    # ── Debug info ────────────────────────────────────────────
    if debug:
        info = get_audio_info(audio_bytes)
        print(f"[STT] Audio info: {info}")

    # ── Format detection & optional conversion ────────────────
    fmt = detect_audio_format(audio_bytes)
    print(f"[STT] Detected format: {fmt} | size: {len(audio_bytes)} bytes")

    # Groq Whisper works best with WAV — convert if needed
    if fmt not in ("wav", "mp3", "flac"):
        print(f"[STT] Converting {fmt} → WAV...")
        audio_bytes = convert_to_wav_bytes(audio_bytes)
        fmt = "wav"

    # ── Build file-like object for Groq SDK ──────────────────
    # Groq SDK expects a tuple: (filename, file_object, mime_type)
    audio_file = io.BytesIO(audio_bytes)
    mime_type  = f"audio/{fmt}"
    filename   = f"audio.{fmt}"

    # ── Call Groq Whisper API ─────────────────────────────────
    try:
        client = get_groq_client()

        # Build kwargs — only add language if hint provided
        kwargs = {
            "file":             (filename, audio_file, mime_type),
            "model":            GROQ_WHISPER_MODEL,
            "response_format":  "verbose_json",   # includes word timestamps
            "temperature":      0.0,              # deterministic output
        }

        if language_hint and language_hint in WHISPER_LANG_HINTS:
            kwargs["language"] = WHISPER_LANG_HINTS[language_hint]
            print(f"[STT] Language hint: {language_hint}")

        transcription = client.audio.transcriptions.create(**kwargs)

        text = transcription.text.strip()

        elapsed_ms = int((time.time() - t_start) * 1000)
        print(f"[STT] Result: '{text}' ({elapsed_ms}ms)")

        return text

    except Exception as e:
        elapsed_ms = int((time.time() - t_start) * 1000)
        print(f"[STT] Error after {elapsed_ms}ms: {e}")
        return ""


# ── Multilingual transcription ────────────────────────────────
def transcribe_multilingual(audio_bytes: bytes) -> dict:
    """
    Transcribes without a language hint, letting Whisper
    auto-detect the language.

    Returns:
        {
          "text":     "transcribed text",
          "language": "en" | "hi" | "ta" | ...,
          "duration": 1.23
        }
    """
    t_start = time.time()

    is_valid, error_msg = validate_audio(audio_bytes)
    if not is_valid:
        return {"text": "", "language": "en", "duration": 0}

    fmt        = detect_audio_format(audio_bytes)
    audio_file = io.BytesIO(audio_bytes)

    try:
        client = get_groq_client()

        transcription = client.audio.transcriptions.create(
            file            = (f"audio.{fmt}", audio_file, f"audio/{fmt}"),
            model           = GROQ_WHISPER_MODEL,
            response_format = "verbose_json",
            temperature     = 0.0,
        )

        elapsed_ms = int((time.time() - t_start) * 1000)

        # verbose_json returns detected language
        detected = getattr(transcription, "language", "en")

        # Normalise to our 2-letter codes
        lang_map = {"english": "en", "hindi": "hi", "tamil": "ta"}
        detected = lang_map.get(detected.lower(), detected[:2].lower())

        result = {
            "text":        transcription.text.strip(),
            "language":    detected,
            "duration_ms": elapsed_ms,
        }
        print(f"[STT][ML] '{result['text']}' lang={detected} ({elapsed_ms}ms)")
        return result

    except Exception as e:
        print(f"[STT][ML] Error: {e}")
        return {"text": "", "language": "en", "duration_ms": 0}


# ── Streaming-friendly chunked transcription ──────────────────
def transcribe_chunk(chunk_bytes: bytes,
                     previous_text: str = "",
                     language_hint: str = None) -> str:
    """
    For streaming audio — transcribes a chunk and uses
    previous_text as a prompt to improve continuity.

    Args:
        chunk_bytes:   Audio chunk bytes
        previous_text: Last transcribed text (used as prompt)
        language_hint: Language code hint

    Returns:
        Transcribed text for this chunk.
    """
    is_valid, _ = validate_audio(chunk_bytes)
    if not is_valid:
        return ""

    fmt        = detect_audio_format(chunk_bytes)
    audio_file = io.BytesIO(chunk_bytes)

    try:
        client = get_groq_client()

        kwargs = {
            "file":            (f"chunk.{fmt}", audio_file, f"audio/{fmt}"),
            "model":           GROQ_WHISPER_MODEL,
            "response_format": "text",
            "temperature":     0.0,
        }

        # Prompt helps Whisper continue naturally from previous chunk
        if previous_text:
            kwargs["prompt"] = previous_text[-200:]   # last 200 chars

        if language_hint and language_hint in WHISPER_LANG_HINTS:
            kwargs["language"] = WHISPER_LANG_HINTS[language_hint]

        result = client.audio.transcriptions.create(**kwargs)
        return result.strip() if isinstance(result, str) else result.text.strip()

    except Exception as e:
        print(f"[STT][CHUNK] Error: {e}")
        return ""