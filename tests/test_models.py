"""
Tests for the data models module.
"""

import pytest
from datetime import datetime, timezone
from pydantic import ValidationError

from src.models import (
    User, Group, Entitlement, GroupMembership, UserEntitlementSummary,
    OrganizationReport, SubjectKind, AccessLevel, GroupType
)


class TestUser:
    """Tests for User model."""

    def test_user_creation_minimal(self):
        """Test creating a user with minimal required fields."""
        user = User(
            descriptor="user-123",
            display_name="John Doe"
        )

        assert user.descriptor == "user-123"
        assert user.display_name == "John Doe"
        assert user.subject_kind == SubjectKind.USER
        assert user.metadata == {}

    def test_user_creation_full(self):
        """Test creating a user with all fields."""
        user = User(
            descriptor="user-123",
            display_name="John Doe",
            unique_name="john.doe@company.com",
            principal_name="john.doe@company.com",
            mail_address="john.doe@company.com",
            domain="company.com",
            origin="aad",
            origin_id="aad-123",
            is_active=True,
            metadata={"custom": "value"}
        )

        assert user.unique_name == "john.doe@company.com"
        assert user.domain == "company.com"
        assert user.is_active is True
        assert user.metadata["custom"] == "value"

    def test_user_empty_display_name(self):
        """Test that empty display name is rejected."""
        with pytest.raises(ValidationError, match="Name fields cannot be empty strings"):
            User(descriptor="user-123", display_name="   ")

    def test_user_whitespace_stripping(self):
        """Test that whitespace is stripped from string fields."""
        user = User(
            descriptor="  user-123  ",
            display_name="  John Doe  "
        )

        assert user.descriptor == "user-123"
        assert user.display_name == "John Doe"


class TestGroup:
    """Tests for Group model."""

    def test_group_creation_minimal(self):
        """Test creating a group with minimal required fields."""
        group = Group(
            descriptor="group-123",
            display_name="Developers"
        )

        assert group.descriptor == "group-123"
        assert group.display_name == "Developers"
        assert group.subject_kind == SubjectKind.GROUP
        assert group.members == []

    def test_group_creation_with_members(self):
        """Test creating a group with members."""
        group = Group(
            descriptor="group-123",
            display_name="Developers",
            group_type=GroupType.AZURE_AD,
            member_count=5,
            members=["user-1", "user-2", "user-3"]
        )

        assert group.group_type == GroupType.AZURE_AD
        assert group.member_count == 5
        assert len(group.members) == 3

    def test_group_security_group(self):
        """Test group with security information."""
        group = Group(
            descriptor="group-123",
            display_name="Security Group",
            security_id="S-1-5-21-123456789",
            is_security_group=True
        )

        assert group.security_id == "S-1-5-21-123456789"
        assert group.is_security_group is True


class TestEntitlement:
    """Tests for Entitlement model."""

    def test_entitlement_creation_minimal(self):
        """Test creating an entitlement with minimal required fields."""
        entitlement = Entitlement(
            user_descriptor="user-123",
            access_level=AccessLevel.BASIC
        )

        assert entitlement.user_descriptor == "user-123"
        assert entitlement.access_level == AccessLevel.BASIC
        assert entitlement.project_entitlements == []
        assert entitlement.group_assignments == []

    def test_entitlement_creation_full(self):
        """Test creating an entitlement with all fields."""
        entitlement = Entitlement(
            user_descriptor="user-123",
            access_level=AccessLevel.VISUAL_STUDIO_SUBSCRIBER,
            license_display_name="Visual Studio Subscriber",
            license_name="vs-subscriber",
            account_license_type="msdn",
            assignment_source="group",
            project_entitlements=["project-1", "project-2"],
            group_assignments=["group-1", "group-2"]
        )

        assert entitlement.access_level == AccessLevel.VISUAL_STUDIO_SUBSCRIBER
        assert entitlement.license_display_name == "Visual Studio Subscriber"
        assert len(entitlement.project_entitlements) == 2
        assert len(entitlement.group_assignments) == 2

    def test_entitlement_with_extensions(self):
        """Test entitlement with extensions."""
        extensions = [
            {"id": "ext-1", "name": "Test Extension"},
            {"id": "ext-2", "name": "Another Extension"}
        ]

        entitlement = Entitlement(
            user_descriptor="user-123",
            access_level=AccessLevel.BASIC,
            extensions=extensions
        )

        assert len(entitlement.extensions) == 2
        assert entitlement.extensions[0]["id"] == "ext-1"


class TestGroupMembership:
    """Tests for GroupMembership model."""

    def test_group_membership_creation(self):
        """Test creating a group membership."""
        membership = GroupMembership(
            group_descriptor="group-123",
            member_descriptor="user-456",
            member_type=SubjectKind.USER
        )

        assert membership.group_descriptor == "group-123"
        assert membership.member_descriptor == "user-456"
        assert membership.member_type == SubjectKind.USER

    def test_group_membership_with_metadata(self):
        """Test group membership with additional metadata."""
        now = datetime.now(timezone.utc)
        membership = GroupMembership(
            group_descriptor="group-123",
            member_descriptor="group-456",
            member_type=SubjectKind.GROUP,
            is_active=True,
            date_created=now,
            metadata={"source": "inheritance"}
        )

        assert membership.member_type == SubjectKind.GROUP
        assert membership.is_active is True
        assert membership.date_created == now
        assert membership.metadata["source"] == "inheritance"


class TestUserEntitlementSummary:
    """Tests for UserEntitlementSummary model."""

    def test_user_summary_creation(self):
        """Test creating a user entitlement summary."""
        user = User(descriptor="user-123", display_name="John Doe")
        entitlement = Entitlement(user_descriptor="user-123", access_level=AccessLevel.BASIC)
        groups = [
            Group(descriptor="group-1", display_name="Developers"),
            Group(descriptor="group-2", display_name="Team Lead")
        ]

        summary = UserEntitlementSummary(
            user=user,
            entitlement=entitlement,
            direct_groups=groups,
            all_groups=groups,
            effective_access_level=AccessLevel.BASIC,
            chargeback_groups=["Developers", "Team Lead"]
        )

        assert summary.user.descriptor == "user-123"
        assert summary.entitlement.access_level == AccessLevel.BASIC
        assert len(summary.direct_groups) == 2
        assert len(summary.chargeback_groups) == 2
        assert isinstance(summary.last_updated, datetime)

    def test_user_summary_without_entitlement(self):
        """Test user summary without entitlement."""
        user = User(descriptor="user-123", display_name="John Doe")

        summary = UserEntitlementSummary(
            user=user,
            entitlement=None,
            effective_access_level=AccessLevel.NONE
        )

        assert summary.entitlement is None
        assert summary.effective_access_level == AccessLevel.NONE

    def test_user_summary_with_license_cost(self):
        """Test user summary with license cost calculation."""
        user = User(descriptor="user-123", display_name="John Doe")
        entitlement = Entitlement(user_descriptor="user-123", access_level=AccessLevel.BASIC)

        summary = UserEntitlementSummary(
            user=user,
            entitlement=entitlement,
            license_cost=50.0
        )

        assert summary.license_cost == 50.0


class TestOrganizationReport:
    """Tests for OrganizationReport model."""

    def test_organization_report_creation_minimal(self):
        """Test creating an organization report with minimal data."""
        report = OrganizationReport(
            organization="test-org"
        )

        assert report.organization == "test-org"
        assert isinstance(report.generated_at, datetime)
        assert report.total_users == 0
        assert report.total_groups == 0
        assert report.total_entitlements == 0
        assert report.user_summaries == []

    def test_organization_report_creation_full(self):
        """Test creating a complete organization report."""
        user = User(descriptor="user-123", display_name="John Doe")
        entitlement = Entitlement(user_descriptor="user-123", access_level=AccessLevel.BASIC)
        group = Group(descriptor="group-123", display_name="Developers")

        summary = UserEntitlementSummary(
            user=user,
            entitlement=entitlement,
            direct_groups=[group]
        )

        report = OrganizationReport(
            organization="test-org",
            total_users=1,
            total_groups=1,
            total_entitlements=1,
            user_summaries=[summary],
            groups_by_type={"azureActiveDirectory": 1},
            orphaned_groups=[],
            licenses_by_type={"basic": 1},
            total_license_cost=50.0,
            chargeback_by_group={
                "Developers": {
                    "users": [{"name": "John Doe", "access_level": "basic"}],
                    "total_users": 1,
                    "total_cost": 50.0
                }
            }
        )

        assert report.total_users == 1
        assert report.total_groups == 1
        assert len(report.user_summaries) == 1
        assert report.groups_by_type["azureActiveDirectory"] == 1
        assert report.licenses_by_type["basic"] == 1
        assert report.total_license_cost == 50.0
        assert "Developers" in report.chargeback_by_group

    def test_organization_report_with_orphaned_groups(self):
        """Test organization report with orphaned groups."""
        orphaned_group = Group(
            descriptor="group-orphan",
            display_name="Orphaned Group",
            member_count=0
        )

        report = OrganizationReport(
            organization="test-org",
            orphaned_groups=[orphaned_group]
        )

        assert len(report.orphaned_groups) == 1
        assert report.orphaned_groups[0].display_name == "Orphaned Group"


class TestEnums:
    """Tests for enum types."""

    def test_subject_kind_enum(self):
        """Test SubjectKind enum values."""
        assert SubjectKind.USER == "user"
        assert SubjectKind.GROUP == "group"
        assert SubjectKind.SERVICE_PRINCIPAL == "servicePrincipal"

    def test_access_level_enum(self):
        """Test AccessLevel enum values."""
        assert AccessLevel.NONE == "none"
        assert AccessLevel.BASIC == "basic"
        assert AccessLevel.STAKEHOLDER == "stakeholder"
        assert AccessLevel.VISUAL_STUDIO_SUBSCRIBER == "visualStudioSubscriber"

    def test_group_type_enum(self):
        """Test GroupType enum values."""
        assert GroupType.WINDOWS == "windows"
        assert GroupType.AZURE_AD == "azureActiveDirectory"
        assert GroupType.SERVICE_PRINCIPAL == "servicePrincipal"
        assert GroupType.UNKNOWN == "unknown"