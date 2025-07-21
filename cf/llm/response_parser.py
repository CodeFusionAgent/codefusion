"""
Unified response parser for LLM outputs.
"""

import json
import re
from typing import Dict, Any, List, Optional


class ResponseParser:
    """Unified parser for LLM responses."""
    
    def __init__(self):
        self.confidence_patterns = [
            r'0\.\d+',      # 0.8
            r'\d+%',        # 80%
            r'\d+/10',      # 8/10
            r'\d+/100'      # 80/100
        ]
    
    def parse_response(self, response: str, expected_schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse LLM response using expected schema.
        
        Args:
            response: Raw LLM response
            expected_schema: Expected response structure with default values
            
        Returns:
            Parsed response with fallback to defaults
        """
        try:
            # Clean response
            cleaned = self._clean_response(response)
            
            # Try JSON parsing first
            if cleaned.strip().startswith('{'):
                try:
                    parsed = json.loads(cleaned)
                    return self._validate_and_fill_defaults(parsed, expected_schema)
                except json.JSONDecodeError:
                    pass
            
            # Fall back to text parsing
            parsed = self._parse_text_response(cleaned, expected_schema)
            return self._validate_and_fill_defaults(parsed, expected_schema)
            
        except Exception as e:
            # Return schema with defaults and error info
            result = {key: default for key, default in expected_schema.items()}
            result['parsing_error'] = str(e)
            result['raw_response'] = response
            return result
    
    def _clean_response(self, response: str) -> str:
        """Clean response by removing markdown and extra whitespace."""
        response = response.strip()
        
        # Remove markdown code blocks
        if response.startswith('```json'):
            response = response[7:]
        if response.startswith('```'):
            response = response[3:]
        if response.endswith('```'):
            response = response[:-3]
        
        return response.strip()
    
    def _parse_text_response(self, response: str, expected_schema: Dict[str, Any]) -> Dict[str, Any]:
        """Parse text response using section headers."""
        result = {}
        lines = response.split('\n')
        
        current_section = None
        current_content = []
        
        for line in lines:
            line = line.strip()
            
            # Check for section headers
            section_found = False
            for key in expected_schema.keys():
                if self._is_section_header(line, key):
                    # Save previous section
                    if current_section:
                        result[current_section] = self._process_section_content(
                            current_content, current_section, expected_schema[current_section]
                        )
                    
                    # Start new section
                    current_section = key
                    current_content = [self._extract_section_content(line, key)]
                    section_found = True
                    break
            
            # Add to current section if not a header
            if not section_found and current_section and line:
                current_content.append(line)
        
        # Process final section
        if current_section and current_content:
            result[current_section] = self._process_section_content(
                current_content, current_section, expected_schema[current_section]
            )
        
        return result
    
    def _is_section_header(self, line: str, key: str) -> bool:
        """Check if line is a section header for the given key."""
        line_lower = line.lower()
        key_lower = key.lower()
        
        # Common header patterns
        patterns = [
            f"1. {key_lower}:",
            f"2. {key_lower}:",
            f"3. {key_lower}:",
            f"4. {key_lower}:",
            f"5. {key_lower}:",
            f"6. {key_lower}:",
            f"{key_lower}:",
            f"**{key_lower}:**",
            f"## {key_lower}",
            f"### {key_lower}"
        ]
        
        return any(pattern in line_lower for pattern in patterns)
    
    def _extract_section_content(self, line: str, key: str) -> str:
        """Extract content from section header line."""
        key_lower = key.lower()
        line_lower = line.lower()
        
        # Find the key and extract content after it
        for pattern in [f"{key_lower}:", f"**{key_lower}:**"]:
            if pattern in line_lower:
                index = line_lower.find(pattern)
                return line[index + len(pattern):].strip()
        
        return ""
    
    def _process_section_content(self, content: List[str], section_key: str, default_value: Any) -> Any:
        """Process section content based on expected type."""
        if not content:
            return default_value
        
        # Join content
        text = '\n'.join(content).strip()
        
        # Handle different types based on default value
        if isinstance(default_value, list):
            return self._parse_list_content(text)
        elif isinstance(default_value, float):
            return self._parse_confidence(text)
        elif isinstance(default_value, dict):
            return self._parse_dict_content(text)
        else:
            return text if text else default_value
    
    def _parse_list_content(self, text: str) -> List[str]:
        """Parse text content into a list."""
        if not text:
            return []
        
        # Split by bullet points or numbers
        items = []
        lines = text.split('\n')
        
        for line in lines:
            line = line.strip()
            if line:
                # Remove bullet points and numbers
                cleaned = re.sub(r'^[-•*\d+.)\s]+', '', line).strip()
                if cleaned:
                    items.append(cleaned)
        
        return items
    
    def _parse_confidence(self, text: str) -> float:
        """Parse confidence value from text."""
        if not text:
            return 0.8
        
        # Look for confidence patterns
        for pattern in self.confidence_patterns:
            matches = re.findall(pattern, text)
            if matches:
                conf_str = matches[0]
                try:
                    if '%' in conf_str:
                        return float(conf_str.replace('%', '')) / 100
                    elif '/' in conf_str:
                        parts = conf_str.split('/')
                        return float(parts[0]) / float(parts[1])
                    else:
                        return float(conf_str)
                except ValueError:
                    continue
        
        return 0.8
    
    def _parse_dict_content(self, text: str) -> Dict[str, Any]:
        """Parse text content into a dictionary."""
        # For now, return simple dict with content
        return {'content': text}
    
    def _validate_and_fill_defaults(self, parsed: Dict[str, Any], expected_schema: Dict[str, Any]) -> Dict[str, Any]:
        """Validate parsed response and fill in missing defaults."""
        result = {}
        
        for key, default_value in expected_schema.items():
            if key in parsed:
                # Validate type
                if type(parsed[key]) == type(default_value):
                    result[key] = parsed[key]
                else:
                    # Try to convert
                    try:
                        if isinstance(default_value, float):
                            result[key] = float(parsed[key])
                        elif isinstance(default_value, int):
                            result[key] = int(parsed[key])
                        elif isinstance(default_value, list) and isinstance(parsed[key], str):
                            result[key] = self._parse_list_content(parsed[key])
                        else:
                            result[key] = parsed[key]
                    except (ValueError, TypeError):
                        result[key] = default_value
            else:
                result[key] = default_value
        
        return result


# Predefined schemas for common response types
REASONING_SCHEMA = {
    'reasoning': '',
    'confidence': 0.8,
    'suggested_actions': [],
    'context_analysis': {}
}

SUMMARY_SCHEMA = {
    'summary': '',
    'key_points': [],
    'confidence': 0.7,
    'content_analysis': {}
}

LIFE_OF_X_SCHEMA = {
    'narrative': '',
    'journey_stages': [],
    'key_components': [],
    'flow_summary': '',
    'code_insights': [],
    'confidence': 0.8
}


# Global parser instance
response_parser = ResponseParser()