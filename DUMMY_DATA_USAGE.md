# Dummy Data Generator Usage Guide

The ADO Entitlement Reporting tool includes a comprehensive dummy data generator that allows you to test the application without requiring Azure DevOps API access.

## Features

- Generate realistic user, group, entitlement, and membership data
- Reproducible data generation with seed support
- Configurable number of users and groups
- Realistic access level distribution
- Nested group memberships
- Multiple licensing sources (Account, MSDN)
- No API credentials required

## Command Line Usage

### Basic Usage

Generate dummy data reports with default settings (50 users, 15 groups):

```bash
python main.py --generate-dummy-data
```

### Custom User and Group Counts

Specify the number of users and groups to generate:

```bash
python main.py --generate-dummy-data --dummy-users 100 --dummy-groups 20
```

### Specify Output Directory

Save reports to a custom directory:

```bash
python main.py --generate-dummy-data --output ./demo-reports
```

### Complete Example

```bash
python main.py \
  --generate-dummy-data \
  --dummy-users 75 \
  --dummy-groups 12 \
  --output ./test-reports \
  --verbose
```

## Programmatic Usage

### Using the Dummy Data Generator in Tests

```python
from src.dummy_data import DummyDataGenerator

# Create generator with fixed seed for reproducibility
generator = DummyDataGenerator(seed=42)

# Generate complete dataset
users, groups, entitlements, memberships = generator.generate_complete_dataset(
    num_users=30,
    num_groups=10,
    avg_groups_per_user=3
)

# Or generate entities individually
users = generator.generate_users(count=50)
groups = generator.generate_groups(count=15)
entitlements = generator.generate_entitlements(users)
memberships = generator.generate_memberships(users, groups)
```

### Integration with Data Processor

```python
from src.dummy_data import DummyDataGenerator
from src.data_processor import EntitlementDataProcessor
from src.auth import AuthConfig, AzureDevOpsAuth
from src.config import ReportsConfig

# Generate dummy data
generator = DummyDataGenerator(seed=42)
users, groups, entitlements, memberships = generator.generate_complete_dataset(
    num_users=50,
    num_groups=15
)

# Create mock authentication (not used for actual API calls)
auth_config = AuthConfig(
    organization="test-org",
    pat_token="dummy-token"
)
auth = AzureDevOpsAuth(auth_config)

# Create processor and inject dummy data
report_config = ReportsConfig()
processor = EntitlementDataProcessor(auth, config=report_config)

# Convert lists to dictionaries (required format)
processor.users = {user.descriptor: user for user in users}
processor.groups = {group.descriptor: group for group in groups}
processor.entitlements = {ent.user_descriptor: ent for ent in entitlements}
processor.memberships = memberships

# Process and generate reports
processor.process_user_entitlements()
org_report = processor.generate_organization_report()
```

## Generated Data Characteristics

### Access Level Distribution

The dummy data generator creates realistic access level distributions:

- **Basic**: ~60% (standard user access)
- **Stakeholder**: ~20% (limited access)
- **Basic + Test Plans**: ~10% (with test management)
- **Visual Studio Professional**: ~7% (MSDN license)
- **Visual Studio Enterprise**: ~3% (MSDN license)

### Group Types

Generated groups include:

- External security groups (Azure AD) - ~70%
- Azure DevOps security groups - ~30%
- Nested group memberships (groups within groups)
- Realistic group names (Development Team, QA Team, etc.)

### User Properties

Each generated user includes:

- Unique descriptor (AAD format)
- Display name (realistic names via Faker)
- Principal name (email format)
- Mail address
- Origin information (AAD)
- Domain information

### Membership Relationships

- Users assigned to multiple groups (average configurable)
- Nested group memberships
- Realistic membership distributions

## Use Cases

### 1. Development and Testing

Test report generation logic without API access:

```bash
python main.py --generate-dummy-data --dummy-users 20 --dummy-groups 5
```

### 2. Demo and Training

Create sample reports for demonstrations:

```bash
python main.py --generate-dummy-data --dummy-users 100 --dummy-groups 25 --output ./demo
```

### 3. Performance Testing

Generate large datasets to test performance:

```bash
python main.py --generate-dummy-data --dummy-users 500 --dummy-groups 50
```

### 4. Unit Testing

Use in pytest fixtures for consistent test data:

```python
@pytest.fixture
def sample_data():
    generator = DummyDataGenerator(seed=12345)
    return generator.generate_complete_dataset(num_users=10, num_groups=5)
```

## Advantages

- **No Credentials Required**: Test without Azure DevOps PAT tokens
- **Fast**: Generate data instantly without API calls
- **Reproducible**: Use seeds for consistent test data
- **Realistic**: Data mimics real Azure DevOps structures
- **Flexible**: Configure size and characteristics
- **Offline**: Works without internet connectivity

## Example Output

When using the dummy data generator, you'll see output like:

```
[INFO] Processing organization: test-org
[INFO] Using dummy data generator (no API access required)
[INFO] Generating 50 users and 15 groups...

[STEP 1/4] Using generated dummy data...
[STEP 2/4] Processing user entitlements and group memberships...
[STEP 3/4] Generating organization analysis...
[STEP 4/4] Generating reports...

[SUCCESS] Report generation completed for test-org
[INFO] Processed 50 users, 15 groups
[INFO] Reports saved to: reports/

[SUMMARY] Statistics:
  - Total Users: 50
  - Total Groups: 15
  - Total Entitlements: 50
  - Total License Cost: $585.00

[LICENSES] Distribution:
  - Basic: 31
  - Stakeholder: 9
  - Basic + Test Plans: 6
  - Visual Studio Professional: 3
  - Visual Studio Enterprise: 1
```

## Testing

Run the comprehensive test suite for the dummy data generator:

```bash
# Run all dummy data tests
pytest tests/test_dummy_data.py -v

# Run with coverage
pytest tests/test_dummy_data.py --cov=src.dummy_data --cov-report=html
```

The test suite includes:

- Unit tests for all generator methods
- Integration tests with data processor
- Report generation tests
- Validation of data characteristics
- Reproducibility tests
- Edge case handling

## Notes

- Dummy data is generated fresh each time (not cached)
- Using a fixed seed ensures reproducible results
- Generated data follows the same schema as real Azure DevOps data
- All generated reports use the same format as production reports
- The dummy data generator filters are applied the same way as real data
