"""
File Analyzer - File Analysis Utilities for Code Analysis

This module provides utilities for analyzing source code files:
- File content analysis with AST parsing
- Code structure extraction (functions, classes, imports)
- Language detection with multi-language support
- Complexity metrics (cyclomatic, cognitive)
- File relevance scoring for questions
- Dependency extraction and analysis
- Code pattern detection
- File categorization (config, test, model, etc.)

Used by agents to analyze and understand source code files.
"""

import ast
import re
import hashlib
import mimetypes
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Callable, Set
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
    constant_details: List['ConstantInfo'] = field(default_factory=list)  # Enhanced: includes values
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

    LANGUAGE_EXTENSIONS = {
        '.py': 'python',
        '.pyx': 'python',
        '.pyi': 'python',
        '.js': 'javascript',
        '.mjs': 'javascript',
        '.cjs': 'javascript',
        '.ts': 'typescript',
        '.tsx': 'typescript',
        '.jsx': 'javascript',
        '.java': 'java',
        '.go': 'go',
        '.rs': 'rust',
        '.cpp': 'cpp',
        '.cc': 'cpp',
        '.cxx': 'cpp',
        '.c': 'c',
        '.h': 'c',
        '.hpp': 'cpp',
        '.rb': 'ruby',
        '.php': 'php',
        '.swift': 'swift',
        '.kt': 'kotlin',
        '.kts': 'kotlin',
        '.scala': 'scala',
        '.cs': 'csharp',
        '.vue': 'vue',
        '.svelte': 'svelte',
    }

    # Patterns for file categorization
    CATEGORY_PATTERNS = {
        FileCategory.CONFIG: [
            r'config', r'settings', r'\.env', r'\.yaml$', r'\.yml$', r'\.json$',
            r'\.toml$', r'\.ini$', r'setup\.py$', r'pyproject\.toml$'
        ],
        FileCategory.TEST: [
            r'test_', r'_test\.py$', r'tests/', r'spec\.', r'\.spec\.',
            r'__tests__/', r'\.test\.'
        ],
        FileCategory.MODEL: [
            r'model', r'schema', r'entity', r'domain', r'dataclass'
        ],
        FileCategory.VIEW: [
            r'view', r'template', r'component', r'\.html$', r'\.vue$', r'\.svelte$'
        ],
        FileCategory.CONTROLLER: [
            r'controller', r'handler', r'route', r'endpoint', r'api/', r'views\.py$'
        ],
        FileCategory.UTIL: [
            r'util', r'helper', r'common', r'shared', r'tools'
        ],
        FileCategory.SERVICE: [
            r'service', r'manager', r'provider', r'client'
        ],
        FileCategory.API: [
            r'api', r'rest', r'graphql', r'grpc'
        ],
        FileCategory.MIGRATION: [
            r'migration', r'migrate', r'alembic', r'versions/'
        ],
        FileCategory.DOCUMENTATION: [
            r'\.md$', r'\.rst$', r'\.txt$', r'readme', r'changelog', r'docs/'
        ],
        FileCategory.SCRIPT: [
            r'script', r'bin/', r'__main__\.py$', r'cli'
        ],
    }

    # Standard library modules (common ones)
    STDLIB_MODULES = {
        'os', 'sys', 're', 'json', 'time', 'datetime', 'collections',
        'itertools', 'functools', 'pathlib', 'typing', 'dataclasses',
        'abc', 'enum', 'copy', 'math', 'random', 'hashlib', 'logging',
        'unittest', 'asyncio', 'threading', 'multiprocessing', 'subprocess',
        'io', 'pickle', 'csv', 'xml', 'html', 'http', 'urllib', 'socket',
        'email', 'argparse', 'configparser', 'contextlib', 'inspect',
        'traceback', 'warnings', 'types', 'operator', 'string', 'textwrap',
        'shutil', 'glob', 'tempfile', 'stat', 'filecmp', 'platform',
        'struct', 'codecs', 'base64', 'binascii', 'uuid', 'secrets',
    }

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

        # Language-specific analysis
        if language == 'python':
            self._analyze_python(content, info)
        elif language in ['javascript', 'typescript']:
            self._analyze_js_ts(content, info)
        elif language == 'java':
            self._analyze_java(content, info)
        elif language == 'go':
            self._analyze_go(content, info)
        else:
            self._analyze_generic(content, info)

        # Extract TODOs and FIXMEs
        info.todos = self._extract_todos(content)

        # Calculate complexity
        info.complexity = self._calculate_complexity(info)

        # Cache result
        self._cache[cache_key] = info

        return info

    def _detect_language(self, path: Path) -> str:
        """Detect language from file extension"""
        suffix = path.suffix.lower()
        if suffix in self.LANGUAGE_EXTENSIONS:
            return self.LANGUAGE_EXTENSIONS[suffix]

        # Try MIME type
        mime_type, _ = mimetypes.guess_type(str(path))
        if mime_type:
            if 'python' in mime_type:
                return 'python'
            if 'javascript' in mime_type:
                return 'javascript'
            if 'java' in mime_type:
                return 'java'

        return 'unknown'

    def _categorize_file(self, file_path: str, content: str) -> FileCategory:
        """Categorize file based on path and content"""
        file_lower = file_path.lower()

        for category, patterns in self.CATEGORY_PATTERNS.items():
            if any(re.search(p, file_lower) for p in patterns):
                return category

        # Content-based categorization
        if re.search(r'def test_|class Test|@pytest|unittest', content):
            return FileCategory.TEST
        if re.search(r'@dataclass|class.*Model|BaseModel', content):
            return FileCategory.MODEL
        if re.search(r'@app\.route|@router\.|def get_|def post_', content):
            return FileCategory.CONTROLLER

        return FileCategory.UNKNOWN

    def _analyze_python(self, content: str, info: FileInfo) -> None:
        """Analyze Python file using AST"""
        try:
            tree = ast.parse(content)
        except SyntaxError as e:
            info.errors.append(f"Syntax error: {e}")
            self._analyze_generic(content, info)
            return

        # Extract module-level docstring
        docstring = ast.get_docstring(tree)

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

        # Check decorator types
        is_property = 'property' in decorators
        is_static = 'staticmethod' in decorators
        is_class_method = 'classmethod' in decorators

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

        # Check class type
        is_dataclass = 'dataclass' in decorators
        is_abstract = 'ABC' in bases or 'ABCMeta' in bases or any(
            isinstance(d, ast.Call) and self._get_decorator_name(d) == 'abstractmethod'
            for d in node.decorator_list
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

    def _analyze_js_ts(self, content: str, info: FileInfo) -> None:
        """Analyze JavaScript/TypeScript file using patterns"""
        # Find functions
        func_patterns = [
            r'function\s+(\w+)\s*\(([^)]*)\)',
            r'const\s+(\w+)\s*=\s*(?:async\s+)?\(([^)]*)\)\s*=>',
            r'(\w+)\s*:\s*(?:async\s+)?function\s*\(([^)]*)\)',
            r'(\w+)\s*=\s*(?:async\s+)?\(([^)]*)\)\s*=>',
            r'(?:async\s+)?(\w+)\s*\(([^)]*)\)\s*\{',
        ]

        for pattern in func_patterns:
            matches = re.finditer(pattern, content)
            for match in matches:
                name = match.group(1)
                params_str = match.group(2) if len(match.groups()) > 1 else ""
                params = [p.strip() for p in params_str.split(',') if p.strip()]

                info.functions.append(FunctionInfo(
                    name=name,
                    start_line=content[:match.start()].count('\n') + 1,
                    end_line=0,
                    params=params,
                    is_async='async' in match.group(0),
                ))

        # Find classes
        class_pattern = r'class\s+(\w+)(?:\s+extends\s+(\w+))?'
        for match in re.finditer(class_pattern, content):
            bases = [match.group(2)] if match.group(2) else []
            info.classes.append(ClassInfo(
                name=match.group(1),
                start_line=content[:match.start()].count('\n') + 1,
                end_line=0,
                bases=bases,
            ))

        # Find imports
        import_patterns = [
            r'import\s+.*?\s+from\s+[\'"]([^\'"]+)[\'"]',
            r'require\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)',
            r'import\s+[\'"]([^\'"]+)[\'"]',
        ]
        for pattern in import_patterns:
            matches = re.findall(pattern, content)
            for module in matches:
                info.imports.append(ImportInfo(
                    module=module,
                    is_from_import=True
                ))

    def _analyze_java(self, content: str, info: FileInfo) -> None:
        """Analyze Java file using patterns"""
        # Find classes
        class_pattern = r'(?:public\s+|private\s+|protected\s+)?(?:abstract\s+)?class\s+(\w+)(?:\s+extends\s+(\w+))?(?:\s+implements\s+([\w,\s]+))?'
        for match in re.finditer(class_pattern, content):
            bases = []
            if match.group(2):
                bases.append(match.group(2))
            if match.group(3):
                bases.extend([b.strip() for b in match.group(3).split(',')])

            info.classes.append(ClassInfo(
                name=match.group(1),
                start_line=content[:match.start()].count('\n') + 1,
                end_line=0,
                bases=bases,
                is_abstract='abstract' in match.group(0)
            ))

        # Find methods
        method_pattern = r'(?:public|private|protected)\s+(?:static\s+)?(?:[\w<>,\s]+)\s+(\w+)\s*\(([^)]*)\)'
        for match in re.finditer(method_pattern, content):
            params = [p.strip().split()[-1] for p in match.group(2).split(',') if p.strip()]
            info.functions.append(FunctionInfo(
                name=match.group(1),
                start_line=content[:match.start()].count('\n') + 1,
                end_line=0,
                params=params,
                is_static='static' in match.group(0)
            ))

        # Find imports
        import_pattern = r'import\s+([\w.]+);'
        for match in re.finditer(import_pattern, content):
            info.imports.append(ImportInfo(
                module=match.group(1),
                line_number=content[:match.start()].count('\n') + 1
            ))

    def _analyze_go(self, content: str, info: FileInfo) -> None:
        """Analyze Go file using patterns"""
        # Find functions
        func_pattern = r'func\s+(?:\((\w+)\s+\*?(\w+)\)\s+)?(\w+)\s*\(([^)]*)\)'
        for match in re.finditer(func_pattern, content):
            name = match.group(3)
            params_str = match.group(4)
            params = [p.strip().split()[0] for p in params_str.split(',') if p.strip()]

            is_method = bool(match.group(1))
            info.functions.append(FunctionInfo(
                name=name,
                start_line=content[:match.start()].count('\n') + 1,
                end_line=0,
                params=params,
                is_method=is_method
            ))

        # Find structs (like classes)
        struct_pattern = r'type\s+(\w+)\s+struct\s*\{'
        for match in re.finditer(struct_pattern, content):
            info.classes.append(ClassInfo(
                name=match.group(1),
                start_line=content[:match.start()].count('\n') + 1,
                end_line=0,
                bases=[]
            ))

        # Find imports
        import_pattern = r'import\s+["\']([^"\']+)["\']'
        for match in re.finditer(import_pattern, content):
            info.imports.append(ImportInfo(module=match.group(1)))

        # Multi-import block
        multi_import = re.search(r'import\s*\(([\s\S]*?)\)', content)
        if multi_import:
            for module in re.findall(r'["\']([^"\']+)["\']', multi_import.group(1)):
                info.imports.append(ImportInfo(module=module))

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

            if module in self.STDLIB_MODULES:
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
            extensions: File extensions to include

        Returns:
            Dictionary mapping file paths to FileInfo
        """
        path = self.repo_path / directory if directory else self.repo_path
        extensions = extensions or list(self.LANGUAGE_EXTENSIONS.keys())

        results = {}
        for ext in extensions:
            for file_path in path.rglob(f'*{ext}'):
                # Skip common exclusions
                if any(part.startswith('.') or part in ['node_modules', '__pycache__', 'venv', '.git', 'dist', 'build']
                       for part in file_path.parts):
                    continue

                info = self.analyze_file(str(file_path))
                if info:
                    results[info.path] = info

        return results


class FileRelevanceScorer:
    """
    Scores files for relevance to a question.

    Uses multiple signals:
    - Keyword matching in file path and content
    - Function/class name matching
    - Import analysis
    - Semantic similarity (if LLM available)
    """

    def __init__(self, file_analyzer: FileAnalyzer, llm_callback: Optional[Callable] = None):
        """
        Initialize relevance scorer.

        Args:
            file_analyzer: FileAnalyzer instance
            llm_callback: Optional LLM for semantic scoring
        """
        self.analyzer = file_analyzer
        self.llm = llm_callback

    def score_file(
        self,
        file_path: str,
        question: str,
        keywords: Optional[List[str]] = None
    ) -> float:
        """
        Score a file's relevance to a question.

        Args:
            file_path: Path to file
            question: User question
            keywords: Additional keywords to match

        Returns:
            Relevance score (0.0 to 1.0)
        """
        info = self.analyzer.analyze_file(file_path)
        if not info:
            return 0.0

        # Extract keywords from question
        q_keywords = self._extract_keywords(question)
        if keywords:
            q_keywords.extend(keywords)

        score = 0.0

        # Score path matches (0.25 max)
        path_score = self._score_path_match(info.path, q_keywords)
        score += min(0.25, path_score)

        # Score function name matches (0.25 max)
        func_score = self._score_function_match(info.functions, q_keywords)
        score += min(0.25, func_score)

        # Score class name matches (0.2 max)
        class_score = self._score_class_match(info.classes, q_keywords)
        score += min(0.2, class_score)

        # Score import matches (0.15 max)
        import_score = self._score_import_match(info.imports, q_keywords)
        score += min(0.15, import_score)

        # Score category relevance (0.15 max)
        category_score = self._score_category_relevance(info.category, question)
        score += min(0.15, category_score)

        return min(1.0, score)

    def _score_path_match(self, path: str, keywords: List[str]) -> float:
        """Score based on file path matching"""
        path_lower = path.lower()
        matches = sum(1 for kw in keywords if kw in path_lower)
        return matches * 0.1

    def _score_function_match(self, functions: List[FunctionInfo], keywords: List[str]) -> float:
        """Score based on function name matching"""
        func_names = [f.name.lower() for f in functions]
        all_func_text = ' '.join(func_names)

        matches = sum(1 for kw in keywords if kw in all_func_text)
        return matches * 0.08

    def _score_class_match(self, classes: List[ClassInfo], keywords: List[str]) -> float:
        """Score based on class name matching"""
        class_names = [c.name.lower() for c in classes]
        all_class_text = ' '.join(class_names)

        matches = sum(1 for kw in keywords if kw in all_class_text)
        return matches * 0.1

    def _score_import_match(self, imports: List[ImportInfo], keywords: List[str]) -> float:
        """Score based on import matching"""
        import_modules = [i.module.lower() for i in imports]
        all_import_text = ' '.join(import_modules)

        matches = sum(1 for kw in keywords if kw in all_import_text)
        return matches * 0.05

    def _score_category_relevance(self, category: FileCategory, question: str) -> float:
        """Score based on category relevance to question"""
        q_lower = question.lower()

        category_keywords = {
            FileCategory.CONFIG: ['config', 'setting', 'environment', 'variable'],
            FileCategory.TEST: ['test', 'testing', 'spec', 'assert'],
            FileCategory.MODEL: ['model', 'schema', 'data', 'entity', 'class'],
            FileCategory.VIEW: ['view', 'template', 'ui', 'display', 'render'],
            FileCategory.CONTROLLER: ['route', 'endpoint', 'api', 'request', 'handler'],
            FileCategory.UTIL: ['util', 'helper', 'function', 'tool'],
            FileCategory.SERVICE: ['service', 'logic', 'business', 'process'],
            FileCategory.API: ['api', 'rest', 'endpoint', 'call'],
        }

        if category in category_keywords:
            matches = sum(1 for kw in category_keywords[category] if kw in q_lower)
            return matches * 0.05

        return 0.0

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from text"""
        stop_words = {
            'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
            'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
            'would', 'could', 'should', 'may', 'might', 'must', 'shall',
            'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by', 'from',
            'how', 'what', 'where', 'when', 'why', 'which', 'who', 'this',
            'that', 'these', 'those', 'and', 'or', 'but', 'not', 'it'
        }

        words = re.findall(r'\b\w+\b', text.lower())
        keywords = [w for w in words if len(w) > 2 and w not in stop_words]

        # Also extract CamelCase parts
        camel_parts = re.findall(r'[A-Z][a-z]+', text)
        keywords.extend([p.lower() for p in camel_parts])

        return list(set(keywords))

    def rank_files(
        self,
        files: List[str],
        question: str,
        top_k: int = 10
    ) -> List[Tuple[str, float]]:
        """
        Rank files by relevance to a question.

        Args:
            files: List of file paths
            question: User question
            top_k: Number of top files to return

        Returns:
            List of (file_path, score) tuples, sorted by score
        """
        scores = []
        for file_path in files:
            score = self.score_file(file_path, question)
            if score > 0:
                scores.append((file_path, score))

        # Sort by score descending
        scores.sort(key=lambda x: x[1], reverse=True)

        return scores[:top_k]

    def find_related_files(
        self,
        file_path: str,
        all_files: Optional[List[str]] = None
    ) -> List[Tuple[str, float]]:
        """
        Find files related to a given file.

        Args:
            file_path: Reference file
            all_files: Files to search (or use all in repo)

        Returns:
            List of (file_path, relatedness_score) tuples
        """
        info = self.analyzer.analyze_file(file_path)
        if not info:
            return []

        # Build relevance criteria from file
        criteria = []

        # Add import modules as criteria
        for imp in info.imports:
            if not imp.module.startswith('.'):
                criteria.append(imp.module.split('.')[0])

        # Add class names
        criteria.extend([c.name.lower() for c in info.classes])

        # Add key function names
        criteria.extend([f.name.lower() for f in info.functions[:5]])

        # Get all files if not provided
        if all_files is None:
            all_infos = self.analyzer.analyze_directory()
            all_files = list(all_infos.keys())

        # Score each file
        related = []
        for f in all_files:
            if f == file_path:
                continue

            other_info = self.analyzer.analyze_file(f)
            if not other_info:
                continue

            score = 0.0

            # Check import overlap
            other_imports = {i.module.split('.')[0] for i in other_info.imports}
            import_overlap = len(set(criteria) & other_imports)
            score += import_overlap * 0.1

            # Check class/function name overlap
            other_names = {c.name.lower() for c in other_info.classes}
            other_names.update(f.name.lower() for f in other_info.functions)
            name_overlap = len(set(criteria) & other_names)
            score += name_overlap * 0.15

            # Same category bonus
            if other_info.category == info.category and info.category != FileCategory.UNKNOWN:
                score += 0.1

            if score > 0.1:
                related.append((f, score))

        related.sort(key=lambda x: x[1], reverse=True)
        return related[:10]


# Factory functions

def create_file_analyzer(repo_path: str, llm_callback: Optional[Callable] = None) -> FileAnalyzer:
    """Factory function for file analyzer"""
    return FileAnalyzer(repo_path, llm_callback)


def create_relevance_scorer(
    file_analyzer: FileAnalyzer,
    llm_callback: Optional[Callable] = None
) -> FileRelevanceScorer:
    """Factory function for relevance scorer"""
    return FileRelevanceScorer(file_analyzer, llm_callback)
