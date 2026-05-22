# ============================================================
# test_agent.py  —  Standalone agent test
# Run: python test_agent.py
# Make sure DB is seeded: python database/seed.py
# ============================================================

import sys, os, json
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from agent.reasoning.groq_agent import run_agent


def print_section(title: str):
    print(f"\n{'='*58}")
    print(f"  {title}")
    print(f"{'='*58}")


def run_test(label: str, text: str, lang: str,
             patient_id: int = 1, history: list = None):
    print(f"\n  ── {label}")
    print(f"  User [{lang}]: {text}")
    result = run_agent(
        user_text  = text,
        history    = history or [],
        language   = lang,
        patient_id = patient_id
    )
    print(f"  Bot : {result['patient_response']}")
    print(f"  Meta: intent={result['intent']} | "
          f"appt={result['appointment']} | "
          f"needs_more={result['needs_more_info']}")
    return result


# ── Test 1: English — booking flow ───────────────────────────
def test_english_booking():
    print_section("TEST 1 — English booking flow")
    history = []

    r1 = run_test(
        "Book cardiologist tomorrow",
        "Book an appointment with a cardiologist tomorrow",
        "en", patient_id=2
    )
    history.append({"role": "user",      "content": "Book an appointment with a cardiologist tomorrow"})
    history.append({"role": "assistant", "content": r1["patient_response"]})

    run_test("Follow-up", "Yes, the first available time", "en",
             patient_id=2, history=history)


# ── Test 2: Hindi ─────────────────────────────────────────────
def test_hindi():
    print_section("TEST 2 — Hindi conversation")
    run_test(
        "Hindi appointment",
        "मुझे कल हृदय रोग विशेषज्ञ से मिलना है",
        "hi", patient_id=1
    )
    run_test(
        "Hindi cancel",
        "मेरी अपॉइंटमेंट रद्द करें",
        "hi", patient_id=1
    )


# ── Test 3: Tamil ─────────────────────────────────────────────
def test_tamil():
    print_section("TEST 3 — Tamil conversation")
    run_test(
        "Tamil appointment",
        "நாளை மருத்துவரை பார்க்க வேண்டும்",
        "ta", patient_id=3
    )


# ── Test 4: Check availability ────────────────────────────────
def test_availability():
    print_section("TEST 4 — Check availability")
    run_test(
        "Check dermatologist",
        "Is there a dermatologist available tomorrow?",
        "en", patient_id=2
    )


# ── Test 5: Incomplete request (needs clarification) ──────────
def test_clarification():
    print_section("TEST 5 — Incomplete request")
    run_test(
        "No date given",
        "I want to book an appointment",
        "en", patient_id=2
    )


# ── Test 6: Chitchat ──────────────────────────────────────────
def test_chitchat():
    print_section("TEST 6 — Chitchat / off-topic")
    run_test("Greeting", "Hello, how are you?", "en", patient_id=2)
    run_test("Weather",  "What's the weather today?", "en", patient_id=2)


# ── Test 7: Multi-turn context ────────────────────────────────
def test_multiturn():
    print_section("TEST 7 — Multi-turn context")
    history = []

    turns = [
        ("I need to see a doctor", "en"),
        ("A skin doctor", "en"),
        ("Tomorrow morning", "en"),
    ]

    for text, lang in turns:
        r = run_test(f"Turn: '{text}'", text, lang,
                     patient_id=2, history=history)
        history.append({"role": "user",      "content": text})
        history.append({"role": "assistant", "content": r["patient_response"]})


# ── Run all ───────────────────────────────────────────────────
if __name__ == "__main__":
    print("\nMake sure server is NOT needed — agent runs standalone.")
    print("Make sure DB is seeded: python database/seed.py\n")

    test_english_booking()
    test_hindi()
    test_tamil()
    test_availability()
    test_clarification()
    test_chitchat()
    test_multiturn()

    print(f"\n{'='*58}")
    print("  All agent tests complete.")
    print(f"{'='*58}\n")