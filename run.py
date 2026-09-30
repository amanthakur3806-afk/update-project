"""
Application Entry Point
=======================
Starts the Orchestrated Multi-MCP AI Agent Platform.

Usage:
    py -3.12 run.py

This script:
  1. Seeds the SQLite database and FAISS knowledge index (idempotent).
  2. Launches the FastAPI application via Uvicorn.
"""
import sys
import os

# Fix Unicode output on Windows terminals
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import uvicorn
from app.config import settings
from app.seed_data import seed_database


def main():
    print("=" * 70)
    print("  ORCHESTRATED MULTI-MCP AI AGENT PLATFORM")
    print("=" * 70)
    print("[*] Initializing database and FAISS knowledge index...")
    seed_database()
    print()
    print("[+] Ready. Open the interfaces below:")
    print(f"    Web UI       ->  http://localhost:{settings.PORT}/")
    print(f"    Swagger Docs ->  http://localhost:{settings.PORT}/docs")
    print(f"    Health Check ->  http://localhost:{settings.PORT}/health")
    print()
    print("=" * 70)

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=False,
    )


if __name__ == "__main__":
    main()
