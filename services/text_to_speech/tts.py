# ============================================================
# services/text_to_speech/tts.py
# Core TTS engine — gTTS primary, fallback chain included
# ============================================================

import os
import sys
import io
import time

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from config import TTS_OUTPUT_DIR
from services.text_to_speech.tts_utils import (
    GTTS_LANG_MAP,
    GTTS_SLOW_LANGS,
    clean_text_for_tts,
    get_cache_path,
    is_cached,
    read_cache,
    write_cache,
)

os.makedirs(TTS_OUTPUT_DIR, exist_ok=True)


# ── Engine 1: gTTS (Google TTS — free, multilingual) ─────────
def _synthesize_gtts(text: str, lang: str) -> bytes | None:
    """
    Synthesizes speech using gTTS (Google Text-to-Speech).
    Supports English, Hindi, Tamil natively.
    Returns MP3 bytes or None on failure.
    """
    try:
        from gtts import gTTS

        gtts_lang = GTTS_LANG_MAP.get(lang, "en")
        slow      = lang in GTTS_SLOW_LANGS

        tts = gTTS(text=text, lang=gtts_lang, slow=slow)

        buf = io.BytesIO()
        tts.write_to_fp(buf)
        buf.seek(0)
        audio_bytes = buf.read()

        if len(audio_bytes) < 100:
            print(f"[TTS][gTTS] Suspiciously small output: {len(audio_bytes)} bytes")
            return None

        return audio_bytes

    except Exception as e:
        print(f"[TTS][gTTS] Failed: {e}")
        return None


# ── Engine 2: pyttsx3 (offline fallback — English only) ──────
def _synthesize_pyttsx3(text: str) -> bytes | None:
    """
    Offline TTS using pyttsx3.
    Only used when gTTS is unavailable (no internet).
    English only — limited quality.
    Returns WAV bytes or None.
    """
    try:
        import pyttsx3
        import tempfile

        engine = pyttsx3.init()
        engine.setProperty("rate",   160)   # words per minute
        engine.setProperty("volume", 1.0)

        # Save to temp file then read bytes
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name

        engine.save_to_file(text, tmp_path)
        engine.runAndWait()

        with open(tmp_path, "rb") as f:
            audio_bytes = f.read()

        os.unlink(tmp_path)
        return audio_bytes if len(audio_bytes) > 100 else None

    except Exception as e:
        print(f"[TTS][pyttsx3] Failed: {e}")
        return None


# ── Engine 3: Silent WAV (last resort) ───────────────────────
def _synthesize_silent(duration_ms: int = 1000) -> bytes:
    """
    Returns a silent WAV file as absolute last resort.
    The text response will still be sent to the client —
    this just means no audio plays.
    """
    import struct
    import wave

    sample_rate = 16000
    num_samples = int(sample_rate * duration_ms / 1000)
    pcm_data    = struct.pack("<" + "h" * num_samples, *([0] * num_samples))

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_data)

    return buf.getvalue()


# ── Main synthesize function ──────────────────────────────────
def synthesize_speech(text: str,
                      language: str = "en",
                      use_cache: bool = True,
                      speed: float = 1.0) -> bytes:
    """
    Converts text to speech audio bytes.
    Tries engines in order: gTTS → pyttsx3 → silent WAV.

    Args:
        text:      Text to speak.
        language:  Language code — 'en', 'hi', 'ta'.
        use_cache: Return cached audio if same text was
                   synthesized before (speeds up repeated responses).
        speed:     Playback speed multiplier (1.0 = normal).

    Returns:
        Audio bytes (MP3 or WAV). Never raises — falls back to silent.
    """
    t_start = time.time()

    if not text or not text.strip():
        return _synthesize_silent(500)

    # Clean text before synthesis
    clean = clean_text_for_tts(text)
    if not clean:
        return _synthesize_silent(500)

    print(f"[TTS] Synthesizing ({language}): '{clean[:60]}...' " \
          if len(clean) > 60 else f"[TTS] Synthesizing ({language}): '{clean}'")

    # ── Check cache ───────────────────────────────────────────
    if use_cache and is_cached(clean, language):
        cached = read_cache(clean, language)
        if cached:
            elapsed = int((time.time() - t_start) * 1000)
            print(f"[TTS] Cache hit ({elapsed}ms) | {len(cached)} bytes")
            return cached

    # ── Engine 1: gTTS ────────────────────────────────────────
    audio_bytes = _synthesize_gtts(clean, language)

    # ── Engine 2: pyttsx3 fallback ────────────────────────────
    if not audio_bytes:
        print("[TTS] gTTS failed — trying pyttsx3 fallback...")
        audio_bytes = _synthesize_pyttsx3(clean)

    # ── Engine 3: Silent WAV ──────────────────────────────────
    if not audio_bytes:
        print("[TTS] All engines failed — returning silent audio.")
        return _synthesize_silent(1500)

    # ── Speed adjustment ──────────────────────────────────────
    if speed != 1.0:
        from services.text_to_speech.tts_utils import adjust_speed
        audio_bytes = adjust_speed(audio_bytes, speed)

    # ── Write to cache ────────────────────────────────────────
    if use_cache:
        write_cache(clean, language, audio_bytes)

    elapsed = int((time.time() - t_start) * 1000)
    print(f"[TTS] Done: {elapsed}ms | {len(audio_bytes)} bytes | lang={language}")

    return audio_bytes


# ── Batch synthesis ───────────────────────────────────────────
def synthesize_batch(items: list[dict]) -> list[dict]:
    """
    Synthesizes multiple texts at once.
    Each item: {"text": str, "language": str}
    Returns list with "audio_bytes" added to each item.
    Used for outbound campaign pre-generation (Phase 11).
    """
    results = []
    for item in items:
        text     = item.get("text", "")
        language = item.get("language", "en")
        audio    = synthesize_speech(text, language)
        results.append({**item, "audio_bytes": audio})
    return results


# ── Save audio to file ────────────────────────────────────────
def save_audio_file(audio_bytes: bytes,
                    filename: str = None,
                    folder: str = None) -> str:
    """
    Saves audio bytes to a file.
    Returns the full file path.
    """
    folder = folder or TTS_OUTPUT_DIR
    os.makedirs(folder, exist_ok=True)

    if not filename:
        filename = f"response_{int(time.time())}.mp3"

    path = os.path.join(folder, filename)
    with open(path, "wb") as f:
        f.write(audio_bytes)

    print(f"[TTS] Saved: {path}")
    return path


# ── Quick speak test (plays audio if possible) ────────────────
def speak_text(text: str, language: str = "en"):
    """
    Synthesizes and immediately plays audio (for local testing).
    Requires 'playsound' or falls back to saving a file.
    """
    audio_bytes = synthesize_speech(text, language)
    path        = save_audio_file(audio_bytes, folder="tts_output")

    try:
        import subprocess
        # Windows
        if sys.platform == "win32":
            os.startfile(path)
        # Mac
        elif sys.platform == "darwin":
            subprocess.call(["afplay", path])
        # Linux
        else:
            subprocess.call(["mpg123", path])
        print(f"[TTS] Playing: {path}")
    except Exception:
        print(f"[TTS] Auto-play failed. File saved at: {path}")
        print(f"[TTS] Open manually to hear the audio.")