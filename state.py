"""
state.py

Creates the external state object for the agent.
The state is the working memory of the agent (NOT a single prompt).
It is updated after every action by the agent's observe() step.
"""

from typing import Any, Dict, List


def create_initial_state(user_question: str, files: List[str], max_steps: int = 30) -> Dict[str, Any]:
    """
    Create the initial external state for the agent.

    Args:
        user_question: The question or task provided by the user.
        files: List of file paths supplied for the investigation.
        max_steps: Safety limit for the agent loop (prevents infinite loops).

    Returns:
        A dictionary representing the initial agent state.
    """
    return {
        # --- Goal (explicit task object) ---
        "goal": "Answer the user's question using grounded multimodal evidence",
        "success_criteria": [
            "Use evidence from at least two modalities",
            "Return an answer grounded only in the extracted evidence",
            "Return a confidence score",
            "Ask for clarification if evidence is insufficient",
        ],

        # --- Inputs ---
        "user_question": user_question,
        "files": files,

        # --- Finite state machine ---
        "control_state": "INGRESS",

        # --- Working memory, filled in as the agent runs ---
        "available_modalities": [],
        "selected_tools": [],
        "pending_tools": [],      # queue of (tool, file) jobs still to execute
        "evidence": [],           # collected evidence items
        "last_tool_result": None, # raw result of the most recent ACT
        "next_action": None,

        # --- Validation result ---
        "validation": {
            "grounded": False,
            "confidence": 0.0,
            "used_modalities": [],
            "missing_info": [],
        },

        # --- Output ---
        "final_answer": None,

        # --- Bookkeeping / trace ---
        "actions_taken": [],   # the agent trace: one tagged entry per step
        "errors": [],
        "retries": 0,
        "step_count": 0,
        "max_steps": max_steps,
    }
