# ============================================================
# test_stt.py  —  Standalone STT test
# Run: python test_stt.py
# ============================================================

import sys, os, base64, json
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.speech_to_text.stt import (
    transcribe_audio,
    transcribe_multilingual,
)
from services.speech_to_text.audio_utils import (
    generate_test_wav,
    get_audio_info,
    detect_audio_format,
)


def print_section(title: str):
    print(f"\n{'='*55}")
    print(f"  {title}")
    print(f"{'='*55}")


# ── Test 1: Silent WAV (API connectivity check) ───────────────
def test_silent_wav():
    print_section("TEST 1 — Silent WAV (API connectivity)")
    wav_bytes = generate_test_wav(duration_seconds=1.0)
    info      = get_audio_info(wav_bytes)
    print(f"  Generated WAV: {info}")
    text = transcribe_audio(wav_bytes, debug=True)
    print(f"  Transcription: '{text}' (empty = correct for silence)")


# ── Test 2: Real audio file ───────────────────────────────────
def test_real_file(filepath: str):
    print_section(f"TEST 2 — Real audio file: {filepath}")
    if not os.path.exists(filepath):
        print(f"  File not found: {filepath}")
        print("  → Record a WAV file and pass its path to test.")
        return
    with open(filepath, "rb") as f:
        audio_bytes = f.read()
    info = get_audio_info(audio_bytes)
    print(f"  File info: {info}")
    text = transcribe_audio(audio_bytes, debug=True)
    print(f"  Transcription: '{text}'")


# ── Test 3: Multilingual detection ───────────────────────────
def test_multilingual(filepath: str = None):
    print_section("TEST 3 — Multilingual auto-detection")
    if filepath and os.path.exists(filepath):
        with open(filepath, "rb") as f:
            audio_bytes = f.read()
    else:
        print("  No file provided — using silent WAV.")
        audio_bytes = generate_test_wav(duration_seconds=1.0)

    result = transcribe_multilingual(audio_bytes)
    print(f"  Text:     '{result['text']}'")
    print(f"  Language: {result['language']}")
    print(f"  Time:     {result['duration_ms']}ms")


# ── Test 4: Base64 round-trip (simulates WebSocket flow) ──────
def test_base64_roundtrip():
    print_section("TEST 4 — Base64 round-trip (WebSocket simulation)")
    original = generate_test_wav(duration_seconds=0.5)

    # Encode (client side)
    encoded = base64.b64encode(original).decode("utf-8")
    print(f"  Encoded length: {len(encoded)} chars")

    # Decode (server side)
    decoded = base64.b64decode(encoded)
    assert decoded == original, "Round-trip mismatch!"
    print("  Round-trip: OK")

    fmt = detect_audio_format(decoded)
    print(f"  Detected format after decode: {fmt}")

    text = transcribe_audio(decoded)
    print(f"  Transcription: '{text}'")


# ── Test 5: Language hint accuracy ───────────────────────────
def test_language_hints(filepath: str = None):
    print_section("TEST 5 — Language hints")
    if not filepath or not os.path.exists(filepath):
        print("  Skipping — provide a real audio file as argument.")
        return
    with open(filepath, "rb") as f:
        audio_bytes = f.read()
    for lang in ["en", "hi", "ta"]:
        text = transcribe_audio(audio_bytes, language_hint=lang)
        print(f"  Hint={lang}: '{text}'")


# ── Run all tests ─────────────────────────────────────────────
if __name__ == "__main__":
    # Optionally pass an audio file path as CLI arg
    # python test_stt.py path/to/audio.wav
    audio_file = sys.argv[1] if len(sys.argv) > 1 else None

    test_silent_wav()
    test_real_file(audio_file or "test_audio.wav")
    test_multilingual(audio_file)
    test_base64_roundtrip()
    test_language_hints(audio_file)

    print(f"\n{'='*55}")
    print("  All STT tests complete.")
    print(f"{'='*55}\n")