"""
app.py

Entry point for running the Multimodal Investigation Agent.

Usage:
    python app.py                       # uses sample_input.json
    python app.py path/to/input.json    # custom input

Set OPENAI_API_KEY (env var or a local .env file) to run the real OpenAI tools.
There is no mock mode: if the key or the 'openai' package is missing, the program
stops with a clear, actionable error.
"""

import os
import sys
import json

from agent import MultimodalAgent
import tools

# Directory of this file, so .env / sample inputs / outputs resolve regardless
# of the current working directory (e.g. when launched from an IDE run config).
_HERE = os.path.dirname(os.path.abspath(__file__))


def _load_dotenv(path: str = ".env") -> None:
    """Minimal .env loader (no external dependency required)."""
    if not os.path.isabs(path):
        path = os.path.join(_HERE, path)
    if not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
    except OSError:
        pass


def load_sample_input(path: str = "sample_input.json"):
    if not os.path.isabs(path):
        path = os.path.join(_HERE, path)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_run_output(final_state, output_path: str = "outputs/run_example.json"):
    if not os.path.isabs(output_path):
        output_path = os.path.join(_HERE, output_path)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(final_state, f, indent=2, ensure_ascii=False)


def main():
    _load_dotenv()

    input_path = sys.argv[1] if len(sys.argv) > 1 else "sample_input.json"
    sample = load_sample_input(input_path)

    config = tools.load_config()
    # Require a real OpenAI client up front. There is no mock mode: if the SDK
    # or key is missing, this raises a clear, actionable error.
    tools.get_openai_client(config)
    print("Tool mode: REAL OpenAI\n")

    agent = MultimodalAgent(
        user_question=sample["user_question"],
        files=sample["files"],
        max_steps=config.get("max_steps", 14),
        config=config,
    )

    final_state = agent.run()

    _print_trace(final_state)
    save_run_output(final_state)
    print("\nSaved run output to outputs/run_example.json")


def _print_trace(state: dict) -> None:
    SEP = "=" * 70

    print(f"\n{SEP}")
    print("  AGENT TRACE - Multimodal Investigation Agent")
    print(SEP)

    cumulative_tokens = {"prompt": 0, "completion": 0, "total": 0}

    for i, entry in enumerate(state["actions_taken"], start=1):
        st = entry.get("state", "?")
        etype = entry.get("type", "?")
        tok = entry.get("tokens")

        print(f"\n{'-'*70}")
        print(f"  Step {i:>2}  |  State: {st:<22}  |  Event: {etype}")
        print(f"{'-'*70}")

        # modalities detected
        if etype == "modalities_detected":
            print(f"  Modalities found : {entry.get('modalities')}")

        # tools selected
        elif etype == "tools_selected":
            print(f"  Tools selected   : {entry.get('selected_tools')}")

        # evidence from a tool (ACT step — raw result before recording)
        elif etype == "evidence":
            print(f"  Tool             : {entry.get('tool')}")
            print(f"  Modality         : {entry.get('modality')}")
            print(f"  Confidence       : {entry.get('confidence')}")

        # evidence recorded (EXTRACT_EVIDENCE step — full detail)
        elif etype == "evidence_extracted":
            ev = entry.get("evidence", {})
            print(f"  Tool             : {entry.get('tool', ev.get('tool', '?'))}")
            print(f"  Modality         : {ev.get('modality')}")
            print(f"  Source           : {ev.get('source')}")
            content = ev.get("content", "")
            # print first 300 chars so it stays readable
            preview = content[:300] + ("…" if len(content) > 300 else "")
            print(f"  Content preview  :\n    {preview.replace(chr(10), chr(10)+'    ')}")

        # validation
        elif etype == "validation_result":
            print(f"  Grounded         : {entry.get('grounded')}")
            print(f"  Confidence       : {entry.get('confidence')}")
            print(f"  Used modalities  : {entry.get('used_modalities')}")

        # final answer
        elif etype == "final_answer":
            answer = entry.get("answer", "")
            preview = answer[:500] + ("…" if len(answer) > 500 else "")
            print(f"  Answer preview   :\n    {preview.replace(chr(10), chr(10)+'    ')}")

        # token usage for this step
        if tok and tok.get("total", 0) > 0:
            cumulative_tokens["prompt"] += tok["prompt"]
            cumulative_tokens["completion"] += tok["completion"]
            cumulative_tokens["total"] += tok["total"]
            print(f"\n  {'.'*40}")
            print(f"  Token usage this step:")
            print(f"    prompt     : {tok['prompt']:>6}")
            print(f"    completion : {tok['completion']:>6}")
            print(f"    total      : {tok['total']:>6}")
            print(f"  Cumulative tokens so far : {cumulative_tokens['total']}")
        elif tok and tok.get("total", 0) == 0 and etype in ("evidence_extracted", "final_answer"):
            print(f"\n  [mock - no real API call, 0 tokens used]")

    grand = state.get("total_tokens", cumulative_tokens)
    print(f"\n{SEP}")
    print("  TOTAL TOKEN USAGE (all OpenAI calls combined)")
    print(f"{'-'*70}")
    print(f"    prompt tokens     : {grand.get('prompt', 0):>6}")
    print(f"    completion tokens : {grand.get('completion', 0):>6}")
    print(f"    total tokens      : {grand.get('total', 0):>6}")
    print(SEP)

    print(f"\n{'-'*70}")
    print("  VALIDATION RESULT")
    print(f"{'-'*70}")
    v = state.get("validation", {})
    print(f"  Grounded         : {v.get('grounded')}")
    print(f"  Confidence       : {v.get('confidence')}")
    print(f"  Used modalities  : {v.get('used_modalities')}")
    missing = v.get("missing_info", [])
    if missing:
        print(f"  Missing info     : {missing}")

    print(f"\n{'-'*70}")
    print("  FINAL ANSWER")
    print(f"{'-'*70}")
    print(state.get("final_answer", ""))


if __name__ == "__main__":
    main()
