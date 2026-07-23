#!/usr/bin/env python3
"""Baseline benchmark for the NesterAI voice LLM — run BEFORE any re-architecture.

Measures, per scenario, against the REAL production system prompt and tool
schemas: streaming TTFB (the metric that matters for voice), total generation
time, prompt/completion/cached tokens (prompt-cache hit rate), reported cost,
tool-calling correctness, and guardrail/brevity behavior.

Provider is selected by env (honoring the values you asked for):
    LLM_PROVIDER=xai  LLM_MODEL=grok-4.20-0309-non-reasoning  python benchmarks/run_benchmark.py

Supported providers (all via the OpenAI SDK):
    openai  -> Responses API (matches prod: gpt-5.5 + reasoning_effort=none)
    xai     -> chat completions @ https://api.x.ai/v1  (grok)
    groq    -> chat completions @ https://api.groq.com/openai/v1  (llama)

Compare two providers side by side:
    python benchmarks/run_benchmark.py --compare openai:gpt-5.5 xai:grok-4.20-0309-non-reasoning

Dependency-light: openai SDK + pyyaml (both already in the venv). No app import,
no pipeline, no production code touched. Reads the system prompt from
app/config/config.yaml so it never drifts from prod.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
import time
from pathlib import Path

import yaml
from openai import OpenAI

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from benchmarks.scenarios import SCENARIOS  # noqa: E402

CONFIG = yaml.safe_load((ROOT / "app" / "config" / "config.yaml").read_text())
SYSTEM_PROMPT = CONFIG["conversation"]["system_prompt"]

# ---------------------------------------------------------------------------
# Tool schemas — mirror app/services/conversation.py:create_function_schemas()
# (kept inline so the harness stays standalone / import-free).
# ---------------------------------------------------------------------------
_TOOLS = [
    ("call_rag_system", "Search the Nesterlabs knowledge base for deeper specifics, case studies, metrics, named tools, or project details.",
     {"type": "object", "properties": {"question": {"type": "string", "description": "The user's question to research."}}, "required": ["question"]}),
    ("end_conversation", "End the conversation after a farewell. Offer a chat with the team first.",
     {"type": "object", "properties": {}}),
    ("start_appointment_booking", "Begin booking a conversation with the team when the user agrees.",
     {"type": "object", "properties": {}}),
    ("submit_appointment", "Submit the appointment once the user confirms their spelled-out details.",
     {"type": "object", "properties": {"first_name": {"type": "string"}, "last_name": {"type": "string"}, "email": {"type": "string"}}, "required": ["first_name", "last_name", "email"]}),
]
CHAT_TOOLS = [{"type": "function", "function": {"name": n, "description": d, "parameters": p}} for n, d, p in _TOOLS]
RESP_TOOLS = [{"type": "function", "name": n, "description": d, "parameters": p} for n, d, p in _TOOLS]

PROVIDERS = {
    "openai": {"base_url": None, "key_env": "OPENAI_API_KEY", "default_model": "gpt-5.5", "api": "responses"},
    "xai": {"base_url": "https://api.x.ai/v1", "key_env": "XAI_API_KEY", "default_model": "grok-4.20-0309-non-reasoning", "api": "chat"},
    "groq": {"base_url": "https://api.groq.com/openai/v1", "key_env": "GROQ_API_KEY", "default_model": "llama-3.3-70b-versatile", "api": "chat"},
}


def _env(key: str) -> str | None:
    """Read a key from the process env or the local .env (dotenv-free)."""
    if os.getenv(key):
        return os.getenv(key)
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.strip().startswith(f"{key}="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def _client(provider: str) -> OpenAI:
    spec = PROVIDERS[provider]
    key = _env(spec["key_env"])
    if not key:
        raise SystemExit(f"Missing {spec['key_env']} in env/.env for provider '{provider}'")
    return OpenAI(api_key=key, base_url=spec["base_url"])


# ---------------------------------------------------------------------------
# Provider adapters -> normalized result: {ttfb_ms, total_ms, text, tools, usage}
# usage: {prompt, completion, cached, cost_usd}
# ---------------------------------------------------------------------------
def _run_chat(client, model, messages, temperature=0.7):
    start = time.perf_counter()
    stream = client.chat.completions.create(
        model=model, messages=messages, tools=CHAT_TOOLS, tool_choice="auto",
        temperature=temperature, max_tokens=220, stream=True,
        stream_options={"include_usage": True},
    )
    ttfb = None; text = ""; tools = []; usage = None
    for chunk in stream:
        if getattr(chunk, "usage", None):
            usage = chunk.usage
        if not chunk.choices:
            continue
        d = chunk.choices[0].delta
        if ttfb is None and (getattr(d, "content", None) or getattr(d, "tool_calls", None)):
            ttfb = time.perf_counter() - start
        if getattr(d, "content", None):
            text += d.content
        for tc in (getattr(d, "tool_calls", None) or []):
            if tc.function and tc.function.name:
                tools.append(tc.function.name)
    total = time.perf_counter() - start
    u = _norm_usage_chat(usage)
    return {"ttfb_ms": (ttfb or total) * 1000, "total_ms": total * 1000, "text": text.strip(), "tools": tools, "usage": u}


def _run_responses(client, model, messages):
    # Prod path: instructions=system prompt, input=conversation, reasoning none.
    start = time.perf_counter()
    stream = client.responses.create(
        model=model, instructions=SYSTEM_PROMPT, input=messages, tools=RESP_TOOLS,
        reasoning={"effort": "none"}, max_output_tokens=220, stream=True,
    )
    ttfb = None; text = ""; tools = []; usage = None
    for ev in stream:
        et = getattr(ev, "type", "")
        if ttfb is None and et in ("response.output_text.delta", "response.function_call_arguments.delta", "response.output_item.added"):
            ttfb = time.perf_counter() - start
        if et == "response.output_text.delta":
            text += getattr(ev, "delta", "")
        if et == "response.output_item.added":
            item = getattr(ev, "item", None)
            if item is not None and getattr(item, "type", None) == "function_call":
                tools.append(getattr(item, "name", "?"))
        if et == "response.completed":
            usage = getattr(ev.response, "usage", None)
    total = time.perf_counter() - start
    u = _norm_usage_resp(usage)
    return {"ttfb_ms": (ttfb or total) * 1000, "total_ms": total * 1000, "text": text.strip(), "tools": tools, "usage": u}


def _norm_usage_chat(u):
    if not u:
        return {"prompt": 0, "completion": 0, "cached": 0, "cost_usd": None}
    ptd = getattr(u, "prompt_tokens_details", None)
    cached = getattr(ptd, "cached_tokens", 0) if ptd else 0
    ticks = getattr(u, "cost_in_usd_ticks", None)  # xAI reports this
    return {"prompt": u.prompt_tokens, "completion": u.completion_tokens, "cached": cached or 0,
            "cost_usd": (ticks / 1e9) if ticks else None}


def _norm_usage_resp(u):
    if not u:
        return {"prompt": 0, "completion": 0, "cached": 0, "cost_usd": None}
    itd = getattr(u, "input_tokens_details", None)
    cached = getattr(itd, "cached_tokens", 0) if itd else 0
    return {"prompt": getattr(u, "input_tokens", 0), "completion": getattr(u, "output_tokens", 0),
            "cached": cached or 0, "cost_usd": None}


def run_turn(provider, model, client, scenario):
    msgs = list(scenario.get("prior", [])) + [{"role": "user", "content": scenario["user"]}]
    if PROVIDERS[provider]["api"] == "responses":
        return _run_responses(client, model, msgs)
    return _run_chat(client, model, [{"role": "system", "content": SYSTEM_PROMPT}] + msgs)


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------
def _looks_spanish(text: str) -> bool:
    t = text.lower()
    hits = sum(w in t for w in [" de ", " que ", " los ", " las ", " para ", " con ", " voz ", " qué ", " cómo ", "¿", "ñ", " sistemas "])
    return hits >= 2


def score(scenario, result) -> tuple[bool, list[str]]:
    checks = scenario.get("checks", {})
    text = result["text"]; tools = result["tools"]
    fails = []
    if "expect_tool" in checks:
        want = checks["expect_tool"]
        if want is None and tools:
            fails.append(f"expected no tool, got {tools}")
        if want and want not in tools:
            fails.append(f"expected tool {want!r}, got {tools or 'none'}")
    for pat in checks.get("must_include", []):
        if not re.search(pat, text, re.I):
            fails.append(f"missing /{pat}/")
    for pat in checks.get("must_exclude", []):
        if re.search(pat, text, re.I):
            fails.append(f"contains forbidden /{pat}/")
    if "max_words" in checks and len(text.split()) > checks["max_words"]:
        fails.append(f"too long: {len(text.split())}w > {checks['max_words']}")
    if checks.get("expect_lang") == "es" and text and not _looks_spanish(text):
        fails.append("expected Spanish reply, got non-Spanish")
    return (not fails), fails


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------
def run_provider(provider, model):
    client = _client(provider)
    print(f"\n{'='*78}\nPROVIDER: {provider}  MODEL: {model}\n{'='*78}")
    rows = []
    for sc in SCENARIOS:
        try:
            res = run_turn(provider, model, client, sc)
            ok, fails = score(sc, res)
        except Exception as e:
            print(f"  [{sc['id']:<22}] ERROR: {type(e).__name__}: {str(e)[:160]}")
            rows.append({"id": sc["id"], "category": sc["category"], "error": str(e)[:200]})
            continue
        u = res["usage"]
        cache_pct = (100 * u["cached"] / u["prompt"]) if u["prompt"] else 0
        rows.append({
            "id": sc["id"], "category": sc["category"], "pass": ok, "fails": fails,
            "ttfb_ms": round(res["ttfb_ms"]), "total_ms": round(res["total_ms"]),
            "prompt_tok": u["prompt"], "completion_tok": u["completion"],
            "cached_tok": u["cached"], "cache_pct": round(cache_pct),
            "cost_usd": u["cost_usd"], "tools": res["tools"], "text": res["text"],
        })
        flag = "✅" if ok else "❌"
        print(f"  {flag} {sc['id']:<22} ttfb={res['ttfb_ms']:>5.0f}ms total={res['total_ms']:>6.0f}ms "
              f"tok={u['prompt']}+{u['completion']} cache={cache_pct:>3.0f}% "
              f"{('tools='+','.join(res['tools'])) if res['tools'] else ''}")
        if not ok:
            print(f"       └─ {'; '.join(fails)}")
            print(f"       reply: {res['text'][:150]}")
    _summary(provider, model, rows)
    return rows


def _summary(provider, model, rows):
    ok_rows = [r for r in rows if "error" not in r]
    passed = sum(1 for r in ok_rows if r["pass"])
    ttfbs = [r["ttfb_ms"] for r in ok_rows]
    totals = [r["total_ms"] for r in ok_rows]
    caches = [r["cache_pct"] for r in ok_rows]
    costs = [r["cost_usd"] for r in ok_rows if r["cost_usd"] is not None]
    def med(x): return round(statistics.median(x)) if x else 0
    print(f"\n  ── SUMMARY ({provider}:{model}) ──")
    print(f"     behavior pass : {passed}/{len(ok_rows)}")
    print(f"     TTFB  ms      : median {med(ttfbs)}  min {min(ttfbs) if ttfbs else 0:.0f}  max {max(ttfbs) if ttfbs else 0:.0f}")
    print(f"     total ms      : median {med(totals)}")
    print(f"     cache hit %   : median {med(caches)}  (higher = better prompt-cache reuse)")
    if costs:
        print(f"     cost/turn USD : median {statistics.median(costs):.6f}  total {sum(costs):.6f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--compare", nargs="+", metavar="provider:model",
                    help="Run several provider:model pairs (e.g. openai:gpt-5.5 xai:grok-4.20-0309-non-reasoning)")
    ap.add_argument("--json", metavar="PATH", help="Write full results JSON here")
    args = ap.parse_args()

    targets = []
    if args.compare:
        for spec in args.compare:
            prov, _, model = spec.partition(":")
            targets.append((prov, model or PROVIDERS[prov]["default_model"]))
    else:
        prov = (_env("LLM_PROVIDER") or "openai").lower()
        if prov not in PROVIDERS:
            raise SystemExit(f"Unknown LLM_PROVIDER={prov!r}; choose from {list(PROVIDERS)}")
        model = _env("LLM_MODEL") or PROVIDERS[prov]["default_model"]
        targets.append((prov, model))

    all_results = {}
    for prov, model in targets:
        all_results[f"{prov}:{model}"] = run_provider(prov, model)

    if args.json:
        Path(args.json).write_text(json.dumps(all_results, indent=2, default=str))
        print(f"\nWrote {args.json}")


if __name__ == "__main__":
    main()
