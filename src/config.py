"""
Configuration Management Module

Handles loading and validation of YAML configuration files for Azure DevOps reporting.
"""

import os
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field

import yaml
from pydantic import BaseModel, Field, field_validator


logger = logging.getLogger(__name__)


class ApiConfig(BaseModel):
    """Azure DevOps API configuration settings."""
    base_url: str = "https://dev.azure.com"
    vssps_base_url: str = "https://vssps.dev.azure.com"
    vsaex_base_url: str = "https://vsaex.dev.azure.com"
    timeout: int = Field(default=30, ge=1, le=300)
    max_retries: int = Field(default=3, ge=0, le=10)
    retry_delay: int = Field(default=1, ge=0, le=60)

    @field_validator('base_url', 'vssps_base_url', 'vsaex_base_url')
    @classmethod
    def validate_urls(cls, v):
        """Validate that URLs are properly formatted."""
        if not v.startswith(('http://', 'https://')):
            raise ValueError('URL must start with http:// or https://')
        return v.rstrip('/')


class OutputConfig(BaseModel):
    """Output configuration settings."""
    formats: List[str] = Field(default=["csv", "json"])
    directory: str = "./reports"
    timestamp_format: str = "%Y%m%d_%H%M%S"

    @field_validator('formats')
    @classmethod
    def validate_formats(cls, v):
        """Validate supported output formats."""
        supported_formats = {"csv", "json", "excel"}
        invalid_formats = set(v) - supported_formats
        if invalid_formats:
            raise ValueError(f"Unsupported formats: {invalid_formats}. Supported: {supported_formats}")
        return v

    @field_validator('directory')
    @classmethod
    def validate_directory(cls, v):
        """Ensure directory path is valid."""
        if not v:
            raise ValueError("Directory cannot be empty")
        return v


class LoggingConfig(BaseModel):
    """Logging configuration settings."""
    level: str = Field(default="INFO")
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file: Optional[str] = "azure_devops_reporting.log"

    @field_validator('level')
    @classmethod
    def validate_log_level(cls, v):
        """Validate logging level."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v.upper() not in valid_levels:
            raise ValueError(f"Invalid log level: {v}. Valid levels: {valid_levels}")
        return v.upper()


class ReportsConfig(BaseModel):
    """Report generation configuration settings."""
    include_empty_groups: bool = False
    group_details: bool = True
    user_details: bool = True

    # Filtering options
    exclude_vsts_users: bool = Field(
        default=True,
        description="Exclude VSTS built-in users and service accounts from all reports"
    )
    exclude_vsts_groups: bool = Field(
        default=True,
        description="Exclude VSTS built-in groups from all reports"
    )


class AppConfig(BaseModel):
    """Main application configuration."""
    organizations: List[str] = Field(default_factory=list)
    api: ApiConfig = Field(default_factory=ApiConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    reports: ReportsConfig = Field(default_factory=ReportsConfig)

    @field_validator('organizations')
    @classmethod
    def validate_organizations(cls, v):
        """Validate organization names."""
        if not v:
            logger.warning("No organizations configured in config file")
        return v


class ConfigManager:
    """
    Configuration manager for loading and validating YAML configuration files.
    """

    def __init__(self, config_path: Optional[Union[str, Path]] = None):
        """
        Initialize configuration manager.

        Args:
            config_path: Path to configuration file. If None, uses default location.
        """
        self.config_path = self._resolve_config_path(config_path)
        self._config: Optional[AppConfig] = None

    def _resolve_config_path(self, config_path: Optional[Union[str, Path]]) -> Path:
        """
        Resolve the configuration file path.

        Args:
            config_path: Optional path to config file

        Returns:
            Resolved Path object
        """
        if config_path is None:
            # Default to config/config.yaml relative to project root
            current_dir = Path(__file__).parent.parent
            config_path = current_dir / "config" / "config.yaml"

        return Path(config_path)

    def load_config(self, override_organizations: Optional[List[str]] = None) -> AppConfig:
        """
        Load and validate configuration from YAML file.

        Args:
            override_organizations: Organizations to override config file settings

        Returns:
            Validated AppConfig object

        Raises:
            FileNotFoundError: If config file doesn't exist
            yaml.YAMLError: If YAML parsing fails
            ValueError: If configuration validation fails
        """
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")

        try:
            with open(self.config_path, 'r', encoding='utf-8') as file:
                config_data = yaml.safe_load(file)

            if config_data is None:
                config_data = {}

            # Override organizations if provided
            if override_organizations:
                config_data['organizations'] = override_organizations

            # Validate and create configuration object
            self._config = AppConfig(**config_data)

            logger.info(f"Configuration loaded successfully from {self.config_path}")
            return self._config

        except yaml.YAMLError as e:
            error_msg = f"Error parsing YAML configuration: {e}"
            logger.error(error_msg)
            raise yaml.YAMLError(error_msg)

        except Exception as e:
            error_msg = f"Error loading configuration: {e}"
            logger.error(error_msg)
            raise ValueError(error_msg)

    def get_config(self) -> AppConfig:
        """
        Get the current configuration. Loads if not already loaded.

        Returns:
            AppConfig object
        """
        if self._config is None:
            self._config = self.load_config()
        return self._config

    def create_default_config(self, output_path: Optional[Union[str, Path]] = None) -> Path:
        """
        Create a default configuration file.

        Args:
            output_path: Path where to create the config file

        Returns:
            Path to created config file
        """
        if output_path is None:
            output_path = self.config_path

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Create default configuration
        default_config = AppConfig()
        config_dict = default_config.model_dump()

        # Add comments to the YAML output
        yaml_content = self._generate_commented_yaml(config_dict)

        with open(output_path, 'w', encoding='utf-8') as file:
            file.write(yaml_content)

        logger.info(f"Default configuration created at {output_path}")
        return output_path

    def _generate_commented_yaml(self, config_dict: Dict[str, Any]) -> str:
        """
        Generate YAML with comments for better user experience.

        Args:
            config_dict: Configuration dictionary

        Returns:
            YAML string with comments
        """
        yaml_lines = [
            "# Azure DevOps Entitlement Reporting Configuration",
            "",
            "# Organizations to process (can be overridden by command line)",
            "organizations:",
            "  - \"your-org-name\"",
            "",
            "# Azure DevOps API Configuration",
            f"api:",
            f"  base_url: \"{config_dict['api']['base_url']}\"",
            f"  vssps_base_url: \"{config_dict['api']['vssps_base_url']}\"",
            f"  vsaex_base_url: \"{config_dict['api']['vsaex_base_url']}\"",
            f"  timeout: {config_dict['api']['timeout']}",
            f"  max_retries: {config_dict['api']['max_retries']}",
            f"  retry_delay: {config_dict['api']['retry_delay']}",
            "",
            "# Output Configuration",
            "output:",
            "  formats:",
        ]

        for fmt in config_dict['output']['formats']:
            yaml_lines.append(f"    - {fmt}")

        yaml_lines.extend([
            f"  directory: \"{config_dict['output']['directory']}\"",
            f"  timestamp_format: \"{config_dict['output']['timestamp_format']}\"",
            "",
            "# Logging Configuration",
            "logging:",
            f"  level: \"{config_dict['logging']['level']}\"",
            f"  format: \"{config_dict['logging']['format']}\"",
            f"  file: \"{config_dict['logging']['file']}\"",
            "",
            "# Report Configuration",
            "reports:",
            f"  include_empty_groups: {str(config_dict['reports']['include_empty_groups']).lower()}",
            f"  group_details: {str(config_dict['reports']['group_details']).lower()}",
            f"  user_details: {str(config_dict['reports']['user_details']).lower()}",
        ])

        return '\n'.join(yaml_lines)

    def validate_config(self) -> bool:
        """
        Validate the current configuration.

        Returns:
            True if configuration is valid, False otherwise
        """
        try:
            config = self.get_config()

            # Additional validation logic
            if not config.organizations:
                logger.warning("No organizations configured")

            # Validate output directory is writable
            output_dir = Path(config.output.directory)
            try:
                output_dir.mkdir(parents=True, exist_ok=True)
                test_file = output_dir / ".test_write"
                test_file.touch()
                test_file.unlink()
            except (OSError, PermissionError) as e:
                logger.error(f"Output directory is not writable: {e}")
                return False

            logger.info("Configuration validation successful")
            return True

        except Exception as e:
            logger.error(f"Configuration validation failed: {e}")
            return False

    def get_organization_config(self, organization: str) -> Dict[str, Any]:
        """
        Get configuration specific to an organization.

        Args:
            organization: Organization name

        Returns:
            Configuration dictionary for the organization
        """
        config = self.get_config()

        return {
            'organization': organization,
            'api': config.api.model_dump(),
            'output': config.output.model_dump(),
            'reports': config.reports.model_dump()
        }