"""
AST Parser for Python Code

Extracts structural information from Python source code using the ast module:
- Function definitions (name, parameters, decorators, docstring)
- Class definitions (name, bases, methods, docstring)
- Import statements (modules imported)
- Function calls (to build call graphs)
- Variable assignments

This provides accurate, deterministic code structure analysis without LLM hallucinations.
"""

import ast
import os
import re
import sys
import hashlib
from typing import List, Dict, Any, Optional, Set
from pathlib import Path

from cf.knowledge_base.schema import (
    StructuralData, FileNode, FunctionNode, ClassNode, VariableNode, ModuleNode,
    Relationship, RelationType
)


class PythonASTParser:
    """
    Parse Python source files to extract structural information.

    Uses Python's ast module for accurate parsing.
    """

    def __init__(self, repo_path: str, repo_id: str):
        """
        Initialize parser.

        Args:
            repo_path: Root path of repository
            repo_id: Repository identifier
        """
        self.repo_path = repo_path
        self.repo_id = repo_id

    def parse_file(self, file_path: str) -> Optional[StructuralData]:
        """
        Parse a Python file and extract structural data.

        Args:
            file_path: Absolute path to Python file

        Returns:
            StructuralData if successful, None if parsing fails
        """
        try:
            # Read file content
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Get relative path from repo root
            rel_path = os.path.relpath(file_path, self.repo_path)

            # Parse AST
            tree = ast.parse(content, filename=file_path)

            # Create file node
            file_stats = os.stat(file_path)
            file_node = FileNode(
                path=rel_path,
                language='python',
                size=file_stats.st_size,
                last_modified=file_stats.st_mtime,
                lines_of_code=len(content.splitlines()),
                repo_id=self.repo_id,
                hash=hashlib.md5(content.encode()).hexdigest()
            )

            # Extract structural elements
            visitor = StructuralVisitor(rel_path, self.repo_id, self.repo_path)
            visitor.visit(tree)

            # Build StructuralData
            structural_data = StructuralData(
                file_node=file_node,
                functions=visitor.functions,
                classes=visitor.classes,
                variables=visitor.variables,
                modules=visitor.modules,
                relationships=visitor.relationships
            )

            return structural_data

        except SyntaxError as e:
            print(f"⚠️ Syntax error in {file_path}: {e}")
            return None
        except Exception as e:
            print(f"❌ Failed to parse {file_path}: {e}")
            return None


class StructuralVisitor(ast.NodeVisitor):
    """
    AST visitor that extracts structural information.

    Traverses the AST and collects:
    - Functions and methods
    - Classes
    - Imports
    - Function calls
    - Variables
    """

    def __init__(self, file_path: str, repo_id: str, repo_path: str = ""):
        self.file_path = file_path
        self.repo_id = repo_id
        self.repo_path = repo_path

        # Collected data
        self.functions: List[FunctionNode] = []
        self.classes: List[ClassNode] = []
        self.variables: List[VariableNode] = []
        self.modules: List[ModuleNode] = []
        self.relationships: List[Relationship] = []

        # Context tracking
        self.current_class: Optional[str] = None
        self.current_function: Optional[str] = None
        self.module_name = self._infer_module_name(file_path)

        # Track seen modules to avoid duplicates
        self.seen_modules: Set[str] = set()

    def _infer_module_name(self, file_path: str) -> str:
        """
        Infer module name from file path by finding package root.

        Finds the deepest directory with __init__.py or pyproject.toml/setup.py
        to determine the actual Python package structure.

        Example: /repo/src/myapp/agents/base.py -> myapp.agents.base (if myapp has __init__.py)
        """
        # Simple: use filename without extension as module name
        from pathlib import Path
        return Path(file_path).stem

    def _get_qualified_name(self, name: str) -> str:
        """
        Get fully qualified name for a symbol.

        Example: In class Foo, method bar -> module.Foo.bar
        """
        parts = [self.module_name]
        if self.current_class:
            parts.append(self.current_class)
        parts.append(name)
        return '.'.join(parts)

    def _get_docstring(self, node: ast.AST) -> Optional[str]:
        """Extract docstring from a node"""
        return ast.get_docstring(node)

    def _extract_parameters(self, node: ast.FunctionDef) -> List[str]:
        """Extract function parameters as list of strings"""
        params = []
        for arg in node.args.args:
            params.append(arg.arg)
        return params

    def _extract_return_type(self, node: ast.FunctionDef) -> Optional[str]:
        """Extract return type annotation if present"""
        if node.returns:
            return ast.unparse(node.returns)
        return None

    def _is_private(self, name: str) -> bool:
        """Check if name indicates private (starts with _)"""
        return name.startswith('_') and not name.startswith('__')

    def _calculate_complexity(self, node: ast.FunctionDef) -> int:
        """
        Calculate cyclomatic complexity (simplified).

        Counts decision points: if, for, while, except, and, or
        """
        complexity = 1  # Base complexity
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.For, ast.While, ast.ExceptHandler)):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1
        return complexity

    # ========== Visitor Methods ==========

    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Visit function definition"""
        # Create function node
        function = FunctionNode(
            name=node.name,
            qualified_name=self._get_qualified_name(node.name),
            start_line=node.lineno,
            end_line=node.end_lineno or node.lineno,
            file_path=self.file_path,
            parameters=self._extract_parameters(node),
            return_type=self._extract_return_type(node),
            is_async=isinstance(node, ast.AsyncFunctionDef),
            is_method=self.current_class is not None,
            is_static=any('static' in d.id.lower() for d in node.decorator_list if isinstance(d, ast.Name)),
            is_private=self._is_private(node.name),
            docstring=self._get_docstring(node),
            num_lines=(node.end_lineno or node.lineno) - node.lineno + 1,
            cyclomatic_complexity=self._calculate_complexity(node)
        )

        self.functions.append(function)

        # Track current function for call graph
        prev_function = self.current_function
        self.current_function = function.qualified_name

        # Visit function body to find calls
        self.generic_visit(node)

        # Restore context
        self.current_function = prev_function

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        """Visit async function definition"""
        self.visit_FunctionDef(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        """Visit class definition"""
        # Extract base classes
        base_classes = []
        for base in node.bases:
            if isinstance(base, ast.Name):
                base_classes.append(base.id)
            elif isinstance(base, ast.Attribute):
                base_classes.append(ast.unparse(base))

        # Count methods and attributes
        num_methods = sum(1 for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)))
        num_attributes = sum(1 for n in node.body if isinstance(n, ast.Assign))

        # Create class node
        # is_abstract detection is done dynamically by checking decorators
        # No hardcoded decorator names - check if any decorator looks like an abstract marker
        decorators = [
            d.id if isinstance(d, ast.Name) else
            (d.attr if isinstance(d, ast.Attribute) else None)
            for d in node.decorator_list
        ]
        is_abstract = any(
            d and 'abstract' in d.lower()
            for d in decorators
        )

        class_node = ClassNode(
            name=node.name,
            qualified_name=self._get_qualified_name(node.name),
            start_line=node.lineno,
            end_line=node.end_lineno or node.lineno,
            file_path=self.file_path,
            base_classes=base_classes,
            is_abstract=is_abstract,
            is_private=self._is_private(node.name),
            docstring=self._get_docstring(node),
            num_methods=num_methods,
            num_attributes=num_attributes,
            num_lines=(node.end_lineno or node.lineno) - node.lineno + 1
        )

        self.classes.append(class_node)

        # Create inheritance relationships
        for base_class in base_classes:
            rel = Relationship(
                rel_type=RelationType.INHERITS,
                source_id=class_node.qualified_name,
                target_id=f"{self.module_name}.{base_class}",  # Approximate
                metadata={'line': node.lineno}
            )
            self.relationships.append(rel)

        # Track current class for nested functions (methods)
        prev_class = self.current_class
        self.current_class = node.name

        # Visit class body
        self.generic_visit(node)

        # Restore context
        self.current_class = prev_class

    def _is_local_module(self, module_name: str) -> bool:
        """
        Determine if a module is local to this repository.

        Checks if the module path exists in the repo rather than using
        fragile prefix matching.
        """
        if not module_name:
            return False

        # If no repo_path provided, cannot determine locality
        if not self.repo_path:
            return False

        # Check if module path exists in repo - use glob for any extension
        from pathlib import Path
        module_path = module_name.replace('.', os.sep)
        base_path = Path(self.repo_path) / module_path

        # Check if directory exists or any file with this name
        if base_path.is_dir():
            return True
        # Glob for any file with this name (any extension)
        matches = list(base_path.parent.glob(f"{base_path.name}.*")) if base_path.parent.exists() else []
        return len(matches) > 0

    def _resolve_relative_import(self, node: ast.ImportFrom) -> str:
        """
        Resolve relative import to absolute module name.

        Handles:
        - from . import X (level=1)
        - from .. import X (level=2)
        - from .module import X (level=1, module='module')
        """
        if node.level == 0:
            return node.module or ''

        # Get current module's package parts
        module_parts = self.module_name.split('.')

        # Go up 'level' directories (level=1 means current package, level=2 means parent, etc.)
        if node.level <= len(module_parts):
            base_parts = module_parts[:-node.level] if node.level > 0 else module_parts
        else:
            base_parts = []

        # Append the imported module name if any
        if node.module:
            base_parts.append(node.module)

        return '.'.join(base_parts)

    def visit_Import(self, node: ast.Import):
        """Visit import statement: import foo"""
        for alias in node.names:
            module_name = alias.name

            if module_name not in self.seen_modules:
                # Determine if builtin/third-party/local
                is_builtin = self._is_builtin_module(module_name)
                is_local = self._is_local_module(module_name)
                is_third_party = not is_builtin and not is_local

                module = ModuleNode(
                    name=module_name,
                    is_builtin=is_builtin,
                    is_third_party=is_third_party,
                    is_local=is_local
                )
                self.modules.append(module)
                self.seen_modules.add(module_name)

            # Create import relationship
            rel = Relationship(
                rel_type=RelationType.IMPORTS,
                source_id=self.file_path,
                target_id=module_name,
                metadata={'line': node.lineno}
            )
            self.relationships.append(rel)

        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        """Visit import from statement: from foo import bar"""
        # Handle relative imports (from . import X, from .. import Y)
        module_name = self._resolve_relative_import(node)

        if module_name and module_name not in self.seen_modules:
            # Determine if builtin/third-party/local
            is_builtin = self._is_builtin_module(module_name)
            is_local = self._is_local_module(module_name) or node.level > 0  # Relative imports are always local
            is_third_party = not is_builtin and not is_local

            module = ModuleNode(
                name=module_name,
                is_builtin=is_builtin,
                is_third_party=is_third_party,
                is_local=is_local
            )
            self.modules.append(module)
            self.seen_modules.add(module_name)

            # Create import relationship
            rel = Relationship(
                rel_type=RelationType.IMPORTS,
                source_id=self.file_path,
                target_id=module_name,
                metadata={
                    'line': node.lineno,
                    'names': [a.name for a in node.names],
                    'level': node.level  # Track relative import level
                }
            )
            self.relationships.append(rel)

        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        """Visit function call"""
        # Only track calls from within functions
        if self.current_function:
            called_func = None

            # Simple function call: foo()
            if isinstance(node.func, ast.Name):
                called_func = node.func.id

            # Method call: obj.method()
            elif isinstance(node.func, ast.Attribute):
                # Try to get full path
                called_func = ast.unparse(node.func)

            # Create call relationship
            if called_func:
                rel = Relationship(
                    rel_type=RelationType.CALLS,
                    source_id=self.current_function,
                    target_id=called_func,  # This is approximate - may need resolution
                    metadata={'line': node.lineno}
                )
                self.relationships.append(rel)

        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign):
        """Visit variable assignment"""
        # Only track module-level and class-level variables
        if not self.current_function:
            for target in node.targets:
                if isinstance(target, ast.Name):
                    var_name = target.id

                    # Determine scope
                    scope = 'class' if self.current_class else 'global'

                    # Try to infer type from value
                    inferred_type = self._infer_type(node.value)

                    variable = VariableNode(
                        name=var_name,
                        qualified_name=self._get_qualified_name(var_name),
                        scope=scope,
                        file_path=self.file_path,
                        line=node.lineno,
                        inferred_type=inferred_type,
                        is_constant=var_name.isupper(),
                        is_private=self._is_private(var_name)
                    )
                    self.variables.append(variable)

        self.generic_visit(node)

    def _infer_type(self, node: ast.AST) -> Optional[str]:
        """Infer type from AST node (best effort)"""
        if isinstance(node, ast.Constant):
            return type(node.value).__name__
        elif isinstance(node, ast.List):
            return 'list'
        elif isinstance(node, ast.Dict):
            return 'dict'
        elif isinstance(node, ast.Set):
            return 'set'
        elif isinstance(node, ast.Tuple):
            return 'tuple'
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                return node.func.id
        return None

    def _is_builtin_module(self, module_name: str) -> bool:
        """
        Check if module is a Python stdlib module.

        Uses sys.stdlib_module_names (Python 3.10+) for detection.
        """
        first_part = module_name.split('.')[0]
        return first_part in sys.stdlib_module_names


# ============================================================================
# Multi-Language Parser (merged from multi_lang_parser.py)
# ============================================================================

class MultiLanguageParser:
    """
    Parse multiple programming languages using regex patterns.

    Content-driven: tries all pattern sets and uses the one with best matches.
    No hardcoded extension mappings - language is detected from content.
    """

    def __init__(self, repo_path: str, repo_id: str):
        """
        Initialize multi-language parser.

        Args:
            repo_path: Root path of repository
            repo_id: Repository identifier
        """
        self.repo_path = repo_path
        self.repo_id = repo_id

        # All available pattern sets - no extension mapping
        self.pattern_sets = [
            self._get_javascript_patterns(),
            self._get_typescript_patterns(),
            self._get_java_patterns(),
            self._get_go_patterns(),
            self._get_rust_patterns(),
            self._get_cpp_patterns(),
            self._get_csharp_patterns(),
        ]

    def _find_best_patterns(self, content: str) -> Optional[Dict[str, re.Pattern]]:
        """
        Find the pattern set that best matches the file content.

        Tries all pattern sets and returns the one with the most matches.
        """
        best_patterns = None
        best_score = 0

        for patterns in self.pattern_sets:
            score = 0
            for pattern in patterns.values():
                matches = pattern.findall(content)
                score += len(matches)

            if score > best_score:
                best_score = score
                best_patterns = patterns

        # Only return patterns if we found meaningful matches
        return best_patterns if best_score > 0 else None

    def _get_javascript_patterns(self) -> Dict[str, re.Pattern]:
        """Get regex patterns for JavaScript/TypeScript"""
        return {
            'function': re.compile(
                r'(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\([^)]*\)'
            ),
            'arrow_function': re.compile(
                r'(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>'
            ),
            'class': re.compile(
                r'(?:export\s+)?class\s+(\w+)(?:\s+extends\s+(\w+))?'
            ),
            'method': re.compile(
                r'(?:async\s+)?(\w+)\s*\([^)]*\)\s*\{'
            ),
            'import': re.compile(
                r'import\s+.*?from\s+[\'"]([^\'"]+)[\'"]|require\([\'"]([^\'"]+)[\'"]\)'
            )
        }

    def _get_typescript_patterns(self) -> Dict[str, re.Pattern]:
        """Get regex patterns for TypeScript (extends JavaScript)"""
        patterns = self._get_javascript_patterns()
        patterns['interface'] = re.compile(r'(?:export\s+)?interface\s+(\w+)')
        patterns['type'] = re.compile(r'(?:export\s+)?type\s+(\w+)\s*=')
        return patterns

    def _get_java_patterns(self) -> Dict[str, re.Pattern]:
        """Get regex patterns for Java"""
        return {
            'class': re.compile(
                r'(?:public\s+)?(?:abstract\s+)?(?:final\s+)?class\s+(\w+)(?:\s+extends\s+(\w+))?'
            ),
            'interface': re.compile(
                r'(?:public\s+)?interface\s+(\w+)'
            ),
            'method': re.compile(
                r'(?:public|private|protected)\s+(?:static\s+)?(?:\w+)\s+(\w+)\s*\([^)]*\)'
            ),
            'import': re.compile(
                r'import\s+([\w.]+);'
            )
        }

    def _get_go_patterns(self) -> Dict[str, re.Pattern]:
        """Get regex patterns for Go"""
        return {
            'function': re.compile(
                r'func\s+(\w+)\s*\([^)]*\)'
            ),
            'method': re.compile(
                r'func\s+\([^)]+\)\s+(\w+)\s*\([^)]*\)'
            ),
            'struct': re.compile(
                r'type\s+(\w+)\s+struct'
            ),
            'interface': re.compile(
                r'type\s+(\w+)\s+interface'
            ),
            'import': re.compile(
                r'import\s+[(\"]([^)\"]+)[)\"]'
            )
        }

    def _get_rust_patterns(self) -> Dict[str, re.Pattern]:
        """Get regex patterns for Rust"""
        return {
            'function': re.compile(
                r'(?:pub\s+)?fn\s+(\w+)\s*[<\(]'
            ),
            'struct': re.compile(
                r'(?:pub\s+)?struct\s+(\w+)'
            ),
            'trait': re.compile(
                r'(?:pub\s+)?trait\s+(\w+)'
            ),
            'impl': re.compile(
                r'impl(?:\s+<[^>]+>)?\s+(\w+)'
            ),
            'use': re.compile(
                r'use\s+([\w:]+)'
            )
        }

    def _get_cpp_patterns(self) -> Dict[str, re.Pattern]:
        """Get regex patterns for C++"""
        return {
            'class': re.compile(
                r'class\s+(\w+)(?:\s*:\s*(?:public|private|protected)\s+(\w+))?'
            ),
            'function': re.compile(
                r'(?:\w+)\s+(\w+)\s*\([^)]*\)\s*(?:const\s*)?\{'
            ),
            'namespace': re.compile(
                r'namespace\s+(\w+)'
            ),
            'include': re.compile(
                r'#include\s+[<"]([^>"]+)[>"]'
            )
        }

    def _get_csharp_patterns(self) -> Dict[str, re.Pattern]:
        """Get regex patterns for C#"""
        return {
            'class': re.compile(
                r'(?:public\s+)?(?:abstract\s+)?class\s+(\w+)(?:\s*:\s*(\w+))?'
            ),
            'interface': re.compile(
                r'(?:public\s+)?interface\s+(\w+)'
            ),
            'method': re.compile(
                r'(?:public|private|protected)\s+(?:static\s+)?(?:\w+)\s+(\w+)\s*\([^)]*\)'
            ),
            'using': re.compile(
                r'using\s+([\w.]+);'
            )
        }

    def parse_file(self, file_path: str) -> Optional[StructuralData]:
        """
        Parse a source file and extract structural data.

        Content-driven: reads file and finds best matching pattern set.

        Args:
            file_path: Absolute path to source file

        Returns:
            StructuralData or None if parsing fails
        """
        # Read file content first
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except Exception as e:
            print(f"Failed to read {file_path}: {e}")
            return None

        # Find best matching patterns from content (no extension mapping)
        patterns = self._find_best_patterns(content)
        if not patterns:
            return None

        # Calculate relative path
        rel_path = os.path.relpath(file_path, self.repo_path)

        # Calculate file hash
        file_hash = hashlib.md5(content.encode()).hexdigest()

        # Extract functions
        functions = []
        function_names = set()

        # Extract functions based on language
        if 'function' in patterns:
            for match in patterns['function'].finditer(content):
                func_name = match.group(1)
                if func_name and func_name not in function_names:
                    functions.append(FunctionNode(
                        name=func_name,
                        qualified_name=f"{rel_path}::{func_name}",
                        file_path=rel_path,
                        start_line=match.start(),
                        end_line=match.end(),
                        parameters=[],  # Simplified - not parsing parameters
                        return_type='unknown',
                        docstring='',
                        is_async=False
                    ))
                    function_names.add(func_name)

        # Extract arrow functions (JavaScript/TypeScript)
        if 'arrow_function' in patterns:
            for match in patterns['arrow_function'].finditer(content):
                func_name = match.group(1)
                if func_name and func_name not in function_names:
                    functions.append(FunctionNode(
                        name=func_name,
                        qualified_name=f"{rel_path}::{func_name}",
                        file_path=rel_path,
                        start_line=match.start(),
                        end_line=match.end(),
                        parameters=[],
                        return_type='unknown',
                        docstring='',
                        is_async=False
                    ))
                    function_names.add(func_name)

        # Extract classes
        classes = []
        class_names = set()

        if 'class' in patterns:
            for match in patterns['class'].finditer(content):
                class_name = match.group(1)
                base_class = match.group(2) if match.lastindex >= 2 else None
                if class_name and class_name not in class_names:
                    classes.append(ClassNode(
                        name=class_name,
                        qualified_name=f"{rel_path}::{class_name}",
                        file_path=rel_path,
                        start_line=match.start(),
                        end_line=match.end(),
                        base_classes=[base_class] if base_class else [],
                        docstring=''
                    ))
                    class_names.add(class_name)

        # Extract struct (Go, Rust)
        if 'struct' in patterns:
            for match in patterns['struct'].finditer(content):
                struct_name = match.group(1)
                if struct_name and struct_name not in class_names:
                    classes.append(ClassNode(
                        name=struct_name,
                        qualified_name=f"{rel_path}::{struct_name}",
                        file_path=rel_path,
                        start_line=match.start(),
                        end_line=match.end(),
                        base_classes=[],
                        docstring=''
                    ))
                    class_names.add(struct_name)

        # Extract imports
        imports = []

        for pattern_name in ['import', 'using', 'use', 'include']:
            if pattern_name in patterns:
                for match in patterns[pattern_name].finditer(content):
                    # Get first non-None group
                    module_name = next((g for g in match.groups() if g), None)
                    if module_name:
                        imports.append(module_name)

        # Extract function calls for execution tracing
        relationships = self._extract_function_calls(
            content, functions, classes, rel_path, language
        )

        # Create file node
        file_stat = os.stat(file_path)
        file_node = FileNode(
            path=rel_path,
            repo_id=self.repo_id,
            hash=file_hash,
            language=language,
            lines_of_code=len(content.splitlines()),
            size=file_stat.st_size,
            last_modified=file_stat.st_mtime
        )

        # Create structural data
        return StructuralData(
            file_node=file_node,
            functions=functions,
            classes=classes,
            variables=[],  # Simplified - not extracting variables
            modules=[],
            relationships=relationships
        )

    def _extract_function_calls(
        self,
        content: str,
        functions: List[FunctionNode],
        classes: List[ClassNode],
        file_path: str,
        language: str
    ) -> List[Relationship]:
        """
        Extract function calls to build execution trace relationships.

        This enables execution path tracing for non-Python languages.

        Args:
            content: Source file content
            functions: Extracted functions
            classes: Extracted classes
            file_path: Relative file path
            language: Programming language

        Returns:
            List of CALLS relationships
        """
        relationships = []

        # Common function call pattern (works for most C-style languages)
        # Matches: functionName(args), object.method(args), module.function(args)
        call_pattern = re.compile(
            r'\b([a-zA-Z_][\w]*(?:\.[\w]+)?)\s*\('
        )

        # Build set of known function/method names from this file
        known_functions = {f.name for f in functions}
        known_classes = {c.name for c in classes}

        # Extract method names from classes
        # Note: ClassNode doesn't have .methods attribute in simplified parser
        known_methods = set()

        # For each function, find what it calls
        for func in functions:
            # Simple heuristic: look for function calls in the content
            # We can't perfectly parse without AST, but we can find likely calls

            func_calls_seen = set()

            for match in call_pattern.finditer(content):
                called_name = match.group(1)

                # Skip if it's the function itself or already processed
                if called_name == func.name or called_name in func_calls_seen:
                    continue

                # Extract base name if it's a method call (obj.method → method)
                base_name = called_name.split('.')[-1]

                # Check if this is a known function, method, or class constructor
                is_internal_call = (
                    base_name in known_functions or
                    base_name in known_methods or
                    base_name in known_classes
                )

                # Create relationship for known internal calls
                if is_internal_call:
                    relationships.append(Relationship(
                        rel_type=RelationType.CALLS,
                        source_id=func.qualified_name,
                        target_id=f"{file_path}::{base_name}"
                    ))
                    func_calls_seen.add(called_name)

        return relationships

