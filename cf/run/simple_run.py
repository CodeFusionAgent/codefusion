"""
Simple CodeFusion CLI

This replaces the complex run.py with a human-like exploration approach.
No AST, no vector DB, no complex knowledge graphs - just natural investigation.
"""

import argparse
import sys
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

from cf.config import CfConfig
from cf.agents.react_supervisor_agent import ReActSupervisorAgent
from cf.aci.repo import LocalCodeRepo
from cf.utils.logging_utils import init_cf_logger, execution_log, error_log, progress_log, info_log
from cf.tools import display_life_of_x_narrative
from cf.core.interactive_session import InteractiveSessionManager


class SimpleCodeFusionCLI:
    """
    CLI for CodeFusion ReAct framework.
    """
    
    def __init__(self):
        self.config: Optional[CfConfig] = None
        self.supervisor: Optional[ReActSupervisorAgent] = None
    
    def run(self):
        """Main CLI entry point."""
        # Initialize basic logging first (will be reconfigured later with config)
        init_cf_logger()  # Initialize with defaults
        
        execution_log(f"\n🚀 [CLI] CodeFusion CLI Starting")
        execution_log(f"📋 [CLI] Parsing command line arguments...")
        
        parser = self.create_parser()
        args = parser.parse_args()
        
        execution_log(f"✅ [CLI] Arguments parsed successfully")
        execution_log(f"🎯 [CLI] Command: {getattr(args, 'command', 'help')}")
        
        if hasattr(args, 'func'):
            try:
                execution_log(f"🔧 [CLI] Executing command function...")
                args.func(args)
                execution_log(f"✅ [CLI] Command completed successfully")
            except Exception as e:
                error_log(f"❌ [CLI] Command failed with error: {e}")
                print(f"Error: {e}", file=sys.stderr)
                sys.exit(1)
        else:
            execution_log(f"📖 [CLI] No command specified, showing help")
            parser.print_help()
    
    def create_parser(self):
        """Create the argument parser."""
        parser = argparse.ArgumentParser(
            description="CodeFusion - ReAct Framework for Intelligent Code Analysis",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples - Life of X Narratives:
  python -m cf explore /path/to/repo "How does authentication work?"
  python -m cf ask /path/to/repo "What happens when a user logs in?"
  python -m cf explore /path/to/repo "How is data processed?"
  python -m cf continue /path/to/repo "How is the response sent back?" --previous "How does authentication work?"
  python -m cf analyze /path/to/repo --focus=all

Interactive Mode (NEW):
  python -m cf interactive /path/to/repo
  • Continuous question-answer sessions
  • Memory persistence across questions
  • Web search integration for external documentation
  • Context building and accumulated learning
  • Session history and summaries

Life of X Format:
  CodeFusion answers questions as architectural narratives following a feature
  through the entire system - like "Life of a Search Query in Google".
  Ask questions like "How does X work?" or "What happens when Y?" for best results.
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
        
        parser.add_argument(
            "--logs", "--enable-logs",
            action="store_true",
            help="Enable execution flow logging (shows detailed progress)"
        )
        
        parser.add_argument(
            "--no-progress",
            action="store_true",
            help="Disable progress indicators"
        )
        
        parser.add_argument(
            "--llm-logs",
            action="store_true",
            help="Enable LLM API call logging"
        )
        
        parser.add_argument(
            "--tool-logs",
            action="store_true",
            help="Enable tool execution logging"
        )
        
        parser.add_argument(
            "--agent-logs",
            action="store_true",
            help="Enable agent reasoning logging"
        )
        
        subparsers = parser.add_subparsers(title="commands", dest="command")
        
        # Explore command - main human-like exploration
        explore_parser = subparsers.add_parser(
            "explore",
            help="Explore repository like a human engineer"
        )
        explore_parser.add_argument("repo_path", help="Path to repository")
        explore_parser.add_argument("question", help="What to understand about the code")
        explore_parser.set_defaults(func=self.cmd_explore)
        
        # Ask command - alias for explore
        ask_parser = subparsers.add_parser(
            "ask",
            help="Ask a question about the repository"
        )
        ask_parser.add_argument("repo_path", help="Path to repository")
        ask_parser.add_argument("question", help="Question about the codebase")
        ask_parser.set_defaults(func=self.cmd_explore)
        
        # Continue command - build on previous exploration
        continue_parser = subparsers.add_parser(
            "continue",
            help="Continue exploration building on previous knowledge"
        )
        continue_parser.add_argument("repo_path", help="Path to repository")
        continue_parser.add_argument("question", help="New question to explore")
        continue_parser.add_argument(
            "--previous",
            required=True,
            help="Previous question that was explored"
        )
        continue_parser.set_defaults(func=self.cmd_continue)
        
        # Multi-agent command - comprehensive analysis
        agent_parser = subparsers.add_parser(
            "analyze",
            help="Comprehensive multi-agent analysis"
        )
        agent_parser.add_argument("repo_path", help="Path to repository")
        agent_parser.add_argument("--focus", choices=["docs", "code_arch", "all"], default="all", help="Focus area")
        agent_parser.set_defaults(func=self.cmd_analyze)
        
        # Summary command - show all explorations
        summary_parser = subparsers.add_parser(
            "summary",
            help="Show summary of all explorations"
        )
        summary_parser.add_argument("repo_path", help="Path to repository")
        summary_parser.set_defaults(func=self.cmd_summary)
        
        # Interactive command - continuous exploration
        interactive_parser = subparsers.add_parser(
            "interactive",
            help="Start interactive exploration session with memory and web search"
        )
        interactive_parser.add_argument("repo_path", help="Path to repository")
        interactive_parser.add_argument(
            "--session-dir",
            help="Directory to store session data (default: <repo>/.codefusion_sessions)"
        )
        interactive_parser.add_argument(
            "--resume",
            help="Resume a specific session by session ID (e.g., session_20250720_153304)"
        )
        interactive_parser.add_argument(
            "--list-sessions",
            action="store_true",
            help="List available sessions to resume"
        )
        interactive_parser.set_defaults(func=self.cmd_interactive)
        
        return parser
    
    def load_config(self, config_path: str, args=None):
        """Load configuration and initialize logging."""
        
        progress_log(f"\n⚙️  Loading configuration from: {config_path}")
        
        try:
            self.config = CfConfig.from_file(config_path)
            if self.config:
                progress_log(f"✅ Configuration loaded successfully")
                progress_log(f"🔍 Validating configuration...")
                self.config.validate()
                progress_log(f"✅ Configuration validation passed")
            else:
                progress_log(f"⚠️  Configuration loaded but is None, using defaults")
                self.config = CfConfig()
        except FileNotFoundError:
            progress_log(f"⚠️  Config file not found: {config_path}")
            self.config = CfConfig()
            if config_path != "config/default/config.yaml":  # Only warn if non-default
                progress_log(f"Warning: Config file {config_path} not found, using defaults")
            progress_log(f"🔧 Using default configuration")
        except Exception as e:
            progress_log(f"❌ Error loading config: {e}")
            print(f"Error loading config: {e}")
            progress_log(f"🔧 Falling back to default configuration")
            self.config = CfConfig()
        
        # Override logging settings with CLI arguments
        if args:
            if hasattr(args, 'logs') and args.logs:
                self.config.logging['enable_execution_logs'] = True
                self.config.logging['enable_llm_logs'] = True
                self.config.logging['enable_tool_logs'] = True
                self.config.logging['enable_agent_logs'] = True
            
            if hasattr(args, 'llm_logs') and args.llm_logs:
                self.config.logging['enable_llm_logs'] = True
            
            if hasattr(args, 'tool_logs') and args.tool_logs:
                self.config.logging['enable_tool_logs'] = True
            
            if hasattr(args, 'agent_logs') and args.agent_logs:
                self.config.logging['enable_agent_logs'] = True
            
            if hasattr(args, 'no_progress') and args.no_progress:
                self.config.logging['show_progress'] = False
        
        # Initialize the global logger with the configuration
        init_cf_logger(self.config.to_dict())
    
    def setup_explorer(self, repo_path: str):
        """Setup the ReAct supervisor."""
        
        execution_log(f"\n🏗️  [CLI] Setting up ReAct supervisor agent")
        execution_log(f"📁 [CLI] Repository path: {repo_path}")
        
        if not self.config:
            error_log(f"❌ [CLI] Configuration not loaded")
            raise Exception("Configuration not loaded")
        
        # Validate repository path
        execution_log(f"🔍 [CLI] Validating repository path...")
        repo_path_obj = Path(repo_path)
        if not repo_path_obj.exists():
            error_log(f"❌ [CLI] Repository path does not exist: {repo_path}")
            raise Exception(f"Repository path does not exist: {repo_path}")
        
        if not repo_path_obj.is_dir():
            error_log(f"❌ [CLI] Repository path is not a directory: {repo_path}")
            raise Exception(f"Repository path is not a directory: {repo_path}")
        
        execution_log(f"✅ [CLI] Repository path validation passed")
        
        # Create ReAct supervisor agent
        execution_log(f"🤖 [CLI] Creating LocalCodeRepo for path: {repo_path}")
        code_repo = LocalCodeRepo(repo_path)
        execution_log(f"🎯 [CLI] Initializing ReActSupervisorAgent...")
        self.supervisor = ReActSupervisorAgent(code_repo, self.config)
        execution_log(f"✅ [CLI] ReAct supervisor agent ready")
        progress_log(f"✅ Ready to explore: {repo_path_obj.name}")
    
    def cmd_explore(self, args):
        """Handle explore/ask command."""
        
        execution_log("\n🚀 [CLI] Starting explore command")
        info_log("🚀 CodeFusion - ReAct Framework Explorer")
        info_log("=" * 50)
        
        execution_log(f"📝 [CLI] Question: {args.question}")
        execution_log(f"📁 [CLI] Repository: {args.repo_path}")
        execution_log(f"⚙️  [CLI] Config: {args.config}")
        
        self.load_config(args.config, args)
        self.setup_explorer(args.repo_path)
        
        # Show the question being explored
        info_log(f"\n🔍 Exploring: {args.question}")
        info_log("-" * 30)
        
        # Generate Life of X narrative
        try:
            progress_log(f"📖 Generating comprehensive analysis...")
            narrative_result = self.supervisor.generate_life_of_x_narrative(args.question)
            execution_log(f"✅ [CLI] Life of X narrative generated successfully")
            self._display_life_of_x_narrative(narrative_result, args.question)
        except Exception as e:
            error_log(f"❌ Error generating narrative: {e}")
            # Fallback to basic results
            progress_log(f"🔄 Falling back to basic repository exploration...")
            result = self.supervisor.explore_repository(goal=args.question, focus="all")
            agent_results = self.supervisor.get_agent_results()
            execution_log(f"✅ [CLI] Basic exploration completed")
            
            # Always show the analysis summary
            info_log(f"\n📊 Analysis Summary:")
            info_log(f"   🤖 Agents Activated: {len(agent_results)}")
            
            for agent_name, agent_result in agent_results.items():
                if isinstance(agent_result, dict) and agent_result.get('summary'):
                    info_log(f"   📋 {agent_name.title()}: Completed")
    
    def _display_life_of_x_narrative(self, narrative_result: Dict[str, Any], question: str):
        """Display the Life of X narrative in a beautiful format."""
        display_life_of_x_narrative(narrative_result, question)
    
    
    def cmd_continue(self, args):
        """Handle continue command."""
        
        info_log("🔄 CodeFusion - Continuing Analysis")
        info_log("=" * 50)
        
        self.load_config(args.config, args)
        self.setup_explorer(args.repo_path)
        
        info_log(f"\n🏗️  Building on: {args.previous}")
        info_log(f"🔍 New question: {args.question}")
        info_log("-" * 30)
        
        # Generate Life of X narrative for the continued question
        combined_question = f"Building on '{args.previous}': {args.question}"
        try:
            narrative_result = self.supervisor.generate_life_of_x_narrative(combined_question)
            self._display_life_of_x_narrative(narrative_result, args.question)
        except Exception as e:
            error_log(f"❌ Error generating narrative: {e}")
            # Fallback to basic results
            result = self.supervisor.explore_repository(goal=combined_question, focus="all")
            agent_results = self.supervisor.get_agent_results()
            info_log(f"\n📊 Continued Analysis:")
            info_log(f"   🤖 Agents Activated: {len(agent_results)}")
    
    def cmd_analyze(self, args):
        """Handle multi-agent analyze command."""
        
        execution_log("\n🤖 [CLI] Starting analyze command")
        info_log("🤖 CodeFusion - Multi-Agent Analysis")
        info_log("=" * 50)
        
        execution_log(f"🎯 [CLI] Focus: {args.focus}")
        execution_log(f"📁 [CLI] Repository: {args.repo_path}")
        execution_log(f"⚙️  [CLI] Config: {args.config}")
        
        self.load_config(args.config, args)
        self.setup_explorer(args.repo_path)
        
        execution_log(f"\n🔍 [CLI] Starting repository analysis with focus: {args.focus}")
        info_log(f"\n🔍 Analyzing with focus: {args.focus}")
        info_log("-" * 30)
        
        execution_log(f"📊 [CLI] Executing multi-agent exploration...")
        result = self.supervisor.explore_repository(focus=args.focus)
        execution_log(f"✅ [CLI] Multi-agent exploration completed")
        
        # Display results from the ReAct supervisor
        if result.get("summary"):
            info_log("\n📋 Analysis Summary:")
            info_log(result["summary"])
        
        # Display agent-specific results
        agent_results = result.get("agent_results", {})
        for agent_name, agent_result in agent_results.items():
            if isinstance(agent_result, dict) and agent_result.get("summary"):
                info_log(f"\n🤖 {agent_name.title()} Agent Results:")
                info_log(agent_result["summary"])
        
        # Display cross-agent insights
        insights = result.get("cross_agent_insights", [])
        if insights:
            info_log("\n🔄 Cross-Agent Insights:")
            for insight in insights:
                if isinstance(insight, dict):
                    info_log(f"  • {insight.get('content', 'Unknown insight')}")
        
        # Display execution stats
        execution_time = result.get("execution_time", 0)
        iterations = result.get("iterations", 0)
        if execution_time > 0:
            info_log(f"\n⏱️  Execution Time: {execution_time:.2f}s ({iterations} iterations)")
        
        # Display any errors
        if result.get("error"):
            error_log(f"\n❌ Error: {result['error']}")
    
    def cmd_summary(self, args):
        """Handle summary command."""
        
        info_log("📊 CodeFusion - Analysis Summary")
        info_log("=" * 50)
        
        self.load_config(args.config, args)
        self.setup_explorer(args.repo_path)
        
        # Run quick analysis to generate summary
        result = self.supervisor.explore_repository(goal="generate repository summary", focus="all")
        
        # Display comprehensive report
        report = self.supervisor.generate_comprehensive_report()
        info_log(report.get('summary', 'No analysis completed yet.'))
        
        info_log("\n💡 Try analyzing with: python -m cf analyze <repo_path> --focus=all")
        info_log("\nFocus options:")
        info_log("  • --focus=all       : Comprehensive analysis")
        info_log("  • --focus=docs      : Documentation analysis")
        info_log("  • --focus=code_arch : Code and Architecture analysis")
    
    def cmd_interactive(self, args):
        """Handle interactive command."""
        
        execution_log("\n🎯 [CLI] Starting interactive command")
        info_log("🎯 CodeFusion - Interactive Session")
        info_log("=" * 50)
        
        execution_log(f"📁 [CLI] Repository: {args.repo_path}")
        execution_log(f"⚙️  [CLI] Config: {args.config}")
        
        self.load_config(args.config, args)
        
        # Handle list sessions command
        if args.list_sessions:
            execution_log(f"📋 [CLI] Listing available sessions...")
            sessions = InteractiveSessionManager.list_sessions(args.repo_path, args.session_dir)
            
            if not sessions:
                info_log("📭 No sessions found.")
                info_log(f"💡 Start a new session with: python -m cf interactive {args.repo_path}")
                return
            
            info_log("📚 Available Sessions:")
            info_log("=" * 50)
            for i, session in enumerate(sessions, 1):
                started = datetime.fromisoformat(session['started_at']).strftime("%Y-%m-%d %H:%M:%S")
                info_log(f"{i}. {session['session_id']}")
                info_log(f"   📅 Started: {started}")
                info_log(f"   ❓ Questions: {session['total_questions']}")
                info_log(f"   🔧 Components: {session['discovered_components']}")
                info_log(f"   💻 Technologies: {session['technologies']}")
                info_log("")
            
            info_log("💡 Resume a session with:")
            info_log(f"   python -m cf interactive {args.repo_path} --resume <session_id>")
            return
        
        # Validate repository path first
        execution_log(f"🔍 [CLI] Validating repository path...")
        repo_path_obj = Path(args.repo_path)
        if not repo_path_obj.exists():
            error_log(f"❌ [CLI] Repository path does not exist: {args.repo_path}")
            raise Exception(f"Repository path does not exist: {args.repo_path}")
        
        if not repo_path_obj.is_dir():
            error_log(f"❌ [CLI] Repository path is not a directory: {args.repo_path}")
            raise Exception(f"Repository path is not a directory: {args.repo_path}")
        
        execution_log(f"✅ [CLI] Repository path validation passed")
        
        # Create interactive session manager
        try:
            execution_log(f"🎯 [CLI] Creating interactive session manager...")
            session_manager = InteractiveSessionManager(
                repo_path=args.repo_path,
                config=self.config,
                session_dir=args.session_dir,
                resume_session_id=args.resume
            )
            execution_log(f"✅ [CLI] Interactive session manager created")
            
            # Start interactive loop
            execution_log(f"🚀 [CLI] Starting interactive exploration loop...")
            session_manager.start_interactive_loop()
            execution_log(f"✅ [CLI] Interactive session completed")
            
        except Exception as e:
            error_log(f"❌ [CLI] Interactive session failed: {e}")
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)


def main():
    """Main entry point for simple CLI."""
    cli = SimpleCodeFusionCLI()
    cli.run()


if __name__ == "__main__":
    main()