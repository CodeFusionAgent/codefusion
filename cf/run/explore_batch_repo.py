"""Batch repository exploration runner for CodeFusion."""

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

from ..config import CfConfig
from .run_single import run_single_exploration


def run_batch_exploration(
    repo_paths: List[str],
    config: Optional[CfConfig] = None,
    strategy: str = "react",
    max_workers: int = 4,
    output_file: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Run exploration on multiple repositories in parallel.

    Args:
        repo_paths: List of repository paths to explore
        config: Configuration object (uses default if None)
        strategy: Exploration strategy to use
        max_workers: Maximum number of parallel workers
        output_file: Optional file to save results

    Returns:
        List of exploration results for each repository
    """
    if config is None:
        config = CfConfig()

    results = []
    failed_repos = []

    print(f"🚀 Starting batch exploration of {len(repo_paths)} repositories...")
    print(f"👥 Using {max_workers} parallel workers")
    print(f"🧠 Strategy: {strategy}")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all exploration tasks
        future_to_repo = {
            executor.submit(
                run_single_exploration, repo_path, config, strategy
            ): repo_path
            for repo_path in repo_paths
        }

        # Collect results as they complete
        for future in as_completed(future_to_repo):
            repo_path = future_to_repo[future]
            try:
                result = future.result()
                results.append(result)
                print(
                    f"✅ Completed: {repo_path} ({result['entities_created']} entities)"
                )
            except Exception as e:
                error_result = {
                    "repository_path": repo_path,
                    "error": str(e),
                    "status": "failed",
                }
                failed_repos.append(error_result)
                print(f"❌ Failed: {repo_path} - {str(e)}")

    # Summary
    print("\n📊 Batch Exploration Summary:")
    print(f"✅ Successful: {len(results)}")
    print(f"❌ Failed: {len(failed_repos)}")

    if failed_repos:
        print("\nFailed repositories:")
        for failed in failed_repos:
            print(f"  - {failed['repository_path']}: {failed['error']}")

    # Save results if requested
    if output_file:
        all_results = {
            "successful": results,
            "failed": failed_repos,
            "summary": {
                "total_repos": len(repo_paths),
                "successful_count": len(results),
                "failed_count": len(failed_repos),
                "strategy_used": strategy,
            },
        }

        with open(output_file, "w") as f:
            json.dump(all_results, f, indent=2, default=str)
        print(f"💾 Results saved to: {output_file}")

    return results


def load_repo_list(file_path: str) -> List[str]:
    """Load repository paths from a file (one per line)."""
    with open(file_path, "r") as f:
        return [line.strip() for line in f if line.strip() and not line.startswith("#")]


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print(
            "Usage: python -m cf.run.run_batch <repo_list_file> [strategy] [max_workers]"
        )
        print("  repo_list_file: File containing repository paths (one per line)")
        print("  strategy: react, plan_act, or sense_act (default: react)")
        print("  max_workers: Number of parallel workers (default: 4)")
        sys.exit(1)

    repo_list_file = sys.argv[1]
    strategy = sys.argv[2] if len(sys.argv) > 2 else "react"
    max_workers = int(sys.argv[3]) if len(sys.argv) > 3 else 4

    try:
        repo_paths = load_repo_list(repo_list_file)
        output_file = f"batch_results_{strategy}.json"

        results = run_batch_exploration(
            repo_paths=repo_paths,
            strategy=strategy,
            max_workers=max_workers,
            output_file=output_file,
        )

        print("\n🎉 Batch exploration completed!")

    except FileNotFoundError:
        print(f"❌ Error: Repository list file '{repo_list_file}' not found")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        sys.exit(1)
