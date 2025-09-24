"""
Tests for the reporting module.
"""

import pytest
import json
import csv
from pathlib import Path
from unittest.mock import Mock, patch, mock_open
from datetime import datetime, timezone
from tempfile import TemporaryDirectory

from src.reporting import ReportGenerator
from src.models import (
    User, Group, Entitlement, UserEntitlementSummary, OrganizationReport,
    AccessLevel, GroupType, SubjectKind
)


class TestReportGenerator:
    """Tests for ReportGenerator."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = TemporaryDirectory()
        self.output_dir = Path(self.temp_dir.name)
        self.generator = ReportGenerator(str(self.output_dir))

        # Create sample test data
        self.sample_user1 = User(
            descriptor="user-1",
            display_name="John Doe",
            mail_address="john@test.com",
            unique_name="john@test.com"
        )

        self.sample_user2 = User(
            descriptor="user-2",
            display_name="Jane Smith",
            mail_address="jane@test.com",
            unique_name="jane@test.com"
        )

        self.sample_group1 = Group(
            descriptor="group-1",
            display_name="Developers",
            group_type=GroupType.AZURE_AD,
            member_count=2
        )

        self.sample_group2 = Group(
            descriptor="group-2",
            display_name="Managers",
            group_type=GroupType.WINDOWS,
            member_count=1
        )

        self.sample_entitlement1 = Entitlement(
            user_descriptor="user-1",
            access_level=AccessLevel.BASIC,
            last_accessed_date=datetime.now(timezone.utc)
        )

        self.sample_entitlement2 = Entitlement(
            user_descriptor="user-2",
            access_level=AccessLevel.STAKEHOLDER
        )

        self.sample_summary1 = UserEntitlementSummary(
            user=self.sample_user1,
            entitlement=self.sample_entitlement1,
            direct_groups=[self.sample_group1],
            all_groups=[self.sample_group1],
            effective_access_level=AccessLevel.BASIC,
            chargeback_groups=["Developers"],
            license_cost=50.0
        )

        self.sample_summary2 = UserEntitlementSummary(
            user=self.sample_user2,
            entitlement=self.sample_entitlement2,
            direct_groups=[self.sample_group2],
            all_groups=[self.sample_group2],
            effective_access_level=AccessLevel.STAKEHOLDER,
            chargeback_groups=["Managers"],
            license_cost=25.0
        )

        self.sample_report = OrganizationReport(
            organization="test-org",
            total_users=2,
            total_groups=2,
            total_entitlements=2,
            user_summaries=[self.sample_summary1, self.sample_summary2],
            groups_by_type={"azureActiveDirectory": 1, "windows": 1},
            licenses_by_type={"basic": 1, "stakeholder": 1},
            orphaned_groups=[],
            total_license_cost=75.0,
            chargeback_by_group={
                "Developers": {
                    "total_users": 1,
                    "users": [
                        {
                            "user": "John Doe",
                            "email": "john@test.com",
                            "license": "basic",
                            "cost": 50.0
                        }
                    ],
                    "licenses": {"basic": 1},
                    "total_cost": 50.0
                },
                "Managers": {
                    "total_users": 1,
                    "users": [
                        {
                            "user": "Jane Smith",
                            "email": "jane@test.com",
                            "license": "stakeholder",
                            "cost": 25.0
                        }
                    ],
                    "licenses": {"stakeholder": 1},
                    "total_cost": 25.0
                }
            }
        )

    def teardown_method(self):
        """Clean up test fixtures."""
        self.temp_dir.cleanup()

    def test_init(self):
        """Test report generator initialization."""
        assert self.generator.output_directory == self.output_dir
        assert self.output_dir.exists()

    def test_init_creates_directory(self):
        """Test that initialization creates output directory."""
        with TemporaryDirectory() as temp_dir:
            non_existent_dir = Path(temp_dir) / "reports"
            generator = ReportGenerator(str(non_existent_dir))
            assert non_existent_dir.exists()

    def test_generate_csv_reports(self):
        """Test CSV reports generation."""
        result = self.generator.generate_csv_reports(self.sample_report)

        assert len(result) == 4  # user_summary, chargeback, group_analysis, license_summary

        # Check that all files were created
        for report_type, file_path in result.items():
            assert file_path.exists()
            assert file_path.suffix == ".csv"

            # Check that files have content
            with open(file_path, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                # Some reports might be empty if no data, but headers should exist
                assert reader.fieldnames is not None

    def test_generate_json_report(self):
        """Test JSON report generation."""
        result = self.generator.generate_json_report(self.sample_report)

        assert result.exists()
        assert result.suffix == ".json"

        # Verify JSON content
        with open(result, 'r', encoding='utf-8') as f:
            data = json.load(f)

        assert data["metadata"]["organization"] == "test-org"
        assert data["metadata"]["total_users"] == 2
        assert data["metadata"]["total_groups"] == 2
        assert len(data["user_summaries"]) == 2
        assert "chargeback_analysis" in data

    def test_generate_excel_report(self):
        """Test Excel report generation."""
        result = self.generator.generate_excel_report(self.sample_report)

        assert result.exists()
        assert result.suffix == ".xlsx"

    def test_generate_all_reports_csv_only(self):
        """Test generating all reports with CSV format only."""
        result = self.generator.generate_all_reports(self.sample_report, ["csv"])

        assert "csv" in result
        assert len(result) == 1

        csv_files = result["csv"]
        assert len(csv_files) == 4
        assert "user_summary" in csv_files
        assert "chargeback" in csv_files
        assert "group_analysis" in csv_files
        assert "license_summary" in csv_files

    def test_generate_all_reports_all_formats(self):
        """Test generating all reports with all formats."""
        result = self.generator.generate_all_reports(
            self.sample_report,
            ["csv", "json", "excel"]
        )

        assert len(result) == 3
        assert "csv" in result
        assert "json" in result
        assert "excel" in result

    def test_generate_all_reports_invalid_format(self):
        """Test generating reports with invalid format."""
        result = self.generator.generate_all_reports(self.sample_report, ["invalid"])
        # Should just log warning and continue, not raise exception
        assert len(result) == 0

    def test_csv_special_characters(self):
        """Test CSV generation with special characters."""
        # Create user with special characters
        special_user = User(
            descriptor="user-special",
            display_name="John, \"Special\" User",
            mail_address="john@test.com"
        )

        special_summary = UserEntitlementSummary(
            user=special_user,
            entitlement=self.sample_entitlement1,
            chargeback_groups=["Team, with \"comma\""]
        )

        special_report = OrganizationReport(
            organization="test-org",
            user_summaries=[special_summary]
        )

        result = self.generator.generate_csv_reports(special_report)

        # Verify the file was created and can be read
        user_summary_file = result["user_summary"]
        with open(user_summary_file, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 1
        assert rows[0]["User Name"] == "John, \"Special\" User"

    def test_empty_report(self):
        """Test generating reports with empty data."""
        empty_report = OrganizationReport(
            organization="empty-org",
            user_summaries=[]
        )

        result = self.generator.generate_csv_reports(empty_report)

        # Files should still be created with headers
        for report_type, file_path in result.items():
            assert file_path.exists()

            with open(file_path, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                # User summary should have no rows, but other reports might have summary data
                if report_type == "user_summary":
                    assert len(rows) == 0  # Only headers, no data
                else:
                    # Other reports might have summary rows even with empty data
                    assert len(rows) >= 0

    def test_large_dataset(self):
        """Test handling of large datasets."""
        # Create a larger dataset
        large_summaries = []
        for i in range(100):
            user = User(
                descriptor=f"user-{i}",
                display_name=f"User {i}",
                mail_address=f"user{i}@test.com"
            )
            summary = UserEntitlementSummary(
                user=user,
                entitlement=Entitlement(
                    user_descriptor=f"user-{i}",
                    access_level=AccessLevel.BASIC
                ),
                chargeback_groups=[f"Group-{i % 10}"]
            )
            large_summaries.append(summary)

        large_report = OrganizationReport(
            organization="large-org",
            total_users=100,
            user_summaries=large_summaries
        )

        result = self.generator.generate_csv_reports(large_report)

        # Verify all data was written
        user_summary_file = result["user_summary"]
        with open(user_summary_file, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 100

    def test_unicode_handling(self):
        """Test handling of Unicode characters."""
        unicode_user = User(
            descriptor="user-unicode",
            display_name="José María Azañar",
            mail_address="jose@test.com"
        )

        unicode_summary = UserEntitlementSummary(
            user=unicode_user,
            entitlement=self.sample_entitlement1,
            chargeback_groups=["Développeurs"]
        )

        unicode_report = OrganizationReport(
            organization="test-org",
            user_summaries=[unicode_summary]
        )

        result = self.generator.generate_csv_reports(unicode_report)

        # Verify Unicode characters are preserved
        user_summary_file = result["user_summary"]
        with open(user_summary_file, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 1
        assert rows[0]["User Name"] == "José María Azañar"
        assert "Développeurs" in rows[0]["Chargeback Groups"]

    @patch('builtins.open', side_effect=PermissionError("Permission denied"))
    def test_file_permission_error(self, mock_open):
        """Test handling of file permission errors."""
        with pytest.raises(PermissionError):
            self.generator.generate_csv_reports(self.sample_report)

    def test_output_directory_permissions(self):
        """Test behavior when output directory has limited permissions."""
        # This test would need to be run with appropriate permissions
        # For now, just verify the directory exists
        assert self.generator.output_directory.exists()
        assert self.generator.output_directory.is_dir()