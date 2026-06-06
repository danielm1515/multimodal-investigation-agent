"""
app.py

Main entry point for running the Multimodal Investigation Agent.
"""

import json
import os

from agent import MultimodalAgent


def load_sample_input(path: str = "sample_input.json"):
    """
    Load sample input from JSON.
    """
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_run_output(final_state, output_path: str = "outputs/run_example.json"):
    """
    Save the final state and trace to a JSON file.
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(final_state, f, indent=2, ensure_ascii=False)


def main():
    sample = load_sample_input()

    user_question = sample["user_question"]
    files = sample["files"]

    agent = MultimodalAgent(user_question=user_question, files=files)

    final_state = agent.run()

    print("Final Answer:")
    print(final_state["final_answer"])

    print("\nAgent Trace:")
    for i, action in enumerate(final_state["actions_taken"], start=1):
        print(f"\nStep {i}:")
        print(action)

    print("\nValidation:")
    print(final_state["validation"])

    save_run_output(final_state)
    print("\nSaved run output to outputs/run_example.json")


if __name__ == "__main__":
    main()
