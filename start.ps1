# VyroClipper Quick Start
# =======================
# Simple launcher for common operations

param(
    [Parameter(Position=0)]
    [ValidateSet("test", "run", "daemon", "status", "dashboard", "fetch", "post")]
    [string]$Mode = "status",
    
    [Parameter()]
    [int]$Count = 0
)

# Activate virtual environment
if (Test-Path "venv\Scripts\Activate.ps1") {
    & .\venv\Scripts\Activate.ps1
}

# Build command
$cmd = "python main.py --mode $Mode"
if ($Count -gt 0) {
    $cmd += " --count $Count"
}

# Run
Write-Host "Running: $cmd" -ForegroundColor Cyan
Invoke-Expression $cmd
