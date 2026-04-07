# Snov Selector Fix Guide

## Problem
The scraper is running but not finding data because CSS selectors don't match the current Snov website structure.

## Solution Steps

### Step 1: Run the Selector Inspector
This script will automatically inspect the Snov website and identify the correct selectors.

```bash
cd "c:\Users\Admin\Desktop\MOTM Diagnose\Snov Tool\updated_snov\new_flask"
python selector_inspector.py
```

**What it does:**
- Opens Snov.io in a Playwright browser
- Inspects the actual DOM structure
- Tests different CSS/XPath selectors
- Shows which selectors work (✓ FOUND)
- Saves detailed report to `snov_selector_report.json`

### Step 2: Review the Output
The script will show:
```
Table Rows:
   1. css=tbody tr                    ✓ FOUND         (25 found)
   2. css=tr                          ✓ FOUND         (40 found)

Email Cells:
   1. css=td[class*='email']          ✓ FOUND         (25 found)
   2. css=[class*='email']            ✓ FOUND         (25 found)
```

Note which selectors have ✓ FOUND status.

### Step 3: Update finalcode.py
The code has been updated with **flexible selector matching** that automatically tries multiple selectors. These changes are:

1. **Helper Functions** (already added):
   - `find_element_flexible()` - Tries multiple selectors
   - `find_elements_flexible()` - Tries multiple selectors for multiple elements

2. **Flexible Selectors** (already updated):
   - Table rows: Tries multiple row selectors
   - Email cells: Tries multiple email cell selectors
   - Action buttons: Tries multiple button selectors
   - "Add to list" buttons: Tries multiple button selectors

### Step 4: Run the Scraper Again
```bash
python finalcode.py
```

The scraper will now:
- Try multiple selector combinations
- Log which selectors it's using
- Provide detailed debugging output

### Step 5: Monitor the Console Output
Watch for these messages:
```
✓ Using email selector: css=td[class*='email']
Found 25 prospect rows using flexible selector
EMAIL FOUND - user@example.com for manager
```

## If Selectors Still Don't Work

### Option 1: Manual Browser Inspection
1. Open Snov.io in your browser
2. Search for prospects
3. Right-click on an email cell → Inspect
4. Note the `class` attribute
5. Update the selector list in `finalcode.py`

**Example:** If the email cell has `class="prospect-email"`, use:
```python
"css=td.prospect-email"
"css=[class*='prospect-email']"
```

### Option 2: Check the Debug Screenshot
When selectors fail, the script saves a screenshot:
```
debug_page_[SESSION_ID].png
```
Open this to see what's actually on the page.

### Option 3: Modify the Selector List
Edit `finalcode.py` and update the selector lists:

**For email cells** (around line 879):
```python
email_cell_selectors = [
    "css=td.YOUR_ACTUAL_EMAIL_CLASS",  # Add your class here
    "css=td[class*='email']",
    "css=td.email",
]
```

**For table rows** (around line 720):
```python
row_selectors = [
    "css=tbody tr.YOUR_ACTUAL_ROW_CLASS",  # Add your class here
    "css=tbody tr",
    "css=tr",
]
```

## Troubleshooting

### No rows found
- Check if page is loading correctly
- Verify cookies are valid
- Check if Snov website layout changed

### Rows found but no emails
- Email selector doesn't match
- Emails might be in a different cell structure
- Check `debug_page_*.png` screenshot

### Buttons not clickable
- Button selector might be wrong
- Button might be in a different location
- Check button text and classes

## Key Improvements Made

The code now includes:
1. **Flexible selector matching** - Tries multiple selectors automatically
2. **Better error logging** - Shows which selectors work
3. **Diagnostic screenshots** - Saves page screenshots on failure
4. **Alternative selectors** - Falls back to more generic selectors

This means even if some selectors are wrong, others should work!

## Files Modified

- `finalcode.py` - Added flexible selector functions and updated all element queries
- `selector_inspector.py` - New diagnostic tool (created)
- `SELECTOR_FIX_GUIDE.md` - This file

## Quick Summary

```
1. Run: python selector_inspector.py
2. Check output for ✓ FOUND selectors
3. Run scraper: python finalcode.py
4. Monitor console for selector matches
5. If issues persist, manually inspect website and update selectors
```

Good luck! 🚀
