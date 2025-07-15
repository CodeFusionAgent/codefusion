"""Content analyzer for extracting structured information from code repositories."""

import re
from dataclasses import dataclass
from typing import Dict, List

from ..kb.knowledge_base import CodeEntity


@dataclass
class AnalyzedAnswer:
    """Structured answer with analysis details."""

    question: str
    answer: str
    commands: List[str]
    files: List[str]
    confidence: float
    sources: List[CodeEntity]


class ContentAnalyzer:
    """Analyzes repository content to answer questions intelligently."""

    def __init__(self):
        self.question_patterns = self._load_question_patterns()

    def analyze_question(
        self, question: str, entities: List[CodeEntity]
    ) -> AnalyzedAnswer:
        """Analyze entities to answer the question intelligently."""
        question_type = self._classify_question(question)

        if question_type == "testing":
            return self._analyze_testing_question(question, entities)
        elif question_type == "setup":
            return self._analyze_setup_question(question, entities)
        elif question_type == "usage":
            return self._analyze_usage_question(question, entities)
        elif question_type == "configuration":
            return self._analyze_config_question(question, entities)
        elif question_type == "deployment":
            return self._analyze_deployment_question(question, entities)
        else:
            return self._analyze_general_question(question, entities)

    def _classify_question(self, question: str) -> str:
        """Classify the question type based on keywords."""
        question_lower = question.lower()

        patterns = {
            "testing": [
                r"test.*suite",
                r"run.*test",
                r"pytest",
                r"coverage",
                r"test.*report",
                r"testing.*setup",
                r"test.*config",
                r"test.*dependencies",
            ],
            "setup": [
                r"install",
                r"setup",
                r"getting.*started",
                r"requirements",
                r"dependencies",
                r"environment",
                r"virtual.*env",
            ],
            "usage": [
                r"how.*use",
                r"example",
                r"tutorial",
                r"getting.*started",
                r"quick.*start",
                r"basic.*usage",
            ],
            "configuration": [
                r"config",
                r"settings",
                r"environment.*var",
                r"configure",
            ],
            "deployment": [r"deploy", r"production", r"docker", r"build", r"release"],
        }

        for question_type, type_patterns in patterns.items():
            for pattern in type_patterns:
                if re.search(pattern, question_lower):
                    return question_type

        return "general"

    def _analyze_testing_question(
        self, question: str, entities: List[CodeEntity]
    ) -> AnalyzedAnswer:
        """Analyze testing-related questions."""
        commands = []
        files = []
        relevant_content = []

        # Look for test configuration files
        test_files = [
            e
            for e in entities
            if any(
                keyword in e.name.lower()
                for keyword in ["test", "pytest", "coverage", "requirements"]
            )
        ]

        for entity in test_files:
            files.append(f"{entity.name} ({entity.path})")

            # Extract test commands
            entity_commands = self._extract_commands(entity.content)
            commands.extend(entity_commands)

            # Extract test configuration
            if "requirements" in entity.name.lower() and "test" in entity.name.lower():
                test_deps = self._extract_test_dependencies(entity.content)
                if test_deps:
                    relevant_content.append(
                        f"Test dependencies: {', '.join(test_deps[:5])}"
                    )

            if entity.name.lower() in ["pyproject.toml", "setup.cfg", "pytest.ini"]:
                test_config = self._extract_test_config(entity.content, entity.name)
                relevant_content.extend(test_config)

        # Synthesize answer
        answer_parts = []

        # Installation step
        if any("requirements-test" in f for f in files):
            answer_parts.append(
                "1. **Install test dependencies:**\n   ```bash\n   "
                "pip install -r requirements-tests.txt\n   ```"
            )

        # Running tests
        if any("pytest" in cmd for cmd in commands) or any(
            "pytest" in content for content in relevant_content
        ):
            answer_parts.append(
                "2. **Run the complete test suite:**\n   ```bash\n   pytest\n   ```"
            )
        else:
            answer_parts.append(
                "2. **Run tests:**\n   ```bash\n   python -m pytest\n   ```"
            )

        # Coverage
        if any("coverage" in content for content in relevant_content):
            answer_parts.append(
                "3. **Generate coverage reports:**\n   ```bash\n   pytest --cov\n   pytest --cov --cov-report=html\n   ```"
            )

        # Configuration details
        if relevant_content:
            config_info = "\\n".join(
                f"   - {content}" for content in relevant_content[:3]
            )
            answer_parts.append(f"**Test Configuration:**\\n{config_info}")

        main_answer = (
            "\\n\\n".join(answer_parts)
            if answer_parts
            else "Test configuration found in the repository."
        )

        return AnalyzedAnswer(
            question=question,
            answer=main_answer,
            commands=commands,
            files=files,
            confidence=0.8 if answer_parts else 0.4,
            sources=test_files,
        )

    def _analyze_setup_question(
        self, question: str, entities: List[CodeEntity]
    ) -> AnalyzedAnswer:
        """Analyze setup/installation questions."""
        commands = []
        files = []

        # Look for setup files
        setup_files = [
            e
            for e in entities
            if any(
                keyword in e.name.lower()
                for keyword in [
                    "readme",
                    "requirements",
                    "setup",
                    "pyproject",
                    "install",
                ]
            )
        ]

        install_steps = []

        for entity in setup_files:
            files.append(f"{entity.name} ({entity.path})")

            # Extract installation commands
            entity_commands = self._extract_commands(entity.content)
            commands.extend(entity_commands)

            # Look for installation instructions in README
            if "readme" in entity.name.lower():
                install_instructions = self._extract_install_instructions(
                    entity.content
                )
                install_steps.extend(install_instructions)

        # Standard Python setup if pyproject.toml or setup.py found
        if any("pyproject.toml" in f or "setup.py" in f for f in files):
            install_steps.insert(0, "pip install -e .")

        # Create answer
        if install_steps:
            formatted_steps = "\\n".join(
                f"{i + 1}. `{step}`" for i, step in enumerate(install_steps[:5])
            )
            answer = f"**Installation Steps:**\\n{formatted_steps}"
        else:
            answer = "Installation instructions can be found in the repository files."

        return AnalyzedAnswer(
            question=question,
            answer=answer,
            commands=commands,
            files=files,
            confidence=0.7 if install_steps else 0.4,
            sources=setup_files,
        )

    def _analyze_usage_question(
        self, question: str, entities: List[CodeEntity]
    ) -> AnalyzedAnswer:
        """Analyze usage/example questions."""
        files = []
        examples = []

        # Look for documentation and example files
        usage_files = [
            e
            for e in entities
            if any(
                keyword in e.path.lower()
                for keyword in ["readme", "doc", "example", "tutorial", "guide"]
            )
        ]

        for entity in usage_files:
            files.append(f"{entity.name} ({entity.path})")

            # Extract code examples
            code_examples = self._extract_code_examples(entity.content)
            examples.extend(code_examples)

        if examples:
            formatted_examples = "\\n\\n".join(
                f"```python\\n{ex}\\n```" for ex in examples[:2]
            )
            answer = f"**Usage Examples:**\\n{formatted_examples}"
        else:
            answer = "Usage examples and documentation found in the repository."

        return AnalyzedAnswer(
            question=question,
            answer=answer,
            commands=[],
            files=files,
            confidence=0.6 if examples else 0.4,
            sources=usage_files,
        )

    def _analyze_config_question(
        self, question: str, entities: List[CodeEntity]
    ) -> AnalyzedAnswer:
        """Analyze configuration questions."""
        files = []
        config_info = []

        config_files = [
            e
            for e in entities
            if any(
                keyword in e.name.lower()
                for keyword in ["config", "settings", ".env", "pyproject", "setup"]
            )
        ]

        for entity in config_files:
            files.append(f"{entity.name} ({entity.path})")

            if entity.name.endswith(".toml"):
                sections = self._extract_toml_sections(entity.content)
                config_info.extend([f"[{section}]" for section in sections[:3]])

        if config_info:
            formatted_config = "\\n".join(f"- {info}" for info in config_info)
            answer = f"**Configuration sections found:**\\n{formatted_config}"
        else:
            answer = "Configuration files found in the repository."

        return AnalyzedAnswer(
            question=question,
            answer=answer,
            commands=[],
            files=files,
            confidence=0.6,
            sources=config_files,
        )

    def _analyze_deployment_question(
        self, question: str, entities: List[CodeEntity]
    ) -> AnalyzedAnswer:
        """Analyze deployment questions."""
        files = []
        deploy_info = []

        deploy_files = [
            e
            for e in entities
            if any(
                keyword in e.name.lower()
                for keyword in ["docker", "deploy", "ci", "workflow", "action"]
            )
        ]

        for entity in deploy_files:
            files.append(f"{entity.name} ({entity.path})")

            if "docker" in entity.name.lower():
                deploy_info.append(f"Docker configuration: {entity.name}")
            elif "workflow" in entity.path.lower():
                deploy_info.append(f"CI/CD workflow: {entity.name}")

        if deploy_info:
            formatted_deploy = "\\n".join(f"- {info}" for info in deploy_info)
            answer = f"**Deployment configuration:**\\n{formatted_deploy}"
        else:
            answer = "Deployment configuration files found in the repository."

        return AnalyzedAnswer(
            question=question,
            answer=answer,
            commands=[],
            files=files,
            confidence=0.5,
            sources=deploy_files,
        )

    def _analyze_general_question(
        self, question: str, entities: List[CodeEntity]
    ) -> AnalyzedAnswer:
        """Analyze general questions."""
        files = [f"{e.name} ({e.path})" for e in entities[:5]]

        # Group entities by type
        entity_summary = {}
        for entity in entities:
            entity_type = entity.type
            if entity_type not in entity_summary:
                entity_summary[entity_type] = []
            entity_summary[entity_type].append(entity.name)

        summary_lines = []
        for entity_type, names in entity_summary.items():
            summary_lines.append(f"- {entity_type.title()}s: {', '.join(names[:3])}")
            if len(names) > 3:
                summary_lines[-1] += f" (and {len(names) - 3} more)"

        answer = "**Found relevant code:**\\n" + "\\n".join(summary_lines)

        return AnalyzedAnswer(
            question=question,
            answer=answer,
            commands=[],
            files=files,
            confidence=0.3,
            sources=entities[:5],
        )

    def _extract_commands(self, content: str) -> List[str]:
        """Extract command-line commands from content."""
        commands = []

        # Patterns for different command formats
        patterns = [
            r"```(?:bash|shell|sh)\\n([^`]+)```",  # Code blocks
            r"`([^`]*(?:pip|python|pytest|npm|yarn)[^`]*)`",  # Inline code with tools
            r"^\\s*\\$\\s*(.+)$",  # Shell prompt lines
            r"^\\s*([a-z-]+(?:\\s+[a-z0-9._-]+)+)\\s*$",  # Simple command lines
        ]

        for pattern in patterns:
            matches = re.findall(pattern, content, re.MULTILINE | re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    match = match[0] if match else ""

                # Clean up the command
                cmd = match.strip().replace("\\n", " ").strip()
                if cmd and len(cmd) > 3 and len(cmd) < 100:  # Reasonable command length
                    commands.append(cmd)

        return list(set(commands))  # Remove duplicates

    def _extract_test_dependencies(self, content: str) -> List[str]:
        """Extract test dependencies from requirements files."""
        deps = []
        for line in content.split("\\n"):
            line = line.strip()
            if line and not line.startswith("#") and not line.startswith("-"):
                # Extract package name (before version specifiers)
                pkg = re.split(r"[>=<~!]", line)[0].strip()
                if pkg:
                    deps.append(pkg)
        return deps

    def _extract_test_config(self, content: str, filename: str) -> List[str]:
        """Extract test configuration details."""
        config_info = []

        if filename.endswith(".toml"):
            # Look for pytest and coverage sections
            if "[tool.pytest" in content:
                config_info.append("Pytest configuration found in pyproject.toml")
            if "[tool.coverage" in content:
                config_info.append("Coverage configuration found in pyproject.toml")

        return config_info

    def _extract_install_instructions(self, content: str) -> List[str]:
        """Extract installation instructions from README files."""
        instructions = []

        # Look for installation section
        lines = content.split("\\n")
        in_install_section = False

        for line in lines:
            line_lower = line.lower()

            # Check for installation section headers
            if any(
                keyword in line_lower
                for keyword in ["install", "setup", "getting started"]
            ):
                if line.startswith("#") or line.startswith("##"):
                    in_install_section = True
                    continue

            # Stop at next major section
            if (
                in_install_section
                and line.startswith("#")
                and not any(keyword in line_lower for keyword in ["install", "setup"])
            ):
                break

            # Extract commands from installation section
            if in_install_section:
                # Look for code blocks or command patterns
                if line.strip().startswith("pip ") or line.strip().startswith(
                    "python "
                ):
                    instructions.append(line.strip())
                elif "`pip " in line or "`python " in line:
                    # Extract from inline code
                    cmd_match = re.search(r"`([^`]*(?:pip|python)[^`]*)`", line)
                    if cmd_match:
                        instructions.append(cmd_match.group(1))

        return instructions

    def _extract_code_examples(self, content: str) -> List[str]:
        """Extract code examples from documentation."""
        examples = []

        # Look for code blocks
        code_block_pattern = r"```(?:python|py)?\\n([^`]+)```"
        matches = re.findall(code_block_pattern, content, re.DOTALL)

        for match in matches:
            if (
                len(match.strip()) > 20 and len(match.strip()) < 500
            ):  # Reasonable example size
                examples.append(match.strip())

        return examples

    def _extract_toml_sections(self, content: str) -> List[str]:
        """Extract section names from TOML files."""
        sections = []
        for line in content.split("\\n"):
            line = line.strip()
            if (
                line.startswith("[")
                and line.endswith("]")
                and not line.startswith("[[")
            ):
                section = line[1:-1]
                sections.append(section)
        return sections

    def _load_question_patterns(self) -> Dict[str, List[str]]:
        """Load patterns for different question types."""
        return {
            "testing": [
                "how to run tests",
                "test suite execution",
                "pytest commands",
                "coverage reports",
            ],
            "setup": ["how to install", "installation steps", "setup instructions"],
        }
