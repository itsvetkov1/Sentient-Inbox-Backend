#!/usr/bin/env python
"""
Test runner for storage module tests with mocked imports.

This script runs the storage module tests with proper import mocking to avoid
import errors from the root __init__.py file.
"""

import sys
import os
from pathlib import Path
import pytest
import coverage

# Add project root and src to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

# Mock problematic modules before any other imports
class FakeModule:
    pass

class EmailProcessor:
    pass

class EmailTopic:
    pass

class EmailClassifier:
    pass

class GmailClient:
    pass

class GroqClient:
    pass

# Create mock system modules first
sys.modules['email_processing'] = FakeModule()
sys.modules['email_processing.classification'] = FakeModule()
sys.modules['integrations.gmail'] = FakeModule()
sys.modules['integrations.groq'] = FakeModule()

# Add classes to the mock modules
sys.modules['email_processing'].EmailProcessor = EmailProcessor
sys.modules['email_processing.classification'].EmailTopic = EmailTopic
sys.modules['email_processing.classification'].EmailClassifier = EmailClassifier
sys.modules['integrations.gmail'].GmailClient = GmailClient  
sys.modules['integrations.groq'].GroqClient = GroqClient

def run_tests():
    """Run storage module tests with coverage."""
    # Initialize coverage
    cov = coverage.Coverage(
        source=["src.storage"],
        omit=["*/tests/*", "*/migrations/*"]
    )
    
    cov.start()
    
    # Run pytest on the storage tests
    test_path = "tests/unit/storage"
    result = pytest.main([test_path, "-v", "--import-mode=importlib"])
    
    cov.stop()
    cov.save()
    
    # Print coverage report to console
    print("\nCoverage Summary:\n" + "=" * 70)
    total = cov.report()
    
    # Generate HTML report
    print("\nGenerating HTML coverage report...")
    cov.html_report(directory="coverage_html")
    print(f"HTML report generated at: {os.path.abspath('coverage_html/index.html')}")
    
    # Report results
    if result == 0:
        print("\n✅ All tests passed!")
    else:
        print(f"\n❌ Tests failed with exit code: {result}")
    
    return result

if __name__ == "__main__":
    sys.exit(run_tests())
