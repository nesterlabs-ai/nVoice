#!/usr/bin/env python3
"""Evaluate NesterAI question-card routing against scenario fixtures.

This is intentionally dependency-free so it can run in lightweight local
environments without the full voice stack.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS_PATH = ROOT / "tests" / "fixtures" / "nesterai_question_card_scenarios.json"

sys.path.insert(0, str(ROOT))

from app.services.question_cards import NesterQuestionCardRouter  # noqa: E402


def main() -> int:
    scenarios = json.loads(SCENARIOS_PATH.read_text())
    router = NesterQuestionCardRouter()
    failures: list[str] = []

    for scenario in scenarios:
        text = scenario["latest_user_text"]
        expected_cards = scenario.get("expected_cards", [])
        expected_substrings = scenario.get("prompt_contains", [])

        matches = router.match_all(text)
        actual_cards = [match.card.id for match in matches]
        prompt = router.build_prompt(text) or ""

        missing_cards = [card for card in expected_cards if card not in actual_cards]
        missing_substrings = [
            substring for substring in expected_substrings
            if substring not in prompt
        ]

        if missing_cards or missing_substrings:
            detail = [f"Scenario {scenario['id']} failed"]
            if missing_cards:
                detail.append(f"  missing cards: {missing_cards}")
                detail.append(f"  actual cards: {actual_cards}")
            if missing_substrings:
                detail.append(f"  missing prompt text: {missing_substrings}")
            failures.append("\n".join(detail))
        else:
            print(f"PASS {scenario['id']}: {', '.join(actual_cards)}")

    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1

    print(f"\nAll {len(scenarios)} question-card scenarios passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
