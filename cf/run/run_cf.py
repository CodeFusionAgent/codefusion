#!/usr/bin/env python3
"""
CodeFusion Runner Script
Direct script to run CodeFusion operations without module invocation
"""

import sys
from pathlib import Path

# Add the parent directory to Python path so we can import cf modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from cf.run.run import CodeFusionCLI  # noqa: E402


def main():
    """Main entry point for CodeFusion script."""
    cli = CodeFusionCLI()
    cli.run()


if __name__ == "__main__":
    main()
