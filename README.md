# Multimodal Investigation Agent

A small but real multimodal AI agent built around an **external state machine** —
not a `Upload → Model → Answer` pipeline. It runs the loop:

```
Sense → Plan → Act → Observe → Update State → Validate → Respond / Retry / Clarify
```

## 1. Agent name

**Multimodal Investigation Agent**

## 2. Purpose

The agent receives a small investigation case (a user question plus files from at
least two modalities), figures out which inputs are available, selects matching
tools, extracts evidence from each source, fuses the evidence, validates that the
answer is grounded in **at least two modalities**, and only then returns a final
answer with a confidence score — otherwise it asks for clarification.

## 3. Modalities accepted

| Modality | Extensions | Tool |
|---|---|---|
| `image` | `.png` `.jpg` `.jpeg` | `analyze_image` |
| `document` | `.txt` `.pdf` | `analyze_document` |
| `audio` | `.mp3` `.wav` `.m4a` | `transcribe_audio` (mock) |

The reference example uses **image + document**.

## 4. Tools (more than the required three)

1. **`analyze_image`** — OpenAI vision (`gpt-4o`): sends the image as base64 and
   extracts factual visual evidence. Degrades to a mock if OpenAI is unavailable.
2. **`analyze_document`** — reads real text (`.txt` directly, `.pdf` via PyMuPDF)
   and uses OpenAI (`gpt-4o-mini`) to extract question-relevant evidence.
3. **`transcribe_audio`** — mock transcription (kept to satisfy ≥3 tools; not used
   in the demo).
4. **`generate_answer`** — OpenAI synthesis of the final answer from the evidence
   **only** (anti-hallucination), with a deterministic fallback.
5. Helpers: `detect_modalities`, `select_tools_for_modalities`, `validate_evidence`.

All OpenAI calls read the key from the `OPENAI_API_KEY` environment variable and
fall back to mock/degraded output on any failure, so the architecture always runs.

## 5. States (the 12 required FSM states)

`INGRESS → DETECT_MODALITIES → SELECT_TOOLS → PLAN_NEXT_ACTION → ACT → OBSERVE →
EXTRACT_EVIDENCE → VALIDATE → RESPOND / CLARIFY / ERROR_RECOVERY → DONE`

The per-source extraction runs as a loop:
`PLAN_NEXT_ACTION → ACT → OBSERVE → EXTRACT_EVIDENCE → PLAN_NEXT_ACTION`
(once per file), then continues to `VALIDATE`. The full transition table (state,
action, guard, next) lives in [`state_machine.json`](state_machine.json).

## 6. How the planner decides the next action

[`planner.py`](planner.py) maps the current `control_state` to an action, a reason,
and an intended next state, evaluating explicit guards:

- **INGRESS** → `create_initial_state` if `files_exist`, else `CLARIFY`.
- **DETECT_MODALITIES** → `detect_modalities`.
- **SELECT_TOOLS** → guard `modalities_count >= 2`; otherwise `CLARIFY`.
- **PLAN_NEXT_ACTION** → if `pending_tools` is non-empty, schedule the next tool
  (`ACT`); otherwise proceed to `VALIDATE`.
- **ACT / OBSERVE / EXTRACT_EVIDENCE** → run one tool, observe its result, record
  the evidence.
- **VALIDATE** → `RESPOND` if grounded, else `CLARIFY`.
- **ERROR_RECOVERY** → guard `retries < 2`: retry/fallback, else `CLARIFY`.

`observe()` finalizes result-dependent branches (a failed tool → `ERROR_RECOVERY`,
ungrounded evidence → `CLARIFY`). A global `max_steps` guard guarantees termination.

## 7. How validation works

[`validator.py`](validator.py) computes the distinct `used_modalities`, the average
evidence `confidence`, and marks the answer **grounded** only when there are
≥ 2 modalities **and** the average confidence clears `minimum_confidence`
(from [`config.json`](config.json)). If not grounded, it returns `missing_info`
and the agent routes to `CLARIFY` instead of answering.

## 8. Example input

[`sample_input.json`](sample_input.json):

```json
{
  "user_question": "What is the main problem shown in the files, and what should we do next?",
  "files": ["examples/dashboard.png", "examples/context.txt"]
}
```

## 9. Example output

```
Final Answer:
... grounded answer synthesized from the image + document evidence ...
Confidence: 0.72
Used modalities: ['document', 'image']

Agent Trace:
Step 1  [INGRESS]:          {'type': 'ingress_ok'}
Step 2  [DETECT_MODALITIES]:{'type': 'modalities_detected', 'modalities': ['document', 'image']}
Step 3  [SELECT_TOOLS]:     {'type': 'tools_selected', ...}
Step 4  [PLAN_NEXT_ACTION]: {'type': 'planned'}
Step 5  [ACT]:              {'type': 'evidence', 'tool': 'analyze_image', ...}
Step 6  [OBSERVE]:          {'type': 'observed'}
Step 7  [EXTRACT_EVIDENCE]: {'type': 'evidence_extracted', ...}
...
Step 13 [VALIDATE]:         {'type': 'validation_result', 'grounded': True, 'confidence': 0.72, ...}
Step 14 [RESPOND]:          {'type': 'final_answer'}
```

The full state + trace is saved to
[`outputs/run_example.json`](outputs/run_example.json).

## 10. Known limitations

- Audio analysis is mock only.
- PDF support depends on PyMuPDF being installed.
- `confidence` is a heuristic (average of per-evidence scores), not a calibrated
  probability.
- Real OpenAI calls cost money and require network access; the mock fallback keeps
  the agent runnable without a key.

## 11. How to run

```bash
# (optional) install real-tool dependencies
pip install -r requirements.txt

# (optional) enable real OpenAI tools
cp .env.example .env        # then put your key in .env, OR:
export OPENAI_API_KEY="sk-..."     # Windows PowerShell: $env:OPENAI_API_KEY="sk-..."

# run the default example
python app.py

# run a custom case
python app.py path/to/input.json
```

Without `OPENAI_API_KEY`, the agent runs end-to-end in mock mode. With the key set,
`analyze_image` / `analyze_document` / `generate_answer` use OpenAI.

## Project structure

```text
multimodal_agent_project/
├── app.py              # entry point: load input, run agent, print trace, save output
├── agent.py            # MultimodalAgent: run/plan/act/observe FSM loop
├── state.py            # external state object (working memory)
├── planner.py          # decides the next action per control_state (with guards)
├── tools.py            # tools: OpenAI image/document/answer + mocks + routing
├── validator.py        # grounding + confidence validation
├── prompts.py          # prompt templates used by the real tools
├── config.json         # models, thresholds, feature flags
├── state_machine.json  # declarative 12-state transition table
├── sample_input.json   # example input
├── requirements.txt    # openai, PyMuPDF
├── .env.example        # template for OPENAI_API_KEY
├── examples/           # dashboard.png + context.txt (two modalities)
├── outputs/            # run_example.json (final state + trace)
└── README.md
```
