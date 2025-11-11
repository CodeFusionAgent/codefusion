"""
Incremental Context Building for CodeFusion

Analyzes files in phases (core → dependencies → periphery) where each phase
builds on the understanding from previous phases, resulting in better
architectural comprehension.
"""

import re
from typing import Dict, List, Any, Set, Tuple
from dataclasses import dataclass


@dataclass
class FilePhase:
    """Represents a file's analysis phase"""
    file_path: str
    phase: int  # 1 = core, 2 = dependencies, 3 = periphery
    priority: float  # Higher priority analyzed first
    reason: str  # Why file is in this phase


@dataclass
class PhaseAnalysisResult:
    """Result of analyzing a single phase"""
    phase_number: int
    phase_name: str
    files_analyzed: List[str]
    summaries: Dict[str, Any]
    cumulative_context: Dict[str, Any]
    analysis_time_ms: float


class IncrementalContextBuilder:
    """
    Builds context incrementally by analyzing files in phases.

    Phase 1 (Core): Entry points, main classes, key abstractions
    Phase 2 (Dependencies): Files imported/used by core files
    Phase 3 (Periphery): Utilities, helpers, supporting code

    Each phase builds on understanding from previous phases.
    """

    def __init__(self, config: Dict[str, Any], repo_tools=None):
        self.config = config
        self.repo_tools = repo_tools

    def organize_files_by_phase(self,
                                file_paths: List[str],
                                architectural_analysis=None) -> Dict[int, List[FilePhase]]:
        """
        Organize files into phases based on importance and dependencies.

        Args:
            file_paths: All discovered file paths
            architectural_analysis: Optional architectural analysis result

        Returns:
            Dict mapping phase number to list of FilePhase objects
        """
        print("🔄 [INCREMENTAL] Organizing files into analysis phases...")

        phases: Dict[int, List[FilePhase]] = {1: [], 2: [], 3: []}

        # Phase 1: Identify core files
        core_files = self._identify_core_files(file_paths, architectural_analysis)
        for file_path, priority, reason in core_files:
            phases[1].append(FilePhase(
                file_path=file_path,
                phase=1,
                priority=priority,
                reason=reason
            ))

        # Phase 2: Identify dependency files (imported by core)
        core_file_paths = [f.file_path for f in phases[1]]
        dependency_files = self._identify_dependency_files(
            file_paths, core_file_paths, architectural_analysis
        )
        for file_path, priority, reason in dependency_files:
            if file_path not in core_file_paths:  # Not already in core
                phases[2].append(FilePhase(
                    file_path=file_path,
                    phase=2,
                    priority=priority,
                    reason=reason
                ))

        # Phase 3: Remaining files (periphery)
        analyzed_files = set(core_file_paths + [f.file_path for f in phases[2]])
        for file_path in file_paths:
            if file_path not in analyzed_files:
                phases[3].append(FilePhase(
                    file_path=file_path,
                    phase=3,
                    priority=0.5,
                    reason="Supporting/utility code"
                ))

        # Sort each phase by priority
        for phase_num in phases:
            phases[phase_num].sort(key=lambda f: f.priority, reverse=True)

        print(f"   Phase 1 (Core): {len(phases[1])} files")
        print(f"   Phase 2 (Dependencies): {len(phases[2])} files")
        print(f"   Phase 3 (Periphery): {len(phases[3])} files")

        return phases

    def _identify_core_files(self,
                            file_paths: List[str],
                            architectural_analysis=None) -> List[Tuple[str, float, str]]:
        """
        Identify core files that should be analyzed first.

        Returns: List of (file_path, priority, reason) tuples
        """
        core_files = []

        # Strategy 1: From architectural analysis
        if architectural_analysis:
            # Entry points are core
            for entry_point in architectural_analysis.entry_points:
                for file_path in entry_point.files:
                    if file_path in file_paths:
                        core_files.append((
                            file_path,
                            0.95,
                            f"Entry point: {entry_point.name}"
                        ))

            # Core abstractions are core
            for abstraction in architectural_analysis.core_abstractions:
                for file_path in abstraction.files:
                    if file_path in file_paths:
                        core_files.append((
                            file_path,
                            0.90,
                            f"Core abstraction: {abstraction.name}"
                        ))

        # Strategy 2: Pattern-based detection
        core_patterns = [
            (r'main\.py$', 1.0, 'Main entry point'),
            (r'__main__\.py$', 1.0, 'Main entry point'),
            (r'app\.py$', 0.95, 'Application entry'),
            (r'server\.py$', 0.95, 'Server entry'),
            (r'routes?\.py$', 0.90, 'API routes'),
            (r'views?\.py$', 0.90, 'View handlers'),
            (r'controllers?\.py$', 0.90, 'Controllers'),
            (r'models?\.py$', 0.85, 'Data models'),
            (r'base[^/]*\.py$', 0.85, 'Base classes'),
            (r'core[^/]*/.*\.py$', 0.85, 'Core module'),
            (r'api[^/]*/.*\.py$', 0.80, 'API module'),
        ]

        for file_path in file_paths:
            for pattern, priority, reason in core_patterns:
                if re.search(pattern, file_path):
                    core_files.append((file_path, priority, reason))
                    break

        # Deduplicate (keep highest priority)
        seen = {}
        for file_path, priority, reason in core_files:
            if file_path not in seen or priority > seen[file_path][0]:
                seen[file_path] = (priority, reason)

        return [(path, pri, rea) for path, (pri, rea) in seen.items()]

    def _identify_dependency_files(self,
                                   all_files: List[str],
                                   core_files: List[str],
                                   architectural_analysis=None) -> List[Tuple[str, float, str]]:
        """
        Identify files that are dependencies of core files.

        Returns: List of (file_path, priority, reason) tuples
        """
        dependency_files = []

        # Strategy 1: From architectural analysis component relationships
        if architectural_analysis and architectural_analysis.component_relationships:
            for core_file in core_files:
                if core_file in architectural_analysis.component_relationships:
                    deps = architectural_analysis.component_relationships[core_file]
                    for dep in deps:
                        if dep in all_files:
                            dependency_files.append((
                                dep,
                                0.75,
                                f"Imported by {core_file.split('/')[-1]}"
                            ))

        # Strategy 2: Parse imports from core files (if repo tools available)
        if self.repo_tools:
            for core_file in core_files:
                try:
                    result = self.repo_tools.execute('read_file', file_path=core_file)
                    if result.get('success'):
                        content = result.get('content', '')
                        imports = self._extract_imports(content, core_file)

                        for imported_file in imports:
                            if imported_file in all_files:
                                dependency_files.append((
                                    imported_file,
                                    0.70,
                                    f"Imported by {core_file.split('/')[-1]}"
                                ))
                except Exception as e:
                    pass  # Silently skip if can't read file

        # Strategy 3: Pattern-based (files likely to be dependencies)
        dependency_patterns = [
            (r'config\.py$', 0.75, 'Configuration'),
            (r'settings\.py$', 0.75, 'Settings'),
            (r'constants\.py$', 0.70, 'Constants'),
            (r'exceptions?\.py$', 0.70, 'Exceptions'),
            (r'errors?\.py$', 0.70, 'Errors'),
            (r'types?\.py$', 0.70, 'Type definitions'),
            (r'schemas?\.py$', 0.70, 'Schemas'),
            (r'validators?\.py$', 0.65, 'Validators'),
        ]

        for file_path in all_files:
            if file_path not in core_files:
                for pattern, priority, reason in dependency_patterns:
                    if re.search(pattern, file_path):
                        dependency_files.append((file_path, priority, reason))
                        break

        # Deduplicate
        seen = {}
        for file_path, priority, reason in dependency_files:
            if file_path not in seen or priority > seen[file_path][0]:
                seen[file_path] = (priority, reason)

        return [(path, pri, rea) for path, (pri, rea) in seen.items()]

    def _extract_imports(self, content: str, current_file: str) -> List[str]:
        """
        Extract imported file paths from Python code.

        Returns: List of potentially imported file paths (relative to repo)
        """
        imports = []

        # Extract import statements
        import_patterns = [
            r'from\s+([\w.]+)\s+import',
            r'import\s+([\w.]+)',
        ]

        for pattern in import_patterns:
            matches = re.findall(pattern, content)
            imports.extend(matches)

        # Convert module paths to file paths
        # e.g., "cf.agents.pipelines.analysis" -> "cf/agents/pipelines/analysis.py"
        file_imports = []
        for module_path in imports:
            # Skip stdlib and third-party
            if '.' not in module_path:
                continue

            # Convert to file path
            file_path = module_path.replace('.', '/') + '.py'
            file_imports.append(file_path)

        return file_imports

    def build_cumulative_context(self,
                                phase_results: List[PhaseAnalysisResult]) -> Dict[str, Any]:
        """
        Build cumulative context from all completed phases.

        This context is passed to subsequent phases to inform their analysis.
        """
        context = {
            'analyzed_files': [],
            'key_abstractions': [],
            'patterns_found': [],
            'entry_points': [],
            'architectural_insights': [],
            'phase_count': len(phase_results)
        }

        for phase_result in phase_results:
            context['analyzed_files'].extend(phase_result.files_analyzed)

            # Aggregate insights from summaries
            for file_path, summary in phase_result.summaries.items():
                if not isinstance(summary, dict):
                    continue

                # Collect abstractions (classes, key functions)
                classes = summary.get('classes', [])
                for cls in classes:
                    if isinstance(cls, dict):
                        context['key_abstractions'].append({
                            'name': cls.get('name', ''),
                            'file': file_path,
                            'type': 'class'
                        })

                # Collect architectural insights
                insights = summary.get('architectural_insights', '')
                if insights:
                    context['architectural_insights'].append({
                        'file': file_path,
                        'insight': insights
                    })

        return context
