"""
Tests for the data retrieval module.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import requests
from requests.exceptions import HTTPError, RequestException

from src.auth import AzureDevOpsAuth, AuthConfig
from src.data_retrieval import (
    AzureDevOpsApiClient, UsersApiClient, GroupsApiClient,
    EntitlementsApiClient, MembershipApiClient, RateLimitError
)
from src.models import User, Group, Entitlement, GroupMembership, SubjectKind, AccessLevel


class TestAzureDevOpsApiClient:
    """Tests for AzureDevOpsApiClient base class."""

    def setup_method(self):
        """Set up test fixtures."""
        config = AuthConfig(pat_token="test-token", organization="test-org")
        self.auth = AzureDevOpsAuth(config)
        self.client = AzureDevOpsApiClient(self.auth)

    def test_init(self):
        """Test client initialization."""
        assert self.client.auth == self.auth
        assert self.client.max_retries == 3
        assert self.client.retry_delay == 1
        assert self.client.session is not None

    def test_init_custom_settings(self):
        """Test client initialization with custom settings."""
        client = AzureDevOpsApiClient(self.auth, max_retries=5, retry_delay=2)
        assert client.max_retries == 5
        assert client.retry_delay == 2

    @patch('src.data_retrieval.requests.Session.get')
    def test_handle_response_success(self, mock_get):
        """Test successful response handling."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.ok = True
        mock_response.json.return_value = {"test": "data"}

        result = self.client._handle_response(mock_response)
        assert result == {"test": "data"}

    @patch('src.data_retrieval.requests.Session.get')
    def test_handle_response_rate_limit(self, mock_get):
        """Test rate limit response handling."""
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.headers = {'Retry-After': '60'}

        with pytest.raises(RateLimitError) as exc_info:
            self.client._handle_response(mock_response)

        assert exc_info.value.retry_after == 60

    @patch('src.data_retrieval.requests.Session.get')
    def test_handle_response_http_error(self, mock_get):
        """Test HTTP error response handling."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.ok = False
        mock_response.json.return_value = {"message": "Not found"}
        mock_response.raise_for_status.side_effect = HTTPError("404 Error")

        with pytest.raises(HTTPError):
            self.client._handle_response(mock_response)

    @patch('src.data_retrieval.requests.Session.get')
    def test_make_request_success(self, mock_get):
        """Test successful API request."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.ok = True
        mock_response.json.return_value = {"test": "data"}
        mock_get.return_value = mock_response

        result = self.client._make_request("https://api.test.com", {"param": "value"})
        assert result == {"test": "data"}

    @patch('src.data_retrieval.requests.Session.get')
    @patch('src.data_retrieval.time.sleep')
    def test_make_request_rate_limit_retry(self, mock_sleep, mock_get):
        """Test rate limit handling with retry."""
        # First call returns rate limit, second succeeds
        rate_limit_response = Mock()
        rate_limit_response.status_code = 429
        rate_limit_response.headers = {'Retry-After': '2'}

        success_response = Mock()
        success_response.status_code = 200
        success_response.ok = True
        success_response.json.return_value = {"test": "data"}

        mock_get.side_effect = [rate_limit_response, success_response]

        result = self.client._make_request("https://api.test.com")
        assert result == {"test": "data"}
        mock_sleep.assert_called_once_with(2)

    @patch('src.data_retrieval.requests.Session.get')
    def test_paginate_request(self, mock_get):
        """Test paginated request handling."""
        # First page
        page1_response = Mock()
        page1_response.status_code = 200
        page1_response.ok = True
        page1_response.json.return_value = {
            "value": [{"id": 1}, {"id": 2}],
            "continuationToken": "token123"
        }

        # Second page
        page2_response = Mock()
        page2_response.status_code = 200
        page2_response.ok = True
        page2_response.json.return_value = {
            "value": [{"id": 3}, {"id": 4}]
        }

        mock_get.side_effect = [page1_response, page2_response]

        items = list(self.client._paginate_request("https://api.test.com"))
        assert len(items) == 4
        assert items[0]["id"] == 1
        assert items[3]["id"] == 4


class TestUsersApiClient:
    """Tests for UsersApiClient."""

    def setup_method(self):
        """Set up test fixtures."""
        config = AuthConfig(pat_token="test-token", organization="test-org")
        self.auth = AzureDevOpsAuth(config)
        self.client = UsersApiClient(self.auth)

    @patch.object(UsersApiClient, '_paginate_request')
    def test_get_users(self, mock_paginate):
        """Test retrieving users."""
        mock_paginate.return_value = [
            {
                "descriptor": "user-1",
                "displayName": "John Doe",
                "uniqueName": "john@test.com",
                "mailAddress": "john@test.com"
            },
            {
                "descriptor": "user-2",
                "displayName": "Jane Smith",
                "uniqueName": "jane@test.com",
                "mailAddress": "jane@test.com"
            }
        ]

        users = self.client.get_users()
        assert len(users) == 2
        assert users[0].descriptor == "user-1"
        assert users[0].display_name == "John Doe"
        assert users[1].descriptor == "user-2"
        assert users[1].display_name == "Jane Smith"

    @patch.object(UsersApiClient, '_make_request')
    def test_get_user_by_descriptor_success(self, mock_request):
        """Test retrieving user by descriptor successfully."""
        mock_request.return_value = {
            "descriptor": "user-1",
            "displayName": "John Doe",
            "uniqueName": "john@test.com"
        }

        user = self.client.get_user_by_descriptor("user-1")
        assert user is not None
        assert user.descriptor == "user-1"
        assert user.display_name == "John Doe"

    @patch.object(UsersApiClient, '_make_request')
    def test_get_user_by_descriptor_not_found(self, mock_request):
        """Test retrieving non-existent user."""
        mock_response = Mock()
        mock_response.status_code = 404
        error = HTTPError("Not found")
        error.response = mock_response
        mock_request.side_effect = error

        user = self.client.get_user_by_descriptor("nonexistent")
        assert user is None

    def test_parse_user(self):
        """Test parsing user data."""
        user_data = {
            "descriptor": "user-1",
            "displayName": "John Doe",
            "uniqueName": "john@test.com",
            "principalName": "john@test.com",
            "mailAddress": "john@test.com",
            "domain": "test.com",
            "origin": "aad",
            "originId": "aad-123",
            "isActive": True
        }

        user = self.client._parse_user(user_data)
        assert user.descriptor == "user-1"
        assert user.display_name == "John Doe"
        assert user.unique_name == "john@test.com"
        assert user.subject_kind == SubjectKind.USER
        assert user.is_active is True


class TestGroupsApiClient:
    """Tests for GroupsApiClient."""

    def setup_method(self):
        """Set up test fixtures."""
        config = AuthConfig(pat_token="test-token", organization="test-org")
        self.auth = AzureDevOpsAuth(config)
        self.client = GroupsApiClient(self.auth)

    @patch.object(GroupsApiClient, '_paginate_request')
    def test_get_groups(self, mock_paginate):
        """Test retrieving groups."""
        mock_paginate.return_value = [
            {
                "descriptor": "group-1",
                "displayName": "Developers",
                "origin": "aad"
            },
            {
                "descriptor": "group-2",
                "displayName": "Admins",
                "origin": "windows"
            }
        ]

        groups = self.client.get_groups()
        assert len(groups) == 2
        assert groups[0].descriptor == "group-1"
        assert groups[0].display_name == "Developers"

    def test_parse_group_azure_ad(self):
        """Test parsing Azure AD group."""
        group_data = {
            "descriptor": "group-1",
            "displayName": "Azure AD Group",
            "origin": "aad",
            "isActive": True
        }

        group = self.client._parse_group(group_data)
        assert group.descriptor == "group-1"
        assert group.display_name == "Azure AD Group"
        assert group.group_type.value == "azureActiveDirectory"

    def test_parse_group_windows(self):
        """Test parsing Windows group."""
        group_data = {
            "descriptor": "group-2",
            "displayName": "Windows Group",
            "origin": "windows",
            "securityId": "S-1-5-21-123"
        }

        group = self.client._parse_group(group_data)
        assert group.group_type.value == "windows"
        assert group.security_id == "S-1-5-21-123"


class TestEntitlementsApiClient:
    """Tests for EntitlementsApiClient."""

    def setup_method(self):
        """Set up test fixtures."""
        config = AuthConfig(pat_token="test-token", organization="test-org")
        self.auth = AzureDevOpsAuth(config)
        self.client = EntitlementsApiClient(self.auth)

    @patch.object(EntitlementsApiClient, 'get_entitlement_by_user_id')
    def test_get_entitlements(self, mock_get_by_id):
        """Test retrieving entitlements."""
        # Create test users
        test_users = [
            User(descriptor="user-1", display_name="John Doe"),
            User(descriptor="user-2", display_name="Jane Smith")
        ]

        # Mock the individual entitlement lookups
        mock_get_by_id.side_effect = [
            Entitlement(
                user_descriptor="user-1",
                access_level=AccessLevel.BASIC,
                account_license_type="basic",
                license_display_name="Basic"
            ),
            Entitlement(
                user_descriptor="user-2",
                access_level=AccessLevel.STAKEHOLDER,
                account_license_type="stakeholder",
                license_display_name="Stakeholder"
            )
        ]

        entitlements = self.client.get_entitlements(users=test_users)
        assert len(entitlements) == 2
        assert entitlements[0].user_descriptor == "user-1"
        assert entitlements[0].access_level == AccessLevel.BASIC
        assert entitlements[1].user_descriptor == "user-2"
        assert entitlements[1].access_level == AccessLevel.STAKEHOLDER

    def test_parse_entitlement(self):
        """Test parsing entitlement data per Microsoft API spec."""
        # Test Visual Studio Subscriber (none + msdn + eligible)
        entitlement_data = {
            "user": {"descriptor": "user-1"},
            "accessLevel": {
                "accountLicenseType": "none",
                "licenseDisplayName": "Visual Studio Subscriber",
                "licensingSource": "msdn",
                "msdnLicenseType": "eligible",
                "assignmentSource": "group"
            },
            "projectEntitlements": [
                {"projectRef": {"id": "project-1"}}
            ],
            "groupAssignments": [
                {"group": {"descriptor": "group-1"}}
            ],
            "extensions": [{"id": "ext-1"}]
        }

        entitlement = self.client._parse_entitlement(entitlement_data)
        assert entitlement.user_descriptor == "user-1"
        assert entitlement.access_level == AccessLevel.VISUAL_STUDIO_SUBSCRIBER
        assert entitlement.license_display_name == "Visual Studio Subscriber"
        assert len(entitlement.project_entitlements) == 1
        assert len(entitlement.group_assignments) == 1
        assert len(entitlement.extensions) == 1

        # Test Basic (express + account + none)
        basic_data = {
            "user": {"descriptor": "user-2"},
            "accessLevel": {
                "accountLicenseType": "express",
                "licenseDisplayName": "Basic",
                "licensingSource": "account",
                "msdnLicenseType": "none",
                "assignmentSource": "group"
            },
            "projectEntitlements": [],
            "groupAssignments": []
        }
        basic_entitlement = self.client._parse_entitlement(basic_data)
        assert basic_entitlement.access_level == AccessLevel.BASIC

        # Test Basic + Test Plans (advanced + account + none)
        advanced_data = {
            "user": {"descriptor": "user-3"},
            "accessLevel": {
                "accountLicenseType": "advanced",
                "licenseDisplayName": "Basic + Test Plans",
                "licensingSource": "account",
                "msdnLicenseType": "none"
            },
            "projectEntitlements": [],
            "groupAssignments": []
        }
        advanced_entitlement = self.client._parse_entitlement(advanced_data)
        assert advanced_entitlement.access_level == AccessLevel.BASIC_PLUS_TEST_PLANS

        # Test Visual Studio Enterprise (none + msdn + enterprise)
        enterprise_data = {
            "user": {"descriptor": "user-4"},
            "accessLevel": {
                "accountLicenseType": "none",
                "licenseDisplayName": "Visual Studio Enterprise",
                "licensingSource": "msdn",
                "msdnLicenseType": "enterprise"
            },
            "projectEntitlements": [],
            "groupAssignments": []
        }
        enterprise_entitlement = self.client._parse_entitlement(enterprise_data)
        assert enterprise_entitlement.access_level == AccessLevel.VISUAL_STUDIO_ENTERPRISE


class TestMembershipApiClient:
    """Tests for MembershipApiClient."""

    def setup_method(self):
        """Set up test fixtures."""
        config = AuthConfig(pat_token="test-token", organization="test-org")
        self.auth = AzureDevOpsAuth(config)
        self.client = MembershipApiClient(self.auth)

    @patch.object(MembershipApiClient, '_paginate_request')
    def test_get_group_memberships(self, mock_paginate):
        """Test retrieving group memberships."""
        mock_paginate.return_value = [
            {
                "containerDescriptor": "group-1",
                "memberDescriptor": "user-1",
                "subjectKind": "user",
                "isActive": True
            },
            {
                "containerDescriptor": "group-1",
                "memberDescriptor": "user-2",
                "subjectKind": "user",
                "isActive": True
            }
        ]

        memberships = self.client.get_group_memberships("group-1")
        assert len(memberships) == 2
        assert memberships[0].group_descriptor == "group-1"
        assert memberships[0].member_descriptor == "user-1"
        assert memberships[0].member_type == SubjectKind.USER

    @patch.object(MembershipApiClient, '_paginate_request')
    def test_get_user_memberships(self, mock_paginate):
        """Test retrieving user memberships."""
        mock_paginate.return_value = [
            {
                "containerDescriptor": "group-1",
                "memberDescriptor": "user-1",
                "subjectKind": "user",
                "isActive": True
            }
        ]

        memberships = self.client.get_user_memberships("user-1")
        assert len(memberships) == 1
        assert memberships[0].group_descriptor == "group-1"
        assert memberships[0].member_descriptor == "user-1"

    def test_parse_membership(self):
        """Test parsing membership data."""
        membership_data = {
            "containerDescriptor": "group-1",
            "memberDescriptor": "user-1",
            "subjectKind": "user",
            "isActive": True
        }

        membership = self.client._parse_membership(membership_data)
        assert membership.group_descriptor == "group-1"
        assert membership.member_descriptor == "user-1"
        assert membership.member_type == SubjectKind.USER
        assert membership.is_active is True


class TestRateLimitError:
    """Tests for RateLimitError exception."""

    def test_rate_limit_error_creation(self):
        """Test creating RateLimitError."""
        error = RateLimitError("Rate limit exceeded", retry_after=60)
        assert str(error) == "Rate limit exceeded"
        assert error.retry_after == 60

    def test_rate_limit_error_without_retry_after(self):
        """Test RateLimitError without retry_after."""
        error = RateLimitError("Rate limit exceeded")
        assert str(error) == "Rate limit exceeded"
        assert error.retry_after is None