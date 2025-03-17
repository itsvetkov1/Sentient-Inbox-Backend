# Test Coverage Improvement Plan

This document outlines the comprehensive plan for improving test coverage in the Sentient-Inbox-Backend project to reach 100% coverage.

## Current Coverage Status

As of the analysis on 3/14/2025:
* Overall coverage: 14.12%
* Most critical uncovered modules:
  * Storage modules (database.py, encryption.py, secure.py, user_repository.py)
  * API services
  * Email processing components
  * Integration modules (gmail, groq)

## Dependencies Required

Several dependencies must be properly installed to run the tests:

```
# Core Testing Dependencies
pytest>=7.0.0
pytest-asyncio>=0.21.0
pytest-cov>=4.1.0
coverage>=7.0.0

# Database Dependencies
sqlalchemy>=2.0.0

# Encryption & Security Dependencies
cryptography>=41.0.0
```

## Test Structure Improvements

### 1. Storage Module Tests

#### A. Encryption Module (src/storage/encryption.py)
* Test cryptographic key generation
* Test value encryption/decryption
* Test error handling for invalid inputs
* Test null/empty value handling

#### B. Database Module (src/storage/database.py)
* Test session creation and management
* Test connection pooling configuration
* Test error handling and connection recovery
* Mock SQLAlchemy components to avoid actual database operations

#### C. User Repository (src/storage/user_repository.py)
* Test user creation, retrieval, and updates
* Test OAuth token management
* Test error handling for database operations
* Test encryption integration for sensitive fields

#### D. Secure Storage (src/storage/secure.py)
* Test encryption and decryption operations
* Test key rotation mechanisms
* Test backup and recovery procedures
* Test record management operations

### 2. API Services Tests

#### A. Email Service (api/services/email_service.py)
* Test email retrieval operations
* Test email analysis workflow
* Test error handling and retry logic
* Mock external dependencies (Gmail API, AI models)

#### B. Dashboard Service (api/services/dashboard_service.py)
* Test statistics calculations
* Test data aggregation methods
* Test filtering and sorting operations
* Mock data sources to provide predictable inputs

### 3. Integration Tests

#### A. Gmail Integration (src/integrations/gmail/)
* Test authentication flows
* Test email retrieval, modification, and sending
* Test error handling for API failures
* Mock Google API responses

#### B. Groq Integration (src/integrations/groq/)
* Test AI model interactions
* Test retry mechanisms
* Test error handling
* Mock API responses for deterministic testing

## Implementation Approach

### Phase 1: Fix Testing Infrastructure
1. Resolve dependency issues (sqlalchemy, cryptography)
2. Create proper test runners with import mocking
3. Establish baseline coverage metrics

### Phase 2: Core Module Tests
1. Implement storage module tests
2. Implement authentication tests
3. Implement model tests

### Phase 3: Service & Integration Tests
1. Implement service layer tests
2. Implement integration tests
3. Implement API route tests

### Phase 4: End-to-End Tests
1. Implement workflow tests
2. Test error recovery scenarios
3. Measure and validate complete coverage

## Test Implementation Best Practices

1. **Isolation**: Every test should be independent and not rely on the state from other tests
2. **Mocking**: External dependencies should be mocked to provide predictable behavior
3. **Error Cases**: Test both success and failure paths
4. **Edge Cases**: Include tests for boundary conditions and unusual inputs
5. **Code Quality**: Tests should be as well-structured and documented as the code they test

## Continuous Integration

Add coverage reporting to CI pipeline:
```yaml
- name: Run tests with coverage
  run: |
    python test_runner_with_coverage.py --report --xml --threshold=100
```

## Tracking & Metrics

Create a coverage dashboard that tracks:
* Overall coverage percentage
* Coverage by module
* Uncovered lines report
* Historical coverage trends

## Next Steps

1. Resolve dependency conflicts in the testing environment
2. Set up the CI pipeline with coverage reporting
3. Implement unit tests for storage modules (highest priority)
4. Expand testing to service and API layers
