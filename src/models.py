"""
Data Models for Azure DevOps Entities

This module defines Pydantic models for Azure DevOps users, groups, entitlements,
and related entities used in the entitlement reporting system.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Union
from enum import Enum

from pydantic import BaseModel, Field, field_validator, ConfigDict


class SubjectKind(str, Enum):
    """Types of subjects in Azure DevOps."""
    USER = "user"
    GROUP = "group"
    SERVICE_PRINCIPAL = "servicePrincipal"


class AccessLevel(str, Enum):
    """Azure DevOps access levels."""
    NONE = "none"
    STAKEHOLDER = "stakeholder"
    BASIC = "basic"
    BASIC_PLUS_TEST_PLANS = "basicPlusTestPlans"
    VISUAL_STUDIO_SUBSCRIBER = "visualStudioSubscriber"
    VISUAL_STUDIO_ENTERPRISE = "visualStudioEnterprise"
    VISUAL_STUDIO_PROFESSIONAL = "visualStudioProfessional"
    VISUAL_STUDIO_TEST_PROFESSIONAL = "visualStudioTestProfessional"


class GroupType(str, Enum):
    """Azure DevOps group types."""
    WINDOWS = "windows"
    AZURE_AD = "azureActiveDirectory"
    SERVICE_PRINCIPAL = "servicePrincipal"
    UNKNOWN = "unknown"


class User(BaseModel):
    """Azure DevOps user entity."""

    # Core identity fields
    descriptor: str = Field(..., description="Unique descriptor for the user")
    display_name: str = Field(..., description="User's display name")
    unique_name: Optional[str] = Field(None, description="User's unique name (email)")
    principal_name: Optional[str] = Field(None, description="User's principal name")
    mail_address: Optional[str] = Field(None, description="User's email address")

    # Identity metadata
    subject_kind: SubjectKind = Field(SubjectKind.USER, description="Type of subject")
    domain: Optional[str] = Field(None, description="User's domain")
    origin: Optional[str] = Field(None, description="Origin of the user account")
    origin_id: Optional[str] = Field(None, description="Original ID from the origin system")

    # Status information
    is_active: Optional[bool] = Field(None, description="Whether the user is active")
    last_changed: Optional[datetime] = Field(None, description="Last time user was modified")

    # Additional metadata
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional user metadata")

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True
    )

    @field_validator('display_name', 'unique_name', 'principal_name')
    @classmethod
    def validate_names(cls, v):
        """Validate name fields are not empty strings."""
        if v is not None and not v.strip():
            raise ValueError("Name fields cannot be empty strings")
        return v


class Group(BaseModel):
    """Azure DevOps group entity."""

    # Core identity fields
    descriptor: str = Field(..., description="Unique descriptor for the group")
    display_name: str = Field(..., description="Group's display name")
    principal_name: Optional[str] = Field(None, description="Group's principal name")
    mail_address: Optional[str] = Field(None, description="Group's email address")

    # Group metadata
    subject_kind: SubjectKind = Field(SubjectKind.GROUP, description="Type of subject")
    group_type: Optional[GroupType] = Field(None, description="Type of group")
    domain: Optional[str] = Field(None, description="Group's domain")
    origin: Optional[str] = Field(None, description="Origin of the group")
    origin_id: Optional[str] = Field(None, description="Original ID from the origin system")

    # Security and permissions
    security_id: Optional[str] = Field(None, description="Security identifier")
    is_security_group: Optional[bool] = Field(None, description="Whether this is a security group")

    # Status information
    is_active: Optional[bool] = Field(None, description="Whether the group is active")
    last_changed: Optional[datetime] = Field(None, description="Last time group was modified")

    # Membership information (populated separately)
    member_count: Optional[int] = Field(None, description="Number of members in the group")
    members: List[str] = Field(default_factory=list, description="List of member descriptors")

    # Additional metadata
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional group metadata")

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True
    )


class Entitlement(BaseModel):
    """Azure DevOps user entitlement entity."""

    # Core entitlement fields
    user_descriptor: str = Field(..., description="Descriptor of the entitled user")
    access_level: AccessLevel = Field(..., description="User's access level")

    # Licensing information
    license_display_name: Optional[str] = Field(None, description="Display name of the license")
    license_name: Optional[str] = Field(None, description="Technical name of the license")
    account_license_type: Optional[str] = Field(None, description="Type of account license")

    # Assignment information
    assignment_source: Optional[str] = Field(None, description="Source of the assignment")
    date_created: Optional[datetime] = Field(None, description="When the entitlement was created")
    last_accessed_date: Optional[datetime] = Field(None, description="When user last accessed")

    # Project and group memberships
    project_entitlements: List[str] = Field(default_factory=list, description="Project entitlements")
    group_assignments: List[str] = Field(default_factory=list, description="Group assignments")

    # Extensions and features
    extensions: List[Dict[str, Any]] = Field(default_factory=list, description="Extension entitlements")

    # Additional metadata
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional entitlement metadata")

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True
    )


class GroupMembership(BaseModel):
    """Azure DevOps group membership relationship."""

    # Relationship identifiers
    group_descriptor: str = Field(..., description="Descriptor of the group")
    member_descriptor: str = Field(..., description="Descriptor of the member")

    # Member information
    member_type: SubjectKind = Field(..., description="Type of member (user/group)")
    is_active: Optional[bool] = Field(None, description="Whether membership is active")

    # Membership metadata
    date_created: Optional[datetime] = Field(None, description="When membership was created")
    last_changed: Optional[datetime] = Field(None, description="Last time membership was modified")

    # Additional metadata
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional membership metadata")

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True
    )


class UserEntitlementSummary(BaseModel):
    """Summary of a user's complete entitlement information."""

    # User information
    user: User = Field(..., description="User entity")
    entitlement: Optional[Entitlement] = Field(None, description="User's entitlement")

    # Group memberships
    direct_groups: List[Group] = Field(default_factory=list, description="Direct group memberships")
    all_groups: List[Group] = Field(default_factory=list, description="All group memberships (including inherited)")

    # Calculated fields for reporting
    effective_access_level: Optional[AccessLevel] = Field(None, description="Effective access level")
    license_cost: Optional[float] = Field(None, description="Calculated license cost")
    chargeback_groups: List[str] = Field(default_factory=list, description="Groups for chargeback purposes")

    # Metadata
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="When this summary was generated")

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True
    )


class OrganizationReport(BaseModel):
    """Complete organization entitlement report."""

    # Organization information
    organization: str = Field(..., description="Organization name")
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Report generation time")

    # Entity counts
    total_users: int = Field(0, description="Total number of users")
    total_groups: int = Field(0, description="Total number of groups")
    total_entitlements: int = Field(0, description="Total number of entitlements")

    # User summaries
    user_summaries: List[UserEntitlementSummary] = Field(default_factory=list, description="User entitlement summaries")

    # Group analysis
    groups_by_type: Dict[str, int] = Field(default_factory=dict, description="Group counts by type")
    orphaned_groups: List[Group] = Field(default_factory=list, description="Groups with no members")

    # License analysis
    licenses_by_type: Dict[str, int] = Field(default_factory=dict, description="License counts by type")
    total_license_cost: Optional[float] = Field(None, description="Total calculated license cost")

    # Chargeback analysis
    chargeback_by_group: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="Chargeback analysis grouped by security groups"
    )

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True
    )


class ApiResponse(BaseModel):
    """Generic API response wrapper."""

    # Response metadata
    count: Optional[int] = Field(None, description="Number of items in response")
    value: List[Dict[str, Any]] = Field(default_factory=list, description="Response data")

    # Pagination
    continuation_token: Optional[str] = Field(None, description="Token for next page")

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True
    )


class ApiError(BaseModel):
    """API error response model."""

    # Error information
    error_code: Optional[str] = Field(None, description="Error code")
    message: str = Field(..., description="Error message")
    status_code: int = Field(..., description="HTTP status code")

    # Additional error details
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="When the error occurred")

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True
    )