"""
planner.py

The planner decides what the agent should do next based on its current state.
This is what makes the system agentic: the next action depends on state.
"""

from typing import Any, Dict


def plan_next_action(state: Dict[str, Any]) -> Dict[str, str]:
    """
    Decide the next action according to the current agent state.
    """
    if state["step_count"] >= state["max_steps"]:
        return {
            "action": "stop_with_error",
            "reason": "Maximum number of steps reached"
        }

    control_state = state["control_state"]

    if control_state == "INGRESS":
        return {
            "action": "detect_modalities",
            "reason": "The agent needs to understand which input types were provided."
        }

    if control_state == "MODALITIES_DETECTED":
        if len(state["available_modalities"]) < 2:
            return {
                "action": "ask_clarification",
                "reason": "The assignment requires at least two modalities."
            }

        return {
            "action": "select_tools",
            "reason": "The agent should select tools according to the detected modalities."
        }

    if control_state == "TOOLS_SELECTED":
        return {
            "action": "extract_evidence",
            "reason": "The agent has selected tools and now needs to extract evidence."
        }

    if control_state == "EVIDENCE_EXTRACTED":
        return {
            "action": "validate_evidence",
            "reason": "The agent needs to check if the evidence is grounded and sufficient."
        }

    if control_state == "VALIDATED":
        if state["validation"]["grounded"]:
            return {
                "action": "generate_answer",
                "reason": "The evidence is sufficient for a grounded answer."
            }

        return {
            "action": "ask_clarification",
            "reason": "The evidence is not sufficient."
        }

    if control_state == "CLARIFY":
        return {
            "action": "ask_clarification",
            "reason": "The agent needs more user input."
        }

    if control_state == "ERROR":
        return {
            "action": "stop_with_error",
            "reason": "The agent encountered an error."
        }

    return {
        "action": "stop_with_error",
        "reason": f"Unknown control state: {control_state}"
    }
