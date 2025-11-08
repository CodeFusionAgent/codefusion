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
import hashlib
from typing import List, Dict, Any, Optional, Set
from pathlib import Path

from cf.knowledge.structural.schema import (
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
            visitor = StructuralVisitor(rel_path, self.repo_id)
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

    def __init__(self, file_path: str, repo_id: str):
        self.file_path = file_path
        self.repo_id = repo_id

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
        Infer module name from file path.

        Example: src/agents/base.py -> agents.base
        """
        # Remove .py extension
        path_without_ext = file_path.replace('.py', '')
        # Replace path separators with dots
        module = path_without_ext.replace(os.sep, '.')
        # Remove leading dots
        module = module.lstrip('.')
        return module

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
            is_static='staticmethod' in [d.id for d in node.decorator_list if isinstance(d, ast.Name)],
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
        class_node = ClassNode(
            name=node.name,
            qualified_name=self._get_qualified_name(node.name),
            start_line=node.lineno,
            end_line=node.end_lineno or node.lineno,
            file_path=self.file_path,
            base_classes=base_classes,
            is_abstract=any(
                isinstance(d, ast.Name) and d.id in ('ABC', 'ABCMeta')
                for d in node.decorator_list
            ),
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

    def visit_Import(self, node: ast.Import):
        """Visit import statement: import foo"""
        for alias in node.names:
            module_name = alias.name

            if module_name not in self.seen_modules:
                # Determine if builtin/third-party/local
                is_builtin = self._is_builtin_module(module_name)
                is_local = module_name.startswith(self.module_name.split('.')[0])
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
        module_name = node.module or ''

        if module_name and module_name not in self.seen_modules:
            # Determine if builtin/third-party/local
            is_builtin = self._is_builtin_module(module_name)
            is_local = module_name.startswith(self.module_name.split('.')[0])
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
                metadata={'line': node.lineno, 'names': [a.name for a in node.names]}
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
                    var_name = target.value if isinstance(target.value, str) else str(target)

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
        """Check if module is a Python builtin"""
        builtins = {
            'os', 'sys', 'ast', 'json', 'time', 'datetime', 'collections',
            'itertools', 'functools', 'pathlib', 're', 'math', 'random',
            'typing', 'dataclasses', 'enum', 'abc', 'asyncio', 'concurrent',
            'logging', 'argparse', 'unittest', 'io', 'csv', 'hashlib', 'base64'
        }
        return module_name.split('.')[0] in builtins
