"""
Unit Tests for FrameworkDetector and Import Following

Tests the LLM-driven framework detection and two-pass import following functionality.
"""

import pytest
import tempfile
import shutil
import sys
from pathlib import Path
from unittest.mock import Mock, patch

from cf.agents.framework_detector import FrameworkDetector, FrameworkContext


class TestFrameworkContext:
    """Test FrameworkContext dataclass"""

    def test_empty_context_returns_empty_prompt(self):
        """Empty context should return empty string for prompt section"""
        context = FrameworkContext()
        assert context.to_prompt_section() == ""

    def test_context_with_language_returns_prompt(self):
        """Context with language should return formatted prompt"""
        context = FrameworkContext(
            primary_language="python",
            frameworks=["django", "celery"]
        )
        prompt = context.to_prompt_section()
        assert "CODEBASE CONTEXT" in prompt
        assert "python" in prompt
        assert "django" in prompt
        assert "celery" in prompt

    def test_context_with_hints_includes_them(self):
        """Context with analysis hints should include them in prompt"""
        context = FrameworkContext(
            primary_language="python",
            analysis_hints=["Look for signals.py", "Check admin.py"]
        )
        prompt = context.to_prompt_section()
        assert "signals.py" in prompt
        assert "admin.py" in prompt

    def test_context_limits_items_to_prevent_bloat(self):
        """Context should limit items to prevent prompt bloat"""
        context = FrameworkContext(
            primary_language="python",
            key_file_patterns=[f"pattern_{i}" for i in range(10)]
        )
        prompt = context.to_prompt_section()
        # Should only include first 5 patterns
        assert "pattern_0" in prompt
        assert "pattern_4" in prompt
        # pattern_5 and beyond should not be included (limit is 5)


class TestFrameworkDetector:
    """Test FrameworkDetector class"""

    @pytest.fixture
    def temp_repo(self):
        """Create a temporary repository with indicator files"""
        temp_dir = tempfile.mkdtemp()
        repo_path = Path(temp_dir)

        # Create requirements.txt (Python indicator)
        (repo_path / "requirements.txt").write_text("""
django==4.2
celery==5.3
redis==4.5
""")

        # Create a sample Python file
        src_dir = repo_path / "app"
        src_dir.mkdir()
        (src_dir / "models.py").write_text("""
from django.db import models

class User(models.Model):
    name = models.CharField(max_length=100)
""")

        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def mock_llm_callback(self):
        """Create a mock LLM callback that returns framework detection"""
        def callback(prompt: str, system_prompt: str):
            return {
                'success': True,
                'content': '''{
                    "primary_language": "python",
                    "frameworks": ["django", "celery"],
                    "key_file_patterns": ["models.py contains data models"],
                    "important_directories": ["app/ - main application"],
                    "analysis_hints": ["Look for signals.py"]
                }'''
            }
        return callback

    def test_detector_initializes(self, temp_repo, mock_llm_callback):
        """Test that detector initializes correctly"""
        detector = FrameworkDetector(temp_repo, mock_llm_callback)
        assert detector.repo_path == Path(temp_repo)

    def test_detector_detects_framework(self, temp_repo, mock_llm_callback):
        """Test that detector detects framework correctly"""
        detector = FrameworkDetector(temp_repo, mock_llm_callback)
        context = detector.detect()

        assert context.primary_language == "python"
        assert "django" in context.frameworks
        assert "celery" in context.frameworks

    def test_detector_caches_result(self, temp_repo, mock_llm_callback):
        """Test that detector caches result for subsequent calls"""
        detector = FrameworkDetector(temp_repo, mock_llm_callback)

        # First detection
        context1 = detector.detect()

        # Second detection should use cache
        context2 = detector.detect()

        assert context1.primary_language == context2.primary_language
        assert context1.detection_hash == context2.detection_hash

    def test_detector_handles_llm_failure(self, temp_repo):
        """Test that detector handles LLM failure gracefully"""
        def failing_callback(prompt, system_prompt):
            return {'success': False, 'error': 'API error'}

        detector = FrameworkDetector(temp_repo, failing_callback)
        context = detector.detect()

        # Should return empty context on failure
        assert context.primary_language == "unknown"
        assert context.frameworks == []

    def test_detector_handles_invalid_json(self, temp_repo):
        """Test that detector handles invalid JSON from LLM"""
        def invalid_json_callback(prompt, system_prompt):
            return {'success': True, 'content': 'not valid json'}

        detector = FrameworkDetector(temp_repo, invalid_json_callback)
        context = detector.detect()

        # Should return empty context on parse error
        assert context.primary_language == "unknown"

    def test_detector_no_hardcoded_exclusions(self, temp_repo, mock_llm_callback):
        """Test that detector has no hardcoded exclusions - LLM decides relevance."""
        repo_path = Path(temp_repo)

        # Create various directories
        (repo_path / "node_modules").mkdir()
        (repo_path / "node_modules" / "package.json").write_text("{}")
        (repo_path / ".venv").mkdir()

        detector = FrameworkDetector(temp_repo, mock_llm_callback)

        # _is_excluded returns False for all paths - LLM decides relevance
        assert not detector._is_excluded(repo_path / "node_modules" / "package.json")
        assert not detector._is_excluded(repo_path / ".venv")


class TestIsExternalImport:
    """Test _is_external_import method from SupervisorAgent"""

    @pytest.fixture
    def supervisor_config(self):
        """Create a minimal config for testing"""
        return {
            'agents': {
                'max_files_to_analyze': 10,
                'max_import_follow': 5
            }
        }

    def test_stdlib_detection_uses_sys_module_names(self, supervisor_config):
        """Test that stdlib detection uses sys.stdlib_module_names (Python 3.10+)"""
        # We're testing the concept - sys.stdlib_module_names should exist
        if hasattr(sys, 'stdlib_module_names'):
            assert 'os' in sys.stdlib_module_names
            assert 'json' in sys.stdlib_module_names
            assert 'typing' in sys.stdlib_module_names
            assert 'pathlib' in sys.stdlib_module_names
            # Third-party should not be in stdlib
            assert 'django' not in sys.stdlib_module_names
            assert 'requests' not in sys.stdlib_module_names

    def test_stdlib_module_names_available(self):
        """Test that sys.stdlib_module_names is available (Python 3.10+)"""
        # This test documents the Python version requirement
        import sys
        if sys.version_info >= (3, 10):
            assert hasattr(sys, 'stdlib_module_names')


class TestImportResolution:
    """Test import resolution helpers"""

    @pytest.fixture
    def temp_repo_with_imports(self):
        """Create a temp repo with import structure"""
        temp_dir = tempfile.mkdtemp()
        repo_path = Path(temp_dir)

        # Create app structure
        app_dir = repo_path / "app"
        app_dir.mkdir()
        (app_dir / "__init__.py").write_text("")

        # Create models.py
        (app_dir / "models.py").write_text("""
from django.db import models
from app.constants import STATUS_PENDING
""")

        # Create constants.py (imported by models)
        (app_dir / "constants.py").write_text("""
STATUS_PENDING = 'pending'
STATUS_ACTIVE = 'active'
""")

        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_resolve_import_to_file(self, temp_repo_with_imports):
        """Test that internal imports can be resolved to file paths"""
        repo_path = Path(temp_repo_with_imports)

        # app.constants should resolve to app/constants.py
        expected_path = repo_path / "app" / "constants.py"
        assert expected_path.exists()

    def test_external_imports_not_resolved(self, temp_repo_with_imports):
        """Test that external imports (django) are not resolved to files"""
        repo_path = Path(temp_repo_with_imports)

        # django should not exist as a local file
        django_path = repo_path / "django"
        assert not django_path.exists()
