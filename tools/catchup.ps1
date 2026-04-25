param(
    [int]$Commits = 15
)

Write-Host "=== README (top) ===" -ForegroundColor Cyan
Get-Content -Path "$PSScriptRoot\..\README.md" -TotalCount 60

Write-Host "`n=== Recent commits ===" -ForegroundColor Cyan
git --no-pager log --oneline -n $Commits

Write-Host "`n=== Decisions ===" -ForegroundColor Cyan
if (Test-Path "$PSScriptRoot\..\DECISIONS.md") { Get-Content "$PSScriptRoot\..\DECISIONS.md" }

Write-Host "`n=== Latest session notes ===" -ForegroundColor Cyan
$latest = Get-ChildItem "$PSScriptRoot\..\PROJECT_NOTES" -ErrorAction SilentlyContinue | Sort-Object Name -Descending | Select-Object -First 1
if ($latest) { Get-Content $latest.FullName -TotalCount 120 } else { Write-Host "No session notes yet." }