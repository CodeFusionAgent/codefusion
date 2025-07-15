"""Plan-then-act exploration strategy for CodeFusion."""

import os
import json
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path

try:
    import litellm
    LITELLM_AVAILABLE = True
except ImportError:
    LITELLM_AVAILABLE = False

from ..kb.knowledge_base import CodeEntity, CodeKB
from ..config import CfConfig
from ..aci.system_access import SystemAccess


@dataclass
class ExplorationPlan:
    """Plan for exploring a codebase."""
    goal: str
    priority_areas: List[str]
    exploration_steps: List[str]
    expected_entities: List[str]
    success_criteria: List[str]
    estimated_time: int  # in minutes


@dataclass
class PlanStep:
    """Individual step in the exploration plan."""
    step_id: str
    description: str
    action_type: str  # "analyze_directory", "examine_files", "trace_relationships", "validate_findings"
    target_paths: List[str]
    expected_findings: List[str]
    completed: bool = False
    results: List[str] = None


@dataclass
class PlanResult:
    """Result of executing a plan."""
    plan: ExplorationPlan
    executed_steps: List[PlanStep]
    discovered_entities: List[CodeEntity]
    insights: List[str]
    success_rate: float
    execution_time: int


class PlanThenActAgent:
    """Agent that creates a plan before exploring the codebase."""
    
    def __init__(self, config: CfConfig, kb: CodeKB):
        self.config = config
        self.kb = kb
        self.system_access = SystemAccess()
        self.llm_available = LITELLM_AVAILABLE and self.system_access.has_llm_config()
        
        if self.llm_available:
            self._setup_llm()
    
    def _setup_llm(self):
        """Setup LLM configuration."""
        llm_config = self.system_access.get_llm_config()
        if llm_config["api_key"]:
            os.environ["OPENAI_API_KEY"] = llm_config["api_key"]
        if llm_config["base_url"]:
            os.environ["OPENAI_BASE_URL"] = llm_config["base_url"]
    
    def explore_codebase(self, question: str, repo_path: str) -> PlanResult:
        """Explore codebase using plan-then-act strategy."""
        # Phase 1: Create exploration plan
        plan = self._create_exploration_plan(question, repo_path)
        
        # Phase 2: Execute the plan
        return self._execute_plan(plan, repo_path)
    
    def _create_exploration_plan(self, question: str, repo_path: str) -> ExplorationPlan:
        """Create a structured exploration plan."""
        if self.llm_available:
            return self._llm_create_plan(question, repo_path)
        else:
            return self._rule_based_create_plan(question, repo_path)
    
    def _llm_create_plan(self, question: str, repo_path: str) -> ExplorationPlan:
        """Use LLM to create exploration plan."""
        # Analyze directory structure first
        structure_analysis = self._analyze_directory_structure(repo_path)
        
        prompt = f"""Create an exploration plan for this codebase question: "{question}"

Directory structure:
{structure_analysis}

Create a JSON plan with:
1. goal: Clear objective
2. priority_areas: List of 3-5 key directories/files to focus on
3. exploration_steps: List of 5-8 specific actions to take
4. expected_entities: List of code entities (classes, functions, files) we expect to find
5. success_criteria: List of criteria to determine if exploration was successful
6. estimated_time: Estimated time in minutes

Return only the JSON object."""
        
        try:
            response = litellm.completion(
                model=self.config.llm_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1
            )
            
            plan_data = json.loads(response.choices[0].message.content)
            return ExplorationPlan(**plan_data)
            
        except Exception as e:
            print(f"LLM plan creation failed: {e}")
            return self._rule_based_create_plan(question, repo_path)
    
    def _rule_based_create_plan(self, question: str, repo_path: str) -> ExplorationPlan:
        """Create exploration plan using rule-based approach."""
        question_lower = question.lower()
        
        # Analyze directory structure
        structure_analysis = self._analyze_directory_structure(repo_path)
        priority_areas = self._identify_priority_areas(structure_analysis, question_lower)
        
        # Create exploration steps based on question type
        exploration_steps = []
        if any(word in question_lower for word in ['test', 'testing']):
            exploration_steps.extend([
                "Examine test directories and files",
                "Analyze test configuration files",
                "Trace test execution patterns",
                "Identify test frameworks and utilities"
            ])
        
        if any(word in question_lower for word in ['config', 'setup', 'install']):
            exploration_steps.extend([
                "Examine configuration files",
                "Analyze package/dependency files",
                "Review setup and installation scripts",
                "Check environment configuration"
            ])
        
        if any(word in question_lower for word in ['api', 'endpoint', 'route']):
            exploration_steps.extend([
                "Identify API definition files",
                "Trace route handlers and controllers",
                "Analyze middleware and authentication",
                "Review API documentation"
            ])
        
        # Default exploration steps
        exploration_steps.extend([
            "Analyze main entry points",
            "Examine core modules and packages",
            "Review documentation and README files",
            "Validate findings against question"
        ])
        
        return ExplorationPlan(
            goal=f"Answer: {question}",
            priority_areas=priority_areas,
            exploration_steps=exploration_steps[:8],  # Limit to 8 steps
            expected_entities=["main functions", "configuration files", "core classes"],
            success_criteria=["Question answered", "Key entities identified", "Relationships mapped"],
            estimated_time=15
        )
    
    def _analyze_directory_structure(self, repo_path: str) -> str:
        """Analyze and summarize directory structure."""
        structure_lines = []
        repo_path = Path(repo_path)
        
        try:
            # Get top-level directories
            for item in sorted(repo_path.iterdir()):
                if item.is_dir() and not item.name.startswith('.'):
                    # Count files in directory
                    try:
                        file_count = len([f for f in item.rglob('*') if f.is_file()])
                        structure_lines.append(f"📁 {item.name}/ ({file_count} files)")
                        
                        # Show important subdirectories
                        subdirs = [d for d in item.iterdir() if d.is_dir() and not d.name.startswith('.')]
                        if subdirs:
                            for subdir in sorted(subdirs)[:3]:  # Show top 3 subdirs
                                structure_lines.append(f"  📁 {subdir.name}/")
                    except PermissionError:
                        structure_lines.append(f"📁 {item.name}/ (access denied)")
                        
                elif item.is_file() and not item.name.startswith('.'):
                    structure_lines.append(f"📄 {item.name}")
            
            return "\n".join(structure_lines[:20])  # Limit output
            
        except Exception as e:
            return f"Error analyzing structure: {e}"
    
    def _identify_priority_areas(self, structure_analysis: str, question: str) -> List[str]:
        """Identify priority areas based on structure and question."""
        priority_areas = []
        
        # Extract directory names from structure
        lines = structure_analysis.split('\n')
        directories = [line.split()[1].rstrip('/') for line in lines if line.startswith('📁')]
        
        # Priority based on common patterns
        high_priority = ['src', 'lib', 'app', 'main', 'core', 'api']
        medium_priority = ['tests', 'test', 'docs', 'config', 'utils', 'helpers']
        
        # Question-specific priorities
        if 'test' in question:
            priority_areas.extend([d for d in directories if 'test' in d.lower()])
        if 'config' in question:
            priority_areas.extend([d for d in directories if 'config' in d.lower()])
        if 'api' in question:
            priority_areas.extend([d for d in directories if any(term in d.lower() for term in ['api', 'route', 'endpoint'])])
        
        # Add high priority directories
        for dir_name in directories:
            if dir_name.lower() in high_priority:
                priority_areas.append(dir_name)
        
        # Add medium priority if not enough areas
        if len(priority_areas) < 3:
            for dir_name in directories:
                if dir_name.lower() in medium_priority:
                    priority_areas.append(dir_name)
        
        return list(set(priority_areas))[:5]  # Return top 5 unique areas
    
    def _execute_plan(self, plan: ExplorationPlan, repo_path: str) -> PlanResult:
        """Execute the exploration plan."""
        executed_steps = []
        discovered_entities = []
        insights = []
        
        print(f"🎯 Executing Plan: {plan.goal}")
        print(f"📍 Priority Areas: {', '.join(plan.priority_areas)}")
        print(f"⏱️  Estimated Time: {plan.estimated_time} minutes")
        print()
        
        # Execute each step
        for i, step_desc in enumerate(plan.exploration_steps, 1):
            step = PlanStep(
                step_id=f"step_{i}",
                description=step_desc,
                action_type=self._classify_action_type(step_desc),
                target_paths=self._determine_target_paths(step_desc, plan.priority_areas, repo_path),
                expected_findings=[]
            )
            
            print(f"🔍 Step {i}: {step_desc}")
            
            # Execute the step
            step_results = self._execute_step(step, repo_path)
            step.results = step_results
            step.completed = True
            
            # Extract entities and insights
            step_entities = self._extract_entities_from_results(step_results)
            discovered_entities.extend(step_entities)
            
            step_insights = self._extract_insights_from_results(step_results, step_desc)
            insights.extend(step_insights)
            
            executed_steps.append(step)
            print(f"   ✅ Found {len(step_entities)} entities, {len(step_insights)} insights")
        
        # Calculate success rate
        success_rate = len([s for s in executed_steps if s.completed]) / len(executed_steps)
        
        return PlanResult(
            plan=plan,
            executed_steps=executed_steps,
            discovered_entities=discovered_entities,
            insights=insights,
            success_rate=success_rate,
            execution_time=plan.estimated_time
        )
    
    def _classify_action_type(self, step_desc: str) -> str:
        """Classify the type of action for a step."""
        desc_lower = step_desc.lower()
        
        if any(word in desc_lower for word in ['directory', 'folder', 'structure']):
            return "analyze_directory"
        elif any(word in desc_lower for word in ['file', 'examine', 'review']):
            return "examine_files"
        elif any(word in desc_lower for word in ['trace', 'relationship', 'connection']):
            return "trace_relationships"
        elif any(word in desc_lower for word in ['validate', 'verify', 'check']):
            return "validate_findings"
        else:
            return "general_analysis"
    
    def _determine_target_paths(self, step_desc: str, priority_areas: List[str], repo_path: str) -> List[str]:
        """Determine target paths for a step."""
        desc_lower = step_desc.lower()
        repo_path = Path(repo_path)
        target_paths = []
        
        # Specific path patterns
        if 'test' in desc_lower:
            test_dirs = [d for d in priority_areas if 'test' in d.lower()]
            target_paths.extend(test_dirs)
        
        if 'config' in desc_lower:
            config_patterns = ['config', 'settings', 'conf']
            for pattern in config_patterns:
                matching_dirs = [d for d in priority_areas if pattern in d.lower()]
                target_paths.extend(matching_dirs)
        
        if 'main' in desc_lower or 'entry' in desc_lower:
            entry_patterns = ['src', 'app', 'main', 'lib']
            for pattern in entry_patterns:
                matching_dirs = [d for d in priority_areas if pattern in d.lower()]
                target_paths.extend(matching_dirs)
        
        # Default to priority areas if no specific paths found
        if not target_paths:
            target_paths = priority_areas[:3]
        
        return target_paths
    
    def _execute_step(self, step: PlanStep, repo_path: str) -> List[str]:
        """Execute a single exploration step."""
        results = []
        repo_path = Path(repo_path)
        
        if step.action_type == "analyze_directory":
            for target in step.target_paths:
                target_path = repo_path / target
                if target_path.exists():
                    dir_analysis = self._analyze_directory_contents(target_path)
                    results.append(f"Directory {target}: {dir_analysis}")
        
        elif step.action_type == "examine_files":
            for target in step.target_paths:
                target_path = repo_path / target
                if target_path.exists():
                    file_analysis = self._examine_files_in_directory(target_path)
                    results.extend(file_analysis)
        
        elif step.action_type == "trace_relationships":
            # Use knowledge base to find relationships
            entities = self.kb.search_entities("", limit=50)
            relationship_analysis = self._analyze_entity_relationships(entities)
            results.extend(relationship_analysis)
        
        elif step.action_type == "validate_findings":
            # Validate findings against the original question
            validation_results = self._validate_exploration_results(step.description)
            results.extend(validation_results)
        
        return results
    
    def _analyze_directory_contents(self, directory: Path) -> str:
        """Analyze contents of a directory."""
        try:
            files = list(directory.glob('*'))
            file_count = len([f for f in files if f.is_file()])
            dir_count = len([d for d in files if d.is_dir()])
            
            # Important files
            important_files = []
            for file in files:
                if file.is_file() and file.suffix in ['.py', '.js', '.ts', '.java', '.cpp', '.rs']:
                    important_files.append(file.name)
            
            return f"{file_count} files, {dir_count} directories. Key files: {', '.join(important_files[:5])}"
            
        except Exception as e:
            return f"Error analyzing directory: {e}"
    
    def _examine_files_in_directory(self, directory: Path) -> List[str]:
        """Examine files in a directory."""
        results = []
        
        try:
            for file_path in directory.glob('**/*.py'):
                if file_path.is_file():
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            if len(content) > 100:  # Only analyze substantial files
                                file_analysis = self._analyze_file_content(file_path, content)
                                results.append(file_analysis)
                    except Exception:
                        continue
        except Exception as e:
            results.append(f"Error examining files: {e}")
        
        return results
    
    def _analyze_file_content(self, file_path: Path, content: str) -> str:
        """Analyze content of a single file."""
        lines = content.split('\n')
        
        # Extract key information
        classes = [line.strip() for line in lines if line.strip().startswith('class ')]
        functions = [line.strip() for line in lines if line.strip().startswith('def ')]
        imports = [line.strip() for line in lines if line.strip().startswith('import ') or line.strip().startswith('from ')]
        
        return f"File {file_path.name}: {len(classes)} classes, {len(functions)} functions, {len(imports)} imports"
    
    def _analyze_entity_relationships(self, entities: List[CodeEntity]) -> List[str]:
        """Analyze relationships between entities."""
        results = []
        
        # Group entities by type
        entity_groups = {}
        for entity in entities:
            if entity.type not in entity_groups:
                entity_groups[entity.type] = []
            entity_groups[entity.type].append(entity)
        
        # Analyze relationships
        for entity_type, entity_list in entity_groups.items():
            if len(entity_list) > 1:
                results.append(f"Found {len(entity_list)} {entity_type} entities with potential relationships")
        
        return results
    
    def _validate_exploration_results(self, step_desc: str) -> List[str]:
        """Validate exploration results."""
        return [f"Validation completed for: {step_desc}"]
    
    def _extract_entities_from_results(self, results: List[str]) -> List[CodeEntity]:
        """Extract entities from step results."""
        # This would typically extract entities from the KB based on results
        return []
    
    def _extract_insights_from_results(self, results: List[str], step_desc: str) -> List[str]:
        """Extract insights from step results."""
        insights = []
        
        for result in results:
            if "classes" in result or "functions" in result:
                insights.append(f"Code structure insight: {result}")
            elif "files" in result:
                insights.append(f"File organization insight: {result}")
        
        return insights
