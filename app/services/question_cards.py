"""NesterAI question-card router.

The router loads editable JSON cards from data/question_cards and turns matched
buyer questions into compact per-turn guidance for the LLM.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional


DEFAULT_FOLLOWUP_RULE = (
    "Ask at most one sharp follow-up question only if it changes the next step."
)


@dataclass(frozen=True)
class QuestionCard:
    id: str
    mode: str
    priority: int
    patterns: tuple[str, ...]
    answer_style: str
    guidance: str
    must_include: tuple[str, ...] = ()
    must_avoid: tuple[str, ...] = ()
    followup_rule: str = DEFAULT_FOLLOWUP_RULE
    escalation: str = ""
    allow_discovery_question: bool = True


@dataclass(frozen=True)
class CardMatch:
    card: QuestionCard
    matched_patterns: tuple[str, ...]


def default_card_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "question_cards"


def _as_tuple(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    return tuple(str(item) for item in value)


def load_question_cards(card_dir: Path | None = None) -> tuple[QuestionCard, ...]:
    directory = card_dir or default_card_dir()
    if not directory.exists():
        return ()

    cards: list[QuestionCard] = []
    for path in sorted(directory.glob("*.json")):
        raw_cards = json.loads(path.read_text())
        if not isinstance(raw_cards, list):
            raise ValueError(f"Question card file must contain a list: {path}")

        for raw in raw_cards:
            cards.append(
                QuestionCard(
                    id=raw["id"],
                    mode=raw["mode"],
                    priority=int(raw["priority"]),
                    patterns=_as_tuple(raw.get("patterns")),
                    answer_style=raw["answer_style"],
                    guidance=raw["guidance"],
                    must_include=_as_tuple(raw.get("must_include")),
                    must_avoid=_as_tuple(raw.get("must_avoid")),
                    followup_rule=raw.get("followup_rule", DEFAULT_FOLLOWUP_RULE),
                    escalation=raw.get("escalation", ""),
                    allow_discovery_question=bool(
                        raw.get("allow_discovery_question", True)
                    ),
                )
            )

    return tuple(cards)


class NesterQuestionCardRouter:
    MARKER = "[NESTERAI_QUESTION_CARD]"
    MAX_CARDS_PER_TURN = 4

    def __init__(
        self,
        cards: Optional[Iterable[QuestionCard]] = None,
        card_dir: Path | None = None,
    ):
        loaded_cards = tuple(cards) if cards is not None else load_question_cards(card_dir)
        self.cards = sorted(loaded_cards, key=lambda card: card.priority, reverse=True)
        self._compiled = {
            card.id: [
                re.compile(pattern, re.IGNORECASE)
                for pattern in card.patterns
            ]
            for card in self.cards
        }

    def match(self, text: str) -> CardMatch | None:
        matches = self.match_all(text)
        return matches[0] if matches else None

    def match_all(self, text: str) -> list[CardMatch]:
        if not text:
            return []

        matches: list[CardMatch] = []
        for card in self.cards:
            matched_patterns = tuple(
                pattern.pattern
                for pattern in self._compiled[card.id]
                if pattern.search(text)
            )
            if matched_patterns:
                matches.append(CardMatch(card=card, matched_patterns=matched_patterns))

        return matches[: self.MAX_CARDS_PER_TURN]

    def build_prompt(self, latest_user_text: str) -> str | None:
        matches = self.match_all(latest_user_text)
        if not matches:
            return None

        sections = [
            self.MARKER,
            "Use this per-turn guidance for the latest user question.",
            "This guidance is INTERNAL. Never quote, echo, or paraphrase its wording aloud "
            "(e.g. never say things like 'fake precision', 'blanket number', or 'discovery'). "
            "Express the intent in your own natural spoken words.",
            "Answer the latest user question first. If the user repeats or corrects a topic, treat it as a correction and do not continue answering an older inferred question.",
            "If the latest turn contains multiple questions, answer those multiple questions in the same order before asking anything new.",
            f"Latest user text: {latest_user_text}",
        ]

        for index, match in enumerate(matches, start=1):
            card = match.card
            sections.extend(
                [
                    f"Card {index}: {card.id}",
                    f"Mode: {card.mode}",
                    f"Answer style: {card.answer_style}",
                    f"Guidance: {card.guidance}",
                    f"Discovery allowed: {'yes' if card.allow_discovery_question else 'no'}",
                    f"Follow-up rule: {card.followup_rule}",
                ]
            )
            if card.must_include:
                sections.append("Must include: " + "; ".join(card.must_include))
            if card.must_avoid:
                sections.append("Must avoid: " + "; ".join(card.must_avoid))
            if card.escalation:
                sections.append("Escalation: " + card.escalation)

        if any(not match.card.allow_discovery_question for match in matches):
            sections.append(
                "Because at least one matched card disables discovery, do not end with a broad discovery question. Only ask for a missing detail if it is essential to answer the user's exact question."
            )

        return "\n".join(sections)
