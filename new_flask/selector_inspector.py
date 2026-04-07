"""
Selector Inspector for Snov.io
This script inspects the actual DOM structure of Snov and identifies
the correct CSS/XPath selectors for scraping.
"""

import asyncio
import json
from playwright.async_api import async_playwright

async def inspect_snov():
    """Inspect Snov.io DOM structure and find correct selectors"""

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(no_viewport=True)
        page = await context.new_page()

        print("=" * 80)
        print("SNOV.IO SELECTOR INSPECTOR")
        print("=" * 80)

        # Navigate to Snov
        print("\n1. Navigating to Snov.io...")
        await page.goto("https://app.snov.io/database-search/prospects")
        await asyncio.sleep(3)

        # Get page info
        title = await page.title()
        url = page.url
        print(f"   Page Title: {title}")
        print(f"   Page URL: {url}")

        # Check for table structures
        print("\n2. Checking for table/grid structures...")

        # Try to find various table elements
        searches = {
            "tbody rows": "tbody tr",
            "table rows (all)": "tr",
            "data rows (class)": "[class*='row']",
            "data rows (grid)": "[role='row']",
            "cells with email": "[class*='email']",
            "action cells": "[class*='action']",
            "buttons": "button",
            "inputs": "input[class*='filter']"
        }

        for label, selector in searches.items():
            try:
                count = await page.locator(selector).count()
                print(f"   {label:30} ('{selector}'): {count} found")
            except:
                print(f"   {label:30} ('{selector}'): ERROR")

        # Get all visible element classes
        print("\n3. Analyzing visible element classes...")
        classes_info = await page.evaluate("""
            () => {
                const info = {
                    tables: [],
                    rows: [],
                    cells: [],
                    buttons: [],
                    inputs: []
                };

                // Find tables
                document.querySelectorAll('table, [role="grid"], [role="table"]').forEach(el => {
                    info.tables.push({
                        tag: el.tagName,
                        classes: el.className,
                        childCount: el.children.length
                    });
                });

                // Find row-like elements
                document.querySelectorAll('tr, [class*="row"], [role="row"]').forEach(el => {
                    if (el.offsetHeight > 0) {  // Only visible
                        info.rows.push({
                            tag: el.tagName,
                            classes: el.className,
                            text: el.innerText.substring(0, 50)
                        });
                    }
                });

                // Find cell-like elements
                document.querySelectorAll('td, [class*="cell"], [class*="email"]').forEach(el => {
                    if (el.offsetHeight > 0) {  // Only visible
                        info.cells.push({
                            tag: el.tagName,
                            classes: el.className,
                            text: el.innerText.substring(0, 30)
                        });
                    }
                });

                // Find buttons
                document.querySelectorAll('button').forEach(el => {
                    if (el.offsetHeight > 0) {  // Only visible
                        info.buttons.push({
                            classes: el.className,
                            text: el.innerText.substring(0, 30)
                        });
                    }
                });

                // Find inputs
                document.querySelectorAll('input[type="text"], input[class*="filter"]').forEach(el => {
                    if (el.offsetHeight > 0) {  // Only visible
                        info.inputs.push({
                            classes: el.className,
                            placeholder: el.placeholder
                        });
                    }
                });

                return info;
            }
        """)

        print("\n   Tables found:")
        for t in classes_info['tables'][:3]:
            print(f"      {t['tag']}: {t['classes']}")

        print("\n   Rows found (first 3):")
        for r in classes_info['rows'][:3]:
            print(f"      {r['tag']}: {r['classes']}")

        print("\n   Cells found (first 3):")
        for c in classes_info['cells'][:3]:
            print(f"      {c['tag']}: {c['classes']}")

        print("\n   Buttons found (first 5):")
        for b in classes_info['buttons'][:5]:
            print(f"      {b['classes']}: {b['text']}")

        print("\n   Inputs found (first 3):")
        for i in classes_info['inputs'][:3]:
            print(f"      {i['classes']}: {i['placeholder']}")

        # Generate selector recommendations
        print("\n4. RECOMMENDED SELECTORS FOR YOUR CODE:")
        print("   " + "-" * 76)

        recommendations = {
            "Table Rows": [
                "css=tbody tr",
                "css=tr",
                "css=[class*='row']",
                "xpath=//tr"
            ],
            "Email Cells": [
                "css=td[class*='email']",
                "css=[class*='email']",
                "css=td",
                "xpath=//td[contains(@class, 'email')]"
            ],
            "Action Cells": [
                "css=td[class*='action']",
                "css=[class*='action']",
                "xpath=//td[contains(@class, 'action')]"
            ],
            "Buttons": [
                "xpath=//button[.//span[contains(text(), 'Add to list')]]",
                "xpath=//button[contains(text(), 'Add to list')]",
                "css=button:has-text('Add to list')"
            ]
        }

        for category, selectors in recommendations.items():
            print(f"\n   {category}:")
            for i, selector in enumerate(selectors, 1):
                try:
                    if "css=" in selector or "xpath=" not in selector:
                        count = await page.locator(selector).count()
                    else:
                        count = len(await page.query_selector_all(selector))
                    status = "✓ FOUND" if count > 0 else "✗ NOT FOUND"
                    print(f"      {i}. {selector:50} {status:12} ({count} found)")
                except:
                    print(f"      {i}. {selector:50} ERROR")

        # Save detailed info to file
        output_file = "snov_selector_report.json"
        with open(output_file, 'w') as f:
            json.dump(classes_info, f, indent=2)

        print(f"\n5. Detailed report saved to: {output_file}")

        print("\n" + "=" * 80)
        print("NEXT STEPS:")
        print("1. Review the selectors that show '✓ FOUND'")
        print("2. Update finalcode.py with the correct selectors")
        print("3. Run the scraper again")
        print("=" * 80)

        # Keep page open for manual inspection
        print("\nPage is open for manual inspection. Close the browser when done.")
        await asyncio.sleep(60)  # Wait 60 seconds for manual inspection

        await browser.close()

if __name__ == "__main__":
    asyncio.run(inspect_snov())
