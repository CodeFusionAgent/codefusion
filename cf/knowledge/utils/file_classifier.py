"""
File Classification Utilities

Classifies files as test, utility, or entry point files based on path patterns.
Extracted from StructuralPipeline for better modularity.
"""

import os
from typing import Optional


class FileClassifier:
    """
    Utility class for classifying files by type.

    Provides methods to identify:
    - Test files (test_*.py, *_test.py, tests/ directory)
    - Utility files (helpers, managers, tasks, factories, migrations)
    - Entry point files (views, APIs, handlers, routes)
    """

    # Path patterns for different file types
    TEST_PATTERNS = [
        '/test/', '/tests/', 'test_', '_test.py', '/spec/', '/specs/',
        '__tests__/', '.test.', '.spec.'
    ]

    UTILITY_PATTERNS = [
        '/managers/', '/tasks/', '/helpers/', '/utils/', '/utilities/',
        '/factories/', '/commands/', '/management/commands/', '/migrations/',
        '/admin.py', '/serializers/', '/forms/', '/constants/', '/config/',
        '/settings/', 'helpers.py', 'utils.py', 'constants.py'
    ]

    ENTRY_POINT_PATTERNS = [
        '/views.py', '/views/', '/api/', '/endpoints/', '/handlers/',
        '/routes/', '/urls.py', '/controllers/', '/resources/',
        '/graphql/', '/rest/', 'main.py', 'cli.py', 'app.py', '__main__.py'
    ]

    def __init__(self, repo_path: Optional[str] = None):
        """
        Initialize file classifier.

        Args:
            repo_path: Optional repository root path for validation
        """
        self.repo_path = repo_path

    def is_test_file(self, file_path: str) -> bool:
        """
        Check if file is a test file.

        Args:
            file_path: File path to check

        Returns:
            True if file is a test file
        """
        if not file_path:
            return False

        file_path_lower = file_path.lower()
        return any(pattern in file_path_lower for pattern in self.TEST_PATTERNS)

    def is_utility_file(self, file_path: str) -> bool:
        """
        Check if file is a utility/helper file.

        Utility files include:
        - Managers, tasks, helpers, utilities
        - Factories, commands, migrations
        - Admin, serializers, forms, constants

        Args:
            file_path: File path to check

        Returns:
            True if file is a utility file
        """
        if not file_path:
            return False

        file_path_lower = file_path.lower()
        return any(pattern in file_path_lower for pattern in self.UTILITY_PATTERNS)

    def is_entry_point_file(self, file_path: str) -> bool:
        """
        Check if file contains entry points (views, APIs, handlers).

        Entry point files are where requests/operations typically start:
        - Views (Flask, Django views)
        - API endpoints (REST, GraphQL)
        - Handlers (Lambda, event handlers)
        - Routes/Controllers

        Args:
            file_path: File path to check

        Returns:
            True if file contains entry points
        """
        if not file_path:
            return False

        file_path_lower = file_path.lower()
        return any(pattern in file_path_lower for pattern in self.ENTRY_POINT_PATTERNS)

    def validate_file_path(self, file_path: str) -> bool:
        """
        Validate that a file path exists and is readable.

        Args:
            file_path: Relative path from repo root (or absolute)

        Returns:
            True if file exists and is readable
        """
        if not file_path:
            return False

        # If repo_path provided, construct absolute path
        if self.repo_path:
            abs_path = os.path.join(self.repo_path, file_path)
        else:
            abs_path = file_path

        # Check if file exists
        if not os.path.exists(abs_path):
            return False

        # Check if it's a file (not directory)
        if not os.path.isfile(abs_path):
            return False

        # Check if it's readable
        if not os.access(abs_path, os.R_OK):
            return False

        return True

    def classify_file(self, file_path: str) -> str:
        """
        Classify file into one of: 'test', 'utility', 'entry_point', or 'production'.

        Args:
            file_path: File path to classify

        Returns:
            Classification string: 'test', 'utility', 'entry_point', or 'production'
        """
        if self.is_test_file(file_path):
            return 'test'
        elif self.is_utility_file(file_path):
            return 'utility'
        elif self.is_entry_point_file(file_path):
            return 'entry_point'
        else:
            return 'production'

    def get_file_priority(self, file_path: str) -> int:
        """
        Get priority score for file (higher = more important for analysis).

        Priority order:
        1. Entry points (100) - Where execution starts
        2. Production (75) - Main business logic
        3. Utility (50) - Helper/support code
        4. Test (25) - Test code (lower priority for production analysis)

        Args:
            file_path: File path to score

        Returns:
            Priority score (0-100)
        """
        classification = self.classify_file(file_path)

        priority_map = {
            'entry_point': 100,
            'production': 75,
            'utility': 50,
            'test': 25
        }

        return priority_map.get(classification, 50)
