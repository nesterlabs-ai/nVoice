# NesterAI Question Card Coverage

This document maps the questions NesterAI should answer against the current
knowledge sources in `data/rag_seed`, `data/nester_labs_knowledge.json`, and
`docs/nesterai_response_matrix.md`.

Coverage states:

- `Covered`: enough source material exists for a strong spoken answer.
- `Partial`: source material exists, but the answer needs an approved house
  card to avoid vague or inconsistent responses.
- `Missing`: source material is not specific enough; we need to author a new
  card before NesterAI should answer confidently.

## Covered Cards

These can be answered from the current corpus with limited additional work.

| Card | Example user questions | Current sources | Notes |
|---|---|---|---|
| Company positioning | What is Nesterlabs? How are you different? | `01_company_positioning_and_operating_model.md`, response matrix scenarios 1-2 | Strong. Should lead with embedded AI-native team / execution layer, not generic studio language. |
| Staff augmentation vs agency | Are you an agency? Are you staff augmentation? | `01_company_positioning_and_operating_model.md`, response matrix scenario 2 | Strong. Needs direct answer and contrast. |
| How Nesterlabs works | What is your process? How do engagements work? | `01_company_positioning_and_operating_model.md`, `data/nester_labs_knowledge.json`, response matrix scenario 4 | Strong at the Imagine / Make / Scale level. |
| Voice AI overview | How do you build voice AI? What makes your voice systems different? | `03_voice_ai_overview.md`, `13_nvoice.md`, `21_voice_runtime_and_control_patterns.md`, response matrix scenario 5 | Strong. Should frame voice as runtime, not STT-LLM-TTS glue. |
| Voice runtime controls | How do you handle interruptions, silence, latency, turn-taking? | `03_voice_ai_overview.md`, `13_nvoice.md`, `21_voice_runtime_and_control_patterns.md`, `23_safety_reliability_and_hardening_patterns.md` | Strong. Good for technical buyers. |
| Emotion-aware voice | Is tone adaptation rule-based? Does it detect emotion in real time? | `12_npulse.md`, `03_voice_ai_overview.md`, `data/nester_labs_knowledge.json` | Strong source material exists. Needs a house card so NesterAI answers this directly instead of drifting to UI-state triggers. |
| Knowledge retrieval / memory | Does it use a knowledge base or freeform LLM response? How does memory work? | `11_nmemory.md`, `20_prompt_memory_and_personality_patterns.md`, `03_voice_ai_overview.md`, `data/nester_labs_knowledge.json` | Strong. Needs distinction between curated RAG, memory, and generated language. |
| Agentic AI overview | How do you think about agentic AI? | `02_agentic_systems_overview.md`, `22_agentic_orchestration_and_state_patterns.md`, response matrix scenario 8 | Strong. Lead with workflow, state, and control. |
| Agentic orchestration | How do you handle state, tools, permissions, approvals, retries? | `02_agentic_systems_overview.md`, `14_nflow.md`, `22_agentic_orchestration_and_state_patterns.md`, `25_tooling_and_platform_selection.md` | Strong. This is one of the better-covered areas. |
| Tooling / platform selection | Do you use LangGraph, CrewAI, OpenAI Agents SDK, Google ADK, Bedrock, LiveKit, Pipecat? | `25_tooling_and_platform_selection.md`, `data/nester_labs_knowledge.json` | Strong. Must avoid raw stack dumps unless user asks. |
| Existing stack integration | Will you replace our existing stack? | `01_company_positioning_and_operating_model.md`, `02_agentic_systems_overview.md`, `24_case_studies_and_buyers_questions.md`, response matrix scenario 9 | Strong. Answer should be no forced replacement. |
| Internal stack / accelerators | Do you start from scratch? What gives you leverage? | `04_nester_stack_overview.md`, `10_nester_stack_tools.md`, per-tool docs, response matrix scenario 6 | Strong. Should be matter-of-fact, not a product pitch. |
| nMemory | What is nMemory? | `11_nmemory.md`, `10_nester_stack_tools.md` | Covered. |
| nPulse | What is nPulse? | `12_npulse.md`, `10_nester_stack_tools.md` | Covered. |
| nVoice | What is nVoice? | `13_nvoice.md`, `10_nester_stack_tools.md` | Covered. |
| nFlow | What is nFlow? | `14_nflow.md`, `10_nester_stack_tools.md` | Covered. |
| nCompose | What is nCompose? | `15_ncompose.md`, `10_nester_stack_tools.md` | Covered. |
| nGuard | What is nGuard? | `16_nguard.md`, `10_nester_stack_tools.md` | Covered. |
| nForge | What is nForge? | `17_nforge.md`, `10_nester_stack_tools.md` | Covered. |
| Reliability / hardening | How do you ensure reliability? | `23_safety_reliability_and_hardening_patterns.md`, `16_nguard.md`, `17_nforge.md`, response matrix scenario 7 | Covered. Needs mode-specific versions for voice, agentic, and enterprise security. |
| Case study overview | What proof points do you have? Any examples? | `24_case_studies_and_buyers_questions.md`, `data/nester_labs_knowledge.json` | Covered for public examples. Must avoid inventing client names or finance-specific proof. |
| Human oversight | Can humans stay involved? How do escalation paths work? | `23_safety_reliability_and_hardening_patterns.md`, `24_case_studies_and_buyers_questions.md`, `14_nflow.md` | Covered. |
| Post-launch evolution | What happens after launch? | `01_company_positioning_and_operating_model.md`, `24_case_studies_and_buyers_questions.md` | Covered. |

## Partial Cards

These have some source material but need approved house answers before they
should be used in high-stakes buyer conversations.

| Card | Example user questions | Current sources | Gap to fill |
|---|---|---|---|
| Enterprise security posture | How do you handle enterprise security? What security controls do you use? | `16_nguard.md`, `23_safety_reliability_and_hardening_patterns.md`, `data/nester_labs_knowledge.json` | Current content is broad. Need a precise answer covering access control, encryption, logging, environment separation, vendor controls, and security review workflow. |
| SOC 2 / HIPAA / GDPR posture | Are you SOC 2 certified? Do you support SOC 2 Type II, HIPAA, GDPR? | Mentions in `16_nguard.md`, `11_nmemory.md`, `data/nester_labs_knowledge.json` | Need legal-safe wording. Do not claim certification unless verified. Card should separate "architect for", "support", "compliance-ready", and "certified". |
| Data residency | How do you handle data residency? Can data stay in a region or private cloud? | `13_nvoice.md`, `25_tooling_and_platform_selection.md`, `data/nester_labs_knowledge.json` | Needs approved deployment patterns: regional hosting, self-hosting, private cloud, vendor constraints, and what requires client/legal review. |
| Multi-tenant isolation | How do you guarantee tenant isolation? | `14_nflow.md`, `22_agentic_orchestration_and_state_patterns.md`, `23_safety_reliability_and_hardening_patterns.md` | The corpus has permissions/auditability, but not tenant isolation mechanisms. Need a card with safe architecture patterns. |
| Audit trails | How do you guarantee audit trails? What gets logged? | `14_nflow.md`, `16_nguard.md`, `22_agentic_orchestration_and_state_patterns.md` | Needs concrete logging surface: tool calls, state transitions, approvals, access, model outputs, escalation decisions, retention. |
| SLA / support terms | What are your SLA terms? What support do we get after launch? | `24_case_studies_and_buyers_questions.md` | Missing specifics. Need a cautious card that says terms depend on engagement and are defined commercially, with examples of what SLA can cover. |
| Timelines | How long from kickoff to pilot or production? | `24_case_studies_and_buyers_questions.md`, `data/nester_labs_knowledge.json` | Corpus says "within weeks"; recent test used 9-14 weeks. Need approved ranges by engagement type: prototype, controlled pilot, production launch, enterprise rollout. |
| Pricing / setup fees | What does it cost? Setup fee? Monthly cost? | System prompt has some posture, but RAG seed is thin | Needs approved commercial language. Avoid improvising low-six-figure or monthly ranges unless confirmed. |
| Cancellation / contract terms | Is it month-to-month? Notice period? Cancellation policy? | Not covered | Needs commercial policy from Ankur/team. Until then, NesterAI should say this is scoped in the agreement and offer to route. |
| References / NDA | Can you provide references? Can we sign an NDA? | `24_case_studies_and_buyers_questions.md` has proof points, not process | Need a card: references may be arranged under NDA and client permission; no public naming of confidential clients. |
| Proposal / procurement next step | Can you send a proposal? What do you need from us? | Not covered directly | Need a card with intake details: use case, systems, compliance constraints, timeline, stakeholders, preferred procurement route. |
| Leadership involvement | Who from your senior team is involved? | System prompt escalation notes; no RAG card | Needs a card with clean founder names and responsibilities: Shrey, Kunal, Ankur. Avoid garbled or overpromising involvement. |
| UX/product strategy | Can you help define the product? How do you approach UX? | `01_company_positioning_and_operating_model.md`, `15_ncompose.md`, response matrix scenarios 3 and 10 | Good positioning, but weak methodology. Need specific UX/research process card. |
| Research methodology | What research do you run? Contextual inquiry? User interviews? Validation? | `data/nester_labs_knowledge.json` mentions Contextual Inquiry | Too thin. Need house card with research methods, artifacts, and when research is light vs deep. |
| Brand/product vision | Can you help with brand and product vision? | `01_company_positioning_and_operating_model.md`, portfolio mention of Kahuna/SquareX | Good high-level claim, little method. Need card with how brand expression connects to AI behavior, UI, trust, and roadmap. |
| Design deliverables | What do we get from design? Screens, design system, conversation flows? | `15_ncompose.md` covers design-to-code only | Need deliverables card: flows, service blueprint, conversation design, trust/error states, UI states, design system, prototype. |
| Agentic UI / A2UI | How do visual UI responses work with agents? | Product code has A2UI; corpus only lightly mentions adaptive visual UI | Need a card explaining voice-to-UI events, generated cards/forms, dashboard states, and boundaries. |
| Measurement / success metrics | How do you measure success? | Some metrics in case studies and nForge VoiceScore | Need cards by domain: voice latency/resolution/escalation, agentic task completion/error rate, UX adoption, reliability. |
| Risk handling when blockers appear | What happens if security/data access blocks the timeline? | `23_safety_reliability_and_hardening_patterns.md` general reliability | Need enterprise delivery card: surface early, resequence tracks, decision logs, escalation owners, timeline impact handling. |

## Missing Cards

These should not be answered confidently until new source material is added.

| Card | Example user questions | Needed source material |
|---|---|---|
| Exact certifications | Are you SOC 2 Type II certified? Do you have ISO 27001? | Verified certification status, dates, scope, auditor, and allowed public wording. |
| Exact SLA terms | What uptime do you guarantee? What are response times? | Approved SLA tiers and support obligations. |
| Exact commercial policy | Setup fees, monthly minimums, cancellation notice, retainer terms | Approved pricing and contract policy. |
| Finance-grade regional case study | Show a finance multi-region deployment | Approved case study or explicit "not public, NDA only" language. |
| Data processing agreement / subprocessors | Who processes data? Which vendors are subprocessors? | Legal-approved vendor/subprocessor list and data flow. |
| Incident response | What happens during a security incident? | Incident response process, notification windows, escalation owners. |
| Model governance | How do you evaluate models, prevent regressions, approve model changes? | Model evaluation and release-management policy. |
| Red teaming / adversarial testing | Do you red-team agents and voice bots? | nForge/nGuard give a base, but need a buyer-facing security testing card. |
| Accessibility | How do you design for accessibility? | Accessibility standards and design/QA process. |
| Privacy / PII retention | How long is PII retained? How is deletion handled? | Approved retention/deletion policy by deployment model. |
| Enterprise deployment models | SaaS, single tenant, VPC, on-prem, private cloud | Supported deployment models and tradeoffs. |
| Procurement process | MSA, DPA, security questionnaire, vendor onboarding | Standard procurement workflow and owner. |

## Priority House Cards To Author First

Based on the two test transcripts, these should be authored before expanding
into more scenarios.

1. Enterprise security posture
2. SOC 2 / HIPAA / GDPR safe wording
3. Data residency and deployment model
4. Audit trails and tenant isolation
5. Enterprise timeline and blocker handling
6. Pricing, setup fees, and ongoing support
7. Cancellation / contract terms
8. References and NDA process
9. Leadership involvement
10. Emotion-aware voice adaptation
11. Knowledge retrieval / RAG in sensitive domains
12. UX / research / product definition methodology
13. Brand and product vision methodology
14. Agentic orchestration / nFlow answer
15. Agentic reliability and governance

## Recommended Card Format

Each house card should be small enough to inject dynamically into the prompt.

```json
{
  "id": "enterprise.audit_trails_and_tenant_isolation",
  "mode": "enterprise_evaluator",
  "priority": 104,
  "patterns": [
    "\\b(audit trail|audit trails|auditable|auditability)\\b",
    "\\b(tenant isolation|data isolation|multi[- ]tenant)\\b"
  ],
  "answer_style": "specific architecture answer",
  "guidance": "Direct 2-3 sentence spoken answer for technical evaluators.",
  "must_include": [
    "concrete mechanisms",
    "what depends on deployment model"
  ],
  "must_avoid": [
    "claiming certification or guarantees we cannot prove",
    "vague security language"
  ],
  "followup_rule": "Ask only if needed to distinguish deployment model.",
  "escalation": "Route detailed architecture review to Kunal/team.",
  "allow_discovery_question": false
}
```

## Router Modes Needed

The corpus suggests these dynamic prompt modes:

| Mode | Use when | Follow-up behavior |
|---|---|---|
| `company_positioning` | User asks what Nesterlabs is or how it is different | One optional sharp question |
| `voice_ai_buyer` | User evaluates voice systems, emotion, RAG, interruption, latency | Answer exact question first; one optional technical clarifier |
| `enterprise_evaluator` | User mentions SOC 2, enterprise, board, SLA, security, data residency, references | Direct structured answer; usually no discovery question |
| `agentic_architecture` | User asks about agents, workflows, orchestration, tools, state, approvals | Direct architecture answer; optional clarifier if architecture depends on workflow |
| `ux_product_strategy` | User asks about product, UX, research, design, roadmap, brand | Think with them; one sharp question is allowed |
| `commercial_procurement` | User asks pricing, contract, cancellation, proposal, MSA, NDA | Use approved commercial card; route unknowns |
| `proof_case_study` | User asks for proof, references, named clients, metrics | Give public proof only; offer NDA/reference process |
| `off_topic_or_booking` | User leaves scope or wants a call | Decline or book cleanly |

## Immediate Gap-Fill Sequence

1. Author enterprise/security/commercial cards because the latest test exposed
   these as the most damaging gaps.
2. Author voice buyer cards for emotion adaptation and RAG because the first
   test exposed stale-topic failures there.
3. Author UX/research/brand cards because the corpus has positioning but not
   enough practical method.
4. Author agentic cards last only because the current corpus is already fairly
   strong there; the main need is formatting into injectable answer cards.
