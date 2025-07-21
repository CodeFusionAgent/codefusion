"""
Exploration Memory System for CodeFusion

This module implements a sophisticated caching and context-building system that:
1. Uses LLM to analyze questions and determine exploration strategies
2. Caches discoveries and builds progressive understanding
3. Supports high-level to deep-dive exploration methodology
4. Maintains exploration context across multiple questions
"""

import json
import time
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta

from cf.config import CfConfig
from cf.llm.real_llm import get_real_llm


@dataclass
class ExplorationQuestion:
    """Represents a question asked during exploration."""
    question: str
    timestamp: datetime
    question_type: str  # 'high_level', 'component_specific', 'deep_dive', 'implementation_detail'
    focus_areas: List[str]  # LLM-determined focus areas
    related_components: List[str] = field(default_factory=list)
    exploration_depth: int = 1  # 1=high-level, 5=deep implementation details


@dataclass
class ComponentKnowledge:
    """Knowledge accumulated about a specific component."""
    name: str
    component_type: str  # 'service', 'module', 'layer', 'package', 'class', 'function'
    description: str
    files: List[str] = field(default_factory=list)
    key_functions: List[Dict[str, Any]] = field(default_factory=list)
    key_classes: List[Dict[str, Any]] = field(default_factory=list)
    patterns: List[str] = field(default_factory=list)
    relationships: List[str] = field(default_factory=list)
    confidence: float = 0.0
    last_updated: datetime = field(default_factory=datetime.now)


@dataclass
class ArchitecturalLayer:
    """Represents an architectural layer discovered in the codebase."""
    name: str
    layer_type: str  # 'presentation', 'business', 'data', 'infrastructure', 'domain'
    components: List[str] = field(default_factory=list)
    responsibilities: List[str] = field(default_factory=list)
    files: List[str] = field(default_factory=list)
    entry_points: List[str] = field(default_factory=list)


@dataclass
class ExplorationPath:
    """Tracks the path of exploration through the codebase."""
    questions: List[ExplorationQuestion] = field(default_factory=list)
    discoveries: List[str] = field(default_factory=list)  # Major discoveries made
    focus_evolution: List[str] = field(default_factory=list)  # How focus has evolved
    depth_progression: List[int] = field(default_factory=list)  # Depth over time


class ExplorationMemory:
    """
    Sophisticated memory system for progressive codebase exploration.
    
    Supports:
    - LLM-driven question analysis and strategy determination
    - Progressive context building from high-level to implementation details
    - Component knowledge caching and relationship mapping
    - Exploration path tracking for better guidance
    """
    
    def __init__(self, repo_path: str, config: CfConfig):
        self.repo_path = repo_path
        self.config = config
        
        # Core memory stores
        self.components: Dict[str, ComponentKnowledge] = {}
        self.architectural_layers: Dict[str, ArchitecturalLayer] = {}
        self.file_analysis_cache: Dict[str, Dict[str, Any]] = {}
        self.pattern_cache: Dict[str, List[Dict[str, Any]]] = {}
        
        # Exploration tracking
        self.exploration_path = ExplorationPath()
        self.session_start = datetime.now()
        self.current_focus_areas: List[str] = []
        self.discovered_entry_points: Set[str] = set()
        
        # High-level codebase understanding
        self.codebase_summary: Optional[str] = None
        self.technology_stack: List[str] = []
        self.architectural_style: Optional[str] = None
        self.primary_purpose: Optional[str] = None
        
        # Question analysis cache (LLM results)
        self.question_analysis_cache: Dict[str, Dict[str, Any]] = {}
    
    def analyze_question_with_llm(self, question: str) -> Dict[str, Any]:
        """Use LLM to analyze question and determine exploration strategy."""
        # Check cache first
        if question in self.question_analysis_cache:
            return self.question_analysis_cache[question]
        
        try:
            real_llm = get_real_llm()
            if not real_llm or not real_llm.client:
                return self._fallback_question_analysis(question)
            
            # Build context from current exploration state
            context = self._build_llm_context_for_question(question)
            
            prompt = f"""
Analyze this codebase exploration question and determine the optimal exploration strategy.

QUESTION: {question}

CURRENT EXPLORATION CONTEXT:
{context}

Please analyze:
1. QUESTION_TYPE: Is this 'high_level', 'component_specific', 'deep_dive', or 'implementation_detail'?
2. FOCUS_AREAS: What specific areas of the codebase should be explored? (be generic, not framework-specific)
3. EXPLORATION_DEPTH: Rate 1-5 (1=high-level overview, 5=implementation details)
4. PRIORITY_TARGETS: What types of files/components to examine first?
5. EXPLORATION_STRATEGY: How should the exploration proceed?
6. RELATED_COMPONENTS: Based on current knowledge, what components might be relevant?

Be adaptive and generic - don't assume specific frameworks or technologies.
Work with whatever codebase architecture exists.

Format as JSON with keys: question_type, focus_areas, exploration_depth, priority_targets, exploration_strategy, related_components
"""
            
            response = real_llm._call_llm(prompt)
            
            try:
                analysis = json.loads(response)
                # Cache the result
                self.question_analysis_cache[question] = analysis
                return analysis
            except json.JSONDecodeError:
                # Fallback if JSON parsing fails
                return self._extract_analysis_from_text(response, question)
                
        except Exception as e:
            print(f"⚠️ [ExplorationMemory] LLM question analysis failed: {e}")
            return self._fallback_question_analysis(question)
    
    def _build_llm_context_for_question(self, question: str) -> str:
        """Build context from current exploration state for LLM analysis."""
        context_parts = []
        
        # Session overview
        context_parts.append(f"Exploration session started: {self.session_start.strftime('%H:%M:%S')}")
        context_parts.append(f"Questions asked so far: {len(self.exploration_path.questions)}")
        
        # Codebase understanding so far
        if self.codebase_summary:
            context_parts.append(f"Codebase Summary: {self.codebase_summary}")
        
        if self.technology_stack:
            context_parts.append(f"Technology Stack: {', '.join(self.technology_stack)}")
        
        if self.architectural_style:
            context_parts.append(f"Architectural Style: {self.architectural_style}")
        
        # Component knowledge
        if self.components:
            context_parts.append(f"Components Discovered: {len(self.components)}")
            for comp_name, comp in list(self.components.items())[:5]:  # Top 5 components
                context_parts.append(f"  - {comp_name} ({comp.component_type}): {comp.description[:100]}")
        
        # Architectural layers
        if self.architectural_layers:
            context_parts.append(f"Architectural Layers: {', '.join(self.architectural_layers.keys())}")
        
        # Previous questions and focus evolution
        if self.exploration_path.questions:
            context_parts.append("Recent Questions:")
            for q in self.exploration_path.questions[-3:]:  # Last 3 questions
                context_parts.append(f"  - {q.question} (depth: {q.exploration_depth}, type: {q.question_type})")
        
        # Current focus areas
        if self.current_focus_areas:
            context_parts.append(f"Current Focus Areas: {', '.join(self.current_focus_areas)}")
        
        # Files analyzed
        context_parts.append(f"Files Analyzed: {len(self.file_analysis_cache)}")
        
        return "\n".join(context_parts)
    
    def _fallback_question_analysis(self, question: str) -> Dict[str, Any]:
        """Fallback question analysis when LLM is unavailable."""
        question_lower = question.lower()
        
        # Simple heuristics for question type
        if any(word in question_lower for word in ['how does', 'what is', 'overview', 'explain']):
            question_type = 'high_level'
            exploration_depth = 2
        elif any(word in question_lower for word in ['implement', 'code', 'function', 'method', 'class']):
            question_type = 'implementation_detail'
            exploration_depth = 4
        elif any(word in question_lower for word in ['component', 'module', 'service']):
            question_type = 'component_specific'
            exploration_depth = 3
        else:
            question_type = 'deep_dive'
            exploration_depth = 3
        
        return {
            'question_type': question_type,
            'focus_areas': ['core_components', 'entry_points', 'main_logic'],
            'exploration_depth': exploration_depth,
            'priority_targets': ['main files', 'core modules', 'configuration'],
            'exploration_strategy': 'Start with main entry points and core components',
            'related_components': []
        }
    
    def _extract_analysis_from_text(self, response: str, question: str) -> Dict[str, Any]:
        """Extract analysis from text response if JSON parsing fails."""
        # Simple extraction logic as fallback
        analysis = self._fallback_question_analysis(question)
        
        # Try to extract some insights from the text
        if 'high-level' in response.lower() or 'overview' in response.lower():
            analysis['question_type'] = 'high_level'
            analysis['exploration_depth'] = 2
        elif 'implementation' in response.lower() or 'detail' in response.lower():
            analysis['question_type'] = 'implementation_detail'
            analysis['exploration_depth'] = 4
        
        return analysis
    
    def record_question(self, question: str) -> ExplorationQuestion:
        """Record a new question and analyze it."""
        # Analyze the question with LLM
        analysis = self.analyze_question_with_llm(question)
        
        # Create question record
        q_record = ExplorationQuestion(
            question=question,
            timestamp=datetime.now(),
            question_type=analysis.get('question_type', 'high_level'),
            focus_areas=analysis.get('focus_areas', []),
            exploration_depth=analysis.get('exploration_depth', 2)
        )
        
        # Update exploration path
        self.exploration_path.questions.append(q_record)
        self.exploration_path.depth_progression.append(q_record.exploration_depth)
        
        # Update current focus areas
        self.current_focus_areas = analysis.get('focus_areas', [])
        
        return q_record
    
    def cache_file_analysis(self, file_path: str, analysis: Dict[str, Any]) -> None:
        """Cache comprehensive file analysis results."""
        self.file_analysis_cache[file_path] = {
            **analysis,
            'cached_at': datetime.now().isoformat(),
            'file_path': file_path
        }
        
        # Extract component knowledge from file analysis
        self._extract_component_knowledge_from_file(file_path, analysis)
    
    def _extract_component_knowledge_from_file(self, file_path: str, analysis: Dict[str, Any]) -> None:
        """Extract and cache component knowledge from file analysis."""
        # Extract functions as potential components
        functions = analysis.get('functions', [])
        for func in functions:
            if func.get('name') and not func['name'].startswith('_'):
                comp_name = f"{Path(file_path).stem}.{func['name']}"
                if comp_name not in self.components:
                    self.components[comp_name] = ComponentKnowledge(
                        name=comp_name,
                        component_type='function',
                        description=func.get('purpose', ''),
                        files=[file_path],
                        key_functions=[func],
                        confidence=0.7
                    )
        
        # Extract classes as components
        classes = analysis.get('classes', [])
        for cls in classes:
            if cls.get('name'):
                comp_name = f"{Path(file_path).stem}.{cls['name']}"
                if comp_name not in self.components:
                    self.components[comp_name] = ComponentKnowledge(
                        name=comp_name,
                        component_type='class',
                        description=cls.get('purpose', ''),
                        files=[file_path],
                        key_classes=[cls],
                        confidence=0.8
                    )
    
    def get_exploration_context_for_agent(self) -> str:
        """Get current exploration context for agent reasoning."""
        if not self.exploration_path.questions:
            return "No exploration context available yet."
        
        current_question = self.exploration_path.questions[-1]
        
        context_parts = [
            f"🎯 **Current Question Type**: {current_question.question_type}",
            f"📊 **Exploration Depth**: {current_question.exploration_depth}/5",
            f"🔍 **Focus Areas**: {', '.join(current_question.focus_areas)}",
        ]
        
        # Add progression context
        if len(self.exploration_path.questions) > 1:
            context_parts.append(f"📈 **Exploration Progression**: {' → '.join([q.question_type for q in self.exploration_path.questions[-3:]])}")
        
        # Add component context
        if self.components:
            context_parts.append(f"🏗️ **Components Discovered**: {len(self.components)} ({', '.join(list(self.components.keys())[:3])})")
        
        # Add cache status
        context_parts.append(f"💾 **Files Analyzed**: {len(self.file_analysis_cache)}")
        
        return "\n".join(context_parts)
    
    def suggest_next_actions(self) -> List[str]:
        """Suggest next actions based on exploration context."""
        if not self.exploration_path.questions:
            return ["scan_directory", "list_files"]
        
        current_question = self.exploration_path.questions[-1]
        
        if current_question.question_type == 'high_level':
            if not self.file_analysis_cache:
                return ["scan_directory", "search_files", "read_file"]
            else:
                return ["analyze_code", "generate_summary"]
        
        elif current_question.question_type == 'component_specific':
            return ["search_files", "read_file", "analyze_code"]
        
        elif current_question.question_type == 'implementation_detail':
            return ["read_file", "analyze_code", "search_files"]
        
        else:  # deep_dive
            return ["analyze_code", "read_file", "generate_summary"]
    
    def get_cache_summary(self) -> Dict[str, Any]:
        """Get summary of cached exploration data."""
        return {
            'session_duration': str(datetime.now() - self.session_start),
            'questions_asked': len(self.exploration_path.questions),
            'components_discovered': len(self.components),
            'files_analyzed': len(self.file_analysis_cache),
            'architectural_layers': len(self.architectural_layers),
            'current_focus': self.current_focus_areas,
            'exploration_depth_trend': self.exploration_path.depth_progression[-5:] if self.exploration_path.depth_progression else [],
            'recent_discoveries': self.exploration_path.discoveries[-3:] if self.exploration_path.discoveries else []
        }


# Global exploration memory instance
exploration_memory: Optional[ExplorationMemory] = None

def init_exploration_memory(repo_path: str, config: CfConfig) -> ExplorationMemory:
    """Initialize the global exploration memory instance."""
    global exploration_memory
    exploration_memory = ExplorationMemory(repo_path, config)
    return exploration_memory

def get_exploration_memory() -> Optional[ExplorationMemory]:
    """Get the global exploration memory instance."""
    return exploration_memory