#!/usr/bin/env python3
"""
Universal CodeFusion ReAct Framework Demo

This comprehensive demo showcases the complete ReAct framework capabilities:
- Multi-agent coordination and reasoning loops
- Live analysis with performance metrics
- Educational explanations of the ReAct pattern
- Can run on any repository (CodeFusion itself, FastAPI, or any other repo)
"""

import sys
import time
import logging
import argparse
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(name)s - %(message)s')

from cf.agents.react_supervisor_agent import ReActSupervisorAgent
from cf.aci.repo import LocalCodeRepo
from cf.config import CfConfig

def demo_react_framework(repo_path: str, show_concepts: bool = True, focus: str = "all"):
    """
    Comprehensive ReAct framework demonstration.
    
    Args:
        repo_path: Path to repository to analyze
        show_concepts: Whether to show educational concepts
        focus: Analysis focus ('all', 'docs', 'code', 'arch')
    """
    print("🤖 CodeFusion ReAct Framework Demo")
    print("=" * 50)
    print()
    
    # Educational introduction (optional)
    if show_concepts:
        print("📚 What is the ReAct Pattern?")
        print("This demo shows how CodeFusion uses the ReAct (Reasoning + Acting) pattern:")
        print("1. 🧠 REASON: AI-powered analysis of current state and goal progress")
        print("2. 🎯 ACT: Execute specialized tools based on reasoning")  
        print("3. 👁️ OBSERVE: Process results and update understanding")
        print("4. 🔄 REPEAT: Continue until goals are achieved")
        print()
    
    # Setup
    repo_path_obj = Path(repo_path)
    print(f"📁 Target Repository: {repo_path_obj.name} ({repo_path})")
    print(f"🔍 Analysis Focus: {focus}")
    
    if not repo_path_obj.exists():
        print(f"❌ Repository path does not exist: {repo_path}")
        return None
    
    try:
        # Initialize components
        repo = LocalCodeRepo(repo_path)
        config = CfConfig()
        supervisor = ReActSupervisorAgent(repo, config)
        
        print("✅ Initialized ReAct components")
        print("   • LocalCodeRepo for file system access")
        print("   • CfConfig with default settings")
        print("   • ReActSupervisorAgent for multi-agent coordination")
        print()
        
        # Start comprehensive analysis
        print("🚀 Starting Multi-Agent ReAct Analysis")
        print("   Focus: Comprehensive (all agents)")
        print("   Pattern: Reason → Act → Observe loops")
        print()
        
        start_time = time.time()
        
        # Execute the ReAct exploration
        goal = f"comprehensive analysis of {repo_path_obj.name} repository"
        results = supervisor.explore_repository(goal=goal, focus=focus)
        
        execution_time = time.time() - start_time
        
        print("🎯 Analysis Complete!")
        print("=" * 30)
        print()
        
        # Display results
        print("📊 Execution Summary:")
        print(f"   ⏱️  Total Time: {execution_time:.2f} seconds")
        print(f"   🔄 Total Iterations: {results.get('total_iterations', 'N/A')}")
        print(f"   🤖 Agents Activated: {len(supervisor.get_agent_results())}")
        print()
        
        # Agent-specific results
        agent_results = supervisor.get_agent_results()
        
        if 'documentation' in agent_results:
            doc_result = agent_results['documentation']
            print("📚 Documentation Agent Results:")
            if doc_result.get('summary'):
                print(f"   ✅ {doc_result['summary']}")
            else:
                print(f"   📝 Status: {doc_result.get('status', 'Completed')}")
            print()
        
        if 'codebase' in agent_results:
            code_result = agent_results['codebase']
            print("💻 Codebase Agent Results:")
            if code_result.get('summary'):
                print(f"   ✅ {code_result['summary']}")
            else:
                print(f"   📝 Status: {code_result.get('status', 'Completed')}")
            print()
        
        if 'architecture' in agent_results:
            arch_result = agent_results['architecture']
            print("🏗️  Architecture Agent Results:")
            if arch_result.get('summary'):
                print(f"   ✅ {arch_result['summary']}")
            else:
                print(f"   📝 Status: {arch_result.get('status', 'Completed')}")
            print()
        
        # Cross-agent insights
        insights = supervisor.get_cross_agent_insights()
        if insights:
            print("🔗 Cross-Agent Insights:")
            for insight in insights:
                print(f"   • {insight.insight_type}: {insight.content}")
            print()
        
        # Performance metrics
        print("📈 Performance Metrics:")
        total_cache_hits = sum(
            result.get('cache_hits', 0) for result in agent_results.values()
            if isinstance(result, dict)
        )
        total_errors = sum(
            result.get('error_count', 0) for result in agent_results.values()
            if isinstance(result, dict)
        )
        
        print(f"   💾 Cache Hits: {total_cache_hits}")
        print(f"   ❌ Errors: {total_errors}")
        print(f"   🎯 Success Rate: {(len(agent_results) - total_errors) / max(len(agent_results), 1) * 100:.1f}%")
        print()
        
        # Framework capabilities demonstrated
        print("✅ ReAct Framework Capabilities Demonstrated:")
        print("   🧠 Multi-Agent Reasoning: Each agent used Reason → Act → Observe cycles")
        print("   🔄 Adaptive Exploration: Agents adjusted based on observations")
        print("   🤖 Supervisor Coordination: Orchestrated specialized agent activation")
        print("   💾 Persistent Caching: Cross-session memory for efficiency")
        print("   🔍 Comprehensive Analysis: Documentation, code, and architecture coverage")
        print("   📊 Performance Monitoring: Execution tracing and metrics collection")
        print()
        
        return results
        
    except Exception as e:
        print(f"❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def show_framework_comparison():
    """Show comparison between traditional and ReAct approaches."""
    
    print("\n🆚 Traditional vs ReAct Framework Comparison")
    print("=" * 55)
    
    print("\n❌ Traditional Static Analysis:")
    print("  1. One-time parsing of entire codebase")
    print("  2. Static analysis without context")
    print("  3. Limited reasoning about findings")
    print("  4. No adaptive exploration")
    print("  → Fast but shallow, misses context")
    
    print("\n✅ ReAct Framework Approach:")
    print("  1. 🧠 REASON: AI analyzes current state and plans next steps")
    print("  2. 🎯 ACT: Execute specialized tools based on reasoning")
    print("  3. 👁️ OBSERVE: Process results and update understanding")
    print("  4. 🔄 ITERATE: Adapt exploration based on findings")
    print("  5. 🤖 COORDINATE: Multiple specialized agents collaborate")
    print("  → Intelligent, adaptive, comprehensive")
    
    print("\n🚀 ReAct Framework Advantages:")
    print("  • 🧠 AI-powered reasoning and decision making")
    print("  • 🤖 Multi-agent collaborative analysis")
    print("  • 🔄 Adaptive exploration that learns from observations")
    print("  • 🎯 Goal-oriented loops with progress tracking")
    print("  • 💾 Persistent caching across sessions")
    print("  • 🛠️ Rich tool ecosystem (8 specialized tools)")
    print("  • 🔧 Comprehensive error recovery")


def show_usage_examples():
    """Show practical usage examples."""
    
    print("\n🚀 How to Use CodeFusion ReAct Framework")
    print("=" * 45)
    
    print("\n📋 Command Line Interface:")
    print("  # Comprehensive analysis")
    print("  python -m cf.run.simple_run analyze /path/to/repo --focus=all")
    print("  ")
    print("  # Documentation-focused analysis")
    print("  python -m cf.run.simple_run analyze /path/to/repo --focus=docs")
    print("  ")
    print("  # Architecture analysis")
    print("  python -m cf.run.simple_run analyze /path/to/repo --focus=arch")
    print("  ")
    print("  # Question-based exploration")
    print("  python -m cf.run.simple_run explore /path/to/repo \"How does auth work?\"")
    
    print("\n🐍 Python API:")
    print("  from cf.agents.react_supervisor_agent import ReActSupervisorAgent")
    print("  from cf.aci.repo import LocalCodeRepo")
    print("  from cf.config import CfConfig")
    print("  ")
    print("  repo = LocalCodeRepo('/path/to/repo')")
    print("  supervisor = ReActSupervisorAgent(repo, CfConfig())")
    print("  results = supervisor.explore_repository(focus='all')")
    
    print("\n📊 Demo Script:")
    print("  # Run this demo on any repository")
    print("  python demo_cf_framework.py /path/to/repo")
    print("  python demo_cf_framework.py . --focus=docs --no-concepts")


def main():
    """Main demo function with command line interface."""
    parser = argparse.ArgumentParser(
        description="CodeFusion ReAct Framework Demo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python demo_cf_framework.py /tmp/fastapi
  python demo_cf_framework.py . --focus=docs
  python demo_cf_framework.py /path/to/repo --no-concepts --focus=arch
  python demo_cf_framework.py --self-analysis
        """
    )
    
    parser.add_argument(
        "repo_path", 
        nargs="?",
        default=".",
        help="Path to repository to analyze (default: current directory)"
    )
    parser.add_argument(
        "--focus", 
        choices=["all", "docs", "code", "arch"],
        default="all",
        help="Analysis focus (default: all)"
    )
    parser.add_argument(
        "--no-concepts",
        action="store_true", 
        help="Skip educational concept explanations"
    )
    parser.add_argument(
        "--self-analysis",
        action="store_true",
        help="Analyze CodeFusion itself (same as '.')"
    )
    parser.add_argument(
        "--show-comparison",
        action="store_true",
        help="Show framework comparison and exit"
    )
    parser.add_argument(
        "--show-usage",
        action="store_true", 
        help="Show usage examples and exit"
    )
    
    args = parser.parse_args()
    
    # Handle informational flags
    if args.show_comparison:
        show_framework_comparison()
        return
        
    if args.show_usage:
        show_usage_examples()
        return
    
    # Determine repository path
    if args.self_analysis:
        repo_path = str(Path(__file__).parent)
        print("🔍 Self-Analysis Mode: Analyzing CodeFusion itself")
    else:
        repo_path = args.repo_path
    
    # Run the demo
    results = demo_react_framework(
        repo_path=repo_path,
        show_concepts=not args.no_concepts,
        focus=args.focus
    )
    
    # Summary
    if results:
        print("\n🎉 Demo completed successfully!")
        print("   The ReAct framework is fully operational with:")
        print("   • Multi-agent coordination")
        print("   • Systematic reasoning and action cycles") 
        print("   • Comprehensive code analysis capabilities")
        print("   • Error recovery and performance monitoring")
        
        # Show additional info
        if not args.no_concepts:
            show_framework_comparison()
            show_usage_examples()
    else:
        print("❌ Demo encountered issues")


if __name__ == "__main__":
    main()