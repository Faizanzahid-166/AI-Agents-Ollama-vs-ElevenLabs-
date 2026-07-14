"""
main.py
Grace v3 — Pure Python Desktop AI Assistant
Entry point. Run with: python main.py
"""

import sys
import os

# Ensure the project root is on sys.path when launched from anywhere
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.logger import log


def main():
    log.info("=" * 52)
    log.info("  ✦  GRACE v3 — Pure Python Desktop Assistant")
    log.info("=" * 52)

    # Verify critical imports early
    try:
        import customtkinter  # noqa
    except ImportError:
        print("ERROR: customtkinter not installed.")
        print("Run: pip install customtkinter")
        sys.exit(1)

    try:
        import psycopg2  # noqa
    except ImportError:
        print("ERROR: psycopg2 not installed.")
        print("Run: pip install psycopg2-binary")
        sys.exit(1)

    # Initialize database schema (import after dependency checks)
    from core.database import init_schema
    init_schema()

    # Launch app
    from ui.app import GraceApp

    app = GraceApp()
    app.mainloop()


if __name__ == "__main__":
    main()