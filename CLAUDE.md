# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a fully implemented Python application that generates comprehensive Azure DevOps entitlement reports for license chargeback purposes. The system:

- Retrieves all users, groups, and entitlements from Azure DevOps organizations
- Enables chargeback billing based on security groups and group rules
- Cross-references users against groups and their memberships for cost allocation
- Supports multi-organization reporting with consolidated outputs
- Excludes VSTS built-in groups, service accounts, and system users automatically
- Supports external Azure AD security groups for chargeback allocation

## Architecture

This is a **completed and production-ready** project with the following architecture:

### Core Components (Implemented)

1. **Authentication Module** (`src/auth.py`)
   - `AuthManager` class for PAT token authentication
   - Token validation against Azure DevOps APIs
   - Environment variable support for secure credential storage
   - Organization-specific authentication management

2. **Data Retrieval Layer** (`src/data_retrieval.py`)
   - `UsersApiClient`: Fetches users and their metadata
   - `GroupsApiClient`: Retrieves security groups and Azure AD groups
   - `EntitlementsApiClient`: Gets user entitlements and license information (Basic, Stakeholder, Basic+Test Plans, Advanced)
   - `MembershipsApiClient`: Retrieves group membership relationships
   - All clients include retry logic and error handling

3. **Data Processing Engine** (`src/data_processor.py`)
   - `EntitlementDataProcessor`: Main orchestrator for data processing
   - Cross-references users with groups and entitlements
   - Calculates chargeback allocations based on security groups
   - Filters out VSTS built-in groups and service accounts
   - Supports external Azure AD security groups
   - Generates comprehensive organization reports

4. **Reporting Module** (`src/reporting.py`)
   - `ReportGenerator`: Creates per-organization reports in CSV, JSON, and Excel formats
   - `ConsolidatedReportGenerator`: Generates cross-organization consolidated reports
   - Four CSV reports per organization: User Summary, Chargeback, Group Analysis, License Summary
   - Complete JSON export with all metadata
   - Multi-worksheet Excel reports

5. **Configuration Management** (`src/config.py`)
   - `ConfigManager`: YAML configuration file handling
   - Pydantic-based configuration validation
   - Support for environment variable overrides
   - Default configuration creation

6. **Data Models** (`src/models.py`)
   - Pydantic models for type safety and validation
   - `User`, `Group`, `Entitlement`, `Membership` models
   - `UserSummary`, `ChargebackGroup`, `OrganizationReport` models
   - Full type hints throughout the codebase

### Integrated API Endpoints
All Azure DevOps REST API endpoints are fully integrated:
- Users API: `https://vssps.dev.azure.com/{organization}/_apis/graph/users`
- Groups API: `https://vssps.dev.azure.com/{organization}/_apis/graph/groups`
- Entitlements API: `https://vsaex.dev.azure.com/{organization}/_apis/userentitlements`
- Group Memberships API: `https://vssps.dev.azure.com/{organization}/_apis/graph/memberships/{descriptor}`

## Development Guidelines

### Technology Stack (Implemented)
- **Python 3.8+**: Production implementation with full type hints
- **Core Libraries**:
  - `requests`: HTTP client for Azure DevOps APIs
  - `pydantic`: Data validation and settings management
  - `pandas`: Data manipulation and CSV generation
  - `openpyxl`: Excel file generation
  - `click`: CLI interface
  - `colorlog`: Colored console logging
  - `python-dotenv`: Environment variable management
  - `pyyaml`: YAML configuration parsing

### Authentication (Implemented)
Secure credential storage is fully implemented:
- ✅ Environment variables for PAT tokens (`AZURE_DEVOPS_PAT`)
- ✅ `.env` file support with `.env.example` template
- ✅ `.gitignore` configured to prevent credential commits
- ✅ Multiple organization support via configuration files
- ✅ Token validation before processing

### Error Handling (Implemented)
Comprehensive error handling for:
- ✅ API rate limiting with automatic retry logic
- ✅ Network connectivity issues and timeouts
- ✅ Invalid or expired authentication tokens
- ✅ Missing or inaccessible organizations
- ✅ Malformed API responses
- ✅ File I/O errors during report generation

### Testing Strategy (Implemented)
Complete test suite with 124 tests:
- ✅ Unit tests for all core modules (`test_auth.py`, `test_config.py`, `test_data_processor.py`, etc.)
- ✅ Mock API responses using `responses` library for reliable testing
- ✅ Validation of all report output formats
- ✅ Edge case testing (empty organizations, missing data, etc.)
- ✅ Test coverage reporting with `pytest-cov`
- ✅ Type checking with `mypy`
- ✅ Code formatting with `black`
- ✅ Linting with `flake8`

## Data Flow (Implemented)

The application follows this production workflow:

1. **Configuration Loading** (`ConfigManager`)
   - Load YAML configuration file
   - Apply environment variable overrides
   - Validate configuration with pydantic

2. **Authentication** (`AuthManager`)
   - Validate credentials against Azure DevOps APIs
   - Establish authenticated session for organization

3. **Data Retrieval** (`EntitlementDataProcessor.retrieve_all_data()`)
   - Fetch all users via `UsersApiClient`
   - Fetch all groups via `GroupsApiClient`
   - Fetch all entitlements via `EntitlementsApiClient`
   - Fetch group memberships via `MembershipsApiClient`
   - Filter out VSTS built-in users and service accounts

4. **Data Processing** (`EntitlementDataProcessor.process_user_entitlements()`)
   - Map users to their entitlements
   - Cross-reference users with group memberships
   - Determine chargeback group for each user
   - Exclude VSTS built-in groups from chargeback
   - Support external Azure AD security groups

5. **Aggregation** (`EntitlementDataProcessor.generate_organization_report()`)
   - Calculate license costs per user
   - Aggregate costs by chargeback groups
   - Identify orphaned groups (groups with no members)
   - Generate license distribution statistics

6. **Report Generation** (`ReportGenerator`)
   - Generate 4 CSV reports per organization
   - Generate JSON export with complete data
   - Generate multi-worksheet Excel report
   - For multiple organizations: generate consolidated reports

7. **Consolidated Reporting** (`ConsolidatedReportGenerator`)
   - Combine user data across all organizations
   - Aggregate chargeback data across organizations
   - Include organization field for tracking

## Configuration (Implemented)

The application uses YAML configuration files (`config/config.yaml`):

```yaml
# Azure DevOps Organizations
organizations:
  - "org1"
  - "org2"

# API Configuration
api:
  base_url: "https://vssps.dev.azure.com"
  timeout: 30
  max_retries: 3
  rate_limit_delay: 1.0

# Output Configuration
output:
  directory: "./reports"
  formats:
    - csv
    - json
    - excel

# Logging Configuration
logging:
  level: "INFO"
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  file: "azure_devops_reporting.log"

# Report Configuration
reports:
  include_empty_groups: false
  group_details: true
  user_details: true
```

**Note**: License costs are hard-coded in `src/data_processor.py` based on Microsoft's standard pricing.

Environment variables (stored in `.env` file):
```bash
AZURE_DEVOPS_PAT=your-personal-access-token
AZURE_DEVOPS_ORG=your-default-organization
```

## Common Commands (Implemented)

### Development Setup
- **Setup virtual environment**: `python -m venv venv && source venv/bin/activate`
- **Install dependencies**: `pip install -r requirements.txt`
- **Setup environment**: Copy `.env.example` to `.env` and add your PAT token

### Running Reports
- **Single organization**: `python main.py --organization <org_name>`
- **Multiple organizations**: `python main.py --config config/config.yaml`
- **Custom output directory**: `python main.py --organization <org_name> --output ./custom-reports`
- **Specific formats**: `python main.py --organization <org_name> --format csv json`
- **Verbose logging**: `python main.py --organization <org_name> --verbose`
- **Dry run**: `python main.py --dry-run --organization <org_name>`
- **Validate config**: `python main.py --validate-config`
- **Create default config**: `python main.py --create-config config/config.yaml`

### Testing and Quality
- **Run all tests**: `python -m pytest tests/ -v`
- **Run tests with coverage**: `python -m pytest tests/ --cov=src --cov-report=html`
- **Run specific test**: `python -m pytest tests/test_reporting.py -v`
- **Type checking**: `mypy src/`
- **Code formatting**: `black src/ tests/`
- **Linting**: `flake8 src/ tests/`

## Security Considerations (Implemented)

All security best practices are implemented:
- ✅ API tokens stored in environment variables (`.env` file)
- ✅ `.gitignore` configured to exclude `.env`, `reports/`, logs
- ✅ Logging configured to avoid exposing sensitive data (tokens, passwords)
- ✅ All API communications use HTTPS
- ✅ Input validation via pydantic models
- ✅ No hardcoded credentials in codebase
- ✅ `.env.example` template provided for setup guidance

### Required Azure DevOps Permissions
Your PAT token needs:
- **Identity (Read)**: For user and group information
- **User Entitlements (Read)**: For license information
- **Graph (Read)**: For membership relationships

## Key Implementation Details

### Built-in Group Filtering
The system automatically excludes VSTS built-in groups from chargeback:
- Groups starting with `[TEAM FOUNDATION]`
- Groups starting with `[<organization>]\` (default project groups)
- Service accounts and system users

### Chargeback Group Determination
The system determines chargeback groups using this logic:
1. Prioritizes external security groups (Azure AD groups)
2. Falls back to Azure DevOps security groups
3. Excludes built-in system groups
4. Handles users with multiple group memberships

### Supported Access Levels
- **Basic**: Standard user access
- **Stakeholder**: Limited access for stakeholders
- **Basic + Test Plans**: Basic access with test management
- **Advanced**: Full access (formerly VS Enterprise)

### Multi-Organization Support
- Process multiple organizations in a single run
- Generates per-organization reports
- Creates consolidated cross-organization reports
- Includes organization field in all consolidated data