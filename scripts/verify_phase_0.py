import sys

from qdrant_client import QdrantClient

from app.core.config import get_settings


def run_audit():
    print("==================================================")
    print("PHASE 0 GATEKEEPER AUDIT: VERIFYING REQUISITES")
    print("==================================================")

    # 1. Audit Settings Loader (Task 0.3)
    print("\n[CHECK 1/2] Auditing Task 0.3: Settings & Secrets Layer...")
    try:
        settings = get_settings()
        print("  --> Settings Loaded: SUCCESS")
        print(f"      Qdrant Target Host : {settings.QDRANT_HOST}")
        print(f"      REST Port          : {settings.QDRANT_PORT}")
        print(f"      gRPC Port          : {settings.QDRANT_GRPC_PORT}")
        print(f"      Collection Name    : {settings.QDRANT_COLLECTION_NAME}")
        print(f"      Inference Model    : {settings.INFERENCE_MODEL}")
    except Exception as e:
        print(f"  [X] CONFIGURATION VALIDATION FAILED: {e}")
        print("      Remediation: Ensure .env exists and GROQ_API_KEY starts with 'gsk_'")
        sys.exit(1)

    # 2. Audit Qdrant Connectivity across Both Protocols (Task 0.2)
    print("\n[CHECK 2/2] Auditing Task 0.2: Qdrant Dual-Protocol Connectivity...")
    try:
        # A. HTTP REST Interface (Port 6333)
        rest_client = QdrantClient(
            host=settings.QDRANT_HOST, port=settings.QDRANT_PORT, prefer_grpc=False
        )
        rest_cols = rest_client.get_collections()
        print(
            f"  --> REST Interface (Port {settings.QDRANT_PORT}) : CONNECTED (Active Collections: {len(rest_cols.collections)})"
        )

        # B. Binary gRPC Interface (Port 6334)
        grpc_client = QdrantClient(
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_PORT,
            grpc_port=settings.QDRANT_GRPC_PORT,
            prefer_grpc=True,
        )
        grpc_cols = grpc_client.get_collections()
        print(
            f"  --> gRPC Interface (Port {settings.QDRANT_GRPC_PORT}) : CONNECTED (Active Collections: {len(grpc_cols.collections)})"
        )

    except Exception as e:
        print(f"  [X] QDRANT CONNECTION FAILED: {e}")
        print("      Remediation: Verify 'docker compose ps' shows scaffold_rag_qdrant running.")
        sys.exit(1)

    print("\n==================================================")
    print("AUDIT RESULT: 100% PASSED. PHASE 0 OFFICIALLY CLOSED.")
    print("==================================================")


if __name__ == "__main__":
    run_audit()
