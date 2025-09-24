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


class ReportGenerator:
    """
    Main report generator class that handles multiple output formats
    for Azure DevOps entitlement reporting.
    """

    def __init__(self, output_directory: Union[str, Path] = "./reports"):
        """
        Initialize the report generator.

        Args:
            output_directory: Directory to save reports
        """
        self.output_directory = Path(output_directory)
        self.output_directory.mkdir(parents=True, exist_ok=True)
        logger.info(f"Report generator initialized with output directory: {self.output_directory}")

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
        timestamp = report.generated_at.strftime("%Y%m%d_%H%M%S")
        org_name = report.organization

        csv_files = {}

        # 1. User Summary Report
        user_summary_file = self.output_directory / f"{org_name}_user_summary_{timestamp}.csv"
        csv_files['user_summary'] = self._generate_user_summary_csv(report, user_summary_file)

        # 2. Chargeback Report
        chargeback_file = self.output_directory / f"{org_name}_chargeback_{timestamp}.csv"
        csv_files['chargeback'] = self._generate_chargeback_csv(report, chargeback_file)

        # 3. Group Analysis Report
        group_analysis_file = self.output_directory / f"{org_name}_group_analysis_{timestamp}.csv"
        csv_files['group_analysis'] = self._generate_group_analysis_csv(report, group_analysis_file)

        # 4. License Summary Report
        license_summary_file = self.output_directory / f"{org_name}_license_summary_{timestamp}.csv"
        csv_files['license_summary'] = self._generate_license_summary_csv(report, license_summary_file)

        logger.info(f"Generated {len(csv_files)} CSV reports")
        return csv_files

    def _generate_user_summary_csv(self, report: OrganizationReport, file_path: Path) -> Path:
        """Generate detailed user summary CSV report."""
        logger.debug(f"Generating user summary CSV: {file_path}")

        with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = [
                'User Name', 'Email', 'Principal Name', 'Access Level', 'License Display Name',
                'Is Active', 'Direct Groups', 'All Groups', 'Chargeback Groups',
                'License Cost', 'Last Accessed', 'Origin'
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for summary in report.user_summaries:
                user = summary.user
                entitlement = summary.entitlement

                writer.writerow({
                    'User Name': user.display_name,
                    'Email': user.mail_address or user.unique_name or '',
                    'Principal Name': user.principal_name or '',
                    'Access Level': summary.effective_access_level.value if summary.effective_access_level else 'none',
                    'License Display Name': entitlement.license_display_name if entitlement else '',
                    'Is Active': 'Yes' if user.is_active else 'No' if user.is_active is not None else 'Unknown',
                    'Direct Groups': '; '.join([g.display_name for g in summary.direct_groups]),
                    'All Groups': '; '.join([g.display_name for g in summary.all_groups]),
                    'Chargeback Groups': '; '.join(summary.chargeback_groups),
                    'License Cost': summary.license_cost or 0.0,
                    'Last Accessed': entitlement.last_accessed_date.strftime('%Y-%m-%d') if entitlement and entitlement.last_accessed_date else '',
                    'Origin': user.origin or ''
                })

        return file_path

    def _generate_chargeback_csv(self, report: OrganizationReport, file_path: Path) -> Path:
        """Generate chargeback analysis CSV report."""
        logger.debug(f"Generating chargeback CSV: {file_path}")

        with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = [
                'Group Name', 'Total Users', 'Basic Licenses', 'Stakeholder Licenses',
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
                basic_count = licenses.get('basic', 0)
                stakeholder_count = licenses.get('stakeholder', 0)
                vs_subscriber_count = licenses.get('visualStudioSubscriber', 0)
                vs_enterprise_count = licenses.get('visualStudioEnterprise', 0)
                other_count = total_users - (basic_count + stakeholder_count + vs_subscriber_count + vs_enterprise_count)

                writer.writerow({
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
                'Group Name', 'Group Type', 'Member Count', 'Is Security Group',
                'Domain', 'Origin', 'Is Orphaned', 'Principal Name'
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            # Get all groups from user summaries
            all_groups = {}
            for summary in report.user_summaries:
                for group in summary.all_groups:
                    all_groups[group.descriptor] = group

            # Add orphaned groups
            for group in report.orphaned_groups:
                all_groups[group.descriptor] = group

            for group in all_groups.values():
                is_orphaned = group in report.orphaned_groups

                writer.writerow({
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
        timestamp = report.generated_at.strftime("%Y%m%d_%H%M%S")
        org_name = report.organization
        file_path = self.output_directory / f"{org_name}_complete_report_{timestamp}.json"

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
                        'email': summary.user.mail_address or summary.user.unique_name,
                        'principal_name': summary.user.principal_name,
                        'is_active': summary.user.is_active,
                        'origin': summary.user.origin
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
        timestamp = report.generated_at.strftime("%Y%m%d_%H%M%S")
        org_name = report.organization
        file_path = self.output_directory / f"{org_name}_report_{timestamp}.xlsx"

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
                'User Name': user.display_name,
                'Email': user.mail_address or user.unique_name or '',
                'Principal Name': user.principal_name or '',
                'Access Level': summary.effective_access_level.value if summary.effective_access_level else 'none',
                'License Display Name': entitlement.license_display_name if entitlement else '',
                'Is Active': 'Yes' if user.is_active else 'No' if user.is_active is not None else 'Unknown',
                'Direct Groups Count': len(summary.direct_groups),
                'Total Groups Count': len(summary.all_groups),
                'Chargeback Groups': '; '.join(summary.chargeback_groups),
                'License Cost': summary.license_cost or 0.0,
                'Last Accessed': entitlement.last_accessed_date.strftime('%Y-%m-%d') if entitlement and entitlement.last_accessed_date else '',
                'Origin': user.origin or ''
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

        # Collect all unique groups
        all_groups = {}
        for summary in report.user_summaries:
            for group in summary.all_groups:
                all_groups[group.descriptor] = group

        for group in report.orphaned_groups:
            all_groups[group.descriptor] = group

        for group in all_groups.values():
            is_orphaned = group in report.orphaned_groups

            group_data.append({
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