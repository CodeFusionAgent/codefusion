"""
Test File Analysis Pipeline for CodeFusion

Specialized analyzer for test files that extracts:
- Test scenarios and cases
- Usage examples
- Edge cases and error handling
- Tested components mapping
"""

import re
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass


@dataclass
class TestScenario:
    """A single test scenario"""
    test_name: str
    tested_function: Optional[str]
    scenario_type: str  # 'positive', 'negative', 'edge_case', 'integration'
    description: str
    assertions: List[str]
    line_number: Optional[int] = None


@dataclass
class TestFileAnalysis:
    """Result of analyzing a test file"""
    file_path: str
    test_framework: str  # 'pytest', 'unittest', 'nose', 'unknown'
    tested_module: Optional[str]
    scenarios: List[TestScenario]
    usage_examples: List[str]
    edge_cases: List[str]
    total_tests: int


class TestFileAnalyzer:
    """
    Specialized analyzer for test files.

    Why tests matter:
    - Show how APIs are actually used
    - Reveal edge cases and error handling
    - Document expected behavior
    - Provide concrete usage examples
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config

        # Test file patterns
        self.test_file_patterns = [
            r'test_.*\.py$',
            r'.*_test\.py$',
            r'tests?/.*\.py$',
        ]

        # Test function patterns
        self.test_function_patterns = [
            r'def\s+test_(\w+)',
            r'def\s+(\w+_test)\(',
            r'@pytest\.mark\.',
            r'class\s+Test(\w+)',
        ]

    def is_test_file(self, file_path: str) -> bool:
        """Check if a file is a test file"""
        for pattern in self.test_file_patterns:
            if re.search(pattern, file_path):
                return True
        return False

    def analyze_test_file(self, file_path: str, content: str, structure: Dict[str, Any]) -> TestFileAnalysis:
        """
        Analyze a test file to extract test scenarios and usage patterns.

        Args:
            file_path: Path to test file
            content: File content
            structure: Parsed structure (functions, classes)

        Returns:
            TestFileAnalysis with extracted test information
        """
        # 1. Detect test framework
        framework = self._detect_test_framework(content)

        # 2. Identify tested module
        tested_module = self._identify_tested_module(file_path, content)

        # 3. Extract test scenarios
        scenarios = self._extract_test_scenarios(content, structure, framework)

        # 4. Extract usage examples (how the tested code is called)
        usage_examples = self._extract_usage_examples(content, scenarios)

        # 5. Identify edge cases
        edge_cases = self._identify_edge_cases(scenarios)

        return TestFileAnalysis(
            file_path=file_path,
            test_framework=framework,
            tested_module=tested_module,
            scenarios=scenarios,
            usage_examples=usage_examples,
            edge_cases=edge_cases,
            total_tests=len(scenarios)
        )

    def _detect_test_framework(self, content: str) -> str:
        """Detect which test framework is being used"""
        if 'import pytest' in content or '@pytest.' in content:
            return 'pytest'
        elif 'import unittest' in content or 'TestCase' in content:
            return 'unittest'
        elif 'import nose' in content:
            return 'nose'
        elif '@Test' in content:  # Java-style
            return 'junit'
        else:
            return 'unknown'

    def _identify_tested_module(self, file_path: str, content: str) -> Optional[str]:
        """Identify which module is being tested"""
        # Strategy 1: Look for imports from parent module
        # E.g., test_auth.py imports from auth.py
        imports = re.findall(r'from\s+([\w.]+)\s+import', content)
        imports.extend(re.findall(r'import\s+([\w.]+)', content))

        # Filter out test frameworks and stdlib
        stdlib_modules = {'os', 'sys', 'time', 'json', 'unittest', 'pytest', 'nose'}
        candidate_modules = [m for m in imports if not m.startswith('test') and m not in stdlib_modules]

        if candidate_modules:
            return candidate_modules[0]

        # Strategy 2: Infer from file name
        # test_auth.py -> auth
        match = re.search(r'test[_-]?(\w+)\.py$', file_path)
        if match:
            return match.group(1)

        return None

    def _extract_test_scenarios(self,
                               content: str,
                               structure: Dict[str, Any],
                               framework: str) -> List[TestScenario]:
        """Extract test scenarios from test file"""
        scenarios = []
        functions = structure.get('functions', [])

        for func_info in functions:
            if not isinstance(func_info, dict):
                continue

            func_name = func_info.get('name', '')
            if not func_name.startswith('test_'):
                continue

            # Extract test type from name
            scenario_type = self._infer_scenario_type(func_name)

            # Find tested function (heuristic)
            tested_func = self._infer_tested_function(func_name)

            # Extract assertions
            assertions = self._extract_assertions(content, func_name, framework)

            # Generate description from test name
            description = self._generate_test_description(func_name)

            scenarios.append(TestScenario(
                test_name=func_name,
                tested_function=tested_func,
                scenario_type=scenario_type,
                description=description,
                assertions=assertions,
                line_number=func_info.get('line', None)
            ))

        return scenarios

    def _infer_scenario_type(self, test_name: str) -> str:
        """Infer test scenario type from test name"""
        test_lower = test_name.lower()

        if any(word in test_lower for word in ['invalid', 'error', 'fail', 'exception', 'raises']):
            return 'negative'
        elif any(word in test_lower for word in ['edge', 'boundary', 'limit', 'empty', 'null', 'none']):
            return 'edge_case'
        elif any(word in test_lower for word in ['integration', 'end_to_end', 'e2e']):
            return 'integration'
        else:
            return 'positive'

    def _infer_tested_function(self, test_name: str) -> Optional[str]:
        """Infer which function is being tested from test name"""
        # Common patterns:
        # test_calculate_total -> calculate_total
        # test_user_login_success -> user_login
        # test_valid_email -> validate_email

        test_lower = test_name.lower().replace('test_', '')

        # Remove common suffixes
        for suffix in ['_success', '_failure', '_error', '_valid', '_invalid', '_edge', '_integration']:
            test_lower = test_lower.replace(suffix, '')

        return test_lower if test_lower else None

    def _extract_assertions(self, content: str, test_name: str, framework: str) -> List[str]:
        """Extract assertion statements from a test function"""
        assertions = []

        # Find the test function body
        func_pattern = rf'def {test_name}\([^)]*\):'
        match = re.search(func_pattern, content)
        if not match:
            return assertions

        # Get content after function definition
        start_pos = match.end()
        rest_content = content[start_pos:]

        # Find assertions based on framework
        if framework == 'pytest':
            # pytest: assert statements
            assertion_pattern = r'assert\s+([^\n]+)'
            assertions = re.findall(assertion_pattern, rest_content[:1000])  # Limit to first 1000 chars
        elif framework == 'unittest':
            # unittest: self.assert* methods
            assertion_pattern = r'self\.(assert\w+)\('
            assertions = re.findall(assertion_pattern, rest_content[:1000])
        else:
            # Generic
            assertion_pattern = r'(assert\s+[^\n]+|self\.assert\w+)'
            assertions = re.findall(assertion_pattern, rest_content[:1000])

        return assertions[:5]  # Limit to 5 assertions per test

    def _generate_test_description(self, test_name: str) -> str:
        """Generate human-readable description from test name"""
        # test_user_login_with_valid_credentials -> "User login with valid credentials"
        desc = test_name.replace('test_', '').replace('_', ' ').title()
        return desc

    def _extract_usage_examples(self, content: str, scenarios: List[TestScenario]) -> List[str]:
        """Extract concrete usage examples from test code"""
        examples = []

        # Look for patterns like:
        # result = function_name(arg1, arg2)
        # obj = ClassName(params)
        # response = client.post(url, data)

        usage_patterns = [
            r'(\w+)\s*=\s*(\w+)\([^)]*\)',  # result = func(args)
            r'(\w+)\.(\w+)\([^)]*\)',  # obj.method(args)
        ]

        for pattern in usage_patterns:
            matches = re.findall(pattern, content)
            for match in matches[:10]:  # Limit to 10 examples
                if isinstance(match, tuple):
                    example = ' '.join(match)
                    if not any(kw in example.lower() for kw in ['test', 'assert', 'mock', 'patch']):
                        examples.append(example)

        return list(set(examples))[:5]  # Deduplicate and limit to 5

    def _identify_edge_cases(self, scenarios: List[TestScenario]) -> List[str]:
        """Identify edge cases from test scenarios"""
        edge_cases = []

        for scenario in scenarios:
            if scenario.scenario_type in ['edge_case', 'negative']:
                edge_cases.append(f"{scenario.description}: {', '.join(scenario.assertions[:2])}")

        return edge_cases[:5]  # Limit to 5 edge cases

    def enhance_analysis_with_tests(self,
                                    file_summaries: Dict[str, Any],
                                    test_analyses: List[TestFileAnalysis]) -> Dict[str, Any]:
        """
        Enhance regular file summaries with test information.

        Maps test files to their tested modules and adds test insights.
        """
        enhanced_summaries = file_summaries.copy()

        # Build test mapping: module -> tests
        test_mapping: Dict[str, List[TestFileAnalysis]] = {}
        for test_analysis in test_analyses:
            if test_analysis.tested_module:
                if test_analysis.tested_module not in test_mapping:
                    test_mapping[test_analysis.tested_module] = []
                test_mapping[test_analysis.tested_module].append(test_analysis)

        # Enhance summaries with test info
        for file_path, summary in enhanced_summaries.items():
            if not isinstance(summary, dict):
                continue

            # Check if this file has tests
            file_module = self._extract_module_name(file_path)
            if file_module in test_mapping:
                tests = test_mapping[file_module]
                summary['test_info'] = {
                    'has_tests': True,
                    'test_count': sum(t.total_tests for t in tests),
                    'test_files': [t.file_path for t in tests],
                    'usage_examples': [ex for t in tests for ex in t.usage_examples[:2]],
                    'edge_cases': [ec for t in tests for ec in t.edge_cases[:2]]
                }

        return enhanced_summaries

    def _extract_module_name(self, file_path: str) -> str:
        """Extract module name from file path"""
        # src/auth/handlers.py -> auth.handlers
        parts = file_path.replace('.py', '').split('/')
        relevant_parts = [p for p in parts if p not in ['src', 'lib', 'app']]
        return '.'.join(relevant_parts[-2:]) if len(relevant_parts) >= 2 else relevant_parts[-1]
