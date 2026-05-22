# ============================================================
# test_lang.py  —  Language detection test suite
# Run: python test_lang.py
# ============================================================

import sys, os, time
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.language_detection.detector import (
    detect_language,
    detect_by_script,
    detect_by_langdetect,
    detect_language_with_context,
    detect_language_batch,
)
from services.language_detection.language_utils import (
    get_template,
    quick_intent_hint,
    get_language_name,
)


def print_section(title: str):
    print(f"\n{'='*55}")
    print(f"  {title}")
    print(f"{'='*55}")


# ── Test cases ────────────────────────────────────────────────
TEST_CASES = [
    # (text, expected_language, description)

    # English
    ("Book appointment with cardiologist tomorrow",   "en", "English booking"),
    ("I want to see a dermatologist",                 "en", "English doctor request"),
    ("Cancel my appointment please",                  "en", "English cancel"),
    ("What slots are available on Friday?",           "en", "English check slots"),

    # Hindi (Devanagari script — always Layer 1)
    ("मुझे कल डॉक्टर से मिलना है",                  "hi", "Hindi appointment"),
    ("मेरी अपॉइंटमेंट रद्द करें",                   "hi", "Hindi cancel"),
    ("क्या कोई स्लॉट उपलब्ध है?",                   "hi", "Hindi check slots"),
    ("मुझे हृदय रोग विशेषज्ञ से मिलना है",          "hi", "Hindi cardiologist"),

    # Tamil (Tamil script — always Layer 1)
    ("நாளை மருத்துவரை பார்க்க வேண்டும்",            "ta", "Tamil appointment"),
    ("என் சந்திப்பை ரத்து செய்யுங்கள்",             "ta", "Tamil cancel"),
    ("மருத்துவர் கிடைக்கிறார்களா?",                 "ta", "Tamil check"),

    # Edge cases
    ("ok",                                            "en", "Short text"),
    ("hi",                                            "en", "Ambiguous short"),
    ("",                                              "en", "Empty string"),
    ("123 456 789",                                   "en", "Numbers only"),
]


def test_full_pipeline():
    print_section("TEST 1 — Full pipeline (all test cases)")
    passed = 0
    failed = 0

    for text, expected, desc in TEST_CASES:
        t0     = time.time()
        result = detect_language(text, verbose=False)
        ms     = int((time.time() - t0) * 1000)
        status = "✓" if result == expected else "✗"
        if result == expected:
            passed += 1
        else:
            failed += 1
        print(f"  {status} [{ms:>3}ms] {desc}")
        if result != expected:
            print(f"       Expected={expected} Got={result} Text='{text[:40]}'")

    print(f"\n  Results: {passed} passed, {failed} failed out of {len(TEST_CASES)}")


def test_layer_speeds():
    print_section("TEST 2 — Layer speed comparison")
    samples = [
        ("Book my appointment",            "English (Layer 1 — Latin)"),
        ("मुझे डॉक्टर से मिलना है",         "Hindi  (Layer 1 — Script)"),
        ("நாளை மருத்துவர்",                "Tamil  (Layer 1 — Script)"),
    ]
    for text, label in samples:
        # Layer 1 only
        t0 = time.time()
        r1 = detect_by_script(text)
        ms1 = int((time.time() - t0) * 1000)

        # Layer 2 only
        t0 = time.time()
        r2 = detect_by_langdetect(text)
        ms2 = int((time.time() - t0) * 1000)

        # Full pipeline
        t0 = time.time()
        r3 = detect_language(text, use_llm_fallback=False)
        ms3 = int((time.time() - t0) * 1000)

        print(f"\n  {label}")
        print(f"    Layer 1 (script):     {r1} in {ms1}ms")
        print(f"    Layer 2 (langdetect): {r2} in {ms2}ms")
        print(f"    Full pipeline:        {r3} in {ms3}ms")


def test_context_aware():
    print_section("TEST 3 — Context-aware detection (session switching)")

    cases = [
        ("ok",   "hi", "hi",  "Short 'ok' → keeps Hindi session"),
        ("yes",  "ta", "ta",  "Short 'yes' → keeps Tamil session"),
        ("मुझे डॉक्टर चाहिए", "en", "hi", "Long Hindi → switches from English"),
        ("நாளை பார்க்க வேண்டும்", "en", "ta", "Long Tamil → switches from English"),
        ("Book appointment tomorrow", "hi", "en", "Long English → switches from Hindi"),
    ]

    for text, session_lang, expected, desc in cases:
        result = detect_language_with_context(text, session_language=session_lang)
        status = "✓" if result == expected else "✗"
        print(f"  {status} {desc}")
        if result != expected:
            print(f"       Expected={expected} Got={result}")


def test_templates():
    print_section("TEST 4 — Response templates per language")
    keys = ["greeting", "book_confirm", "cancel_confirm", "ask_date"]
    for lang in ["en", "hi", "ta"]:
        print(f"\n  [{lang.upper()}]")
        for key in keys:
            print(f"    {key}: {get_template(lang, key)}")


def test_intent_hints():
    print_section("TEST 5 — Quick intent keyword hints")
    samples = [
        ("Book appointment with cardiologist", "en"),
        ("Cancel my appointment",              "en"),
        ("मेरी अपॉइंटमेंट रद्द करें",         "hi"),
        ("மருத்துவர் பதிவு செய்ய வேண்டும்",   "ta"),
        ("What slots are available?",          "en"),
    ]
    for text, lang in samples:
        hint = quick_intent_hint(text, lang)
        print(f"  [{lang}] '{text[:40]}' → intent_hint={hint}")


def test_batch():
    print_section("TEST 6 — Batch detection")
    texts = [
        "Book appointment tomorrow",
        "मुझे डॉक्टर से मिलना है",
        "நாளை மருத்துவரை பார்க்க",
        "Cancel my appointment",
        "क्या स्लॉट उपलब्ध है?",
    ]
    t0      = time.time()
    results = detect_language_batch(texts)
    ms      = int((time.time() - t0) * 1000)
    for text, lang in zip(texts, results):
        print(f"  [{lang}] {text[:45]}")
    print(f"\n  Batch of {len(texts)} in {ms}ms total")


# ── Run all ───────────────────────────────────────────────────
if __name__ == "__main__":
    test_full_pipeline()
    test_layer_speeds()
    test_context_aware()
    test_templates()
    test_intent_hints()
    test_batch()

    print(f"\n{'='*55}")
    print("  All language detection tests complete.")
    print(f"{'='*55}\n")