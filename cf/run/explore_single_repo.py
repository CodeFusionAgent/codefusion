"""Single repository exploration runner for CodeFusion."""

from typing import Dict, Any, Optional
from pathlib import Path

from ..config import CfConfig
from ..aci.repo import LocalCodeRepo
from ..kb.knowledge_base import create_knowledge_base
from ..indexer.code_indexer import CodeIndexer


def run_single_exploration(
    repo_path: str,
    config: Optional[CfConfig] = None,
    strategy: str = "react"
) -> Dict[str, Any]:
    """Run exploration on a single repository.
    
    Args:
        repo_path: Path to the repository to explore
        config: Configuration object (uses default if None)
        strategy: Exploration strategy to use
        
    Returns:
        Dictionary containing exploration results
    """
    if config is None:
        config = CfConfig()
    
    config.exploration_strategy = strategy
    config.repo_path = repo_path
    
    # Setup components
    repo = LocalCodeRepo(repo_path)
    kb = create_knowledge_base(config.kb_type, config.kb_path)
    indexer = CodeIndexer(repo, kb, config)
    
    # Run exploration
    results = indexer.index_repository()
    
    # Add summary information
    results.update({
        "repository_path": repo_path,
        "strategy_used": strategy,
        "kb_statistics": kb.get_statistics()
    })
    
    return results


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python -m cf.run.explore_single_repo <repo_path> [strategy]")
        sys.exit(1)
    
    repo_path = sys.argv[1]
    strategy = sys.argv[2] if len(sys.argv) > 2 else "react"
    
    print(f"Running single exploration on {repo_path} with {strategy} strategy...")
    results = run_single_exploration(repo_path, strategy=strategy)
    
    print(f"✅ Exploration completed!")
    print(f"📁 Files processed: {results['files_processed']}")
    print(f"🏗️ Entities created: {results['entities_created']}")
    print(f"🔗 Relationships: {results['relationships_created']}")