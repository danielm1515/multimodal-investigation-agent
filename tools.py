"""
tools.py

Tools the agent can use. There are more than three tools, satisfying the
"at least three tools" requirement:

    1. analyze_image      -> OpenAI vision (gpt-4o)
    2. analyze_document   -> OpenAI text (gpt-4o-mini) over .txt / .pdf
    3. transcribe_audio   -> OpenAI Whisper (whisper-1)
    4. generate_answer    -> OpenAI text synthesis from evidence only
    plus helpers: detect_modalities, select_tools_for_modalities, build_tool_jobs

All model calls go through OpenAI. The API key is read from the OPENAI_API_KEY
environment variable (never hard-coded). There is no mock fallback: if the key or
the 'openai' package is missing, get_openai_client() raises a clear, actionable
error instead of silently degrading.
"""

import os
import json
import base64
from typing import Any, Dict, List, Optional

from prompts import (
    IMAGE_ANALYSIS_PROMPT,
    DOCUMENT_ANALYSIS_PROMPT,
    FINAL_ANSWER_PROMPT,
)


IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg")
DOCUMENT_EXTENSIONS = (".txt", ".pdf")
AUDIO_EXTENSIONS = (".mp3", ".wav", ".m4a")

# Directory of this file, so config/.env resolve no matter what the current
# working directory is (e.g. when launched from a PyCharm/VSCode run config).
_HERE = os.path.dirname(os.path.abspath(__file__))


# --------------------------------------------------------------------------- #
# Configuration / OpenAI client helpers
# --------------------------------------------------------------------------- #

def load_config(path: str = "config.json") -> Dict[str, Any]:
    """Load the agent configuration (models, flags). Falls back to defaults."""
    defaults = {
        "use_real_tools": True,
        "vision_model": "gpt-4o",
        "text_model": "gpt-4o-mini",
        "minimum_modalities_required": 2,
        "minimum_confidence": 0.5,
    }
    # Resolve relative paths against this file's directory, not the cwd.
    if not os.path.isabs(path):
        path = os.path.join(_HERE, path)
    try:
        with open(path, "r", encoding="utf-8") as f:
            defaults.update(json.load(f))
    except (OSError, json.JSONDecodeError):
        pass
    return defaults


def get_openai_client(config: Optional[Dict[str, Any]] = None):
    """
    Return a real OpenAI client. There is no mock fallback: if the client
    cannot be created, a clear exception is raised explaining how to fix it.

    The key is taken from the OPENAI_API_KEY environment variable.
    """
    config = config or load_config()

    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Put it in the .env file (auto-loaded by "
            "app.py) or export it in your environment. If you launch from an IDE, "
            "make sure the working directory is the project folder so .env is found."
        )

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise ModuleNotFoundError(
            "The 'openai' module is not installed. Please install it: "
            "pip install openai"
        ) from exc

    return OpenAI()


# --------------------------------------------------------------------------- #
# Modality / tool routing helpers (pure code)
# --------------------------------------------------------------------------- #

def detect_modalities(files: List[str]) -> Dict[str, Any]:
    """Detect the modalities available in the provided files."""
    modalities = []
    for file_path in files:
        lowered = file_path.lower()
        if lowered.endswith(IMAGE_EXTENSIONS):
            modalities.append("image")
        elif lowered.endswith(DOCUMENT_EXTENSIONS):
            modalities.append("document")
        elif lowered.endswith(AUDIO_EXTENSIONS):
            modalities.append("audio")
    return {
        "type": "modalities_detected",
        "modalities": sorted(set(modalities)),
    }


def select_tools_for_modalities(modalities: List[str]) -> Dict[str, Any]:
    """Select the tool names to use according to the available modalities."""
    selected_tools = []
    if "image" in modalities:
        selected_tools.append("analyze_image")
    if "document" in modalities:
        selected_tools.append("analyze_document")
    if "audio" in modalities:
        selected_tools.append("transcribe_audio")
    selected_tools.append("validate_evidence")
    selected_tools.append("generate_answer")
    return {
        "type": "tools_selected",
        "selected_tools": selected_tools,
    }


def build_tool_jobs(files: List[str]) -> List[Dict[str, str]]:
    """
    Build the queue of evidence-extraction jobs: one (tool, file, modality) per
    supported file. The planner pops one job at a time during ACT.
    """
    jobs = []
    for file_path in files:
        lowered = file_path.lower()
        if lowered.endswith(IMAGE_EXTENSIONS):
            jobs.append({"tool": "analyze_image", "file": file_path, "modality": "image"})
        elif lowered.endswith(DOCUMENT_EXTENSIONS):
            jobs.append({"tool": "analyze_document", "file": file_path, "modality": "document"})
        elif lowered.endswith(AUDIO_EXTENSIONS):
            jobs.append({"tool": "transcribe_audio", "file": file_path, "modality": "audio"})
    return jobs


def run_tool_job(job: Dict[str, str], user_question: str, config: Dict[str, Any], client) -> Dict[str, Any]:
    """Dispatch a single extraction job to the right tool function."""
    tool = job["tool"]
    file_path = job["file"]
    if tool == "analyze_image":
        return analyze_image(file_path, user_question, config, client)
    if tool == "analyze_document":
        return analyze_document(file_path, user_question, config, client)
    if tool == "transcribe_audio":
        return transcribe_audio(file_path, config, client)
    return {"type": "tool_error", "tool": tool, "source": file_path,
            "error": f"Unknown tool: {tool}"}


# --------------------------------------------------------------------------- #
# Evidence-extraction tools (real OpenAI + mock fallback)
# --------------------------------------------------------------------------- #

def _evidence(tool: str, modality: str, source: str, content: str,
              confidence: float, degraded: bool,
              tokens: Optional[Dict[str, int]] = None) -> Dict[str, Any]:
    result = {
        "type": "evidence",
        "tool": tool,
        "modality": modality,
        "source": source,
        "content": content,
        "confidence": round(confidence, 2),
        "degraded": degraded,
        "tokens": tokens or {"prompt": 0, "completion": 0, "total": 0},
    }
    return result


def analyze_image(file_path: str, user_question: str = "",
                  config: Optional[Dict[str, Any]] = None, client=None) -> Dict[str, Any]:
    """
    Analyze an image with OpenAI vision. No mock fallback: a missing OpenAI
    client / SDK / key raises a clear error.

    Returns an `evidence` dict on success, or a `tool_error` dict if the file is
    missing (which routes the agent to ERROR_RECOVERY).
    """
    config = config or load_config()

    if not os.path.exists(file_path):
        return {"type": "tool_error", "tool": "analyze_image", "source": file_path,
                "error": "Image file not found."}

    client = client if client is not None else get_openai_client(config)

    with open(file_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    ext = os.path.splitext(file_path)[1].lstrip(".").lower() or "png"
    resp = client.chat.completions.create(
        model=config["vision_model"],
        messages=[
            {"role": "system", "content": IMAGE_ANALYSIS_PROMPT},
            {"role": "user", "content": [
                {"type": "text",
                 "text": f"User question: {user_question}\nExtract factual evidence from this image."},
                {"type": "image_url",
                 "image_url": {"url": f"data:image/{ext};base64,{b64}"}},
            ]},
        ],
        max_tokens=400,
    )
    content = resp.choices[0].message.content.strip()
    tokens = {
        "prompt": resp.usage.prompt_tokens,
        "completion": resp.usage.completion_tokens,
        "total": resp.usage.total_tokens,
    }
    return _evidence("analyze_image", "image", file_path, content, 0.80,
                     degraded=False, tokens=tokens)


def analyze_document(file_path: str, user_question: str = "",
                     config: Optional[Dict[str, Any]] = None, client=None) -> Dict[str, Any]:
    """
    Analyze a .txt or .pdf document. Reads real text (PyMuPDF for PDF) and uses
    OpenAI to extract question-relevant evidence; falls back to the raw text /
    a mock when OpenAI is unavailable.
    """
    config = config or load_config()

    if not os.path.exists(file_path):
        return {"type": "tool_error", "tool": "analyze_document", "source": file_path,
                "error": "Document file not found."}

    raw_text = _read_document_text(file_path)
    if raw_text is None:
        return {"type": "tool_error", "tool": "analyze_document", "source": file_path,
                "error": "Could not read document text."}

    client = client if client is not None else get_openai_client(config)

    resp = client.chat.completions.create(
        model=config["text_model"],
        messages=[
            {"role": "system", "content": DOCUMENT_ANALYSIS_PROMPT},
            {"role": "user", "content":
                f"User question: {user_question}\n\nDocument:\n{raw_text}"},
        ],
        max_tokens=400,
    )
    content = resp.choices[0].message.content.strip()
    tokens = {
        "prompt": resp.usage.prompt_tokens,
        "completion": resp.usage.completion_tokens,
        "total": resp.usage.total_tokens,
    }
    return _evidence("analyze_document", "document", file_path, content, 0.82,
                     degraded=False, tokens=tokens)


def _read_document_text(file_path: str) -> Optional[str]:
    """Read text from a .txt directly or a .pdf via PyMuPDF. None on failure."""
    lowered = file_path.lower()
    if lowered.endswith(".txt"):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read().strip()
        except OSError:
            return None
    if lowered.endswith(".pdf"):
        try:
            import fitz  # PyMuPDF
            text = []
            with fitz.open(file_path) as doc:
                for page in doc:
                    text.append(page.get_text())
            return "\n".join(text).strip()
        except Exception:
            return None
    return None


def transcribe_audio(file_path: str, config: Optional[Dict[str, Any]] = None,
                     client=None) -> Dict[str, Any]:
    """
    Transcribe an audio file with OpenAI Whisper. No mock fallback: a missing
    client / SDK / key raises a clear error.
    """
    config = config or load_config()

    if not os.path.exists(file_path):
        return {"type": "tool_error", "tool": "transcribe_audio", "source": file_path,
                "error": "Audio file not found."}

    client = client if client is not None else get_openai_client(config)

    with open(file_path, "rb") as f:
        resp = client.audio.transcriptions.create(model="whisper-1", file=f)
    text = (getattr(resp, "text", "") or "").strip()
    return _evidence("transcribe_audio", "audio", file_path, text, 0.75,
                     degraded=False)


# --------------------------------------------------------------------------- #
# Final answer synthesis (real OpenAI, no mock)
# --------------------------------------------------------------------------- #

def generate_answer(state: Dict[str, Any], config: Optional[Dict[str, Any]] = None,
                    client=None) -> Dict[str, Any]:
    """
    Synthesize the final answer from the collected evidence only, using OpenAI.
    No mock fallback: a missing client / SDK / key raises a clear error.
    """
    config = config or load_config()
    client = client if client is not None else get_openai_client(config)

    evidence = state["evidence"]
    confidence = state["validation"]["confidence"]
    used_modalities = state["validation"]["used_modalities"]
    question = state["user_question"]

    evidence_block = "\n".join(
        f"- [{item['modality']}] {item['content']}" for item in evidence
    )

    resp = client.chat.completions.create(
        model=config["text_model"],
        messages=[
            {"role": "system", "content": FINAL_ANSWER_PROMPT},
            {"role": "user", "content":
                f"User question: {question}\n\nEvidence:\n{evidence_block}\n\n"
                f"Confidence: {confidence}\nUsed modalities: {used_modalities}\n\n"
                "Write the final answer using ONLY the evidence above."},
        ],
        max_tokens=500,
    )
    body = resp.choices[0].message.content.strip()
    answer = (
        f"{body}\n\n"
        f"Confidence: {confidence}\n"
        f"Used modalities: {used_modalities}"
    )
    tokens = {
        "prompt": resp.usage.prompt_tokens,
        "completion": resp.usage.completion_tokens,
        "total": resp.usage.total_tokens,
    }
    return {"type": "final_answer", "answer": answer, "tokens": tokens}
