# ============================================================
# agent/reasoning/groq_agent.py
# Core Groq LLM agent — understands intent + calls tools
# ============================================================

import sys
import os
import json
import time
import re

# Ensure project root is on path regardless of where this file is called from
_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(os.path.dirname(_HERE))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# ── Config (fail loudly if missing) ──────────────────────────
from config import GROQ_LLM_MODEL

# ── Groq client ───────────────────────────────────────────────
from services.groq_client import get_groq_client

# ── Prompts ───────────────────────────────────────────────────
from agent.prompt.system_prompt import (
    get_system_prompt,
    get_tool_result_prompt,
    get_clarify_message,
)

# ── Tool execution ────────────────────────────────────────────
from agent.tools.tool_definitions import (
    execute_tool,
    get_tools_description,
)

# ── Persistent memory ─────────────────────────────────────────
from memory.persistent_memory.patient_memory import (
    build_memory_context_prompt,
    record_appointment_booked,
    record_appointment_cancelled,
    record_appointment_rescheduled,
    update_language_preference,
    record_conversation,
)

print("[AGENT] groq_agent.py imported successfully")


# ── Safe JSON extractor ───────────────────────────────────────
def extract_json(text: str) -> dict | None:
    """
    Extracts JSON from LLM output robustly.
    Handles markdown code blocks, extra text, trailing commas.
    """
    if not text:
        return None

    # Strip markdown code fences
    text = re.sub(r"```(?:json)?", "", text).strip()
    text = text.strip("`").strip()

    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Find first { ... } block
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        candidate = match.group(0)
        # Remove trailing commas before } or ]
        candidate = re.sub(r",\s*([}\]])", r"\1", candidate)
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    return None


# ── LLM call wrapper ──────────────────────────────────────────
def call_llm(
    messages: list,
    language: str = "en",
    max_tokens: int = 512,
    patient_id: int = None
) -> str:
    """
    Calls Groq LLM and returns raw text response.
    Injects system prompt + tools description + memory context.
    """
    # Build memory context if patient_id given
    memory_ctx = ""
    if patient_id:
        try:
            memory_ctx = build_memory_context_prompt(patient_id)
        except Exception as e:
            print(f"[AGENT] Memory context failed (non-critical): {e}")
            memory_ctx = ""

    system_content = (
        get_system_prompt(language)
        + "\n"
        + get_tools_description()
        + "\n\nPATIENT CONTEXT:\n"
        + memory_ctx
    )

    full_messages = [
        {"role": "system", "content": system_content},
        *messages
    ]

    t0 = time.time()
    response = get_groq_client().chat.completions.create(
        model=GROQ_LLM_MODEL,
        messages=full_messages,
        max_tokens=max_tokens,
        temperature=0.3,
        top_p=0.9,
    )
    ms = int((time.time() - t0) * 1000)
    print(f"[AGENT] LLM call: {ms}ms")

    return response.choices[0].message.content.strip()


# ── Build conversation messages ───────────────────────────────
def build_messages(
    user_text: str,
    history: list,
    language: str
) -> list:
    """
    Builds messages array for the LLM.
    Includes last 6 turns of history for context efficiency.
    """
    messages = []

    recent = history[-6:] if len(history) > 6 else history
    for turn in recent:
        role = turn.get("role", "user")
        content = turn.get("content", "")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})

    messages.append({"role": "user", "content": user_text})
    return messages


# ── Fallback responses ────────────────────────────────────────
FALLBACK_RESPONSES = {
    "en": "I'm sorry, I had trouble processing that. Could you please repeat?",
    "hi": "मुझे खेद है, मुझे प्रसंस्करण में समस्या हुई। क्या आप फिर से बोल सकते हैं?",
    "ta": "மன்னிக்கவும், செயலாக்கத்தில் சிக்கல் ஏற்பட்டது. மீண்டும் சொல்ல முடியுமா?",
}

def get_fallback(language: str = "en") -> dict:
    return {
        "intent": "clarify",
        "patient_response": FALLBACK_RESPONSES.get(
            language, FALLBACK_RESPONSES["en"]
        ),
        "tool_to_call": "none",
        "tool_args": {},
        "appointment": None,
        "tool_result": None,
        "needs_more_info": False,
    }


# ── Main agent function ───────────────────────────────────────
def run_agent(
    user_text: str,
    history: list,
    language: str = "en",
    patient_id: int = 1
) -> dict:
    """
    Main agent entry point called by WebSocket handler.

    Flow:
      1. Build messages from history + current input
      2. First LLM call → intent + tool_to_call + tool_args
      3. If tool needed → execute tool
      4. Second LLM call → natural language response from tool result
      5. Update persistent memory
      6. Return final patient_response + structured data

    Returns:
        {
          "intent":           str,
          "patient_response": str,
          "appointment":      dict | None,
          "tool_result":      dict | None,
          "needs_more_info":  bool,
        }
    """
    t_total = time.time()
    print(f"\n[AGENT] ── New turn ──────────────────────────")
    print(f"[AGENT] Input     : '{user_text}'")
    print(f"[AGENT] Language  : {language}")
    print(f"[AGENT] Patient ID: {patient_id}")

    # ── Step 1: Build messages ────────────────────────────────
    messages = build_messages(user_text, history, language)

    # ── Step 2: First LLM call ────────────────────────────────
    try:
        raw_response = call_llm(
            messages,
            language=language,
            patient_id=patient_id
        )
        print(f"[AGENT] Raw LLM   : {raw_response[:300]}")
    except Exception as e:
        print(f"[AGENT] LLM call failed: {e}")
        return get_fallback(language)

    # ── Step 3: Parse JSON ────────────────────────────────────
    parsed = extract_json(raw_response)

    if not parsed:
        print(f"[AGENT] JSON parse failed. Raw: {raw_response[:200]}")
        if raw_response and len(raw_response) > 5:
            return {
                "intent": "chitchat",
                "patient_response": raw_response,
                "appointment": None,
                "tool_result": None,
                "needs_more_info": False,
            }
        return get_fallback(language)

    intent       = parsed.get("intent",           "chitchat")
    tool_to_call = parsed.get("tool_to_call",     "none")
    tool_args    = parsed.get("tool_args",         {})
    patient_resp = parsed.get("patient_response", "")
    needs_more   = parsed.get("needs_more_info",  False)
    missing      = parsed.get("missing_fields",   [])

    print(f"[AGENT] Intent    : {intent}")
    print(f"[AGENT] Tool      : {tool_to_call}")
    print(f"[AGENT] NeedsMore : {needs_more}")
    if tool_args:
        print(f"[AGENT] Tool args : {tool_args}")

    # ── Step 4: Handle missing info ───────────────────────────
    if needs_more and missing:
        first_missing = missing[0]
        clarify_msg = get_clarify_message(first_missing, language)
        final_response = patient_resp or clarify_msg
        print(f"[AGENT] Clarify   : missing={missing}")
        return {
            "intent": "clarify",
            "patient_response": final_response,
            "appointment": None,
            "tool_result": None,
            "needs_more_info": True,
            "missing_fields": missing,
        }

    # ── Step 5: Execute tool if needed ───────────────────────
    tool_result = None

    if tool_to_call and tool_to_call not in ("none", "", None):
        tool_result = execute_tool(
            tool_name=tool_to_call,
            tool_args=tool_args,
            patient_id=patient_id,
        )
        print(
            f"[AGENT] Tool result: success={tool_result.get('success')} "
            f"msg='{str(tool_result.get('message', ''))[:80]}'"
        )

        # ── Step 6: Second LLM call — natural response ────────
        tool_prompt = get_tool_result_prompt(
            tool_name=tool_to_call,
            result=tool_result,
            language=language,
        )

        follow_up_messages = messages + [
            {"role": "assistant", "content": raw_response},
            {"role": "user",      "content": tool_prompt},
        ]

        try:
            follow_up_raw = call_llm(
                follow_up_messages,
                language=language,
                patient_id=patient_id
            )
            follow_up_json = extract_json(follow_up_raw)

            if follow_up_json and follow_up_json.get("patient_response"):
                patient_resp = follow_up_json["patient_response"]
                intent = follow_up_json.get("intent", intent)
                print(f"[AGENT] Follow-up : '{patient_resp[:80]}'")
            elif follow_up_raw:
                patient_resp = follow_up_raw
                print(f"[AGENT] Follow-up (plain): '{patient_resp[:80]}'")

        except Exception as e:
            print(f"[AGENT] Follow-up LLM failed: {e}")
            if tool_result.get("success"):
                patient_resp = tool_result.get("message", patient_resp)
            else:
                err_msg = tool_result.get("message", "")
                alts = tool_result.get("alternatives", [])
                patient_resp = err_msg
                if alts:
                    alt_times = ", ".join(
                        f"{a['time_slot']} on {a['date']}" for a in alts[:2]
                    )
                    patient_resp += f" Available: {alt_times}."

    # ── Step 7: Final safety net ──────────────────────────────
    if not patient_resp or not patient_resp.strip():
        if tool_result:
            patient_resp = tool_result.get(
                "message",
                get_fallback(language)["patient_response"]
            )
        else:
            patient_resp = get_fallback(language)["patient_response"]

    # ── Step 8: Update persistent memory ─────────────────────
    try:
        update_language_preference(patient_id, language)
        record_conversation(patient_id, language)

        if tool_result and tool_result.get("success"):
            appt = tool_result.get("appointment")
            if appt and intent in ("book", "booking"):
                record_appointment_booked(
                    patient_id,
                    doctor_name=appt.get("doctor_name", ""),
                    specialty=appt.get("specialty",   ""),
                    hospital=appt.get("hospital",    ""),
                    date_str=appt.get("date",        ""),
                    time_slot=appt.get("time_slot",   ""),
                )
            elif intent in ("cancel", "cancellation"):
                record_appointment_cancelled(patient_id)
            elif intent in ("reschedule", "rescheduling"):
                record_appointment_rescheduled(patient_id)

    except Exception as mem_err:
        print(f"[AGENT] Memory update failed (non-critical): {mem_err}")

    # ── Step 9: Build final result ────────────────────────────
    total_ms = int((time.time() - t_total) * 1000)
    print(f"[AGENT] Total     : {total_ms}ms")
    print(f"[AGENT] Response  : '{patient_resp[:100]}'")
    print(f"[AGENT] ─────────────────────────────────────\n")

    appointment_data = None
    if tool_result and tool_result.get("success"):
        appointment_data = tool_result.get("appointment")

    return {
        "intent": intent,
        "patient_response": patient_resp,
        "appointment": appointment_data,
        "tool_result": tool_result,
        "needs_more_info": needs_more,
    }