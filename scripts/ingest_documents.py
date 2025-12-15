#!/usr/bin/env python3
"""Document Ingestion Script for Pinecone RAG.

This script allows you to ingest documents into the Pinecone vector store
for use with the RAG system.

Usage:
    python scripts/ingest_documents.py --file documents.json
    python scripts/ingest_documents.py --text "Your text content here"
    python scripts/ingest_documents.py --dir ./documents/

File format (JSON):
    [
        {
            "content": "Document text content...",
            "metadata": {
                "source": "filename.txt",
                "category": "faq"
            }
        }
    ]
"""

import asyncio
import argparse
import json
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from loguru import logger

# Load environment variables
load_dotenv()

from src.services.pinecone_rag_service import PineconeRAGService


async def ingest_from_file(rag_service: PineconeRAGService, file_path: str) -> dict:
    """Ingest documents from a JSON file.

    Args:
        rag_service: The RAG service instance
        file_path: Path to JSON file containing documents

    Returns:
        Ingestion result
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        documents = json.load(f)

    if isinstance(documents, dict):
        documents = [documents]

    return await rag_service.ingest_documents(documents)


async def ingest_from_text(rag_service: PineconeRAGService, text: str, source: str = "cli") -> dict:
    """Ingest a single text string.

    Args:
        rag_service: The RAG service instance
        text: Text content to ingest
        source: Source identifier

    Returns:
        Ingestion result
    """
    return await rag_service.ingest_text(text, metadata={"source": source})


async def ingest_from_directory(rag_service: PineconeRAGService, dir_path: str, extensions: list = None) -> dict:
    """Ingest all documents from a directory.

    Args:
        rag_service: The RAG service instance
        dir_path: Path to directory containing documents
        extensions: List of file extensions to process (default: .txt, .md, .json)

    Returns:
        Aggregated ingestion result
    """
    if extensions is None:
        extensions = ['.txt', '.md', '.json']

    dir_path = Path(dir_path)
    documents = []

    for ext in extensions:
        for file_path in dir_path.glob(f'**/*{ext}'):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Handle JSON files specially
                if ext == '.json':
                    try:
                        data = json.loads(content)
                        if isinstance(data, list):
                            for item in data:
                                if isinstance(item, dict) and 'content' in item:
                                    documents.append(item)
                        elif isinstance(data, dict) and 'content' in data:
                            documents.append(data)
                        continue
                    except json.JSONDecodeError:
                        pass

                documents.append({
                    "content": content,
                    "metadata": {
                        "source": str(file_path.name),
                        "path": str(file_path.relative_to(dir_path)),
                        "extension": ext
                    }
                })

            except Exception as e:
                logger.error(f"Error reading {file_path}: {e}")

    if not documents:
        return {"success": False, "error": "No documents found"}

    return await rag_service.ingest_documents(documents)


async def main():
    parser = argparse.ArgumentParser(
        description="Ingest documents into Pinecone RAG system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        '--file', '-f',
        help='Path to JSON file containing documents'
    )
    input_group.add_argument(
        '--text', '-t',
        help='Direct text to ingest'
    )
    input_group.add_argument(
        '--dir', '-d',
        help='Directory containing documents to ingest'
    )

    parser.add_argument(
        '--namespace', '-n',
        default='default',
        help='Pinecone namespace to use (default: default)'
    )
    parser.add_argument(
        '--chunk-size',
        type=int,
        default=1000,
        help='Size of text chunks (default: 1000)'
    )
    parser.add_argument(
        '--chunk-overlap',
        type=int,
        default=200,
        help='Overlap between chunks (default: 200)'
    )
    parser.add_argument(
        '--clear',
        action='store_true',
        help='Clear existing vectors in namespace before ingesting'
    )
    parser.add_argument(
        '--status',
        action='store_true',
        help='Show RAG service status and exit'
    )

    args = parser.parse_args()

    # Initialize RAG service
    config = {
        "namespace": args.namespace
    }

    logger.info("Initializing Pinecone RAG Service...")
    rag_service = PineconeRAGService(config)

    # Show status if requested
    if args.status:
        status = rag_service.get_status()
        print(json.dumps(status, indent=2, default=str))
        return

    if not rag_service._initialized:
        logger.error("Failed to initialize RAG service. Check your PINECONE_API_KEY and OPENAI_API_KEY.")
        sys.exit(1)

    # Clear namespace if requested
    if args.clear:
        logger.info(f"Clearing namespace: {args.namespace}")
        rag_service.delete_namespace(args.namespace)

    # Process input
    if args.file:
        logger.info(f"Ingesting from file: {args.file}")
        result = await ingest_from_file(rag_service, args.file)

    elif args.text:
        logger.info("Ingesting text input...")
        result = await ingest_from_text(rag_service, args.text)

    elif args.dir:
        logger.info(f"Ingesting from directory: {args.dir}")
        result = await ingest_from_directory(rag_service, args.dir)

    # Print result
    print("\n" + "="*50)
    print("INGESTION RESULT")
    print("="*50)
    print(json.dumps(result, indent=2))

    if result.get("success"):
        logger.info("Document ingestion completed successfully!")
    else:
        logger.error(f"Ingestion failed: {result.get('error', 'Unknown error')}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
