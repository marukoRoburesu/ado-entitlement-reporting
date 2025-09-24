# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This project creates scripts to handle reporting on Azure DevOps entitlements for license chargeback purposes. The system will:

- Retrieve all users, groups, and entitlements from an Azure DevOps organization
- Enable chargeback billing based on security groups and group rules
- Cross-reference users against groups and their memberships for cost allocation

## Architecture

This is a greenfield project. The recommended architecture should include:

### Core Components
- **Authentication Module**: Handle Azure DevOps API authentication using Personal Access Tokens (PAT) or OAuth
- **Data Retrieval Layer**: Interact with Azure DevOps REST APIs to fetch users, groups, and entitlements
- **Data Processing Engine**: Cross-reference users with groups and calculate entitlements per group
- **Reporting Module**: Generate chargeback reports in various formats (CSV, JSON, Excel)
- **Configuration Management**: Handle organization settings, API endpoints, and output preferences

### API Endpoints to Integrate
- Users API: `https://vssps.dev.azure.com/{organization}/_apis/graph/users`
- Groups API: `https://vssps.dev.azure.com/{organization}/_apis/graph/groups`
- Entitlements API: `https://vsaex.dev.azure.com/{organization}/_apis/userentitlements`
- Group Memberships API: `https://vssps.dev.azure.com/{organization}/_apis/graph/memberships`

## Development Guidelines

### Technology Stack Considerations
- **Python**: Recommended for robust REST API integration and data processing
- **PowerShell**: Alternative for Windows-centric environments with Azure integration
- **Node.js/TypeScript**: For web-based dashboards or modern JavaScript environments

### Required Dependencies
- HTTP client library for API calls
- Data manipulation libraries (pandas for Python, lodash for JS)
- Excel/CSV export capabilities
- Configuration file parsing (JSON/YAML)
- Logging framework

### Authentication Setup
Store Azure DevOps credentials securely:
- Use environment variables for PAT tokens
- Never commit credentials to repository
- Support multiple organization configurations

### Error Handling
Implement robust error handling for:
- API rate limiting (Azure DevOps has rate limits)
- Network connectivity issues
- Invalid or expired authentication tokens
- Missing or inaccessible organizations

### Testing Strategy
- Unit tests for data processing logic
- Integration tests with Azure DevOps APIs (using test organization)
- Mock API responses for reliable testing
- Validation of report output formats

## Data Flow

1. **Authentication**: Validate credentials and establish API connection
2. **Data Collection**: Fetch users, groups, and entitlements from Azure DevOps
3. **Cross-Reference**: Map users to groups and calculate entitlement usage
4. **Aggregation**: Group entitlements by security groups for chargeback
5. **Report Generation**: Output formatted reports for billing teams

## Configuration

Expected configuration structure:
```json
{
  "organizations": ["org1", "org2"],
  "authentication": {
    "pat_token": "env:AZURE_DEVOPS_PAT"
  },
  "output": {
    "format": ["csv", "json"],
    "path": "./reports"
  }
}
```

## Common Commands

- **Setup virtual environment**: `python3 -m venv venv && source venv/bin/activate`
- **Install dependencies**: `pip install -r requirements.txt`
- **Run reports**: `python main.py --organization <org_name>`
- **Run tests**: `pytest`
- **Run tests with coverage**: `pytest --cov=src --cov-report=html`
- **Lint code**: `flake8 src tests`
- **Format code**: `black src tests`
- **Type checking**: `mypy src`

## Security Considerations

- All API tokens must be stored as environment variables
- Implement proper logging without exposing sensitive data
- Validate all input parameters to prevent injection attacks
- Use HTTPS for all API communications
- Regular token rotation procedures