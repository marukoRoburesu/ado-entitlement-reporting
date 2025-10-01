"""
Tests for the dummy data generator module.
"""

import pytest
from src.dummy_data import DummyDataGenerator
from src.models import User, Group, Entitlement, GroupMembership, SubjectKind, AccessLevel


class TestDummyDataGenerator:
    """Test suite for DummyDataGenerator class."""

    @pytest.fixture
    def generator(self):
        """Create a dummy data generator with fixed seed for reproducible tests."""
        return DummyDataGenerator(seed=42)

    def test_generate_users(self, generator):
        """Test generating dummy users."""
        users = generator.generate_users(count=10)

        assert len(users) == 10
        assert all(isinstance(user, User) for user in users)
        assert all(user.subject_kind == SubjectKind.USER for user in users)
        assert all(user.descriptor.startswith("aad.") for user in users)
        assert all(user.display_name for user in users)
        assert all(user.principal_name for user in users)
        assert all(user.mail_address for user in users)

    def test_generate_groups(self, generator):
        """Test generating dummy groups."""
        groups = generator.generate_groups(count=5)

        assert len(groups) == 5
        assert all(isinstance(group, Group) for group in groups)
        assert all(group.subject_kind == SubjectKind.GROUP for group in groups)
        assert all(group.descriptor.startswith("vssgp.") for group in groups)
        assert all(group.display_name for group in groups)

    def test_generate_entitlements(self, generator):
        """Test generating dummy entitlements."""
        users = generator.generate_users(count=10)
        entitlements = generator.generate_entitlements(users)

        assert len(entitlements) == 10
        assert all(isinstance(entitlement, Entitlement) for entitlement in entitlements)

        # Check that all users have entitlements
        user_descriptors = {user.descriptor for user in users}
        entitlement_descriptors = {e.user_descriptor for e in entitlements}
        assert user_descriptors == entitlement_descriptors

        # Check variety of access levels
        access_levels = {e.access_level for e in entitlements}
        assert len(access_levels) > 1  # Should have multiple access levels

    def test_generate_entitlements_without_users_raises_error(self, generator):
        """Test that generating entitlements without users raises an error."""
        with pytest.raises(ValueError, match="No users available"):
            generator.generate_entitlements()

    def test_generate_memberships(self, generator):
        """Test generating dummy group memberships."""
        users = generator.generate_users(count=10)
        groups = generator.generate_groups(count=5)
        memberships = generator.generate_memberships(users, groups, avg_groups_per_user=2)

        assert len(memberships) > 0
        assert all(isinstance(membership, GroupMembership) for membership in memberships)

        # Check that memberships reference valid users and groups
        user_descriptors = {user.descriptor for user in users}
        group_descriptors = {group.descriptor for group in groups}

        for membership in memberships:
            if membership.member_type == SubjectKind.USER:
                assert membership.member_descriptor in user_descriptors
            else:
                # Nested group membership
                assert membership.member_descriptor in group_descriptors
            assert membership.group_descriptor in group_descriptors

    def test_generate_memberships_without_users_raises_error(self, generator):
        """Test that generating memberships without users raises an error."""
        groups = generator.generate_groups(count=5)
        with pytest.raises(ValueError, match="No users available"):
            generator.generate_memberships(groups=groups)

    def test_generate_memberships_without_groups_raises_error(self, generator):
        """Test that generating memberships without groups raises an error."""
        users = generator.generate_users(count=10)
        with pytest.raises(ValueError, match="No groups available"):
            generator.generate_memberships(users=users)

    def test_generate_complete_dataset(self, generator):
        """Test generating a complete dataset."""
        users, groups, entitlements, memberships = generator.generate_complete_dataset(
            num_users=20,
            num_groups=8,
            avg_groups_per_user=3
        )

        # Check that all data was generated
        assert len(users) == 20
        assert len(groups) == 8
        assert len(entitlements) == 20
        assert len(memberships) > 0

        # Check relationships
        assert all(isinstance(user, User) for user in users)
        assert all(isinstance(group, Group) for group in groups)
        assert all(isinstance(entitlement, Entitlement) for entitlement in entitlements)
        assert all(isinstance(membership, GroupMembership) for membership in memberships)

    def test_get_all_data(self, generator):
        """Test retrieving all generated data."""
        generator.generate_complete_dataset(num_users=10, num_groups=5)
        data = generator.get_all_data()

        assert 'users' in data
        assert 'groups' in data
        assert 'entitlements' in data
        assert 'memberships' in data

        assert len(data['users']) == 10
        assert len(data['groups']) == 5
        assert len(data['entitlements']) == 10
        assert len(data['memberships']) > 0

    def test_reproducibility_with_seed(self):
        """Test that using the same seed produces reproducible results."""
        # Generate data twice with the same seed to verify consistency
        gen1 = DummyDataGenerator(seed=12345)
        users1 = gen1.generate_users(count=5)
        groups1 = gen1.generate_groups(count=3)

        gen2 = DummyDataGenerator(seed=12345)
        users2 = gen2.generate_users(count=5)
        groups2 = gen2.generate_groups(count=3)

        # Check that the same number of entities are generated
        assert len(users1) == len(users2)
        assert len(groups1) == len(groups2)

        # Verify data properties match (names should be identical with same seed)
        for u1, u2 in zip(users1, users2):
            assert u1.display_name == u2.display_name
            assert u1.principal_name == u2.principal_name

        for g1, g2 in zip(groups1, groups2):
            assert g1.display_name == g2.display_name

    def test_access_level_distribution(self, generator):
        """Test that entitlements have realistic access level distribution."""
        users = generator.generate_users(count=100)
        entitlements = generator.generate_entitlements(users)

        # Count access levels
        access_level_counts = {}
        for entitlement in entitlements:
            level = entitlement.access_level
            access_level_counts[level] = access_level_counts.get(level, 0) + 1

        # Should have multiple access levels represented
        assert len(access_level_counts) >= 3

        # Basic should be most common (around 60%)
        assert access_level_counts.get(AccessLevel.BASIC, 0) > 40

    def test_nested_group_memberships(self, generator):
        """Test that nested group memberships are created."""
        users = generator.generate_users(count=10)
        groups = generator.generate_groups(count=10)
        memberships = generator.generate_memberships(users, groups)

        # Check for nested group memberships (groups in groups)
        nested_memberships = [
            m for m in memberships
            if m.member_type == SubjectKind.GROUP
        ]

        assert len(nested_memberships) > 0

    def test_licensing_source_variety(self, generator):
        """Test that entitlements include different licensing sources."""
        users = generator.generate_users(count=100)
        entitlements = generator.generate_entitlements(users)

        licensing_sources = {e.licensing_source for e in entitlements}

        # Should have both ACCOUNT and MSDN licensing sources
        assert len(licensing_sources) > 1

    def test_default_parameters(self):
        """Test that generator works with default parameters."""
        gen = DummyDataGenerator()
        users, groups, entitlements, memberships = gen.generate_complete_dataset()

        # Check default counts
        assert len(users) == 50  # Default num_users
        assert len(groups) == 15  # Default num_groups
        assert len(entitlements) == 50
        assert len(memberships) > 0


class TestDummyDataIntegration:
    """Integration tests using dummy data with data processor."""

    def test_data_processor_with_dummy_data(self):
        """Test that dummy data works with EntitlementDataProcessor."""
        from src.data_processor import EntitlementDataProcessor
        from src.auth import AuthConfig, AzureDevOpsAuth
        from src.config import ReportsConfig

        # Create dummy data
        generator = DummyDataGenerator(seed=42)
        users, groups, entitlements, memberships = generator.generate_complete_dataset(
            num_users=30,
            num_groups=10
        )

        # Create mock auth
        auth_config = AuthConfig(
            organization="test-org",
            pat_token="dummy-token"
        )
        auth = AzureDevOpsAuth(auth_config)

        # Create processor with dummy data (convert lists to dictionaries)
        report_config = ReportsConfig()
        processor = EntitlementDataProcessor(auth, config=report_config)
        processor.users = {user.descriptor: user for user in users}
        processor.groups = {group.descriptor: group for group in groups}
        processor.entitlements = {ent.user_descriptor: ent for ent in entitlements}
        processor.memberships = memberships

        # Process data
        processor.process_user_entitlements()
        report = processor.generate_organization_report()

        # Verify report was generated
        assert report.organization == "test-org"
        assert report.total_users == 30
        assert report.total_groups == 10
        assert report.total_entitlements == 30
        assert len(report.user_summaries) > 0

    def test_report_generation_with_dummy_data(self):
        """Test that reports can be generated with dummy data."""
        from src.data_processor import EntitlementDataProcessor
        from src.reporting import ReportGenerator
        from src.auth import AuthConfig, AzureDevOpsAuth
        from src.config import ReportsConfig
        import tempfile
        import shutil
        from pathlib import Path

        # Create dummy data
        generator = DummyDataGenerator(seed=42)
        users, groups, entitlements, memberships = generator.generate_complete_dataset(
            num_users=20,
            num_groups=5
        )

        # Create processor
        auth_config = AuthConfig(
            organization="test-org",
            pat_token="dummy-token"
        )
        auth = AzureDevOpsAuth(auth_config)
        report_config = ReportsConfig()
        processor = EntitlementDataProcessor(auth, config=report_config)
        processor.users = {user.descriptor: user for user in users}
        processor.groups = {group.descriptor: group for group in groups}
        processor.entitlements = {ent.user_descriptor: ent for ent in entitlements}
        processor.memberships = memberships

        # Process and generate report
        processor.process_user_entitlements()
        org_report = processor.generate_organization_report()

        # Create temporary directory for reports
        temp_dir = tempfile.mkdtemp()
        try:
            report_gen = ReportGenerator(temp_dir)
            files = report_gen.generate_all_reports(org_report, formats=["csv", "json"])

            # Verify files were created
            assert "csv" in files
            assert "json" in files

            # Check CSV files
            csv_files = files["csv"]
            assert "user_summary" in csv_files
            assert "chargeback" in csv_files
            assert Path(csv_files["user_summary"]).exists()
            assert Path(csv_files["chargeback"]).exists()

            # Check JSON file
            json_file = files["json"]
            assert Path(json_file).exists()

        finally:
            # Cleanup
            shutil.rmtree(temp_dir)
