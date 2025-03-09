# Print colored output for better readability
function Write-ColorOutput($ForegroundColor) {
    $fc = $host.UI.RawUI.ForegroundColor
    $host.UI.RawUI.ForegroundColor = $ForegroundColor
    if ($args) {
        Write-Output $args
    }
    else {
        $input | Write-Output
    }
    $host.UI.RawUI.ForegroundColor = $fc
}

Write-ColorOutput Green "Starting Sentient Inbox setup..."

# Ensure Python 3.x is available
try {
    $pythonVersion = python --version
    if (-not $pythonVersion.Contains("Python 3")) {
        Write-ColorOutput Red "Python 3 is not installed. Please install Python 3.8 or newer."
        exit 1
    }
} catch {
    Write-ColorOutput Red "Python 3 is not installed or not in PATH. Please install Python 3.8 or newer."
    exit 1
}

# Create and activate virtual environment
Write-ColorOutput Yellow "Creating Python virtual environment..."
if (Test-Path -Path "venv") {
    Write-Output "Virtual environment already exists, skipping creation"
} else {
    python -m venv venv
}

# Activate virtual environment
Write-ColorOutput Yellow "Activating virtual environment..."
& .\venv\Scripts\Activate.ps1

# Install dependencies
Write-ColorOutput Yellow "Installing dependencies from requirements.txt..."
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# Create required directories
Write-ColorOutput Yellow "Creating necessary directories..."
New-Item -ItemType Directory -Force -Path data\secure\backups
New-Item -ItemType Directory -Force -Path data\metrics
New-Item -ItemType Directory -Force -Path data\config
New-Item -ItemType Directory -Force -Path data\cache
New-Item -ItemType Directory -Force -Path logs

# Create environment file template if it doesn't exist
if (-not (Test-Path -Path ".env")) {
    Write-ColorOutput Yellow "Creating .env template file..."
    @"
# API Keys
GROQ_API_KEY=your_groq_api_key_here
DEEPSEEK_API_KEY=your_deepseek_api_key_here
OPENAI_API_KEY=your_openai_api_key_here

# OAuth settings for Gmail
# Note: You'll need to create OAuth credentials in Google Cloud Console
# and download client_secret.json file to the project root

# Application settings
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=DEBUG
"@ | Out-File -FilePath ".env" -Encoding utf8
    Write-ColorOutput Green ".env template created. Please edit it with your actual API keys."
} else {
    Write-Output ".env file already exists, skipping creation"
}

# Check for client_secret.json for Gmail OAuth
if (-not (Test-Path -Path "client_secret.json")) {
    Write-ColorOutput Yellow "NOTICE: client_secret.json file for Gmail OAuth is missing."
    Write-Output "You'll need to create OAuth credentials in Google Cloud Console and"
    Write-Output "download the client_secret.json file to the project root before running the application."
}

Write-ColorOutput Green "Setup complete!"
Write-ColorOutput Green "To activate the virtual environment in the future, run:"
Write-Output "  .\venv\Scripts\Activate.ps1"
Write-ColorOutput Green "To run the API server:"
Write-Output "  python run_api.py --env development --reload"
Write-ColorOutput Green "To process emails as a batch job:"
Write-Output "  python main.py"