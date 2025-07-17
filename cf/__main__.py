#!/usr/bin/env python3
"""
Direct execution entry point for CodeFusion module.

Usage:
    python -m cf explore /path/to/repo "How does authentication work?"
    python -m cf ask /path/to/repo "What are the main API endpoints?"
    python -m cf summary /path/to/repo
"""

from .run.simple_run import main

if __name__ == "__main__":
    main()