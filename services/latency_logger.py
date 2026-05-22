# ============================================================
# services/latency_logger.py
# Measures, logs, and reports pipeline latency per request
# ============================================================

import os, sys, json, time
from datetime import datetime
from collections import deque

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
from config import LATENCY_TARGET_MS

# ── Rolling log (last 100 requests in memory) ─────────────────
_log: deque = deque(maxlen=100)

# ── Log file path ─────────────────────────────────────────────
LOG_DIR  = "logs"
LOG_FILE = os.path.join(LOG_DIR, "latency.jsonl")
os.makedirs(LOG_DIR, exist_ok=True)


# ── Timer context manager ─────────────────────────────────────
class Timer:
    """
    Simple context manager for measuring elapsed time.

    Usage:
        with Timer() as t:
            do_something()
        print(t.ms)   # elapsed milliseconds
    """
    def __init__(self):
        self.ms = 0
        self._start = None

    def __enter__(self):
        self._start = time.time()
        return self

    def __exit__(self, *args):
        self.ms = int((time.time() - self._start) * 1000)


# ── Record a full pipeline measurement ────────────────────────
def record_pipeline(session_id: str,
                    patient_id: int,
                    language: str,
                    stt_ms: int,
                    lang_ms: int,
                    agent_ms: int,
                    tts_ms: int,
                    intent: str = "unknown",
                    cache_hit: bool = False) -> dict:
    """
    Records one complete pipeline measurement.
    Saves to in-memory log + JSONL file.
    Returns the full record dict.
    """
    total_ms     = stt_ms + lang_ms + agent_ms + tts_ms
    within_target = total_ms < LATENCY_TARGET_MS

    record = {
        "ts":             datetime.utcnow().isoformat() + "Z",
        "session_id":     session_id[:8] if session_id else "unknown",
        "patient_id":     patient_id,
        "language":       language,
        "intent":         intent,
        "stt_ms":         stt_ms,
        "lang_ms":        lang_ms,
        "agent_ms":       agent_ms,
        "tts_ms":         tts_ms,
        "total_ms":       total_ms,
        "target_ms":      LATENCY_TARGET_MS,
        "within_target":  within_target,
        "tts_cache_hit":  cache_hit,
    }

    # ── In-memory rolling log ─────────────────────────────────
    _log.append(record)

    # ── JSONL file log ────────────────────────────────────────
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except Exception as e:
        print(f"[LATENCY] File write failed: {e}")

    # ── Console summary ───────────────────────────────────────
    target_str = "✓" if within_target else "⚠ OVER"
    cache_str  = "(cached)" if cache_hit else ""
    print(
        f"[LATENCY] STT={stt_ms}ms | LANG={lang_ms}ms | "
        f"AGENT={agent_ms}ms | TTS={tts_ms}ms {cache_str} | "
        f"TOTAL={total_ms}ms {target_str}"
    )

    return record


# ── Statistics ────────────────────────────────────────────────
def get_stats(last_n: int = 50) -> dict:
    """
    Returns statistical summary of recent pipeline measurements.

    Args:
        last_n: How many recent records to analyse.

    Returns dict with averages, p95, target hit rate, etc.
    """
    records = list(_log)[-last_n:]
    if not records:
        return {"error": "No records yet."}

    def avg(key):
        vals = [r[key] for r in records if key in r]
        return round(sum(vals) / len(vals), 1) if vals else 0

    def p95(key):
        vals = sorted(r[key] for r in records if key in r)
        if not vals:
            return 0
        idx = int(len(vals) * 0.95)
        return vals[min(idx, len(vals) - 1)]

    def pct_under_target():
        hits = sum(1 for r in records if r.get("within_target"))
        return round(hits / len(records) * 100, 1)

    def cache_hit_rate():
        hits = sum(1 for r in records if r.get("tts_cache_hit"))
        return round(hits / len(records) * 100, 1)

    totals = [r["total_ms"] for r in records]

    return {
        "sample_size":       len(records),
        "target_ms":         LATENCY_TARGET_MS,
        "within_target_pct": pct_under_target(),
        "cache_hit_rate_pct": cache_hit_rate(),
        "avg": {
            "stt_ms":   avg("stt_ms"),
            "lang_ms":  avg("lang_ms"),
            "agent_ms": avg("agent_ms"),
            "tts_ms":   avg("tts_ms"),
            "total_ms": avg("total_ms"),
        },
        "p95": {
            "stt_ms":   p95("stt_ms"),
            "lang_ms":  p95("lang_ms"),
            "agent_ms": p95("agent_ms"),
            "tts_ms":   p95("tts_ms"),
            "total_ms": p95("total_ms"),
        },
        "min_total_ms": min(totals),
        "max_total_ms": max(totals),
        "by_language": _breakdown_by_language(records),
        "by_intent":   _breakdown_by_intent(records),
    }


def _breakdown_by_language(records: list) -> dict:
    langs = {}
    for r in records:
        lang = r.get("language", "unknown")
        if lang not in langs:
            langs[lang] = []
        langs[lang].append(r["total_ms"])
    return {
        lang: {
            "count":   len(vals),
            "avg_ms":  round(sum(vals) / len(vals), 1),
        }
        for lang, vals in langs.items()
    }


def _breakdown_by_intent(records: list) -> dict:
    intents = {}
    for r in records:
        intent = r.get("intent", "unknown")
        if intent not in intents:
            intents[intent] = []
        intents[intent].append(r["total_ms"])
    return {
        intent: {
            "count":  len(vals),
            "avg_ms": round(sum(vals) / len(vals), 1),
        }
        for intent, vals in intents.items()
    }


def print_stats_report(last_n: int = 50):
    """Prints a formatted latency report to console."""
    stats = get_stats(last_n)
    if "error" in stats:
        print(f"[LATENCY] {stats['error']}")
        return

    print(f"\n{'='*60}")
    print(f"  LATENCY REPORT  (last {stats['sample_size']} requests)")
    print(f"{'='*60}")
    print(f"  Target            : {stats['target_ms']}ms")
    print(f"  Within target     : {stats['within_target_pct']}%")
    print(f"  TTS cache hit rate: {stats['cache_hit_rate_pct']}%")
    print(f"  Min / Max total   : {stats['min_total_ms']}ms / {stats['max_total_ms']}ms")
    print(f"\n  {'Stage':<10} {'Avg':>8} {'p95':>8}")
    print(f"  {'-'*28}")
    for stage in ["stt_ms", "lang_ms", "agent_ms", "tts_ms", "total_ms"]:
        label = stage.replace("_ms", "").upper()
        print(f"  {label:<10} "
              f"{stats['avg'][stage]:>6.0f}ms "
              f"{stats['p95'][stage]:>6.0f}ms")
    print(f"\n  By language: {stats['by_language']}")
    print(f"  By intent  : {stats['by_intent']}")
    print(f"{'='*60}\n")


def get_recent_log(n: int = 10) -> list:
    """Returns last N log records."""
    return list(_log)[-n:]