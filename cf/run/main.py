#!/usr/bin/env python3
"""
CodeFusion - Clean Main Entry Point

Simple command-line interface. Supervisor is agnostic - just answers questions.
"""

import argparse
import sys
import traceback
from pathlib import Path

# All imports at top - no mid-file imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from cf.configs.config_mgr import ConfigManager
from cf.agents.supervisor import SupervisorAgent


def display_result(result, verbose=False):
    """Common result display logic for all commands"""
    if result.get('success'):
        # Display title if available
        title = result.get('title', '')
        if title and title != 'Analysis Results':
            print(f"\n🎯 {title}")
            print("=" * 70)
            print()
        
        # Display main narrative
        print(result['narrative'])
        
        # Display additional info if verbose
        if verbose:
            print(f"\n📊 **Analysis Confidence:** {result.get('confidence', 0):.1%}")
            print(f"🤖 **Powered by:** {result.get('model', 'gpt-4o')}")
            if result.get('agents_consulted'):
                print(f"🎯 **Agents used:** {len(result['agents_consulted'])}")
            print("💡 This unified narrative traces the complete journey of how your")
            print("   question flows through interconnected system components.")
            print(f"⏱️  Response time: {result.get('execution_time', 0):.1f}s")
        
        return 0
    else:
        print(f"❌ Error: {result.get('error', 'Unknown error')}", file=sys.stderr)
        return 1


def run_interactive_session(supervisor, verbose=False):
    """Interactive session - supervisor just answers questions"""
    print("🔄 Interactive mode - type 'exit' or 'quit' to stop")
    print("=" * 50)
    
    while True:
        try:
            question = input("\n❓ Ask a question: ").strip()
            
            if question.lower() in ['exit', 'quit', '']:
                print("👋 Goodbye!")
                break
                
            result = supervisor.analyze(question)
            display_result(result, verbose)
                
        except (KeyboardInterrupt, EOFError):
            print("\n👋 Session ended")
            break


def create_parser():
    """Create argument parser"""
    parser = argparse.ArgumentParser(description="CodeFusion - Simple Code Analysis")
    
    parser.add_argument('--config', default='cf/configs/config.yaml', help='Config file')
    parser.add_argument('--agents', nargs='+', choices=['code', 'docs', 'web'], 
                       default=['code', 'docs', 'web'], help='Agents to use')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    parser.add_argument('--trace', action='store_true', help='Enable tracing')
    
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    ask_parser = subparsers.add_parser('ask', help='Ask question')
    ask_parser.add_argument('repo_path', help='Repository path')
    ask_parser.add_argument('question', help='Question to ask')
    
    summary_parser = subparsers.add_parser('summary', help='Generate summary')
    summary_parser.add_argument('repo_path', help='Repository path')
    
    interactive_parser = subparsers.add_parser('interactive', help='Interactive session')
    interactive_parser.add_argument('repo_path', help='Repository path')
    
    return parser


def main():
    """Main entry point"""
    parser = create_parser()
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    try:
        # Setup
        config_mgr = ConfigManager(args.config)
        config = config_mgr.get_config()
        
        # Override config with CLI flags
        if args.verbose:
            config.setdefault('logging', {})['verbose'] = True
        if args.trace:
            config.setdefault('trace', {})['enabled'] = True
        
        repo_path = Path(args.repo_path)
        if not repo_path.exists():
            print(f"Error: Repository not found: {repo_path}", file=sys.stderr)
            return 1
            
        supervisor = SupervisorAgent(
            repo_path=str(repo_path),
            config=config
        )
        
        if args.verbose:
            print(f"🚀 CodeFusion - {args.command.title()}")
            print(f"📁 {repo_path} | 🤖 {', '.join(args.agents)}")
            print("=" * 50)
        
        # Execute command - supervisor just answers questions
        if args.command == 'ask':
            result = supervisor.analyze(args.question)
            return display_result(result, args.verbose)
            
        elif args.command == 'summary':
            question = "What is this codebase? Provide an overview of architecture and key components."
            result = supervisor.analyze(question)
            return display_result(result, args.verbose)
            
        elif args.command == 'interactive':
            run_interactive_session(supervisor, args.verbose)
            return 0
        
    except KeyboardInterrupt:
        print("\n👋 Interrupted")
        return 0
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        if args.verbose:
            traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
