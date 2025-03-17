# PowerShell script to prepare the testing environment and run comprehensive test coverage

# Ensure needed Python packages are installed
Write-Host "Installing required testing dependencies..." -ForegroundColor Green
pip install -r test-requirements.txt

# Check the import of specific packages we need
if (-not (python -c "import sqlalchemy" 2>$null)) {
    Write-Host "Installing SQLAlchemy..." -ForegroundColor Yellow
    pip install sqlalchemy
}

if (-not (python -c "import cryptography" 2>$null)) {
    Write-Host "Installing Cryptography..." -ForegroundColor Yellow
    pip install cryptography
}

# Run individual module tests first to identify specific issues
Write-Host "`nRunning storage module tests..." -ForegroundColor Green
python universal_test_runner.py tests/unit/storage --module storage --threshold 0

Write-Host "`nRunning authentication module tests..." -ForegroundColor Green
python universal_test_runner.py api/tests/unit/test_auth.py api/tests/unit/test_oauth_providers.py --module auth --threshold 0

# Run all tests and generate a comprehensive coverage report
Write-Host "`nRunning complete test suite for coverage assessment..." -ForegroundColor Green
python universal_test_runner.py --module all --threshold 0 --report --xml

Write-Host "`nTest coverage assessment complete. View the HTML report at 'coverage_html/index.html'" -ForegroundColor Cyan
Write-Host "Follow the guidance in test_coverage_plan.md to reach 100% coverage." -ForegroundColor Cyan
