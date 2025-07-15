"""Sense-then-act exploration strategy for CodeFusion."""

import os
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

try:
    import litellm

    LITELLM_AVAILABLE = True
except ImportError:
    LITELLM_AVAILABLE = False

from ..aci.system_access import SystemAccess
from ..config import CfConfig
from ..kb.knowledge_base import CodeEntity, CodeKB


@dataclass
class SenseResult:
    """Result of sensing the environment."""

    timestamp: float
    focus_area: str
    observations: List[str]
    entities_found: List[CodeEntity]
    confidence: float
    next_actions: List[str]


@dataclass
class ActionResult:
    """Result of taking an action."""

    action_type: str
    target: str
    findings: List[str]
    new_entities: List[CodeEntity]
    insights: List[str]
    success: bool
    execution_time: float


@dataclass
class SenseActCycle:
    """Single sense-act cycle."""

    cycle_id: int
    sense_result: SenseResult
    action_result: ActionResult
    learning: List[str]
    next_focus: str


@dataclass
class ExplorationSession:
    """Complete exploration session."""

    question: str
    cycles: List[SenseActCycle]
    total_entities: List[CodeEntity]
    key_insights: List[str]
    final_answer: str
    success_rate: float


class SenseThenActAgent:
    """Agent that senses environment then acts iteratively."""

    def __init__(self, config: CfConfig, kb: CodeKB):
        self.config = config
        self.kb = kb
        self.system_access = SystemAccess()
        self.llm_available = LITELLM_AVAILABLE and self.system_access.has_llm_config()

        # Internal state
        self.current_focus = ""
        self.explored_areas = set()
        self.accumulated_knowledge = []

        if self.llm_available:
            self._setup_llm()

    def _setup_llm(self):
        """Setup LLM configuration."""
        llm_config = self.system_access.get_llm_config()
        if llm_config["api_key"]:
            os.environ["OPENAI_API_KEY"] = llm_config["api_key"]
        if llm_config["base_url"]:
            os.environ["OPENAI_BASE_URL"] = llm_config["base_url"]

    def explore_codebase(
        self, question: str, repo_path: str, max_cycles: int = 5
    ) -> ExplorationSession:
        """Explore codebase using sense-then-act strategy."""
        print("🌍 Starting Sense-then-Act Exploration")
        print(f"🎯 Question: {question}")
        print(f"📂 Repository: {repo_path}")
        print(f"🔄 Max Cycles: {max_cycles}")
        print()

        cycles = []
        total_entities = []
        key_insights = []

        # Initialize focus based on question
        self.current_focus = self._determine_initial_focus(question)

        for cycle_num in range(1, max_cycles + 1):
            print(f"🔍 Cycle {cycle_num}: Sensing {self.current_focus}")

            # Sense phase
            sense_result = self._sense_environment(
                question, repo_path, self.current_focus
            )

            # Act phase
            action_result = self._act_on_sensing(sense_result, repo_path)

            # Learning phase
            learning = self._learn_from_cycle(sense_result, action_result)

            # Determine next focus
            next_focus = self._determine_next_focus(
                sense_result, action_result, question
            )

            cycle = SenseActCycle(
                cycle_id=cycle_num,
                sense_result=sense_result,
                action_result=action_result,
                learning=learning,
                next_focus=next_focus,
            )

            cycles.append(cycle)
            total_entities.extend(action_result.new_entities)
            key_insights.extend(action_result.insights)

            # Update state
            self.current_focus = next_focus
            self.explored_areas.add(sense_result.focus_area)
            self.accumulated_knowledge.extend(learning)

            print(
                f"   ✅ Found {len(action_result.new_entities)} entities, "
                f"{len(action_result.insights)} insights"
            )

            # Check if we should continue
            if self._should_stop_exploration(cycle, question):
                print("   ⏹️  Stopping exploration - sufficient information gathered")
                break

            print(f"   ➡️  Next focus: {next_focus}")
            print()

        # Generate final answer
        final_answer = self._synthesize_final_answer(
            question, cycles, total_entities, key_insights
        )

        success_rate = len([c for c in cycles if c.action_result.success]) / len(cycles)

        return ExplorationSession(
            question=question,
            cycles=cycles,
            total_entities=total_entities,
            key_insights=key_insights,
            final_answer=final_answer,
            success_rate=success_rate,
        )

    def _determine_initial_focus(self, question: str) -> str:
        """Determine initial focus area based on question."""
        question_lower = question.lower()

        if any(word in question_lower for word in ["test", "testing"]):
            return "testing_infrastructure"
        elif any(word in question_lower for word in ["config", "setup", "install"]):
            return "configuration_setup"
        elif any(word in question_lower for word in ["api", "endpoint", "route"]):
            return "api_structure"
        elif any(word in question_lower for word in ["database", "db", "model"]):
            return "data_layer"
        elif any(word in question_lower for word in ["deploy", "production"]):
            return "deployment_setup"
        else:
            return "project_overview"

    def _sense_environment(
        self, question: str, repo_path: str, focus_area: str
    ) -> SenseResult:
        """Sense the current environment and gather observations."""
        observations = []
        entities_found = []
        confidence = 0.0

        repo_path = Path(repo_path)

        # Observe directory structure
        structure_obs = self._observe_directory_structure(repo_path, focus_area)
        observations.extend(structure_obs)

        # Observe files based on focus area
        file_obs, file_entities = self._observe_relevant_files(repo_path, focus_area)
        observations.extend(file_obs)
        entities_found.extend(file_entities)

        # Query knowledge base for related entities
        kb_entities = self._query_kb_for_focus(focus_area)
        entities_found.extend(kb_entities)

        # Calculate confidence based on findings
        confidence = min(1.0, len(observations) * 0.1 + len(entities_found) * 0.05)

        # Determine next actions based on observations
        next_actions = self._determine_next_actions(observations, focus_area)

        return SenseResult(
            timestamp=time.time(),
            focus_area=focus_area,
            observations=observations,
            entities_found=entities_found,
            confidence=confidence,
            next_actions=next_actions,
        )

    def _observe_directory_structure(
        self, repo_path: Path, focus_area: str
    ) -> List[str]:
        """Observe directory structure relevant to focus area."""
        observations = []

        try:
            # Focus-specific directory patterns
            focus_patterns = {
                "testing_infrastructure": ["test", "tests", "spec", "__tests__"],
                "configuration_setup": ["config", "settings", "conf", "env"],
                "api_structure": ["api", "routes", "endpoints", "controllers"],
                "data_layer": ["models", "database", "db", "schema"],
                "deployment_setup": ["deploy", "docker", "k8s", "infra"],
                "project_overview": ["src", "lib", "app", "main"],
            }

            patterns = focus_patterns.get(focus_area, [])

            for item in repo_path.iterdir():
                if item.is_dir() and not item.name.startswith("."):
                    # Check if directory matches focus patterns
                    if any(pattern in item.name.lower() for pattern in patterns):
                        file_count = len(list(item.glob("**/*")))
                        observations.append(
                            f"Found {focus_area} directory: {item.name} "
                            f"({file_count} items)"
                        )

                    # General directory observation
                    elif focus_area == "project_overview":
                        file_count = len(list(item.glob("*")))
                        observations.append(
                            f"Directory: {item.name} ({file_count} items)"
                        )

        except Exception as e:
            observations.append(f"Error observing directory structure: {e}")

        return observations

    def _observe_relevant_files(
        self, repo_path: Path, focus_area: str
    ) -> Tuple[List[str], List[CodeEntity]]:
        """Observe files relevant to the focus area."""
        observations = []
        entities = []

        try:
            # Focus-specific file patterns
            focus_files = {
                "testing_infrastructure": [
                    "test_*.py",
                    "*_test.py",
                    "pytest.ini",
                    "tox.ini",
                    "conftest.py",
                ],
                "configuration_setup": [
                    "config.*",
                    "settings.*",
                    "requirements.txt",
                    "setup.py",
                    "pyproject.toml",
                ],
                "api_structure": [
                    "*api*.py",
                    "*route*.py",
                    "*endpoint*.py",
                    "*controller*.py",
                ],
                "data_layer": ["*model*.py", "*schema*.py", "*database*.py", "*db*.py"],
                "deployment_setup": [
                    "Dockerfile",
                    "docker-compose.*",
                    "*.yml",
                    "*.yaml",
                    "deploy*",
                ],
                "project_overview": [
                    "main.py",
                    "app.py",
                    "__init__.py",
                    "README.*",
                    "*.md",
                ],
            }

            patterns = focus_files.get(focus_area, [])

            for pattern in patterns:
                for file_path in repo_path.glob(f"**/{pattern}"):
                    if file_path.is_file():
                        observations.append(
                            f"Found {focus_area} file: {file_path.name}"
                        )

                        # Create entity if not too large
                        if file_path.stat().st_size < 100000:  # 100KB limit
                            try:
                                with open(file_path, "r", encoding="utf-8") as f:
                                    content = f.read()

                                entity = CodeEntity(
                                    id=f"file_{file_path.name}",
                                    name=file_path.name,
                                    type="file",
                                    path=str(file_path),
                                    content=content,
                                    language=self._detect_language(file_path),
                                    size=len(content),
                                    created_at=datetime.now(),
                                    metadata={"focus_area": focus_area},
                                )
                                entities.append(entity)
                            except Exception:
                                continue

        except Exception as e:
            observations.append(f"Error observing files: {e}")

        return observations, entities

    def _detect_language(self, file_path: Path) -> str:
        """Detect programming language from file extension."""
        extension_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".java": "java",
            ".cpp": "cpp",
            ".c": "c",
            ".rs": "rust",
            ".go": "go",
            ".rb": "ruby",
            ".php": "php",
            ".md": "markdown",
            ".yml": "yaml",
            ".yaml": "yaml",
            ".json": "json",
            ".xml": "xml",
            ".html": "html",
            ".css": "css",
        }

        return extension_map.get(file_path.suffix.lower(), "unknown")

    def _query_kb_for_focus(self, focus_area: str) -> List[CodeEntity]:
        """Query knowledge base for entities related to focus area."""
        try:
            # Search for entities related to focus area
            search_terms = {
                "testing_infrastructure": "test",
                "configuration_setup": "config",
                "api_structure": "api",
                "data_layer": "model",
                "deployment_setup": "deploy",
                "project_overview": "",
            }

            search_term = search_terms.get(focus_area, "")
            return self.kb.search_entities(search_term, limit=10)

        except Exception:
            return []

    def _determine_next_actions(
        self, observations: List[str], focus_area: str
    ) -> List[str]:
        """Determine next actions based on observations."""
        actions = []

        # Count observations by type
        file_obs = len([obs for obs in observations if "file" in obs.lower()])
        dir_obs = len([obs for obs in observations if "directory" in obs.lower()])

        if file_obs > 0:
            actions.append("analyze_file_contents")
        if dir_obs > 0:
            actions.append("explore_directory_structure")

        # Focus-specific actions
        if focus_area == "testing_infrastructure":
            actions.extend(["analyze_test_patterns", "identify_test_frameworks"])
        elif focus_area == "configuration_setup":
            actions.extend(["parse_config_files", "identify_dependencies"])
        elif focus_area == "api_structure":
            actions.extend(["map_api_endpoints", "analyze_request_handlers"])

        return actions[:3]  # Limit to 3 actions

    def _act_on_sensing(
        self, sense_result: SenseResult, repo_path: str
    ) -> ActionResult:
        """Act based on sensing results."""
        start_time = time.time()
        findings = []
        new_entities = []
        insights = []
        success = True

        try:
            # Execute each action
            for action in sense_result.next_actions:
                action_findings = self._execute_action(action, sense_result, repo_path)
                findings.extend(action_findings)

            # Generate insights from findings
            insights = self._generate_insights(findings, sense_result.focus_area)

            # Extract new entities from findings
            new_entities = self._extract_entities_from_findings(findings)

        except Exception as e:
            findings.append(f"Error during action execution: {e}")
            success = False

        execution_time = time.time() - start_time

        return ActionResult(
            action_type="sense_act_cycle",
            target=sense_result.focus_area,
            findings=findings,
            new_entities=new_entities,
            insights=insights,
            success=success,
            execution_time=execution_time,
        )

    def _execute_action(
        self, action: str, sense_result: SenseResult, repo_path: str
    ) -> List[str]:
        """Execute a specific action."""
        findings = []

        if action == "analyze_file_contents":
            for entity in sense_result.entities_found:
                if entity.type == "file":
                    analysis = self._analyze_file_for_patterns(entity)
                    findings.append(analysis)

        elif action == "explore_directory_structure":
            structure_analysis = self._deep_analyze_structure(
                repo_path, sense_result.focus_area
            )
            findings.extend(structure_analysis)

        elif action == "analyze_test_patterns":
            test_analysis = self._analyze_test_patterns(sense_result.entities_found)
            findings.extend(test_analysis)

        elif action == "identify_test_frameworks":
            framework_analysis = self._identify_frameworks(sense_result.entities_found)
            findings.extend(framework_analysis)

        elif action == "parse_config_files":
            config_analysis = self._parse_configuration_files(
                sense_result.entities_found
            )
            findings.extend(config_analysis)

        return findings

    def _analyze_file_for_patterns(self, entity: CodeEntity) -> str:
        """Analyze a file for patterns."""
        content = entity.content
        lines = content.split("\n")

        patterns = {
            "classes": len(
                [line for line in lines if line.strip().startswith("class ")]
            ),
            "functions": len(
                [line for line in lines if line.strip().startswith("def ")]
            ),
            "imports": len(
                [
                    line
                    for line in lines
                    if line.strip().startswith("import ")
                    or line.strip().startswith("from ")
                ]
            ),
            "comments": len([line for line in lines if line.strip().startswith("#")]),
            "docstrings": content.count('"""') // 2,
        }

        return f"File {entity.name} patterns: {patterns}"

    def _deep_analyze_structure(self, repo_path: str, focus_area: str) -> List[str]:
        """Deep analysis of directory structure."""
        return [f"Deep structure analysis for {focus_area} in {repo_path}"]

    def _analyze_test_patterns(self, entities: List[CodeEntity]) -> List[str]:
        """Analyze test patterns in entities."""
        test_files = [e for e in entities if "test" in e.name.lower()]
        return [f"Found {len(test_files)} test files with various patterns"]

    def _identify_frameworks(self, entities: List[CodeEntity]) -> List[str]:
        """Identify frameworks used in entities."""
        frameworks = set()

        for entity in entities:
            if "pytest" in entity.content:
                frameworks.add("pytest")
            if "unittest" in entity.content:
                frameworks.add("unittest")
            if "fastapi" in entity.content:
                frameworks.add("fastapi")
            if "django" in entity.content:
                frameworks.add("django")

        return [f"Detected frameworks: {', '.join(frameworks)}"]

    def _parse_configuration_files(self, entities: List[CodeEntity]) -> List[str]:
        """Parse configuration files."""
        config_files = [
            e
            for e in entities
            if any(
                ext in e.name.lower()
                for ext in [".ini", ".yaml", ".yml", ".json", ".toml"]
            )
        ]
        return [f"Found {len(config_files)} configuration files"]

    def _generate_insights(self, findings: List[str], focus_area: str) -> List[str]:
        """Generate insights from findings."""
        insights = []

        for finding in findings:
            if "patterns" in finding:
                insights.append(f"Code organization insight: {finding}")
            elif "frameworks" in finding:
                insights.append(f"Technology stack insight: {finding}")
            elif "files" in finding:
                insights.append(f"Project structure insight: {finding}")

        return insights

    def _extract_entities_from_findings(self, findings: List[str]) -> List[CodeEntity]:
        """Extract entities from findings."""
        # This would extract entities based on findings
        # For now, return empty list
        return []

    def _learn_from_cycle(
        self, sense_result: SenseResult, action_result: ActionResult
    ) -> List[str]:
        """Learn from the sense-act cycle."""
        learning = []

        # Learn from confidence levels
        if sense_result.confidence > 0.8:
            learning.append(f"High confidence in {sense_result.focus_area} exploration")
        elif sense_result.confidence < 0.3:
            learning.append(
                f"Low confidence in {sense_result.focus_area} - needs deeper exploration"
            )

        # Learn from action success
        if action_result.success:
            learning.append(f"Successful action execution in {sense_result.focus_area}")
        else:
            learning.append(f"Action execution issues in {sense_result.focus_area}")

        # Learn from insights
        if len(action_result.insights) > 0:
            learning.append(
                f"Generated {len(action_result.insights)} insights from {sense_result.focus_area}"
            )

        return learning

    def _determine_next_focus(
        self, sense_result: SenseResult, action_result: ActionResult, question: str
    ) -> str:
        """Determine next focus area based on cycle results."""
        current_focus = sense_result.focus_area

        # If current focus was highly successful, explore related areas
        if sense_result.confidence > 0.7 and action_result.success:
            focus_transitions = {
                "testing_infrastructure": "configuration_setup",
                "configuration_setup": "api_structure",
                "api_structure": "data_layer",
                "data_layer": "deployment_setup",
                "deployment_setup": "project_overview",
                "project_overview": "testing_infrastructure",
            }
            return focus_transitions.get(current_focus, "project_overview")

        # If current focus had low confidence, try a different approach
        elif sense_result.confidence < 0.3:
            return "project_overview"  # Fall back to overview

        # Default progression
        return "project_overview"

    def _should_stop_exploration(self, cycle: SenseActCycle, question: str) -> bool:
        """Determine if exploration should stop."""
        # Stop if high confidence and successful action
        if (
            cycle.sense_result.confidence > 0.8
            and cycle.action_result.success
            and len(cycle.action_result.insights) > 2
        ):
            return True

        # Stop if we've explored enough areas
        if len(self.explored_areas) >= 4:
            return True

        return False

    def _synthesize_final_answer(
        self,
        question: str,
        cycles: List[SenseActCycle],
        entities: List[CodeEntity],
        insights: List[str],
    ) -> str:
        """Synthesize final answer from exploration cycles."""
        if self.llm_available:
            return self._llm_synthesize_answer(question, cycles, entities, insights)
        else:
            return self._rule_based_synthesize_answer(
                question, cycles, entities, insights
            )

    def _llm_synthesize_answer(
        self,
        question: str,
        cycles: List[SenseActCycle],
        entities: List[CodeEntity],
        insights: List[str],
    ) -> str:
        """Use LLM to synthesize final answer."""
        # Create context from cycles
        cycle_context = "\n".join(
            [
                f"Cycle {cycle.cycle_id}: Explored {cycle.sense_result.focus_area}, "
                f"found {len(cycle.action_result.new_entities)} entities, "
                f"{len(cycle.action_result.insights)} insights"
                for cycle in cycles
            ]
        )

        # Create insights context
        insights_context = "\n".join(insights[:10])

        prompt = f"""Question: {question}

Exploration cycles:
{cycle_context}

Key insights:
{insights_context}

Based on this systematic exploration, provide a comprehensive answer to the question.
Include specific examples, step-by-step procedures, and actionable recommendations."""

        try:
            response = litellm.completion(
                model=self.config.llm_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
            )

            return response.choices[0].message.content
        except Exception:
            return self._rule_based_synthesize_answer(
                question, cycles, entities, insights
            )

    def _rule_based_synthesize_answer(
        self,
        question: str,
        cycles: List[SenseActCycle],
        entities: List[CodeEntity],
        insights: List[str],
    ) -> str:
        """Rule-based answer synthesis."""
        answer_parts = []

        # Summary of exploration
        answer_parts.append(
            f"Based on {len(cycles)} exploration cycles, here's what I found:"
        )

        # Key findings
        total_entities = sum(len(cycle.action_result.new_entities) for cycle in cycles)
        answer_parts.append(f"- Discovered {total_entities} code entities")
        answer_parts.append(f"- Generated {len(insights)} insights")

        # Cycle-specific findings
        for cycle in cycles:
            if cycle.action_result.insights:
                answer_parts.append(
                    f"- {cycle.sense_result.focus_area}: {cycle.action_result.insights[0]}"
                )

        # General recommendations
        answer_parts.append("\nRecommendations:")
        answer_parts.append(
            "- Review the identified entities for detailed implementation"
        )
        answer_parts.append("- Consider the insights for best practices")
        answer_parts.append("- Explore related areas for comprehensive understanding")

        return "\n".join(answer_parts)
