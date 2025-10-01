"""
Tests for the data processor module.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone

from src.auth import AzureDevOpsAuth, AuthConfig
from src.data_processor import EntitlementDataProcessor
from src.models import (
    User, Group, Entitlement, GroupMembership, UserEntitlementSummary,
    OrganizationReport, SubjectKind, AccessLevel, GroupType
)


class TestEntitlementDataProcessor:
    """Tests for EntitlementDataProcessor."""

    def setup_method(self):
        """Set up test fixtures."""
        config = AuthConfig(pat_token="test-token", organization="test-org")
        self.auth = AzureDevOpsAuth(config)
        self.processor = EntitlementDataProcessor(self.auth)

    def test_init(self):
        """Test processor initialization."""
        assert self.processor.auth == self.auth
        assert self.processor.organization == "test-org"
        assert len(self.processor.users) == 0
        assert len(self.processor.groups) == 0
        assert len(self.processor.entitlements) == 0

    def test_retrieve_all_data(self):
        """Test complete data retrieval process."""
        # Mock the API clients directly on the processor instance
        self.processor.users_client = Mock()
        self.processor.groups_client = Mock()
        self.processor.entitlements_client = Mock()
        self.processor.membership_client = Mock()

        # Mock users
        self.processor.users_client.get_users.return_value = [
            User(descriptor="user-1", display_name="John Doe"),
            User(descriptor="user-2", display_name="Jane Smith")
        ]

        # Mock groups
        self.processor.groups_client.get_groups.return_value = [
            Group(descriptor="group-1", display_name="Developers"),
            Group(descriptor="group-2", display_name="Admins")
        ]

        # Mock entitlements
        self.processor.entitlements_client.get_entitlements.return_value = [
            Entitlement(user_descriptor="user-1", access_level=AccessLevel.BASIC),
            Entitlement(user_descriptor="user-2", access_level=AccessLevel.STAKEHOLDER)
        ]

        # Mock memberships
        self.processor.membership_client.get_group_memberships.return_value = [
            GroupMembership(
                group_descriptor="group-1",
                member_descriptor="user-1",
                member_type=SubjectKind.USER
            )
        ]

        # Run data retrieval
        self.processor.retrieve_all_data()

        # Verify data was retrieved and stored
        assert len(self.processor.users) == 2
        assert len(self.processor.groups) == 2
        assert len(self.processor.entitlements) == 2
        assert "user-1" in self.processor.users
        assert "group-1" in self.processor.groups

    def test_build_membership_maps(self):
        """Test building membership lookup maps."""
        # Set up test data
        self.processor.memberships = [
            GroupMembership(
                group_descriptor="group-1",
                member_descriptor="user-1",
                member_type=SubjectKind.USER
            ),
            GroupMembership(
                group_descriptor="group-1",
                member_descriptor="user-2",
                member_type=SubjectKind.USER
            ),
            GroupMembership(
                group_descriptor="group-2",
                member_descriptor="user-1",
                member_type=SubjectKind.USER
            )
        ]

        self.processor._build_membership_maps()

        # Check group -> members mapping
        assert len(self.processor.group_memberships_map["group-1"]) == 2
        assert "user-1" in self.processor.group_memberships_map["group-1"]
        assert "user-2" in self.processor.group_memberships_map["group-1"]
        assert len(self.processor.group_memberships_map["group-2"]) == 1

        # Check user -> groups mapping
        assert len(self.processor.user_memberships_map["user-1"]) == 2
        assert "group-1" in self.processor.user_memberships_map["user-1"]
        assert "group-2" in self.processor.user_memberships_map["user-1"]

    def test_create_user_summary(self):
        """Test creating user entitlement summary."""
        # Set up test data
        user = User(descriptor="user-1", display_name="John Doe", mail_address="john@test.com")
        entitlement = Entitlement(user_descriptor="user-1", access_level=AccessLevel.BASIC)
        group = Group(
            descriptor="group-1",
            display_name="Developers",
            group_type=GroupType.AZURE_AD
        )

        self.processor.users = {"user-1": user}
        self.processor.groups = {"group-1": group}
        self.processor.entitlements = {"user-1": entitlement}
        self.processor.user_memberships_map = {"user-1": ["group-1"]}

        summary = self.processor._create_user_summary(user)

        assert summary.user.descriptor == "user-1"
        assert summary.entitlement.access_level == AccessLevel.BASIC
        assert len(summary.direct_groups) == 1
        assert summary.direct_groups[0].display_name == "Developers"
        assert summary.effective_access_level == AccessLevel.BASIC
        assert len(summary.chargeback_groups) == 1
        assert "Developers" in summary.chargeback_groups

    def test_get_all_user_groups_recursive(self):
        """Test recursive group membership resolution."""
        # Set up nested group structure
        # user-1 -> group-1 -> group-2 -> group-3
        self.processor.user_memberships_map = {
            "user-1": ["group-1"],
            "group-1": ["group-2"],
            "group-2": ["group-3"]
        }

        all_groups = self.processor._get_all_user_groups("user-1")

        assert len(all_groups) == 3
        assert "group-1" in all_groups
        assert "group-2" in all_groups
        assert "group-3" in all_groups

    def test_get_all_user_groups_cycle_detection(self):
        """Test cycle detection in group membership."""
        # Set up circular reference: group-1 -> group-2 -> group-1
        self.processor.user_memberships_map = {
            "user-1": ["group-1"],
            "group-1": ["group-2"],
            "group-2": ["group-1"]  # Circular reference
        }

        all_groups = self.processor._get_all_user_groups("user-1")

        # Should not get stuck in infinite loop
        assert len(all_groups) == 2
        assert "group-1" in all_groups
        assert "group-2" in all_groups

    def test_calculate_effective_access_level(self):
        """Test effective access level calculation."""
        user = User(descriptor="user-1", display_name="John Doe")
        entitlement = Entitlement(user_descriptor="user-1", access_level=AccessLevel.BASIC)
        groups = []

        # With entitlement
        access_level = self.processor._calculate_effective_access_level(user, entitlement, groups)
        assert access_level == AccessLevel.BASIC

        # Without entitlement
        access_level = self.processor._calculate_effective_access_level(user, None, groups)
        assert access_level == AccessLevel.NONE

    def test_determine_chargeback_groups(self):
        """Test determining chargeback groups."""
        groups = [
            Group(
                descriptor="group-1",
                display_name="Developers Team",
                group_type=GroupType.AZURE_AD,
                origin="aad"  # External group
            ),
            Group(
                descriptor="group-2",
                display_name="Project Collection Administrators",  # System group
                group_type=GroupType.AZURE_AD,
                origin="vsts"  # Built-in VSTS group
            ),
            Group(
                descriptor="group-3",
                display_name="Marketing Team",
                group_type=GroupType.WINDOWS,
                origin="aad"  # External group
            ),
            Group(
                descriptor="group-4",
                display_name="Custom Group",
                group_type=GroupType.UNKNOWN  # Should be excluded
            )
        ]

        chargeback_groups = self.processor._determine_chargeback_groups(groups)

        # Should include Azure AD and Windows groups, but exclude system and unknown groups
        assert len(chargeback_groups) == 2
        assert "Developers Team" in chargeback_groups
        assert "Marketing Team" in chargeback_groups
        assert "Project Collection Administrators" not in chargeback_groups
        assert "Custom Group" not in chargeback_groups

    def test_is_system_group(self):
        """Test system group detection."""
        system_group = Group(
            descriptor="group-sys",
            display_name="Project Collection Administrators",
            origin="vsts"  # System groups have 'vsts' origin
        )
        user_group = Group(
            descriptor="group-user",
            display_name="Development Team",
            origin="aad"  # User groups typically have other origins
        )

        assert self.processor._is_system_group(system_group) is True
        assert self.processor._is_system_group(user_group) is False

    def test_process_user_entitlements(self):
        """Test processing user entitlements."""
        # Set up test data
        user1 = User(descriptor="user-1", display_name="John Doe")
        user2 = User(descriptor="user-2", display_name="Jane Smith")

        self.processor.users = {"user-1": user1, "user-2": user2}
        self.processor.groups = {}
        self.processor.entitlements = {
            "user-1": Entitlement(user_descriptor="user-1", access_level=AccessLevel.BASIC)
        }
        self.processor.user_memberships_map = defaultdict(list)

        self.processor.process_user_entitlements()

        assert len(self.processor.user_summaries) == 2
        assert self.processor.user_summaries[0].user.descriptor in ["user-1", "user-2"]

    def test_generate_organization_report(self):
        """Test generating organization report."""
        # Set up test data
        user = User(descriptor="user-1", display_name="John Doe")
        group = Group(
            descriptor="group-1",
            display_name="Developers",
            group_type=GroupType.AZURE_AD,
            member_count=0
        )
        entitlement = Entitlement(user_descriptor="user-1", access_level=AccessLevel.BASIC)

        summary = UserEntitlementSummary(
            user=user,
            entitlement=entitlement,
            chargeback_groups=["Developers"]
        )

        self.processor.users = {"user-1": user}
        self.processor.groups = {"group-1": group}
        self.processor.entitlements = {"user-1": entitlement}
        self.processor.user_summaries = [summary]

        report = self.processor.generate_organization_report()

        assert report.organization == "test-org"
        assert report.total_users == 1
        assert report.total_groups == 1
        assert report.total_entitlements == 1
        assert len(report.user_summaries) == 1
        assert report.groups_by_type["azureActiveDirectory"] == 1
        assert len(report.orphaned_groups) == 1  # group has 0 members
        assert report.licenses_by_type["basic"] == 1

    def test_generate_chargeback_analysis(self):
        """Test generating chargeback analysis."""
        user1 = User(descriptor="user-1", display_name="John Doe", mail_address="john@test.com")
        user2 = User(descriptor="user-2", display_name="Jane Smith", mail_address="jane@test.com")

        summary1 = UserEntitlementSummary(
            user=user1,
            entitlement=Entitlement(user_descriptor="user-1", access_level=AccessLevel.BASIC),
            effective_access_level=AccessLevel.BASIC,
            chargeback_groups=["Developers", "Team Leads"],
            license_cost=50.0
        )

        summary2 = UserEntitlementSummary(
            user=user2,
            entitlement=Entitlement(user_descriptor="user-2", access_level=AccessLevel.STAKEHOLDER),
            effective_access_level=AccessLevel.STAKEHOLDER,
            chargeback_groups=["Developers"],
            license_cost=25.0
        )

        self.processor.user_summaries = [summary1, summary2]

        chargeback_analysis = self.processor._generate_chargeback_analysis()

        # Check Developers group
        developers_data = chargeback_analysis["Developers"]
        assert developers_data["total_users"] == 2
        assert len(developers_data["users"]) == 2
        assert developers_data["licenses"]["basic"] == 1
        assert developers_data["licenses"]["stakeholder"] == 1
        assert developers_data["total_cost"] == 75.0

        # Check Team Leads group
        team_leads_data = chargeback_analysis["Team Leads"]
        assert team_leads_data["total_users"] == 1
        assert len(team_leads_data["users"]) == 1
        assert team_leads_data["total_cost"] == 50.0

    @patch.object(EntitlementDataProcessor, 'retrieve_all_data')
    @patch.object(EntitlementDataProcessor, 'process_user_entitlements')
    @patch.object(EntitlementDataProcessor, 'generate_organization_report')
    def test_run_complete_analysis(self, mock_generate_report, mock_process_entitlements, mock_retrieve_data):
        """Test running complete analysis."""
        mock_report = OrganizationReport(organization="test-org")
        mock_generate_report.return_value = mock_report

        result = self.processor.run_complete_analysis()

        mock_retrieve_data.assert_called_once()
        mock_process_entitlements.assert_called_once()
        mock_generate_report.assert_called_once()
        assert result == mock_report

    def test_is_vsts_user(self):
        """Test VSTS user detection."""
        # VSTS user by origin
        vsts_user = User(descriptor="user-1", display_name="Test User", origin="vsts")
        assert self.processor._is_vsts_user(vsts_user) is True

        # Service account by name
        service_user = User(descriptor="user-2", display_name="Project Collection Build Service")
        assert self.processor._is_vsts_user(service_user) is True

        # Regular user
        regular_user = User(descriptor="user-3", display_name="John Doe", origin="aad")
        assert self.processor._is_vsts_user(regular_user) is False

    def test_is_vsts_group(self):
        """Test VSTS group detection."""
        # VSTS group
        vsts_group = Group(descriptor="group-1", display_name="Contributors", origin="vsts")
        assert self.processor._is_vsts_group(vsts_group) is True

        # Regular group
        regular_group = Group(descriptor="group-2", display_name="Dev Team", origin="aad")
        assert self.processor._is_vsts_group(regular_group) is False

    def test_retrieve_all_data_with_filtering(self):
        """Test data retrieval with VSTS filtering enabled."""
        from src.config import ReportsConfig

        # Create processor with filtering enabled
        config = ReportsConfig(exclude_vsts_users=True, exclude_vsts_groups=True)
        processor = EntitlementDataProcessor(self.auth, config=config)

        # Mock API clients
        processor.users_client = Mock()
        processor.groups_client = Mock()
        processor.entitlements_client = Mock()
        processor.membership_client = Mock()

        # Mock users (mix of regular and VSTS)
        processor.users_client.get_users.return_value = [
            User(descriptor="user-1", display_name="John Doe", origin="aad"),
            User(descriptor="user-2", display_name="Build Service", origin="vsts"),  # Should be filtered
            User(descriptor="user-3", display_name="Jane Smith", origin="aad")
        ]

        # Mock groups (mix of regular and VSTS)
        processor.groups_client.get_groups.return_value = [
            Group(descriptor="group-1", display_name="Developers", origin="aad"),
            Group(descriptor="group-2", display_name="Contributors", origin="vsts"),  # Should be filtered
            Group(descriptor="group-3", display_name="QA Team", origin="aad")
        ]

        # Mock entitlements
        processor.entitlements_client.get_entitlements.return_value = [
            Entitlement(user_descriptor="user-1", access_level=AccessLevel.BASIC),
            Entitlement(user_descriptor="user-3", access_level=AccessLevel.BASIC)
        ]

        # Mock memberships
        processor.membership_client.get_group_memberships.return_value = []

        # Retrieve data
        processor.retrieve_all_data()

        # Verify VSTS users and groups were filtered out
        assert len(processor.users) == 2  # Only 2 regular users
        assert "user-1" in processor.users
        assert "user-2" not in processor.users  # VSTS user filtered
        assert "user-3" in processor.users

        assert len(processor.groups) == 2  # Only 2 regular groups
        assert "group-1" in processor.groups
        assert "group-2" not in processor.groups  # VSTS group filtered
        assert "group-3" in processor.groups

    def test_retrieve_all_data_without_filtering(self):
        """Test data retrieval with VSTS filtering disabled."""
        from src.config import ReportsConfig

        # Create processor with filtering disabled
        config = ReportsConfig(exclude_vsts_users=False, exclude_vsts_groups=False)
        processor = EntitlementDataProcessor(self.auth, config=config)

        # Mock API clients
        processor.users_client = Mock()
        processor.groups_client = Mock()
        processor.entitlements_client = Mock()
        processor.membership_client = Mock()

        # Mock users (mix of regular and VSTS)
        processor.users_client.get_users.return_value = [
            User(descriptor="user-1", display_name="John Doe", origin="aad"),
            User(descriptor="user-2", display_name="Build Service", origin="vsts"),
            User(descriptor="user-3", display_name="Jane Smith", origin="aad")
        ]

        # Mock groups (mix of regular and VSTS)
        processor.groups_client.get_groups.return_value = [
            Group(descriptor="group-1", display_name="Developers", origin="aad"),
            Group(descriptor="group-2", display_name="Contributors", origin="vsts"),
            Group(descriptor="group-3", display_name="QA Team", origin="aad")
        ]

        # Mock entitlements
        processor.entitlements_client.get_entitlements.return_value = [
            Entitlement(user_descriptor="user-1", access_level=AccessLevel.BASIC),
            Entitlement(user_descriptor="user-2", access_level=AccessLevel.BASIC),
            Entitlement(user_descriptor="user-3", access_level=AccessLevel.BASIC)
        ]

        # Mock memberships
        processor.membership_client.get_group_memberships.return_value = []

        # Retrieve data
        processor.retrieve_all_data()

        # Verify all users and groups are included
        assert len(processor.users) == 3  # All users included
        assert "user-1" in processor.users
        assert "user-2" in processor.users  # VSTS user included
        assert "user-3" in processor.users

        assert len(processor.groups) == 3  # All groups included
        assert "group-1" in processor.groups
        assert "group-2" in processor.groups  # VSTS group included
        assert "group-3" in processor.groups


# Helper for defaultdict import in test
from collections import defaultdict