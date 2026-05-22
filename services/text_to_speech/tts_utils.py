# ============================================================
# services/text_to_speech/tts_utils.py
# Audio helpers, caching, and language mapping for TTS
# ============================================================

import os
import sys
import hashlib
import time

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
from config import TTS_OUTPUT_DIR


# ── gTTS language codes ───────────────────────────────────────
# gTTS uses slightly different codes from our internal ones
GTTS_LANG_MAP = {
    "en": "en",
    "hi": "hi",
    "ta": "ta",
}

# ── TTS speed settings ────────────────────────────────────────
# slow=True makes gTTS speak slower — better for medical info
GTTS_SLOW_LANGS = []   # add "en" here if you want slower English


# ── Text cleanup before TTS ───────────────────────────────────
def clean_text_for_tts(text: str) -> str:
    """
    Cleans text before sending to TTS engine.
    Removes markdown, extra whitespace, special chars
    that cause robotic pronunciation.
    """
    import re

    # Remove markdown formatting
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)   # bold
    text = re.sub(r"\*(.+?)\*",     r"\1", text)   # italic
    text = re.sub(r"`(.+?)`",       r"\1", text)   # code

    # Remove URLs
    text = re.sub(r"https?://\S+", "", text)

    # Remove JSON-like fragments that leaked into response
    text = re.sub(r"\{.*?\}", "", text, flags=re.DOTALL)

    # Replace common medical abbreviations
    replacements = {
        "Dr.":  "Doctor",
        "AM":   "A M",
        "PM":   "P M",
        "ID":   "I D",
        "No.":  "Number",
    }
    for abbr, full in replacements.items():
        text = text.replace(abbr, full)

    # Collapse multiple spaces / newlines
    text = re.sub(r"\s+", " ", text).strip()

    # Limit length — TTS gets slow on very long strings
    if len(text) > 500:
        text = text[:500] + "."

    return text


# ── Cache helpers ─────────────────────────────────────────────
def get_cache_path(text: str, lang: str) -> str:
    """
    Returns a deterministic file path for a text+lang combo.
    Same text in same language always returns same path.
    Avoids re-synthesizing identical responses.
    """
    os.makedirs(TTS_OUTPUT_DIR, exist_ok=True)
    key      = f"{lang}:{text}"
    hash_str = hashlib.md5(key.encode("utf-8")).hexdigest()[:12]
    return os.path.join(TTS_OUTPUT_DIR, f"tts_{hash_str}.mp3")


def is_cached(text: str, lang: str) -> bool:
    """Returns True if this text+lang combo is already synthesized."""
    path = get_cache_path(text, lang)
    return os.path.exists(path) and os.path.getsize(path) > 0


def read_cache(text: str, lang: str) -> bytes | None:
    """Reads cached audio bytes. Returns None if not cached."""
    path = get_cache_path(text, lang)
    if os.path.exists(path) and os.path.getsize(path) > 0:
        with open(path, "rb") as f:
            return f.read()
    return None


def write_cache(text: str, lang: str, audio_bytes: bytes) -> str:
    """Writes audio bytes to cache. Returns file path."""
    path = get_cache_path(text, lang)
    with open(path, "wb") as f:
        f.write(audio_bytes)
    return path


def clear_tts_cache():
    """Deletes all cached TTS files."""
    if not os.path.exists(TTS_OUTPUT_DIR):
        return 0
    count = 0
    for fname in os.listdir(TTS_OUTPUT_DIR):
        if fname.startswith("tts_") and fname.endswith(".mp3"):
            os.remove(os.path.join(TTS_OUTPUT_DIR, fname))
            count += 1
    print(f"[TTS] Cache cleared: {count} files removed.")
    return count


def get_cache_stats() -> dict:
    """Returns stats about the TTS cache."""
    if not os.path.exists(TTS_OUTPUT_DIR):
        return {"files": 0, "total_kb": 0}
    files = [
        f for f in os.listdir(TTS_OUTPUT_DIR)
        if f.startswith("tts_") and f.endswith(".mp3")
    ]
    total_bytes = sum(
        os.path.getsize(os.path.join(TTS_OUTPUT_DIR, f))
        for f in files
    )
    return {
        "files":    len(files),
        "total_kb": round(total_bytes / 1024, 2),
        "dir":      TTS_OUTPUT_DIR,
    }


# ── Audio conversion helpers ──────────────────────────────────
def mp3_to_wav_bytes(mp3_bytes: bytes) -> bytes:
    """
    Converts MP3 bytes to WAV bytes using pydub.
    Useful if the client needs WAV instead of MP3.
    """
    try:
        import io
        from pydub import AudioSegment
        mp3_buf = io.BytesIO(mp3_bytes)
        segment = AudioSegment.from_file(mp3_buf, format="mp3")
        wav_buf = io.BytesIO()
        segment.export(wav_buf, format="wav")
        return wav_buf.getvalue()
    except Exception as e:
        print(f"[TTS] mp3→wav conversion failed: {e}")
        return mp3_bytes


def adjust_speed(mp3_bytes: bytes, speed: float = 1.0) -> bytes:
    """
    Adjusts playback speed of MP3 audio.
    speed=1.0 = normal, 1.2 = 20% faster, 0.8 = 20% slower
    Returns original bytes if pydub fails.
    """
    if speed == 1.0:
        return mp3_bytes
    try:
        import io
        from pydub import AudioSegment
        buf     = io.BytesIO(mp3_bytes)
        segment = AudioSegment.from_file(buf, format="mp3")
        # Change frame rate to adjust speed without pitch shift
        altered   = segment._spawn(
            segment.raw_data,
            overrides={"frame_rate": int(segment.frame_rate * speed)}
        ).set_frame_rate(segment.frame_rate)
        out_buf = io.BytesIO()
        altered.export(out_buf, format="mp3")
        return out_buf.getvalue()
    except Exception as e:
        print(f"[TTS] Speed adjustment failed: {e}")
        return mp3_bytes