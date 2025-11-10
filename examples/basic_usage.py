"""
Basic Usage Examples for CodeFusion Pluggable Architecture

Demonstrates:
1. Quick setup and usage
2. Using KB query tools
3. Registering custom agents
4. Per-tool metrics tracking
5. LlmTask for multi-turn conversations
"""

import yaml
from pathlib import Path

from cf.integration.setup import quick_setup, create_integrated_system
from cf.agents.kb_agents import KnowledgeAgent
from cf.llm.task import Message, MessageRole


def example_1_quick_start():
    """
    Example 1: Quick start with default setup
    """
    print("\n" + "="*80)
    print("Example 1: Quick Start")
    print("="*80)

    # Quick setup with sensible defaults
    system = quick_setup(repo_path="/path/to/your/repo")

    # Access components
    tools = system['tool_registry']
    pipeline = system['pipeline']

    # Use KB tools (now exposed!)
    print("\n= Using KB Query Tools:")
    print("-" * 80)

    # Semantic search
    result = tools.execute(
        'structural_kb_search_by_semantics',
        query="find authentication code",
        scope="all",
        limit=10
    )

    if result.get('success'):
        print(f" Found {result['count']} results via semantic search")
        for i, item in enumerate(result['results'][:3], 1):
            print(f"   {i}. {item.get('metadata', {}).get('file_path', 'N/A')}")
    else:
        print(f"L Error: {result.get('error')}")

    # Pattern detection
    result = tools.execute(
        'structural_kb_find_design_patterns',
        pattern_type='Singleton'
    )

    if result.get('success'):
        print(f"\n Found {result['count']} design patterns")
    else:
        print(f"\nL Error: {result.get('error')}")


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
                        'name': 'security_agent_find_security_vulnerabilities',
                        'description': 'Scan code for security vulnerabilities',
                        'parameters': {
                            'type': 'object',
                            'properties': {
                                'severity': {
                                    'type': 'string',
                                    'enum': ['critical', 'high', 'medium', 'low', 'all']
                                }
                            }
                        }
                    }
                }
            ]

        def find_vulnerabilities(self, severity='all'):
            """Find security vulnerabilities"""
            return {
                'success': True,
                'vulnerabilities': [
                    {'type': 'SQL Injection', 'severity': 'high', 'file': 'api/db.py:45'},
                    {'type': 'XSS Risk', 'severity': 'medium', 'file': 'views/user.py:123'}
                ],
                'count': 2
            }

        def check_sql_injection(self, file_path=''):
            return {'success': True, 'found': True, 'locations': ['api/db.py:45']}

        def find_xss_risks(self):
            return {'success': True, 'risks': 1}

    # Create system
    config_path = Path(__file__).parent.parent / "cf" / "configs" / "config.yaml"
    with open(config_path) as f:
        config = yaml.safe_load(f)

    system = create_integrated_system("/path/to/repo", config)

    # Register custom agent
    security_agent = SecurityAnalysisAgent()
    system['agent_registry'].register(security_agent)

    # Refresh tool registry to pick up new tools
    tools = system['tool_registry']

    # Use custom agent tools
    print("\n= Using Custom Security Agent:")
    print("-" * 80)

    result = tools.execute('security_agent_find_security_vulnerabilities', severity='high')

    if result.get('success'):
        print(f" Found {result['count']} vulnerabilities")
        for vuln in result['vulnerabilities']:
            print(f"   - {vuln['severity'].upper()}: {vuln['type']} at {vuln['file']}")


def example_3_metrics_tracking():
    """
    Example 3: Per-tool metrics tracking
    """
    print("\n" + "="*80)
    print("Example 3: Per-Tool Metrics Tracking")
    print("="*80)

    system = quick_setup("/path/to/repo")
    tools = system['tool_registry']

    # Execute several tools
    print("\n=Ê Executing tools...")
    tools.execute('structural_kb_search_by_semantics', query="authentication", limit=10)
    tools.execute('structural_kb_find_design_patterns', pattern_type='Factory')
    tools.execute('structural_kb_detect_code_smells', scope='all')

    # Get metrics
    metrics = tools.get_metrics()

    print("\n=È Tool Usage Metrics:")
    print("-" * 80)
    print(f"Total tool calls: {metrics['summary']['total_tool_calls']}")
    print(f"Unique tools used: {metrics['summary']['unique_tools_used']}")
    print(f"Total execution time: {metrics['summary']['total_time']:.2f}s")
    print(f"Total cost: ${metrics['summary']['total_cost']:.4f}")

    print("\n=° Cost Breakdown:")
    for tool_cost in metrics['cost_breakdown'][:5]:
        print(f"  {tool_cost['tool_name']}: ${tool_cost['total_cost']:.4f} ({tool_cost['calls']} calls)")


def example_4_llm_task():
    """
    Example 4: Multi-turn conversation with LlmTask
    """
    print("\n" + "="*80)
    print("Example 4: Multi-Turn Conversation with LlmTask")
    print("="*80)

    system = quick_setup("/path/to/repo")
    llm_task = system['llm_task']

    # Set system context
    llm_task.set_system_message(
        "You are a code analysis assistant. Help the user understand their codebase."
    )

    print("\n=¬ Multi-Turn Conversation:")
    print("-" * 80)

    # Turn 1
    response1 = llm_task.ask("What is a singleton pattern?")
    print(f"\nUser: What is a singleton pattern?")
    print(f"Assistant: {response1['content'][:100]}...")

    # Turn 2 (has context from Turn 1)
    response2 = llm_task.ask("Can you show me an example in Python?")
    print(f"\nUser: Can you show me an example in Python?")
    print(f"Assistant: {response2['content'][:100]}...")

    # Turn 3 (has context from both previous turns)
    response3 = llm_task.ask("What are the pros and cons?")
    print(f"\nUser: What are the pros and cons?")
    print(f"Assistant: {response3['content'][:100]}...")

    # Get conversation history
    history = llm_task.get_history()
    print(f"\n=Ý Conversation history: {len(history)} messages")

    # Get metrics
    metrics = llm_task.get_metrics()
    print(f"\n=Ê LLM Task Metrics:")
    print(f"  Total calls: {metrics['total_calls']}")
    print(f"  Total tokens: {metrics['total_tokens']}")
    print(f"  Total cost: ${metrics['total_cost']:.4f}")
    print(f"  Messages in history: {metrics['messages_in_history']}")


def example_5_langfuse_tracing():
    """
    Example 5: Enable Langfuse tracing
    """
    print("\n" + "="*80)
    print("Example 5: Langfuse Tracing (Optional)")
    print("="*80)

    config_path = Path(__file__).parent.parent / "cf" / "configs" / "config.yaml"
    with open(config_path) as f:
        config = yaml.safe_load(f)

    # Create system with Langfuse enabled
    system = create_integrated_system(
        repo_path="/path/to/repo",
        config=config,
        enable_langfuse=True,
        langfuse_config={
            'public_key': 'pk-lf-...',  # Your Langfuse public key
            'secret_key': 'sk-lf-...',  # Your Langfuse secret key
            'host': 'https://cloud.langfuse.com'
        }
    )

    tracer = system['tracer']

    print("\n=á Langfuse tracing enabled!")
    print("   All LLM calls and tool executions will be traced to Langfuse")
    print("   View your traces at: https://cloud.langfuse.com")

    # Use the system normally - tracing happens automatically
    tools = system['tool_registry']
    result = tools.execute('structural_kb_search_by_semantics', query="test")

    print(f"\n Tool execution traced (success: {result.get('success', False)})")


def example_6_all_kb_tools():
    """
    Example 6: Showcase all KB query tools
    """
    print("\n" + "="*80)
    print("Example 6: All Available KB Query Tools")
    print("="*80)

    system = quick_setup("/path/to/repo")
    tools = system['tool_registry']

    kb_tools = [
        ('search_by_semantics', 'Natural language code search'),
        ('search_by_functionality', 'Find code by functional description'),
        ('find_similar_components', 'Find similar code components'),
        ('detect_duplicate_code', 'Detect code duplication'),
        ('find_design_patterns', 'Find design patterns (Singleton, Factory, etc.)'),
        ('detect_code_smells', 'Detect anti-patterns and code smells'),
        ('get_architecture_overview', 'Get high-level architecture overview'),
        ('get_module_boundaries', 'Identify module boundaries'),
        ('identify_cross_cutting_concerns', 'Find cross-cutting concerns'),
        ('trace_execution_path', 'Trace execution flow from entry point'),
        ('trace_data_flow', 'Trace data flow through code'),
        ('trace_request_lifecycle', 'Trace HTTP request lifecycle')
    ]

    print("\n=à  Available KB Query Tools:")
    print("-" * 80)

    for tool_name, description in kb_tools:
        full_name = f"structural_kb_{tool_name}"
        print(f"  {full_name}")
        print(f"    {description}")
        print()

    print("=¡ All these tools are now exposed and ready to use!")


if __name__ == "__main__":
    """
    Run all basic examples
    """
    print("\n" + "="*80)
    print("CodeFusion Basic Usage Examples")
    print("="*80)

    print("\n   NOTE: Update repo_path in examples before running!")
    print("\nExamples:")
    print("  1. Quick start with default setup")
    print("  2. Register custom knowledge agent")
    print("  3. Per-tool metrics tracking")
    print("  4. Multi-turn conversations with LlmTask")
    print("  5. Langfuse tracing integration")
    print("  6. All available KB query tools")

    # Uncomment to run:
    # example_1_quick_start()
    # example_2_custom_agent()
    # example_3_metrics_tracking()
    # example_4_llm_task()
    # example_5_langfuse_tracing()
    example_6_all_kb_tools()
