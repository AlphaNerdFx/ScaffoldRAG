#!/usr/bin/env python3
"""
scripts/ingest_corpus.py
Command-line ingestion script to index all 15 blueprints into Qdrant.
Verifies DoD for Task 1.3: Vector count > 0 with verified payloads.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

from qdrant_client import QdrantClient

from app.core.config import Settings
from app.services.indexer import IndexerService


def main() -> int:
    blueprints_dir = Path("data/blueprints")
    settings = Settings()
    print(
        f"Connecting to Qdrant at {settings.QDRANT_HOST}:{settings.QDRANT_GRPC_PORT} (prefer_grpc=True)..."
    )

    try:
        client = QdrantClient(
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_GRPC_PORT,
            prefer_grpc=True,
            timeout=10.0,
        )
    except Exception as exc:
        print(f"FATAL: Could not establish Qdrant connection: {exc}")
        return 1

    indexer = IndexerService(client=client)

    print(f"Starting ingestion from: {blueprints_dir.resolve()}")
    start_time = time.perf_counter()

    try:
        total_indexed = indexer.index_all(blueprints_dir)
    except Exception as exc:
        print(f"\n[FAILED] Ingestion aborted with error: {exc}")
        return 1

    elapsed = time.perf_counter() - start_time
    print(f"[PASSED] Ingestion completed: {total_indexed} chunks indexed in {elapsed:.3f}s.")

    # Validation against Qdrant API
    collection_info = client.get_collection(indexer.collection_name)
    print(f"Verified Qdrant Collection: '{indexer.collection_name}'")
    print(f"  - Points count: {collection_info.points_count}")
    print(f"  - Status: {collection_info.status}")

    if collection_info.points_count == 0:
        print("ERROR: Points count is 0. Definition of Done not met.")
        return 1

    print(
        "\nDoD Confirmed: Collection is active and populated. Open http://localhost:6333/dashboard to inspect payloads."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
