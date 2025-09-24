"""
Tests for the configuration management module.
"""

import os
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch, mock_open

import yaml
from pydantic import ValidationError

from src.config import (
    ConfigManager, AppConfig, ApiConfig, OutputConfig,
    LoggingConfig, ReportsConfig
)


class TestApiConfig:
    """Tests for ApiConfig model."""

    def test_api_config_defaults(self):
        """Test ApiConfig with default values."""
        config = ApiConfig()

        assert config.base_url == "https://dev.azure.com"
        assert config.vssps_base_url == "https://vssps.dev.azure.com"
        assert config.vsaex_base_url == "https://vsaex.dev.azure.com"
        assert config.timeout == 30
        assert config.max_retries == 3
        assert config.retry_delay == 1

    def test_api_config_custom_values(self):
        """Test ApiConfig with custom values."""
        config = ApiConfig(
            base_url="https://custom.dev.azure.com",
            timeout=60,
            max_retries=5
        )

        assert config.base_url == "https://custom.dev.azure.com"
        assert config.timeout == 60
        assert config.max_retries == 5

    def test_api_config_invalid_url(self):
        """Test ApiConfig with invalid URL."""
        with pytest.raises(ValidationError, match="URL must start with http"):
            ApiConfig(base_url="invalid-url")

    def test_api_config_url_trailing_slash_removed(self):
        """Test that trailing slashes are removed from URLs."""
        config = ApiConfig(base_url="https://dev.azure.com/")
        assert config.base_url == "https://dev.azure.com"

    def test_api_config_invalid_timeout(self):
        """Test ApiConfig with invalid timeout values."""
        with pytest.raises(ValidationError):
            ApiConfig(timeout=0)

        with pytest.raises(ValidationError):
            ApiConfig(timeout=301)

    def test_api_config_invalid_retries(self):
        """Test ApiConfig with invalid retry values."""
        with pytest.raises(ValidationError):
            ApiConfig(max_retries=-1)

        with pytest.raises(ValidationError):
            ApiConfig(max_retries=11)


class TestOutputConfig:
    """Tests for OutputConfig model."""

    def test_output_config_defaults(self):
        """Test OutputConfig with default values."""
        config = OutputConfig()

        assert config.formats == ["csv", "json"]
        assert config.directory == "./reports"
        assert config.timestamp_format == "%Y%m%d_%H%M%S"

    def test_output_config_custom_formats(self):
        """Test OutputConfig with custom formats."""
        config = OutputConfig(formats=["csv", "excel"])
        assert config.formats == ["csv", "excel"]

    def test_output_config_invalid_format(self):
        """Test OutputConfig with invalid format."""
        with pytest.raises(ValidationError, match="Unsupported formats"):
            OutputConfig(formats=["csv", "invalid"])

    def test_output_config_empty_directory(self):
        """Test OutputConfig with empty directory."""
        with pytest.raises(ValidationError, match="Directory cannot be empty"):
            OutputConfig(directory="")


class TestLoggingConfig:
    """Tests for LoggingConfig model."""

    def test_logging_config_defaults(self):
        """Test LoggingConfig with default values."""
        config = LoggingConfig()

        assert config.level == "INFO"
        assert "%(asctime)s" in config.format
        assert config.file == "azure_devops_reporting.log"

    def test_logging_config_valid_levels(self):
        """Test LoggingConfig with valid log levels."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

        for level in valid_levels:
            config = LoggingConfig(level=level)
            assert config.level == level.upper()

    def test_logging_config_case_insensitive_level(self):
        """Test that log level is case insensitive."""
        config = LoggingConfig(level="debug")
        assert config.level == "DEBUG"

    def test_logging_config_invalid_level(self):
        """Test LoggingConfig with invalid log level."""
        with pytest.raises(ValidationError, match="Invalid log level"):
            LoggingConfig(level="INVALID")


class TestReportsConfig:
    """Tests for ReportsConfig model."""

    def test_reports_config_defaults(self):
        """Test ReportsConfig with default values."""
        config = ReportsConfig()

        assert config.include_empty_groups is False
        assert config.group_details is True
        assert config.user_details is True

    def test_reports_config_custom_values(self):
        """Test ReportsConfig with custom values."""
        config = ReportsConfig(
            include_empty_groups=True,
            group_details=False
        )

        assert config.include_empty_groups is True
        assert config.group_details is False


class TestAppConfig:
    """Tests for AppConfig model."""

    def test_app_config_defaults(self):
        """Test AppConfig with default values."""
        config = AppConfig()

        assert config.organizations == []
        assert isinstance(config.api, ApiConfig)
        assert isinstance(config.output, OutputConfig)
        assert isinstance(config.logging, LoggingConfig)
        assert isinstance(config.reports, ReportsConfig)

    def test_app_config_with_organizations(self):
        """Test AppConfig with organizations."""
        config = AppConfig(organizations=["org1", "org2"])
        assert config.organizations == ["org1", "org2"]

    def test_app_config_nested_config(self):
        """Test AppConfig with nested configuration."""
        config_data = {
            "organizations": ["test-org"],
            "api": {"timeout": 60},
            "output": {"formats": ["csv"]},
            "logging": {"level": "DEBUG"}
        }

        config = AppConfig(**config_data)

        assert config.organizations == ["test-org"]
        assert config.api.timeout == 60
        assert config.output.formats == ["csv"]
        assert config.logging.level == "DEBUG"


class TestConfigManager:
    """Tests for ConfigManager class."""

    def test_config_manager_default_path(self):
        """Test ConfigManager with default config path."""
        manager = ConfigManager()
        assert "config.yaml" in str(manager.config_path)

    def test_config_manager_custom_path(self):
        """Test ConfigManager with custom config path."""
        custom_path = "/custom/path/config.yaml"
        manager = ConfigManager(custom_path)
        assert str(manager.config_path) == custom_path

    def test_load_config_file_not_found(self):
        """Test loading config when file doesn't exist."""
        manager = ConfigManager("/nonexistent/config.yaml")

        with pytest.raises(FileNotFoundError, match="Configuration file not found"):
            manager.load_config()

    def test_load_config_success(self):
        """Test successful config loading."""
        config_data = {
            "organizations": ["test-org"],
            "api": {"timeout": 45},
            "output": {"formats": ["json"]}
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            temp_path = f.name

        try:
            manager = ConfigManager(temp_path)
            config = manager.load_config()

            assert config.organizations == ["test-org"]
            assert config.api.timeout == 45
            assert config.output.formats == ["json"]
        finally:
            os.unlink(temp_path)

    def test_load_config_with_override_organizations(self):
        """Test loading config with organization override."""
        config_data = {"organizations": ["original-org"]}

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            temp_path = f.name

        try:
            manager = ConfigManager(temp_path)
            config = manager.load_config(override_organizations=["override-org"])

            assert config.organizations == ["override-org"]
        finally:
            os.unlink(temp_path)

    def test_load_config_empty_file(self):
        """Test loading config from empty file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("")
            temp_path = f.name

        try:
            manager = ConfigManager(temp_path)
            config = manager.load_config()

            # Should create config with defaults
            assert isinstance(config, AppConfig)
            assert config.organizations == []
        finally:
            os.unlink(temp_path)

    def test_load_config_invalid_yaml(self):
        """Test loading config with invalid YAML."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("invalid: yaml: content: [")
            temp_path = f.name

        try:
            manager = ConfigManager(temp_path)

            with pytest.raises(yaml.YAMLError, match="Error parsing YAML"):
                manager.load_config()
        finally:
            os.unlink(temp_path)

    def test_load_config_invalid_configuration(self):
        """Test loading config with invalid configuration values."""
        config_data = {"api": {"timeout": "invalid"}}

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            temp_path = f.name

        try:
            manager = ConfigManager(temp_path)

            with pytest.raises(ValueError, match="Error loading configuration"):
                manager.load_config()
        finally:
            os.unlink(temp_path)

    def test_get_config_loads_if_not_loaded(self):
        """Test that get_config loads config if not already loaded."""
        config_data = {"organizations": ["test-org"]}

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            temp_path = f.name

        try:
            manager = ConfigManager(temp_path)
            config = manager.get_config()

            assert config.organizations == ["test-org"]
            # Second call should return cached config
            config2 = manager.get_config()
            assert config is config2
        finally:
            os.unlink(temp_path)

    def test_create_default_config(self):
        """Test creating default configuration file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "test_config.yaml"
            manager = ConfigManager()

            created_path = manager.create_default_config(output_path)

            assert created_path == output_path
            assert output_path.exists()

            # Verify the created file can be loaded
            with open(output_path, 'r') as f:
                content = f.read()
                assert "Azure DevOps Entitlement Reporting Configuration" in content
                assert "organizations:" in content

    def test_validate_config_directory_creation_failure(self):
        """Test config validation when directory creation fails."""
        config_data = {"output": {"directory": "/root/invalid/path"}}

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            temp_path = f.name

        try:
            manager = ConfigManager(temp_path)
            manager.load_config()

            # This should fail because /root/invalid/path is not writable
            result = manager.validate_config()
            assert result is False
        finally:
            os.unlink(temp_path)

    def test_get_organization_config(self):
        """Test getting organization-specific configuration."""
        config_data = {
            "organizations": ["test-org"],
            "api": {"timeout": 60},
            "output": {"formats": ["csv"]},
            "reports": {"group_details": False}
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            temp_path = f.name

        try:
            manager = ConfigManager(temp_path)
            manager.load_config()

            org_config = manager.get_organization_config("test-org")

            assert org_config['organization'] == "test-org"
            assert org_config['api']['timeout'] == 60
            assert org_config['output']['formats'] == ["csv"]
            assert org_config['reports']['group_details'] is False
        finally:
            os.unlink(temp_path)