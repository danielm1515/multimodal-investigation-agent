"""
validator.py

Validation and grounding checks.

The validator prevents the agent from producing a final answer unless the evidence
is grounded: it must come from at least two modalities, and the average evidence
confidence must clear a minimum threshold.
"""

from typing import Any, Dict, List


def validate_evidence(evidence: List[Dict[str, Any]],
                      minimum_modalities: int = 2,
                      minimum_confidence: float = 0.0) -> Dict[str, Any]:
    """
    Validate whether the available evidence is sufficient and grounded.

    Args:
        evidence: List of evidence items.
        minimum_modalities: Minimum number of distinct modalities required.
        minimum_confidence: Minimum average confidence required.

    Returns:
        A validation_result dict.
    """
    used_modalities = sorted({
        item.get("modality") for item in evidence if item.get("modality")
    })

    avg_confidence = 0.0
    if evidence:
        avg_confidence = sum(float(item.get("confidence", 0.0)) for item in evidence) / len(evidence)

    enough_modalities = len(used_modalities) >= minimum_modalities
    enough_confidence = avg_confidence >= minimum_confidence
    grounded = enough_modalities and enough_confidence and bool(evidence)

    missing_info = []
    if not evidence:
        missing_info.append("No evidence was extracted.")
    if not enough_modalities:
        missing_info.append(
            f"Need evidence from at least {minimum_modalities} modalities; found {used_modalities}."
        )
    if evidence and not enough_confidence:
        missing_info.append(
            f"Average confidence {round(avg_confidence, 2)} is below the minimum {minimum_confidence}."
        )

    return {
        "type": "validation_result",
        "grounded": grounded,
        "confidence": round(avg_confidence, 2),
        "used_modalities": used_modalities,
        "missing_info": missing_info,
    }
