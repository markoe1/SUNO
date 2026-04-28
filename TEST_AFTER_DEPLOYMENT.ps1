# Test POST /api/clips/generate after Render deployment (PowerShell)
# This command matches the exact auth/header format expected by the API

# BEFORE RUNNING:
# 1. Replace <your_email> with a valid user email that exists in the database
# 2. Replace <valid-campaign-uuid> with an actual campaign UUID from the database

$API_URL = "https://suno-api-production.onrender.com"
$USER_EMAIL = "your_email@example.com"  # CHANGE THIS
$CAMPAIGN_UUID = "12345678-1234-1234-1234-123456789012"  # CHANGE THIS

Write-Host "==================================" -ForegroundColor Cyan
Write-Host "Testing POST /api/clips/generate" -ForegroundColor Cyan
Write-Host "==================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "API: $API_URL"
Write-Host "User: $USER_EMAIL"
Write-Host "Campaign: $CAMPAIGN_UUID"
Write-Host ""

$body = @{
    campaign_id       = $CAMPAIGN_UUID
    target_platforms  = @("tiktok", "instagram", "youtube")
    tone              = "energetic"
} | ConvertTo-Json

$response = Invoke-WebRequest -Uri "$API_URL/api/clips/generate" `
    -Method POST `
    -Headers @{
        "Content-Type"  = "application/json"
        "X-User-Email"  = $USER_EMAIL
    } `
    -Body $body `
    -SkipHttpErrorCheck

Write-Host "HTTP Status: $($response.StatusCode)" -ForegroundColor $(
    if ($response.StatusCode -eq 201) { "Green" }
    elseif ($response.StatusCode -eq 500) { "Red" }
    else { "Yellow" }
)

Write-Host ""
Write-Host "Response Body:"
Write-Host $response.Content
Write-Host ""
Write-Host "==================================" -ForegroundColor Cyan
Write-Host "Expected Results:" -ForegroundColor Cyan
Write-Host "  • HTTP Status: 201 (Created)" -ForegroundColor Green
Write-Host "  • No 'Campaign.active' error" -ForegroundColor Green
Write-Host "  • Response: {""clip_id"": ..., ""status"": ..., ""job_id"": ...}" -ForegroundColor Green
Write-Host "==================================" -ForegroundColor Cyan
