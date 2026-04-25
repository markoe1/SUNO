# VyroClipper Installation Script
# ================================
# Run this script to set up the entire system

Write-Host ""
Write-Host "======================================" -ForegroundColor Cyan
Write-Host "  VYROCLIPPER INSTALLATION" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

# Check Python
Write-Host "[1/5] Checking Python..." -ForegroundColor Yellow
$pythonVersion = python --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Python not found. Please install Python 3.9+ first." -ForegroundColor Red
    exit 1
}
Write-Host "Found: $pythonVersion" -ForegroundColor Green

# Create virtual environment
Write-Host ""
Write-Host "[2/5] Creating virtual environment..." -ForegroundColor Yellow
if (!(Test-Path "venv")) {
    python -m venv venv
    Write-Host "Virtual environment created" -ForegroundColor Green
} else {
    Write-Host "Virtual environment already exists" -ForegroundColor Green
}

# Activate and install dependencies
Write-Host ""
Write-Host "[3/5] Installing dependencies..." -ForegroundColor Yellow
& .\venv\Scripts\Activate.ps1
pip install -r requirements.txt --quiet
Write-Host "Dependencies installed" -ForegroundColor Green

# Install Playwright browsers
Write-Host ""
Write-Host "[4/5] Installing Playwright browsers..." -ForegroundColor Yellow
playwright install chromium
Write-Host "Browsers installed" -ForegroundColor Green

# Create .env file if not exists
Write-Host ""
Write-Host "[5/5] Setting up configuration..." -ForegroundColor Yellow
if (!(Test-Path ".env")) {
    Copy-Item ".env.template" ".env"
    Write-Host "Created .env file - PLEASE EDIT WITH YOUR CREDENTIALS" -ForegroundColor Yellow
} else {
    Write-Host ".env file already exists" -ForegroundColor Green
}

# Create directory structure
$dirs = @(
    "clips\inbox",
    "clips\ready",
    "clips\posted",
    "clips\failed",
    "logs",
    "data"
)

foreach ($dir in $dirs) {
    if (!(Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
}
Write-Host "Directory structure created" -ForegroundColor Green

Write-Host ""
Write-Host "======================================" -ForegroundColor Green
Write-Host "  INSTALLATION COMPLETE!" -ForegroundColor Green
Write-Host "======================================" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Edit .env with your credentials"
Write-Host "  2. Run: python main.py --mode test"
Write-Host "  3. Run: python main.py --mode run --count 5"
Write-Host ""
