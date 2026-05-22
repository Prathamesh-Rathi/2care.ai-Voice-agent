# ============================================================
# test_latency.py  —  Latency logger + cache warmer tests
# Run: python test_latency.py
# ============================================================

import sys, os, time
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.latency_logger import (
    record_pipeline, get_stats,
    print_stats_report, get_recent_log, Timer,
)
from services.cache_warmer import warm_cache
from services.text_to_speech.tts_utils import get_cache_stats


def print_section(title: str):
    print(f"\n{'='*58}")
    print(f"  {title}")
    print(f"{'='*58}")


# ── Test 1: Timer context manager ─────────────────────────────
def test_timer():
    print_section("TEST 1 — Timer context manager")
    with Timer() as t:
        time.sleep(0.05)
    print(f"  50ms sleep → measured {t.ms}ms (expected ~50)")

    with Timer() as t:
        _ = sum(range(1_000_000))
    print(f"  Sum 1M    → measured {t.ms}ms")


# ── Test 2: Record pipeline measurements ─────────────────────
def test_record():
    print_section("TEST 2 — Record pipeline measurements")

    # Simulate 10 pipeline calls
    import random
    for i in range(10):
        lang   = random.choice(["en", "hi", "ta"])
        intent = random.choice(["book", "cancel", "check_availability", "chitchat"])
        record_pipeline(
            session_id = f"test_session_{i}",
            patient_id = random.randint(1, 3),
            language   = lang,
            stt_ms     = random.randint(100, 350),
            lang_ms    = random.randint(0, 5),
            agent_ms   = random.randint(200, 500),
            tts_ms     = random.randint(2, 900),
            intent     = intent,
            cache_hit  = random.random() > 0.5,
        )
    print(f"  Recorded 10 pipeline measurements.")


# ── Test 3: Stats report ──────────────────────────────────────
def test_stats():
    print_section("TEST 3 — Stats report")
    print_stats_report(last_n=10)


# ── Test 4: Recent log ────────────────────────────────────────
def test_recent_log():
    print_section("TEST 4 — Recent log (last 5)")
    log = get_recent_log(5)
    for entry in log:
        print(f"  [{entry['language']}] intent={entry['intent']:20s} "
              f"total={entry['total_ms']}ms "
              f"target={'✓' if entry['within_target'] else '✗'}")


# ── Test 5: Cache warmer ──────────────────────────────────────
def test_cache_warmer():
    print_section("TEST 5 — TTS Cache warmer")
    print("  This synthesizes all common phrases.")
    print("  First run takes ~2-3 mins. Re-runs are instant.\n")
    results = warm_cache(verbose=True)
    print(f"\n  Results: {results}")

    stats = get_cache_stats()
    print(f"  Cache stats: {stats}")


# ── Test 6: Cache hit speed comparison ───────────────────────
def test_cache_speed():
    print_section("TEST 6 — Cache hit vs miss speed")
    from services.text_to_speech.tts import synthesize_speech

    text = "Your appointment has been booked successfully."
    lang = "en"

    # First call (may synthesize or hit cache)
    t0    = time.time()
    _     = synthesize_speech(text, lang, use_cache=True)
    first = int((time.time() - t0) * 1000)

    # Second call (always cache)
    t0     = time.time()
    _      = synthesize_speech(text, lang, use_cache=True)
    second = int((time.time() - t0) * 1000)

    print(f"  First call : {first}ms")
    print(f"  Second call: {second}ms (cache)")
    if first > 0:
        print(f"  Speedup    : {round(first/max(second,1), 1)}x")

    # Latency contribution
    print(f"\n  If TTS takes {first}ms  → "
          f"total pipeline ~{300+first}ms "
          f"({'✓' if 300+first < 450 else '⚠ over target'})")
    print(f"  If TTS takes {second}ms  → "
          f"total pipeline ~{300+second}ms "
          f"({'✓' if 300+second < 450 else '⚠ over target'})")


# ── Test 7: Log file check ────────────────────────────────────
def test_log_file():
    print_section("TEST 7 — Log file")
    log_path = "logs/latency.jsonl"
    if os.path.exists(log_path):
        size  = os.path.getsize(log_path)
        lines = 0
        with open(log_path, "r") as f:
            lines = sum(1 for _ in f)
        print(f"  Log file  : {log_path}")
        print(f"  Size      : {size} bytes")
        print(f"  Records   : {lines} lines")
    else:
        print(f"  Log file not yet created (created on first real request).")


# ── Run all ───────────────────────────────────────────────────
if __name__ == "__main__":
    test_timer()
    test_record()
    test_stats()
    test_recent_log()
    test_cache_speed()
    test_log_file()

    # Cache warmer last — it takes time on first run
    run_warmer = input(
        "\n  Run cache warmer? (synthesizes ~40 phrases) [y/N]: "
    ).strip().lower()
    if run_warmer == "y":
        test_cache_warmer()

    print(f"\n{'='*58}")
    print("  All latency tests complete.")
    print(f"{'='*58}\n")