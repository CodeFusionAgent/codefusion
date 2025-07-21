"""
Interactive Session Manager for CodeFusion

Manages continuous exploration sessions with memory persistence, context building,
and enhanced question handling capabilities.
"""

import json
import re
import time
import os
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta

from cf.config import CfConfig
from cf.agents.react_supervisor_agent import ReActSupervisorAgent
from cf.aci.repo import LocalCodeRepo
from cf.utils.logging_utils import info_log, progress_log, error_log, agent_log
from cf.tools import display_life_of_x_narrative, should_consolidate_multi_agent_results, generate_llm_driven_narrative, detect_response_format, display_comparison_analysis
from cf.llm.real_llm import get_real_llm
from cf.agents.web_search_agent import WebSearchAgent


@dataclass
class SessionMemory:
    """Represents a single exploration memory entry."""
    timestamp: str
    question: str
    answer_summary: str
    key_findings: List[str]
    components_discovered: List[str]
    code_examples: List[Dict[str, Any]]
    web_search_results: List[Dict[str, Any]]
    confidence: float
    session_id: str


@dataclass
class SessionContext:
    """Represents the current session context."""
    repository_path: str
    session_id: str
    started_at: str
    total_questions: int
    accumulated_knowledge: Dict[str, Any]
    conversation_history: List[Dict[str, Any]]
    discovered_components: Dict[str, Any]
    technology_insights: Dict[str, Any]


class InteractiveSessionManager:
    """
    Manages interactive exploration sessions with memory persistence.
    
    Features:
    - Continuous question-answer loops
    - Memory persistence across sessions
    - Context building and accumulation
    - Web search integration
    - Enhanced caching and learning
    """
    
    def __init__(self, repo_path: str, config: CfConfig, session_dir: Optional[str] = None, resume_session_id: Optional[str] = None):
        self.repo_path = Path(repo_path)
        self.config = config
        self.session_dir = Path(session_dir) if session_dir else self.repo_path / ".codefusion_sessions"
        self.session_dir.mkdir(exist_ok=True)
        
        # Session state
        if resume_session_id:
            self.session_id = resume_session_id
            self.session_context = self._load_session_context(resume_session_id)
        else:
            self.session_id = self._generate_session_id()
            self.session_context = self._initialize_session_context()
        self.memories: List[SessionMemory] = []
        
        # Components
        self.code_repo = LocalCodeRepo(str(self.repo_path))
        self.supervisor = ReActSupervisorAgent(self.code_repo, config)
        
        # Load existing memories
        self._load_session_memories()
        
        info_log(f"🎯 Interactive session initialized: {self.session_id}")
        info_log(f"📁 Repository: {self.repo_path.name}")
        info_log(f"💾 Session directory: {self.session_dir}")
    
    def start_interactive_loop(self):
        """Start the interactive exploration loop."""
        info_log("\n🚀 CodeFusion Interactive Session")
        info_log("=" * 50)
        info_log("Ask questions about the codebase. Type 'exit', 'quit', or 'help' for assistance.")
        info_log(f"📁 Exploring: {self.repo_path.name}")
        
        # Show previous session context if available
        if self.memories:
            info_log(f"\n💡 Previous explorations: {len(self.memories)} questions answered")
            info_log("📚 Building on accumulated knowledge...")
        
        info_log("\n" + "-" * 50)
        
        try:
            while True:
                # Get user input
                question = self._get_user_input()
                
                if question.lower() in ['exit', 'quit', 'q']:
                    self._handle_session_exit()
                    break
                elif question.lower() in ['help', 'h', '?']:
                    self._show_help()
                    continue
                elif question.lower() in ['history', 'hist']:
                    self._show_session_history()
                    continue
                elif question.lower() in ['summary', 'sum']:
                    self._show_session_summary()
                    continue
                elif question.lower().startswith('search '):
                    search_query = question[7:].strip()
                    self._handle_web_search(search_query)
                    continue
                elif not question.strip():
                    continue
                
                # Process the question
                self._process_question(question)
                
        except KeyboardInterrupt:
            info_log("\n\n🔄 Session interrupted by user")
            self._handle_session_exit()
        except Exception as e:
            error_log(f"❌ Session error: {e}")
            self._handle_session_exit()
    
    def _get_user_input(self) -> str:
        """Get user input with prompt."""
        try:
            return input(f"\n🔍 Question ({self.session_context.total_questions + 1}): ").strip()
        except EOFError:
            return "exit"
    
    def _process_question(self, question: str):
        """Process a user question with context building."""
        start_time = time.time()
        
        info_log(f"\n📝 Processing: {question}")
        progress_log("🧠 Analyzing question and building context...")
        
        # Enhance question with context
        enhanced_question = self._enhance_question_with_context(question)
        
        # Check if multi-agent coordination is needed
        should_coordinate_agents = should_consolidate_multi_agent_results(question)
        
        try:
            if should_coordinate_agents:
                progress_log("🤖 Coordinating multiple specialized agents...")
                narrative_result = self._coordinate_multi_agent_analysis(enhanced_question, question)
            else:
                progress_log("🤖 Generating comprehensive analysis...")
                narrative_result = self.supervisor.generate_life_of_x_narrative(enhanced_question)
            
            # Display the enhanced narrative
            self._display_response(narrative_result, question)
            
            # Extract and store memory
            memory = self._extract_memory_from_response(question, narrative_result)
            self.memories.append(memory)
            
            # Update session context
            self._update_session_context(question, narrative_result)
            
            # Save session state
            self._save_session_state()
            
            # Show session stats
            duration = time.time() - start_time
            agents_used = 3 if should_coordinate_agents else 1  # Track actual agents used
            self._show_question_stats(duration, agents_used)
            
        except Exception as e:
            error_log(f"❌ Error processing question: {e}")
            # Fallback to basic exploration
            self._handle_fallback_exploration(question)
    
    def _coordinate_multi_agent_analysis(self, enhanced_question: str, original_question: str) -> Dict[str, Any]:
        """
        Coordinate multiple agents and consolidate their results using LLM.
        
        Args:
            enhanced_question: Question with context
            original_question: Original user question
            
        Returns:
            Consolidated narrative result
        """
        progress_log("🔍 Running code analysis agent...")
        
        # Run code analysis agent
        try:
            code_results = self.supervisor.explore_repository(goal=enhanced_question, focus="code")
            code_agent_results = self.supervisor.get_agent_results()
        except Exception as e:
            error_log(f"⚠️  Code analysis failed: {e}")
            code_results = {}
            code_agent_results = {}
        
        progress_log("📚 Running documentation agent...")
        
        # Run documentation analysis
        try:
            docs_results = self.supervisor.explore_repository(goal=enhanced_question, focus="docs")
            docs_agent_results = self.supervisor.get_agent_results()
        except Exception as e:
            error_log(f"⚠️  Documentation analysis failed: {e}")
            docs_results = {}
            docs_agent_results = {}
        
        progress_log("🌐 Running web search agent...")
        
        # Run web search using dedicated agent
        try:
            web_search_agent = WebSearchAgent(self.code_repo, self.config)
            web_search_result = web_search_agent.search_for_question(original_question)
            web_results = {
                'insights': web_search_result.get('insights', []),
                'results': web_search_result.get('results', []),
                'success': web_search_result.get('success', False)
            }
        except Exception as e:
            error_log(f"⚠️  Web search failed: {e}")
            web_results = {'insights': [], 'results': [], 'success': False}
        
        progress_log("🤖 Consolidating results with LLM...")
        
        # Use LLM to consolidate all results
        try:
            consolidated_result = generate_llm_driven_narrative(
                original_question,
                code_agent_results,
                docs_agent_results, 
                web_results
            )
            
            # Add web search insights to the result
            if web_results.get('insights'):
                consolidated_result['web_search_insights'] = web_results['insights']
            
            return consolidated_result
            
        except Exception as e:
            error_log(f"❌ LLM consolidation failed: {e}")
            # Fallback to supervisor narrative generation
            return self.supervisor.generate_life_of_x_narrative(enhanced_question)
    
    def _enhance_question_with_context(self, question: str) -> str:
        """Enhance the question with accumulated context."""
        context_parts = [question]
        
        # Add context from previous explorations
        if self.memories:
            recent_findings = []
            for memory in self.memories[-3:]:  # Last 3 questions
                # Ensure key_findings are strings
                for finding in memory.key_findings[:2]:
                    if isinstance(finding, str):
                        recent_findings.append(finding)
                    else:
                        recent_findings.append(str(finding))
            
            if recent_findings:
                context_parts.append(f"Context from previous explorations: {'; '.join(recent_findings)}")
        
        # Add discovered components context
        if self.session_context.discovered_components:
            components = list(self.session_context.discovered_components.keys())[:5]
            # Ensure components are strings
            string_components = [str(comp) for comp in components]
            if string_components:
                context_parts.append(f"Known components: {', '.join(string_components)}")
        
        # Add instructions for better code analysis (generic for any repository)
        context_parts.append("IMPORTANT: Find and analyze the actual source code files related to this question. Read the code, extract classes and methods, show file paths, and provide code samples. Don't give generic explanations - analyze the real implementation in this repository.")
        
        return ". ".join(context_parts)
    
    def _display_response(self, narrative_result: Dict[str, Any], original_question: str):
        """Display the enhanced response with integrated web search."""
        info_log("\n" + "=" * 60)
        
        # Ensure web search insights are properly integrated
        if narrative_result.get('web_search_insights'):
            progress_log(f"✅ Integrated {len(narrative_result['web_search_insights'])} web insights into narrative")
        
        # Use appropriate display format based on question type
        response_format = detect_response_format(original_question)
        if response_format == "comparison":
            display_comparison_analysis(narrative_result, original_question)
        else:
            display_life_of_x_narrative(narrative_result, original_question)
    
    def _perform_automatic_web_search(self, question: str, narrative_result: Dict[str, Any]):
        """Perform automatic web search to enhance the response."""
        try:
            real_llm = get_real_llm()
            if not real_llm or not real_llm.client:
                return  # Skip if LLM not available
            
            # Use LLM to craft search queries based on the question and response
            search_queries = self._craft_search_queries_with_llm(question, narrative_result)
            
            if search_queries:
                info_log(f"\n🌐 Searching Web for Additional Information...")
                progress_log(f"Generated {len(search_queries)} search queries")
                
                search_tool = WebSearchTool(max_results=3)
                all_results = []
                
                for query in search_queries[:2]:  # Limit to 2 searches
                    progress_log(f"🔍 Searching: {query}")
                    results = search_tool.search(query, filter_keywords=['docs', 'documentation', 'tutorial'])
                    
                    progress_log(f"Search results: success={results.get('success')}, count={len(results.get('results', []))}")
                    
                    if results['success'] and results['results']:
                        all_results.extend(results['results'])
                
                # If no results from primary search, try LLM-powered fallback
                if not all_results:
                    progress_log("🤖 Using LLM to generate documentation suggestions...")
                    llm_results = self._generate_llm_documentation_suggestions(search_queries[0] if search_queries else question)
                    if llm_results:
                        all_results.extend(llm_results)
                
                if all_results:
                    self._display_web_search_results(all_results[:5])  # Top 5 results
                else:
                    info_log("🔍 No relevant web results found for this query")
                    
        except Exception as e:
            # Log web search errors for debugging
            error_log(f"❌ Web search failed: {e}")
            info_log(f"\n⚠️  Web search temporarily unavailable: {str(e)}")
    
    
    
    
    
    
    
    def _display_web_search_results(self, results: List[Dict[str, Any]]):
        """Display web search results in a clean format."""
        info_log("\n📚 Relevant Documentation Found:")
        info_log("-" * 40)
        
        for i, result in enumerate(results, 1):
            title = result.get('title', 'Unknown')
            snippet = result.get('snippet', '')[:100]
            url = result.get('url', '')
            source = result.get('source', 'Web')
            
            info_log(f"{i}. {title}")
            if snippet:
                info_log(f"   📄 {snippet}...")
            if url:
                info_log(f"   🔗 {url}")
            info_log("")
        
        info_log("💡 Use these resources for deeper understanding!")
    
    
    def _extract_memory_from_response(self, question: str, response: Dict[str, Any]) -> SessionMemory:
        """Extract memory from a response."""
        key_findings = []
        components = []
        code_examples = []
        web_results = []
        
        # Extract key findings
        if response.get("key_components"):
            # Ensure components are strings
            raw_components = response["key_components"][:5]
            for comp in raw_components:
                if isinstance(comp, dict):
                    # Extract component name from dict
                    components.append(comp.get('component', comp.get('name', str(comp))))
                elif isinstance(comp, str):
                    components.append(comp)
                else:
                    components.append(str(comp))
        
        if response.get("code_insights"):
            # Ensure code insights are strings
            raw_insights = response["code_insights"][:3]
            for insight in raw_insights:
                if isinstance(insight, str):
                    key_findings.append(insight)
                else:
                    key_findings.append(str(insight))
        
        # Extract journey stages as findings (ensure strings)
        if response.get("journey_stages"):
            raw_stages = response["journey_stages"][:2]
            for stage in raw_stages:
                if isinstance(stage, dict):
                    # Extract stage description or name
                    stage_text = stage.get('description', stage.get('stage', str(stage)))
                    key_findings.append(stage_text)
                elif isinstance(stage, str):
                    key_findings.append(stage)
                else:
                    key_findings.append(str(stage))
        
        # Create memory entry
        return SessionMemory(
            timestamp=datetime.now().isoformat(),
            question=question,
            answer_summary=response.get("narrative", "Analysis completed")[:200],
            key_findings=key_findings,
            components_discovered=components,
            code_examples=code_examples,
            web_search_results=web_results,
            confidence=response.get("confidence", 0.7),
            session_id=self.session_id
        )
    
    def _update_session_context(self, question: str, response: Dict[str, Any]):
        """Update the session context with new information."""
        self.session_context.total_questions += 1
        
        # Add to conversation history
        self.session_context.conversation_history.append({
            "question": question,
            "timestamp": datetime.now().isoformat(),
            "confidence": response.get("confidence", 0.7)
        })
        
        # Update discovered components
        if response.get("key_components"):
            for component in response["key_components"]:
                if isinstance(component, str):
                    self.session_context.discovered_components[component] = {
                        "discovered_in_question": self.session_context.total_questions,
                        "context": question
                    }
        
        # Update technology insights using web search agent
        try:
            web_search_agent = WebSearchAgent(self.code_repo, self.config)
            tech_keywords = web_search_agent._extract_tech_keywords(question)
            for tech in tech_keywords:
                if tech not in self.session_context.technology_insights:
                    self.session_context.technology_insights[tech] = []
                
                insight = f"Explored in Q{self.session_context.total_questions}: {question[:50]}"
                self.session_context.technology_insights[tech].append(insight)
        except Exception:
            # Skip tech insights if web search agent fails
            pass
    
    def _handle_web_search(self, search_query: str):
        """Handle web search commands using WebSearchAgent."""
        try:
            progress_log(f"🌐 Searching web for: {search_query}")
            
            web_search_agent = WebSearchAgent(self.code_repo, self.config)
            results = web_search_agent.search_for_question(search_query)
            
            if results["success"]:
                info_log("\n🌐 Web Search Results:")
                info_log("=" * 40)
                
                for i, result in enumerate(results["results"], 1):
                    info_log(f"{i}. {result['title']}")
                    info_log(f"   📄 {result['snippet'][:100]}...")
                    if result.get('url'):
                        info_log(f"   🔗 {result['url']}")
                    info_log("")
                
                info_log("💡 Tip: Use these results to formulate more detailed questions!")
            else:
                error_log(f"❌ Web search failed: {results.get('error', 'Unknown error')}")
                
        except Exception as e:
            error_log(f"❌ Web search error: {e}")
    
    def _show_help(self):
        """Show help information."""
        info_log("\n📖 CodeFusion Interactive Help")
        info_log("=" * 40)
        info_log("Commands:")
        info_log("  • Ask any question about the codebase")
        info_log("  • help, h, ? - Show this help")
        info_log("  • history, hist - Show question history")
        info_log("  • summary, sum - Show session summary")
        info_log("  • search <query> - Search web for documentation")
        info_log("  • exit, quit, q - End session")
        info_log("\nExample questions:")
        info_log("  • How does authentication work?")
        info_log("  • What happens when a user logs in?")
        info_log("  • Explain the relationship between FastAPI and Starlette")
        info_log("  • How is data validation handled?")
    
    def _show_session_history(self):
        """Show session history."""
        info_log("\n📚 Session History")
        info_log("=" * 30)
        
        if not self.memories:
            info_log("No questions asked yet in this session.")
            return
        
        for i, memory in enumerate(self.memories, 1):
            info_log(f"{i}. {memory.question}")
            if memory.key_findings:
                info_log(f"   💡 Key finding: {memory.key_findings[0]}")
            info_log("")
    
    def _show_session_summary(self):
        """Show session summary."""
        info_log("\n📊 Session Summary")
        info_log("=" * 30)
        info_log(f"Questions asked: {len(self.memories)}")
        info_log(f"Components discovered: {len(self.session_context.discovered_components)}")
        info_log(f"Technologies explored: {len(self.session_context.technology_insights)}")
        
        if self.session_context.discovered_components:
            info_log("\n🔧 Key Components:")
            for component in list(self.session_context.discovered_components.keys())[:5]:
                info_log(f"   • {component}")
        
        if self.session_context.technology_insights:
            info_log("\n💻 Technologies:")
            for tech in self.session_context.technology_insights.keys():
                info_log(f"   • {tech}")
    
    def _show_question_stats(self, duration: float, agents_used: int = None):
        """Show stats for the last question."""
        if agents_used is None:
            agent_results = self.supervisor.get_agent_results()
            agents_used = len(agent_results)
        
        stats = []
        stats.append(f"⏱️  Response time: {duration:.1f}s")
        stats.append(f"🤖 Agents used: {agents_used}")
        
        # Show cache performance if available  
        if agents_used is None:
            agent_results = self.supervisor.get_agent_results()
            total_cache_hits = sum(
                result.get('cache_hits', 0) for result in agent_results.values()
                if isinstance(result, dict)
            )
            if total_cache_hits > 0:
                stats.append(f"💾 Cache hits: {total_cache_hits}")
        
        info_log(f"\n📈 {' | '.join(stats)}")
    
    def _handle_fallback_exploration(self, question: str):
        """Handle fallback exploration when narrative generation fails."""
        try:
            progress_log("🔄 Using fallback exploration...")
            result = self.supervisor.explore_repository(goal=question, focus="all")
            agent_results = self.supervisor.get_agent_results()
            
            info_log("\n📊 Exploration Results:")
            for agent_name, agent_result in agent_results.items():
                if isinstance(agent_result, dict) and agent_result.get('summary'):
                    info_log(f"🤖 {agent_name.title()}: {agent_result['summary'][:100]}...")
                    
        except Exception as e:
            error_log(f"❌ Fallback exploration failed: {e}")
            info_log("💡 Try rephrasing your question or check the repository path.")
    
    def _generate_session_id(self) -> str:
        """Generate a unique session ID."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"session_{timestamp}"
    
    def _initialize_session_context(self) -> SessionContext:
        """Initialize session context."""
        return SessionContext(
            repository_path=str(self.repo_path),
            session_id=self.session_id,
            started_at=datetime.now().isoformat(),
            total_questions=0,
            accumulated_knowledge={},
            conversation_history=[],
            discovered_components={},
            technology_insights={}
        )
    
    def _load_session_context(self, session_id: str) -> SessionContext:
        """Load existing session context."""
        context_file = self.session_dir / f"context_{session_id}.json"
        
        if context_file.exists():
            try:
                with open(context_file, 'r') as f:
                    context_data = json.load(f)
                return SessionContext(**context_data)
            except Exception as e:
                error_log(f"❌ Failed to load session context: {e}")
        
        # Fallback to new context if loading fails
        return self._initialize_session_context()
    
    @classmethod
    def list_sessions(cls, repo_path: str, session_dir: Optional[str] = None) -> List[Dict[str, Any]]:
        """List available sessions for a repository."""
        repo_path_obj = Path(repo_path)
        session_dir_obj = Path(session_dir) if session_dir else repo_path_obj / ".codefusion_sessions"
        
        if not session_dir_obj.exists():
            return []
        
        sessions = []
        for context_file in session_dir_obj.glob("context_session_*.json"):
            try:
                with open(context_file, 'r') as f:
                    context_data = json.load(f)
                
                session_info = {
                    'session_id': context_data['session_id'],
                    'started_at': context_data['started_at'],
                    'total_questions': context_data['total_questions'],
                    'discovered_components': len(context_data.get('discovered_components', {})),
                    'technologies': len(context_data.get('technology_insights', {}))
                }
                sessions.append(session_info)
            except Exception as e:
                continue
        
        # Sort by start time (most recent first)
        sessions.sort(key=lambda x: x['started_at'], reverse=True)
        return sessions
    
    def _load_session_memories(self):
        """Load existing session memories from disk."""
        memories_file = self.session_dir / "memories.json"
        
        if memories_file.exists():
            try:
                with open(memories_file, 'r') as f:
                    memories_data = json.load(f)
                
                # Load recent memories (last 10)
                for memory_data in memories_data[-10:]:
                    memory = SessionMemory(**memory_data)
                    self.memories.append(memory)
                
                agent_log(f"📚 Loaded {len(self.memories)} previous memories")
                
            except Exception as e:
                error_log(f"❌ Failed to load memories: {e}")
    
    def _save_session_state(self):
        """Save current session state to disk."""
        try:
            # Save memories
            memories_file = self.session_dir / "memories.json"
            memories_data = [asdict(memory) for memory in self.memories]
            
            with open(memories_file, 'w') as f:
                json.dump(memories_data, f, indent=2)
            
            # Save session context
            context_file = self.session_dir / f"context_{self.session_id}.json"
            with open(context_file, 'w') as f:
                json.dump(asdict(self.session_context), f, indent=2)
                
        except Exception as e:
            error_log(f"❌ Failed to save session state: {e}")
    
    def _handle_session_exit(self):
        """Handle session exit."""
        self._save_session_state()
        
        info_log("\n👋 Session Summary:")
        info_log(f"   📝 Questions answered: {len(self.memories)}")
        info_log(f"   🔧 Components discovered: {len(self.session_context.discovered_components)}")
        info_log(f"   💾 Session saved to: {self.session_dir}")
        info_log("\n✨ Thank you for using CodeFusion!")
        info_log("💡 Your exploration history is saved for future sessions.")