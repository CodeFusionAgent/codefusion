"""Tests for configuration management."""

import tempfile
from pathlib import Path

import pytest
import yaml

from cf.config import CfConfig


class TestCfConfig:
    """Test cases for CfConfig class."""

    def test_default_config(self):
        """Test default configuration creation."""
        config = CfConfig()

        assert config.repo_path is None
        assert config.output_dir == "./output"
        assert config.max_exploration_depth == 5
        assert config.max_file_size == 1024 * 1024
        assert ".git" in config.excluded_dirs
        assert ".pyc" in config.excluded_extensions

    def test_config_from_dict(self):
        """Test configuration creation from dictionary."""
        config_dict = {
            "repo_path": "/test/repo",
            "output_dir": "/test/output",
            "max_file_size": 2048,
            "max_exploration_depth": 10,
        }

        config = CfConfig.from_dict(config_dict)

        assert config.repo_path == "/test/repo"
        assert config.output_dir == "/test/output"
        assert config.max_file_size == 2048
        assert config.max_exploration_depth == 10

    def test_config_from_yaml_file(self):
        """Test configuration loading from YAML file."""
        config_data = {
            "repo_path": "/test/repo",
            "output_dir": "/test/output",
            "max_exploration_depth": 10,
            "max_file_size": 2048,
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_data, f)
            temp_path = f.name

        try:
            config = CfConfig.from_file(temp_path)

            assert config.repo_path == "/test/repo"
            assert config.output_dir == "/test/output"
            assert config.max_exploration_depth == 10
            assert config.max_file_size == 2048
        finally:
            Path(temp_path).unlink()

    def test_config_validation(self):
        """Test configuration validation."""
        # Valid config should not raise
        config = CfConfig()
        config.validate()  # Should not raise

        # Invalid max_exploration_depth should raise
        config.max_exploration_depth = 0
        with pytest.raises(ValueError):
            config.validate()

        # Invalid max_file_size should raise
        config.max_exploration_depth = 5
        config.max_file_size = 0
        with pytest.raises(ValueError):
            config.validate()

    def test_config_to_dict(self):
        """Test configuration serialization to dictionary."""
        config = CfConfig(repo_path="/test", output_dir="/test/output", max_file_size=2048)

        config_dict = config.to_dict()

        assert config_dict["repo_path"] == "/test"
        assert config_dict["output_dir"] == "/test/output"
        assert config_dict["max_file_size"] == 2048

    def test_config_save_and_load(self):
        """Test configuration save and load cycle."""
        original_config = CfConfig(
            repo_path="/test/repo", output_dir="/test/output", max_file_size=2048
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            temp_path = f.name

        try:
            original_config.save(temp_path)
            loaded_config = CfConfig.from_file(temp_path)

            assert loaded_config.repo_path == original_config.repo_path
            assert loaded_config.output_dir == original_config.output_dir
            assert loaded_config.max_file_size == original_config.max_file_size
        finally:
            Path(temp_path).unlink()

    def test_missing_config_file(self):
        """Test handling of missing configuration file."""
        with pytest.raises(FileNotFoundError):
            CfConfig.from_file("/nonexistent/config.yaml")
