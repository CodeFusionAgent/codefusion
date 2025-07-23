#!/usr/bin/env python3
"""
Direct execution entry point for CodeFusion module.

Usage:
    python -m cf ask /path/to/repo "How does authentication work?"
    python -m cf summary /path/to/repo
    python -m cf interactive /path/to/repo
"""

# Import at module level to avoid import warnings
from cf.run.main import main

if __name__ == "__main__":
    main()