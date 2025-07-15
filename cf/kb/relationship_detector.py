"""Advanced relationship detection for code entities."""

import ast
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional, Any
from dataclasses import dataclass
from datetime import datetime

from ..kb.knowledge_base import CodeEntity, CodeRelationship
from ..exceptions import AnalysisError


@dataclass
class ImportInfo:
    """Information about an import statement."""
    module: str
    alias: Optional[str] = None
    from_module: Optional[str] = None
    is_relative: bool = False
    line_number: int = 0


@dataclass
class CallInfo:
    """Information about a function/method call."""
    caller: str
    callee: str
    call_type: str  # "function", "method", "class_instantiation"
    line_number: int
    context: str = ""


@dataclass
class InheritanceInfo:
    """Information about class inheritance."""
    child_class: str
    parent_class: str
    line_number: int
    is_multiple: bool = False


class RelationshipDetector:
    """Detects relationships between code entities using AST analysis."""
    
    def __init__(self):
        self.relationships: List[CodeRelationship] = []
        self.current_file_path: str = ""
        self.current_entities: Dict[str, CodeEntity] = {}
        
    def detect_relationships(self, entities: Dict[str, CodeEntity]) -> List[CodeRelationship]:
        """Detect all relationships between the given entities."""
        self.relationships.clear()
        self.current_entities = entities
        
        # Group entities by file for efficient processing
        entities_by_file = self._group_entities_by_file(entities)
        
        for file_path, file_entities in entities_by_file.items():
            self.current_file_path = file_path
            
            # Get the file entity to analyze its content
            file_entity = next((e for e in file_entities if e.type == "file"), None)
            if not file_entity:
                continue
                
            try:
                # Parse the file content
                if file_entity.language == "python":
                    self._analyze_python_file(file_entity, file_entities)
                elif file_entity.language == "javascript":
                    self._analyze_javascript_file(file_entity, file_entities)
                elif file_entity.language == "typescript":
                    self._analyze_typescript_file(file_entity, file_entities)
                    
            except Exception as e:
                print(f"Warning: Could not analyze relationships in {file_path}: {e}")
                continue
        
        # Detect cross-file relationships
        self._detect_cross_file_relationships(entities)
        
        return self.relationships
    
    def _group_entities_by_file(self, entities: Dict[str, CodeEntity]) -> Dict[str, List[CodeEntity]]:
        """Group entities by their file path."""
        grouped = {}
        for entity in entities.values():
            file_path = entity.path
            if file_path not in grouped:
                grouped[file_path] = []
            grouped[file_path].append(entity)
        return grouped
    
    def _analyze_python_file(self, file_entity: CodeEntity, file_entities: List[CodeEntity]):
        """Analyze Python file for relationships."""
        try:
            tree = ast.parse(file_entity.content)
            
            # Extract imports
            imports = self._extract_python_imports(tree)
            
            # Extract function calls
            calls = self._extract_python_calls(tree)
            
            # Extract inheritance relationships
            inheritances = self._extract_python_inheritance(tree)
            
            # Extract decorators and context managers
            decorators = self._extract_python_decorators(tree)
            
            # Extract exception handling
            exceptions = self._extract_python_exceptions(tree)
            
            # Create relationships
            self._create_import_relationships(imports, file_entity)
            self._create_call_relationships(calls, file_entities)
            self._create_inheritance_relationships(inheritances, file_entities)
            self._create_decorator_relationships(decorators, file_entities)
            self._create_exception_relationships(exceptions, file_entities)
            
        except SyntaxError as e:
            print(f"Warning: Syntax error in {file_entity.path}: {e}")
        except Exception as e:
            print(f"Warning: Error analyzing Python file {file_entity.path}: {e}")
    
    def _analyze_javascript_file(self, file_entity: CodeEntity, file_entities: List[CodeEntity]):
        """Analyze JavaScript file for relationships (basic implementation)."""
        content = file_entity.content
        
        # Extract require/import statements
        import_patterns = [
            r'require\([\'"]([^\'"]+)[\'"]\)',
            r'import\s+.*?\s+from\s+[\'"]([^\'"]+)[\'"]',
            r'import\s+[\'"]([^\'"]+)[\'"]'
        ]
        
        imports = []
        for pattern in import_patterns:
            matches = re.finditer(pattern, content, re.MULTILINE)
            for match in matches:
                imports.append(ImportInfo(
                    module=match.group(1),
                    line_number=content[:match.start()].count('\n') + 1
                ))
        
        # Extract function calls (basic)
        call_pattern = r'(\w+)\s*\('
        calls = []
        for match in re.finditer(call_pattern, content):
            calls.append(CallInfo(
                caller="",  # Would need more sophisticated parsing
                callee=match.group(1),
                call_type="function",
                line_number=content[:match.start()].count('\n') + 1
            ))
        
        # Create relationships
        self._create_import_relationships(imports, file_entity)
        self._create_call_relationships(calls, file_entities)
    
    def _analyze_typescript_file(self, file_entity: CodeEntity, file_entities: List[CodeEntity]):
        """Analyze TypeScript file for relationships."""
        # For now, use JavaScript analysis as a base
        self._analyze_javascript_file(file_entity, file_entities)
        
        # TODO: Add TypeScript-specific analysis (interfaces, types, etc.)
    
    def _extract_python_imports(self, tree: ast.AST) -> List[ImportInfo]:
        """Extract import information from Python AST."""
        imports = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(ImportInfo(
                        module=alias.name,
                        alias=alias.asname,
                        line_number=node.lineno
                    ))
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    imports.append(ImportInfo(
                        module=alias.name,
                        alias=alias.asname,
                        from_module=module,
                        is_relative=node.level > 0,
                        line_number=node.lineno
                    ))
        
        return imports
    
    def _extract_python_calls(self, tree: ast.AST) -> List[CallInfo]:
        """Extract function call information from Python AST."""
        calls = []
        
        class CallVisitor(ast.NodeVisitor):
            def __init__(self):
                self.current_function = None
                self.current_class = None
                
            def visit_FunctionDef(self, node):
                old_function = self.current_function
                self.current_function = node.name
                self.generic_visit(node)
                self.current_function = old_function
                
            def visit_ClassDef(self, node):
                old_class = self.current_class
                self.current_class = node.name
                self.generic_visit(node)
                self.current_class = old_class
                
            def visit_Call(self, node):
                caller = self.current_function or self.current_class or "module"
                
                # Extract callee name
                callee = ""
                call_type = "function"
                
                if isinstance(node.func, ast.Name):
                    callee = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    callee = node.func.attr
                    call_type = "method"
                elif isinstance(node.func, ast.Call):
                    # Nested call
                    callee = "nested_call"
                
                if callee:
                    calls.append(CallInfo(
                        caller=caller,
                        callee=callee,
                        call_type=call_type,
                        line_number=node.lineno
                    ))
                
                self.generic_visit(node)
        
        visitor = CallVisitor()
        visitor.visit(tree)
        return calls
    
    def _extract_python_inheritance(self, tree: ast.AST) -> List[InheritanceInfo]:
        """Extract inheritance information from Python AST."""
        inheritances = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for base in node.bases:
                    parent_name = ""
                    if isinstance(base, ast.Name):
                        parent_name = base.id
                    elif isinstance(base, ast.Attribute):
                        parent_name = base.attr
                    
                    if parent_name:
                        inheritances.append(InheritanceInfo(
                            child_class=node.name,
                            parent_class=parent_name,
                            line_number=node.lineno,
                            is_multiple=len(node.bases) > 1
                        ))
        
        return inheritances
    
    def _extract_python_decorators(self, tree: ast.AST) -> List[Tuple[str, str, int]]:
        """Extract decorator usage from Python AST."""
        decorators = []
        
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                for decorator in node.decorator_list:
                    decorator_name = ""
                    if isinstance(decorator, ast.Name):
                        decorator_name = decorator.id
                    elif isinstance(decorator, ast.Attribute):
                        decorator_name = decorator.attr
                    elif isinstance(decorator, ast.Call):
                        if isinstance(decorator.func, ast.Name):
                            decorator_name = decorator.func.id
                        elif isinstance(decorator.func, ast.Attribute):
                            decorator_name = decorator.func.attr
                    
                    if decorator_name:
                        decorators.append((node.name, decorator_name, node.lineno))
        
        return decorators
    
    def _extract_python_exceptions(self, tree: ast.AST) -> List[Tuple[str, str, int]]:
        """Extract exception handling from Python AST."""
        exceptions = []
        
        class ExceptionVisitor(ast.NodeVisitor):
            def __init__(self):
                self.current_function = None
                
            def visit_FunctionDef(self, node):
                old_function = self.current_function
                self.current_function = node.name
                self.generic_visit(node)
                self.current_function = old_function
                
            def visit_Try(self, node):
                for handler in node.handlers:
                    if handler.type:
                        exception_name = ""
                        if isinstance(handler.type, ast.Name):
                            exception_name = handler.type.id
                        elif isinstance(handler.type, ast.Attribute):
                            exception_name = handler.type.attr
                        
                        if exception_name and self.current_function:
                            exceptions.append((self.current_function, exception_name, node.lineno))
                
                self.generic_visit(node)
                
            def visit_Raise(self, node):
                if node.exc and self.current_function:
                    exception_name = ""
                    if isinstance(node.exc, ast.Name):
                        exception_name = node.exc.id
                    elif isinstance(node.exc, ast.Call) and isinstance(node.exc.func, ast.Name):
                        exception_name = node.exc.func.id
                    
                    if exception_name:
                        exceptions.append((self.current_function, exception_name, node.lineno))
                
                self.generic_visit(node)
        
        visitor = ExceptionVisitor()
        visitor.visit(tree)
        return exceptions
    
    def _create_import_relationships(self, imports: List[ImportInfo], file_entity: CodeEntity):
        """Create import relationships."""
        for imp in imports:
            # Try to find the imported entity
            target_entity = self._find_entity_by_name(imp.module)
            if target_entity:
                relationship = CodeRelationship(
                    id=f"import_{file_entity.id}_{target_entity.id}",
                    source_id=file_entity.id,
                    target_id=target_entity.id,
                    relationship_type="imports",
                    strength=1.0,
                    metadata={
                        "import_type": "from" if imp.from_module else "direct",
                        "alias": imp.alias,
                        "line_number": imp.line_number,
                        "is_relative": imp.is_relative
                    }
                )
                self.relationships.append(relationship)
    
    def _create_call_relationships(self, calls: List[CallInfo], file_entities: List[CodeEntity]):
        """Create function call relationships."""
        for call in calls:
            # Find caller entity
            caller_entity = self._find_entity_in_file(call.caller, file_entities)
            if not caller_entity:
                continue
            
            # Find callee entity
            callee_entity = self._find_entity_by_name(call.callee)
            if callee_entity:
                relationship = CodeRelationship(
                    id=f"calls_{caller_entity.id}_{callee_entity.id}_{call.line_number}",
                    source_id=caller_entity.id,
                    target_id=callee_entity.id,
                    relationship_type="calls",
                    strength=0.8,
                    metadata={
                        "call_type": call.call_type,
                        "line_number": call.line_number,
                        "context": call.context
                    }
                )
                self.relationships.append(relationship)
    
    def _create_inheritance_relationships(self, inheritances: List[InheritanceInfo], file_entities: List[CodeEntity]):
        """Create inheritance relationships."""
        for inheritance in inheritances:
            # Find child class entity
            child_entity = self._find_entity_in_file(inheritance.child_class, file_entities)
            if not child_entity:
                continue
            
            # Find parent class entity
            parent_entity = self._find_entity_by_name(inheritance.parent_class)
            if parent_entity:
                relationship = CodeRelationship(
                    id=f"inherits_{child_entity.id}_{parent_entity.id}",
                    source_id=child_entity.id,
                    target_id=parent_entity.id,
                    relationship_type="inherits",
                    strength=1.0,
                    metadata={
                        "line_number": inheritance.line_number,
                        "is_multiple": inheritance.is_multiple
                    }
                )
                self.relationships.append(relationship)
    
    def _create_decorator_relationships(self, decorators: List[Tuple[str, str, int]], file_entities: List[CodeEntity]):
        """Create decorator relationships."""
        for decorated, decorator, line_number in decorators:
            decorated_entity = self._find_entity_in_file(decorated, file_entities)
            decorator_entity = self._find_entity_by_name(decorator)
            
            if decorated_entity and decorator_entity:
                relationship = CodeRelationship(
                    id=f"decorates_{decorator_entity.id}_{decorated_entity.id}",
                    source_id=decorator_entity.id,
                    target_id=decorated_entity.id,
                    relationship_type="decorates",
                    strength=0.9,
                    metadata={
                        "line_number": line_number
                    }
                )
                self.relationships.append(relationship)
    
    def _create_exception_relationships(self, exceptions: List[Tuple[str, str, int]], file_entities: List[CodeEntity]):
        """Create exception handling relationships."""
        for function, exception, line_number in exceptions:
            function_entity = self._find_entity_in_file(function, file_entities)
            exception_entity = self._find_entity_by_name(exception)
            
            if function_entity and exception_entity:
                relationship = CodeRelationship(
                    id=f"handles_{function_entity.id}_{exception_entity.id}_{line_number}",
                    source_id=function_entity.id,
                    target_id=exception_entity.id,
                    relationship_type="handles",
                    strength=0.7,
                    metadata={
                        "line_number": line_number,
                        "exception_type": "catch_or_raise"
                    }
                )
                self.relationships.append(relationship)
    
    def _detect_cross_file_relationships(self, entities: Dict[str, CodeEntity]):
        """Detect relationships that span across files."""
        # Detect module-level relationships
        self._detect_module_relationships(entities)
        
        # Detect similar function/class names (potential refactoring opportunities)
        self._detect_similar_entities(entities)
        
        # Detect shared dependencies
        self._detect_shared_dependencies(entities)
    
    def _detect_module_relationships(self, entities: Dict[str, CodeEntity]):
        """Detect relationships between modules/packages."""
        modules = [e for e in entities.values() if e.type in ["file", "module"]]
        
        for i, module1 in enumerate(modules):
            for module2 in modules[i+1:]:
                # Check if modules are in the same package
                path1_parts = Path(module1.path).parts
                path2_parts = Path(module2.path).parts
                
                # Find common path prefix
                common_parts = []
                for p1, p2 in zip(path1_parts, path2_parts):
                    if p1 == p2:
                        common_parts.append(p1)
                    else:
                        break
                
                if len(common_parts) > 1:  # Same package
                    strength = len(common_parts) / max(len(path1_parts), len(path2_parts))
                    relationship = CodeRelationship(
                        id=f"same_package_{module1.id}_{module2.id}",
                        source_id=module1.id,
                        target_id=module2.id,
                        relationship_type="same_package",
                        strength=strength,
                        metadata={
                            "common_path": "/".join(common_parts),
                            "relationship_reason": "same_directory_structure"
                        }
                    )
                    self.relationships.append(relationship)
    
    def _detect_similar_entities(self, entities: Dict[str, CodeEntity]):
        """Detect entities with similar names or functionality."""
        entity_list = list(entities.values())
        
        for i, entity1 in enumerate(entity_list):
            for entity2 in entity_list[i+1:]:
                if entity1.type == entity2.type and entity1.type in ["function", "class"]:
                    # Calculate name similarity
                    similarity = self._calculate_name_similarity(entity1.name, entity2.name)
                    
                    if similarity > 0.7:  # High similarity threshold
                        relationship = CodeRelationship(
                            id=f"similar_{entity1.id}_{entity2.id}",
                            source_id=entity1.id,
                            target_id=entity2.id,
                            relationship_type="similar",
                            strength=similarity,
                            metadata={
                                "similarity_type": "name",
                                "similarity_score": similarity
                            }
                        )
                        self.relationships.append(relationship)
    
    def _detect_shared_dependencies(self, entities: Dict[str, CodeEntity]):
        """Detect entities that share common dependencies."""
        # Group entities by their import patterns
        import_patterns = {}
        
        for entity in entities.values():
            if entity.type == "file":
                # Extract imports from content (simplified)
                imports = re.findall(r'import\s+(\w+)', entity.content)
                imports.extend(re.findall(r'from\s+(\w+)', entity.content))
                
                for imp in imports:
                    if imp not in import_patterns:
                        import_patterns[imp] = []
                    import_patterns[imp].append(entity)
        
        # Create relationships for shared dependencies
        for imp, dependent_entities in import_patterns.items():
            if len(dependent_entities) > 1:
                for i, entity1 in enumerate(dependent_entities):
                    for entity2 in dependent_entities[i+1:]:
                        relationship = CodeRelationship(
                            id=f"shared_dep_{entity1.id}_{entity2.id}_{imp}",
                            source_id=entity1.id,
                            target_id=entity2.id,
                            relationship_type="shared_dependency",
                            strength=0.6,
                            metadata={
                                "shared_import": imp,
                                "dependency_type": "import"
                            }
                        )
                        self.relationships.append(relationship)
    
    def _find_entity_by_name(self, name: str) -> Optional[CodeEntity]:
        """Find an entity by name across all entities."""
        for entity in self.current_entities.values():
            if entity.name == name:
                return entity
        return None
    
    def _find_entity_in_file(self, name: str, file_entities: List[CodeEntity]) -> Optional[CodeEntity]:
        """Find an entity by name within specific file entities."""
        for entity in file_entities:
            if entity.name == name:
                return entity
        return None
    
    def _calculate_name_similarity(self, name1: str, name2: str) -> float:
        """Calculate similarity between two names using simple string matching."""
        if name1 == name2:
            return 1.0
        
        # Convert to lowercase for comparison
        name1, name2 = name1.lower(), name2.lower()
        
        # Calculate Levenshtein distance-based similarity
        def levenshtein_distance(s1, s2):
            if len(s1) > len(s2):
                s1, s2 = s2, s1
            
            distances = range(len(s1) + 1)
            for i2, c2 in enumerate(s2):
                distances_ = [i2 + 1]
                for i1, c1 in enumerate(s1):
                    if c1 == c2:
                        distances_.append(distances[i1])
                    else:
                        distances_.append(1 + min((distances[i1], distances[i1 + 1], distances_[-1])))
                distances = distances_
            return distances[-1]
        
        max_len = max(len(name1), len(name2))
        if max_len == 0:
            return 1.0
        
        distance = levenshtein_distance(name1, name2)
        similarity = 1.0 - (distance / max_len)
        
        return max(0.0, similarity)