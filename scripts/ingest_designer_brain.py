"""
Ingest Designer Brain knowledge documents into LightRAG.

Ingests DOC4B–4E (Discovery, Execution, UX Principles, Product References)
as separate documents so LightRAG can retrieve them on relevant design queries.

Usage:
    python scripts/ingest_designer_brain.py

Requires LIGHTRAG_BASE_URL and LIGHTRAG_API_KEY in environment (or .env file).
"""

import asyncio
import os
import sys

import httpx
from dotenv import load_dotenv

load_dotenv()

LIGHTRAG_BASE_URL = os.getenv("LIGHTRAG_BASE_URL", "https://lightrag.nesterlabs.com").rstrip("/")
LIGHTRAG_API_KEY = os.getenv("LIGHTRAG_API_KEY", "")

DOCS_BASE = "/Users/kunalshrivastava/Downloads/NAI Design Brain Layer"

DOCUMENTS = [
    {
        "file": f"{DOCS_BASE}/DOC4B_DISCOVERY_PATTERNS.md",
        "label": "Nesterlabs Design Brain — Discovery Patterns",
    },
    {
        "file": f"{DOCS_BASE}/DOC4C_EXECUTION_PATTERNS.md",
        "label": "Nesterlabs Design Brain — Execution Patterns",
    },
    {
        "file": f"{DOCS_BASE}/DOC4D_UX_PRINCIPLES_LIBRARY.md",
        "label": "Nesterlabs Design Brain — UX Principles Library",
    },
    {
        "file": f"{DOCS_BASE}/DOC4E_PRODUCT_REFERENCES.md",
        "label": "Nesterlabs Design Brain — Product Reference Examples",
    },
]


async def main():
    if not LIGHTRAG_API_KEY:
        print("❌ LIGHTRAG_API_KEY not set. Check your .env file.")
        sys.exit(1)

    print(f"🔗 LightRAG URL: {LIGHTRAG_BASE_URL}")
    print(f"📚 Loading {len(DOCUMENTS)} Designer Brain documents...\n")

    texts = []
    for doc in DOCUMENTS:
        path = doc["file"]
        label = doc["label"]

        if not os.path.exists(path):
            print(f"  ⚠️  File not found: {path}")
            continue

        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        # Prepend clear title so LightRAG's entity graph can label it correctly
        full_content = f"# {label}\n\n{content}"
        texts.append(full_content)
        print(f"  📄 Loaded: {label} ({len(content):,} chars)")

    if not texts:
        print("❌ No documents loaded. Exiting.")
        sys.exit(1)

    print(f"\n⬆️  Sending {len(texts)} documents to LightRAG as a batch...")

    async with httpx.AsyncClient(verify=False, timeout=300.0) as client:
        try:
            response = await client.post(
                f"{LIGHTRAG_BASE_URL}/documents/texts",
                headers={
                    "X-API-Key": LIGHTRAG_API_KEY,
                    "Content-Type": "application/json",
                },
                json={"texts": texts},
            )
            if response.status_code == 200:
                print(f"\n✅ All {len(texts)} documents ingested successfully!")
                print(f"   Response: {response.text[:300]}")
            else:
                print(f"\n❌ Failed ({response.status_code})")
                print(f"   Response: {response.text[:500]}")
        except Exception as e:
            print(f"\n❌ Error during ingestion: {e}")

    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
