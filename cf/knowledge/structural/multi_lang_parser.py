"""
Multi-Language Parser for Structural Analysis

Provides regex-based parsing for common programming languages beyond Python.
While not as accurate as AST parsing, this provides useful structural information
for JavaScript, TypeScript, Java, Go, Rust, C++, and C#.

Extracted information:
- Function/method definitions
- Class definitions
- Import/require statements
- Basic structure and organization
"""

import re
import os
import hashlib
from typing import List, Dict, Any, Optional, Set
from pathlib import Path

from cf.knowledge.structural.schema import (
    StructuralData, FileNode, FunctionNode, ClassNode, VariableNode, ModuleNode,
    Relationship, RelationType
)


class MultiLanguageParser:
    """
    Parse multiple programming languages using regex patterns.

    Supports: JavaScript, TypeScript, Java, Go, Rust, C++, C#
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

        # Language-specific patterns
        self.patterns = {
            'javascript': self._get_javascript_patterns(),
            'typescript': self._get_typescript_patterns(),
            'java': self._get_java_patterns(),
            'go': self._get_go_patterns(),
            'rust': self._get_rust_patterns(),
            'cpp': self._get_cpp_patterns(),
            'csharp': self._get_csharp_patterns()
        }

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

    def detect_language(self, file_path: str) -> Optional[str]:
        """
        Detect programming language from file extension.

        Returns:
            Language identifier or None if unsupported
        """
        ext = Path(file_path).suffix.lower()

        extension_map = {
            '.js': 'javascript',
            '.jsx': 'javascript',
            '.ts': 'typescript',
            '.tsx': 'typescript',
            '.java': 'java',
            '.go': 'go',
            '.rs': 'rust',
            '.cpp': 'cpp',
            '.cc': 'cpp',
            '.cxx': 'cpp',
            '.hpp': 'cpp',
            '.h': 'cpp',
            '.cs': 'csharp'
        }

        return extension_map.get(ext)

    def parse_file(self, file_path: str) -> Optional[StructuralData]:
        """
        Parse a source file and extract structural data.

        Args:
            file_path: Absolute path to source file

        Returns:
            StructuralData or None if parsing fails
        """
        # Detect language
        language = self.detect_language(file_path)
        if not language:
            return None

        # Read file content
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except Exception as e:
            print(f"Failed to read {file_path}: {e}")
            return None

        # Get patterns for this language
        patterns = self.patterns.get(language, {})

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
                        repo_id=self.repo_id,
                        parameters=[],  # Simplified - not parsing parameters
                        return_type='unknown',
                        docstring='',
                        decorators=[],
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
                        repo_id=self.repo_id,
                        parameters=[],
                        return_type='unknown',
                        docstring='',
                        decorators=[],
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
                        repo_id=self.repo_id,
                        base_classes=[base_class] if base_class else [],
                        methods=[],
                        docstring='',
                        decorators=[]
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
                        repo_id=self.repo_id,
                        base_classes=[],
                        methods=[],
                        docstring='',
                        decorators=[]
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

        # Create file node
        file_node = FileNode(
            path=rel_path,
            repo_id=self.repo_id,
            file_hash=file_hash,
            language=language,
            lines_of_code=len(content.splitlines())
        )

        # Create structural data
        return StructuralData(
            file=file_node,
            functions=functions,
            classes=classes,
            variables=[],  # Simplified - not extracting variables
            modules=[],
            relationships=[],
            imports=imports
        )
