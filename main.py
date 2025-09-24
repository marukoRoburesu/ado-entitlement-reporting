#!/usr/bin/env python3
"""
Azure DevOps Entitlement Reporting - Main Entry Point

This script generates reports on Azure DevOps entitlements for license chargeback purposes.
"""

import sys
import logging
import colorlog
from pathlib import Path

import click

from src.config import ConfigManager, AppConfig
from src.auth import AuthManager
from src.data_processor import EntitlementDataProcessor
from src.reporting import ReportGenerator


def setup_logging(config: AppConfig, verbose: bool = False) -> None:
    """
    Set up logging configuration.

    Args:
        config: Application configuration
        verbose: Enable verbose logging
    """
    log_level = logging.DEBUG if verbose else getattr(logging, config.logging.level)

    # Create colored formatter for console output
    console_formatter = colorlog.ColoredFormatter(
        "%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'red,bg_white',
        }
    )

    # Set up console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(log_level)

    # Set up file handler if configured
    handlers = [console_handler]
    if config.logging.file:
        file_formatter = logging.Formatter(config.logging.format)
        file_handler = logging.FileHandler(config.logging.file)
        file_handler.setFormatter(file_formatter)
        file_handler.setLevel(log_level)
        handlers.append(file_handler)

    # Configure root logger
    logging.basicConfig(
        level=log_level,
        handlers=handlers,
        format=config.logging.format
    )

    # Reduce noise from external libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)


@click.command()
@click.option(
    "--organization",
    "-o",
    help="Azure DevOps organization name (overrides config file)"
)
@click.option(
    "--config",
    "-c",
    default="config/config.yaml",
    help="Configuration file path",
    type=click.Path(exists=True, path_type=Path)
)
@click.option(
    "--output",
    help="Output directory for reports (overrides config file)",
    type=click.Path(path_type=Path)
)
@click.option(
    "--format",
    "output_formats",
    type=click.Choice(["csv", "json", "excel"], case_sensitive=False),
    multiple=True,
    help="Output format(s) (overrides config file)"
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Enable verbose logging"
)
@click.option(
    "--validate-config",
    is_flag=True,
    help="Validate configuration and exit"
)
@click.option(
    "--create-config",
    type=click.Path(path_type=Path),
    help="Create default configuration file at specified path and exit"
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Perform a dry run without generating reports"
)
def main(organization, config, output, output_formats, verbose, validate_config, create_config, dry_run):
    """Generate Azure DevOps entitlement reports for license chargeback."""

    # Handle config creation
    if create_config:
        try:
            config_manager = ConfigManager()
            created_path = config_manager.create_default_config(create_config)
            click.echo(f"✅ Default configuration created at: {created_path}")
            return
        except Exception as e:
            click.echo(f"❌ Error creating configuration: {e}", err=True)
            sys.exit(1)

    # Load configuration
    try:
        config_manager = ConfigManager(config)

        # Override organizations if provided via command line
        override_orgs = [organization] if organization else None
        app_config = config_manager.load_config(override_organizations=override_orgs)

        # Set up logging early
        setup_logging(app_config, verbose)
        logger = logging.getLogger(__name__)

        logger.info(f"Configuration loaded from: {config_manager.config_path}")

    except Exception as e:
        click.echo(f"❌ Error loading configuration: {e}", err=True)
        sys.exit(1)

    # Handle config validation
    if validate_config:
        try:
            is_valid = config_manager.validate_config()
            if is_valid:
                click.echo("✅ Configuration is valid")
                return
            else:
                click.echo("❌ Configuration validation failed", err=True)
                sys.exit(1)
        except Exception as e:
            click.echo(f"❌ Error validating configuration: {e}", err=True)
            sys.exit(1)

    # Determine organizations to process
    organizations_to_process = app_config.organizations
    if not organizations_to_process:
        click.echo("❌ No organizations specified. Use --organization or configure in config file.", err=True)
        sys.exit(1)

    # Apply command line overrides
    if output:
        app_config.output.directory = str(output)

    if output_formats:
        app_config.output.formats = list(output_formats)

    # Process each organization
    logger.info("Starting Azure DevOps entitlement reporting...")

    try:
        for org in organizations_to_process:
            logger.info(f"Processing organization: {org}")
            click.echo(f"🚀 Processing organization: {org}")

            # Create authentication
            auth = AuthManager.from_environment(org)

            # Validate token
            if not auth.validate_token():
                logger.error(f"Authentication failed for organization: {org}")
                click.echo(f"❌ Authentication failed for organization: {org}", err=True)
                sys.exit(1)

            logger.info(f"✅ Authentication successful for organization: {org}")

            # Create data processor
            data_processor = EntitlementDataProcessor(auth)

            if dry_run:
                click.echo("🔍 Dry run mode - skipping data retrieval and report generation")
                click.echo(f"📁 Would save reports to: {app_config.output.directory}")
                click.echo(f"📄 Would generate formats: {', '.join(app_config.output.formats)}")
                continue

            # Generate progress indicators
            with click.progressbar(length=4, label='Retrieving data') as bar:
                # Step 1: Retrieve all data
                click.echo("\n📡 Retrieving data from Azure DevOps APIs...")
                data_processor.retrieve_all_data()
                bar.update(1)

                # Step 2: Process entitlements
                click.echo("🔄 Processing user entitlements and group memberships...")
                data_processor.process_user_entitlements()
                bar.update(1)

                # Step 3: Generate organization report
                click.echo("📊 Generating organization analysis...")
                organization_report = data_processor.generate_organization_report()
                bar.update(1)

                # Step 4: Generate output reports
                click.echo("📝 Generating reports...")
                report_generator = ReportGenerator(app_config.output.directory)
                generated_files = report_generator.generate_all_reports(
                    organization_report,
                    app_config.output.formats
                )
                bar.update(1)

            # Display results
            click.echo(f"\n✅ Report generation completed for {org}")
            click.echo(f"📊 Processed {organization_report.total_users} users, {organization_report.total_groups} groups")
            click.echo(f"📁 Reports saved to: {app_config.output.directory}")

            # Show generated files
            for format_type, file_path in generated_files.items():
                if isinstance(file_path, dict):
                    # CSV generates multiple files
                    click.echo(f"   📄 {format_type.upper()} reports:")
                    for report_type, path in file_path.items():
                        click.echo(f"      - {report_type}: {path.name}")
                else:
                    click.echo(f"   📄 {format_type.upper()}: {file_path.name}")

            # Show summary statistics
            click.echo(f"\n📈 Summary Statistics:")
            click.echo(f"   • Total Users: {organization_report.total_users}")
            click.echo(f"   • Total Groups: {organization_report.total_groups}")
            click.echo(f"   • Total Entitlements: {organization_report.total_entitlements}")

            if organization_report.chargeback_by_group:
                click.echo(f"   • Chargeback Groups: {len(organization_report.chargeback_by_group)}")

            if organization_report.total_license_cost:
                click.echo(f"   • Total License Cost: ${organization_report.total_license_cost:.2f}")

            if organization_report.orphaned_groups:
                click.echo(f"   • Orphaned Groups: {len(organization_report.orphaned_groups)}")

            # License breakdown
            if organization_report.licenses_by_type:
                click.echo(f"\n📋 License Distribution:")
                for license_type, count in organization_report.licenses_by_type.items():
                    click.echo(f"   • {license_type.replace('_', ' ').title()}: {count}")

    except Exception as e:
        logger.error(f"Error during execution: {e}")
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)

    click.echo(f"\n🎉 Azure DevOps entitlement reporting completed successfully!")
    logger.info("Azure DevOps entitlement reporting completed successfully")


if __name__ == "__main__":
    main()