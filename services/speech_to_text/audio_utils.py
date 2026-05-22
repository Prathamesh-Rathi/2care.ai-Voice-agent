# ============================================================
# services/speech_to_text/audio_utils.py
# Audio format helpers — validation, conversion, saving
# ============================================================

import io
import os
import time
import wave
import struct
import sys

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
from config import TTS_OUTPUT_DIR


# ── Supported formats Groq Whisper accepts ────────────────────
SUPPORTED_FORMATS = {
    "wav":  "audio/wav",
    "mp3":  "audio/mpeg",
    "mp4":  "audio/mp4",
    "webm": "audio/webm",
    "ogg":  "audio/ogg",
    "flac": "audio/flac",
    "m4a":  "audio/mp4",
}

# ── File signature bytes (magic bytes) ───────────────────────
MAGIC_BYTES = {
    b"RIFF":        "wav",
    b"\xff\xfb":    "mp3",
    b"\xff\xf3":    "mp3",
    b"\xff\xf2":    "mp3",
    b"ID3":         "mp3",
    b"\x1aE\xdf\xa3": "webm",
    b"OggS":        "ogg",
    b"fLaC":        "flac",
}


def detect_audio_format(audio_bytes: bytes) -> str:
    """
    Sniff the first few bytes to detect audio format.
    Returns format string like 'wav', 'mp3', etc.
    Defaults to 'wav' if unknown.
    """
    header = audio_bytes[:4]
    for magic, fmt in MAGIC_BYTES.items():
        if header.startswith(magic):
            return fmt
    return "wav"   # safe default


def validate_audio(audio_bytes: bytes) -> tuple[bool, str]:
    """
    Basic validation — checks audio is non-empty and
    at least 0.1 seconds of data.
    Returns (is_valid, error_message).
    """
    if not audio_bytes:
        return False, "Empty audio data received."

    if len(audio_bytes) < 1000:
        return False, f"Audio too short ({len(audio_bytes)} bytes). Minimum 1000 bytes."

    if len(audio_bytes) > 25 * 1024 * 1024:   # 25 MB Groq limit
        return False, "Audio exceeds 25 MB limit."

    return True, ""


def create_minimal_wav(audio_bytes: bytes,
                       sample_rate: int = 16000,
                       channels: int = 1,
                       sample_width: int = 2) -> bytes:
    """
    Wraps raw PCM bytes in a proper WAV header.
    Use this when you receive raw PCM from a browser
    and need to send it to Whisper as WAV.
    """
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(sample_rate)
        wf.writeframes(audio_bytes)
    return buf.getvalue()


def convert_to_wav_bytes(audio_bytes: bytes) -> bytes:
    """
    Attempts to convert any supported format to WAV bytes.
    Falls back to treating as raw WAV if pydub fails.
    """
    try:
        from pydub import AudioSegment
        fmt = detect_audio_format(audio_bytes)
        audio_buf = io.BytesIO(audio_bytes)
        segment   = AudioSegment.from_file(audio_buf, format=fmt)

        # Normalise to 16kHz mono — optimal for Whisper
        segment = segment.set_frame_rate(16000).set_channels(1)

        out_buf = io.BytesIO()
        segment.export(out_buf, format="wav")
        return out_buf.getvalue()

    except Exception as e:
        print(f"[AUDIO] pydub conversion failed ({e}), returning as-is.")
        return audio_bytes


def save_audio_debug(audio_bytes: bytes, prefix: str = "debug") -> str:
    """
    Saves audio bytes to disk for debugging.
    Returns the file path.
    """
    os.makedirs("debug_audio", exist_ok=True)
    fmt  = detect_audio_format(audio_bytes)
    path = f"debug_audio/{prefix}_{int(time.time())}.{fmt}"
    with open(path, "wb") as f:
        f.write(audio_bytes)
    print(f"[AUDIO] Saved debug audio → {path}")
    return path


def generate_test_wav(duration_seconds: float = 1.0,
                      sample_rate: int = 16000) -> bytes:
    """
    Generates a silent WAV file for unit testing.
    Useful when you have no microphone available.
    """
    num_samples = int(sample_rate * duration_seconds)
    pcm_data    = struct.pack("<" + "h" * num_samples, *([0] * num_samples))
    return create_minimal_wav(pcm_data, sample_rate=sample_rate)


def get_audio_info(audio_bytes: bytes) -> dict:
    """
    Returns basic info about the audio buffer.
    """
    fmt  = detect_audio_format(audio_bytes)
    info = {
        "format":     fmt,
        "size_bytes": len(audio_bytes),
        "size_kb":    round(len(audio_bytes) / 1024, 2),
    }

    # Extra info for WAV files
    if fmt == "wav":
        try:
            buf = io.BytesIO(audio_bytes)
            with wave.open(buf, "rb") as wf:
                info["channels"]    = wf.getnchannels()
                info["sample_rate"] = wf.getframerate()
                info["duration_s"]  = round(
                    wf.getnframes() / wf.getframerate(), 2
                )
        except Exception:
            pass

    return info