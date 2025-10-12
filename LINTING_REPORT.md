# Backend Linting Report

**Overall Score: 3.63/10** 😬

## Issue Breakdown (Top Issues)

### Formatting Issues (Most Common)
- **C0303** (864) - Trailing whitespace
- **C0301** (542) - Line too long (>120 characters)
- **C0304** (98) - Missing final newline
- **C0321** (100) - Multiple statements on single line
- **W0311** (35) - Bad indentation

**Quick Fix:** Run `black` or `autopep8` to auto-format:
```bash
venv/bin/black backend/app/
# or
venv/bin/autopep8 --in-place --recursive backend/app/
```

### Model/Type Issues (Serious)
- **E1101** (396) - Module has no member (SQLAlchemy models not detected properly)
- **E1136** (17) - Value is unsubscriptable
- **E0611** (5) - No name in module

**Fix:** This is mostly a Pylint limitation with SQLAlchemy. Can be suppressed with:
```python
# pylint: disable=no-member
```

### Code Quality Issues
- **W1203** (297) - Use lazy % formatting in logging (f-strings in logs)
  ```python
  # Bad:
  logger.info(f"User {user_id} logged in")
  # Good:
  logger.info("User %s logged in", user_id)
  ```

- **W0611** (118) - Unused imports
- **W0718** (50) - Catching too general exception (catching `Exception`)
- **W0612** (20) - Unused variables
- **R0912** (35) - Too many branches (functions with too many if/else)

### Import Issues
- **C0411** (74) - Wrong import order (standard lib should come first)
- **C0413** (16) - Import should be at top of module
- **R0401** (11) - Cyclic imports (⚠️ This is concerning!)

### Structural Issues
- **R0801** (19) - Duplicate code
- **C0415** (9) - Import outside toplevel
- **R0911** (11) - Too many return statements

## Recommended Actions

### 1. Auto-Fix Formatting (Easy Win!)
```bash
# Fix most formatting issues automatically
venv/bin/black backend/app/

# Or use autopep8
venv/bin/autopep8 --in-place --aggressive --recursive backend/app/
```

This will fix:
- ✅ Trailing whitespace (864 issues)
- ✅ Line length (542 issues)
- ✅ Missing newlines (98 issues)
- ✅ Bad indentation (35 issues)

**Estimated improvement: +2-3 points**

### 2. Fix Logging F-Strings (Medium)
Search for `logger.info(f"` and replace with `logger.info("...", var)`
- 297 occurrences to fix

### 3. Remove Unused Imports (Easy)
Use VS Code's "Organize Imports" or run:
```bash
venv/bin/autoflake --remove-all-unused-imports --in-place --recursive backend/app/
```

### 4. Address Cyclic Imports (Important)
11 cyclic import warnings detected. This can cause runtime issues:
- `app.models` ↔ `app.models.character`
- `app.schemas` ↔ `app.schemas.shop`
- `app.services.room_service` ↔ `app.websocket_manager`
- Several in combat system

**Fix:** Restructure imports or use lazy imports

### 5. Suppress SQLAlchemy False Positives
Add to `.pylintrc` or settings:
```ini
[TYPECHECK]
generated-members=query,session,id,name,created_at,updated_at
```

## Quick Commands

### Run linter on specific module
```bash
venv/bin/pylint backend/app/main.py
venv/bin/pylint backend/app/websocket_manager.py
```

### Auto-fix formatting
```bash
venv/bin/black backend/app/
```

### Check for unused imports
```bash
venv/bin/pylint backend/app/ | grep "W0611"
```

### Generate full report
```bash
venv/bin/pylint backend/app/ --disable=C0111,C0103,W0212,R0903,R0913,R0914,R0915 --max-line-length=120 > pylint_report.txt
```

## Priority Fixes

### High Priority (Security/Stability)
1. ⚠️ Cyclic imports (11) - Can cause runtime issues
2. ⚠️ Broad exception catching (50) - May hide real errors

### Medium Priority (Code Quality)
3. Logging f-strings (297) - Performance issue
4. Unused imports (118) - Code cleanliness
5. Too many branches (35) - Refactoring needed

### Low Priority (Style)
6. Trailing whitespace (864) - Auto-fixable
7. Line length (542) - Auto-fixable
8. Import order (74) - Auto-fixable

## Next Steps

1. Run `black` to auto-fix formatting → **~1500 issues fixed**
2. Remove unused imports → **~118 issues fixed**
3. Fix logging statements → **~297 issues fixed**
4. Review cyclic imports → **Important for stability**

**Expected score after easy fixes: ~7-8/10** 🎯
