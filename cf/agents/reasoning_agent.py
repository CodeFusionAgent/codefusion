"""Agentic reasoning framework for detailed question answering."""

import os
import json
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path

try:
    import litellm
    LITELLM_AVAILABLE = True
except ImportError:
    LITELLM_AVAILABLE = False

from ..kb.knowledge_base import CodeEntity
from ..kb.content_analyzer import ContentAnalyzer, AnalyzedAnswer
from ..config import CfConfig


@dataclass
class ReasoningStep:
    """Single step in the reasoning process."""
    question: str
    answer: str
    entities_used: List[str]
    confidence: float
    step_type: str  # "decomposition", "analysis", "synthesis"


@dataclass
class ReasoningResult:
    """Result of the agentic reasoning process."""
    original_question: str
    final_answer: str
    reasoning_steps: List[ReasoningStep]
    entities_consulted: List[CodeEntity]
    confidence: float
    answer_type: str


class ReasoningAgent:
    """Agent that performs multi-step reasoning for detailed question answering."""
    
    def __init__(self, config: CfConfig):
        self.config = config
        self.content_analyzer = ContentAnalyzer()
        self.llm_available = LITELLM_AVAILABLE and config.llm_api_key is not None
        
        if self.llm_available:
            self._setup_llm()
    
    def _setup_llm(self):
        """Setup LLM configuration."""
        if self.config.llm_api_key:
            os.environ["OPENAI_API_KEY"] = self.config.llm_api_key
        
        if self.config.llm_base_url:
            os.environ["OPENAI_BASE_URL"] = self.config.llm_base_url
    
    def reason_about_question(self, question: str, entities: List[CodeEntity], 
                            kb_results: List[str]) -> ReasoningResult:
        """Perform multi-step reasoning about a question."""
        reasoning_steps = []
        entities_consulted = []
        
        # Step 1: Decompose the question
        decomposition_step = self._decompose_question(question, entities)
        reasoning_steps.append(decomposition_step)
        
        # Step 2: Analyze each sub-question
        sub_questions = self._extract_sub_questions(decomposition_step.answer)
        for sub_q in sub_questions:
            analysis_step = self._analyze_sub_question(sub_q, entities, kb_results)
            reasoning_steps.append(analysis_step)
            
            # Track entities used
            for entity_name in analysis_step.entities_used:
                matching_entities = [e for e in entities if e.name == entity_name]
                entities_consulted.extend(matching_entities)
        
        # Step 3: Synthesize comprehensive answer
        synthesis_step = self._synthesize_answer(question, reasoning_steps, entities)
        reasoning_steps.append(synthesis_step)
        
        # Calculate overall confidence
        overall_confidence = sum(step.confidence for step in reasoning_steps) / len(reasoning_steps)
        
        return ReasoningResult(
            original_question=question,
            final_answer=synthesis_step.answer,
            reasoning_steps=reasoning_steps,
            entities_consulted=entities_consulted,
            confidence=overall_confidence,
            answer_type=self._classify_answer_type(question)
        )
    
    def _decompose_question(self, question: str, entities: List[CodeEntity]) -> ReasoningStep:
        """Break down complex questions into sub-questions."""
        if self.llm_available:
            return self._llm_decompose_question(question, entities)
        else:
            return self._rule_based_decompose_question(question, entities)
    
    def _llm_decompose_question(self, question: str, entities: List[CodeEntity]) -> ReasoningStep:
        """Use LLM to decompose question into sub-questions."""
        entity_context = self._build_entity_context(entities[:10])  # Limit for token efficiency
        
        prompt = f"""Given this question about a codebase: "{question}"

And these relevant code entities:
{entity_context}

Break down this question into 3-5 specific sub-questions that need to be answered to provide a comprehensive response. Focus on:
1. Installation/setup procedures
2. Configuration requirements
3. Code examples and usage
4. Troubleshooting common issues
5. Best practices

Return the sub-questions as a JSON array of strings."""
        
        try:
            response = litellm.completion(
                model=self.config.llm_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1
            )
            
            sub_questions_json = response.choices[0].message.content
            sub_questions = json.loads(sub_questions_json)
            
            return ReasoningStep(
                question="How should I break down this question?",
                answer=json.dumps(sub_questions),
                entities_used=[e.name for e in entities[:10]],
                confidence=0.8,
                step_type="decomposition"
            )
        except Exception as e:
            print(f"LLM decomposition failed: {e}")
            return self._rule_based_decompose_question(question, entities)
    
    def _rule_based_decompose_question(self, question: str, entities: List[CodeEntity]) -> ReasoningStep:
        """Rule-based question decomposition fallback."""
        sub_questions = []
        question_lower = question.lower()
        
        # Standard decomposition patterns
        if any(word in question_lower for word in ['install', 'setup', 'configure']):
            sub_questions.extend([
                "What are the installation requirements?",
                "How do I set up the environment?",
                "What configuration is needed?"
            ])
        
        if any(word in question_lower for word in ['test', 'testing']):
            sub_questions.extend([
                "What testing frameworks are used?",
                "How do I run the tests?",
                "What do the test results mean?"
            ])
        
        if any(word in question_lower for word in ['usage', 'example', 'how']):
            sub_questions.extend([
                "What are the main usage patterns?",
                "Can you provide code examples?",
                "What are common use cases?"
            ])
        
        if any(word in question_lower for word in ['error', 'issue', 'problem']):
            sub_questions.extend([
                "What are common issues?",
                "How do I troubleshoot problems?",
                "What are the error patterns?"
            ])
        
        # Always add these general questions
        sub_questions.extend([
            "What are the key components involved?",
            "What are the best practices?"
        ])
        
        return ReasoningStep(
            question="How should I break down this question?",
            answer=json.dumps(sub_questions[:5]),  # Limit to 5 sub-questions
            entities_used=[e.name for e in entities[:5]],
            confidence=0.6,
            step_type="decomposition"
        )
    
    def _extract_sub_questions(self, decomposition_answer: str) -> List[str]:
        """Extract sub-questions from decomposition step."""
        try:
            return json.loads(decomposition_answer)
        except json.JSONDecodeError:
            # Fallback parsing
            lines = decomposition_answer.split('\n')
            return [line.strip('- ').strip() for line in lines if line.strip()]
    
    def _analyze_sub_question(self, sub_question: str, entities: List[CodeEntity], 
                            kb_results: List[str]) -> ReasoningStep:
        """Analyze a single sub-question."""
        # Use content analyzer for detailed analysis
        analyzed_answer = self.content_analyzer.analyze_question(sub_question, entities)
        
        # Enhance with KB results
        enhanced_answer = self._enhance_with_kb_results(analyzed_answer.answer, kb_results)
        
        return ReasoningStep(
            question=sub_question,
            answer=enhanced_answer,
            entities_used=[e.name for e in analyzed_answer.sources],
            confidence=analyzed_answer.confidence,
            step_type="analysis"
        )
    
    def _enhance_with_kb_results(self, base_answer: str, kb_results: List[str]) -> str:
        """Enhance answer with knowledge base results."""
        if not kb_results:
            return base_answer
        
        relevant_snippets = []
        for result in kb_results[:3]:  # Limit to top 3 results
            if len(result) > 100:  # Only include substantial snippets
                relevant_snippets.append(result[:500])  # Truncate for readability
        
        if relevant_snippets:
            enhanced = f"{base_answer}\n\n📖 **Relevant Code References:**\n"
            for i, snippet in enumerate(relevant_snippets, 1):
                enhanced += f"\n{i}. ```\n{snippet}\n```\n"
            return enhanced
        
        return base_answer
    
    def _synthesize_answer(self, original_question: str, reasoning_steps: List[ReasoningStep], 
                         entities: List[CodeEntity]) -> ReasoningStep:
        """Synthesize a comprehensive final answer."""
        if self.llm_available:
            return self._llm_synthesize_answer(original_question, reasoning_steps, entities)
        else:
            return self._rule_based_synthesize_answer(original_question, reasoning_steps, entities)
    
    def _llm_synthesize_answer(self, original_question: str, reasoning_steps: List[ReasoningStep], 
                             entities: List[CodeEntity]) -> ReasoningStep:
        """Use LLM to synthesize comprehensive answer."""
        analysis_context = "\n\n".join([
            f"Q: {step.question}\nA: {step.answer}"
            for step in reasoning_steps if step.step_type == "analysis"
        ])
        
        prompt = f"""Original question: "{original_question}"

Based on this analysis of the codebase:
{analysis_context}

Provide a comprehensive, detailed answer that includes:
1. Step-by-step procedures (if applicable)
2. Configuration details with examples
3. Code snippets with context
4. Common troubleshooting tips
5. Best practices and recommendations

Format the answer with clear sections and examples."""
        
        try:
            response = litellm.completion(
                model=self.config.llm_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2
            )
            
            synthesized_answer = response.choices[0].message.content
            
            return ReasoningStep(
                question=original_question,
                answer=synthesized_answer,
                entities_used=[e.name for e in entities[:10]],
                confidence=0.9,
                step_type="synthesis"
            )
        except Exception as e:
            print(f"LLM synthesis failed: {e}")
            return self._rule_based_synthesize_answer(original_question, reasoning_steps, entities)
    
    def _rule_based_synthesize_answer(self, original_question: str, reasoning_steps: List[ReasoningStep], 
                                    entities: List[CodeEntity]) -> ReasoningStep:
        """Rule-based answer synthesis fallback."""
        analysis_steps = [step for step in reasoning_steps if step.step_type == "analysis"]
        
        synthesized_answer = f"## {original_question}\n\n"
        
        # Group answers by type
        setup_answers = []
        usage_answers = []
        troubleshooting_answers = []
        other_answers = []
        
        for step in analysis_steps:
            if any(word in step.question.lower() for word in ['install', 'setup', 'configure']):
                setup_answers.append(step.answer)
            elif any(word in step.question.lower() for word in ['usage', 'example', 'how']):
                usage_answers.append(step.answer)
            elif any(word in step.question.lower() for word in ['error', 'issue', 'problem']):
                troubleshooting_answers.append(step.answer)
            else:
                other_answers.append(step.answer)
        
        # Build comprehensive answer
        if setup_answers:
            synthesized_answer += "### 🚀 Setup and Installation\n"
            synthesized_answer += "\n".join(setup_answers) + "\n\n"
        
        if usage_answers:
            synthesized_answer += "### 💡 Usage and Examples\n"
            synthesized_answer += "\n".join(usage_answers) + "\n\n"
        
        if troubleshooting_answers:
            synthesized_answer += "### 🔧 Troubleshooting\n"
            synthesized_answer += "\n".join(troubleshooting_answers) + "\n\n"
        
        if other_answers:
            synthesized_answer += "### 📚 Additional Information\n"
            synthesized_answer += "\n".join(other_answers) + "\n\n"
        
        return ReasoningStep(
            question=original_question,
            answer=synthesized_answer,
            entities_used=[e.name for e in entities[:10]],
            confidence=0.7,
            step_type="synthesis"
        )
    
    def _build_entity_context(self, entities: List[CodeEntity]) -> str:
        """Build context string from entities."""
        context_parts = []
        for entity in entities:
            context_parts.append(f"- {entity.name} ({entity.type}): {entity.metadata.get('description', 'No description')}")
        return "\n".join(context_parts)
    
    def _classify_answer_type(self, question: str) -> str:
        """Classify the type of answer needed."""
        question_lower = question.lower()
        
        if any(word in question_lower for word in ['install', 'setup']):
            return "installation"
        elif any(word in question_lower for word in ['test', 'testing']):
            return "testing"
        elif any(word in question_lower for word in ['configure', 'config']):
            return "configuration"
        elif any(word in question_lower for word in ['usage', 'example']):
            return "usage"
        elif any(word in question_lower for word in ['error', 'issue']):
            return "troubleshooting"
        else:
            return "general"
