"""Deterministic guardrail decision policy — the single source of truth.

Both the production runtime (SafetyController + the report_* tool handlers in
conversation.py) and the benchmark (benchmarks/run_multiturn.py) import these
functions, so the benchmark literally exercises the code that ships.

Design (see docs/design/prompt-and-guardrails-redesign.md §10.3):
  · The model DETECTS a concern and calls a tool once. It is unreliable at
    re-calling the tool every turn.
  · Therefore counting, escalation, and disengagement are decided HERE, in code,
    driven by (seriousness, round number) — not by the model's goodwill. That is
    what makes crisis handling loop-proof and consistent.
"""

from __future__ import annotations

# Category -> seriousness. High severity escalates and ends faster.
SEVERITY = {
    "self_harm": "high",
    "violence": "high",
    "medical": "high",
    "abuse": "moderate",
    "distress": "moderate",
}

# US crisis resources, stated once per handoff (never counseling).
RESOURCES = "call or text 988 (Suicide & Crisis Lifeline); 911 if in immediate danger; the National Domestic Violence Hotline at 1-800-799-7233"


def decide(severity: str, rnd: int) -> tuple[str, str]:
    """Return (action, directive) for a safety turn from seriousness × round.

    action is one of: "handoff", "wind_down", "final_end".
    The directive is the instruction the model must follow VERBATIM for its reply.
    """
    if severity == "high":
        if rnd <= 1:
            return "handoff", (
                f"Say ONE warm sentence, then give the exact resource: {RESOURCES}. "
                "No counseling, no questions, no NesterLabs talk."
            )
        return "final_end", (
            "Give ONE short caring line and 988, then STOP — the call is ending now "
            "so they can reach trained help."
        )
    # moderate
    if rnd <= 1:
        return "handoff", (
            f"Acknowledge warmly and offer the resource: {RESOURCES}. "
            "No counseling, no discovery question, no NesterLabs talk."
        )
    if rnd == 2:
        return "wind_down", (
            "Briefly restate that 988 is there and that you'll let them reach real "
            "support now. Begin closing. Do not pitch NesterLabs."
        )
    return "final_end", (
        "Give ONE short caring line and 988, then STOP — the call is ending."
    )


def decide_offtopic(rnd: int) -> tuple[str, str]:
    """Return (action, directive) for a repeated off-topic ask (no crisis resources)."""
    if rnd <= 1:
        return "decline", (
            "Decline in ONE warm sentence and redirect to why they reached NesterLabs. "
            "Do NOT answer the off-topic request and do NOT mention crisis resources."
        )
    if rnd == 2:
        return "decline_firm", (
            "Politely say you can only help with NesterLabs, and ask if there's anything "
            "about what we build they'd like to explore."
        )
    return "wrap", (
        "They've asked several off-topic things; if there's nothing about NesterLabs, "
        "warmly offer to wrap up."
    )


def severity_of(category: str) -> str:
    return SEVERITY.get(category, "moderate")
