"""
Simple CodeFusion CLI

This replaces the complex run.py with a human-like exploration approach.
No AST, no vector DB, no complex knowledge graphs - just natural investigation.
"""

import argparse
import sys
from pathlib import Path
from typing import Optional

from ..config import CfConfig
from ..agents.react_supervisor_agent import ReActSupervisorAgent
from ..aci.repo import LocalCodeRepo


class SimpleCodeFusionCLI:
    """
    CLI for CodeFusion ReAct framework.
    """
    
    def __init__(self):
        self.config: Optional[CfConfig] = None
        self.supervisor: Optional[ReActSupervisorAgent] = None
    
    def run(self):
        """Main CLI entry point."""
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
        """Create the argument parser."""
        parser = argparse.ArgumentParser(
            description="CodeFusion - ReAct Framework for Intelligent Code Analysis",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  cf explore /path/to/repo "How does authentication work?"
  cf ask /path/to/repo "What are the main API endpoints?"
  cf continue /path/to/repo "How is data validated?" --previous "How does authentication work?"
  cf summary /path/to/repo
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
        agent_parser.add_argument("--focus", choices=["docs", "code", "arch", "all"], default="all", help="Focus area")
        agent_parser.set_defaults(func=self.cmd_analyze)
        
        # Summary command - show all explorations
        summary_parser = subparsers.add_parser(
            "summary",
            help="Show summary of all explorations"
        )
        summary_parser.add_argument("repo_path", help="Path to repository")
        summary_parser.set_defaults(func=self.cmd_summary)
        
        return parser
    
    def load_config(self, config_path: str):
        """Load configuration."""
        try:
            self.config = CfConfig.from_file(config_path)
            if self.config:
                self.config.validate()
        except FileNotFoundError:
            self.config = CfConfig()
            if config_path != "config/default/config.yaml":  # Only warn if non-default
                print(f"Warning: Config file {config_path} not found, using defaults")
        except Exception as e:
            print(f"Error loading config: {e}")
            self.config = CfConfig()
    
    def setup_explorer(self, repo_path: str):
        """Setup the ReAct supervisor."""
        if not self.config:
            raise Exception("Configuration not loaded")
        
        # Validate repository path
        repo_path_obj = Path(repo_path)
        if not repo_path_obj.exists():
            raise Exception(f"Repository path does not exist: {repo_path}")
        
        if not repo_path_obj.is_dir():
            raise Exception(f"Repository path is not a directory: {repo_path}")
        
        # Create ReAct supervisor agent
        code_repo = LocalCodeRepo(repo_path)
        self.supervisor = ReActSupervisorAgent(code_repo, self.config)
        print(f"✅ Ready to explore: {repo_path_obj.name}")
    
    def cmd_explore(self, args):
        """Handle explore/ask command."""
        print("🚀 CodeFusion - ReAct Framework Explorer")
        print("=" * 50)
        
        self.load_config(args.config)
        self.setup_explorer(args.repo_path)
        
        # Perform multi-agent exploration
        print(f"\n🔍 Exploring: {args.question}")
        print("-" * 30)
        
        result = self.supervisor.explore_repository(goal=args.question, focus="all")
        
        # Show results
        agent_results = self.supervisor.get_agent_results()
        print(f"\n📊 Analysis Summary:")
        print(f"   🤖 Agents Activated: {len(agent_results)}")
        
        for agent_name, agent_result in agent_results.items():
            if isinstance(agent_result, dict) and agent_result.get('summary'):
                print(f"   📋 {agent_name.title()}: Completed")
        
        # Show cross-agent insights
        insights = self.supervisor.get_cross_agent_insights()
        if insights:
            print(f"   🔗 Cross-Agent Insights: {len(insights)} generated")
    
    def cmd_continue(self, args):
        """Handle continue command."""
        print("🔄 CodeFusion - Continuing Analysis")
        print("=" * 50)
        
        self.load_config(args.config)
        self.setup_explorer(args.repo_path)
        
        print(f"\n🏗️  Building on: {args.previous}")
        print(f"🔍 New question: {args.question}")
        print("-" * 30)
        
        # Run focused analysis based on the new question
        result = self.supervisor.explore_repository(goal=f"{args.previous} -> {args.question}", focus="all")
        
        # Show results
        agent_results = self.supervisor.get_agent_results()
        print(f"\n📊 Continued Analysis:")
        print(f"   🤖 Agents Activated: {len(agent_results)}")
    
    def cmd_analyze(self, args):
        """Handle multi-agent analyze command."""
        print("🤖 CodeFusion - Multi-Agent Analysis")
        print("=" * 50)
        
        self.load_config(args.config)
        self.setup_explorer(args.repo_path)
        
        print(f"\n🔍 Analyzing with focus: {args.focus}")
        print("-" * 30)
        
        result = self.supervisor.explore_repository(focus=args.focus)
        
        # Display results from the ReAct supervisor
        if result.get("summary"):
            print("\n📋 Analysis Summary:")
            print(result["summary"])
        
        # Display agent-specific results
        agent_results = result.get("agent_results", {})
        for agent_name, agent_result in agent_results.items():
            if isinstance(agent_result, dict) and agent_result.get("summary"):
                print(f"\n🤖 {agent_name.title()} Agent Results:")
                print(agent_result["summary"])
        
        # Display cross-agent insights
        insights = result.get("cross_agent_insights", [])
        if insights:
            print("\n🔄 Cross-Agent Insights:")
            for insight in insights:
                if isinstance(insight, dict):
                    print(f"  • {insight.get('content', 'Unknown insight')}")
        
        # Display execution stats
        execution_time = result.get("execution_time", 0)
        iterations = result.get("iterations", 0)
        if execution_time > 0:
            print(f"\n⏱️  Execution Time: {execution_time:.2f}s ({iterations} iterations)")
        
        # Display any errors
        if result.get("error"):
            print(f"\n❌ Error: {result['error']}")
    
    def cmd_summary(self, args):
        """Handle summary command."""
        print("📊 CodeFusion - Analysis Summary")
        print("=" * 50)
        
        self.load_config(args.config)
        self.setup_explorer(args.repo_path)
        
        # Run quick analysis to generate summary
        result = self.supervisor.explore_repository(goal="generate repository summary", focus="all")
        
        # Display comprehensive report
        report = self.supervisor.generate_comprehensive_report()
        print(report.get('summary', 'No analysis completed yet.'))
        
        print("\n💡 Try analyzing with: python -m cf.run.simple_run analyze <repo_path> --focus=all")
        print("\nFocus options:")
        print("  • --focus=all   : Comprehensive analysis")
        print("  • --focus=docs  : Documentation analysis")
        print("  • --focus=code  : Codebase analysis")
        print("  • --focus=arch  : Architecture analysis")


def main():
    """Main entry point for simple CLI."""
    cli = SimpleCodeFusionCLI()
    cli.run()


if __name__ == "__main__":
    main()