"""
Navigation Tools Handler for StructuralKBAgent

Handles code navigation tools (callers, callees, usages, tests, implementations).
"""

import os
import time
from typing import Dict, Any, Callable
from cf.agents.protocols import KnowledgeBaseProtocol


class NavigationToolsHandler:
    """Handles code navigation tools."""

    def __init__(self, kb: KnowledgeBaseProtocol, config: Dict[str, Any], record_call_fn: Callable):
        self.kb = kb
        self.config = config
        self._record_call = record_call_fn

        # Load config defaults
        kb_agent_config = config.get('agents', {}).get('structural_kb_agent', {})
        self.default_callers_limit = kb_agent_config.get('default_callers_limit', 20)
        self.default_callees_limit = kb_agent_config.get('default_callees_limit', 20)
        self.default_usages_limit = kb_agent_config.get('default_usages_limit', 30)

    def find_callers(self, function_name: str, max_results: int = None) -> Dict[str, Any]:
        """Find all functions that call a given function"""
        start_time = time.time()
        try:
            # Apply default max_results
            max_results = max_results if max_results is not None else self.default_callers_limit

            # Query KB for caller relationships
            query = """
            MATCH (caller:Function)-[:CALLS]->(target:Function)
            WHERE target.qualified_name = $function_name OR target.name = $function_name
            RETURN caller.qualified_name as caller_name,
                   caller.file_path as file_path,
                   caller.start_line as line,
                   caller.name as simple_name
            LIMIT $limit
            """

            results = self.kb.execute_query(query, {
                'function_name': function_name,
                'limit': max_results
            })

            callers = []
            for record in results.records:
                callers.append({
                    'caller': record['caller_name'],
                    'simple_name': record['simple_name'],
                    'file_path': record['file_path'],
                    'line': record['line']
                })

            self._record_call(time_taken=time.time() - start_time, error=False)
            return {
                'success': True,
                'function': function_name,
                'callers': callers,
                'count': len(callers)
            }
        except Exception as e:
            self._record_call(time_taken=time.time() - start_time, error=True)
            return {'success': False, 'error': str(e), 'callers': []}

    def find_callees(self, function_name: str, max_results: int = None) -> Dict[str, Any]:
        """Find all functions called by a given function"""
        start_time = time.time()
        try:
            # Apply default max_results
            max_results = max_results if max_results is not None else self.default_callees_limit

            query = """
            MATCH (caller:Function)-[:CALLS]->(callee:Function)
            WHERE caller.qualified_name = $function_name OR caller.name = $function_name
            RETURN callee.qualified_name as callee_name,
                   callee.file_path as file_path,
                   callee.start_line as line,
                   callee.name as simple_name
            LIMIT $limit
            """

            results = self.kb.execute_query(query, {
                'function_name': function_name,
                'limit': max_results
            })

            callees = []
            for record in results.records:
                callees.append({
                    'callee': record['callee_name'],
                    'simple_name': record['simple_name'],
                    'file_path': record['file_path'],
                    'line': record['line']
                })

            self._record_call(time_taken=time.time() - start_time, error=False)
            return {
                'success': True,
                'function': function_name,
                'callees': callees,
                'count': len(callees)
            }
        except Exception as e:
            self._record_call(time_taken=time.time() - start_time, error=True)
            return {'success': False, 'error': str(e), 'callees': []}

    def find_usages(self, symbol_name: str, symbol_type: str = 'any', max_results: int = None) -> Dict[str, Any]:
        """Find all usages of a class, function, or variable"""
        start_time = time.time()
        try:
            # Apply default max_results
            max_results = max_results if max_results is not None else self.default_usages_limit

            usages = []

            # Build query based on symbol type
            if symbol_type == 'function' or symbol_type == 'any':
                # Find function calls
                query = """
                MATCH (caller:Function)-[:CALLS]->(target:Function)
                WHERE target.name = $symbol_name
                RETURN 'call' as usage_type,
                       caller.qualified_name as location,
                       caller.file_path as file_path,
                       caller.start_line as line
                LIMIT $limit
                """
                results = self.kb.execute_query(query, {'symbol_name': symbol_name, 'limit': max_results})
                for record in results.records:
                    usages.append({
                        'type': record['usage_type'],
                        'location': record['location'],
                        'file_path': record['file_path'],
                        'line': record['line']
                    })

            if symbol_type == 'class' or symbol_type == 'any':
                # Find class usages (imports, inheritance)
                query = """
                MATCH (c:Class)
                WHERE c.name = $symbol_name
                OPTIONAL MATCH (c)<-[:INHERITS]-(subclass:Class)
                OPTIONAL MATCH (f:File)-[:IMPORTS]->(m:Module)
                WHERE m.name CONTAINS $symbol_name
                RETURN 'inheritance' as usage_type,
                       subclass.qualified_name as location,
                       subclass.file_path as file_path,
                       subclass.start_line as line
                LIMIT $limit
                """
                results = self.kb.execute_query(query, {'symbol_name': symbol_name, 'limit': max_results - len(usages)})
                for record in results.records:
                    if record['location']:  # Only if we found actual usages
                        usages.append({
                            'type': record['usage_type'],
                            'location': record['location'],
                            'file_path': record['file_path'],
                            'line': record['line']
                        })

            self._record_call(time_taken=time.time() - start_time, error=False)
            return {
                'success': True,
                'symbol': symbol_name,
                'symbol_type': symbol_type,
                'usages': usages,
                'count': len(usages)
            }
        except Exception as e:
            self._record_call(time_taken=time.time() - start_time, error=True)
            return {'success': False, 'error': str(e), 'usages': []}

    def find_related_tests(self, file_path: str, include_indirect: bool = False) -> Dict[str, Any]:
        """Find test files that test a given production file"""
        start_time = time.time()
        try:
            test_files = []

            # Pattern 1: Name-based matching
            # Extract base name from file_path
            base_name = os.path.basename(file_path).replace('.py', '')
            test_patterns = [
                f'test_{base_name}',
                f'{base_name}_test',
                f'test{base_name}',
                f'{base_name}test'
            ]

            # Find test files matching patterns
            for pattern in test_patterns:
                query = """
                MATCH (f:File)
                WHERE f.path CONTAINS $pattern AND f.path CONTAINS 'test'
                RETURN f.path as test_file
                LIMIT 10
                """
                results = self.kb.execute_query(query, {'pattern': pattern})
                for record in results.records:
                    if record['test_file'] not in [t['file_path'] for t in test_files]:
                        test_files.append({
                            'file_path': record['test_file'],
                            'relationship': 'name_match',
                            'confidence': 0.9
                        })

            # Pattern 2: Import-based matching
            # Find test files that import this file
            query = """
            MATCH (test_file:File)-[:IMPORTS]->(m:Module)
            WHERE test_file.path CONTAINS 'test' AND m.name CONTAINS $base_name
            RETURN test_file.path as test_file
            LIMIT 10
            """
            results = self.kb.execute_query(query, {'base_name': base_name})
            for record in results.records:
                if record['test_file'] not in [t['file_path'] for t in test_files]:
                    test_files.append({
                        'file_path': record['test_file'],
                        'relationship': 'imports',
                        'confidence': 0.8
                    })

            self._record_call(time_taken=time.time() - start_time, error=False)
            return {
                'success': True,
                'production_file': file_path,
                'test_files': test_files,
                'count': len(test_files)
            }
        except Exception as e:
            self._record_call(time_taken=time.time() - start_time, error=True)
            return {'success': False, 'error': str(e), 'test_files': []}

    def find_implementations(self, interface_name: str, include_indirect: bool = False) -> Dict[str, Any]:
        """Find all implementations of an interface or abstract class"""
        start_time = time.time()
        try:
            # Find direct implementations
            depth = '*1..3' if include_indirect else '*1'
            query = f"""
            MATCH (base:Class)-[:INHERITS{depth}]-(impl:Class)
            WHERE base.name = $interface_name OR base.qualified_name = $interface_name
            RETURN impl.qualified_name as implementation,
                   impl.file_path as file_path,
                   impl.start_line as line,
                   impl.name as simple_name,
                   impl.is_abstract as is_abstract
            LIMIT 50
            """

            results = self.kb.execute_query(query, {'interface_name': interface_name})

            implementations = []
            for record in results.records:
                # Filter out abstract classes from results (they're not concrete implementations)
                if not record.get('is_abstract', False):
                    implementations.append({
                        'implementation': record['implementation'],
                        'simple_name': record['simple_name'],
                        'file_path': record['file_path'],
                        'line': record['line']
                    })

            self._record_call(time_taken=time.time() - start_time, error=False)
            return {
                'success': True,
                'interface': interface_name,
                'implementations': implementations,
                'count': len(implementations)
            }
        except Exception as e:
            self._record_call(time_taken=time.time() - start_time, error=True)
            return {'success': False, 'error': str(e), 'implementations': []}
