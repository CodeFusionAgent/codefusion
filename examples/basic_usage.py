"""
Basic Usage Examples for CodeFusion Pluggable Architecture

Demonstrates:
1. Quick setup and usage (tool-only approach)
2. Using KB query tools
3. Registering custom agents
4. Per-tool metrics tracking
5. LlmTask for multi-turn conversations

Updated to follow tool-first design pattern - no direct pipeline access.
"""

import yaml
from pathlib import Path

from cf.integration.setup import quick_setup, create_integrated_system
from cf.agents.knowledge_base import KnowledgeAgent
from cf.llm.task import Message, MessageRole


def example_1_quick_start():
    """
    Example 1: Quick start with default setup (tool-only approach)
    """
    print("\n" + "="*80)
    print("Example 1: Quick Start - Tool-First Design")
    print("="*80)

    # Quick setup with sensible defaults
    system = quick_setup(repo_path="/path/to/your/repo")

    # Access ONLY tool registry (tool-first design)
    # Note: No direct pipeline access - all operations through tools!
    tools = system['tool_registry']

    # Use KB tools
    print("\n📚 Using KB Query Tools:")
    print("-" * 80)

    # Semantic search
    result = tools.execute(
        'structural_kb_search_by_semantics',
        query="find authentication code",
        scope="all",
        limit=10
    )

    if result.get('success'):
        print(f"✅ Found {result['count']} results via semantic search")
        for i, item in enumerate(result['results'][:3], 1):
            print(f"   {i}. {item.get('metadata', {}).get('file_path', 'N/A')}")
    else:
        print(f"❌ Error: {result.get('error')}")

    # Pattern detection
    result = tools.execute(
        'structural_kb_find_design_patterns',
        pattern_type='Singleton'
    )

    if result.get('success'):
        print(f"\n✅ Found {result['count']} design patterns")
    else:
        print(f"\n❌ Error: {result.get('error')}")


def example_2_custom_agent():
    """
    Example 2: Register a custom knowledge agent
    """
    print("\n" + "="*80)
    print("Example 2: Custom Knowledge Agent")
    print("="*80)

    # Define custom agent
    class SecurityAnalysisAgent(KnowledgeAgent):
        """Custom agent that analyzes security vulnerabilities"""

        def __init__(self, config=None):
            super().__init__("security_agent", config)
            self.vulnerabilities_found = []

        def get_capabilities(self):
            return ['security_analysis', 'vulnerability_detection']

        def register_tools(self):
            return {
                'find_security_vulnerabilities': self.find_vulnerabilities,
                'check_sql_injection': self.check_sql_injection,
                'find_xss_risks': self.find_xss_risks
            }

        def get_tool_schemas(self):
            return [
                {
                    'type': 'function',
                    'function': {
                        'name': self.get_prefixed_tool_name('find_security_vulnerabilities'),
                        'description': 'Scan code for security vulnerabilities',
                        'parameters': {
                            'type': 'object',
                            'properties': {
                                'scope': {'type': 'string', 'description': 'Scope to scan (file, directory, all)'}
                            }
                        }
                    }
                }
            ]

        def find_vulnerabilities(self, scope: str = 'all'):
            """Find security vulnerabilities"""
            # Simplified implementation
            return {
                'success': True,
                'vulnerabilities': [
                    {'type': 'SQL Injection', 'file': 'db.py', 'line': 42, 'severity': 'high'},
                    {'type': 'XSS', 'file': 'views.py', 'line': 15, 'severity': 'medium'}
                ],
                'count': 2
            }

        def check_sql_injection(self, file_path: str):
            """Check for SQL injection vulnerabilities"""
            return {'success': True, 'vulnerable': False}

        def find_xss_risks(self, file_path: str):
            """Find XSS risks"""
            return {'success': True, 'risks': []}

    # Create system and register custom agent
    system = quick_setup(repo_path="/path/to/your/repo")
    registry = system['agent_registry']
    tools = system['tool_registry']

    # Register custom agent
    security_agent = SecurityAnalysisAgent(config={})
    registry.register(security_agent)

    # Use custom agent tools (automatically prefixed!)
    print("\n🔒 Using Custom Security Agent:")
    print("-" * 80)

    result = tools.execute('security_agent_find_security_vulnerabilities', scope='all')

    if result.get('success'):
        print(f"✅ Found {result['count']} vulnerabilities")
        for vuln in result['vulnerabilities']:
            print(f"   - {vuln['type']} in {vuln['file']}:{vuln['line']} ({vuln['severity']})")
    else:
        print(f"❌ Error: {result.get('error')}")


def example_3_metrics_tracking():
    """
    Example 3: Track per-tool metrics
    """
    print("\n" + "="*80)
    print("Example 3: Per-Tool Metrics Tracking")
    print("="*80)

    system = quick_setup(repo_path="/path/to/your/repo")
    tools = system['tool_registry']

    # Execute several tools
    print("\n📊 Executing tools...")
    tools.execute('structural_kb_search_by_semantics', query="find auth code", limit=5)
    tools.execute('structural_kb_find_design_patterns', pattern_type='Singleton')
    tools.execute('structural_kb_get_architecture_overview')

    # Get metrics
    metrics = tools.get_metrics()

    print("\n📈 Tool Usage Metrics:")
    print("-" * 80)

    if 'tool_metrics' in metrics:
        for tool_name, tool_metrics in metrics['tool_metrics'].items():
            print(f"\n{tool_name}:")
            print(f"   Calls: {tool_metrics.get('calls', 0)}")
            print(f"   Avg Time: {tool_metrics.get('avg_duration', 0):.3f}s")
            print(f"   Success Rate: {tool_metrics.get('success_rate', 0):.1%}")
            if tool_metrics.get('total_cost', 0) > 0:
                print(f"   Total Cost: ${tool_metrics.get('total_cost', 0):.4f}")


def example_4_llm_task_multi_turn():
    """
    Example 4: Multi-turn conversation with LlmTask
    """
    print("\n" + "="*80)
    print("Example 4: Multi-Turn LLM Conversation")
    print("="*80)

    system = quick_setup(repo_path="/path/to/your/repo")
    llm_task = system['llm_task']

    # Set system context
    llm_task.set_system_message("You are a helpful code analysis assistant.")

    print("\n💬 Multi-turn conversation:")
    print("-" * 80)

    # Turn 1
    response1 = llm_task.ask("What are common security vulnerabilities in Python?")
    print(f"\n👤 User: What are common security vulnerabilities in Python?")
    print(f"🤖 Assistant: {response1['content'][:200]}...")

    # Turn 2 (has context from turn 1)
    response2 = llm_task.ask("Can you explain the first one in more detail?")
    print(f"\n👤 User: Can you explain the first one in more detail?")
    print(f"🤖 Assistant: {response2['content'][:200]}...")

    # Get conversation metrics
    metrics = llm_task.get_metrics()
    print(f"\n📊 Conversation Metrics:")
    print(f"   Total Calls: {metrics['total_calls']}")
    print(f"   Total Tokens: {metrics['total_tokens']}")
    print(f"   Total Cost: ${metrics['total_cost']:.4f}")
    print(f"   Messages in History: {metrics['messages_in_history']}")


def example_5_langfuse_integration():
    """
    Example 5: Langfuse observability integration
    """
    print("\n" + "="*80)
    print("Example 5: Langfuse Observability")
    print("="*80)

    # Create system with Langfuse enabled
    system = create_integrated_system(
        repo_path="/path/to/your/repo",
        config=yaml.safe_load(open("cf/configs/config.yaml")),
        enable_langfuse=True,
        langfuse_config={
            'public_key': 'pk-...',
            'secret_key': 'sk-...',
            'host': 'https://cloud.langfuse.com'
        }
    )

    tools = system['tool_registry']
    tracer = system['tracer']

    # All tool calls are automatically traced
    print("\n📡 Tool calls automatically traced to Langfuse:")
    print("-" * 80)

    result = tools.execute('structural_kb_search_by_semantics', query="find auth code")

    print(f"✅ Executed tool: structural_kb_search_by_semantics")
    print(f"   Results: {result.get('count', 0)} items")
    print(f"   Trace sent to Langfuse for analysis")


def example_6_all_kb_tools():
    """
    Example 6: Showcase all available KB tools
    """
    print("\n" + "="*80)
    print("Example 6: All Available KB Tools")
    print("="*80)

    system = quick_setup(repo_path="/path/to/your/repo")
    tools = system['tool_registry']

    print("\n🛠️ Available KB Query Tools:")
    print("-" * 80)

    # List all available tools
    available_tools = tools.get_available_tools()

    kb_tools = {k: v for k, v in available_tools.items() if k.startswith('structural_kb_')}

    for tool_name, description in kb_tools.items():
        print(f"\n   {tool_name}")
        print(f"      {description}")

    print(f"\n✅ Total KB tools available: {len(kb_tools)}")


if __name__ == "__main__":
    # Run examples (comment out those that require actual repo/KB)
    example_1_quick_start()
    example_2_custom_agent()
    example_3_metrics_tracking()
    example_4_llm_task_multi_turn()
    # example_5_langfuse_integration()  # Requires Langfuse credentials
    example_6_all_kb_tools()

    print("\n" + "="*80)
    print("✨ All examples completed!")
    print("="*80)
