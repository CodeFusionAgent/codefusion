"""
LLM-based Analysis Tools for CodeFusion

Provides intelligent code analysis using LLM capabilities.
"""

import json
from typing import Dict, List, Any, Optional


class LLMTools:
    """LLM-powered code analysis tools"""
    
    def __init__(self):
        self.llm_client = None  # Will be injected by the agent
    
    def set_llm_client(self, llm_client):
        """Set the LLM client for making calls"""
        self.llm_client = llm_client
    
    def analyze_code_structure(self, code_content: str, file_path: str = "", focus: str = "") -> Dict[str, Any]:
        """Analyze code architecture and structure using LLM"""
        if not self.llm_client:
            return {'error': 'LLM client not available'}
        
        prompt = f"""Analyze the following code and provide insights about its structure:

File: {file_path}
Focus: {focus or 'general analysis'}

Code:
```
{code_content[:8000]}  # Limit to avoid token limits
```

Please analyze and return JSON with:
- architecture_type: (e.g., "class-based", "functional", "modular")
- complexity_score: (1-10, where 10 is very complex)
- key_components: list of main classes, functions, or modules
- patterns: design patterns identified
- dependencies: external libraries or imports used
- maintainability: assessment of code maintainability
- suggestions: improvement recommendations
"""
        
        system_prompt = "You are a senior code architect. Analyze code structure and provide detailed technical insights in valid JSON format."
        
        try:
            response = self.llm_client.generate(prompt, system_prompt)
            if response.get('success'):
                # Try to parse JSON from response
                content = response.get('content', '')
                if content.startswith('{'):
                    return json.loads(content)
                else:
                    # Extract JSON from markdown if wrapped
                    start = content.find('{')
                    end = content.rfind('}') + 1
                    if start >= 0 and end > start:
                        return json.loads(content[start:end])
            
            return {'error': 'Failed to get valid analysis', 'raw_response': response}
        except Exception as e:
            return {'error': f'Analysis failed: {str(e)}'}
    
    def extract_functions(self, code_content: str, file_path: str = "") -> Dict[str, Any]:
        """Extract function signatures and documentation from code"""
        if not self.llm_client:
            return {'error': 'LLM client not available'}
        
        prompt = f"""Extract all functions from this code and return detailed information:

File: {file_path}
Code:
```
{code_content[:8000]}
```

Return JSON with "functions" array containing:
- name: function name
- signature: full function signature with parameters
- docstring: docstring if present
- parameters: list of parameter names and types
- returns: return type if specified
- line_number: approximate line number
- complexity: estimated complexity (low/medium/high)
- purpose: brief description of what the function does
"""
        
        system_prompt = "You are a code analyzer. Extract function information and return valid JSON."
        
        try:
            response = self.llm_client.generate(prompt, system_prompt)
            if response.get('success'):
                content = response.get('content', '')
                start = content.find('{')
                end = content.rfind('}') + 1
                if start >= 0 and end > start:
                    return json.loads(content[start:end])
            
            return {'error': 'Failed to extract functions', 'raw_response': response}
        except Exception as e:
            return {'error': f'Function extraction failed: {str(e)}'}
    
    def extract_classes(self, code_content: str, file_path: str = "") -> Dict[str, Any]:
        """Extract class definitions and methods from code"""
        if not self.llm_client:
            return {'error': 'LLM client not available'}
        
        prompt = f"""Extract all classes from this code:

File: {file_path}
Code:
```
{code_content[:8000]}
```

Return JSON with "classes" array containing:
- name: class name
- inheritance: parent classes if any
- docstring: class docstring
- methods: array of method info (name, signature, docstring)
- attributes: instance/class attributes
- line_number: approximate line number
- purpose: what the class represents
- design_pattern: if it follows a known pattern
"""
        
        system_prompt = "You are a code analyzer. Extract class information and return valid JSON."
        
        try:
            response = self.llm_client.generate(prompt, system_prompt)
            if response.get('success'):
                content = response.get('content', '')
                start = content.find('{')
                end = content.rfind('}') + 1
                if start >= 0 and end > start:
                    return json.loads(content[start:end])
            
            return {'error': 'Failed to extract classes', 'raw_response': response}
        except Exception as e:
            return {'error': f'Class extraction failed: {str(e)}'}
    
    def detect_patterns(self, code_content: str, file_path: str = "", pattern_types: Optional[List[str]] = None) -> Dict[str, Any]:
        """Detect design and architectural patterns in code"""
        if not self.llm_client:
            return {'error': 'LLM client not available'}
        
        focus_patterns = pattern_types or ["all patterns"]
        
        prompt = f"""Analyze this code for design and architectural patterns:

File: {file_path}
Focus on: {', '.join(focus_patterns)}

Code:
```
{code_content[:8000]}
```

Return JSON with "patterns" array containing:
- pattern_name: e.g., "Singleton", "Factory", "Observer", "MVC"
- confidence: 0.0-1.0 confidence score
- evidence: specific code elements that indicate this pattern
- location: where in the code the pattern appears
- description: how the pattern is implemented
- quality: assessment of pattern implementation (good/fair/poor)

Also include:
- antipatterns: any problematic patterns found
- suggestions: recommendations for pattern improvements
"""
        
        system_prompt = "You are a software architecture expert. Identify design patterns and return valid JSON."
        
        try:
            response = self.llm_client.generate(prompt, system_prompt)
            if response.get('success'):
                content = response.get('content', '')
                start = content.find('{')
                end = content.rfind('}') + 1
                if start >= 0 and end > start:
                    return json.loads(content[start:end])
            
            return {'error': 'Failed to detect patterns', 'raw_response': response}
        except Exception as e:
            return {'error': f'Pattern detection failed: {str(e)}'}
    
    def summarize_code(self, code_content: str, file_path: str = "", summary_type: str = "overview") -> Dict[str, Any]:
        """Generate summary of code functionality and structure"""
        if not self.llm_client:
            return {'error': 'LLM client not available'}
        
        if summary_type == "detailed":
            detail_level = "Provide detailed analysis with code examples and specific technical details."
        elif summary_type == "technical":
            detail_level = "Focus on technical implementation details, algorithms, and architecture."
        else:
            detail_level = "Provide a concise overview suitable for developers."
        
        prompt = f"""Summarize this code file:

File: {file_path}
Summary Type: {summary_type}
{detail_level}

Code:
```
{code_content[:8000]}
```

Return JSON with:
- file_path: the file being analyzed
- summary: main summary text
- purpose: what this code does
- key_features: list of main features/capabilities
- technologies: languages, frameworks, libraries used
- complexity: overall complexity assessment
- entry_points: main functions or classes to start with
- dependencies: what this code depends on
- usage_examples: how to use this code (if applicable)
- maintenance_notes: important notes for maintainers
"""
        
        system_prompt = "You are a code documentation expert. Create clear, informative summaries and return valid JSON."
        
        try:
            response = self.llm_client.generate(prompt, system_prompt)
            if response.get('success'):
                content = response.get('content', '')
                start = content.find('{')
                end = content.rfind('}') + 1
                if start >= 0 and end > start:
                    return json.loads(content[start:end])
            
            return {'error': 'Failed to generate summary', 'raw_response': response}
        except Exception as e:
            return {'error': f'Code summarization failed: {str(e)}'}
    
    def analyze_dependencies(self, code_content: str, file_path: str = "") -> Dict[str, Any]:
        """Analyze code dependencies and imports"""
        if not self.llm_client:
            return {'error': 'LLM client not available'}
        
        prompt = f"""Analyze the dependencies in this code:

File: {file_path}
Code:
```
{code_content[:8000]}
```

Return JSON with:
- imports: list of all imported modules/packages
- local_imports: imports from the same project
- external_imports: third-party dependencies
- stdlib_imports: standard library imports
- dependency_tree: how imports relate to each other
- unused_imports: imports that appear unused
- missing_imports: functionality used but not imported
- recommendations: suggestions for dependency management
"""
        
        system_prompt = "You are a dependency analysis expert. Analyze imports and dependencies thoroughly."
        
        try:
            response = self.llm_client.generate(prompt, system_prompt)
            if response.get('success'):
                content = response.get('content', '')
                start = content.find('{')
                end = content.rfind('}') + 1
                if start >= 0 and end > start:
                    return json.loads(content[start:end])
            
            return {'error': 'Failed to analyze dependencies', 'raw_response': response}
        except Exception as e:
            return {'error': f'Dependency analysis failed: {str(e)}'}
    
    def get_code_metrics(self, code_content: str, file_path: str = "") -> Dict[str, Any]:
        """Calculate various code quality metrics"""
        if not self.llm_client:
            return {'error': 'LLM client not available'}
        
        prompt = f"""Calculate code quality metrics for this code:

File: {file_path}
Code:
```
{code_content[:8000]}
```

Return JSON with metrics:
- lines_of_code: total lines
- lines_of_comments: comment lines
- cyclomatic_complexity: estimated complexity
- maintainability_index: 0-100 score
- code_duplication: estimated duplication level
- test_coverage_estimate: estimated test coverage needed
- technical_debt: areas needing improvement
- code_smells: problematic patterns found
- refactoring_opportunities: specific improvements suggested
- readability_score: 0-10 readability assessment
"""
        
        system_prompt = "You are a code quality expert. Provide accurate metrics and assessments in JSON format."
        
        try:
            response = self.llm_client.generate(prompt, system_prompt)
            if response.get('success'):
                content = response.get('content', '')
                start = content.find('{')
                end = content.rfind('}') + 1
                if start >= 0 and end > start:
                    return json.loads(content[start:end])
            
            return {'error': 'Failed to calculate metrics', 'raw_response': response}
        except Exception as e:
            return {'error': f'Code metrics calculation failed: {str(e)}'}