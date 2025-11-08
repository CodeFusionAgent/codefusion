#!/usr/bin/env python3
"""
Cache Performance Comparison Script

Runs the same question with cold cache (disabled) and warm cache (enabled) to compare performance.

Usage:
    python compare_cache_performance.py /path/to/repo "Your question"
"""

import sys
import argparse
import time
from pathlib import Path
import copy
import io
import contextlib

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from cf.configs.config_mgr import ConfigManager
from cf.agents.code import CodeAgent


def run_with_config(repo_path: str, question: str, config: dict, run_name: str) -> dict:
    """Run analysis with given config and return metrics"""
    print(f'\n{"=" * 80}')
    print(f'🔬 {run_name}')
    print(f'{"=" * 80}\n')

    agent = CodeAgent(repo_path, config)
    start_time = time.time()

    try:
        result = agent.analyze(question)
        duration = time.time() - start_time
        narrative = result.get('narrative', '')
        # Gather metrics
        metrics = {
            'success': result.get('success', False),
            'duration': duration,
            'files_analyzed': result.get('files_analyzed', 0),
            'insights_count': len(result.get('insights', [])),
            'iterations': getattr(agent, 'iteration', 0),
            'narrative': narrative,
            'narrative_length': len(narrative)
        }

        # Cache stats
        if hasattr(agent, 'file_cache') and agent.file_cache.enabled:
            cache_stats = agent.file_cache.get_stats()
            metrics['cache_hits'] = cache_stats['hits']
            metrics['cache_misses'] = cache_stats['misses']
            metrics['cache_expired'] = cache_stats['expired']
            metrics['cache_hit_rate'] = cache_stats['hit_rate']
            metrics['cache_enabled'] = True
        else:
            metrics['cache_enabled'] = False
            metrics['cache_hits'] = 0
            metrics['cache_misses'] = 0

        # Token metrics from file analysis
        file_tokens = 0
        file_llm_time = 0
        if hasattr(agent, 'file_analysis_metrics') and agent.file_analysis_metrics:
            file_tokens = sum(m.get('total_tokens', 0) for m in agent.file_analysis_metrics)
            file_llm_time = sum(m.get('total_duration_ms', 0) for m in agent.file_analysis_metrics) / 1000
            metrics['avg_tokens_per_file'] = file_tokens / len(agent.file_analysis_metrics)
            metrics['avg_time_per_file'] = file_llm_time / len(agent.file_analysis_metrics)

        # Add synthesis metrics
        synthesis_tokens = 0
        synthesis_time = 0
        if hasattr(agent, 'synthesis_metrics'):
            synthesis_tokens = agent.synthesis_metrics.get('total_tokens', 0)
            synthesis_time = agent.synthesis_metrics.get('duration_ms', 0) / 1000

        # Total tokens = file analysis + synthesis
        metrics['file_analysis_tokens'] = file_tokens
        metrics['synthesis_tokens'] = synthesis_tokens
        metrics['total_tokens'] = file_tokens + synthesis_tokens
        metrics['total_llm_time'] = file_llm_time + synthesis_time

        return metrics

    except Exception as e:
        print(f'❌ Error: {e}')
        import traceback
        traceback.print_exc()
        return {'success': False, 'error': str(e)}


def print_comparison(cold_metrics: dict, warm_metrics: dict):
    """Print detailed comparison between cold and warm runs"""
    print(f'\n{"=" * 80}')
    print('📊 PERFORMANCE COMPARISON')
    print(f'{"=" * 80}\n')

    if not cold_metrics.get('success') or not warm_metrics.get('success'):
        print('❌ One or both runs failed, cannot compare')
        return

    # Time comparison
    print('⏱️  EXECUTION TIME:')
    cold_time = cold_metrics['duration']
    warm_time = warm_metrics['duration']
    speedup = cold_time / warm_time if warm_time > 0 else 0
    time_saved = cold_time - warm_time

    print(f'   Cold cache (disabled): {cold_time:.2f}s ({cold_time/60:.2f}m)')
    print(f'   Warm cache (enabled):  {warm_time:.2f}s ({warm_time/60:.2f}m)')
    print(f'   ⚡ Speedup: {speedup:.2f}x faster')
    print(f'   💰 Time saved: {time_saved:.2f}s ({time_saved/60:.2f}m)')

    # Cache statistics
    print(f'\n📦 CACHE PERFORMANCE:')
    print(f'   Cold run - Cache: disabled')
    print(f'   Warm run - Cache hits: {warm_metrics.get("cache_hits", 0)}')
    print(f'   Warm run - Cache misses: {warm_metrics.get("cache_misses", 0)}')
    print(f'   Warm run - Hit rate: {warm_metrics.get("cache_hit_rate", 0):.1%}')

    # Token comparison with breakdown
    if 'total_tokens' in cold_metrics and 'total_tokens' in warm_metrics:
        print(f'\n💬 TOKEN USAGE:')
        cold_tokens = cold_metrics['total_tokens']
        warm_tokens = warm_metrics['total_tokens']
        tokens_saved = cold_tokens - warm_tokens

        print(f'   Cold cache: {cold_tokens:,} tokens')
        print(f'     - File analysis: {cold_metrics.get("file_analysis_tokens", 0):,} tokens')
        print(f'     - Synthesis: {cold_metrics.get("synthesis_tokens", 0):,} tokens')
        print(f'   Warm cache: {warm_tokens:,} tokens')
        print(f'     - File analysis: {warm_metrics.get("file_analysis_tokens", 0):,} tokens (cached)')
        print(f'     - Synthesis: {warm_metrics.get("synthesis_tokens", 0):,} tokens')
        if cold_tokens > 0:
            print(f'   💰 Tokens saved: {tokens_saved:,} tokens ({(tokens_saved/cold_tokens)*100:.1f}% reduction)')
        else:
            print(f'   💰 Tokens saved: {tokens_saved:,} tokens')
        print(f'   💵 Cost saved: ~${tokens_saved * 0.000002:.4f} (at $2/1M tokens)')

        # LLM time breakdown
        if 'total_llm_time' in cold_metrics:
            print(f'\n🤖 LLM PROCESSING TIME:')
            cold_llm_time = cold_metrics['total_llm_time']
            warm_llm_time = warm_metrics.get('total_llm_time', 0)
            llm_time_saved = cold_llm_time - warm_llm_time

            print(f'   Cold cache: {cold_llm_time:.2f}s ({cold_llm_time/60:.2f}m)')
            print(f'   Warm cache: {warm_llm_time:.2f}s ({warm_llm_time/60:.2f}m)')
            print(f'   Time saved: {llm_time_saved:.2f}s ({llm_time_saved/60:.2f}m)')
            print(f'   LLM time as % of total:')
            print(f'     Cold: {(cold_llm_time/cold_time)*100:.1f}%')
            print(f'     Warm: {(warm_llm_time/warm_time)*100:.1f}%' if warm_time > 0 else '     Warm: N/A')

    # Quality comparison
    print(f'\n📈 ANALYSIS QUALITY:')
    print(f'   Files analyzed:')
    print(f'     Cold: {cold_metrics.get("files_analyzed", 0)}')
    print(f'     Warm: {warm_metrics.get("files_analyzed", 0)}')
    print(f'   Insights gathered:')
    print(f'     Cold: {cold_metrics.get("insights_count", 0)}')
    print(f'     Warm: {warm_metrics.get("insights_count", 0)}')
    print(f'   Iterations:')
    print(f'     Cold: {cold_metrics.get("iterations", 0)}')
    print(f'     Warm: {warm_metrics.get("iterations", 0)}')
    cold_iters = cold_metrics.get("iterations", 0)
    warm_iters = warm_metrics.get("iterations", 0)
    if warm_iters > cold_iters:
        print(f'     ⚠️  WARNING: Warm cache took MORE iterations ({warm_iters} vs {cold_iters})')
        print(f'     This suggests premature early stopping - consider adjusting thresholds')
    elif warm_iters < cold_iters:
        print(f'     ✅ Warm cache converged faster ({warm_iters} vs {cold_iters})')
    print(f'   Narrative length:')
    print(f'     Cold: {cold_metrics.get("narrative_length", 0)} chars')
    print(f'     Warm: {warm_metrics.get("narrative_length", 0)} chars')

    # Summary
    print(f'\n{"=" * 80}')
    print('🎯 SUMMARY:')
    print(f'{"=" * 80}')
    print(f'   Warm cache is {speedup:.2f}x FASTER than cold cache')
    print(f'   Saves {time_saved:.1f}s ({time_saved/60:.1f}m) per question')

    if speedup >= 10:
        print(f'   🚀 EXCELLENT: >10x speedup achieved!')
    elif speedup >= 5:
        print(f'   ✅ GREAT: 5-10x speedup achieved')
    elif speedup >= 2:
        print(f'   👍 GOOD: 2-5x speedup achieved')
    else:
        print(f'   ⚠️  MODEST: <2x speedup (check cache configuration)')

    # Print narratives
    print(f'\n{"=" * 80}')
    print('📖 GENERATED ANSWERS')
    print(f'{"=" * 80}')

    print(f'\n{"─" * 80}')
    print('🧊 COLD CACHE ANSWER:')
    print(f'{"─" * 80}')
    print(cold_metrics.get('narrative', 'No narrative generated'))

    print(f'\n{"─" * 80}')
    print('🔥 WARM CACHE ANSWER:')
    print(f'{"─" * 80}')
    print(warm_metrics.get('narrative', 'No narrative generated'))

    print()


def main():
    parser = argparse.ArgumentParser(
        description="Compare cold vs warm cache performance",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Compare performance for a Django question
  python compare_cache_performance.py /path/to/django "How does the admin interface work?"

  # Use custom config
  python compare_cache_performance.py /path/to/django "Question" --config my_config.yaml

  # Skip cold run (only test warm cache)
  python compare_cache_performance.py /path/to/django "Question" --skip-cold

  # Skip warm run (only test cold cache)
  python compare_cache_performance.py /path/to/django "Question" --skip-warm

This script:
1. Runs question with cache DISABLED (cold cache)
2. Runs same question with cache ENABLED (warm cache - uses cache from previous runs)
3. Compares performance metrics

Note: Run warm_cache.py first to pre-populate the cache for best warm performance.
        """
    )

    parser.add_argument('repo_path', help='Repository path to analyze')
    parser.add_argument('question', help='Question to ask')
    parser.add_argument('--config', default='cf/configs/config.yaml',
                       help='Config file path (default: cf/configs/config.yaml)')
    parser.add_argument('--skip-cold', action='store_true',
                       help='Skip cold run (cache disabled)')
    parser.add_argument('--skip-warm', action='store_true',
                       help='Skip warm run (cache enabled)')
    parser.add_argument('--output', '-o', type=str,
                       help='Save comparison results to file (e.g., comparison_results.txt)')

    args = parser.parse_args()

    print('=' * 80)
    print('🔬 Cache Performance Comparison')
    print('=' * 80)
    print(f'📁 Repository: {args.repo_path}')
    print(f'❓ Question: {args.question}')
    print(f'⚙️  Config: {args.config}')
    print('=' * 80)

    # Load config
    config_mgr = ConfigManager(args.config)
    base_config = config_mgr.get_config()

    cold_metrics = {}
    warm_metrics = {}

    # Cold run (cache DISABLED)
    if not args.skip_cold:
        cold_config = copy.deepcopy(base_config)
        # Disable BOTH semantic cache and file summary cache
        cold_config['cache']['enabled'] = False
        cold_config['cache'].setdefault('file_summary_cache', {})['enabled'] = False

        cold_metrics = run_with_config(
            args.repo_path,
            args.question,
            cold_config,
            'RUN 1: COLD CACHE (cache disabled - no file summary reuse)'
        )

        if not cold_metrics.get('success'):
            print('\n❌ Cold run failed, aborting comparison')
            sys.exit(1)

        print(f'\n✅ Cold run complete: {cold_metrics["duration"]:.2f}s ({cold_metrics["duration"]/60:.2f}m)')
        time.sleep(2)  # Brief pause between runs

    # Warm run (cache ENABLED)
    if not args.skip_warm:
        warm_config = copy.deepcopy(base_config)
        # Enable file summary cache (semantic cache stays as configured)
        warm_config['cache'].setdefault('file_summary_cache', {})['enabled'] = True

        warm_metrics = run_with_config(
            args.repo_path,
            args.question,
            warm_config,
            'RUN 2: WARM CACHE (cache enabled - reuses file summaries)'
        )

        if not warm_metrics.get('success'):
            print('\n❌ Warm run failed')
            sys.exit(1)

        print(f'\n✅ Warm run complete: {warm_metrics["duration"]:.2f}s ({warm_metrics["duration"]/60:.2f}m)')

    # Print comparison
    comparison_output = None
    if cold_metrics and warm_metrics:
        # Capture output if saving to file
        if args.output:

            output_buffer = io.StringIO()
            with contextlib.redirect_stdout(output_buffer):
                print_comparison(cold_metrics, warm_metrics)
            comparison_output = output_buffer.getvalue()

            # Print to console too
            print(comparison_output)

            # Save to file
            try:
                with open(args.output, 'w') as f:
                    f.write(f"Question: {args.question}\n")
                    f.write(f"Repository: {args.repo_path}\n")
                    f.write(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write("\n" + comparison_output)
                print(f"\n💾 Comparison saved to: {args.output}")
            except Exception as e:
                print(f"\n⚠️  Failed to save to file: {e}")
        else:
            print_comparison(cold_metrics, warm_metrics)
    elif cold_metrics:
        print(f'\n✅ Cold run completed in {cold_metrics["duration"]:.2f}s ({cold_metrics["duration"]/60:.2f}m)')
        print('   (Run again without --skip-warm to compare with warm cache)')
    elif warm_metrics:
        print(f'\n✅ Warm run completed in {warm_metrics["duration"]:.2f}s ({warm_metrics["duration"]/60:.2f}m)')
        print('   (Run again without --skip-cold to compare with cold cache)')


if __name__ == '__main__':
    main()
