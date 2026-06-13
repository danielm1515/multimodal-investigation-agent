"""
agent.py

The MultimodalAgent drives an explicit finite state machine through the loop:

    Sense  -> INGRESS / DETECT_MODALITIES / SELECT_TOOLS / EXTRACT_EVIDENCE
    Plan   -> PLAN_NEXT_ACTION
    Act    -> ACT
    Observe-> OBSERVE
    Validate -> VALIDATE
    Respond / Retry / Clarify -> RESPOND / ERROR_RECOVERY / CLARIFY
    DONE

Every iteration is plan() -> act() -> observe(). observe() updates the external
state, appends a tagged entry to the trace, and sets the next control_state.
"""

from typing import Any, Dict, List

from state import create_initial_state
from planner import plan_next_action
from validator import validate_evidence

import tools


class MultimodalAgent:
    """A small multimodal investigation agent based on an external state machine."""

    def __init__(self, user_question: str, files: List[str], max_steps: int = 30,
                 config: Dict[str, Any] = None):
        self.state = create_initial_state(user_question, files, max_steps=max_steps)
        self.config = config or tools.load_config()
        self.client = tools.get_openai_client(self.config)
        self.total_tokens = {"prompt": 0, "completion": 0, "total": 0}

    # ------------------------------------------------------------------ #
    # Main loop
    # ------------------------------------------------------------------ #

    def run(self) -> Dict[str, Any]:
        """Run the agent loop until the DONE state is reached."""
        while self.state["control_state"] != "DONE":
            current_state = self.state["control_state"]
            decision = self.plan()
            result = self.act(decision)
            self.observe(current_state, decision, result)
        self.state["total_tokens"] = self.total_tokens
        return self.state

    def plan(self) -> Dict[str, str]:
        """PLAN: ask the planner what to do in the current control_state."""
        decision = plan_next_action(self.state)
        self.state["next_action"] = decision
        return decision

    def act(self, decision: Dict[str, str]) -> Dict[str, Any]:
        """ACT: execute the chosen action and return its raw result."""
        action = decision["action"]

        if action == "create_initial_state":
            return {"type": "ingress_ok"}

        if action == "detect_modalities":
            return tools.detect_modalities(self.state["files"])

        if action == "choose_tools":
            selected = tools.select_tools_for_modalities(self.state["available_modalities"])
            selected["jobs"] = tools.build_tool_jobs(self.state["files"])
            return selected

        if action == "plan_next_action":
            return {"type": "planned"}

        if action == "run_tool":
            job = self.state["pending_tools"][0]
            return tools.run_tool_job(job, self.state["user_question"], self.config, self.client)

        if action == "update_state":
            return {"type": "observed", "observed": self.state["last_tool_result"]}

        if action == "record_evidence":
            # The raw tool result (with its tokens) was already counted in ACT;
            # here we only record the normalized evidence item. We do NOT re-expose
            # tokens at the top level, so they are never double-counted in the trace.
            return {"type": "evidence_extracted", "evidence": self.state["last_tool_result"]}

        if action == "validate_grounding":
            return validate_evidence(
                self.state["evidence"],
                minimum_modalities=self.config.get("minimum_modalities_required", 2),
                minimum_confidence=self.config.get("minimum_confidence", 0.0),
            )

        if action == "retry_or_fallback":
            return self._retry_or_fallback()

        if action == "render_answer":
            return tools.generate_answer(self.state, self.config, self.client)

        if action == "ask_clarification":
            return {
                "type": "clarification",
                "message": self._clarification_message(),
            }

        return {"type": "error", "message": f"Unknown action: {action}"}

    def observe(self, acted_state: str, decision: Dict[str, str], result: Dict[str, Any]) -> None:
        """OBSERVE: update state, append the trace entry, set the next control_state."""
        self.state["step_count"] += 1
        rtype = result.get("type")

        # default next state proposed by the planner
        next_state = decision["next_state"]

        if rtype == "modalities_detected":
            self.state["available_modalities"] = result["modalities"]

        elif rtype == "tools_selected":
            self.state["selected_tools"] = result["selected_tools"]
            self.state["pending_tools"] = result["jobs"]

        elif rtype == "evidence":  # a tool succeeded during ACT
            self.state["last_tool_result"] = result

        elif rtype == "tool_error":  # a tool failed during ACT -> recover
            self.state["last_tool_result"] = result
            self.state["errors"].append(result)
            next_state = "ERROR_RECOVERY"

        elif rtype == "evidence_extracted":
            self.state["evidence"].append(result["evidence"])
            if self.state["pending_tools"]:
                self.state["pending_tools"].pop(0)  # this job is done

        elif rtype == "recovery":
            # On giving up a source we drop it (no mock evidence is fabricated).
            if result.get("mode") == "fallback":
                if self.state["pending_tools"]:
                    self.state["pending_tools"].pop(0)

        elif rtype == "validation_result":
            self.state["validation"] = {
                "grounded": result["grounded"],
                "confidence": result["confidence"],
                "used_modalities": result["used_modalities"],
                "missing_info": result["missing_info"],
            }
            if not result["grounded"]:
                next_state = "CLARIFY"

        elif rtype == "final_answer":
            self.state["final_answer"] = result["answer"]

        elif rtype == "clarification":
            self.state["final_answer"] = result["message"]

        elif rtype == "error":
            self.state["errors"].append(result)
            self.state["final_answer"] = result["message"]
            next_state = "DONE"

        # record the trace entry, tagged with the state it was produced in
        self._trace(acted_state, result)

        self.state["control_state"] = next_state

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _retry_or_fallback(self) -> Dict[str, Any]:
        """
        Handle a failed tool: retry while retries < 2, otherwise drop this source
        and continue (no mock evidence is fabricated).
        """
        self.state["retries"] += 1
        job = self.state["pending_tools"][0] if self.state["pending_tools"] else None

        if self.state["retries"] < 2 or job is None:
            return {
                "type": "recovery",
                "mode": "retry",
                "message": f"Retrying failed tool (attempt {self.state['retries']}).",
            }

        return {
            "type": "recovery",
            "mode": "fallback",
            "message": "Retry limit reached; dropping this source (no mock evidence).",
        }

    def _clarification_message(self) -> str:
        missing = self.state["validation"].get("missing_info", [])
        detail = (" Details: " + "; ".join(missing)) if missing else ""
        return (
            "I cannot produce a grounded answer yet. I need at least two supported "
            "modalities (for example image + document)." + detail
        )

    def _trace(self, acted_state: str, result: Dict[str, Any]) -> None:
        """Append a compact, tagged trace entry mirroring the assignment example."""
        entry = {"state": acted_state, "type": result.get("type")}
        for key in ("modalities", "selected_tools", "grounded", "confidence",
                    "used_modalities", "tool", "modality", "mode", "message"):
            if key in result:
                entry[key] = result[key]
        if result.get("type") == "evidence_extracted":
            ev = result["evidence"]
            entry["evidence"] = {"tool": ev.get("tool"), "modality": ev.get("modality"),
                                 "source": ev.get("source"), "content": ev.get("content")}
        if result.get("type") == "final_answer":
            entry["answer"] = result["answer"]

        # track token usage from any result that carries it
        tok = result.get("tokens")
        if tok:
            entry["tokens"] = tok
            self.total_tokens["prompt"] += tok.get("prompt", 0)
            self.total_tokens["completion"] += tok.get("completion", 0)
            self.total_tokens["total"] += tok.get("total", 0)

        self.state["actions_taken"].append(entry)
