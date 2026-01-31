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
        self._source_extensions_cache = None

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

        # Use grep to find files that mention the function - search all files
        pattern = rf'\b{re.escape(function_name)}\s*\('
        matching_files = self._grep_files(pattern, None)

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
        # Use word boundary matching - search all files
        pattern = rf'\b{re.escape(symbol_name)}\b'
        matches = self._grep_files(pattern, None)

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
            matches = self._grep_files(pattern, None, case_insensitive=True)

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
            # Search in file names - all source files, not just Python
            for src_file in self.repo_path.rglob('*'):
                if not src_file.is_file():
                    continue
                # Skip hidden files and common non-source directories
                if any(part.startswith('.') for part in src_file.parts):
                    continue
                rel_path = str(src_file.relative_to(self.repo_path))
                if keyword.lower() in rel_path.lower() and rel_path not in seen:
                    seen.add(rel_path)
                    files.append({
                        'file': rel_path,
                        'match_type': 'filename',
                        'keyword': keyword
                    })
                    if len(files) >= max_results:
                        break

            # Search in file content - all files
            if len(files) < max_results:
                matches = self._grep_files(keyword, None, case_insensitive=True)
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
        """Fallback returns empty - test discovery should use KB or LLM."""
        return {
            'tests': [],
            'count': 0,
            'source': 'fallback',
            'source_file': source_file,
            'strategies_used': []
        }

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    def _grep_files(self, pattern: str, extensions: Optional[List[str]] = None,
                   case_insensitive: bool = False) -> List[Dict[str, Any]]:
        """Use grep to find pattern in files. If extensions is None, search all files."""
        results = []

        cmd = ['grep', '-r', '-n']
        if case_insensitive:
            cmd.append('-i')

        # Build file patterns only if extensions specified
        if extensions:
            for ext in extensions:
                cmd.extend(['--include', f'*.{ext}'])

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
        """Find where a function is defined - language-agnostic pattern"""
        # Generic pattern: function name followed by opening paren (works across languages)
        pattern = rf'\b{re.escape(function_name)}\s*\('
        matches = self._grep_files(pattern, None)

        if matches:
            return {
                'file': matches[0]['file'],
                'line': matches[0]['line']
            }
        return None

    def _resolve_target_to_file(self, target: str) -> Optional[str]:
        """Resolve a target (module name or file path) to a file path"""
        # If it's already a file path that exists
        target_path = self.repo_path / target
        if target_path.exists() and target_path.is_file():
            return target

        # Try as module path - use glob to find matching files with any extension
        module_as_dir = target.replace('.', '/')
        parent = self.repo_path / Path(module_as_dir).parent
        name = Path(module_as_dir).name

        if parent.exists():
            # Find any file matching the module name
            matches = list(parent.glob(f"{name}.*"))
            if matches:
                try:
                    return str(matches[0].relative_to(self.repo_path))
                except ValueError:
                    pass

        # Try to find by grep - search all files
        matches = self._grep_files(rf'(class|def|function)\s+{re.escape(target)}\b', None)
        if matches:
            return matches[0]['file']

        return None

    def _extract_keywords(self, text: str) -> List[str]:
        """
        Extract keywords from text.

        Returns all unique words - LLM determines relevance in context.
        No hardcoded length thresholds or filtering.
        """
        # Extract words
        words = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', text.lower())

        # Include all words - LLM determines relevance
        seen = set()
        keywords = []
        for word in words:
            if word not in seen:
                seen.add(word)
                keywords.append(word)

        return keywords[:10]  # Limit count for practical use
