"""
FrameworkDetector - LLM-driven framework and pattern detection.

Analyzes a codebase to detect frameworks, languages, and architectural patterns,
then generates context-specific guidance for the CodeAgent.
"""

import json
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass, field, asdict


@dataclass
class FrameworkContext:
    """Detected framework context for a repository."""

    # Primary framework/language
    primary_language: str = "unknown"
    frameworks: List[str] = field(default_factory=list)

    # LLM-generated analysis guidance
    key_file_patterns: List[str] = field(default_factory=list)
    important_directories: List[str] = field(default_factory=list)
    analysis_hints: List[str] = field(default_factory=list)

    # Metadata
    detection_hash: str = ""  # Hash of files used for detection (for cache invalidation)

    def to_prompt_section(self) -> str:
        """Convert to a prompt section for CodeAgent."""
        if not self.frameworks and self.primary_language == "unknown":
            return ""

        lines = ["CODEBASE CONTEXT (auto-detected):"]

        if self.primary_language != "unknown":
            lines.append(f"- Primary language: {self.primary_language}")

        if self.frameworks:
            lines.append(f"- Frameworks: {', '.join(self.frameworks)}")

        if self.key_file_patterns:
            lines.append("- Key file patterns to examine:")
            for pattern in self.key_file_patterns[:5]:  # Limit to avoid prompt bloat
                lines.append(f"  * {pattern}")

        if self.important_directories:
            lines.append("- Important directories:")
            for dir_hint in self.important_directories[:5]:
                lines.append(f"  * {dir_hint}")

        if self.analysis_hints:
            lines.append("- Analysis hints:")
            for hint in self.analysis_hints[:5]:
                lines.append(f"  * {hint}")

        return "\n".join(lines)


class FrameworkDetector:
    """
    LLM-driven framework and pattern detector.

    Analyzes key files in a repository to detect the framework/language
    and generate context-specific guidance for code analysis.
    """

    def __init__(
        self,
        repo_path: str,
        llm_callback: Callable[[str, str], Dict[str, Any]],
        cache_dir: Optional[str] = None
    ):
        """
        Initialize the framework detector.

        Args:
            repo_path: Path to the repository root
            llm_callback: Function to call LLM (prompt, system_prompt) -> response
            cache_dir: Optional cache directory (defaults to .codefusion in repo)
        """
        self.repo_path = Path(repo_path)
        self.llm_callback = llm_callback
        self.cache_dir = Path(cache_dir) if cache_dir else self.repo_path / ".codefusion"
        self.cache_file = self.cache_dir / "framework_context.json"

    def detect(self, force_refresh: bool = False) -> FrameworkContext:
        """
        Detect framework and patterns for the repository.

        Args:
            force_refresh: If True, bypass cache and re-detect

        Returns:
            FrameworkContext with detected information
        """
        # Compute hash of indicator files for cache validation
        current_hash = self._compute_indicator_hash()

        # Try to load from cache
        if not force_refresh:
            cached = self._load_cache()
            if cached and cached.detection_hash == current_hash:
                return cached

        # Gather context for LLM detection
        context = self._gather_detection_context()

        if not context:
            # No indicator files found, return empty context
            return FrameworkContext()

        # Ask LLM to analyze and provide guidance
        framework_context = self._llm_detect(context)

        # Set hash for cache validation
        framework_context.detection_hash = current_hash

        # Cache the result
        self._save_cache(framework_context)

        return framework_context

    def _gather_detection_context(self) -> str:
        """Gather file contents for LLM to analyze."""
        context_parts = []

        # Dynamically discover and read root-level files (config, build, manifest files)
        root_files_read = 0
        for item in sorted(self.repo_path.iterdir()):
            if item.is_file() and not item.name.startswith('.'):
                content = self._safe_read(item, max_lines=100)
                if content:
                    context_parts.append(f"=== {item.name} ===\n{content}")
                    root_files_read += 1
                    if root_files_read >= 10:
                        break

        # Read a sample of source files (first 3 text files found)
        source_samples = []
        for match in self.repo_path.rglob('*'):
            if match.is_file() and not match.name.startswith('.'):
                content = self._safe_read(match, max_lines=50)
                if content:  # Successfully read as text
                    rel_path = match.relative_to(self.repo_path)
                    source_samples.append(f"=== {rel_path} (sample) ===\n{content}")
                    if len(source_samples) >= 3:
                        break

        context_parts.extend(source_samples)

        # Get directory structure (top 2 levels)
        dir_structure = self._get_directory_structure(max_depth=2)
        if dir_structure:
            context_parts.append(f"=== Directory Structure ===\n{dir_structure}")

        return "\n\n".join(context_parts)

    def _llm_detect(self, context: str) -> FrameworkContext:
        """Use LLM to detect framework and generate guidance."""

        system_prompt = """You are a code analysis expert. Analyze the provided files and directory structure to identify:
1. The primary programming language
2. Frameworks being used (web frameworks, ORMs, testing, etc.)
3. Key file patterns that are important for understanding this codebase
4. Important directories to examine
5. Analysis hints specific to this technology stack

Respond ONLY with a JSON object in this exact format:
{
    "primary_language": "<detected language>",
    "frameworks": ["<detected frameworks>"],
    "key_file_patterns": [
        "<pattern 1 you discovered in this codebase>",
        "<pattern 2 you discovered in this codebase>",
        "<pattern 3 you discovered in this codebase>"
    ],
    "important_directories": [
        "<directory 1> - <its purpose>",
        "<directory 2> - <its purpose>"
    ],
    "analysis_hints": [
        "<hint 1 based on what you found>",
        "<hint 2 based on what you found>",
        "<hint 3 based on what you found>"
    ]
}

Focus on identifying:
- Common file patterns that contain important logic in this codebase
- Directories that hold key code
- Patterns unique to this codebase that would help understand how it works

Be concise. Limit each list to 5 items maximum. Focus on patterns most useful for code analysis."""

        user_prompt = f"""Analyze this codebase and provide framework detection results:

{context}

Respond with ONLY the JSON object, no other text."""

        try:
            response = self.llm_callback(user_prompt, system_prompt)

            if not response.get('success'):
                return FrameworkContext()

            content = response.get('content', '')

            # Parse JSON from response
            # Handle potential markdown code blocks
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0]
            elif '```' in content:
                content = content.split('```')[1].split('```')[0]

            data = json.loads(content.strip())

            return FrameworkContext(
                primary_language=data.get('primary_language', 'unknown'),
                frameworks=data.get('frameworks', []),
                key_file_patterns=data.get('key_file_patterns', []),
                important_directories=data.get('important_directories', []),
                analysis_hints=data.get('analysis_hints', [])
            )

        except (json.JSONDecodeError, KeyError, IndexError) as e:
            # LLM response wasn't valid JSON, return empty context
            return FrameworkContext()

    def _compute_indicator_hash(self) -> str:
        """Compute hash of root-level files for cache invalidation."""
        hasher = hashlib.md5()

        for item in sorted(self.repo_path.iterdir()):
            if item.is_file() and not item.name.startswith('.'):
                try:
                    stat = item.stat()
                    hasher.update(f"{item.name}:{stat.st_mtime}:{stat.st_size}".encode())
                except OSError:
                    pass

        return hasher.hexdigest()[:16]

    def _load_cache(self) -> Optional[FrameworkContext]:
        """Load cached framework context."""
        if not self.cache_file.exists():
            return None

        try:
            with open(self.cache_file, 'r') as f:
                data = json.load(f)
            return FrameworkContext(**data)
        except (json.JSONDecodeError, TypeError, KeyError):
            return None

    def _save_cache(self, context: FrameworkContext) -> None:
        """Save framework context to cache."""
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            with open(self.cache_file, 'w') as f:
                json.dump(asdict(context), f, indent=2)
        except OSError:
            pass  # Cache write failure is non-critical

    def _safe_read(self, filepath: Path, max_lines: int = 100) -> str:
        """Safely read a file with line limit."""
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                lines = []
                for i, line in enumerate(f):
                    if i >= max_lines:
                        lines.append(f"... (truncated at {max_lines} lines)")
                        break
                    lines.append(line.rstrip())
                return '\n'.join(lines)
        except (OSError, UnicodeDecodeError):
            return ""

    def _is_excluded(self, path: Path) -> bool:
        """Check if path should be excluded from sampling."""
        return False

    def _get_directory_structure(self, max_depth: int = 2) -> str:
        """Get top-level directory structure."""
        lines = []

        def _walk(path: Path, prefix: str = "", depth: int = 0):
            if depth > max_depth:
                return

            try:
                entries = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
                dirs = [e for e in entries if e.is_dir() and not e.name.startswith('.') and not self._is_excluded(e)]

                for i, entry in enumerate(dirs[:10]):  # Limit directories shown
                    is_last = i == len(dirs) - 1 or i == 9
                    connector = "└── " if is_last else "├── "
                    lines.append(f"{prefix}{connector}{entry.name}/")

                    if depth < max_depth:
                        extension = "    " if is_last else "│   "
                        _walk(entry, prefix + extension, depth + 1)

                if len(dirs) > 10:
                    lines.append(f"{prefix}... ({len(dirs) - 10} more directories)")

            except OSError:
                pass

        _walk(self.repo_path)
        return '\n'.join(lines)
