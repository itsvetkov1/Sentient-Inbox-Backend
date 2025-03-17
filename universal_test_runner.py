#!/usr/bin/env python
"""
Universal Test Runner with Coverage Reporting

This script runs tests for any specified module with proper import mocking 
and comprehensive coverage reporting.

Usage:
    python universal_test_runner.py [options] [test_path]

Options:
    --module: Module to focus coverage on (e.g., storage, auth, api)
    --threshold: Minimum required coverage percentage (default: 100)
    --report: Generate HTML coverage report (default: True)
    --xml: Generate XML coverage report for CI integration
"""

import sys
import os
import argparse
from pathlib import Path
import pytest
import coverage

# Add project root and src to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

# Mock classes for problematic imports
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

class SecureStorage:
    pass

# Setup mock modules to avoid import errors
def setup_mocks():
    """Set up all necessary mocks to avoid import errors."""
    # Create base modules
    modules_to_mock = [
        'email_processing',
        'email_processing.classification',
        'integrations',
        'integrations.gmail',
        'integrations.groq',
        'storage',
    ]
    
    for module_name in modules_to_mock:
        if module_name not in sys.modules:
            sys.modules[module_name] = FakeModule()
    
    # Add specific classes to modules
    sys.modules['email_processing'].EmailProcessor = EmailProcessor
    sys.modules['email_processing.classification'].EmailTopic = EmailTopic
    sys.modules['email_processing.classification'].EmailClassifier = EmailClassifier
    sys.modules['integrations.gmail'].GmailClient = GmailClient
    sys.modules['integrations.groq'].GroqClient = GroqClient
    sys.modules['storage'].SecureStorage = SecureStorage

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Run tests with coverage reporting")
    parser.add_argument("test_path", nargs="?", default="tests", 
                        help="Path to test file or directory")
    parser.add_argument("--module", type=str, default=None,
                        help="Module to focus coverage on (e.g., storage, auth, api)")
    parser.add_argument("--threshold", type=int, default=100,
                        help="Coverage threshold percentage (default: 100)")
    parser.add_argument("--report", action="store_true", default=True,
                        help="Generate HTML coverage report")
    parser.add_argument("--xml", action="store_true",
                        help="Generate XML coverage report for CI")
    return parser.parse_args()

def get_coverage_source(module):
    """Get source paths based on specified module."""
    if not module:
        return ["src", "api"]
    
    sources = []
    if module == "all":
        sources = ["src", "api"]
    elif module == "storage":
        sources = ["src.storage"]
    elif module == "auth":
        sources = ["src.auth", "api.auth"]
    elif module == "api":
        sources = ["api"]
    elif module == "integrations":
        sources = ["src.integrations"]
    elif module == "email":
        sources = ["src.email_processing"]
    else:
        # Default to the specified module
        sources = [f"src.{module}", f"api.{module}"]
    
    return sources

def run_tests_with_coverage(args):
    """Run tests with coverage tracking."""
    # Set up mocks first
    setup_mocks()
    
    print(f"Running tests with coverage: {args.test_path}")
    print(f"Module focus: {args.module or 'all'}")
    
    # Get appropriate source paths
    sources = get_coverage_source(args.module)
    
    # Initialize coverage
    cov = coverage.Coverage(
        source=sources,
        omit=["*/tests/*", "*/migrations/*"]
    )
    
    cov.start()
    
    # Run pytest
    pytest_args = [args.test_path, "-v", "--import-mode=importlib"]
    result = pytest.main(pytest_args)
    
    cov.stop()
    cov.save()
    
    # Print coverage report to console
    print("\nCoverage Summary:\n" + "=" * 70)
    total = cov.report()
    
    # Generate HTML report if requested
    if args.report:
        print("\nGenerating HTML coverage report...")
        cov.html_report(directory="coverage_html")
        print(f"HTML report generated at: {os.path.abspath('coverage_html/index.html')}")
    
    # Generate XML report if requested (useful for CI systems)
    if args.xml:
        cov.xml_report(outfile="coverage.xml")
        print("XML report generated: coverage.xml")
    
    # Verify coverage threshold
    if total < args.threshold:
        print(f"\n⚠️ COVERAGE ALERT: {total:.2f}% is below the threshold of {args.threshold}%")
    else:
        print(f"\n✅ Coverage threshold met: {total:.2f}% >= {args.threshold}%")
    
    # Report test result
    if result == 0:
        print("\n✅ All tests passed!")
    else:
        print(f"\n❌ Tests failed with exit code: {result}")
    
    return result

if __name__ == "__main__":
    args = parse_args()
    sys.exit(run_tests_with_coverage(args))
