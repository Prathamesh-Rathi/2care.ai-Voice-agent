# ============================================================
# test_tts.py  —  TTS test suite
# Run: python test_tts.py
# Output files saved to tts_output/
# ============================================================

import sys, os, base64, time
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.text_to_speech.tts import (
    synthesize_speech,
    save_audio_file,
    speak_text,
    synthesize_batch,
)
from services.text_to_speech.tts_utils import (
    clean_text_for_tts,
    get_cache_stats,
    clear_tts_cache,
)


def print_section(title: str):
    print(f"\n{'='*56}")
    print(f"  {title}")
    print(f"{'='*56}")


# ── Test 1: Basic English TTS ─────────────────────────────────
def test_english():
    print_section("TEST 1 — English TTS")
    texts = [
        "Your appointment has been booked successfully.",
        "Your appointment with Doctor Arjun Sharma is confirmed for tomorrow at ten AM.",
        "No slots are available on that date. Would you like to try another day?",
    ]
    for text in texts:
        t0    = time.time()
        audio = synthesize_speech(text, "en")
        ms    = int((time.time() - t0) * 1000)
        path  = save_audio_file(audio, folder="tts_output")
        print(f"  [{ms}ms] {len(audio)} bytes → {path}")
        print(f"  Text: '{text[:55]}'")


# ── Test 2: Hindi TTS ─────────────────────────────────────────
def test_hindi():
    print_section("TEST 2 — Hindi TTS")
    texts = [
        "आपकी अपॉइंटमेंट बुक हो गई है।",
        "डॉक्टर अर्जुन शर्मा के साथ कल सुबह दस बजे आपकी अपॉइंटमेंट है।",
        "उस तारीख पर कोई स्लॉट उपलब्ध नहीं है।",
    ]
    for text in texts:
        t0    = time.time()
        audio = synthesize_speech(text, "hi")
        ms    = int((time.time() - t0) * 1000)
        path  = save_audio_file(audio, folder="tts_output")
        print(f"  [{ms}ms] {len(audio)} bytes → {path}")
        print(f"  Text: '{text}'")


# ── Test 3: Tamil TTS ─────────────────────────────────────────
def test_tamil():
    print_section("TEST 3 — Tamil TTS")
    texts = [
        "உங்கள் சந்திப்பு முன்பதிவு செய்யப்பட்டது.",
        "நாளை காலை பத்து மணிக்கு மருத்துவர் அர்ஜுன் சர்மாவுடன் சந்திப்பு உள்ளது.",
        "அந்த தேதியில் இடங்கள் இல்லை.",
    ]
    for text in texts:
        t0    = time.time()
        audio = synthesize_speech(text, "ta")
        ms    = int((time.time() - t0) * 1000)
        path  = save_audio_file(audio, folder="tts_output")
        print(f"  [{ms}ms] {len(audio)} bytes → {path}")
        print(f"  Text: '{text}'")


# ── Test 4: Cache performance ─────────────────────────────────
def test_cache():
    print_section("TEST 4 — Cache performance")
    text = "Your appointment has been confirmed."
    lang = "en"

    # First call — synthesizes
    t0    = time.time()
    audio = synthesize_speech(text, lang, use_cache=True)
    ms1   = int((time.time() - t0) * 1000)
    print(f"  First call  (synthesis): {ms1}ms")

    # Second call — from cache
    t0    = time.time()
    audio = synthesize_speech(text, lang, use_cache=True)
    ms2   = int((time.time() - t0) * 1000)
    print(f"  Second call (cache):     {ms2}ms")
    print(f"  Speedup: {round(ms1/max(ms2,1), 1)}x faster from cache")

    stats = get_cache_stats()
    print(f"  Cache stats: {stats}")


# ── Test 5: Text cleaning ─────────────────────────────────────
def test_text_cleaning():
    print_section("TEST 5 — Text cleaning")
    dirty_texts = [
        "Your **appointment** is *confirmed*!",
        "Visit https://hospital.com for details",
        'Raw JSON leaked: {"intent": "book", "doctor": "Sharma"}',
        "Dr. Sharma at 10 AM in Room No. 5",
        "   Too    many    spaces   ",
    ]
    for dirty in dirty_texts:
        clean = clean_text_for_tts(dirty)
        print(f"  Before: '{dirty[:55]}'")
        print(f"  After:  '{clean[:55]}'")
        print()


# ── Test 6: Base64 encoding (WebSocket simulation) ────────────
def test_base64_encoding():
    print_section("TEST 6 — Base64 encoding (WebSocket flow)")
    text  = "Your appointment has been booked for tomorrow."
    audio = synthesize_speech(text, "en")

    # Encode — as server would do before sending over WebSocket
    encoded = base64.b64encode(audio).decode("utf-8")
    print(f"  Audio bytes  : {len(audio)}")
    print(f"  Base64 length: {len(encoded)} chars")

    # Decode — as client would do on receiving
    decoded = base64.b64decode(encoded)
    assert decoded == audio, "Round-trip mismatch!"
    print(f"  Round-trip   : OK")
    print(f"  First 4 bytes: {decoded[:4]} (should be ID3 or ÿû for MP3)")


# ── Test 7: Batch synthesis ───────────────────────────────────
def test_batch():
    print_section("TEST 7 — Batch synthesis")
    items = [
        {"text": "Hello, this is a reminder for your appointment tomorrow.", "language": "en"},
        {"text": "नमस्ते, कल आपकी अपॉइंटमेंट की याद दिलाने के लिए कॉल कर रहे हैं।", "language": "hi"},
        {"text": "வணக்கம், நாளை உங்கள் சந்திப்பு இருப்பதை நினைவூட்ட அழைக்கிறோம்.", "language": "ta"},
    ]
    t0      = time.time()
    results = synthesize_batch(items)
    ms      = int((time.time() - t0) * 1000)
    for r in results:
        audio = r["audio_bytes"]
        path  = save_audio_file(audio, folder="tts_output")
        print(f"  [{r['language']}] {len(audio)} bytes → {path}")
    print(f"  Total batch time: {ms}ms for {len(items)} items")


# ── Test 8: Full pipeline simulation ─────────────────────────
def test_full_pipeline():
    print_section("TEST 8 — Full pipeline simulation")
    print("  Simulating: user books → agent replies → TTS speaks\n")

    scenarios = [
        {
            "lang":     "en",
            "response": "Your appointment with Doctor Arjun Sharma has been booked "
                        "for tomorrow at nine AM. Please arrive 10 minutes early.",
        },
        {
            "lang":     "hi",
            "response": "आपकी अपॉइंटमेंट डॉक्टर अर्जुन शर्मा के साथ कल सुबह "
                        "नौ बजे बुक हो गई है।",
        },
        {
            "lang":     "ta",
            "response": "உங்கள் சந்திப்பு நாளை காலை ஒன்பது மணிக்கு "
                        "மருத்துவர் அர்ஜுன் சர்மாவுடன் முன்பதிவு செய்யப்பட்டது.",
        },
    ]

    for s in scenarios:
        t0    = time.time()
        audio = synthesize_speech(s["response"], s["lang"])
        ms    = int((time.time() - t0) * 1000)
        enc   = base64.b64encode(audio).decode("utf-8")
        path  = save_audio_file(audio, folder="tts_output")

        print(f"  Language : {s['lang'].upper()}")
        print(f"  Text     : '{s['response'][:50]}...'")
        print(f"  Audio    : {len(audio)} bytes | {ms}ms")
        print(f"  Base64   : {len(enc)} chars (ready for WebSocket)")
        print(f"  File     : {path}")
        print()


# ── Run all ───────────────────────────────────────────────────
if __name__ == "__main__":
    test_english()
    test_hindi()
    test_tamil()
    test_cache()
    test_text_cleaning()
    test_base64_encoding()
    test_batch()
    test_full_pipeline()

    print(f"\n{'='*56}")
    print("  All TTS tests complete.")
    print(f"  Audio files saved in: tts_output/")
    print(f"{'='*56}\n")