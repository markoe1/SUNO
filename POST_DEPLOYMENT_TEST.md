# POST-DEPLOYMENT TEST PLAN

**After API redeploys on Render, test the fix with this command:**

---

## **The Test**

### PowerShell (Windows)
```powershell
$API_URL = "https://suno-api-production.onrender.com"
$USER_EMAIL = "your_email@example.com"      # CHANGE: Use a real user email
$CAMPAIGN_UUID = "actual-campaign-uuid"      # CHANGE: Use a real campaign UUID

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

Write-Host "Status: $($response.StatusCode)"
Write-Host $response.Content
```

### Bash (macOS/Linux)
```bash
curl -X POST https://suno-api-production.onrender.com/api/clips/generate \
  -H "Content-Type: application/json" \
  -H "X-User-Email: your_email@example.com" \
  -d '{
    "campaign_id": "actual-campaign-uuid",
    "target_platforms": ["tiktok", "instagram", "youtube"],
    "tone": "energetic"
  }' \
  -w "\nStatus: %{http_code}\n"
```

---

## **Authentication Details**

**Required Header:** `X-User-Email`
- Must be a valid email in the database
- User must have PENDING or ACTIVE membership
- Example: `X-User-Email: user@example.com`

**Request Body:**
```json
{
  "campaign_id": "uuid-here",
  "target_platforms": ["tiktok", "instagram", "youtube"],
  "tone": "energetic"
}
```

---

## **Expected Result on Success**

**HTTP Status: 201 Created**

```json
{
  "clip_id": 123,
  "status": "needs_review",
  "job_id": "suno-clips:job-1234"
}
```

**Key Signs the Fix Worked:**
- ✅ Status 201 (not 500)
- ✅ No `AttributeError: Campaign has no attribute 'active'`
- ✅ No mention of `.active` field in error message
- ✅ Returns proper clip_id, status, job_id

---

## **If Still Getting 500 Error**

Check Render logs for:
1. **Different error message** (what's the new error?)
2. **Stack trace** (where is it failing?)
3. **Previous error?** (still Campaign.active?)

If still Campaign.active error:
- Verify the commits were deployed: `git log --oneline | head -3`
- Confirm API restarted (check Render deployment log)
- Check that the fix is in the running code

---

## **Test Data You'll Need**

From your database, get:
1. **Valid user email** - Must exist in `users` table
   ```sql
   SELECT email FROM users LIMIT 1;
   ```

2. **Valid campaign UUID** - Must exist and be available
   ```sql
   SELECT id, name, available FROM campaigns WHERE available = true LIMIT 1;
   ```

---

## **Success Metrics**

| Metric | Expected |
|--------|----------|
| HTTP Status | 201 |
| No 500 error | Yes |
| No `Campaign.active` error | Yes |
| Response has clip_id | Yes |
| Response has job_id | Yes |
| Database: Clip created | Yes (check clips table) |
| Job queued | Yes (check Redis queue) |

---

## **Next Steps After Test**

✅ If **201 Success**:
- System is live end-to-end
- Deploy worker (can be after)
- Monitor logs for any other issues

❌ If **Still 500**:
- Check Render logs for exact error message
- Verify commit deployed: `8f204d0`
- Run local test to reproduce
- Escalate with full error trace

---

## **Files Provided**

- `TEST_AFTER_DEPLOYMENT.sh` - Bash version
- `TEST_AFTER_DEPLOYMENT.ps1` - PowerShell version
- This file - `POST_DEPLOYMENT_TEST.md`

Just update the email and campaign UUID, then run the test!
