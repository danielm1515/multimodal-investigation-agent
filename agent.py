"""
agent.py

Main MultimodalAgent implementation.

This file contains the agent loop:
run -> plan -> act -> observe -> update state
"""

from typing import Any, Dict, List

from state import create_initial_state
from planner import plan_next_action
from validator import validate_evidence

from tools import (
    detect_modalities,
    select_tools_for_modalities,
    analyze_image,
    analyze_document,
    transcribe_audio,
    IMAGE_EXTENSIONS,
    DOCUMENT_EXTENSIONS,
    AUDIO_EXTENSIONS
)


class MultimodalAgent:
    """
    A simple multimodal AI agent based on an external state machine.

    Required methods:
    - run()
    - plan()
    - act()
    - observe()
    """

    def __init__(self, user_question: str, files: List[str], max_steps: int = 8):
        self.state = create_initial_state(user_question, files, max_steps=max_steps)

    def run(self) -> Dict[str, Any]:
        """
        Run the agent loop until DONE.
        """
        while self.state["control_state"] != "DONE":
            decision = self.plan()
            result = self.act(decision)
            self.observe(result)

        return self.state

    def plan(self) -> Dict[str, str]:
        """
        Decide the next action.
        """
        decision = plan_next_action(self.state)
        self.state["next_action"] = decision
        return decision

    def act(self, decision: Dict[str, str]) -> Dict[str, Any]:
        """
        Execute the selected action.
        """
        action = decision["action"]

        if action == "detect_modalities":
            return detect_modalities(self.state["files"])

        if action == "select_tools":
            return select_tools_for_modalities(self.state["available_modalities"])

        if action == "extract_evidence":
            return self.extract_all_evidence()

        if action == "validate_evidence":
            return validate_evidence(self.state["evidence"])

        if action == "generate_answer":
            return self.generate_answer()

        if action == "ask_clarification":
            return {
                "type": "clarification",
                "message": (
                    "I need more information or another modality to answer reliably. "
                    "Please provide at least two supported modalities, such as image + text."
                )
            }

        if action == "stop_with_error":
            return {
                "type": "error",
                "message": decision.get("reason", "The agent stopped with an error.")
            }

        return {
            "type": "error",
            "message": f"Unknown action: {action}"
        }

    def extract_all_evidence(self) -> Dict[str, Any]:
        """
        Run the appropriate tool for each file.
        """
        evidence = []

        for file_path in self.state["files"]:
            lowered = file_path.lower()

            if lowered.endswith(IMAGE_EXTENSIONS):
                evidence.append(analyze_image(file_path))

            elif lowered.endswith(DOCUMENT_EXTENSIONS):
                evidence.append(analyze_document(file_path))

            elif lowered.endswith(AUDIO_EXTENSIONS):
                evidence.append(transcribe_audio(file_path))

        return {
            "type": "evidence_extracted",
            "evidence": evidence
        }

    def generate_answer(self) -> Dict[str, Any]:
        """
        Generate a final answer from the extracted evidence.
        """
        evidence_text = "\n".join([
            f"- [{item['modality']}] {item['content']}"
            for item in self.state["evidence"]
        ])

        confidence = self.state["validation"]["confidence"]
        used_modalities = self.state["validation"]["used_modalities"]

        answer = f"""Based on the available multimodal evidence, here is the answer:

User question:
{self.state["user_question"]}

Evidence used:
{evidence_text}

Conclusion:
The agent found evidence from multiple modalities and generated a grounded answer.
In a real implementation, this step should be performed by an LLM using only the evidence above.

Recommended next step:
Replace the mock tools with real model calls and improve the final reasoning prompt.

Confidence:
{confidence}

Used modalities:
{used_modalities}
"""

        return {
            "type": "final_answer",
            "answer": answer
        }

    def observe(self, result: Dict[str, Any]) -> None:
        """
        Observe the action result and update the external state.
        """
        self.state["step_count"] += 1
        self.state["actions_taken"].append(result)

        result_type = result.get("type")

        if result_type == "modalities_detected":
            self.state["available_modalities"] = result["modalities"]
            self.state["control_state"] = "MODALITIES_DETECTED"

        elif result_type == "tools_selected":
            self.state["selected_tools"] = result["selected_tools"]
            self.state["control_state"] = "TOOLS_SELECTED"

        elif result_type == "evidence_extracted":
            self.state["evidence"] = result["evidence"]
            self.state["control_state"] = "EVIDENCE_EXTRACTED"

        elif result_type == "validation_result":
            self.state["validation"] = {
                "grounded": result["grounded"],
                "confidence": result["confidence"],
                "used_modalities": result["used_modalities"],
                "missing_info": result["missing_info"]
            }
            self.state["control_state"] = "VALIDATED"

        elif result_type == "final_answer":
            self.state["final_answer"] = result["answer"]
            self.state["control_state"] = "DONE"

        elif result_type == "clarification":
            self.state["final_answer"] = result["message"]
            self.state["control_state"] = "DONE"

        elif result_type == "error":
            self.state["errors"].append(result)
            self.state["final_answer"] = result["message"]
            self.state["control_state"] = "DONE"

        else:
            self.state["errors"].append({
                "type": "error",
                "message": f"Unknown result type: {result_type}"
            })
            self.state["final_answer"] = "The agent failed because it received an unknown result type."
            self.state["control_state"] = "DONE"
