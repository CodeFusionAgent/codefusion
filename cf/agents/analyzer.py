"""
File Analyzer - File Analysis Utilities for Code Analysis

This module provides utilities for analyzing source code files:
- File content analysis with AST parsing
- Code structure extraction (functions, classes, imports)
- Language detection with multi-language support
- Complexity metrics (cyclomatic, cognitive)
- Dependency extraction and analysis
- Code pattern detection
- File categorization (config, test, model, etc.)

Used by agents to analyze and understand source code files.
"""

import ast
import re
import sys
import hashlib
import mimetypes
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum


class FileCategory(Enum):
    """Categories of source files"""
    CONFIG = "config"
    TEST = "test"
    MODEL = "model"
    VIEW = "view"
    CONTROLLER = "controller"
    UTIL = "util"
    SERVICE = "service"
    API = "api"
    MIGRATION = "migration"
    DOCUMENTATION = "documentation"
    SCRIPT = "script"
    UNKNOWN = "unknown"


class ComplexityLevel(Enum):
    """Complexity levels for code"""
    TRIVIAL = "trivial"  # 1-5
    SIMPLE = "simple"  # 6-10
    MODERATE = "moderate"  # 11-20
    COMPLEX = "complex"  # 21-50
    VERY_COMPLEX = "very_complex"  # 51+


@dataclass
class FunctionInfo:
    """Detailed information about a function"""
    name: str
    start_line: int
    end_line: int
    params: List[str]
    return_type: Optional[str] = None
    docstring: str = ""
    decorators: List[str] = field(default_factory=list)
    is_async: bool = False
    is_method: bool = False
    is_property: bool = False
    is_static: bool = False
    is_class_method: bool = False
    complexity: int = 1
    calls: List[str] = field(default_factory=list)
    local_vars: List[str] = field(default_factory=list)


@dataclass
class ClassInfo:
    """Detailed information about a class"""
    name: str
    start_line: int
    end_line: int
    bases: List[str]
    docstring: str = ""
    decorators: List[str] = field(default_factory=list)
    methods: List[FunctionInfo] = field(default_factory=list)
    class_vars: List[str] = field(default_factory=list)
    instance_vars: List[str] = field(default_factory=list)
    is_dataclass: bool = False
    is_abstract: bool = False


@dataclass
class ImportInfo:
    """Information about an import statement"""
    module: str
    names: List[str] = field(default_factory=list)
    alias: Optional[str] = None
    is_from_import: bool = False
    line_number: int = 0


@dataclass
class ConstantInfo:
    """Information about a constant (uppercase variable at module level)"""
    name: str
    value: Any  # The actual value (string, int, dict, list, etc.)
    value_repr: str  # String representation (truncated for large values)
    line_number: int = 0
    is_dict: bool = False  # True if it's a dict/mapping (status mappings, configs)
    is_list: bool = False  # True if it's a list/tuple


@dataclass
class FileInfo:
    """Comprehensive information about a source file"""
    path: str
    language: str
    size: int
    line_count: int
    functions: List[FunctionInfo] = field(default_factory=list)
    classes: List[ClassInfo] = field(default_factory=list)
    imports: List[ImportInfo] = field(default_factory=list)
    hash: str = ""
    complexity: int = 0
    category: FileCategory = FileCategory.UNKNOWN
    global_vars: List[str] = field(default_factory=list)
    constants: List[str] = field(default_factory=list)
    constant_details: List['ConstantInfo'] = field(default_factory=list)
    todos: List[Tuple[int, str]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


@dataclass
class FileSummary:
    """Summary of file analysis"""
    path: str
    language: str
    line_count: int
    function_count: int
    class_count: int
    import_count: int
    top_functions: List[str]
    top_classes: List[str]
    key_imports: List[str]
    category: FileCategory
    purpose: str = ""
    complexity_score: float = 0.0
    complexity_level: ComplexityLevel = ComplexityLevel.SIMPLE


@dataclass
class DependencyInfo:
    """Dependency analysis results"""
    internal_deps: List[str]  # Files within the project
    external_deps: List[str]  # External packages
    standard_lib: List[str]  # Python standard library
    missing_deps: List[str]  # Unresolved imports


class FileAnalyzer:
    """
    Analyzes source code files to extract structure and metadata.

    Supports:
    - Python files (full AST parsing)
    - JavaScript/TypeScript files (pattern-based)
    - Other languages (basic analysis)
    """


    @property
    def stdlib_modules(self) -> set:
        """Get standard library modules (Python 3.10+)."""
        return sys.stdlib_module_names

    def __init__(self, repo_path: str, llm_callback: Optional[Callable] = None):
        """
        Initialize file analyzer.

        Args:
            repo_path: Path to repository
            llm_callback: Optional LLM callback for enhanced analysis
        """
        self.repo_path = Path(repo_path)
        self.llm = llm_callback
        self._cache: Dict[str, FileInfo] = {}
        self._dependency_cache: Dict[str, DependencyInfo] = {}

    def analyze_file(self, file_path: str) -> Optional[FileInfo]:
        """
        Analyze a single file and extract structure.

        Args:
            file_path: Path to file (relative or absolute)

        Returns:
            FileInfo with analysis results, or None if failed
        """
        # Normalize path
        path = Path(file_path)
        if not path.is_absolute():
            path = self.repo_path / path

        if not path.exists():
            return None

        # Check cache
        cache_key = str(path)
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Read file
        try:
            content = path.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            return None

        # Detect language
        language = self._detect_language(path)

        # Create base info
        try:
            rel_path = str(path.relative_to(self.repo_path))
        except ValueError:
            rel_path = str(path)

        info = FileInfo(
            path=rel_path,
            language=language,
            size=len(content),
            line_count=content.count('\n') + 1,
            hash=hashlib.md5(content.encode()).hexdigest(),
            category=self._categorize_file(rel_path, content)
        )

        # Content-driven analysis: try AST first, fall back to pattern extraction
        try:
            # AST parsing works on valid Python syntax
            tree = ast.parse(content)
            self._analyze_python_ast(tree, content, info)
        except SyntaxError:
            # Not valid Python - use generic pattern extraction
            self._analyze_generic(content, info)

        # Extract TODOs and FIXMEs
        info.todos = self._extract_todos(content)

        # Calculate complexity
        info.complexity = self._calculate_complexity(info)

        # Cache result
        self._cache[cache_key] = info

        return info

    def _detect_language(self, path: Path) -> str:
        """Detect language from file extension using MIME types."""
        # Use MIME type detection (no hardcoded mapping)
        mime_type, _ = mimetypes.guess_type(str(path))
        if mime_type:
            # Extract language from mime type (e.g., 'text/x-python' -> 'python')
            if '/' in mime_type:
                lang_part = mime_type.split('/')[-1]
                # Clean up common prefixes
                lang_part = lang_part.replace('x-', '').replace('application/', '')
                if lang_part and lang_part != 'plain':
                    return lang_part

        # Fall back to extension as language identifier
        suffix = path.suffix.lower().lstrip('.')
        return suffix if suffix else 'unknown'

    def _categorize_file(self, file_path: str, content: str) -> FileCategory:
        """
        Return UNKNOWN - LLM determines file relevance based on content.

        File categorization is not needed for LLM-driven analysis.
        """
        return FileCategory.UNKNOWN

    def _analyze_python_ast(self, tree: ast.AST, content: str, info: FileInfo) -> None:
        """Analyze using AST (already parsed)"""
        # Walk the AST
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func_info = self._extract_function_info(node, content)
                info.functions.append(func_info)

            elif isinstance(node, ast.ClassDef):
                class_info = self._extract_class_info(node, content)
                info.classes.append(class_info)

            elif isinstance(node, ast.Import):
                for alias in node.names:
                    info.imports.append(ImportInfo(
                        module=alias.name,
                        alias=alias.asname,
                        is_from_import=False,
                        line_number=node.lineno
                    ))

            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    names = [alias.name for alias in node.names]
                    info.imports.append(ImportInfo(
                        module=node.module,
                        names=names,
                        is_from_import=True,
                        line_number=node.lineno
                    ))

            elif isinstance(node, ast.Assign):
                # Module-level assignments - enhanced to capture values
                if hasattr(node, 'lineno'):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            name = target.id
                            if name.isupper():
                                info.constants.append(name)
                                # Extract detailed constant info with value
                                const_info = self._extract_constant_info(name, node.value, node.lineno)
                                if const_info:
                                    info.constant_details.append(const_info)
                            else:
                                info.global_vars.append(name)

    def _extract_function_info(self, node: ast.AST, content: str) -> FunctionInfo:
        """Extract detailed function information from AST node"""
        is_async = isinstance(node, ast.AsyncFunctionDef)

        # Get decorators
        decorators = [self._get_decorator_name(d) for d in node.decorator_list]

        # Get parameters
        params = []
        for arg in node.args.args:
            param_str = arg.arg
            if arg.annotation:
                param_str += f": {ast.unparse(arg.annotation)}"
            params.append(param_str)

        # Get return type
        return_type = None
        if node.returns:
            return_type = ast.unparse(node.returns)

        # Get docstring
        docstring = ast.get_docstring(node) or ""

        # Check decorator types - pattern-based, not exact match
        decorators_lower = [d.lower() for d in decorators]
        is_property = any('property' in d for d in decorators_lower)
        is_static = any('static' in d for d in decorators_lower)
        is_class_method = any('classmethod' in d for d in decorators_lower)

        # Extract function calls
        calls = []
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Name):
                    calls.append(child.func.id)
                elif isinstance(child.func, ast.Attribute):
                    calls.append(child.func.attr)

        # Extract local variables
        local_vars = []
        for child in ast.walk(node):
            if isinstance(child, ast.Assign):
                for target in child.targets:
                    if isinstance(target, ast.Name):
                        local_vars.append(target.id)

        # Calculate cyclomatic complexity
        complexity = self._calculate_function_complexity(node)

        return FunctionInfo(
            name=node.name,
            start_line=node.lineno,
            end_line=node.end_lineno or node.lineno,
            params=params,
            return_type=return_type,
            docstring=docstring,
            decorators=decorators,
            is_async=is_async,
            is_property=is_property,
            is_static=is_static,
            is_class_method=is_class_method,
            complexity=complexity,
            calls=list(set(calls)),
            local_vars=list(set(local_vars))
        )

    def _extract_class_info(self, node: ast.ClassDef, content: str) -> ClassInfo:
        """Extract detailed class information from AST node"""
        # Get decorators
        decorators = [self._get_decorator_name(d) for d in node.decorator_list]

        # Get base classes
        bases = [self._get_base_name(b) for b in node.bases]

        # Get docstring
        docstring = ast.get_docstring(node) or ""

        # Check class type - pattern-based
        decorators_lower = [d.lower() for d in decorators]
        bases_lower = [b.lower() for b in bases]
        is_dataclass = any('dataclass' in d or 'data' in d for d in decorators_lower)
        is_abstract = any('abstract' in b or 'abc' in b for b in bases_lower) or any(
            'abstract' in d for d in decorators_lower
        )

        # Extract methods
        methods = []
        class_vars = []
        instance_vars = []

        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                method_info = self._extract_function_info(item, content)
                method_info.is_method = True
                methods.append(method_info)

                # Extract instance variables from __init__
                if item.name == '__init__':
                    for child in ast.walk(item):
                        if isinstance(child, ast.Assign):
                            for target in child.targets:
                                if isinstance(target, ast.Attribute):
                                    if isinstance(target.value, ast.Name) and target.value.id == 'self':
                                        instance_vars.append(target.attr)

            elif isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        class_vars.append(target.id)

            elif isinstance(item, ast.AnnAssign):
                if isinstance(item.target, ast.Name):
                    class_vars.append(item.target.id)

        return ClassInfo(
            name=node.name,
            start_line=node.lineno,
            end_line=node.end_lineno or node.lineno,
            bases=bases,
            docstring=docstring,
            decorators=decorators,
            methods=methods,
            class_vars=list(set(class_vars)),
            instance_vars=list(set(instance_vars)),
            is_dataclass=is_dataclass,
            is_abstract=is_abstract
        )

    def _calculate_function_complexity(self, node: ast.AST) -> int:
        """Calculate cyclomatic complexity for a function"""
        complexity = 1  # Base complexity

        for child in ast.walk(node):
            # Decision points
            if isinstance(child, (ast.If, ast.While, ast.For, ast.AsyncFor)):
                complexity += 1
            elif isinstance(child, ast.ExceptHandler):
                complexity += 1
            elif isinstance(child, (ast.And, ast.Or)):
                complexity += 1
            elif isinstance(child, ast.comprehension):
                complexity += 1
                if child.ifs:
                    complexity += len(child.ifs)
            elif isinstance(child, ast.Assert):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1

        return complexity

    def _get_decorator_name(self, node: ast.AST) -> str:
        """Extract decorator name from AST node"""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return node.attr
        elif isinstance(node, ast.Call):
            return self._get_decorator_name(node.func)
        return 'unknown'

    def _get_base_name(self, node: ast.AST) -> str:
        """Extract base class name from AST node"""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return node.attr
        elif isinstance(node, ast.Subscript):
            return self._get_base_name(node.value)
        return 'unknown'

    def _extract_constant_info(self, name: str, value_node: ast.AST, line_number: int) -> Optional[ConstantInfo]:
        """
        Extract detailed constant information including value.

        Handles:
        - Simple constants (int, str, float, bool)
        - Dict literals (status mappings, configs)
        - List/Tuple literals (state lists, choices)
        """
        try:
            # Try to get the actual value using ast.literal_eval
            value_repr = ast.unparse(value_node)

            # Truncate very long representations
            max_repr_length = 500
            if len(value_repr) > max_repr_length:
                value_repr = value_repr[:max_repr_length] + "..."

            # Determine type flags
            is_dict = isinstance(value_node, ast.Dict)
            is_list = isinstance(value_node, (ast.List, ast.Tuple))

            # Try to evaluate simple literals
            try:
                value = ast.literal_eval(value_repr) if len(value_repr) <= max_repr_length else value_repr
            except (ValueError, SyntaxError):
                value = value_repr  # Keep as string representation

            return ConstantInfo(
                name=name,
                value=value,
                value_repr=value_repr,
                line_number=line_number,
                is_dict=is_dict,
                is_list=is_list
            )
        except Exception:
            # If extraction fails, just return basic info
            return ConstantInfo(
                name=name,
                value=None,
                value_repr="<complex>",
                line_number=line_number,
                is_dict=False,
                is_list=False
            )

    def _analyze_generic(self, content: str, info: FileInfo) -> None:
        """Generic analysis using patterns"""
        # Find function-like patterns
        func_pattern = r'(?:def|func|function|fn)\s+(\w+)'
        for match in re.finditer(func_pattern, content, re.IGNORECASE):
            info.functions.append(FunctionInfo(
                name=match.group(1),
                start_line=content[:match.start()].count('\n') + 1,
                end_line=0,
                params=[]
            ))

        # Find class-like patterns
        class_pattern = r'(?:class|struct|interface)\s+(\w+)'
        for match in re.finditer(class_pattern, content, re.IGNORECASE):
            info.classes.append(ClassInfo(
                name=match.group(1),
                start_line=content[:match.start()].count('\n') + 1,
                end_line=0,
                bases=[]
            ))

    def _extract_todos(self, content: str) -> List[Tuple[int, str]]:
        """Extract TODO and FIXME comments"""
        todos = []
        patterns = [
            r'#\s*(TODO|FIXME|XXX|HACK|BUG):\s*(.+)',
            r'//\s*(TODO|FIXME|XXX|HACK|BUG):\s*(.+)',
            r'/\*\s*(TODO|FIXME|XXX|HACK|BUG):\s*(.+?)\*/',
        ]

        for line_num, line in enumerate(content.split('\n'), 1):
            for pattern in patterns:
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    todos.append((line_num, f"{match.group(1)}: {match.group(2).strip()}"))
                    break

        return todos

    def _calculate_complexity(self, info: FileInfo) -> int:
        """Calculate overall file complexity"""
        complexity = 1

        # Function complexity
        for func in info.functions:
            complexity += func.complexity

        # Class complexity
        for cls in info.classes:
            complexity += 2
            for method in cls.methods:
                complexity += method.complexity

        # Import complexity
        complexity += len(info.imports) // 5

        # Size complexity
        if info.line_count > 500:
            complexity += info.line_count // 500

        return complexity

    def _get_complexity_level(self, complexity: int) -> ComplexityLevel:
        """Convert complexity score to level"""
        if complexity <= 5:
            return ComplexityLevel.TRIVIAL
        elif complexity <= 10:
            return ComplexityLevel.SIMPLE
        elif complexity <= 20:
            return ComplexityLevel.MODERATE
        elif complexity <= 50:
            return ComplexityLevel.COMPLEX
        else:
            return ComplexityLevel.VERY_COMPLEX

    def summarize_file(self, file_path: str) -> Optional[FileSummary]:
        """
        Generate a summary of a file.

        Args:
            file_path: Path to file

        Returns:
            FileSummary with key information
        """
        info = self.analyze_file(file_path)
        if not info:
            return None

        # Get top functions by complexity
        sorted_funcs = sorted(info.functions, key=lambda f: f.complexity, reverse=True)
        top_functions = [f.name for f in sorted_funcs[:5]]

        # Get top classes
        top_classes = [c.name for c in info.classes[:3]]

        # Get key imports (external ones)
        key_imports = []
        for imp in info.imports:
            if not imp.module.startswith('.'):
                key_imports.append(imp.module.split('.')[0])
        key_imports = list(set(key_imports))[:10]

        # Generate purpose (could use LLM if available)
        purpose = self._infer_purpose(info)

        complexity_level = self._get_complexity_level(info.complexity)

        return FileSummary(
            path=info.path,
            language=info.language,
            line_count=info.line_count,
            function_count=len(info.functions),
            class_count=len(info.classes),
            import_count=len(info.imports),
            top_functions=top_functions,
            top_classes=top_classes,
            key_imports=key_imports,
            category=info.category,
            purpose=purpose,
            complexity_score=info.complexity / 10.0,
            complexity_level=complexity_level
        )

    def _infer_purpose(self, info: FileInfo) -> str:
        """Infer file purpose from content"""
        purposes = []

        # Based on category
        category_purposes = {
            FileCategory.CONFIG: "Configuration and settings",
            FileCategory.TEST: "Unit or integration tests",
            FileCategory.MODEL: "Data models and schemas",
            FileCategory.VIEW: "UI components and templates",
            FileCategory.CONTROLLER: "Request handling and routing",
            FileCategory.UTIL: "Utility functions and helpers",
            FileCategory.SERVICE: "Business logic services",
            FileCategory.API: "API endpoints and interfaces",
            FileCategory.MIGRATION: "Database migrations",
            FileCategory.DOCUMENTATION: "Documentation and guides",
            FileCategory.SCRIPT: "Scripts and CLI tools",
        }
        if info.category != FileCategory.UNKNOWN:
            purposes.append(category_purposes.get(info.category, ""))

        # Based on content
        if info.classes:
            class_names = [c.name for c in info.classes[:3]]
            purposes.append(f"Defines {', '.join(class_names)}")

        if not purposes:
            if info.functions:
                func_names = [f.name for f in info.functions[:3]]
                purposes.append(f"Provides {', '.join(func_names)}")

        return '; '.join(purposes) if purposes else "General purpose code"

    def analyze_dependencies(self, file_path: str) -> Optional[DependencyInfo]:
        """
        Analyze file dependencies.

        Args:
            file_path: Path to file

        Returns:
            DependencyInfo with categorized dependencies
        """
        info = self.analyze_file(file_path)
        if not info:
            return None

        cache_key = info.path
        if cache_key in self._dependency_cache:
            return self._dependency_cache[cache_key]

        internal = []
        external = []
        stdlib = []
        missing = []

        for imp in info.imports:
            module = imp.module.split('.')[0]

            if module in self.stdlib_modules:
                stdlib.append(imp.module)
            elif imp.module.startswith('.'):
                internal.append(imp.module)
            elif self._is_internal_module(imp.module):
                internal.append(imp.module)
            else:
                external.append(imp.module)

        dep_info = DependencyInfo(
            internal_deps=list(set(internal)),
            external_deps=list(set(external)),
            standard_lib=list(set(stdlib)),
            missing_deps=missing
        )

        self._dependency_cache[cache_key] = dep_info
        return dep_info

    def _is_internal_module(self, module: str) -> bool:
        """Check if module is internal to the project"""
        # Check if it matches any file in repo
        module_path = module.replace('.', '/')
        potential_paths = [
            self.repo_path / f"{module_path}.py",
            self.repo_path / module_path / "__init__.py",
        ]
        return any(p.exists() for p in potential_paths)

    def analyze_directory(
        self,
        directory: str = '',
        extensions: Optional[List[str]] = None
    ) -> Dict[str, FileInfo]:
        """
        Analyze all files in a directory.

        Args:
            directory: Directory to analyze (relative to repo_path)
            extensions: File extensions to include (if None, analyzes all files)

        Returns:
            Dictionary mapping file paths to FileInfo
        """
        path = self.repo_path / directory if directory else self.repo_path

        results = {}
        pattern = f'*{extensions[0]}' if extensions else '*'

        for file_path in path.rglob(pattern):
            if file_path.is_file() and not any(part.startswith('.') for part in file_path.parts):
                info = self.analyze_file(str(file_path))
                if info:
                    results[info.path] = info

        return results
