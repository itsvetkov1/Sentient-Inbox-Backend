# run_test.py - Place in your project root directory
import sys
import os
from pathlib import Path

# Add project root and src to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

# Create mock modules for the problematic imports
class FakeModule:
    pass

class EmailProcessor:
    pass

class EmailTopic:
    pass

class EmailClassifier:
    pass

# Set up mock modules before imports occur
sys.modules['email_processing'] = FakeModule()
sys.modules['email_processing'].EmailProcessor = EmailProcessor

sys.modules['email_processing.classification'] = FakeModule()
sys.modules['email_processing.classification'].EmailTopic = EmailTopic
sys.modules['email_processing.classification'].EmailClassifier = EmailClassifier

# Run pytest programmatically
if __name__ == "__main__":
    import pytest
    
    # Default test file if none provided
    test_path = "tests/component_unit_tests.py"
    
    # Allow for command-line arguments to specify which test to run
    if len(sys.argv) > 1:
        test_path = sys.argv[1]
    
    # Run pytest with the specified test
    print(f"Running test: {test_path}")
    result = pytest.main([test_path, "-v", "--import-mode=importlib"])
    
    # Report the result
    if result == 0:
        print("\nAll tests passed!")
    else:
        print(f"\nTests failed with exit code: {result}")