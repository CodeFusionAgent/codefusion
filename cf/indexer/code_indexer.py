"""Code Indexer for agentic exploration and knowledge base population."""

import hashlib
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Optional, Any, Set
from datetime import datetime
import uuid

from ..aci.repo import CodeRepo, FileInfo
from ..kb.knowledge_base import CodeKB, CodeEntity, CodeRelationship
from ..config import CfConfig


class ExplorationStrategy(ABC):
    """Abstract base class for exploration strategies."""
    
    def __init__(self, name: str):
        self.name = name
    
    @abstractmethod
    def explore(self, repo: CodeRepo, kb: CodeKB, config: CfConfig) -> Dict[str, Any]:
        """Execute the exploration strategy."""
        pass


class ReactExploration(ExplorationStrategy):
    """ReAct (Reasoning + Acting) exploration strategy."""
    
    def __init__(self):
        super().__init__("react")
    
    def explore(self, repo: CodeRepo, kb: CodeKB, config: CfConfig) -> Dict[str, Any]:
        """Execute ReAct exploration."""
        results = {
            "strategy": self.name,
            "files_processed": 0,
            "entities_created": 0,
            "relationships_created": 0,
            "errors": []
        }
        
        try:
            # Step 1: Reason about the repository structure
            overview = self._analyze_repository_structure(repo)
            
            # Step 2: Act - Process high-priority files first
            priority_files = self._prioritize_files(repo, overview)
            
            # Step 3: Iteratively explore and reason
            for file_path in priority_files[:config.max_exploration_depth * 10]:
                try:
                    self._process_file(repo, kb, file_path)
                    results["files_processed"] += 1
                except Exception as e:
                    results["errors"].append(f"Error processing {file_path}: {str(e)}")
            
            # Step 4: Create relationships between entities
            self._create_relationships(kb)
            
            results["entities_created"] = len(kb._entities)
            results["relationships_created"] = len(kb._relationships)
            
        except Exception as e:
            results["errors"].append(f"ReAct exploration failed: {str(e)}")
        
        return results
    
    def _analyze_repository_structure(self, repo: CodeRepo) -> Dict[str, Any]:
        """Analyze repository structure to inform exploration."""
        stats = repo.get_repository_stats()
        
        # Identify key directories and files
        important_files = []
        for file_info in repo.walk_repository():
            if not file_info.is_directory:
                # Look for important files
                if any(keyword in file_info.path.lower() for keyword in 
                       ['main', 'index', 'app', 'server', 'client', 'core', 'base']):
                    important_files.append(file_info.path)
        
        return {
            "stats": stats,
            "important_files": important_files[:20]  # Top 20 important files
        }
    
    def _prioritize_files(self, repo: CodeRepo, overview: Dict[str, Any]) -> List[str]:
        """Prioritize files for exploration based on reasoning."""
        priority_files = []
        
        # Add important files first
        priority_files.extend(overview["important_files"])
        
        # Add configuration files
        config_patterns = ['config', 'settings', 'env', 'package.json', 'requirements.txt', 'setup.py']
        for file_info in repo.walk_repository():
            if not file_info.is_directory:
                if any(pattern in file_info.path.lower() for pattern in config_patterns):
                    if file_info.path not in priority_files:
                        priority_files.append(file_info.path)
        
        # Add remaining files, prioritizing by extension
        priority_extensions = ['.py', '.js', '.ts', '.java', '.cpp', '.c', '.cs', '.go', '.rs']
        for ext in priority_extensions:
            for file_info in repo.walk_repository():
                if not file_info.is_directory and file_info.extension == ext:
                    if file_info.path not in priority_files:
                        priority_files.append(file_info.path)
        
        return priority_files
    
    def _process_file(self, repo: CodeRepo, kb: CodeKB, file_path: str) -> None:
        """Process a single file and extract entities."""
        try:
            content = repo.read_file(file_path)
            file_info = repo.get_file_info(file_path)
            
            # Create file entity
            file_entity = CodeEntity(
                id=self._generate_id("file", file_path),
                name=Path(file_path).name,
                type="file",
                path=file_path,
                content=content[:1000],  # Store first 1000 chars for search
                language=self._detect_language(file_info.extension),
                size=file_info.size,
                created_at=datetime.now(),
                metadata={
                    "extension": file_info.extension,
                    "modified_time": file_info.modified_time,
                    "line_count": len(content.splitlines()),
                    "char_count": len(content)
                }
            )
            
            kb.add_entity(file_entity)
            
            # Extract code entities (classes, functions) if it's a code file
            if file_entity.language != "unknown":
                self._extract_code_entities(content, file_path, file_entity.language, kb)
                
        except Exception as e:
            raise Exception(f"Failed to process file {file_path}: {str(e)}")
    
    def _extract_code_entities(self, content: str, file_path: str, language: str, kb: CodeKB) -> None:
        """Extract classes, functions, and other code entities."""
        lines = content.splitlines()
        
        if language == "python":
            self._extract_python_entities(lines, file_path, content, kb)
        elif language in ["javascript", "typescript"]:
            self._extract_js_entities(lines, file_path, content, kb)
        # Add more language support as needed
    
    def _extract_python_entities(self, lines: List[str], file_path: str, content: str, kb: CodeKB) -> None:
        """Extract Python classes and functions."""
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # Extract classes
            if stripped.startswith("class "):
                match = re.match(r'class\s+(\w+)', stripped)
                if match:
                    class_name = match.group(1)
                    entity = CodeEntity(
                        id=self._generate_id("class", f"{file_path}:{class_name}"),
                        name=class_name,
                        type="class",
                        path=file_path,
                        content=self._extract_block(lines, i),
                        language="python",
                        size=len(self._extract_block(lines, i)),
                        created_at=datetime.now(),
                        metadata={"line_number": i + 1, "file_path": file_path}
                    )
                    kb.add_entity(entity)
            
            # Extract functions
            elif stripped.startswith("def "):
                match = re.match(r'def\s+(\w+)', stripped)
                if match:
                    func_name = match.group(1)
                    entity = CodeEntity(
                        id=self._generate_id("function", f"{file_path}:{func_name}"),
                        name=func_name,
                        type="function",
                        path=file_path,
                        content=self._extract_block(lines, i),
                        language="python",
                        size=len(self._extract_block(lines, i)),
                        created_at=datetime.now(),
                        metadata={"line_number": i + 1, "file_path": file_path}
                    )
                    kb.add_entity(entity)
    
    def _extract_js_entities(self, lines: List[str], file_path: str, content: str, kb: CodeKB) -> None:
        """Extract JavaScript/TypeScript classes and functions."""
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # Extract classes
            if stripped.startswith("class "):
                match = re.match(r'class\s+(\w+)', stripped)
                if match:
                    class_name = match.group(1)
                    entity = CodeEntity(
                        id=self._generate_id("class", f"{file_path}:{class_name}"),
                        name=class_name,
                        type="class",
                        path=file_path,
                        content=self._extract_block(lines, i),
                        language="javascript",
                        size=len(self._extract_block(lines, i)),
                        created_at=datetime.now(),
                        metadata={"line_number": i + 1, "file_path": file_path}
                    )
                    kb.add_entity(entity)
            
            # Extract functions
            elif "function" in stripped or "=>" in stripped:
                func_match = re.search(r'(?:function\s+(\w+)|(?:const|let|var)\s+(\w+)\s*=)', stripped)
                if func_match:
                    func_name = func_match.group(1) or func_match.group(2)
                    if func_name:
                        entity = CodeEntity(
                            id=self._generate_id("function", f"{file_path}:{func_name}"),
                            name=func_name,
                            type="function",
                            path=file_path,
                            content=self._extract_block(lines, i),
                            language="javascript",
                            size=len(self._extract_block(lines, i)),
                            created_at=datetime.now(),
                            metadata={"line_number": i + 1, "file_path": file_path}
                        )
                        kb.add_entity(entity)
    
    def _extract_block(self, lines: List[str], start_line: int) -> str:
        """Extract a code block starting from the given line."""
        block_lines = [lines[start_line]]
        indent_level = len(lines[start_line]) - len(lines[start_line].lstrip())
        
        for i in range(start_line + 1, min(len(lines), start_line + 50)):  # Max 50 lines
            line = lines[i]
            if line.strip() == "":
                block_lines.append(line)
                continue
            
            current_indent = len(line) - len(line.lstrip())
            if current_indent <= indent_level and line.strip():
                break
            
            block_lines.append(line)
        
        return "\n".join(block_lines)
    
    def _create_relationships(self, kb: CodeKB) -> None:
        """Create relationships between entities using advanced detection."""
        print("Detecting advanced relationships...")
        
        try:
            from ..kb.relationship_detector import RelationshipDetector
            
            # Use advanced relationship detection
            relationship_detector = RelationshipDetector()
            relationships = relationship_detector.detect_relationships(kb._entities)
            
            # Add detected relationships to knowledge base
            for relationship in relationships:
                kb.add_relationship(relationship)
                
            print(f"✓ Detected {len(relationships)} relationships")
            
        except ImportError:
            print("Warning: Advanced relationship detector not available, using basic detection")
            self._create_basic_relationships(kb)
        except Exception as e:
            print(f"Warning: Advanced relationship detection failed: {e}")
            self._create_basic_relationships(kb)
    
    def _create_basic_relationships(self, kb: CodeKB) -> None:
        """Create basic relationships between entities (fallback)."""
        for entity_id, entity in kb._entities.items():
            if entity.type in ["class", "function"]:
                # Find imports/dependencies in the content
                imports = self._find_imports(entity.content, entity.language)
                for imported_item in imports:
                    # Try to find the imported entity in KB
                    for other_id, other_entity in kb._entities.items():
                        if other_entity.name == imported_item and other_id != entity_id:
                            rel = CodeRelationship(
                                id=str(uuid.uuid4()),
                                source_id=entity_id,
                                target_id=other_id,
                                relationship_type="imports",
                                strength=0.8,
                                metadata={"detected_by": "basic_exploration"}
                            )
                            kb.add_relationship(rel)
    
    def _find_imports(self, content: str, language: str) -> List[str]:
        """Find import statements in code content."""
        imports = []
        lines = content.splitlines()
        
        for line in lines:
            if language == "python":
                if line.strip().startswith("import ") or line.strip().startswith("from "):
                    # Extract import names (simplified)
                    parts = line.strip().split()
                    if len(parts) >= 2:
                        imports.append(parts[1].split('.')[0])
            elif language in ["javascript", "typescript"]:
                if "import" in line or "require(" in line:
                    # Extract import names (simplified)
                    match = re.search(r'import\s+.*?from\s+[\'"]([^\'"]+)[\'"]', line)
                    if match:
                        imports.append(match.group(1).split('/')[-1])
        
        return imports
    
    def _detect_language(self, extension: str) -> str:
        """Detect programming language from file extension."""
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
            ".rb": "ruby"
        }
        return language_map.get(extension.lower(), "unknown")
    
    def _generate_id(self, entity_type: str, identifier: str) -> str:
        """Generate a unique ID for an entity."""
        combined = f"{entity_type}:{identifier}"
        return hashlib.md5(combined.encode()).hexdigest()


class PlanActExploration(ExplorationStrategy):
    """Plan-then-Act exploration strategy."""
    
    def __init__(self):
        super().__init__("plan_act")
    
    def explore(self, repo: CodeRepo, kb: CodeKB, config: CfConfig) -> Dict[str, Any]:
        """Execute Plan-then-Act exploration."""
        # Placeholder implementation
        return {
            "strategy": self.name,
            "files_processed": 0,
            "entities_created": 0,
            "relationships_created": 0,
            "errors": ["Plan-Act strategy not yet implemented"]
        }


class SenseActExploration(ExplorationStrategy):
    """Sense-then-Act exploration strategy."""
    
    def __init__(self):
        super().__init__("sense_act")
    
    def explore(self, repo: CodeRepo, kb: CodeKB, config: CfConfig) -> Dict[str, Any]:
        """Execute Sense-then-Act exploration."""
        # Placeholder implementation
        return {
            "strategy": self.name,
            "files_processed": 0,
            "entities_created": 0,
            "relationships_created": 0,
            "errors": ["Sense-Act strategy not yet implemented"]
        }


class CodeIndexer:
    """Main code indexer that orchestrates agentic exploration."""
    
    def __init__(self, repo: CodeRepo, kb: CodeKB, config: CfConfig):
        self.repo = repo
        self.kb = kb
        self.config = config
        self.strategies = {
            "react": ReactExploration(),
            "plan_act": PlanActExploration(),
            "sense_act": SenseActExploration()
        }
    
    def index_repository(self) -> Dict[str, Any]:
        """Index the repository using the configured exploration strategy."""
        strategy_name = self.config.exploration_strategy
        strategy = self.strategies.get(strategy_name)
        
        if not strategy:
            raise ValueError(f"Unknown exploration strategy: {strategy_name}")
        
        print(f"Starting {strategy_name} exploration...")
        results = strategy.explore(self.repo, self.kb, self.config)
        
        # Create C4 mapping
        c4_mapping = self.kb.create_c4_mapping()
        results["c4_levels"] = {
            "context": len(c4_mapping.context),
            "containers": len(c4_mapping.containers), 
            "components": len(c4_mapping.components),
            "code": len(c4_mapping.code)
        }
        
        # Save knowledge base
        self.kb.save()
        
        return results
    
    def get_exploration_summary(self) -> Dict[str, Any]:
        """Get a summary of the exploration results."""
        stats = self.kb.get_statistics()
        c4 = self.kb.get_c4_mapping()
        
        return {
            "knowledge_base_stats": stats,
            "c4_mapping": {
                "context_entities": len(c4.context) if c4 else 0,
                "container_entities": len(c4.containers) if c4 else 0,
                "component_entities": len(c4.components) if c4 else 0,
                "code_entities": len(c4.code) if c4 else 0
            },
            "repository_path": self.repo.repo_path
        }