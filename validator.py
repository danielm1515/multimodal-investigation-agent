"""
validator.py

Validation and grounding checks.

The validator prevents the agent from producing a final answer if it does not have
enough evidence from at least two modalities.
"""

from typing import Any, Dict, List


def validate_evidence(evidence: List[Dict[str, Any]], minimum_modalities: int = 2) -> Dict[str, Any]:
    """
    Validate whether the available evidence is sufficient.

    Args:
        evidence: List of evidence items.
        minimum_modalities: Minimum number of modalities required.

    Returns:
        Validation result.
    """
    used_modalities = sorted(list(set([
        item.get("modality")
        for item in evidence
        if item.get("modality")
    ])))

    grounded = len(used_modalities) >= minimum_modalities

    avg_confidence = 0.0
    if evidence:
        avg_confidence = sum([
            float(item.get("confidence", 0.0))
            for item in evidence
        ]) / len(evidence)

    missing_info = []

    if len(used_modalities) < minimum_modalities:
        missing_info.append(
            f"Need evidence from at least {minimum_modalities} modalities. "
            f"Currently found: {used_modalities}"
        )

    if not evidence:
        missing_info.append("No evidence was extracted.")

    return {
        "type": "validation_result",
        "grounded": grounded,
        "confidence": round(avg_confidence, 2),
        "used_modalities": used_modalities,
        "missing_info": missing_info
    }
