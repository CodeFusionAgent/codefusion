"""
Architectural Analysis Pipeline for CodeFusion

Extracts high-level architecture from analyzed files BEFORE synthesis.
This addresses the weakness where files are analyzed independently without
explicit architectural understanding.
"""

import re
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass


@dataclass
class ArchitecturalInsight:
    """High-level architectural insight"""
    category: str  # 'entry_point', 'core_abstraction', 'pattern', 'call_chain'
    name: str
    description: str
    files: List[str]
    confidence: float
    details: Dict[str, Any]


@dataclass
class ArchitecturalAnalysisResult:
    """Result of architectural analysis"""
    entry_points: List[ArchitecturalInsight]
    core_abstractions: List[ArchitecturalInsight]
    detected_patterns: List[ArchitecturalInsight]
    call_chains: List[ArchitecturalInsight]
    component_relationships: Dict[str, List[str]]
    architectural_summary: str


class ArchitecturalAnalyzer:
    """
    Analyzes file summaries to extract high-level architecture.

    This creates a "mental model" of the codebase architecture
    before synthesis, ensuring better architectural narratives.
    """

    def __init__(self, config: Dict[str, Any], kb_client=None, llm_client=None):
        self.config = config
        self.kb = kb_client  # Optional KB for call graph queries
        self.llm = llm_client  # Optional LLM for architectural synthesis

    def analyze_architecture(self,
                            file_summaries: Dict[str, Any],
                            question: str,
                            question_type: str = 'standard') -> ArchitecturalAnalysisResult:
        """
        Extract architectural insights from file summaries.

        Args:
            file_summaries: Analyzed file summaries from analysis pipeline
            question: User's question for context
            question_type: Type of question (how_it_works, what_is, where_is, etc.)

        Returns:
            ArchitecturalAnalysisResult with high-level architecture
        """
        print("🏗️  [ARCHITECTURE] Extracting architectural insights...")

        # 1. Identify entry points
        entry_points = self._identify_entry_points(file_summaries)
        print(f"   Found {len(entry_points)} entry points")

        # 2. Identify core abstractions (base classes, key interfaces)
        core_abstractions = self._identify_core_abstractions(file_summaries)
        print(f"   Found {len(core_abstractions)} core abstractions")

        # 3. Detect architectural patterns
        detected_patterns = self._detect_architectural_patterns(file_summaries)
        print(f"   Detected {len(detected_patterns)} architectural patterns")

        # 4. Extract call chains (if KB available and relevant)
        call_chains = []
        if self.kb and question_type in ['how_it_works', 'explain']:
            call_chains = self._extract_call_chains(file_summaries, question)
            print(f"   Traced {len(call_chains)} call chains")

        # 5. Build component relationship graph
        relationships = self._build_component_relationships(file_summaries)

        # 6. Generate architectural summary
        summary = self._generate_architectural_summary(
            entry_points, core_abstractions, detected_patterns, call_chains
        )

        return ArchitecturalAnalysisResult(
            entry_points=entry_points,
            core_abstractions=core_abstractions,
            detected_patterns=detected_patterns,
            call_chains=call_chains,
            component_relationships=relationships,
            architectural_summary=summary
        )

    def _identify_entry_points(self, file_summaries: Dict[str, Any]) -> List[ArchitecturalInsight]:
        """Identify system entry points (main, API endpoints, CLI commands)"""
        entry_points = []

        # Entry point indicators
        entry_indicators = {
            'main': ['def main(', 'if __name__ == "__main__"', 'main.py'],
            'api_endpoint': ['@app.route', '@api.route', '@router.', 'FastAPI', 'Flask'],
            'cli_command': ['@click.command', 'argparse', 'ArgumentParser'],
            'event_handler': ['@event.', 'on_message', 'handle_', 'async def on_'],
        }

        for file_path, summary in file_summaries.items():
            if not isinstance(summary, dict):
                continue

            content = summary.get('content', '')
            features = summary.get('key_features', [])
            functions = summary.get('functions', [])

            # Check for entry point patterns
            for entry_type, indicators in entry_indicators.items():
                matches = [ind for ind in indicators if ind in content or any(ind in str(f) for f in features)]

                if matches:
                    # Found entry point
                    entry_points.append(ArchitecturalInsight(
                        category='entry_point',
                        name=f"{entry_type} in {file_path.split('/')[-1]}",
                        description=f"{entry_type.replace('_', ' ').title()} functionality",
                        files=[file_path],
                        confidence=0.8,
                        details={
                            'type': entry_type,
                            'indicators': matches,
                            'functions': [f.get('name', '') for f in functions[:5] if isinstance(f, dict)]
                        }
                    ))

        return entry_points

    def _identify_core_abstractions(self, file_summaries: Dict[str, Any]) -> List[ArchitecturalInsight]:
        """Identify core abstractions (base classes, key interfaces, data models)"""
        abstractions = []

        # Core abstraction indicators
        abstraction_indicators = {
            'base_class': ['Base', 'Abstract', 'ABC', 'metaclass'],
            'interface': ['Interface', 'Protocol', 'typing.Protocol'],
            'model': ['Model', 'Schema', 'Entity', 'DTO', 'dataclass'],
            'manager': ['Manager', 'Controller', 'Service', 'Handler'],
            'factory': ['Factory', 'Builder', 'Creator'],
        }

        for file_path, summary in file_summaries.items():
            if not isinstance(summary, dict):
                continue

            classes = summary.get('classes', [])
            features = summary.get('key_features', [])
            insights = summary.get('architectural_insights', '')

            for class_info in classes:
                if not isinstance(class_info, dict):
                    continue

                class_name = class_info.get('name', '')
                if not class_name:
                    continue

                # Check if class is a core abstraction
                for abs_type, indicators in abstraction_indicators.items():
                    if any(ind.lower() in class_name.lower() for ind in indicators):
                        abstractions.append(ArchitecturalInsight(
                            category='core_abstraction',
                            name=class_name,
                            description=f"{abs_type.replace('_', ' ').title()} - {insights[:100] if insights else 'Core abstraction'}",
                            files=[file_path],
                            confidence=0.7,
                            details={
                                'type': abs_type,
                                'class_name': class_name,
                                'methods': class_info.get('methods', [])[:5]
                            }
                        ))
                        break

        return abstractions

    def _detect_architectural_patterns(self, file_summaries: Dict[str, Any]) -> List[ArchitecturalInsight]:
        """Detect design and architectural patterns in the codebase"""
        patterns = []
        pattern_files: Dict[str, List[str]] = {}

        # Pattern detection keywords
        pattern_keywords = {
            'singleton': ['singleton', 'single instance', '_instance = None'],
            'factory': ['factory', 'create_', 'make_', 'builder'],
            'observer': ['observer', 'listener', 'subscribe', 'event', 'callback'],
            'strategy': ['strategy', 'algorithm', 'policy'],
            'decorator': ['@decorator', 'wrapper', '@wraps'],
            'adapter': ['adapter', 'wrapper', 'adapt_'],
            'mvc': ['model', 'view', 'controller', 'template'],
            'repository': ['repository', 'data access', 'dao', 'crud'],
            'dependency_injection': ['inject', 'dependency', 'di_container'],
        }

        # Collect pattern evidence from all files
        for file_path, summary in file_summaries.items():
            if not isinstance(summary, dict):
                continue

            content = summary.get('content', '').lower()
            features_text = ' '.join(str(f).lower() for f in summary.get('key_features', []))
            insights = summary.get('architectural_insights', '').lower()

            combined_text = f"{content} {features_text} {insights}"

            for pattern_name, keywords in pattern_keywords.items():
                if any(keyword in combined_text for keyword in keywords):
                    if pattern_name not in pattern_files:
                        pattern_files[pattern_name] = []
                    pattern_files[pattern_name].append(file_path)

        # Create pattern insights
        for pattern_name, files in pattern_files.items():
            if len(files) >= 1:  # At least 1 file showing pattern
                patterns.append(ArchitecturalInsight(
                    category='pattern',
                    name=pattern_name.replace('_', ' ').title() + ' Pattern',
                    description=f"Detected {pattern_name.replace('_', ' ')} pattern usage",
                    files=files[:5],  # Limit to 5 files
                    confidence=min(0.5 + len(files) * 0.1, 0.9),
                    details={
                        'pattern_type': pattern_name,
                        'file_count': len(files)
                    }
                ))

        return patterns

    def _extract_call_chains(self, file_summaries: Dict[str, Any], question: str) -> List[ArchitecturalInsight]:
        """Extract execution paths/call chains using KB (if available)"""
        call_chains = []

        if not self.kb:
            return call_chains

        # Extract potential entry function names from question
        # E.g., "How does authentication work?" -> look for "authenticate", "login", etc.
        question_words = re.findall(r'\b\w+\b', question.lower())
        relevant_words = [w for w in question_words if len(w) > 4 and w not in ['does', 'work', 'what', 'where', 'when']]

        # Try to find call chains for relevant functions
        for word in relevant_words[:3]:  # Limit to 3 words
            try:
                # Query KB for call chains (this is a simplified example)
                # Real implementation would use kb.trace_execution_path()
                # For now, just mark that we'd do this
                call_chains.append(ArchitecturalInsight(
                    category='call_chain',
                    name=f"Execution path for {word}",
                    description=f"Call chain analysis for {word} functionality",
                    files=[],  # Would be populated from KB
                    confidence=0.6,
                    details={
                        'entry_function': word,
                        'depth': 5,
                        'note': 'KB integration required'
                    }
                ))
            except Exception as e:
                print(f"   ⚠️ Failed to trace call chain for {word}: {e}")

        return call_chains

    def _build_component_relationships(self, file_summaries: Dict[str, Any]) -> Dict[str, List[str]]:
        """Build a graph of component relationships (dependencies)"""
        relationships = {}

        for file_path, summary in file_summaries.items():
            if not isinstance(summary, dict):
                continue

            dependencies = summary.get('dependencies', [])
            if dependencies:
                relationships[file_path] = dependencies

        return relationships

    def _generate_architectural_summary(self,
                                       entry_points: List[ArchitecturalInsight],
                                       core_abstractions: List[ArchitecturalInsight],
                                       patterns: List[ArchitecturalInsight],
                                       call_chains: List[ArchitecturalInsight]) -> str:
        """Generate a concise architectural summary"""
        summary_parts = []

        if entry_points:
            entry_names = [e.name for e in entry_points[:3]]
            summary_parts.append(f"Entry points: {', '.join(entry_names)}")

        if core_abstractions:
            abs_names = [a.name for a in core_abstractions[:3]]
            summary_parts.append(f"Core abstractions: {', '.join(abs_names)}")

        if patterns:
            pattern_names = [p.name for p in patterns]
            summary_parts.append(f"Patterns: {', '.join(pattern_names)}")

        if call_chains:
            summary_parts.append(f"{len(call_chains)} execution paths traced")

        return " | ".join(summary_parts) if summary_parts else "Architecture analysis complete"
