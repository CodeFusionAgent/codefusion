#!/usr/bin/env python3
"""
Direct execution entry point for CodeFusion module.

Usage:
    python -m cf demo /path/to/repo
    python -m cf index /path/to/repo
    python -m cf query "What does this code do?"
"""

from .run.run import main

if __name__ == "__main__":
    main()