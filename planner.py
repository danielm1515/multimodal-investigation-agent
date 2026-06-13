"""
planner.py

The planner decides what the agent should do next based on its current state.
This is what makes the system agentic: the next action depends on state, not on a
single fixed prompt.

For each control_state the planner returns:
    {
        "action":     name of the action to execute in ACT,
        "reason":     human-readable justification (shown in the trace),
        "next_state": the intended next control_state (observe() may redirect it
                      for result-dependent guards such as tool_ok / grounded),
    }

Guards implemented here: files_exist, has_supported_files, modalities_count >= 2,
pending_tools_not_empty, retries < 2.
"""

from typing import Any, Dict


def plan_next_action(state: Dict[str, Any]) -> Dict[str, str]:
    """Decide the next action according to the current agent state."""

    # --- global safety guard: terminate directly to avoid any loop ---
    if state["step_count"] >= state["max_steps"]:
        return {
            "action": "ask_clarification",
            "reason": "Maximum number of steps reached; stopping safely.",
            "next_state": "DONE",
        }

    cs = state["control_state"]

    if cs == "INGRESS":
        if not state["files"]:
            return {"action": "ask_clarification",
                    "reason": "No files were provided (guard files_exist failed).",
                    "next_state": "CLARIFY"}
        return {"action": "create_initial_state",
                "reason": "Files exist; initialize the investigation.",
                "next_state": "DETECT_MODALITIES"}

    if cs == "DETECT_MODALITIES":
        return {"action": "detect_modalities",
                "reason": "Inspect the files to learn which modalities are available.",
                "next_state": "SELECT_TOOLS"}

    if cs == "SELECT_TOOLS":
        # Guard: at least two modalities are required by the assignment.
        if len(state["available_modalities"]) < 2:
            return {"action": "ask_clarification",
                    "reason": "Fewer than two modalities detected (guard modalities_count >= 2 failed).",
                    "next_state": "CLARIFY"}
        return {"action": "choose_tools",
                "reason": "Two or more modalities detected; select the matching tools.",
                "next_state": "PLAN_NEXT_ACTION"}

    if cs == "PLAN_NEXT_ACTION":
        # Core agentic decision: extract more evidence, or move on to validation.
        if state["pending_tools"]:
            nxt = state["pending_tools"][0]
            return {"action": "plan_next_action",
                    "reason": f"Pending tool '{nxt['tool']}' on '{nxt['file']}'; schedule extraction.",
                    "next_state": "ACT"}
        return {"action": "plan_next_action",
                "reason": "No pending tools; all evidence gathered. Proceed to validation.",
                "next_state": "VALIDATE"}

    if cs == "ACT":
        job = state["pending_tools"][0]
        return {"action": "run_tool",
                "reason": f"Execute '{job['tool']}' on '{job['file']}' to extract evidence.",
                "next_state": "OBSERVE"}

    if cs == "OBSERVE":
        return {"action": "update_state",
                "reason": "Observe the raw tool result and update working memory.",
                "next_state": "EXTRACT_EVIDENCE"}

    if cs == "EXTRACT_EVIDENCE":
        return {"action": "record_evidence",
                "reason": "Record the observed result as a normalized evidence item.",
                "next_state": "PLAN_NEXT_ACTION"}

    if cs == "VALIDATE":
        return {"action": "validate_grounding",
                "reason": "Check grounding and that evidence spans at least two modalities.",
                "next_state": "RESPOND"}

    if cs == "ERROR_RECOVERY":
        # Guard: retries < 2 -> retry/fallback and keep going; otherwise clarify.
        if state["retries"] < 2:
            return {"action": "retry_or_fallback",
                    "reason": f"Tool failed; retry/fallback (retries={state['retries']} < 2).",
                    "next_state": "PLAN_NEXT_ACTION"}
        return {"action": "ask_clarification",
                "reason": "Retry limit reached (guard retries < 2 failed).",
                "next_state": "CLARIFY"}

    if cs == "RESPOND":
        return {"action": "render_answer",
                "reason": "Evidence is grounded; render the final answer.",
                "next_state": "DONE"}

    if cs == "CLARIFY":
        return {"action": "ask_clarification",
                "reason": "Evidence is insufficient; ask the user for more information.",
                "next_state": "DONE"}

    return {"action": "ask_clarification",
            "reason": f"Unknown control state: {cs}.",
            "next_state": "CLARIFY"}
