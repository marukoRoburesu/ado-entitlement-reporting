"""
Tests for the Azure DevOps authentication module.
"""

import base64
import os
import pytest
from unittest.mock import patch, MagicMock
import requests

from src.auth import AzureDevOpsAuth, AuthConfig, AuthManager


class TestAuthConfig:
    """Tests for AuthConfig dataclass."""

    def test_auth_config_creation(self):
        """Test AuthConfig creation with required fields."""
        config = AuthConfig(
            pat_token="test-token",
            organization="test-org"
        )

        assert config.pat_token == "test-token"
        assert config.organization == "test-org"
        assert config.base_url == "https://dev.azure.com"
        assert config.vssps_base_url == "https://vssps.dev.azure.com"
        assert config.vsaex_base_url == "https://vsaex.dev.azure.com"

    def test_auth_config_custom_urls(self):
        """Test AuthConfig with custom URLs."""
        config = AuthConfig(
            pat_token="test-token",
            organization="test-org",
            base_url="https://custom.dev.azure.com",
            vssps_base_url="https://custom.vssps.dev.azure.com"
        )

        assert config.base_url == "https://custom.dev.azure.com"
        assert config.vssps_base_url == "https://custom.vssps.dev.azure.com"


class TestAzureDevOpsAuth:
    """Tests for AzureDevOpsAuth class."""

    def test_init_valid_config(self):
        """Test initialization with valid configuration."""
        config = AuthConfig(pat_token="test-token", organization="test-org")
        auth = AzureDevOpsAuth(config)

        assert auth.config == config
        assert auth._session is None

    def test_init_empty_token(self):
        """Test initialization with empty PAT token."""
        config = AuthConfig(pat_token="", organization="test-org")

        with pytest.raises(ValueError, match="PAT token is required"):
            AzureDevOpsAuth(config)

    def test_init_whitespace_token(self):
        """Test initialization with whitespace-only PAT token."""
        config = AuthConfig(pat_token="   ", organization="test-org")

        with pytest.raises(ValueError, match="PAT token cannot be empty or whitespace"):
            AzureDevOpsAuth(config)

    def test_init_empty_organization(self):
        """Test initialization with empty organization."""
        config = AuthConfig(pat_token="test-token", organization="")

        with pytest.raises(ValueError, match="Organization name is required"):
            AzureDevOpsAuth(config)

    def test_create_auth_header(self):
        """Test creation of authentication header."""
        config = AuthConfig(pat_token="test-token", organization="test-org")
        auth = AzureDevOpsAuth(config)

        header = auth._create_auth_header()

        # Verify the header format
        assert header.startswith("Basic ")

        # Decode and verify the content
        encoded_part = header.split(" ")[1]
        decoded = base64.b64decode(encoded_part).decode()
        assert decoded == ":test-token"

    def test_get_session(self):
        """Test getting authenticated session."""
        config = AuthConfig(pat_token="test-token", organization="test-org")
        auth = AzureDevOpsAuth(config)

        session = auth.get_session()

        assert isinstance(session, requests.Session)
        assert "Authorization" in session.headers
        assert "Content-Type" in session.headers
        assert session.headers["Content-Type"] == "application/json"
        assert session.headers["Accept"] == "application/json"

        # Test session reuse
        session2 = auth.get_session()
        assert session is session2

    def test_get_organization_url(self):
        """Test getting organization URLs for different API types."""
        config = AuthConfig(pat_token="test-token", organization="test-org")
        auth = AzureDevOpsAuth(config)

        core_url = auth.get_organization_url("core")
        vssps_url = auth.get_organization_url("vssps")
        vsaex_url = auth.get_organization_url("vsaex")

        assert core_url == "https://dev.azure.com/test-org"
        assert vssps_url == "https://vssps.dev.azure.com/test-org"
        assert vsaex_url == "https://vsaex.dev.azure.com/test-org"

    def test_get_organization_url_invalid_type(self):
        """Test getting organization URL with invalid API type."""
        config = AuthConfig(pat_token="test-token", organization="test-org")
        auth = AzureDevOpsAuth(config)

        with pytest.raises(ValueError, match="Unknown API type: invalid"):
            auth.get_organization_url("invalid")

    @patch('src.auth.requests.Session.get')
    def test_validate_token_success(self, mock_get):
        """Test successful token validation."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        config = AuthConfig(pat_token="test-token", organization="test-org")
        auth = AzureDevOpsAuth(config)

        result = auth.validate_token()

        assert result is True
        mock_get.assert_called_once()

    @patch('src.auth.requests.Session.get')
    def test_validate_token_unauthorized(self, mock_get):
        """Test token validation with unauthorized response."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_get.return_value = mock_response

        config = AuthConfig(pat_token="test-token", organization="test-org")
        auth = AzureDevOpsAuth(config)

        result = auth.validate_token()

        assert result is False

    @patch('src.auth.requests.Session.get')
    def test_validate_token_unexpected_status(self, mock_get):
        """Test token validation with unexpected status code."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response

        config = AuthConfig(pat_token="test-token", organization="test-org")
        auth = AzureDevOpsAuth(config)

        result = auth.validate_token()

        assert result is False

    @patch('src.auth.requests.Session.get')
    def test_validate_token_request_exception(self, mock_get):
        """Test token validation with request exception."""
        mock_get.side_effect = requests.exceptions.RequestException("Network error")

        config = AuthConfig(pat_token="test-token", organization="test-org")
        auth = AzureDevOpsAuth(config)

        result = auth.validate_token()

        assert result is False


class TestAuthManager:
    """Tests for AuthManager class."""

    @patch.dict(os.environ, {
        'AZURE_DEVOPS_PAT': 'env-token',
        'AZURE_DEVOPS_ORGANIZATION': 'env-org'
    })
    def test_from_environment_success(self):
        """Test creating auth from environment variables."""
        auth = AuthManager.from_environment()

        assert auth.config.pat_token == "env-token"
        assert auth.config.organization == "env-org"

    @patch.dict(os.environ, {
        'AZURE_DEVOPS_PAT': 'env-token',
        'AZURE_DEVOPS_ORGANIZATION': 'env-org'
    })
    def test_from_environment_override_organization(self):
        """Test creating auth from environment with organization override."""
        auth = AuthManager.from_environment(organization="override-org")

        assert auth.config.pat_token == "env-token"
        assert auth.config.organization == "override-org"

    @patch('src.auth.load_dotenv')
    @patch.dict(os.environ, {}, clear=True)
    def test_from_environment_missing_token(self, mock_load_dotenv):
        """Test creating auth from environment with missing PAT token."""
        with pytest.raises(ValueError, match="AZURE_DEVOPS_PAT environment variable is required"):
            AuthManager.from_environment()

    @patch('src.auth.load_dotenv')
    @patch.dict(os.environ, {'AZURE_DEVOPS_PAT': 'env-token'}, clear=True)
    def test_from_environment_missing_organization(self, mock_load_dotenv):
        """Test creating auth from environment with missing organization."""
        with pytest.raises(ValueError, match="Organization name is required"):
            AuthManager.from_environment()

    def test_from_token(self):
        """Test creating auth from explicit token and organization."""
        auth = AuthManager.from_token("explicit-token", "explicit-org")

        assert auth.config.pat_token == "explicit-token"
        assert auth.config.organization == "explicit-org"