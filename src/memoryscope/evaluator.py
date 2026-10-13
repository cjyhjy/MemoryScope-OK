"""Explainable deterministic rule scoring; no LLM calls.

Version 1.1 matches Latin/digit terms on token boundaries (``uv`` does not hit
``uvicorn``; ``pip`` does not hit ``pipx``). CJK terms remain substring matches
because Chinese text has no spaces. ``answer_line`` scores only the final
``答案:`` line so explanations that mention rejected options are not penalised.
"""

import re
from typing import Any

from memoryscope.models import Evaluation, Expected

EVALUATOR_VERSION = "1.1"
_WORDISH = re.compile(r"[A-Za-z0-9]")
_ANSWER_LINE = re.compile(r"^\s*(?:\*\*)?(?:答案|最终答案|answer|final answer)(?:\*\*)?\s*[:：]\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)


def term_matches(term: str, text: str) -> bool:
    folded_term, folded_text = term.casefold(), text.casefold()
    if not _WORDISH.search(term):
        return folded_term in folded_text
    # Boundaries only apply on sides where the term itself starts/ends with a Latin/digit char.
    left = r"(?<![a-z0-9_])" if _WORDISH.match(term[0]) else ""
    right = r"(?![a-z0-9_])" if _WORDISH.match(term[-1]) else ""
    return re.search(left + re.escape(folded_term) + right, folded_text) is not None


def extract_answer_line(response: str) -> str | None:
    matches = _ANSWER_LINE.findall(response)
    return matches[-1] if matches else None


def evaluate(response: str, expected: Expected, evaluation: Evaluation) -> dict[str, Any]:
    """Return status pass/fail/unknown with every term decision and its reason."""
    scope = "full_response"
    target = response
    if evaluation.type == "answer_line":
        scope = "answer_line"
        target = extract_answer_line(response)
        if target is None:
            return {
                "type": evaluation.type, "version": EVALUATOR_VERSION, "status": "unknown",
                "score": None, "passed": None, "scope": scope, "scored_text": None,
                "required_terms": expected.include, "forbidden_terms": expected.exclude,
                "missing_terms": [], "forbidden_hits": [],
                "explanation": "No '答案:' line found; the rule cannot decide, so the result is unknown rather than fail.",
            }
    missing = [term for term in expected.include if not term_matches(term, target)]
    forbidden = [term for term in expected.exclude if term_matches(term, target)]
    passed = not missing and not forbidden
    if passed:
        explanation = "All required terms found; no forbidden terms found."
    else:
        parts = []
        if missing:
            parts.append("missing required: " + ", ".join(missing))
        if forbidden:
            parts.append("forbidden present: " + ", ".join(forbidden))
        explanation = "; ".join(parts) + "."
    return {
        "type": evaluation.type, "version": EVALUATOR_VERSION,
        "status": "pass" if passed else "fail", "passed": passed, "score": 1.0 if passed else 0.0,
        "scope": scope, "scored_text": target,
        "required_terms": expected.include, "forbidden_terms": expected.exclude,
        "missing_terms": missing, "forbidden_hits": forbidden, "explanation": explanation,
    }


def evaluate_contains(response: str, expected: Expected) -> dict[str, Any]:
    return evaluate(response, expected, Evaluation(type="contains"))
