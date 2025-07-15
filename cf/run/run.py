"""Command Line Interface for CodeFusion V0.01."""

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..config import CfConfig
from ..aci.repo import LocalCodeRepo, CodeRepo
from ..aci.environment_manager import EnvironmentManager
from ..kb.knowledge_base import create_knowledge_base, CodeKB
from ..indexer.code_indexer import CodeIndexer
from ..llm.llm_model import create_llm_model, LlmTracer, CodeAnalysisLlm


class CodeFusionCLI:
    """Main CLI class for CodeFusion."""
    
    def __init__(self):
        self.config: Optional[CfConfig] = None
        self.repo: Optional[CodeRepo] = None
        self.kb: Optional[CodeKB] = None
        self.indexer: Optional[CodeIndexer] = None
        self.llm_analyzer: Optional[CodeAnalysisLlm] = None
    
    def run(self):
        """Main entry point for the CLI."""
        parser = self.create_parser()
        args = parser.parse_args()
        
        if hasattr(args, 'func'):
            try:
                args.func(args)
            except Exception as e:
                print(f"Error: {e}", file=sys.stderr)
                sys.exit(1)
        else:
            parser.print_help()
    
    def create_parser(self):
        """Create the command line argument parser."""
        parser = argparse.ArgumentParser(
            description="CodeFusion - Code Understanding Tool",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  cf index /path/to/repo                    # Index a repository
  cf query "What does this code do?"       # Ask about the code
  cf explore /path/to/repo                 # Full exploration workflow
  cf stats                                 # Show knowledge base stats
            """
        )
        
        parser.add_argument(
            "--config", "-c",
            type=str,
            default="config/default/config.yaml",
            help="Configuration file path"
        )
        
        parser.add_argument(
            "--verbose", "-v",
            action="store_true",
            help="Enable verbose output"
        )
        
        subparsers = parser.add_subparsers(title="commands", dest="command")
        
        # Index command
        index_parser = subparsers.add_parser("index", help="Index a repository")
        index_parser.add_argument("repo_path", help="Path to repository to index")
        index_parser.add_argument("--strategy", choices=["react", "plan_act", "sense_act"], 
                                default="react", help="Exploration strategy")
        index_parser.set_defaults(func=self.cmd_index)
        
        # Query command
        query_parser = subparsers.add_parser("query", help="Query the knowledge base")
        query_parser.add_argument("question", help="Question to ask about the code")
        query_parser.add_argument("--repo-path", help="Repository path (if not using saved KB)")
        query_parser.add_argument("--strategy", choices=["react", "plan_act", "sense_act"],
                                default="react", help="Exploration strategy")
        query_parser.set_defaults(func=self.cmd_query)
        
        # Explore command (index + basic query)
        explore_parser = subparsers.add_parser("explore", help="Full exploration workflow")
        explore_parser.add_argument("repo_path", help="Path to repository to explore")
        explore_parser.add_argument("--strategy", choices=["react", "plan_act", "sense_act"],
                                  default="react", help="Exploration strategy")
        explore_parser.set_defaults(func=self.cmd_explore)
        
        # Stats command
        stats_parser = subparsers.add_parser("stats", help="Show knowledge base statistics")
        stats_parser.add_argument("--repo-path", help="Repository path")
        stats_parser.set_defaults(func=self.cmd_stats)
        
        # Demo command
        demo_parser = subparsers.add_parser("demo", help="Run V0.01 demo")
        demo_parser.add_argument("repo_path", help="Path to repository for demo")
        demo_parser.set_defaults(func=self.cmd_demo)
        
        return parser
    
    def load_config(self, config_path: str):
        """Load configuration."""
        try:
            self.config = CfConfig.from_file(config_path)
            if self.config:
                self.config.validate()
        except FileNotFoundError:
            # Use default config if file not found
            self.config = CfConfig()
            print(f"Warning: Config file {config_path} not found, using defaults")
        except Exception as e:
            print(f"Error loading config: {e}")
            self.config = CfConfig()
    
    def setup_components(self, repo_path: str):
        """Setup core components."""
        if not self.config:
            raise Exception("Configuration not loaded")
        
        # Setup repository
        self.repo = LocalCodeRepo(repo_path)
        self.config.repo_path = repo_path
        
        # Create timestamped artifact directory
        self.config.kb_path = self._create_artifact_directory(repo_path, self.config.kb_path)
        
        # Use vector database for artifact directories
        self.config.kb_type = "vector"
        if not hasattr(self.config, 'embedding_model'):
            self.config.embedding_model = "BAAI/bge-small-en-v1.5"
        
        # Setup knowledge base
        self.kb = create_knowledge_base(
            kb_type=self.config.kb_type,
            storage_path=self.config.kb_path,
            embedding_model=self.config.embedding_model
        )
        
        # Setup indexer
        self.indexer = CodeIndexer(self.repo, self.kb, self.config)
        
        # Setup LLM (use mock for demo if no API key)
        tracer = LlmTracer(self.config.output_dir)
        
        if self.config.llm_api_key:
            llm_model = create_llm_model(
                model_type="litellm",
                model_name=self.config.llm_model,
                api_key=self.config.llm_api_key,
                base_url=self.config.llm_base_url,
                tracer=tracer
            )
        else:
            print("Warning: No LLM API key provided, using mock model for demo")
            llm_model = create_llm_model(
                model_type="mock",
                model_name="mock-gpt",
                tracer=tracer
            )
        
        self.llm_analyzer = CodeAnalysisLlm(llm_model)
    
    def _create_artifact_directory(self, repo_path: str, base_kb_path: str) -> str:
        """Create timestamped artifact directory for repository analysis.
        
        Args:
            repo_path: Path to the repository being analyzed
            base_kb_path: Base knowledge base path from config
            
        Returns:
            Path to the created artifact directory
        """
        # Extract repository name from path
        repo_name = Path(repo_path).name
        
        # Check for existing artifact directories for this repository
        base_path = Path(base_kb_path).parent if Path(base_kb_path).name == "kb" else Path(base_kb_path)
        existing_artifacts = list(base_path.glob(f"artifacts_{repo_name}_*"))
        
        # If we have existing artifacts, use the most recent one
        if existing_artifacts:
            # Sort by modification time to get the most recent
            latest_artifact = max(existing_artifacts, key=lambda p: p.stat().st_mtime)
            kb_path = latest_artifact / "kb"
            
            print(f"📁 Using existing artifact directory: {latest_artifact}")
            print(f"📚 Knowledge base path: {kb_path}")
            
            return str(kb_path)
        
        # Generate timestamp for new artifact directory
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Create timestamped artifact directory name
        artifact_dir_name = f"artifacts_{repo_name}_{timestamp}"
        artifact_dir = base_path / artifact_dir_name
        
        # Create the knowledge base directory
        kb_path = artifact_dir / "kb"
        kb_path.mkdir(parents=True, exist_ok=True)
        
        # Create configuration file for this repository
        config_file = artifact_dir / f"{repo_name}_config.yaml"
        self._create_artifact_config(config_file, repo_path, str(kb_path))
        
        print(f"📁 Created artifact directory: {artifact_dir}")
        print(f"📚 Knowledge base path: {kb_path}")
        print(f"⚙️  Configuration file: {config_file}")
        
        return str(kb_path)
    
    def _create_artifact_config(self, config_file: Path, repo_path: str, kb_path: str):
        """Create configuration file for the artifact directory.
        
        Args:
            config_file: Path to the configuration file to create
            repo_path: Path to the repository being analyzed
            kb_path: Path to the knowledge base directory
        """
        # Use absolute paths for the configuration file
        artifact_dir_abs = config_file.parent.resolve()
        kb_path_abs = (artifact_dir_abs / "kb").resolve()
        
        config_content = f"""# CodeFusion Configuration for {Path(repo_path).name}
# Auto-generated artifact configuration

# Repository settings
repo_path: "{repo_path}"

# LLM settings
llm_model: "{self.config.llm_model}"
llm_api_key: null
llm_base_url: null

# Knowledge base settings
kb_type: "vector"
kb_path: "{kb_path_abs}"
embedding_model: "BAAI/bge-small-en-v1.5"
neo4j_uri: null
neo4j_user: null
neo4j_password: null

# File filtering
max_file_size: {self.config.max_file_size}
excluded_dirs:
{self._format_yaml_list(self.config.excluded_dirs)}
excluded_extensions:
{self._format_yaml_list(self.config.excluded_extensions)}

# Exploration settings
exploration_strategy: "{self.config.exploration_strategy}"
max_exploration_depth: {self.config.max_exploration_depth}
"""
        
        config_file.write_text(config_content)
    
    def _format_yaml_list(self, items: list) -> str:
        """Format a list for YAML output."""
        if not items:
            return "  []"
        return "\n".join(f"  - \"{item}\"" for item in items)
    
    def cmd_index(self, args):
        """Index command implementation."""
        print(f"🔍 Indexing repository: {args.repo_path}")
        
        self.load_config(args.config)
        self.config.exploration_strategy = args.strategy
        self.setup_components(args.repo_path)
        
        # Run indexing
        results = self.indexer.index_repository()
        
        print("\n✅ Indexing completed!")
        print(f"📁 Files processed: {results['files_processed']}")
        print(f"🏗️  Entities created: {results['entities_created']}")
        print(f"🔗 Relationships created: {results['relationships_created']}")
        
        if results.get('errors'):
            print(f"⚠️  Errors encountered: {len(results['errors'])}")
            if args.verbose:
                for error in results['errors']:
                    print(f"   - {error}")
        
        # Show C4 mapping
        if results.get('c4_levels'):
            print(f"\n📊 C4 Architecture Levels:")
            for level, count in results['c4_levels'].items():
                print(f"   {level}: {count} entities")
    
    def cmd_query(self, args):
        """Query command implementation."""
        print(f"❓ Question: {args.question}")
        
        self.load_config(args.config)
        
        if args.repo_path:
            self.setup_components(args.repo_path)
        else:
            # Try to load existing KB
            self.kb = create_knowledge_base(
                kb_type=self.config.kb_type,
                storage_path=self.config.kb_path
            )
            
            if not self.kb._entities:
                print("No knowledge base found. Please index a repository first.")
                return
        
        # Search for relevant entities - try multiple search strategies
        entities = self.kb.search_entities(args.question)
        
        # If no direct matches, try extracting key terms and searching by type
        if not entities:
            question_lower = args.question.lower()
            if "class" in question_lower:
                entities = self.kb.search_entities("", entity_type="class")
            elif "function" in question_lower:
                entities = self.kb.search_entities("", entity_type="function")
            elif "file" in question_lower:
                entities = self.kb.search_entities("", entity_type="file")
        
        if not entities:
            print("No relevant code found for your question.")
            return
        
        # Use agentic reasoning framework for detailed answers
        from ..agents.reasoning_agent import ReasoningAgent
        from ..aci.system_access import SystemAccess
        
        # Load environment variables for API keys
        system_access = SystemAccess()
        
        # Check if we have LLM configuration
        if system_access.has_llm_config():
            # Update config with environment variables
            self.config._load_env_overrides()
            
            # Use different strategies based on user choice
            strategy = getattr(args, 'strategy', 'react')
            
            if strategy == 'react':
                # Use advanced reasoning agent (ReAct strategy)
                reasoning_agent = ReasoningAgent(self.config)
                
                # Get knowledge base results for context
                kb_results = []
                try:
                    if hasattr(self.kb, 'search_content'):
                        kb_results = self.kb.search_content(args.question)
                except:
                    pass
                
                # Perform agentic reasoning
                reasoning_result = reasoning_agent.reason_about_question(
                    args.question, entities, kb_results
                )
                
                print(f"\n💡 Comprehensive Answer (ReAct Strategy):")
                print(reasoning_result.final_answer)
                
                # Show reasoning steps if verbose
                if hasattr(args, 'verbose') and args.verbose:
                    print(f"\n🔍 Reasoning Steps:")
                    for i, step in enumerate(reasoning_result.reasoning_steps, 1):
                        print(f"\n{i}. {step.step_type.title()}: {step.question}")
                        print(f"   Answer: {step.answer[:200]}...")
                        print(f"   Confidence: {step.confidence:.2f}")
                
                # Show entities consulted
                if reasoning_result.entities_consulted:
                    print(f"\n📋 Entities Consulted: {len(reasoning_result.entities_consulted)}")
                    for entity in reasoning_result.entities_consulted[:5]:
                        print(f"   • {entity.name} ({entity.type}) in {entity.path}")
            
            elif strategy == 'plan_act':
                # Use Plan-then-Act strategy
                from ..agents.plan_then_act import PlanThenActAgent
                
                if not hasattr(args, 'repo_path') or not args.repo_path:
                    print("Error: --repo-path is required for plan_act strategy")
                    return
                
                plan_agent = PlanThenActAgent(self.config, self.kb)
                plan_result = plan_agent.explore_codebase(args.question, args.repo_path)
                
                print(f"\n💡 Comprehensive Answer (Plan-then-Act Strategy):")
                print(f"Goal: {plan_result.plan.goal}")
                print(f"Success Rate: {plan_result.success_rate:.2f}")
                print(f"Execution Time: {plan_result.execution_time} minutes")
                
                print(f"\n📋 Discovered Entities: {len(plan_result.discovered_entities)}")
                for entity in plan_result.discovered_entities[:5]:
                    print(f"   • {entity.name} ({entity.type}) in {entity.path}")
                
                print(f"\n💡 Key Insights:")
                for insight in plan_result.insights[:5]:
                    print(f"   • {insight}")
                
                # Show plan steps if verbose
                if hasattr(args, 'verbose') and args.verbose:
                    print(f"\n🔍 Execution Steps:")
                    for i, step in enumerate(plan_result.executed_steps, 1):
                        print(f"\n{i}. {step.description}")
                        print(f"   Action: {step.action_type}")
                        print(f"   Completed: {'✅' if step.completed else '❌'}")
                        if step.results:
                            print(f"   Results: {len(step.results)} findings")
            
            elif strategy == 'sense_act':
                # Use Sense-then-Act strategy
                from ..agents.sense_then_act import SenseThenActAgent
                
                if not hasattr(args, 'repo_path') or not args.repo_path:
                    print("Error: --repo-path is required for sense_act strategy")
                    return
                
                sense_agent = SenseThenActAgent(self.config, self.kb)
                session_result = sense_agent.explore_codebase(args.question, args.repo_path)
                
                print(f"\n💡 Comprehensive Answer (Sense-then-Act Strategy):")
                print(session_result.final_answer)
                
                print(f"\n📊 Exploration Summary:")
                print(f"   • Cycles: {len(session_result.cycles)}")
                print(f"   • Entities: {len(session_result.total_entities)}")
                print(f"   • Insights: {len(session_result.key_insights)}")
                print(f"   • Success Rate: {session_result.success_rate:.2f}")
                
                # Show cycles if verbose
                if hasattr(args, 'verbose') and args.verbose:
                    print(f"\n🔍 Exploration Cycles:")
                    for cycle in session_result.cycles:
                        print(f"\nCycle {cycle.cycle_id}: {cycle.sense_result.focus_area}")
                        print(f"   Observations: {len(cycle.sense_result.observations)}")
                        print(f"   Confidence: {cycle.sense_result.confidence:.2f}")
                        print(f"   Success: {'✅' if cycle.action_result.success else '❌'}")
                        print(f"   Next Focus: {cycle.next_focus}")
                
                print(f"\n💡 Key Insights:")
                for insight in session_result.key_insights[:5]:
                    print(f"   • {insight}")
        
        else:
            # Fallback to basic content analysis
            from ..kb.content_analyzer import ContentAnalyzer
            
            analyzer = ContentAnalyzer()
            analyzed_answer = analyzer.analyze_question(args.question, entities)
            
            print(f"\n💡 Answer:")
            print(analyzed_answer.answer)
            
            print(f"\n⚠️  For more detailed answers, add your API key to .env file:")
            print(f"   OPENAI_API_KEY=your_key_here")
            print(f"   # or")
            print(f"   ANTHROPIC_API_KEY=your_key_here")
            
            # Show relevant files if confidence is low
            if analyzed_answer.confidence < 0.6:
                if analyzed_answer.files:
                    print(f"\n📁 Relevant Files:")
                    for file_ref in analyzed_answer.files[:5]:
                        print(f"   • {file_ref}")
    
    def cmd_explore(self, args):
        """Explore command implementation."""
        print(f"🚀 Starting full exploration of: {args.repo_path}")
        
        # First, index the repository
        self.cmd_index(args)
        
        # Then, provide some automatic insights
        print("\n🧠 Generating insights...")
        
        # Get repository overview
        env = EnvironmentManager(self.repo, self.config)
        overview = env.get_repository_overview()
        
        print(f"\n📈 Repository Overview:")
        print(f"   Primary language: {overview['primary_language']}")
        print(f"   Total files: {overview['repository_stats']['total_files']}")
        print(f"   File types: {', '.join(overview['repository_stats']['file_types'].keys())}")
        
        # Get exploration suggestions
        suggestions = env.suggest_exploration_strategy()
        print(f"\n💡 Exploration Suggestions:")
        for suggestion in suggestions:
            print(f"   • {suggestion}")
        
        # Demonstrate query capability
        print(f"\n🔍 Example Analysis:")
        sample_questions = [
            "What is the main purpose of this codebase?",
            "What are the key components?",
        ]
        
        for question in sample_questions:
            print(f"\nQ: {question}")
            try:
                # Mock a quick analysis
                stats = self.kb.get_statistics()
                if stats['total_entities'] > 0:
                    file_count = stats['entity_types'].get('file', 0)
                    print(f"A: Based on {stats['total_entities']} code entities analyzed, this appears to be a {overview['primary_language']} project with {file_count} files.")
                else:
                    print("A: Analysis in progress...")
            except Exception as e:
                print(f"A: Unable to analyze - {e}")
    
    def cmd_stats(self, args):
        """Stats command implementation."""
        self.load_config(args.config)
        
        if args.repo_path:
            self.setup_components(args.repo_path)
        else:
            self.kb = create_knowledge_base(
                kb_type=self.config.kb_type,
                storage_path=self.config.kb_path
            )
        
        stats = self.kb.get_statistics()
        
        print("📊 Knowledge Base Statistics:")
        print(f"   Total entities: {stats['total_entities']}")
        print(f"   Total relationships: {stats['total_relationships']}")
        
        if stats['entity_types']:
            print(f"   Entity types:")
            for entity_type, count in stats['entity_types'].items():
                print(f"     {entity_type}: {count}")
        
        if stats['relationship_types']:
            print(f"   Relationship types:")
            for rel_type, count in stats['relationship_types'].items():
                print(f"     {rel_type}: {count}")
        
        print(f"   Storage path: {stats['storage_path']}")
    
    def cmd_demo(self, args):
        """Demo command implementation."""
        print("🎯 CodeFusion V0.01 Demo")
        print("=" * 40)
        
        try:
            # Load config
            self.load_config(args.config)
            print("✅ Configuration loaded")
            
            # Setup components
            self.setup_components(args.repo_path)
            print("✅ Components initialized")
            
            # Index repository
            print(f"\n🔍 Indexing {args.repo_path}...")
            results = self.indexer.index_repository()
            print(f"✅ Indexed {results['files_processed']} files, created {results['entities_created']} entities")
            
            # Show stats
            stats = self.kb.get_statistics()
            print(f"\n📊 Knowledge Base: {stats['total_entities']} entities, {stats['total_relationships']} relationships")
            
            # Demo query
            print(f"\n❓ Demo Query: 'What programming languages are used?'")
            entities = self.kb.search_entities("language programming")
            languages = set()
            for entity in entities:
                if entity.language != "unknown":
                    languages.add(entity.language)
            
            if languages:
                print(f"💡 Languages detected: {', '.join(languages)}")
            else:
                print("💡 No specific languages detected in entity metadata")
            
            print(f"\n🎉 Demo completed successfully!")
            print(f"💾 Knowledge base saved to: {self.config.kb_path}")
            
        except Exception as e:
            print(f"❌ Demo failed: {e}")
            if args.verbose:
                import traceback
                traceback.print_exc()


def main():
    """Main entry point."""
    cli = CodeFusionCLI()
    cli.run()


if __name__ == "__main__":
    main()