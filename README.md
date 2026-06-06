# Multimodal Investigation Agent

This is a starter project for the assignment:
**Build a Multimodal AI Agent: Sense → Plan → Act → Observe**

The goal is to build a small but real agent, not a chatbot and not a simple pipeline.

## What the agent does

The agent receives:

1. A user question
2. At least two input files from different modalities, for example:
   - image
   - document / text / PDF
   - audio

The agent then:

1. Creates an external state
2. Detects available modalities
3. Selects tools
4. Extracts evidence
5. Validates grounding
6. Generates a final answer or asks for clarification
7. Saves a trace of its actions

## Project structure

```text
multimodal_agent_project/
│
├── app.py
├── agent.py
├── state.py
├── planner.py
├── tools.py
├── validator.py
├── prompts.py
├── config.json
├── state_machine.json
├── sample_input.json
├── examples/
│   └── context.txt
├── outputs/
│   └── run_example.json
└── README.md
```

## How to run

```bash
python app.py
```

The current implementation uses mock tools so the architecture works without external APIs.

Students can replace the mock tools with real models:

- Vision: Qwen2-VL, LLaVA, GPT-4o, Claude Vision
- Audio: Whisper, Qwen2-Audio
- Document/PDF: PyMuPDF + LLM
- Omni: Qwen2.5-Omni, GPT-4o/Omni

## Minimum requirements

A valid project must include:

1. `MultimodalAgent` class
2. `run()`, `plan()`, `act()`, `observe()` methods
3. External state
4. At least three tools
5. At least two modalities
6. Validation before final answer
7. Agent trace
8. Example run
