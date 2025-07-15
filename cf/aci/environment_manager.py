"""Environment Manager for CodeFusion Agent Computer Interface."""

from typing import Any, Dict, List, Optional

from ..config import CfConfig
from .repo import CodeRepo


class EnvironmentManager:
    """Environment class that combines CodeRepo with internet and search
    capabilities."""

    def __init__(self, code_repo: CodeRepo, config: Optional[CfConfig] = None):
        self.code_repo = code_repo
        self.config = config or CfConfig()
        self._search_cache: Dict[str, Any] = {}

    def get_repo(self) -> CodeRepo:
        """Get the underlying code repository."""
        return self.code_repo

    def search_web(self, query: str, max_results: int = 5) -> List[Dict[str, str]]:
        """Search the web for information (placeholder implementation)."""
        # This is a placeholder - in a real implementation, you would integrate
        # with search APIs like Google Custom Search, Bing, or DuckDuckGo

        # For now, return a mock response
        return [
            {
                "title": f"Mock result for: {query}",
                "url": f"https://example.com/search?q={query.replace(' ', '+')}",
                "snippet": f"This is a mock search result for the query: {query}",
            }
        ]

    def search_documentation(self, technology: str, query: str) -> List[Dict[str, str]]:
        """Search documentation for specific technologies."""
        # Map common technologies to their documentation sites
        doc_sites = {
            "python": "https://docs.python.org/3/",
            "javascript": "https://developer.mozilla.org/",
            "react": "https://reactjs.org/docs/",
            "django": "https://docs.djangoproject.com/",
            "flask": "https://flask.palletsprojects.com/",
            "nodejs": "https://nodejs.org/docs/",
            "typescript": "https://www.typescriptlang.org/docs/",
        }

        base_url = doc_sites.get(technology.lower())
        if not base_url:
            return self.search_web(f"{technology} {query} documentation")

        # This would integrate with site-specific search APIs
        return [
            {
                "title": f"{technology.title()} Documentation: {query}",
                "url": f"{base_url}search?q={query.replace(' ', '+')}",
                "snippet": f"Official {technology} documentation for: {query}",
            }
        ]

    def analyze_file_content(self, file_path: str) -> Dict[str, Any]:
        """Analyze the content of a file and extract metadata."""
        try:
            content = self.code_repo.read_file(file_path)
            file_info = self.code_repo.get_file_info(file_path)

            analysis = {
                "file_path": file_path,
                "size": file_info.size,
                "extension": file_info.extension,
                "line_count": len(content.splitlines()),
                "char_count": len(content),
                "encoding": "utf-8",  # Assume UTF-8 for now
            }

            # Basic language detection based on extension
            language_map = {
                ".py": "python",
                ".js": "javascript",
                ".ts": "typescript",
                ".jsx": "javascript",
                ".tsx": "typescript",
                ".java": "java",
                ".cpp": "cpp",
                ".c": "c",
                ".cs": "csharp",
                ".go": "go",
                ".rs": "rust",
                ".php": "php",
                ".rb": "ruby",
                ".swift": "swift",
                ".kt": "kotlin",
                ".scala": "scala",
                ".html": "html",
                ".css": "css",
                ".scss": "scss",
                ".sass": "sass",
                ".less": "less",
                ".sql": "sql",
                ".md": "markdown",
                ".json": "json",
                ".xml": "xml",
                ".yaml": "yaml",
                ".yml": "yaml",
                ".toml": "toml",
                ".ini": "ini",
                ".cfg": "config",
                ".conf": "config",
            }

            analysis["language"] = language_map.get(
                file_info.extension.lower(), "unknown"
            )

            # Extract basic patterns for code files
            if analysis["language"] in [
                "python",
                "javascript",
                "typescript",
                "java",
                "cpp",
                "c",
            ]:
                analysis.update(
                    self._analyze_code_patterns(content, analysis["language"])
                )

            return analysis

        except Exception as e:
            return {"file_path": file_path, "error": str(e), "analysis_failed": True}

    def _analyze_code_patterns(self, content: str, language: str) -> Dict[str, Any]:
        """Extract basic code patterns from content."""
        lines = content.splitlines()
        patterns = {
            "imports": [],
            "functions": [],
            "classes": [],
            "comments_lines": 0,
            "blank_lines": 0,
        }

        for line in lines:
            stripped = line.strip()

            if not stripped:
                patterns["blank_lines"] += 1
                continue

            # Language-specific pattern detection
            if language == "python":
                if stripped.startswith("#"):
                    patterns["comments_lines"] += 1
                elif stripped.startswith(("import ", "from ")):
                    patterns["imports"].append(stripped)
                elif stripped.startswith("def "):
                    func_name = stripped.split("(")[0].replace("def ", "")
                    patterns["functions"].append(func_name)
                elif stripped.startswith("class "):
                    class_name = (
                        stripped.split("(")[0].split(":")[0].replace("class ", "")
                    )
                    patterns["classes"].append(class_name)

            elif language in ["javascript", "typescript"]:
                if stripped.startswith("//") or stripped.startswith("/*"):
                    patterns["comments_lines"] += 1
                elif "import " in stripped or "require(" in stripped:
                    patterns["imports"].append(stripped)
                elif (
                    stripped.startswith(("function ", "const ", "let ", "var "))
                    and "=" in stripped
                    and "=>" in stripped
                ):
                    # Basic function detection
                    if "function" in stripped:
                        func_name = stripped.split("function")[1].split("(")[0].strip()
                    else:
                        func_name = (
                            stripped.split("=")[0]
                            .replace("const ", "")
                            .replace("let ", "")
                            .replace("var ", "")
                            .strip()
                        )
                    patterns["functions"].append(func_name)
                elif stripped.startswith("class "):
                    class_name = stripped.split("{")[0].replace("class ", "").strip()
                    patterns["classes"].append(class_name)

        return patterns

    def get_repository_overview(self) -> Dict[str, Any]:
        """Get a comprehensive overview of the repository."""
        stats = self.code_repo.get_repository_stats()

        # Analyze file types and suggest technologies
        tech_indicators = {
            ".py": "Python",
            ".js": "JavaScript",
            ".ts": "TypeScript",
            ".jsx": "React",
            ".tsx": "React with TypeScript",
            ".java": "Java",
            ".cpp": "C++",
            ".c": "C",
            ".cs": "C#",
            ".go": "Go",
            ".rs": "Rust",
            ".php": "PHP",
            ".rb": "Ruby",
            ".swift": "Swift",
            ".kt": "Kotlin",
        }

        detected_technologies = []
        for ext, count in stats["file_types"].items():
            if ext in tech_indicators and count > 0:
                detected_technologies.append(
                    {
                        "technology": tech_indicators[ext],
                        "extension": ext,
                        "file_count": count,
                    }
                )

        # Sort by file count
        detected_technologies.sort(key=lambda x: x["file_count"], reverse=True)

        overview = {
            "repository_stats": stats,
            "detected_technologies": detected_technologies,
            "primary_language": (
                detected_technologies[0]["technology"]
                if detected_technologies
                else "Unknown"
            ),
            "project_structure": self._analyze_project_structure(),
        }

        return overview

    def _analyze_project_structure(self) -> Dict[str, Any]:
        """Analyze the project structure and identify common patterns."""
        structure = {
            "has_tests": False,
            "has_docs": False,
            "has_config": False,
            "build_system": "unknown",
            "package_manager": "unknown",
        }

        # Check for common files and directories
        common_checks = [
            ("package.json", "package_manager", "npm"),
            ("requirements.txt", "package_manager", "pip"),
            ("Pipfile", "package_manager", "pipenv"),
            ("poetry.lock", "package_manager", "poetry"),
            ("Cargo.toml", "package_manager", "cargo"),
            ("pom.xml", "build_system", "maven"),
            ("build.gradle", "build_system", "gradle"),
            ("Makefile", "build_system", "make"),
            ("CMakeLists.txt", "build_system", "cmake"),
            ("setup.py", "build_system", "setuptools"),
            ("pyproject.toml", "build_system", "modern_python"),
        ]

        for file_name, category, value in common_checks:
            if self.code_repo.exists(file_name):
                structure[category] = value

        # Check for common directory patterns
        if any(
            self.code_repo.exists(d) for d in ["tests", "test", "__tests__", "spec"]
        ):
            structure["has_tests"] = True

        if any(self.code_repo.exists(d) for d in ["docs", "documentation", "doc"]):
            structure["has_docs"] = True

        if any(
            self.code_repo.exists(f)
            for f in ["config.py", "settings.py", ".env", "config.json", "config.yaml"]
        ):
            structure["has_config"] = True

        return structure

    def suggest_exploration_strategy(self) -> List[str]:
        """Suggest an exploration strategy based on the repository."""
        overview = self.get_repository_overview()
        suggestions = []

        # Strategy based on project size
        total_files = overview["repository_stats"]["total_files"]
        if total_files < 50:
            suggestions.append(
                "Small project: Start with main entry points and core modules"
            )
        elif total_files < 500:
            suggestions.append(
                "Medium project: Focus on directory structure and key components"
            )
        else:
            suggestions.append(
                "Large project: Begin with documentation and configuration files"
            )

        # Technology-specific suggestions
        primary_lang = overview["primary_language"]
        if primary_lang == "Python":
            suggestions.append("Look for __init__.py files, setup.py, and main modules")
        elif primary_lang in ["JavaScript", "TypeScript"]:
            suggestions.append(
                "Check package.json, src/ directory, and main entry points"
            )
        elif primary_lang == "Java":
            suggestions.append(
                "Examine package structure, pom.xml/build.gradle, and main classes"
            )

        # Structure-based suggestions
        structure = overview["project_structure"]
        if structure["has_tests"]:
            suggestions.append("Review test files to understand expected behavior")
        if structure["has_docs"]:
            suggestions.append("Start with documentation for high-level understanding")
        if structure["has_config"]:
            suggestions.append("Examine configuration files for system architecture")

        return suggestions
