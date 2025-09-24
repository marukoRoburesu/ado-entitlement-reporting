"""
Azure DevOps Authentication Module

Handles Personal Access Token (PAT) authentication for Azure DevOps APIs.
"""

import base64
import os
from typing import Optional
import logging
from dataclasses import dataclass

import requests
from dotenv import load_dotenv


logger = logging.getLogger(__name__)


@dataclass
class AuthConfig:
    """Configuration for Azure DevOps authentication."""
    pat_token: str
    organization: str
    base_url: str = "https://dev.azure.com"
    vssps_base_url: str = "https://vssps.dev.azure.com"
    vsaex_base_url: str = "https://vsaex.dev.azure.com"


class AzureDevOpsAuth:
    """
    Azure DevOps authentication handler using Personal Access Tokens.

    This class manages authentication for Azure DevOps REST APIs using PAT tokens.
    It handles token validation and provides authenticated session objects.
    """

    def __init__(self, config: AuthConfig):
        """
        Initialize the authentication handler.

        Args:
            config: Authentication configuration containing PAT token and organization
        """
        self.config = config
        self._session = None
        self._validate_config()

    def _validate_config(self) -> None:
        """Validate the authentication configuration."""
        if not self.config.pat_token:
            raise ValueError("PAT token is required")

        if not self.config.organization:
            raise ValueError("Organization name is required")

        if not self.config.pat_token.strip():
            raise ValueError("PAT token cannot be empty or whitespace")

    def _create_auth_header(self) -> str:
        """
        Create the basic authentication header using PAT token.

        Returns:
            Base64 encoded authentication string
        """
        # Azure DevOps PAT tokens use empty username with token as password
        auth_string = f":{self.config.pat_token}"
        encoded_auth = base64.b64encode(auth_string.encode()).decode()
        return f"Basic {encoded_auth}"

    def get_session(self) -> requests.Session:
        """
        Get an authenticated requests session.

        Returns:
            Configured requests session with authentication headers
        """
        if self._session is None:
            self._session = requests.Session()
            self._session.headers.update({
                "Authorization": self._create_auth_header(),
                "Content-Type": "application/json",
                "Accept": "application/json"
            })

        return self._session

    def validate_token(self) -> bool:
        """
        Validate the PAT token by making a test API call.

        Returns:
            True if token is valid, False otherwise
        """
        try:
            session = self.get_session()
            # Test with a simple profile API call
            test_url = f"{self.config.vssps_base_url}/{self.config.organization}/_apis/profile/profiles/me"

            response = session.get(test_url, params={"api-version": "6.0"}, timeout=10)

            if response.status_code == 200:
                logger.info("PAT token validation successful")
                return True
            elif response.status_code == 401:
                logger.error("PAT token validation failed: Unauthorized")
                return False
            else:
                logger.warning(f"PAT token validation returned unexpected status: {response.status_code}")
                return False

        except requests.exceptions.RequestException as e:
            logger.error(f"Error validating PAT token: {e}")
            return False

    def get_organization_url(self, api_type: str = "core") -> str:
        """
        Get the appropriate base URL for the organization and API type.

        Args:
            api_type: Type of API ('core', 'vssps', 'vsaex')

        Returns:
            Complete base URL for the organization and API type
        """
        base_urls = {
            "core": self.config.base_url,
            "vssps": self.config.vssps_base_url,
            "vsaex": self.config.vsaex_base_url
        }

        if api_type not in base_urls:
            raise ValueError(f"Unknown API type: {api_type}")

        return f"{base_urls[api_type]}/{self.config.organization}"


class AuthManager:
    """
    High-level authentication manager that handles environment variables and configuration.
    """

    @staticmethod
    def from_environment(organization: Optional[str] = None) -> AzureDevOpsAuth:
        """
        Create authentication from environment variables.

        Args:
            organization: Organization name (overrides environment variable)

        Returns:
            Configured AzureDevOpsAuth instance

        Raises:
            ValueError: If required environment variables are missing
        """
        # Load environment variables from .env file if it exists
        load_dotenv()

        pat_token = os.getenv("AZURE_DEVOPS_PAT")
        env_organization = os.getenv("AZURE_DEVOPS_ORGANIZATION")

        # Use provided organization or fall back to environment
        final_organization = organization or env_organization

        if not pat_token:
            raise ValueError(
                "AZURE_DEVOPS_PAT environment variable is required. "
                "Set it in your environment or .env file."
            )

        if not final_organization:
            raise ValueError(
                "Organization name is required. "
                "Provide it as parameter or set AZURE_DEVOPS_ORGANIZATION environment variable."
            )

        config = AuthConfig(
            pat_token=pat_token,
            organization=final_organization
        )

        return AzureDevOpsAuth(config)

    @staticmethod
    def from_token(pat_token: str, organization: str) -> AzureDevOpsAuth:
        """
        Create authentication from explicit token and organization.

        Args:
            pat_token: Personal Access Token
            organization: Organization name

        Returns:
            Configured AzureDevOpsAuth instance
        """
        config = AuthConfig(
            pat_token=pat_token,
            organization=organization
        )

        return AzureDevOpsAuth(config)