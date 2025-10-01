#!/usr/bin/env python3
"""
Example script demonstrating the Dummy Data Generator usage.

This script shows various ways to use the dummy data generator for testing,
development, and demonstration purposes.
"""

import sys
from pathlib import Path

# Add parent directory to path to import src module
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.dummy_data import DummyDataGenerator
from src.data_processor import EntitlementDataProcessor
from src.reporting import ReportGenerator
from src.auth import AuthConfig, AzureDevOpsAuth
from src.config import ReportsConfig
from pathlib import Path
import shutil


def example_basic_generation():
    """Example 1: Basic data generation."""
    print("\n" + "="*70)
    print("Example 1: Basic Data Generation")
    print("="*70)

    # Create generator
    generator = DummyDataGenerator(seed=42)

    # Generate individual components
    users = generator.generate_users(count=10)
    groups = generator.generate_groups(count=5)
    entitlements = generator.generate_entitlements(users)
    memberships = generator.generate_memberships(users, groups)

    print(f"✓ Generated {len(users)} users")
    print(f"✓ Generated {len(groups)} groups")
    print(f"✓ Generated {len(entitlements)} entitlements")
    print(f"✓ Generated {len(memberships)} memberships")

    # Show sample user
    sample_user = users[0]
    print(f"\nSample User:")
    print(f"  - Name: {sample_user.display_name}")
    print(f"  - Email: {sample_user.principal_name}")
    print(f"  - Descriptor: {sample_user.descriptor}")

    # Show sample group
    sample_group = groups[0]
    print(f"\nSample Group:")
    print(f"  - Name: {sample_group.display_name}")
    print(f"  - Type: {sample_group.group_type}")
    print(f"  - Origin: {sample_group.origin}")


def example_complete_dataset():
    """Example 2: Generate complete dataset in one call."""
    print("\n" + "="*70)
    print("Example 2: Complete Dataset Generation")
    print("="*70)

    generator = DummyDataGenerator(seed=123)

    # Generate everything at once
    users, groups, entitlements, memberships = generator.generate_complete_dataset(
        num_users=25,
        num_groups=8,
        avg_groups_per_user=3
    )

    print(f"✓ Complete dataset generated")
    print(f"  - Users: {len(users)}")
    print(f"  - Groups: {len(groups)}")
    print(f"  - Entitlements: {len(entitlements)}")
    print(f"  - Memberships: {len(memberships)}")

    # Analyze access levels
    access_level_counts = {}
    for ent in entitlements:
        level = ent.access_level
        access_level_counts[level] = access_level_counts.get(level, 0) + 1

    print(f"\nAccess Level Distribution:")
    for level, count in sorted(access_level_counts.items(), key=lambda x: x[1], reverse=True):
        percentage = (count / len(entitlements)) * 100
        print(f"  - {level}: {count} ({percentage:.1f}%)")


def example_with_data_processor():
    """Example 3: Use dummy data with EntitlementDataProcessor."""
    print("\n" + "="*70)
    print("Example 3: Integration with Data Processor")
    print("="*70)

    # Generate dummy data
    generator = DummyDataGenerator(seed=456)
    users, groups, entitlements, memberships = generator.generate_complete_dataset(
        num_users=30,
        num_groups=10
    )

    # Create mock authentication
    auth_config = AuthConfig(
        organization="example-org",
        pat_token="dummy-token-for-testing"
    )
    auth = AzureDevOpsAuth(auth_config)

    # Create data processor
    report_config = ReportsConfig()
    processor = EntitlementDataProcessor(auth, config=report_config)

    # Inject dummy data (convert lists to dictionaries)
    processor.users = {user.descriptor: user for user in users}
    processor.groups = {group.descriptor: group for group in groups}
    processor.entitlements = {ent.user_descriptor: ent for ent in entitlements}
    processor.memberships = memberships

    print(f"✓ Data loaded into processor")

    # Process entitlements
    processor.process_user_entitlements()
    print(f"✓ Entitlements processed")

    # Generate organization report
    org_report = processor.generate_organization_report()
    print(f"✓ Organization report generated")

    # Display report summary
    print(f"\nOrganization Report Summary:")
    print(f"  - Organization: {org_report.organization}")
    print(f"  - Total Users: {org_report.total_users}")
    print(f"  - Total Groups: {org_report.total_groups}")
    print(f"  - Total Entitlements: {org_report.total_entitlements}")
    print(f"  - Total License Cost: ${org_report.total_license_cost:.2f}")

    if org_report.chargeback_by_group:
        print(f"  - Chargeback Groups: {len(org_report.chargeback_by_group)}")


def example_generate_reports():
    """Example 4: Generate actual report files from dummy data."""
    print("\n" + "="*70)
    print("Example 4: Generate Report Files")
    print("="*70)

    # Setup output directory
    output_dir = Path("./example_reports")
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir()

    # Generate dummy data
    generator = DummyDataGenerator(seed=789)
    users, groups, entitlements, memberships = generator.generate_complete_dataset(
        num_users=40,
        num_groups=12
    )

    # Process data
    auth_config = AuthConfig(organization="demo-org", pat_token="dummy-token")
    auth = AzureDevOpsAuth(auth_config)
    processor = EntitlementDataProcessor(auth, config=ReportsConfig())

    processor.users = {user.descriptor: user for user in users}
    processor.groups = {group.descriptor: group for group in groups}
    processor.entitlements = {ent.user_descriptor: ent for ent in entitlements}
    processor.memberships = memberships

    processor.process_user_entitlements()
    org_report = processor.generate_organization_report()

    # Generate reports
    report_gen = ReportGenerator(str(output_dir))
    files = report_gen.generate_all_reports(org_report, formats=["csv", "json", "excel"])

    print(f"✓ Reports generated in: {output_dir}")
    print(f"\nGenerated Files:")

    for format_type, file_paths in files.items():
        if isinstance(file_paths, dict):
            print(f"  {format_type.upper()}:")
            for report_name, file_path in file_paths.items():
                print(f"    - {report_name}: {file_path.name}")
        else:
            print(f"  {format_type.upper()}: {file_paths.name}")

    print(f"\n✓ All reports saved to: {output_dir.absolute()}")


def example_reproducibility():
    """Example 5: Demonstrate reproducibility with seeds."""
    print("\n" + "="*70)
    print("Example 5: Reproducible Data Generation")
    print("="*70)

    # Generate data twice with same seed
    print("Generating dataset 1 with seed=999...")
    gen1 = DummyDataGenerator(seed=999)
    users1 = gen1.generate_users(count=5)

    print("Generating dataset 2 with seed=999...")
    gen2 = DummyDataGenerator(seed=999)
    users2 = gen2.generate_users(count=5)

    # Compare results
    print("\nComparing datasets:")
    matches = 0
    for i, (u1, u2) in enumerate(zip(users1, users2)):
        if u1.display_name == u2.display_name:
            matches += 1
            print(f"  User {i+1}: ✓ {u1.display_name} == {u2.display_name}")
        else:
            print(f"  User {i+1}: ✗ {u1.display_name} != {u2.display_name}")

    print(f"\n✓ Reproducibility: {matches}/{len(users1)} users matched")
    if matches == len(users1):
        print("  Perfect reproducibility achieved with seed!")


def example_custom_scenario():
    """Example 6: Create a custom test scenario."""
    print("\n" + "="*70)
    print("Example 6: Custom Test Scenario")
    print("="*70)

    # Scenario: Large organization with many stakeholders
    generator = DummyDataGenerator(seed=2024)

    print("Scenario: Testing organization with 200 users and 30 groups")
    users, groups, entitlements, memberships = generator.generate_complete_dataset(
        num_users=200,
        num_groups=30,
        avg_groups_per_user=4
    )

    # Analyze the generated data
    print(f"\nDataset Statistics:")
    print(f"  - Total Users: {len(users)}")
    print(f"  - Total Groups: {len(groups)}")
    print(f"  - Total Memberships: {len(memberships)}")

    # Count memberships per user
    user_membership_counts = {}
    for membership in memberships:
        if hasattr(membership, 'member_type') and membership.member_type.value == 'user':
            user_desc = membership.member_descriptor
            user_membership_counts[user_desc] = user_membership_counts.get(user_desc, 0) + 1

    if user_membership_counts:
        avg_groups = sum(user_membership_counts.values()) / len(user_membership_counts)
        max_groups = max(user_membership_counts.values())
        min_groups = min(user_membership_counts.values())

        print(f"\nMembership Distribution:")
        print(f"  - Average groups per user: {avg_groups:.2f}")
        print(f"  - Maximum groups per user: {max_groups}")
        print(f"  - Minimum groups per user: {min_groups}")

    # Group type distribution
    aad_groups = sum(1 for g in groups if g.origin == 'aad')
    vsts_groups = len(groups) - aad_groups

    print(f"\nGroup Types:")
    print(f"  - Azure AD Groups: {aad_groups} ({aad_groups/len(groups)*100:.1f}%)")
    print(f"  - VSTS Groups: {vsts_groups} ({vsts_groups/len(groups)*100:.1f}%)")


def main():
    """Run all examples."""
    print("\n" + "="*70)
    print("Dummy Data Generator - Usage Examples")
    print("="*70)

    try:
        example_basic_generation()
        example_complete_dataset()
        example_with_data_processor()
        example_generate_reports()
        example_reproducibility()
        example_custom_scenario()

        print("\n" + "="*70)
        print("All Examples Completed Successfully!")
        print("="*70)
        print("\nNext Steps:")
        print("  1. Review the generated reports in ./example_reports/")
        print("  2. Modify the examples to fit your use case")
        print("  3. Run: python main.py --generate-dummy-data --help")
        print("  4. Check out tests/test_dummy_data.py for more examples")
        print("="*70 + "\n")

    except Exception as e:
        print(f"\n✗ Error running examples: {e}")
        raise


if __name__ == "__main__":
    main()
