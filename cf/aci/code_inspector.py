"""Code inspector for analyzing code structure and patterns."""

import ast
import re
from typing import Dict, List, Optional, Any, Set
from pathlib import Path

from ..types import LanguageType, EntityType
from ..exceptions import UnsupportedLanguageError


class CodeInspector:
    """Inspector for analyzing code structure and extracting information."""
    
    def __init__(self):
        self.supported_languages = {
            ".py": LanguageType.PYTHON,
            ".js": LanguageType.JAVASCRIPT,
            ".ts": LanguageType.TYPESCRIPT,
            ".jsx": LanguageType.JAVASCRIPT,
            ".tsx": LanguageType.TYPESCRIPT,
        }
    
    def inspect_file(self, file_path: str, content: str) -> Dict[str, Any]:
        """Inspect a file and extract structural information."""
        language = self._detect_language(file_path)
        
        inspection_result = {
            "file_path": file_path,
            "language": language,
            "size": len(content),
            "line_count": len(content.splitlines()),
            "entities": [],
            "imports": [],
            "dependencies": [],
            "complexity_metrics": {},
            "patterns": [],
            "issues": []
        }
        
        try:
            if language == LanguageType.PYTHON:
                inspection_result.update(self._inspect_python(content))
            elif language in [LanguageType.JAVASCRIPT, LanguageType.TYPESCRIPT]:
                inspection_result.update(self._inspect_javascript(content))
            else:
                inspection_result.update(self._inspect_generic(content))
        except Exception as e:
            inspection_result["issues"].append(f"Inspection failed: {str(e)}")
        
        return inspection_result
    
    def _detect_language(self, file_path: str) -> LanguageType:
        """Detect programming language from file extension."""
        suffix = Path(file_path).suffix.lower()
        return self.supported_languages.get(suffix, LanguageType.UNKNOWN)
    
    def _inspect_python(self, content: str) -> Dict[str, Any]:
        """Inspect Python code using AST parsing."""
        result = {
            "entities": [],
            "imports": [],
            "dependencies": [],
            "complexity_metrics": {},
            "patterns": []
        }
        
        try:
            tree = ast.parse(content)
            visitor = PythonInspector()
            visitor.visit(tree)
            
            result["entities"] = visitor.entities
            result["imports"] = visitor.imports
            result["dependencies"] = visitor.dependencies
            result["complexity_metrics"] = {
                "cyclomatic_complexity": visitor.complexity,
                "class_count": visitor.class_count,
                "function_count": visitor.function_count,
                "line_count": visitor.line_count
            }
            result["patterns"] = visitor.patterns
            
        except SyntaxError as e:
            result["issues"] = [f"Python syntax error: {str(e)}"]
        
        return result
    
    def _inspect_javascript(self, content: str) -> Dict[str, Any]:
        """Inspect JavaScript/TypeScript code using regex patterns."""
        result = {
            "entities": [],
            "imports": [],
            "dependencies": [],
            "complexity_metrics": {},
            "patterns": []
        }
        
        lines = content.splitlines()
        
        # Extract imports
        for line_no, line in enumerate(lines, 1):
            line = line.strip()
            
            # Import statements
            if line.startswith("import ") or "require(" in line:
                import_match = re.search(r'from\s+[\'"]([^\'"]+)[\'"]', line)
                if import_match:
                    result["imports"].append({
                        "module": import_match.group(1),
                        "line": line_no,
                        "type": "es6_import"
                    })
                
                require_match = re.search(r'require\([\'"]([^\'"]+)[\'"]\)', line)
                if require_match:
                    result["imports"].append({
                        "module": require_match.group(1),
                        "line": line_no,
                        "type": "commonjs_require"
                    })
            
            # Class definitions
            if line.startswith("class "):
                class_match = re.match(r'class\s+(\w+)', line)
                if class_match:
                    result["entities"].append({
                        "name": class_match.group(1),
                        "type": EntityType.CLASS,
                        "line": line_no
                    })
            
            # Function definitions
            if line.startswith("function ") or "=>" in line:
                func_match = re.search(r'(?:function\s+(\w+)|(?:const|let|var)\s+(\w+)\s*=)', line)
                if func_match:
                    func_name = func_match.group(1) or func_match.group(2)
                    if func_name:
                        result["entities"].append({
                            "name": func_name,
                            "type": EntityType.FUNCTION,
                            "line": line_no
                        })
        
        result["complexity_metrics"] = {
            "line_count": len(lines),
            "class_count": len([e for e in result["entities"] if e["type"] == EntityType.CLASS]),
            "function_count": len([e for e in result["entities"] if e["type"] == EntityType.FUNCTION])
        }
        
        return result
    
    def _inspect_generic(self, content: str) -> Dict[str, Any]:
        """Generic inspection for unsupported languages."""
        lines = content.splitlines()
        
        return {
            "entities": [],
            "imports": [],
            "dependencies": [],
            "complexity_metrics": {
                "line_count": len(lines),
                "char_count": len(content)
            },
            "patterns": []
        }


class PythonInspector(ast.NodeVisitor):
    """AST visitor for Python code inspection."""
    
    def __init__(self):
        self.entities = []
        self.imports = []
        self.dependencies = []
        self.patterns = []
        self.complexity = 0
        self.class_count = 0
        self.function_count = 0
        self.line_count = 0
    
    def visit_ClassDef(self, node):
        """Visit class definition."""
        self.class_count += 1
        self.entities.append({
            "name": node.name,
            "type": EntityType.CLASS,
            "line": node.lineno,
            "bases": [base.id if isinstance(base, ast.Name) else str(base) for base in node.bases],
            "decorators": [dec.id if isinstance(dec, ast.Name) else str(dec) for dec in node.decorator_list]
        })
        self.generic_visit(node)
    
    def visit_FunctionDef(self, node):
        """Visit function definition."""
        self.function_count += 1
        self.entities.append({
            "name": node.name,
            "type": EntityType.FUNCTION,
            "line": node.lineno,
            "args": [arg.arg for arg in node.args.args],
            "decorators": [dec.id if isinstance(dec, ast.Name) else str(dec) for dec in node.decorator_list]
        })
        
        # Count complexity (simplified)
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.While, ast.For, ast.Try, ast.With)):
                self.complexity += 1
        
        self.generic_visit(node)
    
    def visit_Import(self, node):
        """Visit import statement."""
        for alias in node.names:
            self.imports.append({
                "module": alias.name,
                "alias": alias.asname,
                "line": node.lineno,
                "type": "import"
            })
            self.dependencies.append(alias.name.split('.')[0])
    
    def visit_ImportFrom(self, node):
        """Visit from...import statement."""
        if node.module:
            for alias in node.names:
                self.imports.append({
                    "module": node.module,
                    "name": alias.name,
                    "alias": alias.asname,
                    "line": node.lineno,
                    "type": "from_import"
                })
            self.dependencies.append(node.module.split('.')[0])
    
    def visit_If(self, node):
        """Visit if statement."""
        self.complexity += 1
        self.generic_visit(node)
    
    def visit_While(self, node):
        """Visit while loop."""
        self.complexity += 1
        self.generic_visit(node)
    
    def visit_For(self, node):
        """Visit for loop."""
        self.complexity += 1
        self.generic_visit(node)
    
    def visit_Try(self, node):
        """Visit try block."""
        self.complexity += 1
        self.generic_visit(node)