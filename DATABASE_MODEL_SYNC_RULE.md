# DATABASE MODEL SYNC RULE
## Engineering Standard for SUNO Project

**Status:** MANDATORY
**Effective Date:** 2026-05-02
**Last Updated:** 2026-05-02

---

## THE RULE

**Every ORM model column definition MUST exactly match the actual database column type.**

If the database has `VARCHAR`, the model MUST be `String`.
If the database has `INTEGER`, the model MUST be `Integer`.
If the database has `ENUM`, the model MUST be `SQLEnum`.

**No assumptions. No wishes. Match reality.**

---

## WHY THIS MATTERS

**Real incident from May 2, 2026:**

- Database: `tiers.name` = `VARCHAR`
- ORM Model: `Tier.name = Column(SQLEnum(TierName))`
- Result: SQLAlchemy coerced strings to enum type
- Error: `operator does not exist: character varying = tiername`
- Cost: 6+ hours of debugging

**Root cause:** Model declared what we *wanted*, not what was *actually there*.

---

## THE CHECKLIST

Before committing ANY model changes:

- [ ] **1. Check actual database schema**
  ```sql
  \d tiers;  -- PostgreSQL
  -- or inspect in GUI tool
  ```

- [ ] **2. Read the column type exactly**
  - `character varying(X)` → use `String`
  - `integer` → use `Integer`
  - `boolean` → use `Boolean`
  - `timestamp` → use `DateTime`
  - `jsonb` → use `JSON`
  - `enum type_name` → use `SQLEnum(EnumClass)`

- [ ] **3. Update ORM model to match**
  ```python
  # WRONG - mismatches database
  name = Column(SQLEnum(TierName))  # DB is VARCHAR!

  # CORRECT - matches database
  name = Column(String)
  ```

- [ ] **4. Test in code (no migration needed for type mismatch fixes)**
  ```python
  # Use exact types in queries
  where(Tier.name == "starter")  # String vs enum
  ```

- [ ] **5. Verify in production logs after deployment**
  ```
  Log message shows: GIT COMMIT: [hash]
  Register test succeeds with 200/409 (not 500)
  ```

---

## DEPLOYMENT VERIFICATION

After every deployment to Render:

- [ ] Check startup logs for: `STARTUP: GIT COMMIT: [hash]`
- [ ] Verify commit hash matches latest GitHub commit
- [ ] Test the affected endpoint
- [ ] Confirm no type mismatch errors in response

**NEVER assume "Restart Service" is enough for critical fixes.**

Use: **"Clear build cache & deploy"** on Render for dependency/type changes.

---

## WHAT NOT TO DO

❌ **Don't declare what you wish the database had:**
```python
# Database is VARCHAR but you want to force Enum
name = Column(SQLEnum(TierName))  # WRONG
```

❌ **Don't use type casting as a workaround:**
```python
# This masks the real problem
where(cast(Tier.name, String) == value)
```

❌ **Don't skip migrations if schema AND model don't match:**
```python
# If you change model, you may need a migration
# Check with your DBA/migration lead
```

❌ **Don't assume deployment worked without verification:**
```python
# Always check logs
# Always test
# Always verify commit hash
```

---

## CODE REVIEW CHECKLIST

When reviewing PRs with model changes:

1. **Ask:** "Does this ORM definition match the actual database column type?"
2. **Verify:** Check the migration file or database schema
3. **Test:** Run a test query to confirm no type coercion errors
4. **Approve:** Only if model = database reality

---

## ESCALATION

If you find a model/database mismatch:

1. **Do NOT commit** the model as-is
2. **Document** the mismatch clearly
3. **Decide:** Does database need to change, or model?
4. **Create migration** if database changes needed
5. **Update model** to match final schema
6. **Test** before merging

---

## EXAMPLES

### ❌ WRONG (from real incident)

```python
# Database: CREATE TABLE tiers (id INTEGER, name VARCHAR(50), ...)
class Tier(Base):
    __tablename__ = "tiers"
    id = Column(Integer, primary_key=True)
    name = Column(SQLEnum(TierName))  # ❌ VARCHAR in DB, Enum in model!
```

**Query fails:**
```python
where(Tier.name == TierName.STARTER)  # Type coercion error
```

### ✅ CORRECT

```python
# Database: CREATE TABLE tiers (id INTEGER, name VARCHAR(50), ...)
class Tier(Base):
    __tablename__ = "tiers"
    id = Column(Integer, primary_key=True)
    name = Column(String)  # ✅ Matches VARCHAR in database
```

**Query works:**
```python
where(Tier.name == "starter")  # Pure string comparison
```

---

## QUESTIONS?

If you're unsure about a column type:

1. Check the migration file (alembic/versions/*.py)
2. Query the database directly
3. Ask in code review
4. Document the decision

---

## SIGN-OFF

This rule is **NON-NEGOTIABLE** for SUNO codebase.

Every developer must read and understand this before committing model changes.

**Violations caught in code review will be rejected.**

---

*Created: 2026-05-02*
*Author: Engineering Team*
*Lessons learned from 6-hour debugging session*
