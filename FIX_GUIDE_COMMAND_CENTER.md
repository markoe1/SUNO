# CommandCenter 500 Error Fix Guide

**Status:** Analysis Complete - Ready to Apply
**Issue:** HTTP Response Double-Read in `app/api/sentinel/route.ts`
**Pattern:** Same as SUNO fix

---

## The Issue in CommandCenter

**File:** `app/api/sentinel/route.ts`
**Lines:** 79-88

### Broken Code Pattern

```typescript
// BROKEN - Lines 79-88
const [serviceRes, deploysRes] = await Promise.all([
  fetch(SERVICE_API_URL),
  fetch(DEPLOY_API_URL),
]);

// Line 79-80: Try to read response
if (serviceRes?.ok) {
  const svc = await serviceRes.json();  // First read
}

// Line 87-88: Try to read same response again
if (deploysRes?.ok) {
  const deploys = await deploysRes.json();  // ERROR: Stream consumed
}
```

### Why This Breaks

**JavaScript/Node.js fetch() response behavior:**
- Response body is a stream that can only be read once
- `.json()` method consumes the stream
- Calling `.json()` twice fails on the second call

**Wrapped in `.catch(() => null)`:**
- The error is silently caught
- Returns null instead of data
- Downstream code receives null, returns 500 error

---

## The Fix

### Step 1: Store Response Text First

```typescript
const [serviceRes, deploysRes] = await Promise.all([
  fetch(SERVICE_API_URL),
  fetch(DEPLOY_API_URL),
]);

// Read response bodies once
const serviceText = serviceRes?.ok ? await serviceRes.text() : null;
const deploysText = deploysRes?.ok ? await deploysRes.text() : null;

// Parse JSON from stored text
let svc = null;
if (serviceText) {
  try {
    svc = JSON.parse(serviceText);
  } catch (e) {
    console.error("Failed to parse service response:", e);
  }
}

let deploys = null;
if (deploysText) {
  try {
    deploys = JSON.parse(deploysText);
  } catch (e) {
    console.error("Failed to parse deploys response:", e);
  }
}
```

### Step 2: Clone Response for Multiple Reads

**Alternative approach (if cloning is available):**

```typescript
const [serviceRes, deploysRes] = await Promise.all([
  fetch(SERVICE_API_URL),
  fetch(DEPLOY_API_URL),
]);

if (serviceRes?.ok) {
  const cloned = serviceRes.clone();  // Clone before reading
  const svc = await cloned.json();
}

if (deploysRes?.ok) {
  const cloned = deploysRes.clone();  // Clone before reading
  const deploys = await cloned.json();
}
```

### Step 3: Better Pattern - Read Once, Reuse

**RECOMMENDED - Cleaner approach:**

```typescript
const [serviceRes, deploysRes] = await Promise.all([
  fetch(SERVICE_API_URL),
  fetch(DEPLOY_API_URL),
]);

let svc = null;
let deploys = null;

try {
  // Read service response
  if (serviceRes?.ok) {
    const text = await serviceRes.text();
    svc = text ? JSON.parse(text) : null;
  }

  // Read deploys response
  if (deploysRes?.ok) {
    const text = await deploysRes.text();
    deploys = text ? JSON.parse(text) : null;
  }
} catch (error) {
  console.error("Failed to parse responses:", error);
  // Handle error appropriately
  return { status: "error", message: "Failed to fetch data" };
}

// Now both svc and deploys are safely available
```

---

## Implementation Steps

### For CommandCenter Team

1. **Locate the issue:**
   - File: `app/api/sentinel/route.ts`
   - Lines: ~79-88
   - Method: POST endpoint that fetches from Render API

2. **Apply the fix:**
   - Replace the parallel Promise.all() pattern
   - Use either cloning or read-once-store-variable approach
   - Improve error handling

3. **Test:**
   ```bash
   # Call the endpoint
   curl -X POST http://localhost:3000/api/sentinel \
     -H "Content-Type: application/json" \
     -d '{"action":"test"}'

   # Should return data instead of 500 error
   ```

4. **Verify:**
   - Check logs for "Failed to parse" messages
   - Ensure both svc and deploys data are present
   - Verify no 500 errors on subsequent calls

---

## JavaScript/Node.js Stream Rules

### What You Need to Know

```javascript
// ✗ WRONG - Reading stream twice
const res = await fetch(url);
const text = res.text();      // Consumes stream
const json = res.json();      // Fails - stream consumed

// ✓ CORRECT - Option 1: Read once to variable
const res = await fetch(url);
const text = await res.text();
const json = JSON.parse(text);

// ✓ CORRECT - Option 2: Use clone()
const res = await fetch(url);
const cloned = res.clone();
const json = await cloned.json();

// ✓ CORRECT - Option 3: Read as json directly
const res = await fetch(url);
const json = await res.json();
// (Don't call .text() after this)
```

### When This Pattern Appears

Search for these patterns in CommandCenter:

```typescript
// Pattern 1: Multiple .json() calls
response.json()
// ...
response.json()  // ERROR

// Pattern 2: .text() then .json()
response.text()
response.json()  // ERROR

// Pattern 3: Parallel fetches with .catch(() => null)
const [res1, res2] = await Promise.all([
  fetch(url1).catch(() => null),
  fetch(url2).catch(() => null),
]);
if (res1?.ok) { res1.json(); }  // May fail
if (res2?.ok) { res2.json(); }  // May fail
```

---

## Validation Checklist for CommandCenter

- [ ] Found the response double-read in `route.ts`
- [ ] Applied one of the three fix patterns
- [ ] Added try/catch around JSON.parse()
- [ ] Tested with curl/Postman
- [ ] Verified no 500 errors
- [ ] Checked logs for parse errors
- [ ] Deployed and monitored

---

## Root Cause Summary

**SUNO Issue:**
- File: `services/platform_oauth.py`
- Pattern: `response.text` then `response.json()`
- Cause: httpx async client streams can only be read once
- Status: ✓ FIXED

**CommandCenter Issue:**
- File: `app/api/sentinel/route.ts`
- Pattern: Parallel Promise.all() with multiple `.json()` calls
- Cause: Node.js fetch() response streams can only be read once
- Status: NOT YET FIXED (guidance provided above)

---

## Additional Resources

**Node.js Fetch API:**
- MDN: https://developer.mozilla.org/en-US/docs/Web/API/fetch
- Response.text(): Consumes body stream
- Response.json(): Consumes body stream
- Response.clone(): Creates deep copy

**httpx Documentation:**
- `.text`: Reads streaming response
- `.json()`: Parses JSON after text is read
- Stream consumption: Only once per response object

---

## Quick Reference: The Fix

| Issue | Solution |
|-------|----------|
| `response.json()` called twice | Use `response.clone()` or read `.text()` first |
| `response.text()` then `response.json()` | Call only `.json()`, or store `.text()` result |
| Multiple parallel fetches with reads | Read each response once, store in variable |
| Error in `.catch(() => null)` hiding real error | Remove the catch and handle properly |

---

## Summary

Both SUNO and CommandCenter have the same root cause:

1. **HTTP response bodies are streams**
2. **Streams can only be read once**
3. **Trying to read twice causes silent failures**
4. **Results in 500 errors to the user**

**SUNO:** Fixed in commit `295b26a`
**CommandCenter:** Apply fix from patterns above

This is a common mistake when working with async HTTP clients. The fix is always: read the stream once, store the value, reuse it.
