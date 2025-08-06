"""
Repository Tools for CodeFusion

Clean, efficient file operations with grep-based searching and comprehensive metrics tracking.
"""

import os
import time
import subprocess
import mimetypes
from pathlib import Path
from typing import Dict, List, Any, Optional


class RepoTools:
    """Repository file operations and analysis tools"""
    
    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path).resolve()
        self.max_file_size = 1024 * 1024  # 1MB
        self.excluded_dirs = {'.git', '__pycache__', 'node_modules', '.venv', 'venv', '.pytest_cache'}
        self.excluded_extensions = {'.pyc', '.pyo', '.so', '.dll', '.exe', '.bin'}
    
    def scan_directory(self, directory: str = "", max_depth: int = 3, exclude_dirs: Optional[List[str]] = None) -> Dict[str, Any]:
        """Recursively scan directory to discover files and structure"""
        scan_path = self.repo_path / directory if directory else self.repo_path
        
        print(f"🔍 [SCAN] Starting scan of: {scan_path}")
        print(f"🔍 [SCAN] Max depth: {max_depth}")
        
        if not scan_path.exists():
            print(f"❌ [SCAN] Directory not found: {scan_path}")
            return {'error': f'Directory not found: {scan_path}'}
        
        # Combine default excludes with user-provided ones
        excludes = self.excluded_dirs.copy()
        if exclude_dirs:
            excludes.update(exclude_dirs)
            
        print(f"🔍 [SCAN] Excluded dirs: {excludes}")
        
        result = {
            'directory': str(scan_path),
            'files': [],
            'subdirectories': [],
            'total_files': 0,
            'total_size': 0
        }
        
        def _scan_recursive(path: Path, current_depth: int):
            if current_depth > max_depth:
                print(f"⏭️ [SCAN] Skipping depth {current_depth} (max: {max_depth}): {path}")
                return
                
            print(f"📁 [SCAN] Scanning depth {current_depth}: {path}")
            
            try:
                items = list(path.iterdir())
                print(f"📂 [SCAN] Found {len(items)} items in {path}")
                
                for item in items:
                    if item.name.startswith('.') and item.name not in {'.gitignore', '.env'}:
                        print(f"⏭️ [SCAN] Skipping hidden: {item.name}")
                        continue
                        
                    if item.is_dir():
                        if item.name in excludes:
                            print(f"🚫 [SCAN] Excluded dir: {item.name}")
                            continue
                        print(f"📁 [SCAN] Found directory: {item.name}")
                        result['subdirectories'].append(str(item.relative_to(self.repo_path)))
                        _scan_recursive(item, current_depth + 1)
                    elif item.is_file():
                        if item.suffix in self.excluded_extensions:
                            print(f"🚫 [SCAN] Excluded extension: {item.name} ({item.suffix})")
                            continue
                        if item.stat().st_size > self.max_file_size:
                            print(f"🚫 [SCAN] File too large: {item.name} ({item.stat().st_size} bytes)")
                            continue
                            
                        is_text = self._is_text_file(item)
                        relative_path = str(item.relative_to(self.repo_path))
                        file_size = item.stat().st_size
                        
                        print(f"📄 [SCAN] Found file: {item.name}")
                        print(f"   📊 Size: {file_size} bytes")
                        print(f"   📝 Extension: {item.suffix}")
                        print(f"   📖 Is text: {is_text}")
                        print(f"   🗂️  Relative path: {relative_path}")
                        
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
                print(f"🚫 [SCAN] Permission denied: {path} - {e}")
            except Exception as e:
                print(f"❌ [SCAN] Error scanning {path}: {e}")
        
        _scan_recursive(scan_path, 0)
        
        print(f"✅ [SCAN] Scan complete!")
        print(f"✅ [SCAN] Total files found: {result['total_files']}")
        print(f"✅ [SCAN] Total directories found: {len(result['subdirectories'])}")
        print(f"✅ [SCAN] Total size: {result['total_size']} bytes")
        
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
    
    def read_file(self, file_path: str, max_lines: Optional[int] = None, include_structure: bool = False) -> Dict[str, Any]:
        """Read contents of a specific file, optionally including structural analysis"""
        full_path = self.repo_path / file_path
        
        if not full_path.exists():
            return {'error': f'File not found: {file_path}'}
        
        if full_path.stat().st_size > self.max_file_size:
            return {'error': f'File too large: {file_path}'}
        
        try:
            if not self._is_text_file(full_path):
                return {'error': f'File is not text readable: {file_path}'}
            
            with open(full_path, 'r', encoding='utf-8') as f:
                if max_lines:
                    lines = [f.readline() for _ in range(max_lines)]
                    content = ''.join(lines)
                else:
                    content = f.read()
            
            result = {
                'file_path': file_path,
                'content': content,
                'size': full_path.stat().st_size,
                'lines': len(content.splitlines()),
                'encoding': 'utf-8'
            }
            
            # Add structural analysis if requested
            if include_structure:
                structure = self.analyze_file_structure(file_path)
                if 'error' not in structure:
                    result['structure_analysis'] = structure
            
            return result
        except Exception as e:
            return {'error': f'Failed to read file: {str(e)}'}
    
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
                # Default to common source file types
                for ext in ['.py', '.js', '.ts', '.java', '.cpp', '.c', '.h', '.md', '.txt', '.yml', '.yaml', '.json']:
                    cmd.extend(['--include', f'*{ext}'])
            
            # Exclude common directories
            for exclude_dir in self.excluded_dirs:
                cmd.extend(['--exclude-dir', exclude_dir])
            
            # Set search directory
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
        import re
        
        matches = []
        pattern_re = re.compile(pattern, re.IGNORECASE)
        
        # Determine file extensions to search
        extensions = set()
        if file_types:
            extensions = {f'.{ext}' if not ext.startswith('.') else ext for ext in file_types}
        else:
            extensions = {'.py', '.js', '.ts', '.java', '.cpp', '.c', '.h', '.md', '.txt', '.yml', '.yaml', '.json'}
        
        def _search_directory(directory: Path):
            if len(matches) >= max_results:
                return
                
            try:
                for item in directory.iterdir():
                    if len(matches) >= max_results:
                        break
                        
                    if item.is_dir() and item.name not in self.excluded_dirs:
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
        
        print(f"📋 [FILE_INFO] Getting info for: {file_path}")
        print(f"📋 [FILE_INFO] Include metrics: {include_metrics}")
        
        if not full_path.exists():
            print(f"❌ [FILE_INFO] File not found: {file_path}")
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
            
            print(f"📋 [FILE_INFO] Metadata extracted:")
            print(f"   📊 Size: {stat.st_size} bytes")
            print(f"   📝 Extension: {full_path.suffix}")
            print(f"   📖 Is text: {is_text}")
            print(f"   🏷️  MIME type: {mime_type}")
            
            # Add code metrics if requested and file is text
            if include_metrics and info['is_text']:
                print(f"📊 [FILE_INFO] Calculating code metrics...")
                metrics = self.calculate_file_metrics(file_path)
                if 'error' not in metrics:
                    info['code_metrics'] = metrics
                    print(f"📊 [FILE_INFO] Metrics added: {metrics.get('language', 'unknown')} - {metrics.get('total_lines', 0)} lines")
                else:
                    print(f"❌ [FILE_INFO] Metrics calculation failed: {metrics.get('error')}")
            elif include_metrics and not info['is_text']:
                print(f"⏭️ [FILE_INFO] Skipping metrics for non-text file")
            
            return info
        except Exception as e:
            print(f"❌ [FILE_INFO] Failed to get file info: {str(e)}")
            return {'error': f'Failed to get file info: {str(e)}'}
    
    def _is_text_file(self, file_path: Path) -> bool:
        """Check if file is likely a text file"""
        if file_path.suffix in {'.py', '.js', '.ts', '.java', '.cpp', '.c', '.h', '.md', '.txt', '.yml', '.yaml', '.json', '.xml', '.html', '.css', '.sql', '.sh', '.bat'}:
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
        print(f"📊 [METRICS] Calculating metrics for: {file_path}")
        
        # Use read_file to get content
        file_data = self.read_file(file_path)
        if 'error' in file_data:
            print(f"❌ [METRICS] Failed to read file: {file_data.get('error')}")
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
        
        print(f"📊 [METRICS] Basic metrics:")
        print(f"   📝 Total lines: {len(lines)}")
        print(f"   📝 Non-empty lines: {len(non_empty_lines)}")
        print(f"   🏷️  Language: {language}")
        
        # Language-specific complexity analysis
        if extension == '.py':
            print(f"🐍 [METRICS] Analyzing Python complexity...")
            metrics['complexity_indicators'] = self._analyze_python_complexity(content)
        elif extension in ['.js', '.ts']:
            print(f"🟨 [METRICS] Analyzing JavaScript/TypeScript complexity...")
            metrics['complexity_indicators'] = self._analyze_js_complexity(content)
        else:
            print(f"❓ [METRICS] Unknown language, skipping complexity analysis")
            metrics['complexity_indicators'] = {'estimated_complexity': 'unknown'}
        
        print(f"📊 [METRICS] Complexity: {metrics['complexity_indicators']}")
        
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
        
        if extension == '.py':
            structure.update(self.parse_python_structure(content, lines))
        elif extension in ['.js', '.ts']:
            structure.update(self.parse_js_structure(content, lines))
        elif extension == '.md':
            structure.update(self.parse_markdown_structure(lines))
        
        return structure
    
    def parse_python_structure(self, content: str, lines: List[str]) -> Dict[str, Any]:
        """Parse Python file structure from content"""
        import re
        
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
        import re
        
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
        """Detect programming language from file extension"""
        lang_map = {
            '.py': 'Python',
            '.js': 'JavaScript', 
            '.ts': 'TypeScript',
            '.java': 'Java',
            '.cpp': 'C++',
            '.c': 'C',
            '.h': 'C/C++ Header',
            '.go': 'Go',
            '.rs': 'Rust',
            '.rb': 'Ruby',
            '.php': 'PHP',
            '.md': 'Markdown',
            '.yml': 'YAML',
            '.yaml': 'YAML',
            '.json': 'JSON'
        }
        return lang_map.get(extension.lower(), 'Unknown')
    
    def _analyze_python_complexity(self, content: str) -> Dict[str, Any]:
        """Analyze Python code complexity"""
        import re
        
        functions = len(re.findall(r'^\s*def\s+\w+\s*\(', content, re.MULTILINE))
        classes = len(re.findall(r'^\s*class\s+\w+\s*[:\(]', content, re.MULTILINE))
        imports = len(re.findall(r'^\s*(?:from\s+.+\s+)?import\s+', content, re.MULTILINE))
        
        return {
            'functions': functions,
            'classes': classes,
            'imports': imports,
            'estimated_complexity': 'low' if functions + classes < 5 else 'medium' if functions + classes < 15 else 'high'
        }
    
    def _analyze_js_complexity(self, content: str) -> Dict[str, Any]:
        """Analyze JavaScript/TypeScript code complexity"""
        import re
        
        functions = len(re.findall(r'function\s+\w+\s*\(|const\s+\w+\s*=\s*\([^)]*\)\s*=>', content, re.MULTILINE))
        classes = len(re.findall(r'class\s+\w+\s*{', content, re.MULTILINE))
        imports = len(re.findall(r'^\s*(?:import|export)', content, re.MULTILINE))
        
        return {
            'functions': functions,
            'classes': classes,
            'imports': imports,
            'estimated_complexity': 'low' if functions + classes < 5 else 'medium' if functions + classes < 15 else 'high'
        }

    def _should_exclude_file(self, file_path: Path) -> bool:
        """Check if file should be excluded from processing"""
        if file_path.suffix in self.excluded_extensions:
            return True
        if file_path.stat().st_size > self.max_file_size:
            return True
        if any(excluded in file_path.parts for excluded in self.excluded_dirs):
            return True
        return False

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
        print(f"\n📊 [CODE_AGENT] Per-file metrics: {file_path}")  
        print(f"   🛠️  Tool call (read_file): {metrics['read_duration_ms']:.1f}ms")
        print(f"   📖 File read time: {metrics['read_duration_ms']:.1f}ms") 
        print(f"   🤖 LLM summary generation: {metrics['llm_duration_ms']:.1f}ms")
        print(f"   ⏱️  Total file processing: {metrics['total_duration_ms']:.1f}ms")
        print(f"   🎯 Token usage: {metrics['prompt_tokens']} prompt → {metrics['completion_tokens']} completion = {metrics['total_tokens']} total")
        print(f"   📄 File size: {metrics['file_size_bytes']} bytes, {metrics['file_lines']} lines")
        print(f"   {'─' * 80}")
    
    def print_summary_metrics(self, file_metrics: List[Dict[str, Any]], component_name: str = "CODE_AGENT"):
        """Print comprehensive summary metrics"""
        if not file_metrics:
            return
        
        total_files = len(file_metrics)
        successful_files = len([m for m in file_metrics if m['success']])
        total_read_time = sum(m['read_duration_ms'] for m in file_metrics)
        total_llm_time = sum(m['llm_duration_ms'] for m in file_metrics)
        total_tokens = sum(m['total_tokens'] for m in file_metrics)
        total_prompt_tokens = sum(m['prompt_tokens'] for m in file_metrics)
        total_completion_tokens = sum(m['completion_tokens'] for m in file_metrics)
        
        print(f"\n📊 [{component_name}] File Analysis Metrics Summary:")
        print(f"   📁 Files processed: {successful_files}/{total_files}")
        print(f"   ⏱️  Total read time: {total_read_time:.1f}ms")
        print(f"   🤖 Total LLM time: {total_llm_time:.1f}ms")
        print(f"   🎯 Total tokens: {total_tokens} ({total_prompt_tokens} → {total_completion_tokens})")
        print(f"   📈 Avg tokens/file: {total_tokens/successful_files:.0f}" if successful_files > 0 else "")
        print(f"   🚀 Avg LLM time/file: {total_llm_time/successful_files:.1f}ms" if successful_files > 0 else "")
    
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