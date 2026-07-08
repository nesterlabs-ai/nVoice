# NesterAI Dynamic Prompt Implementation

This tracks the layered prompt plan and current implementation state.

## Implemented

### 1. Question-card router

File: `app/services/question_cards.py`

The router loads editable JSON cards from `data/question_cards`, detects the
latest user turn, and matches compact house-answer cards.
It supports multiple cards per turn so structured evaluator questions can be
answered in order. Example:

> How do you handle enterprise security, what is the timeline, and who is on
> the team?

matches:

- `enterprise.security_posture`
- `enterprise.timeline_blockers`
- `leadership.involvement`

### 2. Dynamic context injection

File: `app/processors/question_card_context_processor.py`

The processor runs after STT and before `context_aggregator.user()`. It removes
the previous dynamic card and injects a fresh system note for the latest user
question. This keeps the model grounded on the current question instead of
answering stale context.

### 3. External card files

Files:

- `data/question_cards/enterprise.json`
- `data/question_cards/voice_ai.json`
- `data/question_cards/agentic.json`
- `data/question_cards/ux_product.json`
- `data/question_cards/commercial.json`

Cards are no longer Python constants. The JSON files own wording, regex
patterns, priority, discovery policy, must-include guidance, must-avoid rules,
and escalation notes.

### 4. Stable core prompt refactor

File: `app/config/config.yaml`

The base prompt has been reduced to stable identity, brand tone, core response
rules, knowledge/tool boundaries, technical posture, commercial/legal/security
safety, escalation owners, appointment rules, and STT interpretation notes.
Scenario-specific buyer answers now live in dynamic cards.

### 5. Structured evaluator / no-discovery mode

Implemented as card `mode.structured_evaluator`.

Triggers include:

- evaluating providers
- comparing vendors
- procurement
- board
- structured questions
- need specifics
- before we proceed

Behavior:

- answer the latest question first
- answer multi-part questions in order
- do not ask broad discovery questions
- avoid inventing exact legal, commercial, certification, SLA, or reference
  details

### 6. Card-level discovery policy

Each card now has `allow_discovery_question`.

Discovery is disabled for:

- structured evaluator mode
- commercial / procurement
- enterprise security
- audit trails / tenant isolation
- timeline blockers
- references / NDA
- leadership involvement

Discovery remains allowed for product, UX, research, and strategy questions
when the user's problem is vague.

### 7. STT correction rules

Added corrections in `app/config/config.yaml` for recurring test failures:

- `Nestor AI` -> `Nester AI`
- `Nestor Labs` -> `Nesterlabs`
- `mister AI` -> `Nester AI`
- `Shri Malik` -> `Shrey Malik`
- `Shrey Malek` -> `Shrey Malik`
- `In car, which Korea` -> `Ankur Richhariya`
- `SOICE` / `SOC two` -> `SOC 2`

### 8. Scenario fixture and evaluator

Files:

- `tests/fixtures/nesterai_question_card_scenarios.json`
- `scripts/evaluate_question_cards.py`
- `tests/unit/test_question_cards.py`

The evaluator is dependency-free and can run without the live voice stack:

```bash
python3 scripts/evaluate_question_cards.py
```

Current scenarios:

- enterprise security + timeline + team
- audit trails + tenant isolation
- emotion-aware voice adaptation
- knowledge retrieval / RAG
- agentic orchestration
- UX / research / brand
- references / NDA
- commercial terms

## Still To Implement

### 1. Approved commercial/security/legal cards

The current cards are safe but not specific. We still need owner-approved
language for:

- exact SOC 2 / ISO / HIPAA posture
- SLA terms
- cancellation policy
- pricing bands
- data processing agreement
- subprocessors
- incident response
- PII retention / deletion
- deployment models

### 2. Full transcript evaluator

The current evaluator checks routing and prompt guidance. It does not yet score
full transcripts for:

- missed latest question
- stale answer
- hallucinated claim
- unnecessary discovery
- weak enterprise specificity
- incorrect escalation

### 3. Runtime observability

The backend logs injected card IDs, but there is no surfaced debug event or
dashboard view yet. A later pass can emit card IDs to the frontend/debug panel
for test sessions.

## Current Verification

Commands run:

```bash
python3 -m py_compile app/services/question_cards.py app/processors/question_card_context_processor.py app/core/voice_assistant.py app/services/__init__.py tests/unit/test_question_cards.py scripts/evaluate_question_cards.py
python3 scripts/evaluate_question_cards.py
python3 - <<'PY'
import tests.unit.test_question_cards as t
for name in dir(t):
    if name.startswith('test_'):
        getattr(t, name)()
        print(f'PASS {name}')
PY
git diff --check
```

`pytest` is not installed in the current shell, so the unit test functions were
run directly with Python.
