#!/bin/bash
# Test POST /api/clips/generate after Render deployment
# This command matches the exact auth/header format expected by the API

# BEFORE RUNNING:
# 1. Replace <your_email> with a valid user email that exists in the database
# 2. Replace <valid-campaign-uuid> with an actual campaign UUID from the database
# 3. Update the Render API URL if different

API_URL="https://suno-api-production.onrender.com"
USER_EMAIL="your_email@example.com"  # CHANGE THIS
CAMPAIGN_UUID="12345678-1234-1234-1234-123456789012"  # CHANGE THIS

echo "=================================="
echo "Testing POST /api/clips/generate"
echo "=================================="
echo ""
echo "API: $API_URL"
echo "User: $USER_EMAIL"
echo "Campaign: $CAMPAIGN_UUID"
echo ""

curl -X POST "$API_URL/api/clips/generate" \
  -H "Content-Type: application/json" \
  -H "X-User-Email: $USER_EMAIL" \
  -d "{
    \"campaign_id\": \"$CAMPAIGN_UUID\",
    \"target_platforms\": [\"tiktok\", \"instagram\", \"youtube\"],
    \"tone\": \"energetic\"
  }" \
  -w "\nHTTP Status: %{http_code}\n"

echo ""
echo "=================================="
echo "Expected Results:"
echo "  • HTTP Status: 201 (Created)"
echo "  • No 'Campaign.active' error"
echo "  • Response: {\"clip_id\": ..., \"status\": ..., \"job_id\": ...}"
echo "=================================="
