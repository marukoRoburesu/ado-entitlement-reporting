"""
Dummy Data Generator Module

Generates realistic dummy data for testing Azure DevOps entitlement reporting.
This module can be used for testing, demos, and development without requiring
actual Azure DevOps API access.
"""

import random
import logging
from typing import List, Dict, Tuple
from datetime import datetime, timezone
from faker import Faker

from src.models import (
    User, Group, Entitlement, GroupMembership,
    SubjectKind, AccessLevel, GroupType,
    LicensingSource, MsdnLicenseType
)


logger = logging.getLogger(__name__)
fake = Faker()


class DummyDataGenerator:
    """
    Generates realistic dummy data for Azure DevOps entitlement reporting.
    """

    def __init__(self, seed: int = None):
        """
        Initialize the dummy data generator.

        Args:
            seed: Random seed for reproducible data generation
        """
        if seed is not None:
            random.seed(seed)
            Faker.seed(seed)

        self.fake = Faker()
        self.generated_users: List[User] = []
        self.generated_groups: List[Group] = []
        self.generated_entitlements: List[Entitlement] = []
        self.generated_memberships: List[GroupMembership] = []

        logger.info("Dummy data generator initialized")

    def generate_users(self, count: int = 50) -> List[User]:
        """
        Generate dummy users.

        Args:
            count: Number of users to generate

        Returns:
            List of User objects
        """
        users = []

        for i in range(count):
            # Generate user details
            first_name = self.fake.first_name()
            last_name = self.fake.last_name()
            email = f"{first_name.lower()}.{last_name.lower()}@{self.fake.domain_name()}"

            user = User(
                descriptor=f"aad.{self.fake.uuid4()}",
                subject_kind=SubjectKind.USER,
                display_name=f"{first_name} {last_name}",
                principal_name=email,
                mail_address=email,
                origin="aad",
                origin_id=self.fake.uuid4(),
                domain=self.fake.domain_name()
            )
            users.append(user)

        self.generated_users = users
        logger.info(f"Generated {len(users)} dummy users")
        return users

    def generate_groups(self, count: int = 15) -> List[Group]:
        """
        Generate dummy security groups.

        Args:
            count: Number of groups to generate

        Returns:
            List of Group objects
        """
        groups = []

        # Group name templates
        group_templates = [
            "Development Team",
            "QA Team",
            "DevOps Team",
            "Product Management",
            "Engineering Managers",
            "Data Science Team",
            "Security Team",
            "Infrastructure Team",
            "Frontend Developers",
            "Backend Developers",
            "Mobile Development",
            "Cloud Architecture",
            "Platform Engineering",
            "Release Management",
            "Technical Writers"
        ]

        for i in range(count):
            if i < len(group_templates):
                group_name = group_templates[i]
            else:
                group_name = f"Team {i + 1}"

            # Mix of AAD and VSTS groups
            is_aad = random.random() > 0.3
            origin = "aad" if is_aad else "vsts"

            group = Group(
                descriptor=f"vssgp.{self.fake.uuid4()}",
                subject_kind=SubjectKind.GROUP,
                display_name=f"[{self.fake.company()}]\\{group_name}",
                principal_name=group_name,
                mail_address=f"{group_name.lower().replace(' ', '-')}@{self.fake.domain_name()}",
                origin=origin,
                origin_id=self.fake.uuid4() if is_aad else None,
                domain=self.fake.domain_name(),
                is_security_group=True,
                group_type=GroupType.AZURE_AD if is_aad else GroupType.WINDOWS
            )
            groups.append(group)

        self.generated_groups = groups
        logger.info(f"Generated {len(groups)} dummy groups")
        return groups

    def generate_entitlements(self, users: List[User] = None) -> List[Entitlement]:
        """
        Generate dummy entitlements for users.

        Args:
            users: List of users to generate entitlements for (uses generated users if None)

        Returns:
            List of Entitlement objects
        """
        if users is None:
            users = self.generated_users

        if not users:
            raise ValueError("No users available. Generate users first.")

        entitlements = []

        # Define access level distribution (realistic percentages)
        access_levels = [
            (AccessLevel.BASIC, 0.60, "express", LicensingSource.ACCOUNT, MsdnLicenseType.NONE),
            (AccessLevel.STAKEHOLDER, 0.20, "stakeholder", LicensingSource.ACCOUNT, MsdnLicenseType.NONE),
            (AccessLevel.BASIC_PLUS_TEST_PLANS, 0.10, "advanced", LicensingSource.ACCOUNT, MsdnLicenseType.NONE),
            (AccessLevel.VISUAL_STUDIO_SUBSCRIBER, 0.07, "express", LicensingSource.MSDN, MsdnLicenseType.PROFESSIONAL),
            (AccessLevel.VISUAL_STUDIO_ENTERPRISE, 0.03, "express", LicensingSource.MSDN, MsdnLicenseType.ENTERPRISE),
        ]

        for user in users:
            # Select access level based on distribution
            rand = random.random()
            cumulative = 0
            selected_level = None

            for level, probability, account_type, licensing_src, msdn_type in access_levels:
                cumulative += probability
                if rand <= cumulative:
                    selected_level = (level, account_type, licensing_src, msdn_type)
                    break

            if selected_level is None:
                selected_level = access_levels[0][0:4]  # Default to Basic

            access_level, account_license_type, licensing_source, msdn_license_type = selected_level

            # Generate license display name
            license_display_names = {
                AccessLevel.BASIC: "Basic",
                AccessLevel.STAKEHOLDER: "Stakeholder",
                AccessLevel.BASIC_PLUS_TEST_PLANS: "Basic + Test Plans",
                AccessLevel.VISUAL_STUDIO_SUBSCRIBER: "Visual Studio Professional",
                AccessLevel.VISUAL_STUDIO_ENTERPRISE: "Visual Studio Enterprise"
            }

            entitlement = Entitlement(
                user_descriptor=user.descriptor,
                access_level=access_level,
                account_license_type=account_license_type,
                licensing_source=licensing_source,
                msdn_license_type=msdn_license_type,
                license_display_name=license_display_names[access_level],
                last_accessed_date=self.fake.date_time_between(start_date='-90d', end_date='now', tzinfo=timezone.utc)
            )
            entitlements.append(entitlement)

        self.generated_entitlements = entitlements
        logger.info(f"Generated {len(entitlements)} dummy entitlements")
        return entitlements

    def generate_memberships(
        self,
        users: List[User] = None,
        groups: List[Group] = None,
        avg_groups_per_user: int = 3
    ) -> List[GroupMembership]:
        """
        Generate dummy group memberships.

        Args:
            users: List of users (uses generated users if None)
            groups: List of groups (uses generated groups if None)
            avg_groups_per_user: Average number of groups each user should belong to

        Returns:
            List of GroupMembership objects
        """
        if users is None:
            users = self.generated_users
        if groups is None:
            groups = self.generated_groups

        if not users:
            raise ValueError("No users available. Generate users first.")
        if not groups:
            raise ValueError("No groups available. Generate groups first.")

        memberships = []

        # Create user-to-group memberships
        for user in users:
            # Randomly assign user to groups
            num_groups = max(1, int(random.gauss(avg_groups_per_user, 1.5)))
            num_groups = min(num_groups, len(groups))  # Don't exceed available groups

            user_groups = random.sample(groups, num_groups)

            for group in user_groups:
                membership = GroupMembership(
                    member_descriptor=user.descriptor,
                    group_descriptor=group.descriptor,
                    member_type=SubjectKind.USER
                )
                memberships.append(membership)

        # Create some nested group memberships (groups in groups)
        if len(groups) > 3:
            parent_groups = random.sample(groups, min(5, len(groups) // 3))

            for parent_group in parent_groups:
                # Select some child groups
                available_children = [g for g in groups if g.descriptor != parent_group.descriptor]
                num_children = random.randint(1, min(3, len(available_children)))
                child_groups = random.sample(available_children, num_children)

                for child_group in child_groups:
                    membership = GroupMembership(
                        member_descriptor=child_group.descriptor,
                        group_descriptor=parent_group.descriptor,
                        member_type=SubjectKind.GROUP
                    )
                    memberships.append(membership)

        self.generated_memberships = memberships
        logger.info(f"Generated {len(memberships)} dummy memberships")
        return memberships

    def generate_complete_dataset(
        self,
        num_users: int = 50,
        num_groups: int = 15,
        avg_groups_per_user: int = 3
    ) -> Tuple[List[User], List[Group], List[Entitlement], List[GroupMembership]]:
        """
        Generate a complete dataset with users, groups, entitlements, and memberships.

        Args:
            num_users: Number of users to generate
            num_groups: Number of groups to generate
            avg_groups_per_user: Average groups per user

        Returns:
            Tuple of (users, groups, entitlements, memberships)
        """
        logger.info(f"Generating complete dataset: {num_users} users, {num_groups} groups")

        users = self.generate_users(num_users)
        groups = self.generate_groups(num_groups)
        entitlements = self.generate_entitlements(users)
        memberships = self.generate_memberships(users, groups, avg_groups_per_user)

        logger.info("Complete dataset generation finished")
        return users, groups, entitlements, memberships

    def get_all_data(self) -> Dict[str, List]:
        """
        Get all generated data as a dictionary.

        Returns:
            Dictionary with keys: users, groups, entitlements, memberships
        """
        return {
            'users': self.generated_users,
            'groups': self.generated_groups,
            'entitlements': self.generated_entitlements,
            'memberships': self.generated_memberships
        }
