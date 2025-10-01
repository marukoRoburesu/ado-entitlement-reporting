"""
Data Processing Engine for Azure DevOps Entitlement Reporting

This module provides the main data processing logic to cross-reference users,
groups, entitlements, and memberships for chargeback reporting.
"""

import logging
from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple, Any
from datetime import datetime, timezone

from src.auth import AzureDevOpsAuth
from src.config import ReportsConfig
from src.data_retrieval import (
    UsersApiClient, GroupsApiClient, EntitlementsApiClient, MembershipApiClient
)
from src.models import (
    User, Group, Entitlement, GroupMembership, UserEntitlementSummary,
    OrganizationReport, AccessLevel, SubjectKind
)


logger = logging.getLogger(__name__)


class EntitlementDataProcessor:
    """
    Main data processor for Azure DevOps entitlement reporting.

    This class orchestrates the retrieval and processing of all Azure DevOps
    data to generate comprehensive entitlement reports for chargeback purposes.
    """

    def __init__(
        self,
        auth: AzureDevOpsAuth,
        config: Optional[ReportsConfig] = None,
        max_retries: int = 3,
        retry_delay: int = 1
    ):
        """
        Initialize the data processor.

        Args:
            auth: Azure DevOps authentication handler
            config: Report configuration for filtering options
            max_retries: Maximum number of retry attempts for API calls
            retry_delay: Delay between retries in seconds
        """
        self.auth = auth
        self.organization = auth.config.organization
        self.config = config or ReportsConfig()

        # Initialize API clients
        self.users_client = UsersApiClient(auth, max_retries, retry_delay)
        self.groups_client = GroupsApiClient(auth, max_retries, retry_delay)
        self.entitlements_client = EntitlementsApiClient(auth, max_retries, retry_delay)
        self.membership_client = MembershipApiClient(auth, max_retries, retry_delay)

        # Data storage
        self.users: Dict[str, User] = {}
        self.groups: Dict[str, Group] = {}
        self.entitlements: Dict[str, Entitlement] = {}
        self.memberships: List[GroupMembership] = []

        # Processed data
        self.user_summaries: List[UserEntitlementSummary] = []
        self.group_memberships_map: Dict[str, List[str]] = defaultdict(list)
        self.user_memberships_map: Dict[str, List[str]] = defaultdict(list)

    def retrieve_all_data(self) -> None:
        """
        Retrieve all data from Azure DevOps APIs and apply configured filters.

        This method orchestrates the data retrieval process, fetching users,
        groups, entitlements, and memberships. It applies filtering based on
        configuration to remove VSTS built-in users/groups before processing.
        """
        logger.info(f"Starting data retrieval for organization: {self.organization}")

        # Step 1: Retrieve users
        logger.info("Retrieving users...")
        users_list = self.users_client.get_users()
        original_user_count = len(users_list)

        # Filter VSTS users if configured
        if self.config.exclude_vsts_users:
            users_list = [u for u in users_list if not self._is_vsts_user(u)]
            filtered_count = original_user_count - len(users_list)
            logger.info(f"Filtered out {filtered_count} VSTS built-in users")

        self.users = {user.descriptor: user for user in users_list}
        logger.info(f"Retrieved {len(self.users)} users (after filtering)")

        # Step 2: Retrieve groups
        logger.info("Retrieving groups...")
        groups_list = self.groups_client.get_groups()
        original_group_count = len(groups_list)

        # Filter VSTS groups if configured
        if self.config.exclude_vsts_groups:
            groups_list = [g for g in groups_list if not self._is_vsts_group(g)]
            filtered_count = original_group_count - len(groups_list)
            logger.info(f"Filtered out {filtered_count} VSTS built-in groups")

        self.groups = {group.descriptor: group for group in groups_list}
        logger.info(f"Retrieved {len(self.groups)} groups (after filtering)")

        # Step 3: Retrieve entitlements (requires per-user lookup by descriptor)
        logger.info("Retrieving entitlements...")
        entitlements_list = self.entitlements_client.get_entitlements(users_list)
        self.entitlements = {ent.user_descriptor: ent for ent in entitlements_list}
        logger.info(f"Retrieved {len(self.entitlements)} entitlements")

        # Step 4: Retrieve memberships (only for remaining groups)
        logger.info("Retrieving group memberships...")
        self._retrieve_all_memberships()
        logger.info(f"Retrieved {len(self.memberships)} membership relationships")

        logger.info("Data retrieval completed successfully")

    def _retrieve_all_memberships(self) -> None:
        """
        Retrieve all group membership relationships.

        This method fetches memberships for all groups to build the complete
        membership graph.
        """
        all_memberships = []

        for group_descriptor in self.groups.keys():
            try:
                group_memberships = self.membership_client.get_group_memberships(group_descriptor)
                all_memberships.extend(group_memberships)

                # Update group member count
                if group_descriptor in self.groups:
                    self.groups[group_descriptor].member_count = len(group_memberships)
                    self.groups[group_descriptor].members = [
                        m.member_descriptor for m in group_memberships
                    ]

            except Exception as e:
                logger.warning(f"Failed to retrieve memberships for group {group_descriptor}: {e}")

        self.memberships = all_memberships
        self._build_membership_maps()

    def _build_membership_maps(self) -> None:
        """
        Build lookup maps for efficient membership queries.

        Creates bidirectional maps for group->members and user->groups relationships.
        """
        self.group_memberships_map.clear()
        self.user_memberships_map.clear()

        for membership in self.memberships:
            # Group -> Members mapping
            self.group_memberships_map[membership.group_descriptor].append(
                membership.member_descriptor
            )

            # User/Member -> Groups mapping
            self.user_memberships_map[membership.member_descriptor].append(
                membership.group_descriptor
            )

    def process_user_entitlements(self) -> None:
        """
        Process and cross-reference all user entitlement data.

        This method creates comprehensive user summaries that include user info,
        entitlements, and group memberships for reporting purposes.
        Excludes VSTS (Azure DevOps built-in) users and service accounts.
        """
        logger.info("Processing user entitlements and group memberships...")

        # Build membership maps if not already built (needed when data is injected directly)
        if not self.user_memberships_map and self.memberships:
            logger.debug("Building membership maps from provided data...")
            self._build_membership_maps()

        self.user_summaries = []
        skipped_vsts_users = 0

        for user_descriptor, user in self.users.items():
            # Skip VSTS built-in users and service accounts
            if user.origin and user.origin.lower() == 'vsts':
                skipped_vsts_users += 1
                logger.debug(f"Skipping VSTS user: {user.display_name}")
                continue

            # Skip service accounts (those with svc. descriptor prefix)
            if user.descriptor and user.descriptor.startswith('svc.'):
                skipped_vsts_users += 1
                logger.debug(f"Skipping service account: {user.display_name}")
                continue

            try:
                summary = self._create_user_summary(user)
                self.user_summaries.append(summary)
            except Exception as e:
                logger.warning(f"Failed to process user {user_descriptor}: {e}")

        logger.info(f"Processed {len(self.user_summaries)} user summaries ({skipped_vsts_users} VSTS/service accounts skipped)")

    def _create_user_summary(self, user: User) -> UserEntitlementSummary:
        """
        Create a comprehensive summary for a single user.

        Args:
            user: User object

        Returns:
            UserEntitlementSummary with complete user information
        """
        # Get user's entitlement
        entitlement = self.entitlements.get(user.descriptor)

        # Get direct group memberships
        direct_group_descriptors = self.user_memberships_map.get(user.descriptor, [])
        direct_groups = [
            self.groups[desc] for desc in direct_group_descriptors
            if desc in self.groups
        ]

        # Get all group memberships (including inherited)
        all_group_descriptors = self._get_all_user_groups(user.descriptor)
        all_groups = [
            self.groups[desc] for desc in all_group_descriptors
            if desc in self.groups
        ]

        # Determine effective access level
        effective_access_level = self._calculate_effective_access_level(user, entitlement, all_groups)

        # Determine chargeback groups (security groups for cost allocation)
        chargeback_groups = self._determine_chargeback_groups(direct_groups)

        # Calculate license cost based on license type
        license_cost = self._calculate_license_cost(entitlement)

        return UserEntitlementSummary(
            user=user,
            entitlement=entitlement,
            direct_groups=direct_groups,
            all_groups=all_groups,
            effective_access_level=effective_access_level,
            license_cost=license_cost,
            chargeback_groups=chargeback_groups,
            last_updated=datetime.now(timezone.utc)
        )

    def _get_all_user_groups(self, user_descriptor: str, visited: Optional[Set[str]] = None) -> Set[str]:
        """
        Recursively get all group memberships for a user, including inherited ones.

        Args:
            user_descriptor: User descriptor
            visited: Set of already visited groups (for cycle detection)

        Returns:
            Set of all group descriptors the user belongs to
        """
        if visited is None:
            visited = set()

        all_groups = set()
        direct_groups = self.user_memberships_map.get(user_descriptor, [])

        for group_descriptor in direct_groups:
            if group_descriptor in visited:
                continue  # Avoid cycles

            visited.add(group_descriptor)
            all_groups.add(group_descriptor)

            # Recursively get parent groups
            parent_groups = self._get_all_user_groups(group_descriptor, visited)
            all_groups.update(parent_groups)

        return all_groups

    def _calculate_effective_access_level(self, user: User, entitlement: Optional[Entitlement],
                                        groups: List[Group]) -> Optional[AccessLevel]:
        """
        Calculate the effective access level for a user.

        Args:
            user: User object
            entitlement: User's entitlement (may be None)
            groups: List of groups user belongs to

        Returns:
            Effective access level
        """
        if entitlement:
            return entitlement.access_level

        # If no direct entitlement, check if user gets access through groups
        # This is a simplified logic - in practice, you might need more complex rules
        return AccessLevel.NONE

    def _determine_chargeback_groups(self, groups: List[Group]) -> List[str]:
        """
        Determine which groups should be used for chargeback purposes.

        All security groups with group rules to a project or the organization should be
        available for chargeback. This includes Azure AD groups and external security groups
        that have been granted permissions to the organization or projects.

        Args:
            groups: List of groups user belongs to

        Returns:
            List of group names for chargeback
        """
        chargeback_groups = []

        for group in groups:
            # Include security groups from external sources (Azure AD, Windows AD)
            if group.group_type and group.group_type.value in ['azureActiveDirectory', 'windows']:
                # Exclude built-in/system groups that are auto-created by Azure DevOps
                if not self._is_system_group(group):
                    chargeback_groups.append(group.display_name)
            # Also check if this is marked as a security group (regardless of origin)
            elif group.is_security_group:
                # Exclude built-in/system groups
                if not self._is_system_group(group):
                    chargeback_groups.append(group.display_name)

        return chargeback_groups

    def _is_vsts_user(self, user: User) -> bool:
        """
        Check if a user is a VSTS built-in user or service account.

        VSTS users typically have:
        - origin='vsts' (built-in accounts)
        - Display names containing common service account patterns

        Args:
            user: User object

        Returns:
            True if this is a VSTS built-in user
        """
        # Check origin - VSTS built-in users have 'vsts' origin
        if user.origin and user.origin.lower() == 'vsts':
            return True

        # Check for common service account patterns in display name
        if user.display_name:
            lower_name = user.display_name.lower()
            service_patterns = [
                'project collection',
                'build service',
                'release management',
                'agent pool service',
                'deployment group service',
                'azure devops',
                'visualstudio.com'
            ]
            if any(pattern in lower_name for pattern in service_patterns):
                return True

        return False

    def _is_vsts_group(self, group: Group) -> bool:
        """
        Check if a group is a VSTS built-in group.

        VSTS built-in groups have origin='vsts' and are auto-created by Azure DevOps.

        Args:
            group: Group object

        Returns:
            True if this is a VSTS built-in group
        """
        # VSTS built-in groups have 'vsts' origin
        if group.origin and group.origin.lower() == 'vsts':
            return True

        return False

    def _is_system_group(self, group: Group) -> bool:
        """
        Check if a group is a system/built-in group that should be excluded from chargeback.

        Built-in groups are auto-created by Azure DevOps (origin='vsts') and should not be
        used for cost allocation as they don't represent actual organizational teams or departments.

        Args:
            group: Group object

        Returns:
            True if this is a system group
        """
        # System groups have 'vsts' origin (Azure DevOps built-in groups)
        if group.origin and group.origin.lower() == 'vsts':
            return True

        return False

    def _calculate_license_cost(self, entitlement: Optional[Entitlement]) -> Optional[float]:
        """
        Calculate the cost of a license based on the access level.

        Uses access level enum to determine cost, as this is the canonical
        representation of license type after parsing API data.

        Args:
            entitlement: User's entitlement

        Returns:
            License cost or None if no entitlement
        """
        if not entitlement:
            return None

        # Azure DevOps license costs (monthly costs in USD)
        # These are standard prices and may vary by region or enterprise agreements
        # Note: Visual Studio subscriptions are paid separately, so cost is $0 from ADO perspective
        LICENSE_COSTS = {
            AccessLevel.STAKEHOLDER: 0.0,  # Free
            AccessLevel.BASIC: 6.0,  # Standard Basic license
            AccessLevel.BASIC_PLUS_TEST_PLANS: 52.0,  # Basic + Test Plans
            AccessLevel.VISUAL_STUDIO_SUBSCRIBER: 0.0,  # Included with VS subscription
            AccessLevel.VISUAL_STUDIO_ENTERPRISE: 0.0,  # Included with VS subscription
            AccessLevel.NONE: 0.0,  # No license
        }

        cost = LICENSE_COSTS.get(entitlement.access_level)

        if cost is None:
            logger.debug(f"Unknown access level for cost calculation: {entitlement.access_level}")
            return 0.0

        return cost

    def generate_organization_report(self) -> OrganizationReport:
        """
        Generate a complete organization entitlement report.

        Returns:
            OrganizationReport with complete analysis
        """
        logger.info("Generating organization report...")

        # Calculate basic statistics
        total_users = len(self.users)
        total_groups = len(self.groups)
        total_entitlements = len(self.entitlements)

        # Analyze groups by type
        groups_by_type = defaultdict(int)
        orphaned_groups = []

        for group in self.groups.values():
            if group.group_type:
                groups_by_type[group.group_type.value] += 1

            # Check for orphaned groups (no members)
            if group.member_count == 0:
                orphaned_groups.append(group)

        # Analyze licenses by type (use license_display_name for accurate license tracking)
        licenses_by_type = defaultdict(int)
        for entitlement in self.entitlements.values():
            # Use license_display_name (e.g., "Basic") instead of access_level (e.g., "express")
            license_type = entitlement.license_display_name or entitlement.access_level.value or 'Unknown'
            licenses_by_type[license_type] += 1

        # Calculate total license cost
        total_license_cost = sum(
            summary.license_cost for summary in self.user_summaries
            if summary.license_cost is not None
        )

        # Generate chargeback analysis
        chargeback_by_group = self._generate_chargeback_analysis()

        report = OrganizationReport(
            organization=self.organization,
            generated_at=datetime.now(timezone.utc),
            total_users=total_users,
            total_groups=total_groups,
            total_entitlements=total_entitlements,
            user_summaries=self.user_summaries,
            groups_by_type=dict(groups_by_type),
            orphaned_groups=orphaned_groups,
            licenses_by_type=dict(licenses_by_type),
            total_license_cost=total_license_cost if total_license_cost > 0 else None,
            chargeback_by_group=chargeback_by_group
        )

        logger.info("Organization report generated successfully")
        return report

    def _generate_chargeback_analysis(self) -> Dict[str, Dict[str, Any]]:
        """
        Generate chargeback analysis grouped by security groups.

        Returns:
            Dictionary with chargeback information per group
        """
        chargeback_analysis = defaultdict(lambda: {
            'users': [],
            'total_users': 0,
            'licenses': defaultdict(int),
            'total_cost': 0.0
        })

        for summary in self.user_summaries:
            user_name = summary.user.display_name
            access_level = summary.effective_access_level or AccessLevel.NONE

            # Get the actual license type from license_display_name (e.g., "Basic")
            # instead of access_level (e.g., "express")
            license_type = 'Unknown'
            if summary.entitlement and summary.entitlement.license_display_name:
                license_type = summary.entitlement.license_display_name
            elif access_level:
                license_type = access_level.value

            # Add user to each of their chargeback groups
            for group_name in summary.chargeback_groups:
                chargeback_analysis[group_name]['users'].append({
                    'name': user_name,
                    'email': summary.user.mail_address,
                    'license_type': license_type,
                    'access_level': access_level.value,
                    'license_cost': summary.license_cost or 0.0
                })
                chargeback_analysis[group_name]['total_users'] += 1
                chargeback_analysis[group_name]['licenses'][license_type] += 1

                if summary.license_cost:
                    chargeback_analysis[group_name]['total_cost'] += summary.license_cost

        # Convert defaultdicts to regular dicts for JSON serialization
        return {
            group: {
                'users': data['users'],
                'total_users': data['total_users'],
                'licenses': dict(data['licenses']),
                'total_cost': data['total_cost']
            }
            for group, data in chargeback_analysis.items()
        }

    def run_complete_analysis(self) -> OrganizationReport:
        """
        Run the complete entitlement analysis process.

        Returns:
            Complete organization report
        """
        logger.info(f"Starting complete entitlement analysis for {self.organization}")

        # Step 1: Retrieve all data
        self.retrieve_all_data()

        # Step 2: Process user entitlements
        self.process_user_entitlements()

        # Step 3: Generate report
        report = self.generate_organization_report()

        logger.info("Complete entitlement analysis finished successfully")
        return report