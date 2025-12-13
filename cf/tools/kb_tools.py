"""
KB Tools - Knowledge Base Tools with Fallback Support

Provides KB query capabilities that work with or without a built knowledge base.
When KB is available, uses fast graph queries. When not, falls back to grep/AST.

This eliminates the need for StructuralKBAgent - tools are registered directly.
"""

import ast
import os
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable


class KBTools:
    """
    Knowledge Base query tools with grep/AST fallbacks.

    Design principle: KB is for PERFORMANCE, not for enabling features.
    All tools work without KB, just slower.
    """

    def __init__(self, repo_path: str, kb_orchestrator: Optional[Any] = None):
        """
        Initialize KB tools.

        Args:
            repo_path: Path to repository
            kb_orchestrator: Optional KBOrchestrator for fast queries
        """
        self.repo_path = Path(repo_path)
        self.kb = kb_orchestrator
        self._kb_available = False

        # Check if KB is available and initialized
        if self.kb:
            try:
                self._kb_available = self.kb.is_initialized()
            except Exception:
                self._kb_available = False

    def is_kb_available(self) -> bool:
        """Check if KB is available for fast queries"""
        return self._kb_available

    # =========================================================================
    # NAVIGATION TOOLS - Find callers, callees, usages
    # =========================================================================

    def find_callers(self, function_name: str, max_results: int = 100) -> Dict[str, Any]:
        """
        Find all functions that call the specified function.

        Uses KB graph query if available, falls back to grep + AST parsing.
        """
        if self._kb_available:
            return self._find_callers_kb(function_name, max_results)
        return self._find_callers_fallback(function_name, max_results)

    def _find_callers_kb(self, function_name: str, max_results: int) -> Dict[str, Any]:
        """KB-based caller lookup (fast)"""
        try:
            result = self.kb.find_callers(function_name, max_results)
            return {
                'callers': result.get('callers', []),
                'count': len(result.get('callers', [])),
                'source': 'kb',
                'function_name': function_name
            }
        except Exception as e:
            # Fall back if KB query fails
            return self._find_callers_fallback(function_name, max_results)

    def _find_callers_fallback(self, function_name: str, max_results: int) -> Dict[str, Any]:
        """Grep + AST fallback for finding callers (slower but always works)"""
        callers = []

        # Use grep to find files that mention the function
        pattern = rf'\b{re.escape(function_name)}\s*\('
        matching_files = self._grep_files(pattern, ['py'])

        for file_info in matching_files[:max_results * 2]:  # Check more files than needed
            file_path = file_info['file']
            try:
                with open(self.repo_path / file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Parse AST to find actual function calls
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Call):
                        call_name = self._get_call_name(node)
                        if call_name == function_name:
                            # Find the enclosing function
                            enclosing = self._find_enclosing_function(tree, node)
                            if enclosing:
                                caller_info = {
                                    'caller': enclosing,
                                    'file': file_path,
                                    'line': node.lineno
                                }
                                if caller_info not in callers:
                                    callers.append(caller_info)
                                    if len(callers) >= max_results:
                                        break
            except Exception:
                # Skip files that can't be parsed
                continue

            if len(callers) >= max_results:
                break

        return {
            'callers': callers,
            'count': len(callers),
            'source': 'grep_ast',
            'function_name': function_name
        }

    def find_callees(self, function_name: str, max_results: int = 100) -> Dict[str, Any]:
        """
        Find all functions called by the specified function.

        Uses KB graph query if available, falls back to AST parsing.
        """
        if self._kb_available:
            return self._find_callees_kb(function_name, max_results)
        return self._find_callees_fallback(function_name, max_results)

    def _find_callees_kb(self, function_name: str, max_results: int) -> Dict[str, Any]:
        """KB-based callee lookup (fast)"""
        try:
            result = self.kb.find_callees(function_name, max_results)
            return {
                'callees': result.get('callees', []),
                'count': len(result.get('callees', [])),
                'source': 'kb',
                'function_name': function_name
            }
        except Exception as e:
            return self._find_callees_fallback(function_name, max_results)

    def _find_callees_fallback(self, function_name: str, max_results: int) -> Dict[str, Any]:
        """AST fallback for finding callees"""
        callees = []

        # First find the function definition
        func_def = self._find_function_definition(function_name)
        if not func_def:
            return {
                'callees': [],
                'count': 0,
                'source': 'grep_ast',
                'function_name': function_name,
                'error': f'Function {function_name} not found'
            }

        try:
            with open(self.repo_path / func_def['file'], 'r', encoding='utf-8') as f:
                content = f.read()

            tree = ast.parse(content)

            # Find the function node
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if node.name == function_name:
                        # Extract all calls within this function
                        for child in ast.walk(node):
                            if isinstance(child, ast.Call):
                                call_name = self._get_call_name(child)
                                if call_name and call_name not in [c['callee'] for c in callees]:
                                    callees.append({
                                        'callee': call_name,
                                        'line': child.lineno
                                    })
                                    if len(callees) >= max_results:
                                        break
                        break
        except Exception:
            pass

        return {
            'callees': callees,
            'count': len(callees),
            'source': 'grep_ast',
            'function_name': function_name
        }

    def find_usages(self, symbol_name: str, symbol_type: str = 'any',
                    max_results: int = 100) -> Dict[str, Any]:
        """
        Find all usages of a symbol (function, class, variable).

        Uses KB if available, falls back to grep.
        """
        if self._kb_available:
            return self._find_usages_kb(symbol_name, symbol_type, max_results)
        return self._find_usages_fallback(symbol_name, symbol_type, max_results)

    def _find_usages_kb(self, symbol_name: str, symbol_type: str,
                        max_results: int) -> Dict[str, Any]:
        """KB-based usage lookup"""
        try:
            result = self.kb.find_usages(symbol_name, symbol_type, max_results)
            return {
                'usages': result.get('usages', []),
                'count': len(result.get('usages', [])),
                'source': 'kb',
                'symbol_name': symbol_name,
                'symbol_type': symbol_type
            }
        except Exception:
            return self._find_usages_fallback(symbol_name, symbol_type, max_results)

    def _find_usages_fallback(self, symbol_name: str, symbol_type: str,
                              max_results: int) -> Dict[str, Any]:
        """Grep fallback for finding usages"""
        # Use word boundary matching
        pattern = rf'\b{re.escape(symbol_name)}\b'
        matches = self._grep_files(pattern, ['py'])

        usages = []
        for match in matches[:max_results]:
            usages.append({
                'file': match['file'],
                'line': match.get('line', 0),
                'context': match.get('context', '')[:100]
            })

        return {
            'usages': usages,
            'count': len(usages),
            'source': 'grep',
            'symbol_name': symbol_name,
            'symbol_type': symbol_type
        }

    # =========================================================================
    # SEMANTIC SEARCH TOOLS
    # =========================================================================

    def search_by_semantics(self, query: str, scope: str = 'all',
                           limit: int = 20) -> Dict[str, Any]:
        """
        Search code by semantic meaning.

        Uses KB embeddings if available, falls back to keyword search.
        """
        if self._kb_available:
            return self._search_semantics_kb(query, scope, limit)
        return self._search_semantics_fallback(query, scope, limit)

    def _search_semantics_kb(self, query: str, scope: str, limit: int) -> Dict[str, Any]:
        """KB-based semantic search using embeddings"""
        try:
            result = self.kb.semantic_search(query, scope, limit)
            return {
                'results': result.get('results', []),
                'count': len(result.get('results', [])),
                'source': 'kb_embeddings',
                'query': query
            }
        except Exception:
            return self._search_semantics_fallback(query, scope, limit)

    def _search_semantics_fallback(self, query: str, scope: str,
                                   limit: int) -> Dict[str, Any]:
        """Keyword-based fallback for semantic search"""
        # Extract keywords from query
        keywords = self._extract_keywords(query)

        results = []
        seen_files = set()

        for keyword in keywords:
            pattern = rf'\b{re.escape(keyword)}\b'
            matches = self._grep_files(pattern, ['py'], case_insensitive=True)

            for match in matches:
                if match['file'] not in seen_files:
                    seen_files.add(match['file'])
                    results.append({
                        'file': match['file'],
                        'relevance': 'keyword_match',
                        'matched_keyword': keyword,
                        'line': match.get('line', 0)
                    })
                    if len(results) >= limit:
                        break

            if len(results) >= limit:
                break

        return {
            'results': results,
            'count': len(results),
            'source': 'keyword_search',
            'query': query,
            'keywords_used': keywords
        }

    def search_by_functionality(self, description: str,
                               limit: int = 20) -> Dict[str, Any]:
        """
        Find code that implements specific functionality.

        Uses KB if available, falls back to keyword + pattern matching.
        """
        if self._kb_available:
            return self._search_functionality_kb(description, limit)
        return self._search_functionality_fallback(description, limit)

    def _search_functionality_kb(self, description: str, limit: int) -> Dict[str, Any]:
        """KB-based functionality search"""
        try:
            result = self.kb.search_by_functionality(description, limit)
            return {
                'results': result.get('results', []),
                'count': len(result.get('results', [])),
                'source': 'kb',
                'description': description
            }
        except Exception:
            return self._search_functionality_fallback(description, limit)

    def _search_functionality_fallback(self, description: str,
                                       limit: int) -> Dict[str, Any]:
        """Keyword + pattern based fallback"""
        # Use semantic search fallback with extracted keywords
        return self._search_semantics_fallback(description, 'all', limit)

    # =========================================================================
    # DEPENDENCY TOOLS
    # =========================================================================

    def find_dependencies(self, target: str,
                         dependency_type: str = 'all') -> Dict[str, Any]:
        """
        Find what a module/function depends on.

        Uses KB if available, falls back to AST import analysis.
        """
        if self._kb_available:
            return self._find_dependencies_kb(target, dependency_type)
        return self._find_dependencies_fallback(target, dependency_type)

    def _find_dependencies_kb(self, target: str, dependency_type: str) -> Dict[str, Any]:
        """KB-based dependency lookup"""
        try:
            result = self.kb.find_dependencies(target, dependency_type)
            return {
                'dependencies': result.get('dependencies', []),
                'count': len(result.get('dependencies', [])),
                'source': 'kb',
                'target': target
            }
        except Exception:
            return self._find_dependencies_fallback(target, dependency_type)

    def _find_dependencies_fallback(self, target: str,
                                    dependency_type: str) -> Dict[str, Any]:
        """AST-based dependency analysis"""
        dependencies = {'imports': [], 'calls': []}

        # Try to find the target file
        target_file = self._resolve_target_to_file(target)
        if not target_file:
            return {
                'dependencies': dependencies,
                'count': 0,
                'source': 'ast',
                'target': target,
                'error': f'Target {target} not found'
            }

        try:
            with open(self.repo_path / target_file, 'r', encoding='utf-8') as f:
                content = f.read()

            tree = ast.parse(content)

            # Extract imports
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        dependencies['imports'].append({
                            'module': alias.name,
                            'alias': alias.asname
                        })
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ''
                    for alias in node.names:
                        dependencies['imports'].append({
                            'module': f'{module}.{alias.name}' if module else alias.name,
                            'from': module,
                            'name': alias.name,
                            'alias': alias.asname
                        })
        except Exception:
            pass

        total = len(dependencies['imports']) + len(dependencies['calls'])
        return {
            'dependencies': dependencies,
            'count': total,
            'source': 'ast',
            'target': target
        }

    # =========================================================================
    # FILE DISCOVERY
    # =========================================================================

    def find_files_for_question(self, question: str,
                               max_results: int = 50) -> Dict[str, Any]:
        """
        Find relevant files to answer a question.

        Uses KB semantic search if available, falls back to keyword matching.
        """
        if self._kb_available:
            return self._find_files_kb(question, max_results)
        return self._find_files_fallback(question, max_results)

    def _find_files_kb(self, question: str, max_results: int) -> Dict[str, Any]:
        """KB-based file discovery"""
        try:
            result = self.kb.find_files_for_question(question, max_results)
            return {
                'files': result.get('files', []),
                'count': len(result.get('files', [])),
                'source': 'kb',
                'question': question
            }
        except Exception:
            return self._find_files_fallback(question, max_results)

    def _find_files_fallback(self, question: str, max_results: int) -> Dict[str, Any]:
        """Keyword-based file discovery"""
        keywords = self._extract_keywords(question)

        files = []
        seen = set()

        for keyword in keywords:
            # Search in file names
            for py_file in self.repo_path.rglob('*.py'):
                rel_path = str(py_file.relative_to(self.repo_path))
                if keyword.lower() in rel_path.lower() and rel_path not in seen:
                    seen.add(rel_path)
                    files.append({
                        'file': rel_path,
                        'match_type': 'filename',
                        'keyword': keyword
                    })
                    if len(files) >= max_results:
                        break

            # Search in file content
            if len(files) < max_results:
                matches = self._grep_files(keyword, ['py'], case_insensitive=True)
                for match in matches:
                    if match['file'] not in seen:
                        seen.add(match['file'])
                        files.append({
                            'file': match['file'],
                            'match_type': 'content',
                            'keyword': keyword
                        })
                        if len(files) >= max_results:
                            break

            if len(files) >= max_results:
                break

        return {
            'files': files,
            'count': len(files),
            'source': 'keyword_search',
            'question': question,
            'keywords_used': keywords
        }

    # =========================================================================
    # TEST DISCOVERY
    # =========================================================================

    def find_related_tests(self, source_file: str,
                          max_results: int = 20) -> Dict[str, Any]:
        """
        Find test files related to a source file.

        Uses KB if available, falls back to naming conventions and import analysis.
        """
        if self._kb_available:
            return self._find_related_tests_kb(source_file, max_results)
        return self._find_related_tests_fallback(source_file, max_results)

    def _find_related_tests_kb(self, source_file: str,
                               max_results: int) -> Dict[str, Any]:
        """KB-based test discovery"""
        try:
            result = self.kb.find_related_tests(source_file, max_results)
            return {
                'tests': result.get('tests', []),
                'count': len(result.get('tests', [])),
                'source': 'kb',
                'source_file': source_file
            }
        except Exception:
            return self._find_related_tests_fallback(source_file, max_results)

    def _find_related_tests_fallback(self, source_file: str,
                                     max_results: int) -> Dict[str, Any]:
        """
        Fallback test discovery using naming conventions and imports.

        Strategies:
        1. Look for test_<filename>.py or <filename>_test.py
        2. Look for tests/<filename> or test/<filename>
        3. Search for imports of the source module in test files
        """
        tests = []
        seen = set()

        # Normalize source file path
        source_path = Path(source_file)
        if source_path.suffix != '.py':
            source_path = Path(source_file + '.py')

        # Extract base name without extension
        base_name = source_path.stem

        # Strategy 1: Naming conventions (test_*.py, *_test.py)
        test_patterns = [
            f'test_{base_name}.py',
            f'{base_name}_test.py',
            f'test_{base_name}*.py',
            f'*{base_name}*test*.py',
        ]

        for pattern in test_patterns:
            for test_file in self.repo_path.rglob(pattern):
                rel_path = str(test_file.relative_to(self.repo_path))
                if rel_path not in seen and self._is_test_file(rel_path):
                    seen.add(rel_path)
                    tests.append({
                        'test_file': rel_path,
                        'match_type': 'naming_convention',
                        'pattern': pattern
                    })
                    if len(tests) >= max_results:
                        break
            if len(tests) >= max_results:
                break

        # Strategy 2: Look in tests/ or test/ directories
        if len(tests) < max_results:
            for test_dir in ['tests', 'test']:
                test_dir_path = self.repo_path / test_dir
                if test_dir_path.exists():
                    for test_file in test_dir_path.rglob('*.py'):
                        rel_path = str(test_file.relative_to(self.repo_path))
                        if rel_path not in seen and self._is_test_file(rel_path):
                            # Check if file name contains base_name
                            if base_name.lower() in test_file.stem.lower():
                                seen.add(rel_path)
                                tests.append({
                                    'test_file': rel_path,
                                    'match_type': 'test_directory',
                                    'test_dir': test_dir
                                })
                                if len(tests) >= max_results:
                                    break
                if len(tests) >= max_results:
                    break

        # Strategy 3: Search for imports of the source module in test files
        if len(tests) < max_results:
            # Convert file path to module path for import search
            module_name = base_name
            if '/' in source_file or '\\' in source_file:
                # Convert path to module (e.g., cf/agents/base.py -> cf.agents.base)
                module_parts = source_path.with_suffix('').parts
                module_name = '.'.join(module_parts)

            # Search for imports in test files
            import_patterns = [
                rf'from\s+.*{re.escape(base_name)}\s+import',
                rf'import\s+.*{re.escape(base_name)}',
            ]

            for pattern in import_patterns:
                matches = self._grep_files(pattern, ['py'])
                for match in matches:
                    file_path = match['file']
                    if file_path not in seen and self._is_test_file(file_path):
                        seen.add(file_path)
                        tests.append({
                            'test_file': file_path,
                            'match_type': 'import_reference',
                            'line': match.get('line', 0)
                        })
                        if len(tests) >= max_results:
                            break
                if len(tests) >= max_results:
                    break

        return {
            'tests': tests,
            'count': len(tests),
            'source': 'fallback',
            'source_file': source_file,
            'strategies_used': ['naming_convention', 'test_directory', 'import_reference']
        }

    def _is_test_file(self, file_path: str) -> bool:
        """Check if a file is a test file based on naming conventions"""
        path = Path(file_path)
        name = path.stem.lower()
        parts = path.parts

        # Exclude virtual environments and common non-project directories
        excluded_dirs = {'.venv', 'venv', 'env', '.env', 'node_modules',
                        'site-packages', '__pycache__', '.git', '.tox'}
        if any(excl in parts for excl in excluded_dirs):
            return False

        # Check common test file patterns
        if name.startswith('test_') or name.endswith('_test'):
            return True

        # Check if in tests/ or test/ directory
        if 'tests' in parts or 'test' in parts:
            return True

        # Check for conftest.py (pytest fixtures)
        if name == 'conftest':
            return True

        return False

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    def _grep_files(self, pattern: str, extensions: List[str],
                   case_insensitive: bool = False) -> List[Dict[str, Any]]:
        """Use grep to find pattern in files"""
        results = []

        # Build file patterns
        include_args = []
        for ext in extensions:
            include_args.extend(['--include', f'*.{ext}'])

        cmd = ['grep', '-r', '-n']
        if case_insensitive:
            cmd.append('-i')
        cmd.extend(include_args)
        cmd.extend([pattern, str(self.repo_path)])

        try:
            result = subprocess.run(cmd, capture_output=True, text=True,
                                   timeout=30, cwd=str(self.repo_path))

            for line in result.stdout.splitlines()[:200]:  # Limit results
                # Parse grep output: filename:line:content
                parts = line.split(':', 2)
                if len(parts) >= 3:
                    file_path = parts[0]
                    # Make path relative to repo
                    if file_path.startswith(str(self.repo_path)):
                        file_path = file_path[len(str(self.repo_path)) + 1:]
                    results.append({
                        'file': file_path,
                        'line': int(parts[1]) if parts[1].isdigit() else 0,
                        'context': parts[2][:200]
                    })
        except Exception:
            pass

        return results

    def _get_call_name(self, node: ast.Call) -> Optional[str]:
        """Extract the function name from a Call node"""
        if isinstance(node.func, ast.Name):
            return node.func.id
        elif isinstance(node.func, ast.Attribute):
            return node.func.attr
        return None

    def _find_enclosing_function(self, tree: ast.AST,
                                 target_node: ast.AST) -> Optional[str]:
        """Find the function that contains a node"""
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for child in ast.walk(node):
                    if child is target_node:
                        return node.name
        return None

    def _find_function_definition(self, function_name: str) -> Optional[Dict[str, Any]]:
        """Find where a function is defined"""
        pattern = rf'def\s+{re.escape(function_name)}\s*\('
        matches = self._grep_files(pattern, ['py'])

        if matches:
            return {
                'file': matches[0]['file'],
                'line': matches[0]['line']
            }
        return None

    def _resolve_target_to_file(self, target: str) -> Optional[str]:
        """Resolve a target (module name or file path) to a file path"""
        # If it's already a file path
        if target.endswith('.py'):
            if (self.repo_path / target).exists():
                return target

        # Try as module path
        module_path = target.replace('.', '/') + '.py'
        if (self.repo_path / module_path).exists():
            return module_path

        # Try to find by grep
        matches = self._grep_files(rf'(class|def)\s+{re.escape(target)}\b', ['py'])
        if matches:
            return matches[0]['file']

        return None

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract meaningful keywords from text"""
        # Remove common words
        stop_words = {
            'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
            'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
            'would', 'could', 'should', 'may', 'might', 'must', 'shall',
            'can', 'need', 'dare', 'ought', 'used', 'to', 'of', 'in',
            'for', 'on', 'with', 'at', 'by', 'from', 'as', 'into',
            'through', 'during', 'before', 'after', 'above', 'below',
            'between', 'under', 'again', 'further', 'then', 'once',
            'here', 'there', 'when', 'where', 'why', 'how', 'all',
            'each', 'few', 'more', 'most', 'other', 'some', 'such',
            'no', 'nor', 'not', 'only', 'own', 'same', 'so', 'than',
            'too', 'very', 'just', 'and', 'but', 'if', 'or', 'because',
            'until', 'while', 'this', 'that', 'these', 'those', 'what',
            'which', 'who', 'whom', 'whose', 'i', 'you', 'he', 'she',
            'it', 'we', 'they', 'me', 'him', 'her', 'us', 'them'
        }

        # Extract words
        words = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', text.lower())

        # Filter and dedupe
        keywords = []
        seen = set()
        for word in words:
            if word not in stop_words and word not in seen and len(word) > 2:
                seen.add(word)
                keywords.append(word)

        return keywords[:10]  # Limit keywords
