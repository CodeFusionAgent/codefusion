"""
File Change Detection

Detects changes in repository files for incremental KB updates:
- Compare current state with last scan
- Identify added, modified, deleted files
- Use file hashes for accurate change detection
- Persist state for cross-session tracking

Enables efficient incremental updates instead of full re-scans.
"""

import os
import json
import hashlib
from typing import Dict, Set, List
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ChangeSet:
    """
    Set of file changes detected between scans.

    Attributes:
        added: Newly created files
        modified: Files that changed content
        deleted: Files that were removed
    """
    added: Set[str] = field(default_factory=set)
    modified: Set[str] = field(default_factory=set)
    deleted: Set[str] = field(default_factory=set)

    def has_changes(self) -> bool:
        """Check if any changes exist"""
        return bool(self.added or self.modified or self.deleted)

    def total_changes(self) -> int:
        """Total number of changed files"""
        return len(self.added) + len(self.modified) + len(self.deleted)

    def to_dict(self) -> Dict[str, List[str]]:
        """Convert to dictionary"""
        return {
            'added': list(self.added),
            'modified': list(self.modified),
            'deleted': list(self.deleted)
        }

    def __str__(self) -> str:
        return f"ChangeSet(added={len(self.added)}, modified={len(self.modified)}, deleted={len(self.deleted)})"


class FileChangeDetector:
    """
    Detect file changes in a repository.

    Tracks file states (path, mtime, hash) and compares between scans
    to identify changes.
    """

    def __init__(self, repo_path: str, state_file: str = None):
        """
        Initialize file change detector.

        Args:
            repo_path: Root path of repository
            state_file: Path to persist state (default: repo_path/.codefusion/file_state.json)
        """
        self.repo_path = repo_path

        # State file for persistence
        if state_file is None:
            state_dir = os.path.join(repo_path, '.codefusion')
            os.makedirs(state_dir, exist_ok=True)
            state_file = os.path.join(state_dir, 'file_state.json')

        self.state_file = state_file

        # File state: path -> {mtime, hash, size}
        self.last_scan: Dict[str, Dict[str, any]] = {}

        # Load previous state if exists
        self._load_state()

        # Extensions to track (configurable)
        self.tracked_extensions = {'.py', '.js', '.ts', '.go', '.java', '.cpp', '.c', '.h'}

    def _load_state(self):
        """Load previous file state from disk"""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    self.last_scan = json.load(f)
                print(f"✅ Loaded file state: {len(self.last_scan)} files tracked")
            except Exception as e:
                print(f"⚠️ Failed to load file state: {e}")
                self.last_scan = {}
        else:
            print("ℹ️ No previous file state found")

    def _save_state(self):
        """Save current file state to disk"""
        try:
            os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
            with open(self.state_file, 'w') as f:
                json.dump(self.last_scan, f, indent=2)
            print(f"✅ Saved file state: {len(self.last_scan)} files")
        except Exception as e:
            print(f"❌ Failed to save file state: {e}")

    def _calculate_file_hash(self, file_path: str) -> str:
        """
        Calculate MD5 hash of file content.

        More accurate than mtime for detecting changes.

        Args:
            file_path: Absolute path to file

        Returns:
            MD5 hash hex string
        """
        try:
            with open(file_path, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception as e:
            print(f"⚠️ Failed to hash {file_path}: {e}")
            return ""

    def _scan_files(self) -> Dict[str, Dict[str, any]]:
        """
        Scan repository and build current file state.

        Returns:
            Dictionary mapping file paths to {mtime, hash, size}
        """
        current_state = {}

        for root, dirs, files in os.walk(self.repo_path):
            # Skip hidden directories and common ignore patterns
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in {
                'node_modules', '__pycache__', 'venv', 'env', 'dist', 'build', 'target'
            }]

            for file in files:
                # Only track files with tracked extensions
                _, ext = os.path.splitext(file)
                if ext not in self.tracked_extensions:
                    continue

                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, self.repo_path)

                try:
                    stat = os.stat(file_path)

                    current_state[rel_path] = {
                        'mtime': stat.st_mtime,
                        'size': stat.st_size,
                        'hash': self._calculate_file_hash(file_path)
                    }
                except Exception as e:
                    print(f"⚠️ Failed to stat {rel_path}: {e}")

        return current_state

    def detect_changes(self, save_state: bool = True) -> ChangeSet:
        """
        Detect changes since last scan.

        Compares current repository state with last saved state.

        Args:
            save_state: Whether to save current state for next comparison

        Returns:
            ChangeSet with added, modified, deleted files
        """
        print("🔍 Scanning repository for changes...")

        # Scan current state
        current_state = self._scan_files()

        # Compare with last scan
        change_set = ChangeSet()

        # Find added and modified files
        for path, current_info in current_state.items():
            if path not in self.last_scan:
                # New file
                change_set.added.add(path)
            else:
                # Check if modified
                last_info = self.last_scan[path]

                # First check size and mtime (fast)
                if (current_info['size'] != last_info['size'] or
                    current_info['mtime'] != last_info['mtime']):

                    # Verify with hash (accurate)
                    if current_info['hash'] != last_info['hash']:
                        change_set.modified.add(path)

        # Find deleted files
        for path in self.last_scan:
            if path not in current_state:
                change_set.deleted.add(path)

        # Update state
        if save_state:
            self.last_scan = current_state
            self._save_state()

        print(f"✅ {change_set}")
        return change_set

    def force_scan(self):
        """
        Force a full scan and update state.

        Use this for initial KB build or when you want to reset tracking.
        """
        print("🔄 Performing full repository scan...")
        self.last_scan = self._scan_files()
        self._save_state()
        print(f"✅ Full scan complete: {len(self.last_scan)} files tracked")

    def get_tracked_files(self) -> List[str]:
        """
        Get list of currently tracked files.

        Returns:
            List of relative file paths
        """
        return list(self.last_scan.keys())

    def is_file_tracked(self, file_path: str) -> bool:
        """
        Check if a file is currently tracked.

        Args:
            file_path: Relative path from repo root

        Returns:
            True if tracked
        """
        return file_path in self.last_scan

    def add_extension(self, extension: str):
        """
        Add file extension to track.

        Args:
            extension: Extension (e.g., '.rs' for Rust)
        """
        if not extension.startswith('.'):
            extension = '.' + extension
        self.tracked_extensions.add(extension)
        print(f"✅ Now tracking {extension} files")

    def remove_extension(self, extension: str):
        """
        Remove file extension from tracking.

        Args:
            extension: Extension to remove
        """
        if not extension.startswith('.'):
            extension = '.' + extension
        self.tracked_extensions.discard(extension)
        print(f"✅ Stopped tracking {extension} files")

    def get_file_info(self, file_path: str) -> Dict[str, any]:
        """
        Get tracked info for a file.

        Args:
            file_path: Relative path from repo root

        Returns:
            Dictionary with mtime, hash, size or None if not tracked
        """
        return self.last_scan.get(file_path)
