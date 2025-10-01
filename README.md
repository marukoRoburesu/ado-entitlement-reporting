# Azure DevOps Entitlement Reporting

A comprehensive Python tool for generating Azure DevOps entitlement reports for license chargeback purposes. This enterprise-grade solution provides detailed insights into user entitlements, group memberships, and license costs across Azure DevOps organizations.

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://img.shields.io/badge/tests-120%20passing-green.svg)]()

## ✨ Features

### 🔍 **Comprehensive Data Retrieval**
- **Multi-API Integration**: Seamlessly integrates with Azure DevOps Users, Groups, Entitlements, and Memberships APIs
- **Smart Rate Limiting**: Automatic retry mechanisms and rate limit handling for large organizations
- **Recursive Group Resolution**: Resolves nested group memberships with cycle detection
- **Real-time Token Validation**: Validates Azure DevOps PAT tokens before processing
- **Built-in Group Exclusions**: Automatically filters VSTS built-in groups, service accounts, and system users

### 📊 **Advanced Reporting**
- **Multiple Export Formats**: CSV, JSON, and Excel reports for different stakeholder needs
- **Chargeback Analysis**: Detailed cost allocation by security groups with external group support
- **Consolidated Multi-Org Reports**: Generate combined reports across multiple Azure DevOps organizations
- **License Distribution**: Complete breakdown of Basic, Stakeholder, Basic + Test Plans, Visual Studio Subscriber, and Visual Studio Enterprise access levels
- **Orphaned Group Detection**: Identifies unused groups and optimization opportunities

### 🛠️ **Enterprise-Ready Features**
- **YAML Configuration**: Flexible configuration management with validation
- **Environment Variables**: Secure credential storage and management
- **Comprehensive Logging**: Colored console output with file logging support
- **Progress Indicators**: Real-time progress bars for long-running operations
- **Dry-Run Mode**: Test configurations without generating actual reports
- **Multi-Organization Support**: Process multiple Azure DevOps organizations in a single run

### 🧪 **Quality Assurance**
- **124 Tests**: Comprehensive test suite with 100% pass rate
- **Type Safety**: Full type hints with pydantic models and validation
- **Code Quality**: Black formatting and flake8 linting
- **Error Handling**: Robust error handling for network issues and API limits

## 🚀 Quick Start

### Prerequisites

- Python 3.8 or higher
- Azure DevOps Personal Access Token (PAT) with appropriate permissions
- Access to Azure DevOps organization(s)

### Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd azure-devops-entitlement-reporting
   ```

2. **Set up virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Create configuration**:
   ```bash
   python main.py --create-config config/config.yaml
   ```

5. **Set up environment variables**:
   ```bash
   export AZURE_DEVOPS_PAT="your-personal-access-token"
   export AZURE_DEVOPS_ORG="your-organization-name"
   ```

### Basic Usage

**Generate reports for a single organization:**
```bash
python main.py --organization myorg --format csv json excel
```

**Use configuration file:**
```bash
python main.py --config config/config.yaml --verbose
```

**Dry run to test configuration:**
```bash
python main.py --dry-run --organization myorg
```

## 📋 Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `AZURE_DEVOPS_PAT` | Personal Access Token | ✅ |
| `AZURE_DEVOPS_ORG` | Default organization name | ✅ |

### Configuration File (config.yaml)

```yaml
# Azure DevOps Organizations
organizations:
  - "myorg1"
  - "myorg2"

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
  timestamp_format: "%Y%m%d_%H%M%S"
  include_timestamp: true  # Set to false for static filenames (daemon/dashboard use)

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

  # Filtering options - exclude VSTS built-in users and groups from all reports
  exclude_vsts_users: true   # Filter out VSTS built-in users and service accounts
  exclude_vsts_groups: true  # Filter out VSTS built-in groups
```

**Notes**:
- License costs are built-in based on Microsoft's standard pricing and cannot be configured
- VSTS filtering is enabled by default to exclude built-in users/groups from reports
- Set `include_timestamp: false` to generate static filenames (e.g., `org_user_summary.csv`) that overwrite on each run, ideal for daemon/dashboard scenarios

## 🎯 Usage Examples

### Command Line Options

```bash
# Basic report generation (single organization)
python main.py --organization myorg

# Multiple organizations from config file (generates consolidated reports)
python main.py --config config/config.yaml

# Custom output directory
python main.py --config config/config.yaml --output ./custom-reports

# Specific formats only
python main.py --organization myorg --format csv excel

# Verbose logging for debugging
python main.py --organization myorg --verbose

# Validate configuration
python main.py --validate-config --config config/config.yaml

# Create default configuration
python main.py --create-config ./my-config.yaml

# Test run without generating reports
python main.py --dry-run --organization myorg
```

### Programmatic Usage

```python
from src.auth import AuthManager
from src.data_processor import EntitlementDataProcessor
from src.reporting import ReportGenerator

# Create authentication
auth = AuthManager.from_environment("myorg")

# Validate token
if not auth.validate_token():
    raise Exception("Authentication failed")

# Process data
processor = EntitlementDataProcessor(auth)

# Retrieve and process all data
processor.retrieve_all_data()
processor.process_user_entitlements()

# Generate organization report
report = processor.generate_organization_report()

# Generate reports
generator = ReportGenerator("./reports")
files = generator.generate_all_reports(report, ["csv", "json", "excel"])

print(f"Generated reports: {files}")
print(f"Total users: {report.total_users}")
print(f"Total license cost: ${report.total_license_cost:.2f}")
```

## 📊 Report Types

### Per-Organization Reports

Each organization generates the following reports:

#### CSV Reports (4 Files Per Organization)

1. **User Summary** (`{org}_user_summary_{timestamp}.csv`)
   - Complete user details with entitlements and group memberships
   - License information and costs (Basic, Stakeholder, Basic + Test Plans, Visual Studio subscriptions)
   - Email addresses and chargeback group assignments
   - Filtered to exclude VSTS built-in users and service accounts

2. **Chargeback Analysis** (`{org}_chargeback_{timestamp}.csv`)
   - Cost allocation by security groups (including external Azure AD groups)
   - License distribution per chargeback group
   - User counts and total costs per group
   - Supports all access levels including Visual Studio subscriptions

3. **Group Analysis** (`{org}_group_analysis_{timestamp}.csv`)
   - Group types and member counts
   - Orphaned group identification
   - Group hierarchy information
   - Origin (Azure DevOps vs External/AAD)

4. **License Summary** (`{org}_license_summary_{timestamp}.csv`)
   - License type distribution (Basic, Stakeholder, Basic + Test Plans, Visual Studio subscriptions)
   - Cost analysis and utilization
   - Percentage breakdowns

#### JSON Report (`{org}_complete_report_{timestamp}.json`)

Complete data export with full hierarchical structure including all metadata, users, groups, chargeback analysis, and license information.

#### Excel Report (`{org}_entitlement_report_{timestamp}.xlsx`)

Multi-worksheet Excel file with separate tabs for Summary, User Details, Chargeback, Group Analysis, and License Analysis.

### Consolidated Multi-Organization Reports

When processing multiple organizations, two additional consolidated reports are generated:

1. **Consolidated User Report** (`all_organizations_users_{timestamp}.csv`)
   - Combined user data from all organizations
   - Includes organization field for tracking
   - Consolidated view of all users across the enterprise

2. **Consolidated Chargeback Report** (`all_organizations_chargeback_{timestamp}.csv`)
   - Aggregated chargeback data across all organizations
   - Organization-level cost breakdowns
   - Enterprise-wide license cost visibility

### JSON Report Structure

Complete data export with full hierarchical structure:
```json
{
  "metadata": {
    "organization": "myorg",
    "generated_at": "2025-09-30T10:30:00Z",
    "total_users": 150,
    "total_groups": 25,
    "total_entitlements": 150,
    "total_license_cost": 7500.0
  },
  "chargeback_analysis": {
    "Development Team": {
      "total_users": 12,
      "total_cost": 600.0,
      "licenses": {"basic": 10, "stakeholder": 2}
    }
  },
  "user_summaries": [...],
  "licenses_by_type": {
    "basic": 100,
    "stakeholder": 40,
    "basic_test_plans": 5,
    "advanced": 5
  },
  "orphaned_groups": [...]
}
```

## 🔧 Development

### Setting Up Development Environment

```bash
# Clone and setup
git clone <repository-url>
cd azure-devops-entitlement-reporting
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Install development dependencies
pip install pytest pytest-cov black flake8 mypy

# Run tests
python -m pytest tests/ -v --cov=src

# Code formatting
black src/ tests/

# Type checking
mypy src/

# Linting
flake8 src/ tests/
```

### Project Structure

```
ado-entitlement-reporting/
├── src/                          # Source code
│   ├── __init__.py
│   ├── auth.py                  # Authentication and token validation
│   ├── config.py                # Configuration management with pydantic
│   ├── data_processor.py        # Data processing and analysis engine
│   ├── data_retrieval.py        # Azure DevOps API clients
│   ├── models.py                # Pydantic data models
│   └── reporting.py             # Report generation (CSV, JSON, Excel)
├── tests/                       # Test suite (124 tests)
│   ├── test_auth.py
│   ├── test_config.py
│   ├── test_data_processor.py
│   ├── test_data_retrieval.py
│   ├── test_models.py
│   └── test_reporting.py
├── config/                      # Configuration files directory
├── main.py                      # CLI entry point
├── requirements.txt             # Dependencies
├── pytest.ini                   # Test configuration
├── CLAUDE.md                    # AI assistant guidance
├── .env.example                 # Environment variables template
├── .gitignore                   # Git ignore patterns
└── README.md                    # This file
```

### Testing

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test module
python -m pytest tests/test_reporting.py -v

# Run with coverage
python -m pytest tests/ --cov=src --cov-report=html

# Run performance tests
python -m pytest tests/ -k "large_dataset" -v
```

## 🔐 Security Considerations

### Token Security
- **Never commit PAT tokens** to version control
- Use environment variables or secure credential stores
- Regularly rotate Personal Access Tokens
- Grant minimal required permissions

### Required Azure DevOps Permissions
Your PAT token needs the following scopes:
- **Identity (Read)**: For user and group information
- **User Entitlements (Read)**: For license information
- **Graph (Read)**: For membership relationships

### Data Protection
- Generated reports may contain sensitive user information
- Store reports in secure locations with appropriate access controls
- Consider encryption for report storage
- Implement data retention policies

## 🚨 Troubleshooting

### Common Issues

**Authentication Errors**
```bash
# Verify token and organization
python main.py --validate-config --organization myorg

# Check environment variables
echo $AZURE_DEVOPS_PAT
echo $AZURE_DEVOPS_ORG
```

**Rate Limiting**
```bash
# Use verbose logging to see rate limit details
python main.py --verbose --organization myorg

# Increase retry delays in configuration
# api.rate_limit_delay: 2.0
```

**Large Organizations**
```bash
# Use dry-run to estimate processing time
python main.py --dry-run --organization large-org

# Monitor progress with verbose logging
python main.py --verbose --organization large-org
```

**Memory Issues**
```bash
# Process organizations individually
python main.py --organization org1
python main.py --organization org2

# Use CSV format only for large datasets
python main.py --organization large-org --format csv
```

### Getting Help

1. **Check logs**: Review log files in the `logs/` directory
2. **Run tests**: Ensure your environment is correctly set up
3. **Validate config**: Use `--validate-config` to check configuration
4. **Dry run**: Use `--dry-run` to test without generating reports

## 🤝 Contributing

### Development Workflow

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Make** your changes with tests
4. **Run** the test suite (`python -m pytest tests/ -v`)
5. **Format** code (`black src/ tests/`)
6. **Commit** your changes (`git commit -m 'Add amazing feature'`)
7. **Push** to the branch (`git push origin feature/amazing-feature`)
8. **Create** a Pull Request

### Code Standards

- **Python 3.8+** compatibility
- **Type hints** for all functions
- **Comprehensive tests** for new features
- **Black** code formatting
- **Flake8** linting compliance
- **Docstrings** for all public functions

## 📈 Performance

### Benchmarks

| Organization Size | Processing Time | Memory Usage | Reports Generated |
|------------------|-----------------|--------------|-------------------|
| Small (< 100 users) | 30-60 seconds | < 100MB | 6 files |
| Medium (100-500 users) | 2-5 minutes | 100-300MB | 6 files |
| Large (500+ users) | 5-15 minutes | 300-500MB | 6 files |

### Optimization Tips

- **Process organizations individually** for very large enterprises
- **Use CSV format only** for faster processing
- **Enable rate limiting** for API stability
- **Run during off-peak hours** for better API performance

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **Azure DevOps REST API** for comprehensive entitlement data
- **Python community** for excellent libraries and tools
- **Enterprise DevOps teams** for requirements and feedback

---

**Built with ❤️ for Azure DevOps administrators and finance teams seeking comprehensive license chargeback solutions.**