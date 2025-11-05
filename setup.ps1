# Setup script for altitude-maps project
# This script sets up and activates the Python 3.13 virtual environment

Write-Host "Setting up altitude-maps environment..." -ForegroundColor Green

# Check if Python 3.13 is installed
Write-Host "Checking for Python 3.13..." -ForegroundColor Yellow
$python313 = & py -3.13 --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Python 3.13 not found. Installing via winget..." -ForegroundColor Yellow
    winget install Python.Python.3.13 --silent
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Failed to install Python 3.13. Please install manually from python.org" -ForegroundColor Red
        exit 1
    }
    Write-Host "Python 3.13 installed successfully!" -ForegroundColor Green
}

# Check if venv exists
if (-Not (Test-Path "venv")) {
    Write-Host "Creating Python 3.13 virtual environment..." -ForegroundColor Yellow
    py -3.13 -m venv venv
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Failed to create virtual environment" -ForegroundColor Red
        exit 1
    }
}

# Activate virtual environment
Write-Host "Activating virtual environment..." -ForegroundColor Yellow
& ".\venv\Scripts\Activate.ps1"

# Upgrade pip
Write-Host "Upgrading pip..." -ForegroundColor Yellow
python -m pip install --upgrade pip

# Install requirements if they exist
if (Test-Path "requirements.txt") {
    Write-Host "Installing dependencies..." -ForegroundColor Yellow
    pip install -r requirements.txt
}

Write-Host "Setup complete! Virtual environment is activated." -ForegroundColor Green
Write-Host "Python version:" -ForegroundColor Cyan
python --version

