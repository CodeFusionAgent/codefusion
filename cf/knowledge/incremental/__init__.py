"""
Incremental Knowledge Base Updates

Provides efficient KB updates when files change:
- File change detection (modified, added, deleted)
- Differential updates (only re-parse changed files)
- Change tracking and versioning

Dramatically improves performance for long-lived projects:
- Without incremental: Re-scan 100K files (90 min)
- With incremental: Update 5 files (5 seconds)
"""

from cf.knowledge.incremental.file_watcher import FileChangeDetector, ChangeSet
from cf.knowledge.incremental.differential import IncrementalKBUpdater

__all__ = [
    "FileChangeDetector",
    "ChangeSet",
    "IncrementalKBUpdater"
]
