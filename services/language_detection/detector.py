# ============================================================
# services/language_detection/detector.py
# Three-layer language detection pipeline
# ============================================================

import sys, os, time, re
sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from config import DEFAULT_LANGUAGE, GROQ_API_KEY, GROQ_LLM_MODEL
from services.language_detection.language_utils import (
    contains_devanagari,
    contains_tamil,
    is_latin_script,
    normalise_language_code,
    get_language_name,
    is_supported_language,
)


# ── Layer 1: Script-based detection (fastest — microseconds) ──
def detect_by_script(text: str) -> str | None:
    """
    Detects language purely from Unicode script.
    Returns language code or None if inconclusive.

    This is the fastest path — no API calls, no imports.
    Hindi and Tamil are always caught here because they use
    unique non-Latin scripts.
    """
    if not text or not text.strip():
        return None

    if contains_devanagari(text):
        return "hi"

    if contains_tamil(text):
        return "ta"

    # Mostly ASCII/Latin → likely English, but not certain
    # (could be romanised Hindi/Tamil — let langdetect confirm)
    if is_latin_script(text):
        return "en"   # confident enough for Latin-only text

    return None


# ── Layer 2: langdetect library (fast — <5ms) ─────────────────
def detect_by_langdetect(text: str) -> str | None:
    """
    Uses the langdetect library for statistical detection.
    Returns normalised code or None on failure.
    """
    try:
        from langdetect import detect, LangDetectException
        from langdetect.detector_factory import DetectorFactory

        # Seed for reproducibility — same text always gives same result
        DetectorFactory.seed = 42

        # Need at least ~10 chars for reliable detection
        if len(text.strip()) < 6:
            return None

        raw_code = detect(text)
        normalised = normalise_language_code(raw_code)
        return normalised

    except Exception as e:
        print(f"[LANG][langdetect] Failed: {e}")
        return None


# ── Layer 3: LLM-based detection (slowest — ~200ms) ──────────
def detect_by_llm(text: str) -> str | None:
    """
    Uses Groq LLM as final fallback for ambiguous cases.
    Only called when layers 1 and 2 are inconclusive.
    Returns 'en', 'hi', or 'ta'.
    """
    try:
        from groq import Groq
        client = Groq(api_key=GROQ_API_KEY)

        prompt = f"""Detect the language of this text. 
Reply with ONLY one of these codes: en, hi, ta
- en = English
- hi = Hindi  
- ta = Tamil

Text: "{text}"

Code:"""

        response = client.chat.completions.create(
            model=GROQ_LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=5,
            temperature=0.0,
        )

        raw = response.choices[0].message.content.strip().lower()

        # Extract just the code (model might add punctuation)
        match = re.search(r"\b(en|hi|ta)\b", raw)
        if match:
            return match.group(1)

        return None

    except Exception as e:
        print(f"[LANG][LLM] Failed: {e}")
        return None


# ── Main detection function ───────────────────────────────────
def detect_language(text: str,
                    use_llm_fallback: bool = True,
                    verbose: bool = False) -> str:
    """
    Three-layer language detection pipeline.

    Layer 1 — Script check    (microseconds, no network)
    Layer 2 — langdetect      (<5ms, no network)
    Layer 3 — LLM fallback    (~200ms, Groq API)

    Args:
        text:             Input text to detect language of.
        use_llm_fallback: Whether to call LLM if layers 1+2 fail.
        verbose:          Print which layer resolved detection.

    Returns:
        Language code: 'en', 'hi', or 'ta'.
        Falls back to DEFAULT_LANGUAGE if all layers fail.
    """
    t_start = time.time()

    if not text or not text.strip():
        return DEFAULT_LANGUAGE

    # Clean text — remove URLs, numbers, punctuation for better detection
    clean = re.sub(r"http\S+", "", text)
    clean = re.sub(r"[0-9]", "", clean).strip()

    # ── Layer 1: Script ───────────────────────────────────────
    t1 = time.time()
    result = detect_by_script(clean)
    if result:
        elapsed = int((time.time() - t_start) * 1000)
        if verbose:
            print(f"[LANG] Script → '{result}' "
                  f"({get_language_name(result)}) in {elapsed}ms")
        return result

    # ── Layer 2: langdetect ───────────────────────────────────
    t2 = time.time()
    result = detect_by_langdetect(clean)
    if result:
        elapsed = int((time.time() - t_start) * 1000)
        if verbose:
            print(f"[LANG] langdetect → '{result}' "
                  f"({get_language_name(result)}) in {elapsed}ms")
        return result

    # ── Layer 3: LLM ─────────────────────────────────────────
    if use_llm_fallback:
        t3 = time.time()
        result = detect_by_llm(clean)
        if result:
            elapsed = int((time.time() - t_start) * 1000)
            if verbose:
                print(f"[LANG] LLM → '{result}' "
                      f"({get_language_name(result)}) in {elapsed}ms")
            return result

    # ── Final fallback ────────────────────────────────────────
    elapsed = int((time.time() - t_start) * 1000)
    if verbose:
        print(f"[LANG] Fallback → '{DEFAULT_LANGUAGE}' in {elapsed}ms")
    return DEFAULT_LANGUAGE


# ── Session-aware detection ───────────────────────────────────
def detect_language_with_context(text: str,
                                  session_language: str = None,
                                  confidence_threshold: int = 4) -> str:
    """
    Detects language but considers the session's current language.
    If the detected language differs from session language, requires
    a minimum text length before switching — avoids false switches
    on very short utterances like 'ok', 'yes', 'ha'.

    Args:
        text:                 Input text.
        session_language:     Current session language code.
        confidence_threshold: Min character count to trust a switch.

    Returns:
        Language code.
    """
    detected = detect_language(text)

    if not session_language:
        return detected

    # If detected language differs from session language
    if detected != session_language:
        # Short text → trust the session language
        clean_len = len(text.strip())
        if clean_len < confidence_threshold:
            return session_language
        # Longer text → trust the detection (user switched language)
        print(f"[LANG] Language switch detected: "
              f"{session_language} → {detected}")

    return detected


# ── Batch detection ───────────────────────────────────────────
def detect_language_batch(texts: list[str]) -> list[str]:
    """
    Detects language for a list of texts efficiently.
    Script check is reused without re-importing langdetect.
    """
    results = []
    for text in texts:
        results.append(detect_language(text, use_llm_fallback=False))
    return results