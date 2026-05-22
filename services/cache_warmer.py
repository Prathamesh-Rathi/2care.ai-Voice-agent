# ============================================================
# services/cache_warmer.py
# Pre-synthesizes common TTS responses at startup.
# These are served from cache instantly — zero synthesis delay.
# ============================================================

import os, sys, time
sys.path.append(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

from services.text_to_speech.tts import synthesize_speech
from services.text_to_speech.tts_utils import is_cached


# ── Common responses to pre-cache ────────────────────────────
WARM_PHRASES = {
    "en": [
        "Your appointment has been booked successfully.",
        "Your appointment has been cancelled.",
        "Your appointment has been rescheduled.",
        "I'm sorry, that slot is not available.",
        "No slots are available on that date.",
        "Could you please tell me which date you prefer?",
        "Which type of doctor would you like to see?",
        "What time works best for you?",
        "Hello! How can I help you today?",
        "I'm sorry, I didn't understand that. Could you repeat?",
        "Here are the available time slots.",
        "Would you like me to book the first available slot?",
        "Your appointment is confirmed.",
        "Is there anything else I can help you with?",
        "That date is in the past. Please choose a future date.",
        "The clinic is closed on weekends.",
        "Let me check the available slots for you.",
    ],
    "hi": [
        "आपकी अपॉइंटमेंट बुक हो गई है।",
        "आपकी अपॉइंटमेंट रद्द कर दी गई है।",
        "आपकी अपॉइंटमेंट दोबारा निर्धारित की गई है।",
        "क्षमा करें, वह स्लॉट उपलब्ध नहीं है।",
        "उस तारीख पर कोई स्लॉट उपलब्ध नहीं है।",
        "आप किस तारीख को पसंद करेंगे?",
        "आप किस प्रकार के डॉक्टर से मिलना चाहते हैं?",
        "आपके लिए कौन सा समय सबसे अच्छा रहेगा?",
        "नमस्ते! मैं आपकी कैसे मदद कर सकता हूँ?",
        "मुझे खेद है, मैं समझ नहीं पाया। क्या आप फिर से बोल सकते हैं?",
        "क्या मैं पहला उपलब्ध स्लॉट बुक कर दूँ?",
        "क्या मैं और कुछ मदद कर सकता हूँ?",
        "वह तारीख बीत चुकी है। कृपया भविष्य की तारीख चुनें।",
        "क्लिनिक सप्ताहांत पर बंद रहता है।",
    ],
    "ta": [
        "உங்கள் சந்திப்பு முன்பதிவு செய்யப்பட்டது.",
        "உங்கள் சந்திப்பு ரத்து செய்யப்பட்டது.",
        "உங்கள் சந்திப்பு மறுதிட்டமிடப்பட்டது.",
        "மன்னிக்கவும், அந்த இடம் கிடைக்கவில்லை.",
        "அந்த தேதியில் இடங்கள் இல்லை.",
        "நீங்கள் எந்த தேதியை விரும்புகிறீர்கள்?",
        "நீங்கள் எந்த வகை மருத்துவரை சந்திக்க விரும்புகிறீர்கள்?",
        "உங்களுக்கு எந்த நேரம் சரியாக இருக்கும்?",
        "வணக்கம்! நான் உங்களுக்கு எப்படி உதவலாம்?",
        "மன்னிக்கவும், என்னால் புரிந்துகொள்ள முடியவில்லை.",
        "வேறு ஏதாவது உதவி தேவையா?",
        "கிளினிக் வார இறுதியில் மூடியிருக்கும்.",
    ],
}


def warm_cache(verbose: bool = True) -> dict:
    """
    Pre-synthesizes all phrases in WARM_PHRASES.
    Skips phrases already in cache.
    Returns summary of what was synthesized vs skipped.

    Called once at application startup.
    """
    t_start  = time.time()
    results  = {"synthesized": 0, "skipped": 0, "failed": 0}

    total = sum(len(v) for v in WARM_PHRASES.values())
    if verbose:
        print(f"\n[CACHE WARMER] Starting — {total} phrases to check...")

    for lang, phrases in WARM_PHRASES.items():
        for phrase in phrases:
            if is_cached(phrase, lang):
                results["skipped"] += 1
                if verbose:
                    print(f"  [SKIP] [{lang}] {phrase[:50]}")
                continue

            try:
                audio = synthesize_speech(phrase, lang, use_cache=True)
                if audio and len(audio) > 100:
                    results["synthesized"] += 1
                    if verbose:
                        print(f"  [WARM] [{lang}] {phrase[:50]}")
                else:
                    results["failed"] += 1
                    print(f"  [FAIL] [{lang}] {phrase[:50]}")
            except Exception as e:
                results["failed"] += 1
                print(f"  [ERR ] [{lang}] {phrase[:50]} → {e}")

    elapsed = int((time.time() - t_start) * 1000)
    results["elapsed_ms"] = elapsed

    if verbose:
        print(
            f"\n[CACHE WARMER] Done in {elapsed}ms — "
            f"synthesized={results['synthesized']} | "
            f"skipped={results['skipped']} | "
            f"failed={results['failed']}\n"
        )

    return results


def warm_cache_background():
    """
    Runs warm_cache in a background thread so startup
    is not blocked. Fire-and-forget.
    """
    import threading
    t = threading.Thread(target=warm_cache, daemon=True)
    t.start()
    print("[CACHE WARMER] Running in background thread...")