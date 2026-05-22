# ============================================================
# services/language_detection/language_utils.py
# Language constants, script detection, response templates
# ============================================================

import sys, os
sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
from config import SUPPORTED_LANGUAGES, DEFAULT_LANGUAGE


# ── Unicode script ranges ─────────────────────────────────────
# We check character ranges BEFORE calling langdetect.
# Script-based detection is instant and 100% accurate
# for Hindi (Devanagari) and Tamil scripts.

DEVANAGARI_RANGE = (0x0900, 0x097F)   # Hindi, Marathi, Sanskrit
TAMIL_RANGE      = (0x0B80, 0x0BFF)   # Tamil


def contains_devanagari(text: str) -> bool:
    """Returns True if text has any Devanagari characters (Hindi)."""
    return any(DEVANAGARI_RANGE[0] <= ord(c) <= DEVANAGARI_RANGE[1]
               for c in text)


def contains_tamil(text: str) -> bool:
    """Returns True if text has any Tamil script characters."""
    return any(TAMIL_RANGE[0] <= ord(c) <= TAMIL_RANGE[1]
               for c in text)


def is_latin_script(text: str) -> bool:
    """Returns True if text is mostly ASCII/Latin (likely English)."""
    if not text:
        return True
    latin_chars = sum(1 for c in text if ord(c) < 256)
    return (latin_chars / len(text)) > 0.85


# ── Language metadata ─────────────────────────────────────────
LANGUAGE_META = {
    "en": {
        "name":         "English",
        "native_name":  "English",
        "greeting":     "Hello! How can I help you today?",
        "fallback_msg": "I'm sorry, I didn't understand that.",
        "book_confirm": "Your appointment has been booked.",
        "cancel_confirm": "Your appointment has been cancelled.",
        "reschedule_confirm": "Your appointment has been rescheduled.",
        "no_slots":     "No slots available on that date.",
        "ask_date":     "What date would you prefer?",
        "ask_doctor":   "Which type of doctor would you like to see?",
        "ask_time":     "What time works best for you?",
        "clarify":      "Could you please clarify that?",
    },
    "hi": {
        "name":         "Hindi",
        "native_name":  "हिन्दी",
        "greeting":     "नमस्ते! मैं आपकी कैसे मदद कर सकता हूँ?",
        "fallback_msg": "मुझे खेद है, मैं समझ नहीं पाया।",
        "book_confirm": "आपकी अपॉइंटमेंट बुक हो गई है।",
        "cancel_confirm": "आपकी अपॉइंटमेंट रद्द कर दी गई है।",
        "reschedule_confirm": "आपकी अपॉइंटमेंट दोबारा निर्धारित की गई है।",
        "no_slots":     "उस तारीख पर कोई स्लॉट उपलब्ध नहीं है।",
        "ask_date":     "आप किस तारीख को पसंद करेंगे?",
        "ask_doctor":   "आप किस प्रकार के डॉक्टर से मिलना चाहते हैं?",
        "ask_time":     "आपके लिए कौन सा समय सबसे अच्छा रहेगा?",
        "clarify":      "क्या आप कृपया इसे स्पष्ट कर सकते हैं?",
    },
    "ta": {
        "name":         "Tamil",
        "native_name":  "தமிழ்",
        "greeting":     "வணக்கம்! நான் உங்களுக்கு எப்படி உதவலாம்?",
        "fallback_msg": "மன்னிக்கவும், என்னால் புரிந்துகொள்ள முடியவில்லை.",
        "book_confirm": "உங்கள் சந்திப்பு முன்பதிவு செய்யப்பட்டது.",
        "cancel_confirm": "உங்கள் சந்திப்பு ரத்து செய்யப்பட்டது.",
        "reschedule_confirm": "உங்கள் சந்திப்பு மறுதிட்டமிடப்பட்டது.",
        "no_slots":     "அந்த தேதியில் இடங்கள் இல்லை.",
        "ask_date":     "நீங்கள் எந்த தேதியை விரும்புகிறீர்கள்?",
        "ask_doctor":   "நீங்கள் எந்த வகை மருத்துவரை சந்திக்க விரும்புகிறீர்கள்?",
        "ask_time":     "உங்களுக்கு எந்த நேரம் சரியாக இருக்கும்?",
        "clarify":      "தயவுசெய்து தெளிவுபடுத்த முடியுமா?",
    },
}


# ── langdetect → our code mapping ────────────────────────────
# langdetect returns codes like 'hi', 'ta', 'en', 'mr' etc.
# We map anything we don't support to DEFAULT_LANGUAGE.
LANGDETECT_MAP = {
    "en":  "en",
    "hi":  "hi",
    "ta":  "ta",
    "mr":  "hi",   # Marathi → treat as Hindi (both Devanagari)
    "ne":  "hi",   # Nepali  → treat as Hindi
    "ur":  "hi",   # Urdu    → treat as Hindi
    "ml":  "ta",   # Malayalam → closest supported
    "te":  "ta",   # Telugu    → closest supported
    "kn":  "en",   # Kannada   → fallback English
}


def normalise_language_code(code: str) -> str:
    """
    Maps any langdetect code to one of our supported codes.
    Falls back to DEFAULT_LANGUAGE if unknown.
    """
    if not code:
        return DEFAULT_LANGUAGE
    code = code.strip().lower()[:2]
    return LANGDETECT_MAP.get(code, DEFAULT_LANGUAGE)


def get_language_name(code: str) -> str:
    """Returns human-readable language name."""
    return LANGUAGE_META.get(code, {}).get("name", "English")


def get_template(lang_code: str, key: str) -> str:
    """
    Fetches a response template in the given language.
    Falls back to English if key or language missing.
    """
    lang_data = LANGUAGE_META.get(lang_code, LANGUAGE_META["en"])
    return lang_data.get(key, LANGUAGE_META["en"].get(key, ""))


def is_supported_language(code: str) -> bool:
    return code in SUPPORTED_LANGUAGES


# ── Appointment-related keyword hints per language ────────────
# These help the agent when LLM detection might be slow.
INTENT_KEYWORDS = {
    "en": {
        "book":       ["book", "schedule", "appointment", "see", "visit", "meet"],
        "cancel":     ["cancel", "remove", "delete", "drop"],
        "reschedule": ["reschedule", "change", "move", "shift", "postpone"],
        "check":      ["available", "free", "slots", "when", "check"],
    },
    "hi": {
        "book":       ["बुक", "अपॉइंटमेंट", "मिलना", "दिखाना", "डॉक्टर"],
        "cancel":     ["रद्द", "कैंसिल", "हटाना"],
        "reschedule": ["बदलना", "दूसरे", "शिफ्ट"],
        "check":      ["उपलब्ध", "खाली", "कब", "स्लॉट"],
    },
    "ta": {
        "book":       ["பதிவு", "சந்திப்பு", "மருத்துவர்", "பார்க்க"],
        "cancel":     ["ரத்து", "நீக்க"],
        "reschedule": ["மாற்ற", "நகர்த்த"],
        "check":      ["கிடைக்கும்", "காலி", "எப்போது"],
    },
}


def quick_intent_hint(text: str, lang: str) -> str | None:
    """
    Fast keyword scan to hint at intent before LLM call.
    Returns intent string or None if no clear match.
    """
    text_lower = text.lower()
    keywords   = INTENT_KEYWORDS.get(lang, INTENT_KEYWORDS["en"])
    for intent, words in keywords.items():
        if any(w in text_lower for w in words):
            return intent
    return None