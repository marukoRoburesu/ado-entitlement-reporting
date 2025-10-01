"""
Data Retrieval Layer for Azure DevOps APIs

This module provides classes and functions to retrieve data from Azure DevOps
REST APIs including users, groups, entitlements, and memberships.
"""

import time
import logging
from typing import Dict, List, Optional, Any, Union, Iterator
from urllib.parse import urlencode

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.auth import AzureDevOpsAuth
from src.models import (
    User, Group, Entitlement, GroupMembership, UserEntitlementSummary,
    OrganizationReport, ApiResponse, ApiError, SubjectKind, AccessLevel, GroupType
)


logger = logging.getLogger(__name__)


class RateLimitError(Exception):
    """Raised when API rate limit is exceeded."""

    def __init__(self, message: str, retry_after: Optional[int] = None):
        super().__init__(message)
        self.retry_after = retry_after


class AzureDevOpsApiClient:
    """
    Azure DevOps API client with rate limiting, retry logic, and error handling.
    """

    def __init__(self, auth: AzureDevOpsAuth, max_retries: int = 3, retry_delay: int = 1):
        """
        Initialize the API client.

        Args:
            auth: Azure DevOps authentication handler
            max_retries: Maximum number of retry attempts
            retry_delay: Delay between retries in seconds
        """
        self.auth = auth
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.session = self._create_session()

    def _create_session(self) -> requests.Session:
        """
        Create a requests session with retry configuration.

        Returns:
            Configured requests session
        """
        session = self.auth.get_session()

        # Configure retry strategy
        retry_strategy = Retry(
            total=self.max_retries,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"],
            backoff_factor=1
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        return session

    def _handle_response(self, response: requests.Response) -> Dict[str, Any]:
        """
        Handle API response and extract data.

        Args:
            response: HTTP response object

        Returns:
            Response data as dictionary

        Raises:
            RateLimitError: If rate limit is exceeded
            requests.HTTPError: For other HTTP errors
        """
        if response.status_code == 429:
            retry_after = int(response.headers.get('Retry-After', 60))
            raise RateLimitError(
                f"Rate limit exceeded. Retry after {retry_after} seconds.",
                retry_after=retry_after
            )

        if not response.ok:
            error_msg = f"API request failed with status {response.status_code}"
            try:
                error_data = response.json()
                if 'message' in error_data:
                    error_msg += f": {error_data['message']}"
            except ValueError:
                error_msg += f": {response.text}"

            logger.error(error_msg)
            response.raise_for_status()

        try:
            return response.json()
        except ValueError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            raise

    def _make_request(self, url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Make an API request with error handling and retries.

        Args:
            url: API endpoint URL
            params: Query parameters

        Returns:
            Response data as dictionary
        """
        params = params or {}
        full_url = f"{url}?{urlencode(params)}" if params else url

        logger.debug(f"Making API request to: {full_url}")

        try:
            response = self.session.get(url, params=params, timeout=30)
            return self._handle_response(response)

        except RateLimitError as e:
            logger.warning(f"Rate limit hit, waiting {e.retry_after} seconds...")
            time.sleep(e.retry_after)
            # Retry once after rate limit
            response = self.session.get(url, params=params, timeout=30)
            return self._handle_response(response)

        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            raise

    def _paginate_request(self, url: str, params: Optional[Dict[str, Any]] = None) -> Iterator[Dict[str, Any]]:
        """
        Handle paginated API requests.

        Args:
            url: API endpoint URL
            params: Query parameters

        Yields:
            Individual items from paginated response
        """
        params = params or {}
        continuation_token = None

        while True:
            if continuation_token:
                params['continuationToken'] = continuation_token

            data = self._make_request(url, params)

            # Yield individual items
            if 'value' in data:
                for item in data['value']:
                    yield item

            # Check for more pages
            continuation_token = data.get('continuationToken')
            if not continuation_token:
                break

            logger.debug(f"Fetching next page with token: {continuation_token[:20]}...")


class UsersApiClient(AzureDevOpsApiClient):
    """Client for Azure DevOps Users API."""

    def get_users(self, subject_types: Optional[List[str]] = None) -> List[User]:
        """
        Retrieve all users from the organization.

        Args:
            subject_types: Filter by subject types (user, group, etc.)

        Returns:
            List of User objects
        """
        logger.info("Retrieving users from Azure DevOps")

        url = f"{self.auth.get_organization_url('vssps')}/_apis/graph/users"
        params = {"api-version": "7.1-preview.1"}

        if subject_types:
            params['subjectTypes'] = ','.join(subject_types)

        users = []
        for user_data in self._paginate_request(url, params):
            try:
                user = self._parse_user(user_data)
                users.append(user)
            except Exception as e:
                logger.warning(f"Failed to parse user data: {e}")
                logger.debug(f"User data: {user_data}")

        logger.info(f"Retrieved {len(users)} users")
        return users

    def get_user_by_descriptor(self, descriptor: str) -> Optional[User]:
        """
        Retrieve a specific user by descriptor.

        Args:
            descriptor: User descriptor

        Returns:
            User object or None if not found
        """
        logger.debug(f"Retrieving user with descriptor: {descriptor}")

        url = f"{self.auth.get_organization_url('vssps')}/_apis/graph/users/{descriptor}"
        params = {"api-version": "7.1-preview.1"}

        try:
            user_data = self._make_request(url, params)
            return self._parse_user(user_data)
        except requests.HTTPError as e:
            if e.response.status_code == 404:
                logger.warning(f"User not found: {descriptor}")
                return None
            raise

    def _parse_user(self, user_data: Dict[str, Any]) -> User:
        """
        Parse user data from API response.

        Args:
            user_data: Raw user data from API

        Returns:
            User object
        """
        # Log available keys for debugging
        logger.debug(f"User data keys: {list(user_data.keys())}")
        logger.debug(f"User: {user_data.get('displayName')}, id: {user_data.get('id')}, originId: {user_data.get('originId')}, descriptor: {user_data.get('descriptor')}")

        return User(
            descriptor=user_data.get('descriptor', ''),
            display_name=user_data.get('displayName', ''),
            unique_name=user_data.get('uniqueName'),
            principal_name=user_data.get('principalName'),
            mail_address=user_data.get('mailAddress'),
            subject_kind=SubjectKind.USER,
            domain=user_data.get('domain'),
            origin=user_data.get('origin'),
            origin_id=user_data.get('originId'),
            id=user_data.get('id'),
            is_active=user_data.get('isActive'),
            metadata=user_data
        )


class GroupsApiClient(AzureDevOpsApiClient):
    """Client for Azure DevOps Groups API."""

    def get_groups(self, subject_types: Optional[List[str]] = None) -> List[Group]:
        """
        Retrieve all groups from the organization.

        Args:
            subject_types: Filter by subject types

        Returns:
            List of Group objects
        """
        logger.info("Retrieving groups from Azure DevOps")

        url = f"{self.auth.get_organization_url('vssps')}/_apis/graph/groups"
        params = {"api-version": "7.1-preview.1"}

        if subject_types:
            params['subjectTypes'] = ','.join(subject_types)

        groups = []
        for group_data in self._paginate_request(url, params):
            try:
                group = self._parse_group(group_data)
                groups.append(group)
            except Exception as e:
                logger.warning(f"Failed to parse group data: {e}")
                logger.debug(f"Group data: {group_data}")

        logger.info(f"Retrieved {len(groups)} groups")
        return groups

    def get_group_by_descriptor(self, descriptor: str) -> Optional[Group]:
        """
        Retrieve a specific group by descriptor.

        Args:
            descriptor: Group descriptor

        Returns:
            Group object or None if not found
        """
        logger.debug(f"Retrieving group with descriptor: {descriptor}")

        url = f"{self.auth.get_organization_url('vssps')}/_apis/graph/groups/{descriptor}"
        params = {"api-version": "7.1-preview.1"}

        try:
            group_data = self._make_request(url, params)
            return self._parse_group(group_data)
        except requests.HTTPError as e:
            if e.response.status_code == 404:
                logger.warning(f"Group not found: {descriptor}")
                return None
            raise

    def _parse_group(self, group_data: Dict[str, Any]) -> Group:
        """
        Parse group data from API response.

        Args:
            group_data: Raw group data from API

        Returns:
            Group object
        """
        # Determine group type from origin
        origin = group_data.get('origin', '').lower()
        if 'windows' in origin:
            group_type = GroupType.WINDOWS
        elif 'aad' in origin or 'azuread' in origin:
            group_type = GroupType.AZURE_AD
        elif 'serviceprincipal' in origin:
            group_type = GroupType.SERVICE_PRINCIPAL
        else:
            group_type = GroupType.UNKNOWN

        return Group(
            descriptor=group_data.get('descriptor', ''),
            display_name=group_data.get('displayName', ''),
            principal_name=group_data.get('principalName'),
            mail_address=group_data.get('mailAddress'),
            subject_kind=SubjectKind.GROUP,
            group_type=group_type,
            domain=group_data.get('domain'),
            origin=group_data.get('origin'),
            origin_id=group_data.get('originId'),
            security_id=group_data.get('securityId'),
            is_active=group_data.get('isActive'),
            metadata=group_data
        )


class EntitlementsApiClient(AzureDevOpsApiClient):
    """Client for Azure DevOps User Entitlements API."""

    def get_entitlements(self, users: Optional[List[User]] = None) -> List[Entitlement]:
        """
        Retrieve all user entitlements from the organization.

        Note: The User Entitlements API requires looking up individual users by their descriptor.
        You cannot retrieve a list without specifying a user. Service accounts and build service
        identities don't have entitlements and will be skipped.

        Args:
            users: List of User objects to lookup entitlements for

        Returns:
            List of Entitlement objects
        """
        logger.info("Retrieving user entitlements from Azure DevOps")

        if not users:
            logger.warning("No users provided for entitlement lookup")
            return []

        entitlements = []
        failed_count = 0
        skipped_service_accounts = 0

        for user in users:
            # Skip service accounts and build service identities
            # These don't have entitlements in the User Entitlements API
            if self._is_service_account(user):
                skipped_service_accounts += 1
                logger.debug(f"Skipping service account: {user.display_name}")
                continue

            # Try descriptor first, then origin_id as fallback
            user_id = user.descriptor or user.origin_id

            if not user_id:
                logger.debug(f"Skipping user {user.display_name} - no descriptor or origin_id")
                continue

            try:
                entitlement = self.get_entitlement_by_user_id(user_id)
                if entitlement:
                    entitlements.append(entitlement)
                else:
                    logger.debug(f"No entitlement found for user {user.display_name}")
            except requests.HTTPError as e:
                if e.response.status_code == 404:
                    # If descriptor lookup failed, try origin_id as fallback
                    if user_id == user.descriptor and user.origin_id:
                        logger.debug(f"Descriptor lookup failed for {user.display_name}, trying origin_id")
                        try:
                            entitlement = self.get_entitlement_by_user_id(user.origin_id)
                            if entitlement:
                                entitlements.append(entitlement)
                                continue
                        except Exception:
                            pass
                    logger.debug(f"No entitlement found for user {user.display_name} (user_id: {user_id})")
                else:
                    failed_count += 1
                    logger.warning(f"Failed to retrieve entitlement for user {user.display_name} (user_id: {user_id}): HTTP {e.response.status_code}")
            except Exception as e:
                failed_count += 1
                logger.warning(f"Failed to retrieve entitlement for user {user.display_name} (user_id: {user_id}): {e}")

        logger.info(f"Retrieved {len(entitlements)} entitlements out of {len(users)} users ({skipped_service_accounts} service accounts, {failed_count} failures)")
        return entitlements

    def _is_service_account(self, user: User) -> bool:
        """
        Check if a user is a service account or build service identity.

        Service accounts don't have entitlements in the User Entitlements API.

        Args:
            user: User object

        Returns:
            True if this is a service account
        """
        # Check if descriptor starts with "svc." which indicates a service account
        if user.descriptor and user.descriptor.startswith('svc.'):
            return True

        if not user.display_name:
            return False

        display_name_lower = user.display_name.lower()

        # Common service account patterns
        service_patterns = [
            'build service',
            'agent pool service',
            'project collection service',
            'release management',
            'deployment',
            'pipeline'
        ]

        return any(pattern in display_name_lower for pattern in service_patterns)

    def get_entitlement_by_user_id(self, user_id: str) -> Optional[Entitlement]:
        """
        Retrieve entitlement for a specific user.

        Args:
            user_id: User ID or descriptor

        Returns:
            Entitlement object or None if not found
        """
        logger.debug(f"Retrieving entitlement for user: {user_id}")

        url = f"{self.auth.get_organization_url('vsaex')}/_apis/userentitlements/{user_id}"
        params = {"api-version": "7.1-preview.3"}

        try:
            entitlement_data = self._make_request(url, params)
            return self._parse_entitlement(entitlement_data)
        except requests.HTTPError as e:
            if e.response.status_code == 404:
                logger.warning(f"Entitlement not found for user: {user_id}")
                return None
            raise

    def _parse_entitlement(self, entitlement_data: Dict[str, Any]) -> Entitlement:
        """
        Parse entitlement data from API response.

        Per Microsoft spec, access level is determined by:
        - accountLicenseType (express, advanced, stakeholder, none)
        - licensingSource (account, msdn)
        - msdnLicenseType (none, eligible, enterprise, etc.)

        Mapping table:
        | Access Level                | accountLicenseType | licensingSource | msdnLicenseType |
        |-----------------------------|--------------------|-----------------|-----------------|
        | Basic                       | express            | account         | none            |
        | Basic + Test Plans          | advanced           | account         | none            |
        | Visual Studio Subscriber    | none               | msdn            | eligible        |
        | Stakeholder                 | stakeholder        | account         | none            |
        | Visual Studio Enterprise    | none               | msdn            | enterprise      |

        Args:
            entitlement_data: Raw entitlement data from API

        Returns:
            Entitlement object
        """
        from src.models import LicensingSource, MsdnLicenseType

        # Extract user info
        user = entitlement_data.get('user', {})
        user_descriptor = user.get('descriptor', '')

        # Extract access level info from API
        access_level_data = entitlement_data.get('accessLevel', {})
        account_license_type = access_level_data.get('accountLicenseType', 'none')
        licensing_source_str = access_level_data.get('licensingSource', 'none')
        msdn_license_type_str = access_level_data.get('msdnLicenseType', 'none')
        license_display_name = access_level_data.get('licenseDisplayName')

        # Parse enums
        try:
            licensing_source = LicensingSource(licensing_source_str.lower())
        except ValueError:
            licensing_source = LicensingSource.NONE
            logger.warning(f"Unknown licensing source: {licensing_source_str}")

        try:
            msdn_license_type = MsdnLicenseType(msdn_license_type_str.lower())
        except ValueError:
            msdn_license_type = MsdnLicenseType.NONE
            if msdn_license_type_str and msdn_license_type_str.lower() != 'none':
                logger.warning(f"Unknown MSDN license type: {msdn_license_type_str}")

        # Determine access level based on the combination (per Microsoft spec)
        access_level = self._determine_access_level(
            account_license_type,
            licensing_source,
            msdn_license_type
        )

        # Extract project entitlements
        project_entitlements = []
        for project in entitlement_data.get('projectEntitlements', []):
            project_entitlements.append(project.get('projectRef', {}).get('id', ''))

        # Extract group assignments
        group_assignments = []
        for group in entitlement_data.get('groupAssignments', []):
            group_assignments.append(group.get('group', {}).get('descriptor', ''))

        return Entitlement(
            user_descriptor=user_descriptor,
            access_level=access_level,
            account_license_type=account_license_type,
            licensing_source=licensing_source,
            msdn_license_type=msdn_license_type,
            license_display_name=license_display_name,
            assignment_source=access_level_data.get('assignmentSource'),
            date_created=entitlement_data.get('dateCreated'),
            last_accessed_date=entitlement_data.get('lastAccessedDate'),
            project_entitlements=project_entitlements,
            group_assignments=group_assignments,
            extensions=entitlement_data.get('extensions', []),
            metadata=entitlement_data
        )

    def _determine_access_level(
        self,
        account_license_type: str,
        licensing_source: 'LicensingSource',
        msdn_license_type: 'MsdnLicenseType'
    ) -> AccessLevel:
        """
        Determine the access level based on Microsoft's API specification.

        Args:
            account_license_type: Account license type from API
            licensing_source: Source of the license
            msdn_license_type: MSDN license type

        Returns:
            AccessLevel enum value
        """
        from src.models import LicensingSource, MsdnLicenseType

        account_license_lower = account_license_type.lower()

        # Basic: express + account + none
        if (account_license_lower == 'express' and
            licensing_source == LicensingSource.ACCOUNT and
            msdn_license_type == MsdnLicenseType.NONE):
            return AccessLevel.BASIC

        # Basic + Test Plans: advanced + account + none
        if (account_license_lower == 'advanced' and
            licensing_source == LicensingSource.ACCOUNT and
            msdn_license_type == MsdnLicenseType.NONE):
            return AccessLevel.BASIC_PLUS_TEST_PLANS

        # Visual Studio Subscriber: none + msdn + eligible
        if (account_license_lower == 'none' and
            licensing_source == LicensingSource.MSDN and
            msdn_license_type == MsdnLicenseType.ELIGIBLE):
            return AccessLevel.VISUAL_STUDIO_SUBSCRIBER

        # Visual Studio Enterprise: none + msdn + enterprise
        if (account_license_lower == 'none' and
            licensing_source == LicensingSource.MSDN and
            msdn_license_type == MsdnLicenseType.ENTERPRISE):
            return AccessLevel.VISUAL_STUDIO_ENTERPRISE

        # Stakeholder: stakeholder + account + none
        if (account_license_lower == 'stakeholder' and
            licensing_source == LicensingSource.ACCOUNT and
            msdn_license_type == MsdnLicenseType.NONE):
            return AccessLevel.STAKEHOLDER

        # Default case - log for investigation
        logger.warning(
            f"Unmapped access level combination: "
            f"accountLicenseType={account_license_type}, "
            f"licensingSource={licensing_source}, "
            f"msdnLicenseType={msdn_license_type}"
        )
        return AccessLevel.NONE


class MembershipApiClient(AzureDevOpsApiClient):
    """Client for Azure DevOps Group Membership API."""

    def get_group_memberships(self, group_descriptor: str) -> List[GroupMembership]:
        """
        Retrieve all memberships for a specific group.

        Args:
            group_descriptor: Group descriptor

        Returns:
            List of GroupMembership objects
        """
        logger.debug(f"Retrieving memberships for group: {group_descriptor}")

        url = f"{self.auth.get_organization_url('vssps')}/_apis/graph/memberships/{group_descriptor}"
        params = {"api-version": "7.1-preview.1", "direction": "down"}

        memberships = []
        for membership_data in self._paginate_request(url, params):
            try:
                membership = self._parse_membership(membership_data, group_descriptor)
                memberships.append(membership)
            except Exception as e:
                logger.warning(f"Failed to parse membership data: {e}")
                logger.debug(f"Membership data: {membership_data}")

        return memberships

    def get_user_memberships(self, user_descriptor: str) -> List[GroupMembership]:
        """
        Retrieve all group memberships for a specific user.

        Args:
            user_descriptor: User descriptor

        Returns:
            List of GroupMembership objects
        """
        logger.debug(f"Retrieving memberships for user: {user_descriptor}")

        url = f"{self.auth.get_organization_url('vssps')}/_apis/graph/memberships/{user_descriptor}"
        params = {"api-version": "7.1-preview.1", "direction": "up"}

        memberships = []
        for membership_data in self._paginate_request(url, params):
            try:
                membership = self._parse_membership(membership_data, None, user_descriptor)
                memberships.append(membership)
            except Exception as e:
                logger.warning(f"Failed to parse membership data: {e}")
                logger.debug(f"Membership data: {membership_data}")

        return memberships

    def _parse_membership(self, membership_data: Dict[str, Any],
                         group_descriptor: Optional[str] = None,
                         member_descriptor: Optional[str] = None) -> GroupMembership:
        """
        Parse membership data from API response.

        Args:
            membership_data: Raw membership data from API
            group_descriptor: Group descriptor (if querying group members)
            member_descriptor: Member descriptor (if querying user memberships)

        Returns:
            GroupMembership object
        """
        # Extract container and member descriptors
        container_descriptor = membership_data.get('containerDescriptor', group_descriptor)
        member_desc = membership_data.get('memberDescriptor', member_descriptor)

        # Determine member type from metadata
        member_subject_kind = SubjectKind.USER  # Default to user
        if 'subjectKind' in membership_data:
            try:
                member_subject_kind = SubjectKind(membership_data['subjectKind'].lower())
            except ValueError:
                pass

        return GroupMembership(
            group_descriptor=container_descriptor,
            member_descriptor=member_desc,
            member_type=member_subject_kind,
            is_active=membership_data.get('isActive'),
            metadata=membership_data
        )