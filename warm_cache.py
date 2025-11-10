#!/usr/bin/env python3
"""
Warm Cache Script

Pre-analyzes repository files and builds the file summary cache.
Use this before running evaluation questions to test warm vs cold performance.

Usage:
    python warm_cache.py /path/to/repo [--max-files N] [--clear-first]
"""

import sys
import argparse
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from cf.configs.config_mgr import ConfigManager
from cf.agents.code import CodeAgent
from cf.cache.file_summary_cache import FileSummaryCache


def main():
    parser = argparse.ArgumentParser(
        description="Warm up file summary cache by pre-analyzing repository files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Warm cache for Django repo (default: 50 files)
  python warm_cache.py /path/to/django

  # Warm cache with specific file limit
  python warm_cache.py /path/to/django --max-files 100

  # Clear existing cache first, then warm
  python warm_cache.py /path/to/django --clear-first

  # Use custom config
  python warm_cache.py /path/to/django --config my_config.yaml

After warming cache, run questions:
  python run_code_agent_only.py /path/to/django "How does admin work?"
        """
    )

    parser.add_argument('repo_path', help='Repository path to analyze')
    parser.add_argument('--max-files', type=int, default=50,
                       help='Maximum files to analyze (default: 50)')
    parser.add_argument('--clear-first', action='store_true',
                       help='Clear existing cache before warming')
    parser.add_argument('--config', default='cf/configs/config.yaml',
                       help='Config file path (default: cf/configs/config.yaml)')
    parser.add_argument('--disable-cache', action='store_true',
                       help='Disable cache (for testing performance without cache)')

    args = parser.parse_args()

    print('=' * 80)
    print('🔥 Cache Warming Script')
    print('=' * 80)
    print(f'📁 Repository: {args.repo_path}')
    print(f'📊 Max files: {args.max_files}')
    print(f'⚙️  Config: {args.config}')
    print('=' * 80)
    print()

    # Load configuration
    config_mgr = ConfigManager(args.config)
    config = config_mgr.get_config()

    # Override max files in config
    config.setdefault('repo', {})['max_analysis_files'] = args.max_files

    # Disable cache if requested
    if args.disable_cache:
        config['cache']['enabled'] = False
        print('⚠️  Cache DISABLED for this run\n')

    # Clear cache if requested
    if args.clear_first:
        cache_dir = config.get('cache', {}).get('cache_dir', 'cf_cache')
        cache = FileSummaryCache(f"{cache_dir}/file_summaries")
        print(f'🗑️  Clearing existing cache...')
        cache.clear()
        print()

    # Initialize CodeAgent
    print('🚀 Initializing CodeAgent...\n')
    agent = CodeAgent(args.repo_path, config)

    # Warm the cache by discovering and analyzing files
    print(f'🔍 Discovering repository files...\n')
    start_time = time.time()

    # Use a generic question to trigger file discovery and analysis
    warm_question = "Analyze the codebase architecture and key components"

    print(f'📝 Warming cache with question: "{warm_question}"\n')
    print('=' * 80)
    print('CACHE WARMING IN PROGRESS')
    print('=' * 80)
    print()

    try:
        result = agent.analyze(warm_question)

        warm_time = time.time() - start_time

        print()
        print('=' * 80)
        print('✅ CACHE WARMING COMPLETE')
        print('=' * 80)
        print(f'⏱️  Total time: {warm_time:.2f}s ({warm_time/60:.2f}m)')
        print(f'📄 Files analyzed: {result.get("files_analyzed", 0)}')
        print(f'💡 Insights gathered: {len(result.get("insights", []))}')

        # Show cache statistics
        if hasattr(agent, 'file_cache') and agent.file_cache.enabled:
            cache_stats = agent.file_cache.get_stats()
            print()
            print('📊 Cache Statistics:')
            print(f'   Total requests: {cache_stats["total_requests"]}')
            print(f'   Cache hits: {cache_stats["hits"]}')
            print(f'   Cache misses: {cache_stats["misses"]}')
            print(f'   Cache expired: {cache_stats["expired"]}')
            print(f'   Hit rate: {cache_stats["hit_rate"]:.1%}')
            print(f'   Cache size: {cache_stats["cache_size"]} entries stored')

            # Calculate estimated savings
            if cache_stats["cache_size"] > 0:
                cache_dir = config.get('cache', {}).get('cache_dir', 'cf_cache')
                cache_path = Path(cache_dir) / 'file_summaries'
                print()
                print(f'💾 Cache location: {cache_path.absolute()}')

                # Estimate tokens saved
                if hasattr(agent, 'file_analysis_metrics'):
                    total_tokens = sum(m.get('total_tokens', 0) for m in agent.file_analysis_metrics)
                    avg_tokens_per_file = total_tokens / len(agent.file_analysis_metrics) if agent.file_analysis_metrics else 0
                    estimated_tokens_saved = cache_stats["cache_size"] * avg_tokens_per_file

                    print()
                    print('💰 Estimated Savings (for next run with warm cache):')
                    print(f'   Tokens saved: ~{estimated_tokens_saved:,.0f} tokens')
                    print(f'   Time saved: ~{estimated_tokens_saved * 0.01:.1f}s ({estimated_tokens_saved * 0.01 / 60:.1f}m)')
                    print(f'   Cost saved: ~${estimated_tokens_saved * 0.000002:.4f} (at $2/1M tokens)')

        # Show performance metrics if available
        if hasattr(agent, 'file_analysis_metrics') and agent.file_analysis_metrics:
            print()
            print('⚡ Performance Breakdown:')
            total_tokens = sum(m.get('total_tokens', 0) for m in agent.file_analysis_metrics)
            total_llm_time = sum(m.get('total_duration_ms', 0) for m in agent.file_analysis_metrics) / 1000

            print(f'   Total tokens: {total_tokens:,}')
            print(f'   Total LLM time: {total_llm_time:.2f}s ({total_llm_time/60:.2f}m)')
            print(f'   Avg tokens/file: {total_tokens/len(agent.file_analysis_metrics):.0f}')
            print(f'   Avg time/file: {total_llm_time/len(agent.file_analysis_metrics):.2f}s')

            # Show model used
            fast_model = config.get('llm', {}).get('fast_model', 'N/A')
            main_model = config.get('llm', {}).get('model', 'N/A')
            print()
            print(f'🤖 Models Used:')
            print(f'   Fast model (summaries): {fast_model}')
            print(f'   Main model (synthesis): {main_model}')

        print()
        print('=' * 80)
        print('🎉 Cache is now warmed up!')
        print('=' * 80)
        print()
        print('Next steps:')
        print('  1. Run questions with warm cache (should be fast):')
        print(f'     python run_code_agent_only.py {args.repo_path} "Your question"')
        print()
        print('  2. Compare with cold cache by clearing first:')
        print(f'     python warm_cache.py {args.repo_path} --clear-first')
        print()

    except KeyboardInterrupt:
        print('\n\n⚠️  Interrupted by user')
        print(f'⏱️  Partial warming time: {time.time() - start_time:.2f}s')

        if hasattr(agent, 'file_cache'):
            cache_stats = agent.file_cache.get_stats()
            if cache_stats['total_requests'] > 0:
                print(f'📊 Partial cache: {cache_stats["cache_size"]} entries stored')

        sys.exit(1)

    except Exception as e:
        print(f'\n\n❌ Error during cache warming: {e}')
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
