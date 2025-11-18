"""
Knowledge Base Manager

Handles KB lifecycle: build, load, update, and query operations.
Extracted from StructuralPipeline to improve maintainability.
"""

import os
import time
import hashlib
import concurrent.futures
from typing import Dict, List, Any, Optional
from pathlib import Path

from cf.knowledge.structural.schema import StructuralData, BuildResult
from cf.knowledge.structural.ast_parser import PythonASTParser
from cf.knowledge.structural.multi_lang_parser import MultiLanguageParser
from cf.knowledge.structural.neo4j_client import Neo4jKnowledgeBase
from cf.knowledge.incremental.file_watcher import FileChangeDetector
from cf.knowledge.incremental.differential import IncrementalKBUpdater


class KnowledgeBaseManager:
    """
    Manages knowledge base lifecycle and operations.

    Responsibilities:
    - KB initialization (build/load)
    - File parsing (AST analysis)
    - Incremental updates
    - Repository statistics
    """

    def __init__(self, repo_path: str, config: Dict[str, Any], kb: Neo4jKnowledgeBase = None):
        self.repo_path = repo_path
        self.config = config
        self.kb = kb
        self.repo_id = self._generate_repo_id(repo_path)

        # Incremental update support
        self.file_watcher = None
        self.incremental_updater = None

        # Store last build's structural data for enhanced layers
        self._last_structural_data = []

    def _generate_repo_id(self, repo_path: str) -> str:
        """Generate unique repo ID from path"""
        abs_path = os.path.abspath(repo_path)
        return hashlib.md5(abs_path.encode()).hexdigest()[:12]

    def is_available(self) -> bool:
        """Check if KB is available"""
        return self.kb is not None

    def exists(self) -> bool:
        """Check if KB exists (has data)"""
        if not self.kb:
            return False
        try:
            stats = self.kb.get_repository_stats(self.repo_id)
            return stats.get('files', 0) > 0  # Note: key is 'files', not 'total_files'
        except Exception:
            return False

    def parse_file(self, file_path: str) -> Optional[StructuralData]:
        """Parse a file and extract structural data (auto-detect language)"""
        try:
            # Detect language from extension
            ext = os.path.splitext(file_path)[1].lower()

            if ext == '.py':
                parser = PythonASTParser(self.repo_path, self.repo_id)
                return parser.parse_file(file_path)
            else:
                # Use multi-language parser for other languages
                parser = MultiLanguageParser(self.repo_path, self.repo_id)
                return parser.parse_file(file_path)

        except Exception as e:
            print(f"⚠️ [KB_MANAGER] Failed to parse {file_path}: {e}")
            return None

    def build(self, force_rebuild: bool = False) -> BuildResult:
        """
        Build knowledge base from source files.

        Args:
            force_rebuild: Force rebuild even if KB exists

        Returns:
            BuildResult with statistics
        """
        if not self.kb:
            return BuildResult(
                success=False,
                total_files=0,
                total_functions=0,
                total_classes=0,
                build_time_seconds=0,
                error="KB not initialized"
            )

        start_time = time.time()

        # Delete existing KB if force rebuild
        if force_rebuild and self.exists():
            print("🗑️  [KB_MANAGER] Force rebuild - deleting existing KB...")
            self.kb.delete_repository(self.repo_id)

        # Check if KB exists (after potential deletion)
        if not force_rebuild and self.exists():
            print("✅ [KB_MANAGER] KB already exists, skipping build")
            stats = self.get_stats()
            total_files = stats.get('files', 0)
            return BuildResult(
                total_files=total_files,
                total_functions=stats.get('functions', 0),
                total_classes=stats.get('classes', 0),
                total_variables=stats.get('variables', 0),
                total_modules=stats.get('modules', 0),
                total_relationships=stats.get('relationships', 0),
                build_time_seconds=time.time() - start_time,
                files_per_second=0
            )

        print("🔨 [KB_MANAGER] Building knowledge base...")

        # Get source files
        source_files = self._get_source_files()
        print(f"   Found {len(source_files)} source files")

        # Parse files in parallel
        build_config = self.config.get('knowledge_base', {}).get('build', {})
        max_workers = build_config.get('parallel_workers', 10)

        structural_data_list = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(self.parse_file, f): f for f in source_files}

            for future in concurrent.futures.as_completed(futures):
                file_path = futures[future]
                try:
                    data = future.result()
                    if data:
                        structural_data_list.append(data)
                except Exception as e:
                    print(f"⚠️ [KB_MANAGER] Error parsing {file_path}: {e}")

        print(f"   Parsed {len(structural_data_list)} files successfully")

        # Populate KB
        print(f"   Inserting {len(structural_data_list)} files into Neo4j...")
        for i, structural_data in enumerate(structural_data_list, 1):
            try:
                self.kb.insert_structural_data(structural_data)
                if i % 100 == 0:
                    print(f"   Inserted {i}/{len(structural_data_list)} files...")
            except Exception as e:
                print(f"⚠️ [KB_MANAGER] Failed to insert {structural_data.file_node.path}: {e}")

        # Store structural data for enhanced layers (semantic, patterns, etc.)
        self._last_structural_data = structural_data_list

        build_time = time.time() - start_time
        stats = self.get_stats()

        print(f"✅ [KB_MANAGER] KB built in {build_time:.1f}s")

        # Note: stats keys are 'files', 'functions', 'classes', 'relationships'
        total_files = stats.get('files', 0)
        files_per_sec = total_files / build_time if build_time > 0 else 0

        return BuildResult(
            total_files=total_files,
            total_functions=stats.get('functions', 0),
            total_classes=stats.get('classes', 0),
            total_variables=stats.get('variables', 0),  # Not tracked yet
            total_modules=stats.get('modules', 0),  # Not tracked yet
            total_relationships=stats.get('relationships', 0),
            build_time_seconds=build_time,
            files_per_second=files_per_sec
        )

    def update(self) -> Dict[str, Any]:
        """Incrementally update KB with changed files"""
        if not self.kb:
            return {'success': False, 'error': 'KB not initialized'}

        incremental_config = self.config.get('knowledge_base', {}).get('incremental', {})
        if not incremental_config.get('enabled', False):
            return {'success': False, 'error': 'Incremental updates not enabled'}

        # Initialize file watcher if needed
        if not self.file_watcher:
            self.file_watcher = FileChangeDetector(
                self.repo_path,
                use_hashing=incremental_config.get('use_file_hashing', True)
            )

        # Initialize incremental updater
        if not self.incremental_updater:
            self.incremental_updater = IncrementalKBUpdater(self.kb, self.repo_id)

        # Detect changes
        changes = self.file_watcher.detect_changes()
        if not changes.has_changes():
            return {'success': True, 'changes': 0}

        # Parse changed files
        structural_data_list = []
        for file_path in changes.modified_files + changes.added_files:
            data = self.parse_file(file_path)
            if data:
                structural_data_list.append(data)

        # Update KB
        self.incremental_updater.update(structural_data_list, changes.deleted_files)

        return {
            'success': True,
            'changes': len(changes.modified_files) + len(changes.added_files) + len(changes.deleted_files),
            'added': len(changes.added_files),
            'modified': len(changes.modified_files),
            'deleted': len(changes.deleted_files)
        }

    def _get_source_files(self) -> List[str]:
        """Get all source files in repository"""
        repo_config = self.config.get('repo', {})
        source_exts = set(e.lstrip('.') for e in repo_config.get('source_code_extensions', ['.py']))
        excluded_dirs = set(repo_config.get('excluded_dirs', []))

        source_files = []
        for root, dirs, files in os.walk(self.repo_path):
            # Filter excluded directories
            dirs[:] = [d for d in dirs if d not in excluded_dirs]

            for file in files:
                ext = file.rsplit('.', 1)[-1] if '.' in file else ''
                if ext in source_exts:
                    source_files.append(os.path.join(root, file))

        return source_files

    def get_stats(self) -> Dict[str, Any]:
        """Get repository statistics from KB"""
        if not self.kb:
            return {}

        try:
            return self.kb.get_repository_stats(self.repo_id)
        except Exception as e:
            print(f"⚠️ [KB_MANAGER] Failed to get stats: {e}")
            return {}

    def get_structural_data(self) -> List[Any]:
        """
        Get structural data from last build.

        Used by enhanced layers (semantic, patterns, etc.) to build their indices.

        Returns:
            List of StructuralData objects from last KB build
        """
        return self._last_structural_data

    def lookup_file_path(self, qualified_name: str) -> Optional[str]:
        """Look up file path for a qualified name (e.g., module.Class.method)"""
        if not self.kb:
            return None

        try:
            # Query KB for function or class
            query = """
            MATCH (n {qualified_name: $qname, repo_id: $repo_id})
            WHERE n:Function OR n:Class
            RETURN n.file_path as file_path
            LIMIT 1
            """
            result = self.kb.execute_query(query, {'qname': qualified_name, 'repo_id': self.repo_id})

            if result.records:
                return result.records[0]['file_path']
        except Exception as e:
            print(f"⚠️ [KB_MANAGER] Lookup failed for {qualified_name}: {e}")

        return None

    def close(self):
        """Close KB connection"""
        if self.kb:
            try:
                self.kb.close()
            except Exception:
                # Ignore cleanup errors during close
                pass
