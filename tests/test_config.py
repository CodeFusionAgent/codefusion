"""Tests for configuration management."""

import pytest
import tempfile
import yaml
from pathlib import Path

from cf.config import CfConfig
from cf.exceptions import ConfigurationError


class TestCfConfig:
    """Test cases for CfConfig class."""
    
    def test_default_config(self):
        """Test default configuration creation."""
        config = CfConfig()
        
        assert config.repo_path is None
        assert config.output_dir == "./output"
        assert config.llm_model == "gpt-3.5-turbo"
        assert config.kb_type == "text"
        assert config.exploration_strategy == "react"
        assert config.max_exploration_depth == 5
    
    def test_config_from_dict(self):
        """Test configuration creation from dictionary."""
        config_dict = {
            "repo_path": "/test/repo",
            "llm_model": "gpt-4",
            "kb_type": "neo4j",
            "exploration_strategy": "plan_act"
        }
        
        config = CfConfig.from_dict(config_dict)
        
        assert config.repo_path == "/test/repo"
        assert config.llm_model == "gpt-4"
        assert config.kb_type == "neo4j"
        assert config.exploration_strategy == "plan_act"
    
    def test_config_from_yaml_file(self):
        """Test configuration loading from YAML file."""
        config_data = {
            "repo_path": "/test/repo",
            "llm_model": "claude-3",
            "kb_type": "text",
            "max_exploration_depth": 10
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            temp_path = f.name
        
        try:
            config = CfConfig.from_file(temp_path)
            
            assert config.repo_path == "/test/repo"
            assert config.llm_model == "claude-3"
            assert config.kb_type == "text"
            assert config.max_exploration_depth == 10
        finally:
            Path(temp_path).unlink()
    
    def test_config_validation(self):
        """Test configuration validation."""
        # Valid config should not raise
        config = CfConfig()
        config.validate()  # Should not raise
        
        # Invalid kb_type should raise
        config.kb_type = "invalid"
        with pytest.raises(ValueError):
            config.validate()
        
        # Invalid exploration strategy should raise
        config.kb_type = "text"
        config.exploration_strategy = "invalid"
        with pytest.raises(ValueError):
            config.validate()
    
    def test_config_to_dict(self):
        """Test configuration serialization to dictionary."""
        config = CfConfig(
            repo_path="/test",
            llm_model="gpt-4",
            kb_type="neo4j"
        )
        
        config_dict = config.to_dict()
        
        assert config_dict["repo_path"] == "/test"
        assert config_dict["llm_model"] == "gpt-4"
        assert config_dict["kb_type"] == "neo4j"
    
    def test_config_save_and_load(self):
        """Test configuration save and load cycle."""
        original_config = CfConfig(
            repo_path="/test/repo",
            llm_model="gpt-4",
            exploration_strategy="plan_act"
        )
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            temp_path = f.name
        
        try:
            original_config.save(temp_path)
            loaded_config = CfConfig.from_file(temp_path)
            
            assert loaded_config.repo_path == original_config.repo_path
            assert loaded_config.llm_model == original_config.llm_model
            assert loaded_config.exploration_strategy == original_config.exploration_strategy
        finally:
            Path(temp_path).unlink()
    
    def test_missing_config_file(self):
        """Test handling of missing configuration file."""
        with pytest.raises(FileNotFoundError):
            CfConfig.from_file("/nonexistent/config.yaml")