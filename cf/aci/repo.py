"""Repository abstraction for CodeFusion."""

import fnmatch
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional


@dataclass
class FileInfo:
    """Information about a file in the repository."""

    path: str
    size: int
    modified_time: float
    is_directory: bool
    extension: str


class CodeAction:
    """Defines possible actions on a CodeRepo."""

    READ_FILE = "read_file"
    WRITE_FILE = "write_file"
    LIST_DIR = "list_dir"
    SEARCH_FILES = "search_files"
    GET_FILE_INFO = "get_file_info"
    EXISTS = "exists"


class CodeRepo(ABC):
    """Base class for repository environments."""

    def __init__(self, repo_path: str):
        self.repo_path = repo_path
        self._excluded_dirs = {".git", "__pycache__", "node_modules", ".venv", "venv"}
        self._excluded_extensions = {".pyc", ".pyo", ".pyd", ".so", ".dll", ".exe"}

    def set_exclusions(
        self, excluded_dirs: List[str], excluded_extensions: List[str]
    ) -> None:
        """Set directories and file extensions to exclude."""
        self._excluded_dirs = set(excluded_dirs)
        self._excluded_extensions = set(excluded_extensions)

    @abstractmethod
    def read_file(self, file_path: str) -> str:
        """Read the contents of a file."""
        pass

    @abstractmethod
    def write_file(self, file_path: str, content: str) -> None:
        """Write content to a file."""
        pass

    @abstractmethod
    def list_directory(self, dir_path: str = "") -> List[FileInfo]:
        """List files and directories in the given path."""
        pass

    @abstractmethod
    def exists(self, path: str) -> bool:
        """Check if a file or directory exists."""
        pass

    @abstractmethod
    def get_file_info(self, file_path: str) -> FileInfo:
        """Get information about a file."""
        pass

    def search_files(self, pattern: str, include_dirs: bool = False) -> List[str]:
        """Search for files matching a pattern."""
        matches = []
        for file_info in self.walk_repository():
            if include_dirs or not file_info.is_directory:
                if fnmatch.fnmatch(file_info.path, pattern):
                    matches.append(file_info.path)
        return matches

    def walk_repository(self) -> Iterator[FileInfo]:
        """Walk through all files in the repository."""
        for file_info in self._walk_recursive(""):
            yield file_info

    @abstractmethod
    def _walk_recursive(self, path: str) -> Iterator[FileInfo]:
        """Recursively walk through repository files."""
        pass

    @abstractmethod
    def get_repository_stats(self) -> Dict[str, Any]:
        """Get statistics about the repository."""
        pass

    def _should_exclude_dir(self, dir_name: str) -> bool:
        """Check if a directory should be excluded."""
        return dir_name in self._excluded_dirs

    def _should_exclude_file(self, file_path: str) -> bool:
        """Check if a file should be excluded."""
        file_path_obj = Path(file_path)
        return file_path_obj.suffix in self._excluded_extensions


class LocalCodeRepo(CodeRepo):
    """Local filesystem implementation of CodeRepo."""

    def __init__(self, repo_path: str):
        super().__init__(repo_path)
        self._repo_path_str = repo_path
        self._repo_path_obj = Path(repo_path).resolve()

        if not self._repo_path_obj.exists():
            raise FileNotFoundError(f"Repository path does not exist: {repo_path}")

        if not self._repo_path_obj.is_dir():
            raise NotADirectoryError(f"Repository path is not a directory: {repo_path}")

    def read_file(self, file_path: str) -> str:
        """Read the contents of a file."""
        full_path = self._repo_path_obj / file_path

        if not full_path.exists():
            raise FileNotFoundError(f"File does not exist: {file_path}")

        if full_path.is_dir():
            raise IsADirectoryError(f"Path is a directory: {file_path}")

        try:
            with open(full_path, "r", encoding="utf-8") as f:
                return f.read()
        except UnicodeDecodeError:
            # Try reading as binary and decode with fallback
            with open(full_path, "rb") as f:
                content = f.read()
                return content.decode("utf-8", errors="replace")

    def write_file(self, file_path: str, content: str) -> None:
        """Write content to a file."""
        full_path = self._repo_path_obj / file_path

        # Create parent directories if they don't exist
        full_path.parent.mkdir(parents=True, exist_ok=True)

        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)

    def list_directory(self, dir_path: str = "") -> List[FileInfo]:
        """List files and directories in the given path."""
        full_path = self._repo_path_obj / dir_path

        if not full_path.exists():
            raise FileNotFoundError(f"Directory does not exist: {dir_path}")

        if not full_path.is_dir():
            raise NotADirectoryError(f"Path is not a directory: {dir_path}")

        items = []
        for item in full_path.iterdir():
            if item.is_dir() and self._should_exclude_dir(item.name):
                continue

            rel_path = item.relative_to(self._repo_path_obj)
            if item.is_file() and self._should_exclude_file(str(rel_path)):
                continue

            stat = item.stat()
            items.append(
                FileInfo(
                    path=str(rel_path),
                    size=stat.st_size,
                    modified_time=stat.st_mtime,
                    is_directory=item.is_dir(),
                    extension=item.suffix if item.is_file() else "",
                )
            )

        return sorted(items, key=lambda x: (not x.is_directory, x.path))

    def exists(self, path: str) -> bool:
        """Check if a file or directory exists."""
        full_path = self._repo_path_obj / path
        return full_path.exists()

    def get_file_info(self, file_path: str) -> FileInfo:
        """Get information about a file."""
        full_path = self._repo_path_obj / file_path

        if not full_path.exists():
            raise FileNotFoundError(f"File does not exist: {file_path}")

        stat = full_path.stat()
        return FileInfo(
            path=file_path,
            size=stat.st_size,
            modified_time=stat.st_mtime,
            is_directory=full_path.is_dir(),
            extension=full_path.suffix if full_path.is_file() else "",
        )

    def _walk_recursive(self, path: str) -> Iterator[FileInfo]:
        """Recursively walk through repository files."""
        try:
            for item in self.list_directory(path):
                yield item

                if item.is_directory and not self._should_exclude_dir(
                    Path(item.path).name
                ):
                    yield from self._walk_recursive(item.path)
        except (FileNotFoundError, NotADirectoryError, PermissionError):
            # Skip directories we can't access
            pass

    def get_repository_stats(self) -> Dict[str, Any]:
        """Get statistics about the repository."""
        stats: Dict[str, Any] = {
            "total_files": 0,
            "total_directories": 0,
            "total_size": 0,
            "file_types": {},
            "largest_files": [],
        }

        files_by_size: List[tuple[str, int]] = []

        for file_info in self.walk_repository():
            if file_info.is_directory:
                stats["total_directories"] += 1
            else:
                stats["total_files"] += 1
                stats["total_size"] += file_info.size

                # Track file types
                ext = file_info.extension or "no_extension"
                stats["file_types"][ext] = stats["file_types"].get(ext, 0) + 1

                # Track largest files
                files_by_size.append((file_info.path, file_info.size))

        # Get top 10 largest files
        files_by_size.sort(key=lambda x: x[1], reverse=True)
        stats["largest_files"] = files_by_size[:10]

        return stats


class RemoteCodeRepo(CodeRepo):
    """Future implementation for remote repositories."""

    def __init__(self, repo_url: str, access_token: Optional[str] = None):
        super().__init__(repo_url)
        self.access_token = access_token
        raise NotImplementedError("RemoteCodeRepo is not yet implemented")

    def read_file(self, file_path: str) -> str:
        raise NotImplementedError("RemoteCodeRepo is not yet implemented")

    def write_file(self, file_path: str, content: str) -> None:
        raise NotImplementedError("RemoteCodeRepo is not yet implemented")

    def list_directory(self, dir_path: str = "") -> List[FileInfo]:
        raise NotImplementedError("RemoteCodeRepo is not yet implemented")

    def exists(self, path: str) -> bool:
        raise NotImplementedError("RemoteCodeRepo is not yet implemented")

    def get_file_info(self, file_path: str) -> FileInfo:
        raise NotImplementedError("RemoteCodeRepo is not yet implemented")

    def _walk_recursive(self, path: str) -> Iterator[FileInfo]:
        raise NotImplementedError("RemoteCodeRepo is not yet implemented")
