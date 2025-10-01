"""
Reporting and Output Formatting Module

This module handles the generation of various report formats (CSV, JSON, Excel)
for Azure DevOps entitlement reporting and chargeback analysis.
"""

import csv
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timezone

import pandas as pd

from src.models import OrganizationReport, UserEntitlementSummary, Group, User, Entitlement


logger = logging.getLogger(__name__)


class ConsolidatedReportGenerator:
    """
    Generator for consolidated reports across multiple organizations.

    Handles merging user data across organizations, deduplicating users,
    and aggregating costs.
    """

    def __init__(self, output_directory: Union[str, Path] = "./reports", include_timestamp: bool = True):
        """
        Initialize the consolidated report generator.

        Args:
            output_directory: Directory to save consolidated reports
            include_timestamp: Whether to include timestamp in filenames (for static filenames, set to False)
        """
        self.output_directory = Path(output_directory)
        self.output_directory.mkdir(parents=True, exist_ok=True)
        self.include_timestamp = include_timestamp
        logger.info(f"Consolidated report generator initialized with output directory: {self.output_directory}, "
                   f"include_timestamp: {self.include_timestamp}")

    def generate_consolidated_user_report(self, reports: List[OrganizationReport],
                                         timestamp: str = None) -> Path:
        """
        Generate a consolidated user report across all organizations.

        Users appearing in multiple orgs will have a single row with:
        - Organizations column listing all orgs (comma-separated)
        - License costs summed across orgs
        - Chargeback groups combined from all orgs

        Args:
            reports: List of organization reports
            timestamp: Timestamp string for filename (optional, used if include_timestamp is True)

        Returns:
            Path to generated consolidated CSV file
        """
        if self.include_timestamp:
            if not timestamp:
                timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            file_path = self.output_directory / f"all_organizations_users_{timestamp}.csv"
        else:
            file_path = self.output_directory / f"all_organizations_users.csv"

        logger.info(f"Generating consolidated user report: {file_path}")

        # Build user index by email/principal name
        user_data_by_key = {}

        for report in reports:
            for summary in report.user_summaries:
                user = summary.user
                entitlement = summary.entitlement

                # Create unique key for user (email is best, fallback to principal name)
                user_key = user.mail_address or user.principal_name or user.descriptor

                if user_key not in user_data_by_key:
                    # First time seeing this user
                    user_data_by_key[user_key] = {
                        'organizations': [report.organization],
                        'user_name': user.display_name,
                        'email': user.mail_address or '',
                        'principal_name': user.principal_name or '',
                        'unique_name': user.unique_name or '',
                        'descriptor': user.descriptor,
                        'origin': user.origin or '',
                        'domain': user.domain or '',
                        'license_display_names': [entitlement.license_display_name if entitlement else 'None'],
                        'total_license_cost': summary.license_cost or 0.0,
                        'chargeback_groups': set(summary.chargeback_groups),
                        'is_active': user.is_active,
                        'last_accessed': entitlement.last_accessed_date if entitlement else None
                    }
                else:
                    # User exists in multiple orgs - merge data
                    existing = user_data_by_key[user_key]
                    existing['organizations'].append(report.organization)
                    if entitlement and entitlement.license_display_name:
                        existing['license_display_names'].append(entitlement.license_display_name)
                    existing['total_license_cost'] += (summary.license_cost or 0.0)
                    existing['chargeback_groups'].update(summary.chargeback_groups)
                    # Update last accessed to most recent
                    if entitlement and entitlement.last_accessed_date:
                        if not existing['last_accessed'] or entitlement.last_accessed_date > existing['last_accessed']:
                            existing['last_accessed'] = entitlement.last_accessed_date

        # Write consolidated CSV
        with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = [
                'User Name', 'Email', 'Principal Name', 'Organizations', 'License Types',
                'Total License Cost', 'Chargeback Groups', 'Is Active', 'Last Accessed'
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for user_data in user_data_by_key.values():
                writer.writerow({
                    'User Name': user_data['user_name'],
                    'Email': user_data['email'],
                    'Principal Name': user_data['principal_name'],
                    'Organizations': ', '.join(user_data['organizations']),
                    'License Types': ', '.join(set(user_data['license_display_names'])),
                    'Total License Cost': f"{user_data['total_license_cost']:.2f}",
                    'Chargeback Groups': '; '.join(sorted(user_data['chargeback_groups'])),
                    'Is Active': 'Yes' if user_data['is_active'] else 'No' if user_data['is_active'] is not None else 'Unknown',
                    'Last Accessed': user_data['last_accessed'].strftime('%Y-%m-%d') if user_data['last_accessed'] else ''
                })

        logger.info(f"Generated consolidated user report with {len(user_data_by_key)} unique users")
        return file_path

    def generate_consolidated_chargeback_report(self, reports: List[OrganizationReport],
                                               timestamp: str = None) -> Path:
        """
        Generate a consolidated chargeback report across all organizations.

        Args:
            reports: List of organization reports
            timestamp: Timestamp string for filename (optional, used if include_timestamp is True)

        Returns:
            Path to generated consolidated CSV file
        """
        if self.include_timestamp:
            if not timestamp:
                timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            file_path = self.output_directory / f"all_organizations_chargeback_{timestamp}.csv"
        else:
            file_path = self.output_directory / f"all_organizations_chargeback.csv"

        logger.info(f"Generating consolidated chargeback report: {file_path}")

        # Aggregate by organization and group
        chargeback_data = []

        for report in reports:
            for group_name, group_data in report.chargeback_by_group.items():
                licenses = group_data.get('licenses', {})
                total_users = group_data.get('total_users', 0)
                total_cost = group_data.get('total_cost', 0.0)
                cost_per_user = total_cost / total_users if total_users > 0 else 0.0

                chargeback_data.append({
                    'Organization': report.organization,
                    'Group Name': group_name,
                    'Total Users': total_users,
                    'Basic Licenses': licenses.get('Basic', 0),
                    'Stakeholder Licenses': licenses.get('Stakeholder', 0),
                    'VS Subscriber Licenses': licenses.get('Visual Studio Subscriber', 0),
                    'VS Enterprise Licenses': licenses.get('Visual Studio Enterprise', 0),
                    'Total Cost': f"{total_cost:.2f}",
                    'Cost Per User': f"{cost_per_user:.2f}"
                })

        # Write consolidated CSV
        with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = [
                'Organization', 'Group Name', 'Total Users', 'Basic Licenses',
                'Stakeholder Licenses', 'VS Subscriber Licenses', 'VS Enterprise Licenses',
                'Total Cost', 'Cost Per User'
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(chargeback_data)

        logger.info(f"Generated consolidated chargeback report with {len(chargeback_data)} entries")
        return file_path


class ReportGenerator:
    """
    Main report generator class that handles multiple output formats
    for Azure DevOps entitlement reporting.
    """

    def __init__(self, output_directory: Union[str, Path] = "./reports", include_timestamp: bool = True):
        """
        Initialize the report generator.

        Args:
            output_directory: Directory to save reports
            include_timestamp: Whether to include timestamp in filenames (for static filenames, set to False)
        """
        self.output_directory = Path(output_directory)
        self.output_directory.mkdir(parents=True, exist_ok=True)
        self.include_timestamp = include_timestamp
        logger.info(f"Report generator initialized with output directory: {self.output_directory}, "
                   f"include_timestamp: {self.include_timestamp}")

    def generate_all_reports(self, report: OrganizationReport, formats: List[str]) -> Dict[str, Path]:
        """
        Generate reports in all specified formats.

        Args:
            report: Organization report data
            formats: List of format types ('csv', 'json', 'excel')

        Returns:
            Dictionary mapping format names to generated file paths
        """
        generated_files = {}

        for format_type in formats:
            try:
                if format_type.lower() == 'csv':
                    file_path = self.generate_csv_reports(report)
                    generated_files['csv'] = file_path
                elif format_type.lower() == 'json':
                    file_path = self.generate_json_report(report)
                    generated_files['json'] = file_path
                elif format_type.lower() == 'excel':
                    file_path = self.generate_excel_report(report)
                    generated_files['excel'] = file_path
                else:
                    logger.warning(f"Unknown format type: {format_type}")

            except Exception as e:
                logger.error(f"Failed to generate {format_type} report: {e}")

        return generated_files

    def generate_csv_reports(self, report: OrganizationReport) -> Dict[str, Path]:
        """
        Generate multiple CSV reports for different stakeholder needs.

        Args:
            report: Organization report data

        Returns:
            Dictionary mapping report types to file paths
        """
        org_name = report.organization

        # Build filename suffix (timestamp or empty)
        if self.include_timestamp:
            timestamp = report.generated_at.strftime("%Y%m%d_%H%M%S")
            suffix = f"_{timestamp}"
        else:
            suffix = ""

        csv_files = {}

        # 1. User Summary Report
        user_summary_file = self.output_directory / f"{org_name}_user_summary{suffix}.csv"
        csv_files['user_summary'] = self._generate_user_summary_csv(report, user_summary_file)

        # 2. Chargeback Report
        chargeback_file = self.output_directory / f"{org_name}_chargeback{suffix}.csv"
        csv_files['chargeback'] = self._generate_chargeback_csv(report, chargeback_file)

        # 3. Group Analysis Report
        group_analysis_file = self.output_directory / f"{org_name}_group_analysis{suffix}.csv"
        csv_files['group_analysis'] = self._generate_group_analysis_csv(report, group_analysis_file)

        # 4. License Summary Report
        license_summary_file = self.output_directory / f"{org_name}_license_summary{suffix}.csv"
        csv_files['license_summary'] = self._generate_license_summary_csv(report, license_summary_file)

        logger.info(f"Generated {len(csv_files)} CSV reports")
        return csv_files

    def _generate_user_summary_csv(self, report: OrganizationReport, file_path: Path) -> Path:
        """Generate detailed user summary CSV report."""
        logger.debug(f"Generating user summary CSV: {file_path}")

        with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = [
                'Organization', 'User Name', 'Email', 'Principal Name', 'Unique Name', 'User ID', 'Origin ID',
                'Descriptor', 'Origin', 'Domain', 'Access Level', 'License Display Name',
                'Is Active', 'Direct Groups', 'All Groups', 'Chargeback Groups',
                'License Cost', 'Last Accessed'
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for summary in report.user_summaries:
                user = summary.user
                entitlement = summary.entitlement

                writer.writerow({
                    'Organization': report.organization,
                    'User Name': user.display_name,
                    'Email': user.mail_address or '',
                    'Principal Name': user.principal_name or '',
                    'Unique Name': user.unique_name or '',
                    'User ID': user.id or '',
                    'Origin ID': user.origin_id or '',
                    'Descriptor': user.descriptor,
                    'Origin': user.origin or '',
                    'Domain': user.domain or '',
                    'Access Level': summary.effective_access_level.value if summary.effective_access_level else 'none',
                    'License Display Name': entitlement.license_display_name if entitlement else '',
                    'Is Active': 'Yes' if user.is_active else 'No' if user.is_active is not None else 'Unknown',
                    'Direct Groups': '; '.join([g.display_name for g in summary.direct_groups]),
                    'All Groups': '; '.join([g.display_name for g in summary.all_groups]),
                    'Chargeback Groups': '; '.join(summary.chargeback_groups),
                    'License Cost': summary.license_cost or 0.0,
                    'Last Accessed': entitlement.last_accessed_date.strftime('%Y-%m-%d') if entitlement and entitlement.last_accessed_date else ''
                })

        return file_path

    def _generate_chargeback_csv(self, report: OrganizationReport, file_path: Path) -> Path:
        """Generate chargeback analysis CSV report."""
        logger.debug(f"Generating chargeback CSV: {file_path}")

        with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = [
                'Organization', 'Group Name', 'Total Users', 'Basic Licenses', 'Stakeholder Licenses',
                'VS Subscriber Licenses', 'VS Enterprise Licenses', 'Other Licenses',
                'Total Cost', 'Cost Per User'
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for group_name, group_data in report.chargeback_by_group.items():
                licenses = group_data.get('licenses', {})
                total_users = group_data.get('total_users', 0)
                total_cost = group_data.get('total_cost', 0.0)
                cost_per_user = total_cost / total_users if total_users > 0 else 0.0

                # Count license types
                basic_count = licenses.get('Basic', 0)
                stakeholder_count = licenses.get('Stakeholder', 0)
                vs_subscriber_count = licenses.get('Visual Studio Subscriber', 0)
                vs_enterprise_count = licenses.get('Visual Studio Enterprise', 0)
                other_count = total_users - (basic_count + stakeholder_count + vs_subscriber_count + vs_enterprise_count)

                writer.writerow({
                    'Organization': report.organization,
                    'Group Name': group_name,
                    'Total Users': total_users,
                    'Basic Licenses': basic_count,
                    'Stakeholder Licenses': stakeholder_count,
                    'VS Subscriber Licenses': vs_subscriber_count,
                    'VS Enterprise Licenses': vs_enterprise_count,
                    'Other Licenses': max(0, other_count),
                    'Total Cost': f"{total_cost:.2f}",
                    'Cost Per User': f"{cost_per_user:.2f}"
                })

        return file_path

    def _generate_group_analysis_csv(self, report: OrganizationReport, file_path: Path) -> Path:
        """Generate group analysis CSV report."""
        logger.debug(f"Generating group analysis CSV: {file_path}")

        with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = [
                'Organization', 'Group Name', 'Group Type', 'Member Count', 'Is Security Group',
                'Domain', 'Origin', 'Is Orphaned', 'Principal Name'
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            # Get all groups from user summaries
            all_groups = {}
            for summary in report.user_summaries:
                for group in summary.all_groups:
                    # Skip VSTS built-in groups
                    if group.origin and group.origin.lower() == 'vsts':
                        continue
                    all_groups[group.descriptor] = group

            # Add orphaned groups (excluding VSTS)
            for group in report.orphaned_groups:
                if group.origin and group.origin.lower() == 'vsts':
                    continue
                all_groups[group.descriptor] = group

            for group in all_groups.values():
                is_orphaned = group in report.orphaned_groups

                writer.writerow({
                    'Organization': report.organization,
                    'Group Name': group.display_name,
                    'Group Type': group.group_type.value if group.group_type else 'unknown',
                    'Member Count': group.member_count or 0,
                    'Is Security Group': 'Yes' if group.is_security_group else 'No' if group.is_security_group is not None else 'Unknown',
                    'Domain': group.domain or '',
                    'Origin': group.origin or '',
                    'Is Orphaned': 'Yes' if is_orphaned else 'No',
                    'Principal Name': group.principal_name or ''
                })

        return file_path

    def _generate_license_summary_csv(self, report: OrganizationReport, file_path: Path) -> Path:
        """Generate license summary CSV report."""
        logger.debug(f"Generating license summary CSV: {file_path}")

        with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['License Type', 'Count', 'Percentage']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            total_licenses = sum(report.licenses_by_type.values())

            for license_type, count in report.licenses_by_type.items():
                percentage = (count / total_licenses * 100) if total_licenses > 0 else 0.0

                writer.writerow({
                    'License Type': license_type.replace('_', ' ').title(),
                    'Count': count,
                    'Percentage': f"{percentage:.1f}%"
                })

            # Add summary row
            writer.writerow({
                'License Type': 'TOTAL',
                'Count': total_licenses,
                'Percentage': '100.0%'
            })

        return file_path

    def generate_json_report(self, report: OrganizationReport) -> Path:
        """
        Generate comprehensive JSON report.

        Args:
            report: Organization report data

        Returns:
            Path to generated JSON file
        """
        org_name = report.organization

        # Build filename with or without timestamp
        if self.include_timestamp:
            timestamp = report.generated_at.strftime("%Y%m%d_%H%M%S")
            file_path = self.output_directory / f"{org_name}_complete_report_{timestamp}.json"
        else:
            file_path = self.output_directory / f"{org_name}_complete_report.json"

        logger.debug(f"Generating JSON report: {file_path}")

        # Convert the report to a JSON-serializable format
        report_data = self._prepare_json_data(report)

        with open(file_path, 'w', encoding='utf-8') as jsonfile:
            json.dump(report_data, jsonfile, indent=2, ensure_ascii=False, default=str)

        logger.info(f"Generated JSON report: {file_path}")
        return file_path

    def _prepare_json_data(self, report: OrganizationReport) -> Dict[str, Any]:
        """Prepare report data for JSON serialization."""
        return {
            'metadata': {
                'organization': report.organization,
                'generated_at': report.generated_at.isoformat(),
                'total_users': report.total_users,
                'total_groups': report.total_groups,
                'total_entitlements': report.total_entitlements,
                'total_license_cost': report.total_license_cost
            },
            'license_analysis': {
                'licenses_by_type': report.licenses_by_type,
                'groups_by_type': report.groups_by_type
            },
            'chargeback_analysis': report.chargeback_by_group,
            'user_summaries': [
                {
                    'user': {
                        'display_name': summary.user.display_name,
                        'email': summary.user.mail_address,
                        'unique_name': summary.user.unique_name,
                        'principal_name': summary.user.principal_name,
                        'user_id': summary.user.id,
                        'origin_id': summary.user.origin_id,
                        'descriptor': summary.user.descriptor,
                        'origin': summary.user.origin,
                        'domain': summary.user.domain,
                        'is_active': summary.user.is_active
                    },
                    'entitlement': {
                        'access_level': summary.effective_access_level.value if summary.effective_access_level else None,
                        'license_display_name': summary.entitlement.license_display_name if summary.entitlement else None,
                        'license_cost': summary.license_cost,
                        'last_accessed': summary.entitlement.last_accessed_date.isoformat() if summary.entitlement and summary.entitlement.last_accessed_date else None
                    },
                    'groups': {
                        'direct_groups': [g.display_name for g in summary.direct_groups],
                        'all_groups': [g.display_name for g in summary.all_groups],
                        'chargeback_groups': summary.chargeback_groups
                    },
                    'last_updated': summary.last_updated.isoformat()
                }
                for summary in report.user_summaries
            ],
            'orphaned_groups': [
                {
                    'display_name': group.display_name,
                    'group_type': group.group_type.value if group.group_type else None,
                    'origin': group.origin,
                    'member_count': group.member_count or 0
                }
                for group in report.orphaned_groups
            ]
        }

    def generate_excel_report(self, report: OrganizationReport) -> Path:
        """
        Generate comprehensive Excel report with multiple worksheets.

        Args:
            report: Organization report data

        Returns:
            Path to generated Excel file
        """
        org_name = report.organization

        # Build filename with or without timestamp
        if self.include_timestamp:
            timestamp = report.generated_at.strftime("%Y%m%d_%H%M%S")
            file_path = self.output_directory / f"{org_name}_report_{timestamp}.xlsx"
        else:
            file_path = self.output_directory / f"{org_name}_report.xlsx"

        logger.debug(f"Generating Excel report: {file_path}")

        with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
            # Summary worksheet
            self._create_summary_worksheet(report, writer)

            # User details worksheet
            self._create_user_details_worksheet(report, writer)

            # Chargeback worksheet
            self._create_chargeback_worksheet(report, writer)

            # Group analysis worksheet
            self._create_group_analysis_worksheet(report, writer)

            # License analysis worksheet
            self._create_license_analysis_worksheet(report, writer)

        logger.info(f"Generated Excel report: {file_path}")
        return file_path

    def _create_summary_worksheet(self, report: OrganizationReport, writer: pd.ExcelWriter) -> None:
        """Create summary worksheet for Excel report."""
        summary_data = [
            ['Organization', report.organization],
            ['Report Generated', report.generated_at.strftime('%Y-%m-%d %H:%M:%S UTC')],
            ['Total Users', report.total_users],
            ['Total Groups', report.total_groups],
            ['Total Entitlements', report.total_entitlements],
            ['Total License Cost', f"${report.total_license_cost:.2f}" if report.total_license_cost else 'N/A'],
            [''],
            ['License Distribution', ''],
        ]

        # Add license breakdown
        for license_type, count in report.licenses_by_type.items():
            summary_data.append([f"  {license_type.replace('_', ' ').title()}", count])

        summary_data.extend([
            [''],
            ['Group Type Distribution', ''],
        ])

        # Add group type breakdown
        for group_type, count in report.groups_by_type.items():
            summary_data.append([f"  {group_type.replace('_', ' ').title()}", count])

        summary_df = pd.DataFrame(summary_data, columns=['Metric', 'Value'])
        summary_df.to_excel(writer, sheet_name='Summary', index=False)

    def _create_user_details_worksheet(self, report: OrganizationReport, writer: pd.ExcelWriter) -> None:
        """Create user details worksheet for Excel report."""
        user_data = []

        for summary in report.user_summaries:
            user = summary.user
            entitlement = summary.entitlement

            user_data.append({
                'Organization': report.organization,
                'User Name': user.display_name,
                'Email': user.mail_address or '',
                'Principal Name': user.principal_name or '',
                'Unique Name': user.unique_name or '',
                'User ID': user.id or '',
                'Origin ID': user.origin_id or '',
                'Descriptor': user.descriptor,
                'Origin': user.origin or '',
                'Domain': user.domain or '',
                'Access Level': summary.effective_access_level.value if summary.effective_access_level else 'none',
                'License Display Name': entitlement.license_display_name if entitlement else '',
                'Is Active': 'Yes' if user.is_active else 'No' if user.is_active is not None else 'Unknown',
                'Direct Groups Count': len(summary.direct_groups),
                'Total Groups Count': len(summary.all_groups),
                'Chargeback Groups': '; '.join(summary.chargeback_groups),
                'License Cost': summary.license_cost or 0.0,
                'Last Accessed': entitlement.last_accessed_date.strftime('%Y-%m-%d') if entitlement and entitlement.last_accessed_date else ''
            })

        user_df = pd.DataFrame(user_data)
        user_df.to_excel(writer, sheet_name='User Details', index=False)

    def _create_chargeback_worksheet(self, report: OrganizationReport, writer: pd.ExcelWriter) -> None:
        """Create chargeback analysis worksheet for Excel report."""
        chargeback_data = []

        for group_name, group_data in report.chargeback_by_group.items():
            licenses = group_data.get('licenses', {})
            total_users = group_data.get('total_users', 0)
            total_cost = group_data.get('total_cost', 0.0)

            chargeback_data.append({
                'Group Name': group_name,
                'Total Users': total_users,
                'Basic Licenses': licenses.get('basic', 0),
                'Stakeholder Licenses': licenses.get('stakeholder', 0),
                'VS Subscriber Licenses': licenses.get('visualStudioSubscriber', 0),
                'VS Enterprise Licenses': licenses.get('visualStudioEnterprise', 0),
                'Total Cost': total_cost,
                'Cost Per User': total_cost / total_users if total_users > 0 else 0.0
            })

        chargeback_df = pd.DataFrame(chargeback_data)
        chargeback_df.to_excel(writer, sheet_name='Chargeback Analysis', index=False)

    def _create_group_analysis_worksheet(self, report: OrganizationReport, writer: pd.ExcelWriter) -> None:
        """Create group analysis worksheet for Excel report."""
        group_data = []

        # Collect all unique groups (excluding VSTS)
        all_groups = {}
        for summary in report.user_summaries:
            for group in summary.all_groups:
                # Skip VSTS built-in groups
                if group.origin and group.origin.lower() == 'vsts':
                    continue
                all_groups[group.descriptor] = group

        for group in report.orphaned_groups:
            # Skip VSTS built-in groups
            if group.origin and group.origin.lower() == 'vsts':
                continue
            all_groups[group.descriptor] = group

        for group in all_groups.values():
            is_orphaned = group in report.orphaned_groups

            group_data.append({
                'Organization': report.organization,
                'Group Name': group.display_name,
                'Group Type': group.group_type.value if group.group_type else 'unknown',
                'Member Count': group.member_count or 0,
                'Is Security Group': 'Yes' if group.is_security_group else 'No' if group.is_security_group is not None else 'Unknown',
                'Domain': group.domain or '',
                'Origin': group.origin or '',
                'Is Orphaned': 'Yes' if is_orphaned else 'No'
            })

        group_df = pd.DataFrame(group_data)
        group_df.to_excel(writer, sheet_name='Group Analysis', index=False)

    def _create_license_analysis_worksheet(self, report: OrganizationReport, writer: pd.ExcelWriter) -> None:
        """Create license analysis worksheet for Excel report."""
        license_data = []
        total_licenses = sum(report.licenses_by_type.values())

        for license_type, count in report.licenses_by_type.items():
            percentage = (count / total_licenses * 100) if total_licenses > 0 else 0.0

            license_data.append({
                'License Type': license_type.replace('_', ' ').title(),
                'Count': count,
                'Percentage': f"{percentage:.1f}%",
                'Cost Estimate': 'N/A'  # Could be expanded with actual cost data
            })

        license_df = pd.DataFrame(license_data)
        license_df.to_excel(writer, sheet_name='License Analysis', index=False)