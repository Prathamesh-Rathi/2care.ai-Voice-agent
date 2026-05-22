# ============================================================
# agent/tools/tool_definitions.py
# Tool schemas + executor
# The LLM picks a tool; this file runs it.
# ============================================================

import sys
import os

sys.path.append(
    os.path.dirname(
        os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))
        )
    )
)

from backend.controllers.appointment_controller import (
    check_availability,
    book_appointment,
    cancel_appointment_ctrl,
    reschedule_appointment_ctrl,
    get_patient_appointments,
)

# ============================================================
# Tool Schemas (sent to LLM as context)
# ============================================================

TOOL_SCHEMAS = {

    "check_availability": {
        "name": "check_availability",
        "description": (
            "Check available appointment slots "
            "for a doctor or specialty on a date."
        ),
        "parameters": {
            "specialty": (
                "string — doctor specialty "
                "e.g. cardiologist"
            ),
            "doctor_id": (
                "int — specific doctor ID "
                "(optional)"
            ),
            "date": (
                "string — YYYY-MM-DD or "
                "'today' or 'tomorrow'"
            ),
        },
        "required": ["specialty"]
    },

    "book_appointment": {
        "name": "book_appointment",
        "description": (
            "Book an appointment for the patient."
        ),
        "parameters": {
            "specialty": (
                "string — doctor specialty"
            ),
            "date": (
                "string — YYYY-MM-DD or "
                "'today' or 'tomorrow'"
            ),
            "time_slot": (
                "string — HH:MM format "
                "(optional, picks first free "
                "if omitted)"
            ),
            "notes": (
                "string — optional notes"
            ),
        },
        "required": [
            "specialty",
            "date"
        ]
    },

    "cancel_appointment": {
        "name": "cancel_appointment",
        "description": (
            "Cancel a patient's "
            "existing appointment."
        ),
        "parameters": {
            "appointment_id": (
                "int — the appointment ID "
                "to cancel"
            ),
        },
        "required": ["appointment_id"]
    },

    "reschedule_appointment": {
        "name": "reschedule_appointment",
        "description": (
            "Move an existing appointment "
            "to a new date/time."
        ),
        "parameters": {
            "appointment_id": (
                "int — the appointment "
                "to reschedule"
            ),
            "new_date": (
                "string — new date "
                "YYYY-MM-DD or 'tomorrow'"
            ),
            "new_time_slot": (
                "string — new time HH:MM "
                "(optional)"
            ),
        },
        "required": [
            "appointment_id",
            "new_date"
        ]
    },

    "get_patient_appointments": {
        "name": "get_patient_appointments",
        "description": (
            "List all upcoming confirmed "
            "appointments for the patient."
        ),
        "parameters": {},
        "required": []
    },
}


# ============================================================
# Tool Description Formatter
# ============================================================

def get_tools_description() -> str:
    """
    Returns tool schemas as a formatted string
    for the system prompt.
    """

    lines = ["\nAVAILABLE TOOLS:\n"]

    for name, schema in TOOL_SCHEMAS.items():

        lines.append(f"Tool: {name}")

        lines.append(
            f"  Description: {schema['description']}"
        )

        lines.append(
            f"  Required: {schema['required']}"
        )

        params = schema.get("parameters", {})

        if params:
            for k, v in params.items():
                lines.append(f"    - {k}: {v}")

        lines.append("")

    return "\n".join(lines)


# ============================================================
# Tool Executor
# ============================================================

def execute_tool(
    tool_name: str,
    tool_args: dict,
    patient_id: int
) -> dict:
    """
    Runs the tool requested by the LLM.

    Always returns:
    {
        "success": bool,
        "message": str
    }
    """

    print(
        f"[TOOL] Executing: "
        f"{tool_name} | args={tool_args}"
    )

    try:

        # ====================================================
        # Check Availability
        # ====================================================

        if tool_name == "check_availability":

            return check_availability(
                specialty=tool_args.get(
                    "specialty"
                ),
                doctor_id=tool_args.get(
                    "doctor_id"
                ),
                date_str=tool_args.get(
                    "date"
                ),
            )

        # ====================================================
        # Book Appointment
        # ====================================================

        elif tool_name == "book_appointment":

            from scheduler.appointment_engine.scheduler import (
                smart_book_appointment
            )

            return smart_book_appointment(
                patient_id=patient_id,

                specialty=tool_args.get(
                    "specialty",
                    "general physician"
                ),

                date_str=tool_args.get(
                    "date",
                    "tomorrow"
                ),

                time_str=tool_args.get(
                    "time_slot"
                ),

                doctor_id=tool_args.get(
                    "doctor_id"
                ),

                notes=tool_args.get(
                    "notes",
                    ""
                ),
            )

        # ====================================================
        # Cancel Appointment
        # ====================================================

        elif tool_name == "cancel_appointment":

            appt_id = tool_args.get(
                "appointment_id"
            )

            if not appt_id:

                return {
                    "success": False,
                    "message": (
                        "appointment_id "
                        "is required."
                    )
                }

            return cancel_appointment_ctrl(
                appointment_id=int(appt_id),
                patient_id=patient_id,
            )

        # ====================================================
        # Reschedule Appointment
        # ====================================================

        elif tool_name == "reschedule_appointment":

            appt_id = tool_args.get(
                "appointment_id"
            )

            if not appt_id:

                return {
                    "success": False,
                    "message": (
                        "appointment_id "
                        "is required."
                    )
                }

            return reschedule_appointment_ctrl(
                appointment_id=int(appt_id),

                patient_id=patient_id,

                new_date_str=tool_args.get(
                    "new_date"
                ),

                new_time_slot=tool_args.get(
                    "new_time_slot"
                ),
            )

        # ====================================================
        # Get Patient Appointments
        # ====================================================

        elif tool_name == "get_patient_appointments":

            return get_patient_appointments(
                patient_id=patient_id
            )

        # ====================================================
        # Unknown Tool
        # ====================================================

        else:

            return {
                "success": False,
                "message": (
                    f"Unknown tool: "
                    f"{tool_name}"
                )
            }

    # ========================================================
    # Global Tool Exception Handling
    # ========================================================

    except Exception as e:

        print(
            f"[TOOL] Error in "
            f"{tool_name}: {e}"
        )

        return {
            "success": False,
            "message": (
                f"Tool error: {str(e)}"
            )
        }