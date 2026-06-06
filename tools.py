"""
tools.py

Tools that the agent can use.

The current implementation uses mock tools so students can focus on agent architecture.
Students can replace these functions with real models:
- analyze_image -> Qwen2-VL / LLaVA / GPT-4o / Claude Vision
- analyze_document -> PyMuPDF + LLM
- transcribe_audio -> Whisper / Qwen2-Audio
"""

import os
from typing import Any, Dict, List


IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg")
DOCUMENT_EXTENSIONS = (".txt", ".pdf")
AUDIO_EXTENSIONS = (".mp3", ".wav", ".m4a")


def detect_modalities(files: List[str]) -> Dict[str, Any]:
    """
    Detect the modalities available in the provided files.
    """
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
        "modalities": sorted(list(set(modalities)))
    }


def select_tools_for_modalities(modalities: List[str]) -> Dict[str, Any]:
    """
    Select tools according to available modalities.
    """
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
        "selected_tools": selected_tools
    }


def analyze_image(file_path: str) -> Dict[str, Any]:
    """
    Mock image analysis tool.

    Replace this with a real vision model if desired.
    """
    return {
        "type": "evidence",
        "tool": "analyze_image",
        "modality": "image",
        "source": file_path,
        "content": "The image appears to contain visual information such as a chart, dashboard, diagram, or screenshot relevant to the question.",
        "confidence": 0.70
    }


def analyze_document(file_path: str) -> Dict[str, Any]:
    """
    Mock document analysis tool.

    For .txt files, this tries to read actual text.
    For .pdf files, it returns a placeholder unless students add PDF extraction.
    """
    content = "The document contains textual context relevant to the user's question."

    if file_path.lower().endswith(".txt") and os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read().strip()
            if text:
                content = f"The document states: {text}"
        except OSError:
            content = "The document could not be read, but it was detected as a document."

    elif file_path.lower().endswith(".pdf"):
        content = "A PDF document was provided. Add PDF extraction with PyMuPDF or another parser to extract real content."

    return {
        "type": "evidence",
        "tool": "analyze_document",
        "modality": "document",
        "source": file_path,
        "content": content,
        "confidence": 0.75
    }


def transcribe_audio(file_path: str) -> Dict[str, Any]:
    """
    Mock audio transcription tool.

    Replace this with Whisper or Qwen2-Audio if desired.
    """
    return {
        "type": "evidence",
        "tool": "transcribe_audio",
        "modality": "audio",
        "source": file_path,
        "content": "The audio appears to contain spoken information relevant to the question. Replace this mock output with a real transcription.",
        "confidence": 0.65
    }
