"""
Repository Tools for CodeFusion

Clean, efficient file operations with grep-based searching and comprehensive metrics tracking.
"""

import ast
import os
import re
import time
import shlex
import subprocess
import mimetypes
from pathlib import Path
from typing import Dict, List, Any, Optional
from cf.utils.logger import get_logger

logger = get_logger(__name__)


class RepoTools:
    """Repository file operations and analysis tools"""

    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path).resolve()
        self.max_file_size = 1024 * 1024  # 1MB
        self._source_extensions_cache = None

    def _get_source_extensions(self) -> List[str]:
        """
        Dynamically discover source file extensions from the repository.

        Scans the repo to find what extensions are actually used,
        rather than hardcoding a language-specific list.
        """
        if self._source_extensions_cache is not None:
            return self._source_extensions_cache

        extensions = set()
        try:
            # Sample files from repo to discover extensions
            for path in self.repo_path.rglob('*'):
                if path.is_file():
                    ext = path.suffix.lower()
                    if ext and len(ext) <= 5:
                        extensions.add(ext)
                if len(extensions) >= 50:
                    break
        except Exception:
            pass

        self._source_extensions_cache = list(extensions)
        return self._source_extensions_cache
    
    def scan_directory(self, directory: str = "", max_depth: int = 3, exclude_dirs: Optional[List[str]] = None) -> Dict[str, Any]:
        """Recursively scan directory to discover files and structure"""
        scan_path = self.repo_path / directory if directory else self.repo_path

        logger.debug(f"Starting scan of: {scan_path}")

        if not scan_path.exists():
            logger.error(f"Directory not found: {scan_path}")
            return {'error': f'Directory not found: {scan_path}'}

        excludes = set(exclude_dirs) if exclude_dirs else set()

        result = {
            'directory': str(scan_path),
            'files': [],
            'subdirectories': [],
            'total_files': 0,
            'total_size': 0
        }
        
        def _scan_recursive(path: Path, current_depth: int):
            if current_depth > max_depth:
                return

            try:
                items = list(path.iterdir())

                for item in items:
                    if item.name.startswith('.') and item.name not in {'.gitignore', '.env'}:
                        continue

                    if item.is_dir():
                        if item.name in excludes:
                            continue
                        result['subdirectories'].append(str(item.relative_to(self.repo_path)))
                        _scan_recursive(item, current_depth + 1)
                    elif item.is_file():
                        if item.stat().st_size > self.max_file_size:
                            continue

                        is_text = self._is_text_file(item)
                        relative_path = str(item.relative_to(self.repo_path))
                        file_size = item.stat().st_size

                        file_info = {
                            'path': relative_path,
                            'size': file_size,
                            'extension': item.suffix,
                            'is_text': is_text
                        }
                        result['files'].append(file_info)
                        result['total_files'] += 1
                        result['total_size'] += file_size
            except PermissionError as e:
                logger.error(f"Permission denied: {path} - {e}")
            except Exception as e:
                logger.error(f"Error scanning {path}: {e}")
        
        _scan_recursive(scan_path, 0)

        logger.debug(f"Scan complete: {result['total_files']} files, {len(result['subdirectories'])} directories")

        return result
    
    def list_files(self, pattern: str = "*", directory: str = "", recursive: bool = True) -> Dict[str, Any]:
        """List files matching pattern in directory"""
        search_path = self.repo_path / directory if directory else self.repo_path
        
        if not search_path.exists():
            return {'error': f'Directory not found: {search_path}'}
        
        try:
            if recursive:
                matches = list(search_path.rglob(pattern))
            else:
                matches = list(search_path.glob(pattern))
            
            files = []
            for match in matches:
                if match.is_file() and not self._should_exclude_file(match):
                    files.append({
                        'path': str(match.relative_to(self.repo_path)),
                        'size': match.stat().st_size,
                        'modified': match.stat().st_mtime
                    })
            
            return {
                'pattern': pattern,
                'directory': str(search_path),
                'files': sorted(files, key=lambda x: x['modified'], reverse=True),
                'total': len(files)
            }
        except Exception as e:
            return {'error': f'Failed to list files: {str(e)}'}
    
    def read_file(self, file_path: str, max_lines: Optional[int] = None, offset: int = 0,
                  include_structure: bool = False, extract_imports: bool = False) -> Dict[str, Any]:
        """
        Read contents of a specific file.

        Args:
            file_path: Path to file relative to repo root
            max_lines: Optional limit on number of lines to read
            offset: Line number to start reading from (0-indexed, default 0)
            include_structure: Include AST structure analysis
            extract_imports: Extract and resolve import statements to file paths

        Returns:
            Dict with file content and optional imports/structure
        """
        full_path = self.repo_path / file_path

        if not full_path.exists():
            return {'error': f'File not found: {file_path}'}

        if full_path.stat().st_size > self.max_file_size:
            return {'error': f'File too large: {file_path}'}

        try:
            if not self._is_text_file(full_path):
                return {'error': f'File is not text readable: {file_path}'}

            # Always read full file first to get total line count
            with open(full_path, 'r', encoding='utf-8') as f:
                full_content = f.read()

            all_lines = full_content.splitlines(keepends=True)
            total_lines = len(all_lines)

            # Apply offset and max_lines
            start_line = min(offset, total_lines)
            if max_lines:
                end_line = min(start_line + max_lines, total_lines)
            else:
                end_line = total_lines

            content = ''.join(all_lines[start_line:end_line])
            lines_read = end_line - start_line
            truncated = end_line < total_lines

            result = {
                'file_path': file_path,
                'content': content,
                'size': full_path.stat().st_size,
                'lines': lines_read,
                'total_lines': total_lines,
                'offset': start_line,
                'truncated': truncated,
                'encoding': 'utf-8'
            }

            # Add truncation warning so LLM knows there's more content
            if truncated:
                remaining = total_lines - end_line
                result['truncation_warning'] = f"⚠️ FILE TRUNCATED: Showing lines {start_line+1}-{end_line}/{total_lines}. {remaining} more lines available. Use offset={end_line} to continue reading."

            # Add structural analysis if requested
            if include_structure:
                structure = self.analyze_file_structure(file_path)
                if 'error' not in structure:
                    result['structure_analysis'] = structure

            # Extract imports from FULL file (not truncated) to discover all dependencies
            if extract_imports:
                imports = self._extract_imports(full_path, full_content)
                if imports:
                    result['imports'] = imports

            return result
        except Exception as e:
            return {'error': f'Failed to read file: {str(e)}'}

    def _extract_imports(self, file_path: Path, content: str) -> List[Dict[str, Any]]:
        """
        Extract imports from a source file and resolve to file paths.

        Content-driven: tries extraction methods and uses whichever finds imports.
        """
        # Content-driven: try all extraction methods and combine results
        all_imports = []
        all_imports.extend(self._extract_python_imports(content))
        all_imports.extend(self._extract_js_imports(content))
        imports = all_imports

        # Resolve imports to actual file paths
        resolved = []
        for imp in imports:
            resolved_path = self._resolve_import_path(imp, file_path)
            resolved.append({
                'module': imp.get('module', ''),
                'names': imp.get('names', []),
                'resolved_path': resolved_path,
                'exists': resolved_path is not None and (self.repo_path / resolved_path).exists() if resolved_path else False
            })

        return resolved

    def _extract_python_imports(self, content: str) -> List[Dict[str, Any]]:
        """Extract imports from Python source code using AST."""
        imports = []

        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append({
                            'type': 'import',
                            'module': alias.name,
                            'names': [alias.asname or alias.name],
                            'line': node.lineno
                        })
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ''
                    names = [alias.name for alias in node.names]
                    imports.append({
                        'type': 'from',
                        'module': module,
                        'names': names,
                        'level': node.level,  # Relative import level
                        'line': node.lineno
                    })
        except SyntaxError:
            # Fall back to regex if AST parsing fails
            # Handle single-line imports
            simple_import = re.compile(r'^import\s+([\w.]+)', re.MULTILINE)
            for match in simple_import.finditer(content):
                imports.append({
                    'type': 'import',
                    'module': match.group(1),
                    'names': []
                })

            # Handle from X import Y (single line)
            from_import = re.compile(r'^from\s+([\w.]+)\s+import\s+([^\n(]+)$', re.MULTILINE)
            for match in from_import.finditer(content):
                imports.append({
                    'type': 'from',
                    'module': match.group(1),
                    'names': [n.strip() for n in match.group(2).split(',')]
                })

            # Handle multiline imports: from X import (\n    a,\n    b\n)
            multiline_import = re.compile(
                r'^from\s+([\w.]+)\s+import\s+\(\s*([^)]+)\)',
                re.MULTILINE | re.DOTALL
            )
            for match in multiline_import.finditer(content):
                names = [n.strip() for n in match.group(2).replace('\n', ',').split(',') if n.strip()]
                imports.append({
                    'type': 'from',
                    'module': match.group(1),
                    'names': names
                })

        return imports

    def _extract_js_imports(self, content: str) -> List[Dict[str, Any]]:
        """Extract imports from JavaScript/TypeScript source code."""
        imports = []

        # Match: import X from 'path' or import { X } from 'path'
        import_pattern = re.compile(
            r'''import\s+(?:(?:\{[^}]+\}|[\w*]+(?:\s*,\s*\{[^}]+\})?)\s+from\s+)?['"]([^'"]+)['"]''',
            re.MULTILINE
        )

        for match in import_pattern.finditer(content):
            imports.append({
                'type': 'import',
                'module': match.group(1),
                'names': []
            })

        # Match: require('path')
        require_pattern = re.compile(r'''require\s*\(\s*['"]([^'"]+)['"]\s*\)''')
        for match in require_pattern.finditer(content):
            imports.append({
                'type': 'require',
                'module': match.group(1),
                'names': []
            })

        return imports

    def _resolve_import_path(self, imp: Dict[str, Any], source_file: Path) -> Optional[str]:
        """
        Try to resolve an import to a file path in the repository.

        Uses file system discovery - no hardcoded extensions.
        Returns relative path from repo root if found, None otherwise.
        """
        module = imp.get('module', '')
        if not module:
            return None

        # Determine base path based on import type
        level = imp.get('level', 0)
        if level > 0:
            # Relative import - go up 'level' directories
            base_dir = source_file.parent
            for _ in range(level - 1):
                base_dir = base_dir.parent
        elif module.startswith('.') or module.startswith('/'):
            # JS-style relative import
            base_dir = source_file.parent
            module = module.lstrip('./')
        else:
            # Absolute import - from repo root
            base_dir = self.repo_path

        # Convert module to path (handle both . and / separators)
        module_as_path = module.replace('.', '/').replace('//', '/')
        target_path = base_dir / module_as_path

        # Check if it's a directory - look for any index/init file
        if target_path.is_dir():
            # Find any file that could be an entry point (first file found)
            for f in target_path.iterdir():
                if f.is_file():
                    try:
                        return str(f.relative_to(self.repo_path))
                    except ValueError:
                        pass
            return str(target_path.relative_to(self.repo_path))

        # Check if exact file exists
        if target_path.exists() and target_path.is_file():
            try:
                return str(target_path.relative_to(self.repo_path))
            except ValueError:
                return None

        # Use glob to find matching files with any extension
        parent = target_path.parent
        name = target_path.name
        if parent.exists():
            matches = list(parent.glob(f"{name}.*"))
            if matches:
                try:
                    return str(matches[0].relative_to(self.repo_path))
                except ValueError:
                    pass

        return None
    
    def search_files(self, pattern: str, file_types: Optional[List[str]] = None, max_results: int = 50) -> Dict[str, Any]:
        """Search for pattern across files using grep for better performance"""
        try:
            # Build grep command
            cmd = ['grep', '-rn', pattern]
            
            # Add file type filters
            if file_types:
                for ext in file_types:
                    if not ext.startswith('.'):
                        ext = f'.{ext}'
                    cmd.extend(['--include', f'*{ext}'])
            else:
                # Dynamically discover source extensions from repo
                for ext in self._get_source_extensions():
                    cmd.extend(['--include', f'*{ext}'])

            cmd.append(str(self.repo_path))
            
            # Execute grep
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            matches = []
            if result.stdout:
                lines = result.stdout.strip().split('\n')[:max_results]
                
                for line in lines:
                    # Parse grep output: file:line_number:content
                    parts = line.split(':', 2)
                    if len(parts) >= 3:
                        file_path = parts[0]
                        line_number = parts[1]
                        content = parts[2]
                        
                        # Make path relative to repo_path
                        try:
                            rel_path = str(Path(file_path).relative_to(self.repo_path))
                        except ValueError:
                            rel_path = file_path
                        
                        matches.append({
                            'file': rel_path,
                            'line': int(line_number) if line_number.isdigit() else 0,
                            'content': content.strip(),
                            'match': pattern
                        })
            
            return {
                'pattern': pattern,
                'matches': matches,
                'total': len(matches),
                'truncated': len(matches) == max_results
            }
            
        except subprocess.TimeoutExpired:
            return {'error': 'Search timed out'}
        except FileNotFoundError:
            # Fallback to Python-based search if grep not available
            return self._python_search_fallback(pattern, file_types, max_results)
        except Exception as e:
            return {'error': f'Search failed: {str(e)}'}
    
    def _python_search_fallback(self, pattern: str, file_types: Optional[List[str]], max_results: int) -> Dict[str, Any]:
        """Fallback Python-based search when grep is not available"""
        matches = []
        pattern_re = re.compile(pattern, re.IGNORECASE)
        
        # Determine file extensions to search
        extensions = set()
        if file_types:
            extensions = {f'.{ext}' if not ext.startswith('.') else ext for ext in file_types}
        else:
            # Dynamically discover extensions from repo
            extensions = set(self._get_source_extensions())
        
        def _search_directory(directory: Path):
            if len(matches) >= max_results:
                return
                
            try:
                for item in directory.iterdir():
                    if len(matches) >= max_results:
                        break
                        
                    if item.is_dir():
                        _search_directory(item)
                    elif item.is_file() and item.suffix in extensions:
                        if self._should_exclude_file(item):
                            continue
                            
                        try:
                            with open(item, 'r', encoding='utf-8') as f:
                                for line_num, line in enumerate(f, 1):
                                    if pattern_re.search(line):
                                        matches.append({
                                            'file': str(item.relative_to(self.repo_path)),
                                            'line': line_num,
                                            'content': line.strip(),
                                            'match': pattern
                                        })
                                        if len(matches) >= max_results:
                                            break
                        except (UnicodeDecodeError, PermissionError):
                            continue
            except PermissionError:
                # Skip directories without read permission
                pass
        
        _search_directory(self.repo_path)
        
        return {
            'pattern': pattern,
            'matches': matches,
            'total': len(matches),
            'truncated': len(matches) == max_results,
            'fallback': True
        }
    
    def get_file_info(self, file_path: str, include_metrics: bool = False) -> Dict[str, Any]:
        """Get metadata about a file, optionally including code metrics"""
        full_path = self.repo_path / file_path

        if not full_path.exists():
            logger.error(f"File not found: {file_path}")
            return {'error': f'File not found: {file_path}'}

        try:
            stat = full_path.stat()
            is_text = self._is_text_file(full_path)
            mime_type = mimetypes.guess_type(full_path)[0] or 'unknown'

            info = {
                'file_path': file_path,
                'size': stat.st_size,
                'modified': stat.st_mtime,
                'created': stat.st_ctime,
                'extension': full_path.suffix,
                'is_text': is_text,
                'mime_type': mime_type
            }

            # Add code metrics if requested and file is text
            if include_metrics and info['is_text']:
                metrics = self.calculate_file_metrics(file_path)
                if 'error' not in metrics:
                    info['code_metrics'] = metrics

            return info
        except Exception as e:
            logger.error(f"Failed to get file info: {str(e)}")
            return {'error': f'Failed to get file info: {str(e)}'}
    
    def _is_text_file(self, file_path: Path) -> bool:
        """Check if file is likely a text file"""
        # Use dynamically discovered extensions from repo
        if file_path.suffix in set(self._get_source_extensions()):
            return True

        mime_type = mimetypes.guess_type(file_path)[0]
        if mime_type and mime_type.startswith('text/'):
            return True
            
        # Try reading first few bytes to detect binary
        try:
            with open(file_path, 'rb') as f:
                chunk = f.read(512)
                if b'\x00' in chunk:
                    return False
                return True
        except Exception:
            return False
    
    def calculate_file_metrics(self, file_path: str) -> Dict[str, Any]:
        """Calculate code metrics for a file by reading it first"""
        # Use read_file to get content
        file_data = self.read_file(file_path)
        if 'error' in file_data:
            return file_data

        content = file_data['content']
        lines = content.splitlines()
        extension = Path(file_path).suffix.lower()
        language = self._detect_language(extension)

        non_empty_lines = [line for line in lines if line.strip()]

        metrics = {
            'total_lines': len(lines),
            'non_empty_lines': len(non_empty_lines),
            'language': language
        }

        # Generic complexity analysis - let LLM interpret language-specific patterns
        metrics['complexity_indicators'] = self._analyze_generic_complexity(content)

        return metrics
    
    def analyze_file_structure(self, file_path: str) -> Dict[str, Any]:
        """Analyze file structure by reading it first"""
        # Use read_file to get content
        file_data = self.read_file(file_path)
        if 'error' in file_data:
            return file_data
        
        content = file_data['content']
        lines = content.splitlines()
        extension = Path(file_path).suffix.lower()

        structure = {
            'extension': extension,
            'components': [],
            'imports': []
        }

        # Content-driven parsing - try all parsers and use best result
        parsers = [
            lambda: self.parse_python_structure(content, lines),
            lambda: self.parse_js_structure(content, lines),
            lambda: self.parse_markdown_structure(lines),
        ]

        best_result = {'components': [], 'imports': []}
        best_score = 0

        for parser in parsers:
            try:
                result = parser()
                score = len(result.get('components', [])) + len(result.get('imports', []))
                if score > best_score:
                    best_score = score
                    best_result = result
            except Exception:
                continue

        structure.update(best_result)
        return structure
    
    def parse_python_structure(self, content: str, lines: List[str]) -> Dict[str, Any]:
        """Parse Python file structure from content"""
        components = []
        imports = []
        
        for i, line in enumerate(lines):
            # Find imports
            if re.match(r'^\s*(?:from\s+.+\s+)?import\s+', line):
                imports.append(line.strip())
            
            # Find classes
            class_match = re.match(r'^\s*class\s+(\w+)', line)
            if class_match:
                components.append({
                    'type': 'class',
                    'name': class_match.group(1),
                    'line': i + 1
                })
            
            # Find functions
            func_match = re.match(r'^\s*def\s+(\w+)', line)
            if func_match:
                components.append({
                    'type': 'function',
                    'name': func_match.group(1),
                    'line': i + 1
                })
        
        return {
            'components': components[:10],  # Limit to first 10
            'imports': imports[:5]  # Limit to first 5
        }
    
    def parse_js_structure(self, content: str, lines: List[str]) -> Dict[str, Any]:
        """Parse JavaScript/TypeScript file structure from content"""
        components = []
        imports = []
        
        for i, line in enumerate(lines):
            # Find imports/exports
            if re.match(r'^\s*(?:import|export)', line):
                imports.append(line.strip())
            
            # Find functions
            if re.search(r'function\s+(\w+)', line):
                match = re.search(r'function\s+(\w+)', line)
                components.append({
                    'type': 'function',
                    'name': match.group(1),
                    'line': i + 1
                })
            
            # Find classes
            if re.search(r'class\s+(\w+)', line):
                match = re.search(r'class\s+(\w+)', line)
                components.append({
                    'type': 'class',
                    'name': match.group(1),
                    'line': i + 1
                })
        
        return {
            'components': components[:10],
            'imports': imports[:5]
        }
    
    def parse_markdown_structure(self, lines: List[str]) -> Dict[str, Any]:
        """Parse Markdown file structure from lines"""
        components = []
        
        for i, line in enumerate(lines):
            if line.startswith('#'):
                level = len(line) - len(line.lstrip('#'))
                header_text = line.lstrip('#').strip()
                components.append({
                    'type': f'header_h{level}',
                    'name': header_text,
                    'line': i + 1
                })
        
        return {
            'components': components[:10],
            'imports': []
        }
    
    def _detect_language(self, extension: str) -> str:
        """Return extension as language identifier - let LLM interpret context."""
        if not extension:
            return 'unknown'
        # Return extension without dot, capitalized (e.g., '.py' -> 'py')
        return extension.lstrip('.').lower() or 'unknown'
    
    def _analyze_generic_complexity(self, content: str) -> Dict[str, Any]:
        """Analyze code complexity using generic patterns - works across languages."""
        # Count common structural patterns that appear in most languages
        lines = content.splitlines()

        # Count indentation levels as proxy for nesting complexity
        indent_levels = [len(line) - len(line.lstrip()) for line in lines if line.strip()]
        max_indent = max(indent_levels) if indent_levels else 0
        avg_indent = sum(indent_levels) / len(indent_levels) if indent_levels else 0

        # Count code blocks (lines with certain endings)
        block_starters = len([l for l in lines if l.rstrip().endswith(('{', ':', 'do', 'then'))])

        # Estimate complexity from structure
        total = len(lines)
        complexity = 'low' if total < 100 else 'medium' if total < 500 else 'high'

        return {
            'total_lines': total,
            'max_nesting': max_indent // 4,  # Approximate nesting level
            'block_count': block_starters,
            'estimated_complexity': complexity
        }

    def _should_exclude_file(self, file_path: Path) -> bool:
        """Check if file should be excluded from processing"""
        if file_path.stat().st_size > self.max_file_size:
            return True
        return False

    # ===== ENHANCED FILE TOOLS =====

    def tail_file(self, file_path: str, lines: int = 10) -> Dict[str, Any]:
        """
        Read last N lines of a file (tail equivalent)

        Args:
            file_path: Path to file (relative to repo root)
            lines: Number of lines to read from end (default: 10)

        Returns:
            Dictionary with tail content and metadata
        """
        full_path = self.repo_path / file_path

        if not full_path.exists():
            return {'error': f'File not found: {file_path}'}

        if not full_path.is_file():
            return {'error': f'Not a file: {file_path}'}

        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                all_lines = f.readlines()

            tail_lines = all_lines[-lines:] if len(all_lines) >= lines else all_lines
            content = ''.join(tail_lines)

            return {
                'file_path': file_path,
                'content': content,
                'lines_requested': lines,
                'lines_returned': len(tail_lines),
                'total_lines': len(all_lines)
            }

        except UnicodeDecodeError:
            return {'error': f'File is not text readable: {file_path}'}
        except Exception as e:
            return {'error': f'Failed to read file tail: {str(e)}'}

    def head_file(self, file_path: str, lines: int = 10) -> Dict[str, Any]:
        """
        Read first N lines of a file (head equivalent)

        Args:
            file_path: Path to file (relative to repo root)
            lines: Number of lines to read from start (default: 10)

        Returns:
            Dictionary with head content and metadata
        """
        full_path = self.repo_path / file_path

        if not full_path.exists():
            return {'error': f'File not found: {file_path}'}

        if not full_path.is_file():
            return {'error': f'Not a file: {file_path}'}

        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                all_lines = f.readlines()

            head_lines = all_lines[:lines] if len(all_lines) >= lines else all_lines
            content = ''.join(head_lines)

            return {
                'file_path': file_path,
                'content': content,
                'lines_requested': lines,
                'lines_returned': len(head_lines),
                'total_lines': len(all_lines)
            }

        except UnicodeDecodeError:
            return {'error': f'File is not text readable: {file_path}'}
        except Exception as e:
            return {'error': f'Failed to read file head: {str(e)}'}

    def cat_file(self, file_path: str) -> Dict[str, Any]:
        """
        Read entire file contents (cat equivalent)

        Args:
            file_path: Path to file (relative to repo root)

        Returns:
            Dictionary with full file content and metadata
        """
        full_path = self.repo_path / file_path

        if not full_path.exists():
            return {'error': f'File not found: {file_path}'}

        if not full_path.is_file():
            return {'error': f'Not a file: {file_path}'}

        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()

            lines = content.splitlines()

            return {
                'file_path': file_path,
                'content': content,
                'total_lines': len(lines),
                'size_bytes': full_path.stat().st_size
            }

        except UnicodeDecodeError:
            return {'error': f'File is not text readable: {file_path}'}
        except Exception as e:
            return {'error': f'Failed to read file: {str(e)}'}

    def word_count(self, file_path: str) -> Dict[str, Any]:
        """
        Count lines, words, and characters in a file (wc equivalent)

        Args:
            file_path: Path to file (relative to repo root)

        Returns:
            Dictionary with line/word/character counts
        """
        full_path = self.repo_path / file_path

        if not full_path.exists():
            return {'error': f'File not found: {file_path}'}

        if not full_path.is_file():
            return {'error': f'Not a file: {file_path}'}

        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()

            lines = content.splitlines()
            words = content.split()
            chars = len(content)
            chars_no_spaces = len(content.replace(' ', '').replace('\n', '').replace('\t', ''))

            return {
                'file_path': file_path,
                'lines': len(lines),
                'words': len(words),
                'characters': chars,
                'characters_no_whitespace': chars_no_spaces,
                'bytes': full_path.stat().st_size
            }

        except UnicodeDecodeError:
            # For binary files, just return byte count
            return {
                'file_path': file_path,
                'lines': 0,
                'words': 0,
                'characters': 0,
                'bytes': full_path.stat().st_size,
                'is_binary': True
            }
        except Exception as e:
            return {'error': f'Failed to count: {str(e)}'}

    def regex_replace(self, file_path: str, pattern: str, replacement: str,
                      flags: str = "", preview_only: bool = True) -> Dict[str, Any]:
        """
        Preview or apply regex substitution on file content (sed equivalent)
        Default is preview-only for safety.

        Args:
            file_path: Path to file (relative to repo root)
            pattern: Regex pattern to match
            replacement: Replacement string (supports \\1, \\2 backreferences)
            flags: Regex flags ('i' for ignore case, 'm' for multiline, 'g' implied)
            preview_only: If True, only show preview without modifying file

        Returns:
            Dictionary with original/modified content preview and match count
        """
        full_path = self.repo_path / file_path

        if not full_path.exists():
            return {'error': f'File not found: {file_path}'}

        if not full_path.is_file():
            return {'error': f'Not a file: {file_path}'}

        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Build regex flags
            re_flags = 0
            if 'i' in flags:
                re_flags |= re.IGNORECASE
            if 'm' in flags:
                re_flags |= re.MULTILINE

            # Count matches first
            matches = re.findall(pattern, content, re_flags)
            match_count = len(matches)

            if match_count == 0:
                return {
                    'file_path': file_path,
                    'pattern': pattern,
                    'replacement': replacement,
                    'matches': 0,
                    'message': 'No matches found'
                }

            # Perform substitution
            modified_content = re.sub(pattern, replacement, content, flags=re_flags)

            result = {
                'file_path': file_path,
                'pattern': pattern,
                'replacement': replacement,
                'matches': match_count,
                'preview_only': preview_only,
                'original_lines': len(content.splitlines()),
                'modified_lines': len(modified_content.splitlines())
            }

            # Show diff preview (first few changes)
            original_lines = content.splitlines()
            modified_lines = modified_content.splitlines()
            diff_preview = []
            for i, (orig, mod) in enumerate(zip(original_lines, modified_lines)):
                if orig != mod:
                    diff_preview.append({
                        'line': i + 1,
                        'original': orig[:200],
                        'modified': mod[:200]
                    })
                    if len(diff_preview) >= 5:  # Limit preview to 5 changes
                        break

            result['diff_preview'] = diff_preview

            if not preview_only:
                with open(full_path, 'w', encoding='utf-8') as f:
                    f.write(modified_content)
                result['applied'] = True
                result['message'] = f'Applied {match_count} replacements'
            else:
                result['message'] = f'Preview: {match_count} matches would be replaced'

            return result

        except re.error as e:
            return {'error': f'Invalid regex pattern: {str(e)}'}
        except UnicodeDecodeError:
            return {'error': f'File is not text readable: {file_path}'}
        except Exception as e:
            return {'error': f'Regex replace failed: {str(e)}'}

    def get_file_stat(self, file_path: str) -> Dict[str, Any]:
        """
        Get comprehensive file statistics (stat equivalent)
        More detailed than get_file_info

        Args:
            file_path: Path to file (relative to repo root)

        Returns:
            Dictionary with comprehensive file metadata
        """
        full_path = self.repo_path / file_path

        if not full_path.exists():
            return {'error': f'Path not found: {file_path}'}

        try:
            stat_info = full_path.stat()

            # Determine file type
            if full_path.is_file():
                file_type = 'regular file'
            elif full_path.is_dir():
                file_type = 'directory'
            elif full_path.is_symlink():
                file_type = 'symbolic link'
            else:
                file_type = 'other'

            # Format permissions in octal
            mode = stat_info.st_mode
            perms_octal = oct(mode)[-3:]

            # Human-readable permissions
            perms_str = ''
            for i, (r, w, x) in enumerate([(0o400, 0o200, 0o100),
                                            (0o040, 0o020, 0o010),
                                            (0o004, 0o002, 0o001)]):
                perms_str += 'r' if mode & r else '-'
                perms_str += 'w' if mode & w else '-'
                perms_str += 'x' if mode & x else '-'

            return {
                'file_path': file_path,
                'type': file_type,
                'size_bytes': stat_info.st_size,
                'size_human': self._human_readable_size(stat_info.st_size),
                'permissions_octal': perms_octal,
                'permissions_str': perms_str,
                'mode': oct(mode),
                'uid': stat_info.st_uid,
                'gid': stat_info.st_gid,
                'inode': stat_info.st_ino,
                'device': stat_info.st_dev,
                'hard_links': stat_info.st_nlink,
                'access_time': stat_info.st_atime,
                'modify_time': stat_info.st_mtime,
                'change_time': stat_info.st_ctime,
                'is_symlink': full_path.is_symlink()
            }

        except Exception as e:
            return {'error': f'stat failed: {str(e)}'}

    def _human_readable_size(self, size: int) -> str:
        """Convert bytes to human-readable format"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024:
                return f"{size:.1f}{unit}"
            size /= 1024
        return f"{size:.1f}PB"

    # ===== BASH EXECUTION TOOL =====

    def bash_exec(self, command: str, timeout_seconds: int = 30) -> Dict[str, Any]:
        """
        Execute a shell command within the repository directory.

        LLM-driven: The LLM decides what commands to run.
        Protection: Timeout and working directory restriction only.

        Args:
            command: Shell command to execute
            timeout_seconds: Max execution time (default 30s, max 60s)

        Returns:
            Dict with stdout, stderr, return_code, and execution metadata
        """
        # Cap timeout for runaway processes
        timeout_seconds = min(timeout_seconds, 60)

        try:
            # Execute with timeout and working directory restriction
            result = subprocess.run(
                command,
                shell=True,
                cwd=str(self.repo_path),
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'}
            )

            # Truncate output if too long
            max_output_chars = 10000
            stdout = result.stdout[:max_output_chars]
            stderr = result.stderr[:max_output_chars]

            stdout_truncated = len(result.stdout) > max_output_chars
            stderr_truncated = len(result.stderr) > max_output_chars

            return {
                'command': command,
                'return_code': result.returncode,
                'stdout': stdout,
                'stderr': stderr,
                'stdout_truncated': stdout_truncated,
                'stderr_truncated': stderr_truncated,
                'success': result.returncode == 0,
                'working_directory': str(self.repo_path),
                'timeout_seconds': timeout_seconds
            }

        except subprocess.TimeoutExpired:
            return {
                'error': f'Command timed out after {timeout_seconds}s',
                'command': command,
                'timeout': True,
                'timeout_seconds': timeout_seconds
            }
        except Exception as e:
            return {
                'error': str(e),
                'command': command,
                'exception_type': type(e).__name__
            }

    # ===== METRICS TRACKING FUNCTIONALITY =====
    
    def create_file_metrics_tracker(self) -> Dict[str, Any]:
        """Create a new metrics tracker for file operations"""
        return {
            'file_metrics': [],
            'session_start_time': time.time()
        }
    
    def start_file_analysis_metrics(self, file_path: str) -> Dict[str, Any]:
        """Start tracking metrics for a file analysis"""
        return {
            'file_path': file_path,
            'start_time': time.time(),
            'read_start_time': None,
            'llm_start_time': None,
            'read_duration_ms': 0,
            'llm_duration_ms': 0,
            'total_duration_ms': 0,
            'file_size_bytes': 0,
            'file_lines': 0,
            'prompt_tokens': 0,
            'completion_tokens': 0,
            'total_tokens': 0,
            'success': False
        }
    
    def track_file_read_metrics(self, metrics: Dict[str, Any], file_result: Dict[str, Any]) -> Dict[str, Any]:
        """Track file read operation timing and metadata"""
        if metrics.get('read_start_time'):
            metrics['read_duration_ms'] = round((time.time() - metrics['read_start_time']) * 1000, 2)
        
        metrics['file_size_bytes'] = file_result.get('size', 0)
        metrics['file_lines'] = file_result.get('lines', 0)
        return metrics
    
    def track_llm_metrics(self, metrics: Dict[str, Any], llm_metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Track LLM operation timing and token usage"""
        if metrics.get('llm_start_time'):
            metrics['llm_duration_ms'] = round((time.time() - metrics['llm_start_time']) * 1000, 2)
        
        metrics['prompt_tokens'] = llm_metrics.get('prompt_tokens', 0)
        metrics['completion_tokens'] = llm_metrics.get('completion_tokens', 0)
        metrics['total_tokens'] = llm_metrics.get('total_tokens', 0)
        return metrics
    
    def finalize_file_metrics(self, metrics: Dict[str, Any], success: bool = True) -> Dict[str, Any]:
        """Finalize file metrics and calculate total duration"""
        metrics['total_duration_ms'] = round((time.time() - metrics['start_time']) * 1000, 2)
        metrics['success'] = success
        return metrics
    
    def print_file_metrics(self, metrics: Dict[str, Any]):
        """Print detailed per-file metrics"""
        file_path = metrics['file_path']
        logger.debug(f"Per-file metrics: {file_path} - "
                    f"read: {metrics['read_duration_ms']:.1f}ms, "
                    f"LLM: {metrics['llm_duration_ms']:.1f}ms, "
                    f"total: {metrics['total_duration_ms']:.1f}ms, "
                    f"tokens: {metrics['total_tokens']}")
    
    def print_summary_metrics(self, file_metrics: List[Dict[str, Any]], component_name: str = "CODE_AGENT"):
        """Print comprehensive summary metrics"""
        if not file_metrics:
            return

        total_files = len(file_metrics)
        successful_files = len([m for m in file_metrics if m['success']])
        total_read_time = sum(m['read_duration_ms'] for m in file_metrics)
        total_llm_time = sum(m['llm_duration_ms'] for m in file_metrics)
        total_tokens = sum(m['total_tokens'] for m in file_metrics)

        logger.debug(f"[{component_name}] Metrics summary: {successful_files}/{total_files} files, "
                    f"read: {total_read_time:.1f}ms, LLM: {total_llm_time:.1f}ms, "
                    f"tokens: {total_tokens}")
    
    def get_metrics_summary(self, file_metrics: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Get metrics summary as dictionary for programmatic use"""
        if not file_metrics:
            return {}
        
        total_files = len(file_metrics)
        successful_files = len([m for m in file_metrics if m['success']])
        total_read_time = sum(m['read_duration_ms'] for m in file_metrics)
        total_llm_time = sum(m['llm_duration_ms'] for m in file_metrics)
        total_tokens = sum(m['total_tokens'] for m in file_metrics)
        total_prompt_tokens = sum(m['prompt_tokens'] for m in file_metrics)
        total_completion_tokens = sum(m['completion_tokens'] for m in file_metrics)
        
        return {
            'total_files': total_files,
            'successful_files': successful_files,
            'success_rate': successful_files / total_files if total_files > 0 else 0,
            'total_read_time_ms': total_read_time,
            'total_llm_time_ms': total_llm_time,
            'total_tokens': total_tokens,
            'prompt_tokens': total_prompt_tokens,
            'completion_tokens': total_completion_tokens,
            'avg_tokens_per_file': total_tokens / successful_files if successful_files > 0 else 0,
            'avg_llm_time_per_file_ms': total_llm_time / successful_files if successful_files > 0 else 0
        }