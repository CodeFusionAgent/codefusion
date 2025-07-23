"""Repository abstraction for CodeFusion."""

import fnmatch
import re
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

    def scan_directory(self, path: str = ".", max_depth: int = 3) -> Dict[str, Any]:
        """
        Scan directory structure up to max_depth levels with enhanced return format.
        
        Args:
            path: Directory path to scan (relative to repo root)
            max_depth: Maximum depth to scan
            
        Returns:
            Dictionary with success status, contents, and stats
        """
        scan_path = self._repo_path_obj / path if path != "." else self._repo_path_obj
        
        if not scan_path.exists() or not scan_path.is_dir():
            return {"success": False, "error": f"Directory not found: {path}"}
        
        result = {
            "success": True,
            "path": path,
            "contents": [],
            "stats": {"directories": 0, "files": 0, "total_size": 0}
        }
        
        def scan_recursive(current_path: Path, relative_path: str, depth: int):
            if depth > max_depth:
                return
                
            try:
                for item in current_path.iterdir():
                    if item.is_dir() and self._should_exclude_dir(item.name):
                        continue
                    
                    item_relative = str(Path(relative_path) / item.name) if relative_path else item.name
                    
                    if item.is_file() and self._should_exclude_file(str(item.relative_to(self._repo_path_obj))):
                        continue
                    
                    stat = item.stat()
                    file_info = {
                        "path": item_relative,
                        "name": item.name,
                        "is_directory": item.is_dir(),
                        "size": stat.st_size,
                        "modified_time": stat.st_mtime,
                        "extension": item.suffix if item.is_file() else ""
                    }
                    
                    result["contents"].append(file_info)
                    
                    if item.is_dir():
                        result["stats"]["directories"] += 1
                        if depth < max_depth:
                            scan_recursive(item, item_relative, depth + 1)
                    else:
                        result["stats"]["files"] += 1
                        result["stats"]["total_size"] += stat.st_size
                    
            except PermissionError:
                pass  # Skip directories we can't access
        
        scan_recursive(scan_path, path if path != "." else "", 0)
        return result

    def read_file_safe(self, file_path: str, max_lines: int = None) -> Dict[str, Any]:
        """
        Read file with enhanced return format including success status.
        
        Args:
            file_path: Path to file (relative to repo root)
            max_lines: Maximum number of lines to read
            
        Returns:
            Dictionary with success status, content, and metadata
        """
        try:
            full_path = self._repo_path_obj / file_path
            
            if not full_path.exists():
                return {"success": False, "error": f"File not found: {file_path}"}
            
            if full_path.is_dir():
                return {"success": False, "error": f"Path is a directory: {file_path}"}
            
            with open(full_path, "r", encoding="utf-8") as f:
                if max_lines:
                    lines = []
                    for i, line in enumerate(f):
                        if i >= max_lines:
                            break
                        lines.append(line.rstrip('\n\r'))
                    content = '\n'.join(lines)
                else:
                    content = f.read()
            
            stat = full_path.stat()
            
            return {
                "success": True,
                "file_path": file_path,
                "content": content,
                "size": stat.st_size,
                "lines": len(content.split('\n')),
                "modified_time": stat.st_mtime,
                "extension": full_path.suffix
            }
            
        except UnicodeDecodeError:
            return {"success": False, "error": f"Cannot read file (binary or encoding issue): {file_path}"}
        except Exception as e:
            return {"success": False, "error": f"Error reading file: {e}"}

    def search_content(self, pattern: str, file_types: List[str] = None, max_results: int = 20) -> Dict[str, Any]:
        """
        Search for pattern across file contents in repository.
        
        Args:
            pattern: Regex pattern or text to search for
            file_types: List of file extensions to search in (e.g., ['.py', '.js'])
            max_results: Maximum number of results to return
            
        Returns:
            Dictionary with search results
        """
        results = []
        
        try:
            # Compile regex pattern
            regex = re.compile(pattern, re.IGNORECASE | re.MULTILINE)
            
            # Walk through all files
            for file_info in self.walk_repository():
                if file_info.is_directory:
                    continue
                
                # Filter by file type if specified
                if file_types and not any(file_info.path.endswith(ext) for ext in file_types):
                    continue
                
                if len(results) >= max_results:
                    break
                
                # Read and search file
                try:
                    full_path = self._repo_path_obj / file_info.path
                    with open(full_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    
                    matches = list(regex.finditer(content))
                    if matches:
                        # Get line numbers for matches
                        lines = content.split('\n')
                        match_lines = []
                        
                        for match in matches[:5]:  # Limit matches per file
                            line_num = content[:match.start()].count('\n') + 1
                            line_content = lines[line_num - 1] if line_num <= len(lines) else ""
                            
                            match_lines.append({
                                "line_number": line_num,
                                "line_content": line_content.strip(),
                                "match_text": match.group(0)
                            })
                        
                        results.append({
                            "file_path": file_info.path,
                            "matches": match_lines,
                            "total_matches": len(matches)
                        })
                
                except (UnicodeDecodeError, PermissionError):
                    continue  # Skip files we can't read
                except Exception:
                    continue  # Skip files with errors
            
            return {
                "success": True,
                "pattern": pattern,
                "results": results,
                "total_files_searched": len(results),
                "total_matches": sum(r["total_matches"] for r in results)
            }
            
        except re.error as e:
            return {"success": False, "error": f"Invalid regex pattern: {e}"}
        except Exception as e:
            return {"success": False, "error": f"Search error: {e}"}


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
