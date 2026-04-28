# 🐛 Bug Report & Implementation Plan - Hotel Booking Chatbot

## Executive Summary
Found **8 critical/high severity bugs** that prevent the application from running. This document outlines each bug and the step-by-step fix plan.

---

## 🔴 CRITICAL ISSUES (Must Fix First)

### Bug #1: Git Merge Conflicts in `coordinates.py`
**Severity:** CRITICAL  
**Status:** ❌ BLOCKING  
**Description:** File contains unresolved merge conflict markers from git merge.

**Evidence:**
```
<<<<<<< HEAD
def get_coordinates(city_name, api_key):
    ...
=======
def get_coordinates(city, api_key):
    ...
>>>>>>> origin/chatbot-ui
```

**Impact:** Python cannot parse the file, application crashes on import  
**Fix:** Resolve merge conflict by keeping the best version and removing all markers

---

### Bug #2: Git Merge Conflicts in `src/hotel_search.py`
**Severity:** CRITICAL  
**Status:** ❌ BLOCKING  
**Description:** File contains multiple unresolved merge conflict markers.

**Evidence:**
```
<<<<<<< HEAD
import requests
from datetime import datetime, timedelta
=======
# src/hotel_search.py
...
>>>>>>> origin/chatbot-ui
```

**Impact:** Python cannot parse the file, application crashes on import  
**Fix:** Resolve merge conflict intelligently combining both versions

---

### Bug #3: Corrupted `requirements.txt`
**Severity:** CRITICAL  
**Status:** ❌ BLOCKING  
**Description:** File is encoded in UTF-16 binary format instead of plain text.

**Evidence:** File shows binary data: `00 66 00 3d 00 3d 00...` (UTF-16 encoding)

**Impact:** `pip install -r requirements.txt` will fail  
**Fix:** Recreate the file as plain UTF-8 text with proper Python dependencies

---

## 🟠 HIGH SEVERITY ISSUES

### Bug #4: Environment Variable Naming Mismatch
**Severity:** HIGH  
**Status:** ⚠️ Configuration Issue  
**Description:** Code and documentation use different environment variable names.

**Mismatch:**
- Code expects: `OPENCAGE_KEY`, `RAPIDAPI_KEY`, `RAPIDAPI_HOST`
- README mentions: `OPENCAGE_API_KEY`, `BOOKING_API_KEY`

**Impact:** Users follow README but code fails with missing keys  
**File:** `app.py` line 14-16, `main.py` line 13-15

**Fix:** 
1. Update README.md with correct variable names
2. Create `.env.example` with correct format
3. Add comments explaining where to get each key

---

### Bug #5: Missing Error Handling in `src/coordinates.py`
**Severity:** HIGH  
**Status:** ⚠️ Runtime Risk  
**Description:** No try-catch blocks around API calls. Network errors crash the app.

**Vulnerable Code:**
```python
def get_coordinates(city, api_key):
    response = requests.get(url)  # No error handling!
    data = response.json()  # Fails if response is not JSON
```

**Impact:** Any network error or invalid response crashes the app  
**Fix:** Add comprehensive error handling with meaningful error messages

---

### Bug #6: Missing Error Handling in `src/hotel_search.py`
**Severity:** HIGH  
**Status:** ⚠️ Runtime Risk  
**Description:** Incomplete error handling around API calls.

**Issues:**
- No handling for connection timeouts
- Limited validation of response structure
- Error messages not informative

**Impact:** API failures crash the app  
**Fix:** Add comprehensive try-catch blocks and validation

---

## 🟡 MEDIUM SEVERITY ISSUES

### Bug #7: Duplicate Imports in `main.py`
**Severity:** MEDIUM  
**Status:** ⚠️ Code Quality  
**Description:** `from datetime import datetime, timedelta` appears twice (lines 3 and 7).

**Code:**
```python
from datetime import datetime, timedelta  # Line 3
...
from datetime import datetime, timedelta  # Line 7 - DUPLICATE!
```

**Impact:** Wasted memory, confusing to readers, poor code quality  
**Fix:** Remove one duplicate import

---

### Bug #8: Missing `.env` and `.env.example` Files
**Severity:** MEDIUM  
**Status:** ⚠️ Configuration  
**Description:** No example configuration file for users to reference.

**Impact:** Users don't know what API keys to set up  
**Fix:** Create `.env.example` with template values and instructions

---

### Bug #9: Code Duplication (app.py vs main.py)
**Severity:** MEDIUM  
**Status:** ⚠️ Maintenance Risk  
**Description:** Similar logic exists in both files - DRY principle violated.

**Functions duplicated:**
- `apply_filters()`
- `get_hotel_details()`
- `format_hotel_response()`

**Impact:** Bug fixes need to be applied in multiple places  
**Fix:** Refactor to use shared functions or consolidate code

---

## 🟢 LOW SEVERITY ISSUES

### Bug #10: Regex Pattern Doesn't Support Decimal Prices
**Severity:** LOW  
**Status:** ⚠️ Feature Limitation  
**Description:** Price regex only matches integers, not decimals.

**Current Pattern:**
```python
r"price between (\d+) and (\d+)"  # Matches: "100 and 200"
                                    # Fails: "100.50 and 200.75"
```

**Impact:** Users can't filter by decimal prices  
**Fix:** Update regex to: `r"price between ([\d.]+) and ([\d.]+)"`

---

## 📋 IMPLEMENTATION PRIORITY

| Priority | Bug ID | Issue | Time Est. |
|----------|--------|-------|-----------|
| 🔴 P0 | #1 | Merge conflicts coordinates.py | 5 min |
| 🔴 P0 | #2 | Merge conflicts hotel_search.py | 10 min |
| 🔴 P0 | #3 | Restore requirements.txt | 5 min |
| 🟠 P1 | #4 | Environment variable mismatch | 10 min |
| 🟠 P1 | #5 | Error handling coordinates.py | 15 min |
| 🟠 P1 | #6 | Error handling hotel_search.py | 15 min |
| 🟡 P2 | #7 | Duplicate imports | 2 min |
| 🟡 P2 | #8 | Missing .env files | 10 min |
| 🟡 P2 | #9 | Code duplication | 20 min |
| 🟢 P3 | #10 | Regex pattern | 5 min |

**Total Estimated Time:** ~1.5 hours

---

## 🛠️ Next Steps

1. **Run the fix implementation** to resolve all issues automatically
2. **Test the application** to ensure it runs without errors
3. **Verify all features work** with proper error handling
4. **Commit changes** to git with clear messages

---

## 📞 Questions?
This report identifies all discovered bugs. Ready to implement fixes whenever you give the go-ahead!
