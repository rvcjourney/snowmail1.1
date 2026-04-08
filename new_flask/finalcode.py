import asyncio
import threading
import ast
import re
import json
import pandas as pd
import time # For general time utilities, not for blocking sleeps in async code
import random
import string
from urllib.parse import urlparse
import heapq
from flask import Flask, request
from flask_cors import CORS
from flask_socketio import SocketIO, emit

# --- Playwright ASYNC Imports ---
from playwright.async_api import (
    async_playwright,
    TimeoutError as PlaywrightTimeoutError,
    Error as PlaywrightError,
    Browser, # For type hinting
    BrowserContext,
    Page,
    ElementHandle
)

# 1) FLASK + SOCKETIO SETUP 
app = Flask(__name__)
CORS(app)

socketio = SocketIO(
    app,
    async_mode="threading",      # Force Python threading in SocketIO
    cors_allowed_origins="*",
    engineio_options={'transports': ['polling']},
    ping_interval=25,            # 25 seconds — matches frontend pingInterval
    ping_timeout=60              # 60 seconds — drop truly dead connections
)

print("→ SocketIO async_mode =", socketio.async_mode) # Should print "threading"

# Store per‐client state here
clients_state = {}

# ─────────────────── CONFIGURATION CONSTANTS ───────────────────
DEFAULT_TIMEOUT_MSEC = 20000
SHORT_TIMEOUT_MSEC = 7000
LONG_TIMEOUT_MSEC = 25000
EMAIL_CELL_WAIT_TIMEOUT = 55
BUTTON_STATUS_WAIT_TIMEOUT = 25
INVALID_EMAIL_COUNT_THRESHOLD = 5
EMAIL_STABILITY_CONF_TIME = 1.0

class MySpecialError(Exception):
    """Raised when a special condition occurs or for cancellation."""
    pass

def get_domain(url):
    if not isinstance(url, str) or not url.strip():
        return ''
    raw = re.sub(r'[\x00-\x1F\x7F]', '', url).strip()
    if not re.match(r'^[a-zA-Z][a-zA-Z0-9+.\-]*://', raw):
        raw = 'http://' + raw
    parsed = urlparse(raw)
    domain = parsed.netloc.replace('www.', '').strip()
    return domain

async def check_cancel(state, description=""): # Made async if it needs to await asyncio.sleep(0)
    if state.get("cancel_process"):
        # Optionally, yield control to allow event loop to process other tasks
        # await asyncio.sleep(0) # Not strictly necessary here, but good for long checks
        raise MySpecialError(f"Process cancelled by user during: {description}")

async def find_element_flexible(page: Page, selectors_list: list):
    """
    Try multiple selectors until one works.
    selectors_list: List of selector strings to try in order
    Returns: ElementHandle if found, None otherwise
    """
    for selector in selectors_list:
        try:
            element = await page.query_selector(selector)
            if element:
                return element
        except Exception:
            continue
    return None

async def find_elements_flexible(page: Page, selectors_list: list):
    """
    Try multiple selectors until one works.
    selectors_list: List of selector strings to try in order
    Returns: List of ElementHandles
    """
    for selector in selectors_list:
        try:
            elements = await page.query_selector_all(selector)
            if elements and len(elements) > 0:
                return elements
        except Exception:
            continue
    return []

async def dismiss_onboarding_tooltip(page: Page):
    """
    Attempt multiple strategies to remove or dismiss onboarding tooltips/popups
    that block automated interactions (e.g., 'Got it' buttons, tour tooltips).
    Non-fatal: failures are logged but do not raise.
    """
    try:
        # 1) Click any prominent 'Got it' button
        btn = page.locator("button", has_text="Got it")
        await btn.first.wait_for(state="visible", timeout=3000)
        await btn.first.click(force=True)
        print("✅ Dismissed onboarding 'Got it' button")
        await asyncio.sleep(0.4)
        return
    except Exception:
        pass
    try:
        # 2) Close any close icons/buttons in known modal variants
        close_btns = page.locator("button[aria-label='Close'], button[title='Close'], .onboarding-close, .tour-close, div.BF-modal__close-icon-wrap")
        if await close_btns.count() > 0:
            for i in range(await close_btns.count()):
                try:
                    await close_btns.nth(i).click(force=True)
                except:
                    pass
        # 3) Remove by selector via JS for cosmetic hiding
        await page.evaluate("""() => {
            const sel = ['.onboarding-tooltip', '.tour-tooltip', '.onboarding', '.tour', '.snv-onboard', '.snov-tour', '.tippy-box', '.popover'];
            sel.forEach(s => document.querySelectorAll(s).forEach(e => e.remove()));
            // Attempt to set localStorage flags the site may use
            try { localStorage.setItem('onboarding_shown', 'true'); } catch(e) {}
        }""")
        print("✅ Removed common onboarding tooltip elements (JS)")
        # Add a CSS rule to hide any remaining overlays that might intercept clicks
        try:
            await page.add_style_tag(content=':root .onboarding-tooltip, :root .tour-tooltip, :root .onboarding, :root .tour, :root .popover { display: none !important; pointer-events: none !important; }')
            print("✅ Injected CSS to hide onboarding elements")
        except:
            pass
    except Exception as e:
        print(f"⚠️ Could not dismiss onboarding tooltip: {e}")
        # Non-fatal; continue

# ───────────── 2) GLOBALS FOR THE PLAYWRIGHT WORKER ──────────────────────────
playwright_job_queue = None     # Will be set to an asyncio.Queue() inside worker
WORKER_EVENT_LOOP = None        # To store the worker's event loop instance

async def playwright_worker_main():
    global playwright_job_queue, WORKER_EVENT_LOOP

    WORKER_EVENT_LOOP = asyncio.get_running_loop() 
    """ 
    asyncio.get_running_loop() returns the asyncio event loop object that’s actively running in the current OS thread.
    By assigning it to WORKER_EVENT_LOOP, you now have a handle to that loop which you can use later to schedule new tasks,
    create timers, run callbacks, or shut the loop down.

    This is useful if you need to call loop methods from places that don’t naturally have loop access
    """
    from playwright.async_api import async_playwright # Import here to be in the right context
    pw_instance = await async_playwright().start()
    import os
    run_headless = os.environ.get("PLAYWRIGHT_HEADLESS", "false").lower() != "false"
    browser: Browser = await pw_instance.chromium.launch(
        headless=run_headless,
        args=["--no-sandbox", "--disable-dev-shm-usage", "--window-size=1920,1080"]
    )
    print("→ Playwright worker: browser launched.")

    playwright_job_queue = asyncio.Queue()

    while True:
        job_details = await playwright_job_queue.get()
        if job_details is None:  # Shutdown sentinel
            break

        # Unpack job details
        ( sid, domains_list, designations_list, location_list2,
          converted_list, required_counts, num_results_arg, downloadFileName_arg ) = job_details
        state = clients_state.get(sid)
        if state is None or state.get("cancel_process"): # Check cancel flag before starting
            playwright_job_queue.task_done()
            continue

        # Spawn a new asyncio.Task for each job
        asyncio.create_task(
            handle_one_job(
                browser, pw_instance, sid, domains_list, designations_list,
                location_list2, converted_list, required_counts,
                num_results_arg, downloadFileName_arg
            )
        )

    # Cleanup
    print("→ Playwright worker: shutting down browser and Playwright.")
    await browser.close()
    await pw_instance.stop()
    print("→ Playwright worker: shutdown complete.")


async def handle_one_job(
    browser: Browser, pw_instance, sid: str,
    domains: list, designations: list, locations: list,
    cookies: list, required_counts: dict, num_results_arg: int, downloadFileName: str
):
    state = clients_state.get(sid)
    if state is None or state.get("cancel_process"):
        if playwright_job_queue: playwright_job_queue.task_done() # Must be called if job is taken from queue
        return

    context: BrowserContext = None
    page: Page = None
    result_message = "Processed successfully."
    
    # Data accumulation lists, local to this job
    file_data = []
    file_data2 = []
    emailcount = 0
    not_found_record_id = 1
    processed_count = 0  # Start at 0 for correct progress counting
    total_domains = len(domains)
    domain_remaining = domains[:] # Make a copy to modify

    # Clear previous results for this client for this new job run
    state["df_list"].clear()
    state["preview_list"].clear()

    try:
        await check_cancel(state, "Job initialization")
        print(f"[{sid}] Creating new browser context for job...")
        context = await browser.new_context(no_viewport=True)
        page = await context.new_page()
        state["current_context"] = context # For potential cancellation by refresh/disconnect
        state["current_page"] = page
        print(f"[{sid}] New browser context and page created.")

        await page.goto("https://app.snov.io/prospects/list")
        await asyncio.sleep(4) # Yield control and allow page to load
        await check_cancel(state, "Navigated to SNOV list page")

        print(f"[{sid}] Attempting to add cookies...")
        await context.clear_cookies() # Clear any residual cookies in the context
        playwright_cookies_to_add = []
      
        for sel_cookie_orig in cookies:
            cookie = sel_cookie_orig.copy()
            if "sameSite" in cookie and cookie["sameSite"] not in ["Strict", "Lax", "None"]:
                cookie.pop("sameSite")
            if "expirationDate" in cookie:
                if not isinstance(cookie["expirationDate"], (int, float)): # Allow float then convert
                    try:
                        cookie["expirationDate"] = float(cookie["expirationDate"])
                    except ValueError:
                        cookie.pop("expirationDate", None)
                if isinstance(cookie["expirationDate"], float): # Convert float to int
                    cookie["expirationDate"] = int(cookie["expirationDate"])


            pw_cookie = {
                "name": cookie.get("name"), "value": cookie.get("value"),
                "domain": cookie.get("domain"), "path": cookie.get("path", "/"),
                "httpOnly": bool(cookie.get("httpOnly", False)),
                "secure": bool(cookie.get("secure", False))
            }
            if "expirationDate" in cookie and cookie.get("expirationDate") is not None:
                pw_cookie["expires"] = cookie["expirationDate"]
            if "sameSite" in cookie: # Should be valid by now or removed
                pw_cookie["sameSite"] = cookie["sameSite"]
            
            if not (pw_cookie["name"] and pw_cookie["domain"]):
                continue
            playwright_cookies_to_add.append(pw_cookie)
        
        if playwright_cookies_to_add:
            try:
                await context.add_cookies(playwright_cookies_to_add)
                print(f"[{sid}] ✓ Added {len(playwright_cookies_to_add)} cookies successfully.")
                # Verify cookies were added
                all_cookies = await context.cookies()
                print(f"[{sid}] Total cookies in context: {len(all_cookies)}")
            except PlaywrightError as e:
                print(f"[{sid}] ⚠️  Playwright Warning: Could not add cookies: {e}")
            except Exception as e:
                print(f"[{sid}] ⚠️  Warning: Could not add one or more cookies (generic exception): {e}")
        else:
            print(f"[{sid}] ⚠️  No valid cookies to add!")
        
        await asyncio.sleep(0) # Yield
        await page.reload()
        print(f"[{sid}] Page reloaded after adding cookies.")
        try:
            await page.wait_for_load_state("networkidle", timeout=20_000)
        except PlaywrightTimeoutError:
            await asyncio.sleep(5)  # Fallback if networkidle never fires
        await check_cancel(state, "Added cookies and reloaded")
        try:
            bf_close_btn = page.locator("div.BF-modal__close-icon-wrap")
            await bf_close_btn.wait_for(state="visible", timeout=SHORT_TIMEOUT_MSEC)
            await bf_close_btn.click(force=True)
            await asyncio.sleep(1)
            print("✅ BF popup closed")
        except Exception:
            print("ℹ️ BF popup not present")
        
        # Enhanced toolbar detection with better error handling and logging
        try:
            await page.wait_for_selector("div.list__toolbar", state="attached", timeout=LONG_TIMEOUT_MSEC)
            print("✅ list__toolbar attached")
        except PlaywrightTimeoutError:
            # Provide diagnostic information
            print(f"[{sid}] ⚠️  list__toolbar not found. Checking page state...")
            page_title = await page.title()
            page_url = page.url
            print(f"[{sid}] Page Title: {page_title}")
            print(f"[{sid}] Page URL: {page_url}")
            
            # Check if we're on login page
            try:
                login_indicator = await page.query_selector("input[type='email'], input[name='email'], button[type='submit']")
                if login_indicator:
                    print(f"[{sid}] ❌ ERROR: Session expired or cookies invalid - Redirected to login page!")
                    raise MySpecialError("Session expired or authentication failed. Cookies may be invalid or outdated.")
            except:
                pass
            
            # Try alternative selectors
            alt_selectors = [
                "div.list__toolbar-wrapper",
                "div.toolbar",
                "div[class*='toolbar']",
                "div[class*='list']"
            ]
            
            for alt_selector in alt_selectors:
                try:
                    element = await page.query_selector(alt_selector)
                    if element:
                        print(f"[{sid}] ✓ Found alternative selector: {alt_selector}")
                        break
                except:
                    continue
            else:
                # No alternatives found
                print(f"[{sid}] ❌ Main toolbar AND all alternative selectors not found")
                print(f"[{sid}] Tip: Check if cookies are valid, session is active, or page layout has changed")
                raise MySpecialError("❌ list__toolbar not found and no alternatives detected. This usually means authentication failed or cookies are expired.")
        except MySpecialError:
            raise
        except Exception as e:
            print(f"[{sid}] Unexpected error while checking toolbar: {e}")
            raise MySpecialError(f"Unexpected error detecting toolbar: {e}")
        
        # ✅ 3. Click FIRST toolbar button (Add List)
        add_list_icon_btn_el =  page.locator("div.list__toolbar button.list__btn").nth(0)
        await add_list_icon_btn_el.wait_for(state="visible", timeout=20_000)
        await add_list_icon_btn_el.click(force=True)
        await asyncio.sleep(0.5)

        print("✅ Add List button clicked successfully")    

       
       
    

        modal_title_loc = page.locator("div.modal-snovio__title", has_text="Create a new prospects list")
        await modal_title_loc.wait_for(state="visible", timeout=20_000)
        
        name_input_modal_loc = page.locator("div.modal-snovio__window input.snov-input__input")
        await name_input_modal_loc.wait_for(state="visible", timeout=20_000)
        await name_input_modal_loc.fill(str(downloadFileName)) 
        await asyncio.sleep(0.2)

        await page.wait_for_selector("button[data-test='snov-modal-btn-primary']", state="attached", timeout=20_000)
        create_btn_modal_loc = page.locator("button[data-test='snov-modal-btn-primary']", has_text="Create")
        create_btn_el_handle = await create_btn_modal_loc.element_handle(timeout=5000) 
        if not create_btn_el_handle or not await create_btn_el_handle.is_visible():
            candidate_btns = await page.query_selector_all("button[data-test='snov-modal-btn-primary']")
            found_create_btn_handle = None
            for btn_h in candidate_btns:
                if await btn_h.is_visible() and (await btn_h.inner_text()).strip() == "Create":
                    found_create_btn_handle = btn_h; break
            if not found_create_btn_handle: raise MySpecialError("Could not find visible Create button in modal (Playwright)")
            create_btn_el_handle = found_create_btn_handle
        
        await create_btn_el_handle.scroll_into_view_if_needed()
        await page.evaluate("el => el.click()", create_btn_el_handle) # Use evaluate for tricky clicks
        await page.wait_for_selector("div.modal-snovio__window", state="hidden", timeout=10_000)
        await check_cancel(state, "Created list")

        await page.goto("https://app.snov.io/database-search/prospects")
        await asyncio.sleep(2) 
        # Dismiss onboarding/tooltips that can block interacting with filters (e.g. 'Got it' tour)
        await dismiss_onboarding_tooltip(page)
        await check_cancel(state, "Navigated to database search")
       
        location_input_xpath = "//div[contains(@class,'snov-filter')][.//span[text()='Location']]//input[contains(@class,'snov-filter__block-input')]"
        location_dropdown_list_xpath = "//div[contains(@class,'snov-filter')][.//span[text()='Location']]//ul[contains(@class,'snov-filter__list')]"
        location_first_option_xpath = ("(//div[contains(@class,'snov-filter')][.//span[text()='Location']]"
                                       "//ul[contains(@class,'snov-filter__list')]"
                                       "//div[contains(@class,'snov-filter__option') and .//div[contains(@class,'snov-filter__option-cnt')]][1])")
        
        if locations: 
            for loc_item_str in locations:
                await check_cancel(state, f"setting location {loc_item_str}")
                try:
                    await page.wait_for_selector(".snovContentLoader.snovContentLoader--full-screen", state="hidden", timeout=20_000)
                    loc_input_el = await page.wait_for_selector(location_input_xpath, state="visible", timeout=20_000)
                    try: await loc_input_el.click(timeout=3000)
                    except PlaywrightTimeoutError: await page.evaluate("el => el.click()", loc_input_el)
                    
                    await loc_input_el.fill(loc_item_str)
                    await page.wait_for_selector(location_dropdown_list_xpath, state="visible", timeout=20_000)
                    first_opt_el = await page.wait_for_selector(location_first_option_xpath, state="visible", timeout=20_000)
                    
                    try: await first_opt_el.click(timeout=3000)
                    except PlaywrightTimeoutError: await page.evaluate("el => el.click()", first_opt_el)
                    await asyncio.sleep(0.3) 
                except MySpecialError: raise
                except Exception as e_loc_add: print(f"[{sid}] An error occurred while setting location '{loc_item_str}': {e_loc_add}")
        await check_cancel(state, "Finished adding locations")
      
        company_name_input_xpath_pd = "//input[@placeholder='Enter company name']"
        first_suggestion_locator_xpath_pd = (
            # "//input[@placeholder='Enter company name']"
            # "/ancestor::div[contains(@class, 'snov-filter__block')]"
            # "/following-sibling::ul[contains(@class, 'snov-filter__list')]/div[@data-v-f10c3200]" # Be careful with generated data-v attributes
            # "/div[contains(@class, 'snov-filter__option')][1]"
            "//ul[contains(@class,'snov-filter__list')]"
            "//div[contains(@class,'snov-filter__option')]"
            "[.//div[contains(@class,'snov-filter__option-cnt__subtitle') "
            "and normalize-space()='{domain}']]"

        )
        search_button_xpath_pd = "//button[.//span[text()='Search']]"
        num_results_for_domain_cap = num_results_arg

        # ── Helper functions defined once, shared across all domain/designation iterations ──

        async def _async_wait_all_email_cells_final(pg_handle: Page, current_state, current_domain, current_title, timeout_seconds=30.0):
            start_time_sec = time.monotonic()
            print(f"[{sid}] Waiting for email cells to stabilize for {current_domain}/{current_title}...")
            while time.monotonic() - start_time_sec < timeout_seconds:
                await check_cancel(current_state, f"waiting email states for {current_domain}/{current_title}")
                all_rows_in_table = await pg_handle.query_selector_all("css=tbody tr")
                if not all_rows_in_table:
                    await asyncio.sleep(0.5); continue
                all_cells_are_final = True
                for r_idx, r_el_h in enumerate(all_rows_in_table):
                    try:
                        email_cell_el_h = await r_el_h.query_selector("css=td.row__cell--email")
                        if not email_cell_el_h:
                            all_cells_are_final = False; break
                        text_in_cell = (await email_cell_el_h.inner_text()).strip()
                        is_final_state = (
                            "@" in text_in_cell or
                            "No email found" in text_in_cell or
                            "Click Add to list to initiate email search" in text_in_cell or
                            (text_in_cell == "" and await r_el_h.query_selector("css=td.row__cell--action button span:has-text('Add to list')"))
                        )
                        if not is_final_state:
                            all_cells_are_final = False; break
                    except Exception as e_cell_check:
                        print(f"[{sid}]   Row {r_idx}: Error checking email cell: {e_cell_check}")
                        all_cells_are_final = False; break
                if all_cells_are_final:
                    print(f"[{sid}] All email cells stable for {current_domain}/{current_title}.")
                    return True
                await asyncio.sleep(0.5)
            print(f"[{sid}] Timed out waiting for email cells to stabilize for {current_domain}/{current_title}.")
            return False

        async def _async_wait_stable_email_text_in_cell(email_cell_h: ElementHandle, current_state, current_domain, current_title, timeout_s=55, poll_s=0.5):
            end_t = time.monotonic() + timeout_s; last_t = None; stable_st = None; conf_t = 1.0
            while time.monotonic() < end_t:
                await check_cancel(current_state, f"stable email text {current_domain}/{current_title}")
                curr_t = None
                try:
                    if not email_cell_h or not await email_cell_h.is_visible():
                        await asyncio.sleep(poll_s); continue
                    curr_t = (await email_cell_h.inner_text()).strip()
                except Exception:
                    await asyncio.sleep(poll_s); continue
                is_valid_fmt = "@" in curr_t and "." in curr_t and "No email found" not in curr_t
                if is_valid_fmt:
                    if curr_t == last_t:
                        if stable_st is None: stable_st = time.monotonic()
                        elif time.monotonic() - stable_st >= conf_t:
                            return curr_t
                    else: last_t = curr_t; stable_st = None
                elif curr_t == "No email found":
                    return curr_t
                elif curr_t == "" and await email_cell_h.query_selector("xpath=ancestor::tr//button[.//span[text()='Add to list']]"):
                    return curr_t
                else:
                    last_t = curr_t; stable_st = None
                await asyncio.sleep(poll_s)
            raise PlaywrightTimeoutError(f"Email text did not stabilize. Last: '{last_t}'")

        async def _async_wait_button_status_saved(row_el_h: ElementHandle, current_state, current_domain, current_title, timeout_s=25, poll_s=0.5):
            end_t = time.monotonic() + timeout_s
            # Flexible selectors for the action button — covers both old and new Snov UI
            action_btn_selectors = [
                'css=td.row__cell--action button[class*="pl-select__top-target"]',
                'css=td.row__cell--action button[class*="snv-btn"]',
                'css=td.row__cell--action button',
                'css=td[class*="action"] button',
            ]
            while time.monotonic() < end_t:
                await check_cancel(current_state, f"btn saved status {current_domain}/{current_title}")
                try:
                    if not row_el_h or not await row_el_h.is_visible():
                        await asyncio.sleep(poll_s); continue
                except Exception:
                    raise PlaywrightTimeoutError("Row element became stale while waiting for 'Saved' status.")
                for btn_sel in action_btn_selectors:
                    try:
                        btn_el = await row_el_h.query_selector(btn_sel)
                        if btn_el:
                            full_text = (await btn_el.inner_text()).strip()
                            if "saved" in full_text.lower():
                                return "Saved"
                    except Exception:
                        continue
                await asyncio.sleep(poll_s)
            # Don't raise — just return a warning so the flow continues
            print(f"[{sid}] Warning: 'Saved' status not confirmed within {timeout_s}s — continuing anyway.")
            return "Unknown"

        async def _async_check_tick_mark_in_dropdown_item(dd_item_el_h: ElementHandle):
            if not dd_item_el_h: return False
            try:
                if not await dd_item_el_h.is_visible(): return False
            except Exception: return False
            use_tag_el = await dd_item_el_h.query_selector("css=svg.arrow-icon-selected use, svg.snov-dropdown__check-icon use")
            if use_tag_el:
                try:
                    href_attr = (await use_tag_el.get_attribute("xlink:href")) or (await use_tag_el.get_attribute("href"))
                    if href_attr and ("#check-dropdown_icon" in href_attr or "#check_snov_dropdown" in href_attr):
                        return True
                except Exception:
                    return False
            return False

        # ── End helpers ─────────────────────────────────────────────────────────────────

        for domain_idx, domain_str_item in enumerate(domains):
            await check_cancel(state, f"Starting domain {domain_str_item}")
            processed_count += 1
            remaining_calc = max(0, total_domains - processed_count)
            socketio.emit(
                "overall_progress",
                {"total": total_domains, "processed": processed_count, "remaining": remaining_calc},
                room=sid,
            )
            await asyncio.sleep(0.01) # Miniscule sleep just to ensure emit goes
            print(f"[{sid}] Processing domain: {domain_str_item}")
            socketio.emit(
                "progress_update",
                {"domain": domain_str_item, "message": "Domain processing started"},
                room=sid,
            )

            num_results = num_results_for_domain_cap # Reset cap for each domain as per original logic
            
            found_flag_domain = False
           
            found_verified_email_domain = False # Tracks if a verified (green/yellow) email was found

            company_domain_search_button_el: ElementHandle = None
            job_title_filter_input_el: ElementHandle = None

            clear_company_selector = (
            'div.snov-filter__block:has(div.snov-filter__name:has-text("Company name")) '
             'span.snov-filter__tools-clear'
)
            try:
                clear_company_btn = await page.query_selector(clear_company_selector)
                if clear_company_btn and await clear_company_btn.is_visible():
                    await clear_company_btn.click(timeout=2000)
                    print(f"[{sid}] Cleared 'Company name' filter for domain {domain_str_item}.")
                    await asyncio.sleep(0.3)
            except PlaywrightTimeoutError:
                print(f"[{sid}] No 'Company name' clear button found or not clickable for domain {domain_str_item}; skipping clear.")
            except Exception as e_clear_company:
                print(f"[{sid}] Error trying to clear company name filter: {e_clear_company}")

            try:
                await page.wait_for_selector("div.db-search__filters", timeout=20_000, state="visible")
                company_name_input_el = await page.wait_for_selector(
                    company_name_input_xpath_pd, state="visible", timeout=20_000
                )
                try: await company_name_input_el.click(timeout=3000)
                except PlaywrightTimeoutError: await page.evaluate("el => el.click()", company_name_input_el)
                
                await company_name_input_el.fill(domain_str_item)
                print(f"[{sid}] Entered '{domain_str_item}' into company name input.")

                # Wait for suggestions to appear; the locator might need to be more robust
                # Snov.io might have dynamic loading, so ensure the specific suggestion is loaded

                # first_sugg_el = await page.wait_for_selector(
                #     first_suggestion_locator_xpath_pd, state="visible", timeout=20_000 
                # )

                ########## change1
                # company_xpath = first_suggestion_locator_xpath_pd.format(
                #     domain=domain_str_item
                # )

                # first_sugg_el = await page.wait_for_selector(
                #     company_xpath,
                #     state="visible",
                #     timeout=7000
                # )
                # await first_sugg_el.click()

                company_xpath = first_suggestion_locator_xpath_pd.format(
                    domain=domain_str_item
                )

                # Wait until suggestion exists in DOM
                await page.wait_for_selector(company_xpath, state="attached", timeout=10_000)

                # Click using selector (NOT ElementHandle)
                await page.click(company_xpath, timeout=10_000)

                print(f"[{sid}] Clicked first company suggestion for '{domain_str_item}'.")

                ##### Change2
                # try: await first_sugg_el.click(timeout=30_000) # Increased timeout for click
                # except PlaywrightTimeoutError: await page.evaluate("el => el.click()", first_sugg_el)
                # print(f"[{sid}] Clicked first company suggestion for '{domain_str_item}'.")
                # await check_cancel(state, f"Selected company suggestion for {domain_str_item}")
                # await asyncio.sleep(0.5) # Allow UI to update

                await check_cancel(state, f"Selected company suggestion for {domain_str_item}")
                await asyncio.sleep(0.5)  # Allow UI to update

                company_domain_search_button_el = await page.wait_for_selector(
                    search_button_xpath_pd, state="visible", timeout=20_000
                )
                job_title_filter_input_el = await page.wait_for_selector(
                    "//div[contains(@class,'snov-filter')][.//span[text()='Job title']]"
                    "//input[contains(@class,'snov-filter__block-input')]",
                    state="visible",
                    timeout=20_000,
                )
            except MySpecialError: raise
            except Exception as e_domain_setup:
                print(f"[{sid}] Error during search setup for domain '{domain_str_item}': {e_domain_setup}")
                socketio.emit("progress_update", {"domain": domain_str_item, "message": "Domain not available in snov.io"}, room=sid)
                #------------------------------------------
                new_not_found_record = {
                        "First Name": str(not_found_record_id), "job title": "N/A", "company": "N/A",
                        "location": "N/A", "email": "Not found (domain level)", "domain": domain_str_item
                }
                file_data2.append(new_not_found_record)
                not_found_record_id += 1
                state["preview_list"].append(new_not_found_record)
                try:
                    socketio.emit("preview_data", {"previewData": state["preview_list"]}, room=sid)
                except Exception as e_emit_preview_final:
                    print(f"[{sid}] Error emitting preview data: {e_emit_preview_final}")
                continue
         
    
            for title_idx, title_str_item in enumerate(designations):
                await check_cancel(state, f"Processing designation '{title_str_item}' for domain '{domain_str_item}'")
                socketio.emit("progress_update", {"domain": domain_str_item, "message": f"Processing designation: {title_str_item}"}, room=sid)
                await asyncio.sleep(0.01)

                if num_results <= 0:
                    print(f"[{sid}] Domain email cap (num_results={num_results}) reached for '{domain_str_item}'. Skipping designation '{title_str_item}'.")
                    break

                print(f"[{sid}] Current designation: '{title_str_item}' for domain '{domain_str_item}'")

                clear_job_title_selector = (
                "div.snov-filter__block:has(div.snov-filter__name:has-text(\"Job title\")) "
                "span.snov-filter__tools-clear"
                    )

                try:
                    clear_job_btn = await page.query_selector(clear_job_title_selector)
                    if clear_job_btn and await clear_job_btn.is_visible():
                        await clear_job_btn.click(timeout=2000)
                        print(f"[{sid}] Cleared 'Job title' filter for designation '{title_str_item}'.")
                        await asyncio.sleep(0.3)
                except PlaywrightTimeoutError:
                    print(f"[{sid}] No 'Job title' clear button found or not clickable for '{title_str_item}'; skipping clear.")
                except Exception as e_clear_job:
                    print(f"[{sid}] Error trying to clear job title filter: {e_clear_job}")

                # Re-query filter handles each iteration to avoid stale element errors
                try:
                    job_title_filter_input_el = await page.wait_for_selector(
                        "//div[contains(@class,'snov-filter')][.//span[text()='Job title']]"
                        "//input[contains(@class,'snov-filter__block-input')]",
                        state="visible", timeout=10_000,
                    )
                    company_domain_search_button_el = await page.wait_for_selector(
                        search_button_xpath_pd, state="visible", timeout=10_000
                    )
                except PlaywrightTimeoutError:
                    print(f"[{sid}] Filter inputs not found for designation '{title_str_item}'. Breaking.")
                    break

                try:
                    await job_title_filter_input_el.fill(title_str_item)
                    await job_title_filter_input_el.press("Enter") # Ensure filter is applied
                    await asyncio.sleep(0.2) # Allow filter to apply

                    await company_domain_search_button_el.click()
                    print(f"[{sid}] Search initiated for domain: {domain_str_item}, title: {title_str_item}")
                    await asyncio.sleep(0.8) # Wait for search results to begin loading
                except Exception as e_apply_filter_search:
                    print(f"[{sid}] Error applying filter or searching for title '{title_str_item}': {e_apply_filter_search}")
                    continue # Skip to next designation

                # More flexible selector to catch "No prospects found" message
                # Checks for div with not-found__title class that contains relevant text
                no_prospects_msg_xpath = "//div[contains(@class, 'not-found__title') and (contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'couldn') or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'match') or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'find'))]"
                try:
                    await page.wait_for_selector(no_prospects_msg_xpath, state="visible", timeout=5_000) # Reduced timeout - if no message within 5s, assume results exist
                    # Get the actual message text for debugging
                    try:
                        not_found_msg_element = await page.query_selector(no_prospects_msg_xpath)
                        actual_message = (await not_found_msg_element.inner_text()).strip() if not_found_msg_element else "Unknown"
                        print(f"[{sid}] No prospects found message displayed: '{actual_message}'")
                    except: 
                        actual_message = "Could not retrieve message text"
                    
                    # Double-check: verify there's actually no table data before treating as "no prospects"
                    table_rows_check = await page.query_selector_all("css=tbody tr")
                    if table_rows_check and len(table_rows_check) > 0:
                        print(f"[{sid}] WARNING: 'No prospects' message detected but table has {len(table_rows_check)} rows! Treating as prospects found.")
                        # If we have table rows, fall through to process them (don't continue yet)
                    else:
                        print(f"[{sid}] No prospects found for '{title_str_item}' in domain '{domain_str_item}'.")
                        if title_idx == len(designations) - 1 and not found_flag_domain:
                            print(f"[{sid}] Last designation ('{title_str_item}') and no email found yet for domain '{domain_str_item}' (no prospects path). Adding to file_data2.")
                            if not any(item['domain'] == domain_str_item for item in file_data2):
                                nf_rec = {
                                    "First Name": str(not_found_record_id), "job title": "N/A", "company": "N/A",
                                    "location": "N/A", "email": "Not found", "domain": domain_str_item
                                }
                                file_data2.append(nf_rec)
                                not_found_record_id += 1
                                state["preview_list"].append(nf_rec)
                                try:
                                    socketio.emit("preview_data", {"previewData": state["preview_list"]}, room=sid)
                                except Exception as e_emit_preview_final:
                                    print(f"[{sid}] Error emitting preview data: {e_emit_preview_final}")
                        # Only continue if we actually confirmed no prospects (no table rows)
                        continue 
                except MySpecialError: raise
                except PlaywrightTimeoutError: # This is the "good" path - no "not found" message means prospects might exist
                    print(f"[{sid}] Prospects potentially found for '{title_str_item}' (no 'not found' message).")
                except Exception as e_no_prospects_check:
                    print(f"[{sid}] Error checking for 'no prospects' message: {e_no_prospects_check}")
                    continue

                try:
                    # Wait for at least one table row to ensure results are loaded
                    await page.wait_for_selector("css=tbody tr", state="attached", timeout=15_000)
                except MySpecialError: raise
                except PlaywrightTimeoutError:
                    print(f"[{sid}] Timed out waiting for table rows for title '{title_str_item}'.")
                    # Try alternative row selectors
                    try:
                        alt_rows = await page.query_selector_all("tr.row, div[class*='table-row'], div[class*='prospect'], tr")
                        print(f"[{sid}] ⚠️ Alternative row selectors found: {len(alt_rows)} rows total")

                        if len(alt_rows) > 0:
                            print(f"[{sid}] ✓ Using alternative row selector - found {len(alt_rows)} prospects")
                        else:
                            # Debug: Log page structure
                            await page.screenshot(path=f"debug_page_{sid}.png")
                            print(f"[{sid}] 📸 Screenshot saved to debug_page_{sid}.png")

                            table_elements = await page.query_selector_all("table, [role='grid'], [role='table'], div[class*='list'], div[class*='table']")
                            print(f"[{sid}] Found {len(table_elements)} table-like container elements")

                            # Try to find any element with email-like content
                            all_cells = await page.query_selector_all("[class*='email'], [class*='cell'], [class*='row']")
                            print(f"[{sid}] Found {len(all_cells)} email/cell/row-like elements")
                            if all_cells:
                                print(f"[{sid}] Detected {len(all_cells)} potential data cells")
                            continue
                    except Exception as e_debug:
                        print(f"[{sid}] Error during alternative selector lookup: {str(e_debug)}")
                    continue # To next designation


                if not await _async_wait_all_email_cells_final(page, state, domain_str_item, title_str_item):
                    print(f"[{sid}] Skipping title '{title_str_item}' due to unstable email cells.")
                    continue 
                
                print(f"[{sid}] --- Extracting prospects for heap processing (Title: '{title_str_item}') ---")
                # Try multiple row selectors with flexible matching
                row_selectors = [
                    "css=tbody tr.row",
                    "css=tbody tr",
                    "css=tr.row",
                    "xpath=//tbody/tr",
                    "css=tr",
                ]
                heap_processing_rows = await find_elements_flexible(page, row_selectors)
                print(f"[{sid}] Found {len(heap_processing_rows)} prospect rows using flexible selector")

                if not heap_processing_rows:
                    print(f"[{sid}] ⚠️ No rows found for heap processing for title '{title_str_item}'.")
                    print(f"[{sid}] 🔍 DIAGNOSTICS - Checking page structure...")

                    # Diagnostic: Show available elements
                    try:
                        table_exists = await page.query_selector("table")
                        tbody_exists = await page.query_selector("tbody")
                        any_tr = await page.query_selector("tr")
                        any_rows_css = await page.query_selector_all("tr")

                        print(f"[{sid}]   - Table element exists: {bool(table_exists)}")
                        print(f"[{sid}]   - Tbody element exists: {bool(tbody_exists)}")
                        print(f"[{sid}]   - Any TR elements: {bool(any_tr)} (Total: {len(any_rows_css)})")

                        # Check for alternative row patterns
                        div_rows = await page.query_selector_all("div[class*='row']")
                        print(f"[{sid}]   - Div rows (with 'row' class): {len(div_rows)}")

                        # Print first few row attributes if any found
                        if any_rows_css:
                            for idx, tr_el in enumerate(any_rows_css[:3]):
                                classes = await tr_el.get_attribute("class") or ""
                                print(f"[{sid}]   - TR[{idx}] class='{classes}'")
                    except Exception as diag_err:
                        print(f"[{sid}]   - Diagnostic error: {diag_err}")

                    continue

                # Heap stores (priority, unique_id, row_INDEX) — NOT ElementHandles.
                # Fresh handles are re-queried when popping to avoid stale element errors.
                max_heap = []
                heap_id_counter = 0

                heap_priority_keywords = {
                    "sr head": -17, "senior head": -16, "head": -15, "sr manager": -14,
                    "senior manager": -13, "manager": -12, "deputy manager": -11,"asst manager": -10,"assistant manager": -9,
                    "vice president":-8,"vp":-7,"president":-6,"director":-5,"general manager":-4 , "deputy general manager":-3 ,
                    "engineer":-2
                }

                for r_h_idx, r_h_item in enumerate(heap_processing_rows):
                    await check_cancel(state, f"Building heap for {domain_str_item}/{title_str_item}, row {r_h_idx}")
                    try:
                        job_title_div_el = await r_h_item.query_selector("css=td.row__cell--name > div")
                        designation_text_lower = (await job_title_div_el.inner_text()).strip().lower() if job_title_div_el else ""

                        p_val = 0
                        for keyword, priority in heap_priority_keywords.items():
                            if keyword in designation_text_lower:
                                p_val = priority
                                break

                        heap_id_counter += 1
                        heapq.heappush(max_heap, (p_val, heap_id_counter, r_h_idx))  # store INDEX, not handle
                    except Exception as e_heap_build:
                        print(f"[{sid}] Error adding to heap for row {r_h_idx}: {e_heap_build}")

                num_of_emails_needed_for_title = required_counts.get(title_str_item.lower(), float('inf'))
                print(f"[{sid}] Starting final extraction from heap for title '{title_str_item}'. Need {num_of_emails_needed_for_title}. Domain cap (num_results) left: {num_results}. Heap size: {len(max_heap)}")
                emails_collected_for_this_title_run = 0
                invalid_email_count = 0
               
                while max_heap and emails_collected_for_this_title_run < num_of_emails_needed_for_title and num_results > 0:
                    await check_cancel(state, f"Heap processing loop for {domain_str_item}/{title_str_item}")

                    if invalid_email_count >= INVALID_EMAIL_COUNT_THRESHOLD:
                        break
                    current_p_val, _, current_row_idx = heapq.heappop(max_heap)

                    # Re-query ALL rows fresh to avoid stale ElementHandle errors
                    try:
                        fresh_rows = await page.query_selector_all("css=tbody tr")
                        if current_row_idx >= len(fresh_rows):
                            print(f"[{sid}]   Row index {current_row_idx} out of range (table has {len(fresh_rows)} rows). Skipping.")
                            continue
                        current_row_el_handle = fresh_rows[current_row_idx]
                        if not await current_row_el_handle.is_visible():
                            print(f"[{sid}]   Row {current_row_idx} not visible. Skipping.")
                            continue
                    except Exception as e_fresh_query:
                        print(f"[{sid}]   Could not re-query fresh rows: {e_fresh_query}. Skipping.")
                        continue

                    print(f"[{sid}]\n  Processing Row index={current_row_idx} (priority: {current_p_val})")
                    final_email_str_from_row = None
                    is_green_or_yellow_email_row = False

                    # Extract actual contact info from the row
                    name_from_row = "N/A"
                    jobtitle_from_row = "N/A"
                    company_from_row = "N/A"
                    location_from_row = "N/A"
                    try:
                        name_el = await current_row_el_handle.query_selector(
                            "td.row__cell--first-name, td[class*='first-name']")
                        if name_el:
                            name_from_row = (await name_el.inner_text()).strip() or "N/A"

                        title_el = await current_row_el_handle.query_selector(
                            "td.row__cell--name > div, td[class*='title'] div, td[class*='name'] div")
                        if title_el:
                            jobtitle_from_row = (await title_el.inner_text()).strip() or "N/A"

                        company_el = await current_row_el_handle.query_selector(
                            "td.row__cell--company, td[class*='company']")
                        if company_el:
                            company_from_row = (await company_el.inner_text()).strip() or "N/A"

                        location_el = await current_row_el_handle.query_selector(
                            "td.row__cell--location, td[class*='location']")
                        if location_el:
                            location_from_row = (await location_el.inner_text()).strip() or "N/A"
                    except Exception as e_extract_info:
                        print(f"[{sid}]   Could not extract row contact info: {e_extract_info}")

                    try:
                        # Try multiple email cell selectors
                        email_cell_selectors = [
                            "css=td.row__cell--email",
                            "css=td[class*='email']",
                            "css=td.email",
                            "xpath=.//td[contains(@class, 'email')]",
                            "xpath=.//div[contains(@class, 'email')]"
                        ]
                        email_cell_el_h_current = None
                        for sel in email_cell_selectors:
                            try:
                                email_cell_el_h_current = await current_row_el_handle.query_selector(sel)
                                if email_cell_el_h_current:
                                    print(f"[{sid}]   Using email selector: {sel}")
                                    break
                            except:
                                continue

                        if not email_cell_el_h_current or not await email_cell_el_h_current.is_visible():
                            print(f"[{sid}]   Email cell missing or not visible. Skipping row.")
                            continue

                        initial_email_cell_text = (await email_cell_el_h_current.inner_text()).strip()
                        # More robust check for green/yellow status
                        gy_selector = "css=span.email-status-1, span.email-status-2, span[class*='email-status-1'], span[class*='email-status-2'], span[class*='status--green'], span[class*='status--yellow'], span[class*='verified']"
                        is_green_or_yellow_email_row = bool(await current_row_el_handle.query_selector(gy_selector))
                       
                        if is_green_or_yellow_email_row and "@" in initial_email_cell_text and "." in initial_email_cell_text \
                           and "Add to list" not in initial_email_cell_text and "No email found" not in initial_email_cell_text:
                            
                            potential_email_parsed = initial_email_cell_text.split()[-1] if initial_email_cell_text.split() else initial_email_cell_text
                            if "@" in potential_email_parsed and "." in potential_email_parsed:
                                final_email_str_from_row = potential_email_parsed
                                print(f"[{sid}]   Direct G/Y email found: {final_email_str_from_row}")

                                # Check if already saved to the target list
                                action_cell_selectors = [
                                    "css=td.row__cell--action",
                                    "css=td[class*='action']",
                                    "css=td.action",
                                    "xpath=.//td[contains(@class, 'action')]"
                                ]
                                action_cell_el_h = await find_element_flexible(current_row_el_handle, action_cell_selectors)
                                saved_btn_el_h = None
                                if action_cell_el_h:
                                    saved_btn_selectors = [
                                        "xpath=.//button[contains(@class, 'snv-btn') and contains(@class, 'pl-select__top-target') and .//span[contains(text(), 'Saved')]]",
                                        "xpath=.//button[.//span[contains(text(), 'Saved')]]",
                                        "css=button[class*='snv-btn']:has-text('Saved')",
                                        "xpath=.//button[contains(text(), 'Saved')]"
                                    ]
                                    saved_btn_el_h = await find_element_flexible(action_cell_el_h, saved_btn_selectors)

                                if saved_btn_el_h:
                                    try:
                                        # Use native Playwright click — Vue.js ignores plain JS el.click()
                                        try:
                                            await saved_btn_el_h.scroll_into_view_if_needed()
                                            await saved_btn_el_h.click(timeout=5000)
                                        except Exception:
                                            await page.evaluate(
                                                """el => {
                                                    ['pointerdown','mousedown','pointerup','mouseup','click'].forEach(t =>
                                                        el.dispatchEvent(new MouseEvent(t, {bubbles:true, cancelable:true, view:window}))
                                                    );
                                                }""",
                                                saved_btn_el_h
                                            )  # Click 'Saved' to open dropdown

                                        # Wait for dropdown to appear
                                        dropdown_items_list_h = []
                                        for dd_sel in ["css=li.pl-select__item", "css=div.app-dropdown__drop li", "css=div.snov-dropdown__options li", "css=ul.pl-select__list li"]:
                                            try:
                                                await page.wait_for_selector(dd_sel, state="visible", timeout=5_000)
                                                dropdown_items_list_h = await page.query_selector_all(dd_sel)
                                                if dropdown_items_list_h:
                                                    break
                                            except PlaywrightTimeoutError:
                                                continue

                                        is_already_ticked_in_list = False

                                        if dropdown_items_list_h:
                                            for dd_item_h in dropdown_items_list_h:
                                                item_name_span = await dd_item_h.query_selector(
                                                    "span.pl-select__item-name, span.item-name, span"
                                                )
                                                item_text = (await item_name_span.inner_text()).strip() if item_name_span else \
                                                            (await dd_item_h.inner_text()).strip()
                                                if item_text.lower() == downloadFileName.strip().lower():
                                                    if await _async_check_tick_mark_in_dropdown_item(dd_item_h):
                                                        is_already_ticked_in_list = True
                                                        print(f"[{sid}]     Email already saved in target list '{downloadFileName}'.")
                                                        socketio.emit("progress_update", {"domain": domain_str_item, "message": f"EMAIL FOUND (ALREADY IN LIST) - {final_email_str_from_row} for {title_str_item}"}, room=sid)
                                                        final_email_str_from_row = None # Nullify to prevent re-adding
                                                    else: # Not ticked, so tick it
                                                        print(f"[{sid}]     Saving to target list '{downloadFileName}' (from Saved dropdown).")
                                                        try:
                                                            await dd_item_h.scroll_into_view_if_needed()
                                                            await dd_item_h.click(timeout=5000)
                                                        except Exception:
                                                            await page.evaluate(
                                                                """el => {
                                                                    ['pointerdown','mousedown','pointerup','mouseup','click'].forEach(t =>
                                                                        el.dispatchEvent(new MouseEvent(t, {bubbles:true, cancelable:true, view:window}))
                                                                    );
                                                                }""",
                                                                dd_item_h
                                                            )
                                                        await asyncio.sleep(1.0)
                                                        # Wait for toast confirmation (optional but good)
                                                        try:
                                                            toast_selector = "xpath=//div[contains(text(), 'prospects saved') or contains(text(), 'Prospects have been saved')]"
                                                            await page.wait_for_selector(toast_selector, state="visible", timeout=7_000)
                                                            await page.wait_for_selector(toast_selector, state="hidden", timeout=7_000)
                                                        except PlaywrightTimeoutError: print(f"[{sid}]     'Prospects saved' toast confirmation timeout.")
                                                    break # Found target list item
                                            if not is_already_ticked_in_list and final_email_str_from_row is None and not any((await item.query_selector("span.pl-select__item-name") and await (await item.query_selector("span.pl-select__item-name")).inner_text()).strip().lower() == downloadFileName.strip().lower() for item in dropdown_items_list_h):
                                                 print(f"[{sid}]     ERROR: Target list '{downloadFileName}' NOT FOUND in dropdown (direct G/Y path).")
                                            elif final_email_str_from_row and not any((await item.query_selector("span.pl-select__item-name") and await (await item.query_selector("span.pl-select__item-name")).inner_text()).strip().lower() == downloadFileName.strip().lower() for item in dropdown_items_list_h):
                                                print(f"[{sid}]     WARN: Email found, but target list '{downloadFileName}' not in dropdown. Not saving to list.")
                                        else: print(f"[{sid}]     ERROR: Dropdown for list selection not found (direct G/Y path).")
                                        await page.keyboard.press("Escape") # Close dropdown
                                        await asyncio.sleep(0.2)
                                    except Exception as e_click_saved_dd:
                                        print(f"[{sid}]     Error interacting with 'Saved' button dropdown: {e_click_saved_dd}")
                                        if await page.query_selector("div.app-dropdown__drop, div.snov-dropdown__options"): # If dropdown is open
                                            await page.keyboard.press("Escape")
                                else: # G/Y email but no "Saved" button (might be "Add to list" if not yet processed)
                                    print(f"[{sid}]   G/Y email, but no 'Saved' button. State: '{await action_cell_el_h.inner_text() if action_cell_el_h else 'N/A'}'. Will attempt 'Add to list' if necessary.")
                                    final_email_str_from_row = None # Force "Add to list" path if it's not explicitly saved

                        if not final_email_str_from_row: # Needs "Add to list" or email wasn't G/Y
                            print(f"[{sid}]   Email not G/Y or not directly available ('{initial_email_cell_text}'). Attempting 'Add to list'...")
                            action_cell_selectors_2 = [
                                "css=td.row__cell--action",
                                "css=td[class*='action']",
                                "xpath=.//td[contains(@class, 'action')]"
                            ]
                            action_cell_el_h = await find_element_flexible(current_row_el_handle, action_cell_selectors_2)
                            add_list_btn_el_h = None
                            if action_cell_el_h:
                                add_list_btn_selectors = [
                                    "xpath=.//button[contains(@class, 'snv-btn') and contains(@class, 'pl-select__top-target') and .//span[contains(text(), 'Add to list')]]",
                                    "xpath=.//button[.//span[contains(text(), 'Add to list')]]",
                                    "css=button[class*='snv-btn']:has-text('Add to list')",
                                    "xpath=.//button[contains(text(), 'Add to list')]"
                                ]
                                add_list_btn_el_h = await find_element_flexible(action_cell_el_h, add_list_btn_selectors)
                            
                            if add_list_btn_el_h:
                                print(f"[{sid}]     'Add to list' button identified.")
                                try:
                                    # Use native Playwright click — Vue.js ignores plain JS el.click()
                                    try:
                                        await add_list_btn_el_h.scroll_into_view_if_needed()
                                        await add_list_btn_el_h.click(timeout=5000)
                                    except Exception:
                                        await page.evaluate(
                                            """el => {
                                                ['pointerdown','mousedown','pointerup','mouseup','click'].forEach(t =>
                                                    el.dispatchEvent(new MouseEvent(t, {bubbles:true, cancelable:true, view:window}))
                                                );
                                            }""",
                                            add_list_btn_el_h
                                        )

                                    # Wait for dropdown container to appear — don't rely on bare sleep
                                    dropdown_container_selectors = [
                                        "css=li.pl-select__item",
                                        "css=div.app-dropdown__drop li",
                                        "css=div.snov-dropdown__options li",
                                        "css=ul.pl-select__list li",
                                    ]
                                    dropdown_items_list_h_add = []
                                    for dd_sel in dropdown_container_selectors:
                                        try:
                                            await page.wait_for_selector(dd_sel, state="visible", timeout=5_000)
                                            dropdown_items_list_h_add = await page.query_selector_all(dd_sel)
                                            if dropdown_items_list_h_add:
                                                print(f"[{sid}]     Dropdown found via: {dd_sel} ({len(dropdown_items_list_h_add)} items)")
                                                break
                                        except PlaywrightTimeoutError:
                                            continue

                                    clicked_target_list_dd_item_add = False

                                    if dropdown_items_list_h_add:
                                        target_lower = downloadFileName.strip().lower()
                                        for dd_item_h_add in dropdown_items_list_h_add:
                                            # Try multiple selectors for the item name span
                                            item_name_span = await dd_item_h_add.query_selector(
                                                "span.pl-select__item-name, span.item-name, span"
                                            )
                                            item_text = (await item_name_span.inner_text()).strip() if item_name_span else \
                                                        (await dd_item_h_add.inner_text()).strip()
                                            print(f"[{sid}]     Dropdown item: '{item_text}'")
                                            if item_text.lower() == target_lower:
                                                print(f"[{sid}]     Found target list '{downloadFileName}'. Clicking.")
                                                # Dispatch full mouse event chain — Vue.js needs pointerdown/mousedown/mouseup/click
                                                try:
                                                    await dd_item_h_add.scroll_into_view_if_needed()
                                                    await dd_item_h_add.click(timeout=5000)
                                                except Exception:
                                                    await page.evaluate(
                                                        """el => {
                                                            ['pointerdown','mousedown','pointerup','mouseup','click'].forEach(t =>
                                                                el.dispatchEvent(new MouseEvent(t, {bubbles:true, cancelable:true, view:window}))
                                                            );
                                                        }""",
                                                        dd_item_h_add
                                                    )
                                                clicked_target_list_dd_item_add = True
                                                # Wait for toast confirmation that prospect was saved
                                                try:
                                                    toast_sel = "xpath=//div[contains(text(), 'prospects saved') or contains(text(), 'Prospects have been saved') or contains(text(), 'saved to')]"
                                                    await page.wait_for_selector(toast_sel, state="visible", timeout=7_000)
                                                    await page.wait_for_selector(toast_sel, state="hidden", timeout=7_000)
                                                    print(f"[{sid}]     Toast confirmed: prospect saved to list.")
                                                except PlaywrightTimeoutError:
                                                    print(f"[{sid}]     No toast seen — proceeding anyway.")
                                                await asyncio.sleep(0.5)
                                                break
                                        if not clicked_target_list_dd_item_add:
                                            print(f"[{sid}]     ERROR: Target list '{downloadFileName}' not found in dropdown ('Add to list' path).")
                                            print(f"[{sid}]     Available lists: {[((await i.query_selector('span.pl-select__item-name, span')) and (await (await i.query_selector('span.pl-select__item-name, span')).inner_text()).strip()) for i in dropdown_items_list_h_add]}")
                                    else:
                                        print(f"[{sid}]     ERROR: Dropdown did not appear after clicking 'Add to list'.")

                                    if clicked_target_list_dd_item_add:
                                        saved_status_text = await _async_wait_button_status_saved(current_row_el_handle, state, domain_str_item, title_str_item)
                                        stable_email_text_after_add = await _async_wait_stable_email_text_in_cell(email_cell_el_h_current, state, domain_str_item, title_str_item)
                                        print(f"[{sid}]     Status='{saved_status_text}', Final Email Text='{stable_email_text_after_add}'")

                                        is_green_or_yellow_email_row = bool(await current_row_el_handle.query_selector(gy_selector))
                                        # Accept email if: valid format AND (verified status OR save was confirmed)
                                        email_is_valid_format = "@" in stable_email_text_after_add and "." in stable_email_text_after_add and "No email found" not in stable_email_text_after_add
                                        if email_is_valid_format and (is_green_or_yellow_email_row or "saved" in saved_status_text.lower()):
                                            final_email_str_from_row = stable_email_text_after_add
                                            print(f"[{sid}]     Email successfully retrieved via 'Add to list': {final_email_str_from_row}")
                                        elif email_is_valid_format:
                                            # Email is valid but status uncertain — still record it
                                            final_email_str_from_row = stable_email_text_after_add
                                            print(f"[{sid}]     Email recorded (status uncertain but email valid): {final_email_str_from_row}")
                                        else:
                                            print(f"[{sid}]     Email after 'Add to list' ('{stable_email_text_after_add}') not valid or 'No email found'.")
                                    else: # Target list not clicked
                                        if await page.query_selector("div.app-dropdown__drop, div.snov-dropdown__options"): # If dropdown is open
                                            await page.keyboard.press("Escape")

                                except Exception as e_add_to_list_flow:
                                    print(f"[{sid}]     Error during 'Add to list' flow: {e_add_to_list_flow}")
                                    if await page.query_selector("div.app-dropdown__drop, div.snov-dropdown__options"): # If dropdown is open
                                        await page.keyboard.press("Escape")
                            elif action_cell_el_h and "Saved" in (await action_cell_el_h.inner_text()):
                                
                                stable_email_text_if_saved = await _async_wait_stable_email_text_in_cell(email_cell_el_h_current, state, domain_str_item, title_str_item, timeout_s=10) # Shorter timeout
                                is_green_or_yellow_email_row = bool(await current_row_el_handle.query_selector(gy_selector))
                                email_valid = "@" in stable_email_text_if_saved and "." in stable_email_text_if_saved and "No email found" not in stable_email_text_if_saved
                                if email_valid:
                                    final_email_str_from_row = stable_email_text_if_saved
                                    print(f"[{sid}]     Email confirmed from 'Saved' row: {final_email_str_from_row}")
                                else:
                                    print(f"[{sid}]   Button was 'Saved', but email text ('{stable_email_text_if_saved}') not valid or 'No email found'.")
                            else:
                                print(f"[{sid}]   No 'Add to list' button found, or other state. Action cell: '{await action_cell_el_h.inner_text() if action_cell_el_h else 'N/A'}'")

                    except MySpecialError: raise
                    except PlaywrightTimeoutError as pte_heap_row_proc:
                        print(f"[{sid}]     Timeout processing heap row: {pte_heap_row_proc}")
                    except Exception as e_heap_row_proc: 
                        print(f"[{sid}]     MAJOR ERROR processing heap row: {e_heap_row_proc}")
                        # import traceback; traceback.print_exc() # For debugging

                    #keep track of for a particular desgination how many black and red emails found.    
                    if final_email_str_from_row and "@" in final_email_str_from_row:
                        num_results -= 1
                        emailcount += 1
                        found_flag_domain = True # At least one email found for this domain

                        if is_green_or_yellow_email_row : # If this if statement is not also there then also it is okay.
                            found_verified_email_domain = True
                        
                        emails_collected_for_this_title_run += 1
                        
                       
                        socketio.emit("progress_update", {"domain": domain_str_item, "message": f"EMAIL FOUND - {final_email_str_from_row} for {title_str_item}"}, room=sid)

                        # ADD EMAIL TO FILE_DATA FOR FINAL RESPONSE
                        email_record = {
                            "First Name": name_from_row,
                            "job title": jobtitle_from_row,
                            "company": company_from_row,
                            "location": location_from_row,
                            "email": final_email_str_from_row,
                            "domain": domain_str_item
                        }
                        file_data.append(email_record)

                        # ✅ EMIT PREVIEW DATA IN REAL-TIME
                        try:
                            state["preview_list"].append(email_record)
                            socketio.emit("preview_data", {"previewData": state["preview_list"]}, room=sid)
                            print(f"[{sid}]   ✅ Emitted preview_data. Total items in preview: {len(state['preview_list'])}")
                        except Exception as e_emit_preview:
                            print(f"[{sid}]   ⚠️ Error emitting preview_data: {e_emit_preview}")

                        print(f"[{sid}]   Record added. Email count for '{title_str_item}': {emails_collected_for_this_title_run}/{num_of_emails_needed_for_title}. Domain cap (num_results) left: {num_results}")
                    else:
                        invalid_email_count += 1
                        print(f"[{sid}]   No valid G/Y email found for this row after all attempts. Skipping record add.")
                        # Logic for file_data2 if last designation and no G/Y email from heap
                        if title_idx == len(designations) - 1 and not found_verified_email_domain: # Check found_verified_email_domain for G/Y specifically
                            # Check if this domain already has a "Not found" entry from this path
                            if not any(fd2_item['domain'] == domain_str_item and "Not found (heap path)" in fd2_item['email'] for fd2_item in file_data2):
                                print(f"[{sid}]     Heap: Last designation, no G/Y email from heap yet for domain '{domain_str_item}'. Adding to file_data2.")
                                heap_nf_rec = {
                                    "First Name": str(not_found_record_id), "job title": "N/A", "company": "N/A",
                                    "location": "N/A", "email": "Not found (heap path)", "domain": domain_str_item
                                }
                                file_data2.append(heap_nf_rec)
                                not_found_record_id += 1
                                state["preview_list"].append(heap_nf_rec)
                                try:
                                    socketio.emit("preview_data", {"previewData": state["preview_list"]}, room=sid)
                                except Exception as e_emit_preview_final:
                                    print(f"[{sid}] Error emitting preview data: {e_emit_preview_final}")
                
                await check_cancel(state, f"Finished heap for {domain_str_item}/{title_str_item}")
                print(f"[{sid}]\nFinished processing rows for title '{title_str_item}'. Total G/Y emails for this title run: {emails_collected_for_this_title_run}")
            
            # After all designations for a domain
            if not found_flag_domain: # If NO email of any kind was found for this domain
                print(f"[{sid}] No emails found for domain '{domain_str_item}' after all designations. Adding to file_data2.")
                if not any(fd2_item['domain'] == domain_str_item and "Not found" in fd2_item['email'] for fd2_item in file_data2): # Avoid duplicates
                    domain_nf_rec = {
                        "First Name": str(not_found_record_id), "job title": "N/A", "company": "N/A",
                        "location": "N/A", "email": "Not found (domain level)", "domain": domain_str_item
                    }
                    file_data2.append(domain_nf_rec)
                    not_found_record_id += 1
                    state["preview_list"].append(domain_nf_rec)
                    try:
                        socketio.emit("preview_data", {"previewData": state["preview_list"]}, room=sid)
                    except Exception as e_emit_preview_final:
                        print(f"[{sid}] Error emitting preview data: {e_emit_preview_final}")
            
            socketio.emit("progress_update", {"domain": domain_str_item, "message": "Domain processing finished."}, room=sid)
            # Remove successfully processed domain from 'domain_remaining'
            if domain_str_item in domain_remaining:
                try:
                    domain_remaining.remove(domain_str_item)
                    print(f"[{sid}] Removed processed domain '{domain_str_item}' from remaining list.")
                except ValueError:
                    pass # Should not happen if logic is correct
            await asyncio.sleep(0.01)

        
        if file_data: # Populated with successful G/Y email records
            df_successful_data = pd.DataFrame(file_data)
            state["df_list"].append(df_successful_data) # Storing in client's state
            print(f"[{sid}] Added {len(file_data)} successful records to state['df_list'].")

        if emailcount == 0 and domains: # If no emails were found in the entire run for any domain
            last_processed_domain_for_emit = domains[-1] if domains else "N/A"
            socketio.emit("progress_update", {"domain": last_processed_domain_for_emit, "message": "No emails found (overall process check)"}, room=sid)
            print(f"[{sid}] Overall process check: No emails found in this run.")


    except MySpecialError as e_ms:
        result_message = f"Process cancelled or special error: {str(e_ms)}"
        print(f"[{sid}] MySpecialError in handle_one_job: {e_ms}")
        socketio.emit("process_data_response", {"message": result_message, "error": "CancelledOrError"}, room=sid)
    except PlaywrightTimeoutError as pte:
        result_message = f"A timeout occurred during Playwright operation: {str(pte)}"
        print(f"[{sid}] !!! PlaywrightTimeoutError in handle_one_job: {pte}")
        socketio.emit("process_data_response", {"message": result_message, "error": "PlaywrightTimeout"}, room=sid)
    except PlaywrightError as pe:
        result_message = f"A Playwright error occurred: {str(pe)}"
        print(f"[{sid}] !!! PlaywrightError in handle_one_job: {pe}")
        socketio.emit("process_data_response", {"message": result_message, "error": "PlaywrightError"}, room=sid)
    except Exception as e_global:
        result_message = f"An unexpected error occurred: {str(e_global)}"
        import traceback
        traceback.print_exc()
        print(f"[{sid}] !!! An unexpected generic error occurred in handle_one_job: {e_global}")
        socketio.emit("process_data_response", {"message": result_message, "error": "UnexpectedError"}, room=sid)
    finally:
        print(f"[{sid}] Executing finally block for job...")
        
        if context:
            try:
                print(f"[{sid}] Closing browser context...")
                await context.close()
                print(f"[{sid}] Browser context closed successfully.")
            except Exception as e_context_close:
                print(f"[{sid}] Error closing browser context: {e_context_close}")
        
        state["current_page"] = None
        state["current_context"] = None

        # Add remaining (unprocessed/skipped) domains to df_list in state
        df_rem_data_final_style = []
        for d_rem_item_style in domain_remaining: # domain_remaining now only has skipped domains
            df_rem_data_final_style.append({"First Name": d_rem_item_style, "email": "Skipped/Not Processed", "domain": d_rem_item_style}) # Add more info
        
        if df_rem_data_final_style:
            df_remaining_obj_final = pd.DataFrame(df_rem_data_final_style)
            state["df_list"].append(df_remaining_obj_final)
            print(f"[{sid}] Added {len(df_rem_data_final_style)} remaining/skipped domains to state['df_list'].")
        
        
        # If it's not an error already emitted, send a success message.
        if "CancelledOrError" not in result_message and "PlaywrightTimeout" not in result_message and "PlaywrightError" not in result_message and "UnexpectedError" not in result_message:
             if not file_data and not file_data2 : # if no data was processed at all.
                result_message = "No prospects data found or processed based on criteria."
                socketio.emit('process_data_response', {
                    "message": result_message,
                    "error": "NoDataFound", # Custom error type
                }, room=sid)
             else:
                socketio.emit("process_data_response", {"message": result_message, "status": "completed"}, room=sid)


        # Always clear job_running so the client can submit again
        current_state = clients_state.get(sid)
        if current_state:
            current_state["job_running"] = False

        print(f"[{sid}] Job handle_one_job finished. Result message: {result_message}")
        if playwright_job_queue: playwright_job_queue.task_done() # Crucial: Signal completion to the queue

# --- Start the worker thread ---
def start_playwright_worker_thread():
    def run_loop():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(playwright_worker_main())
        except KeyboardInterrupt:
            print("Worker thread interrupted. Shutting down...")
        finally:
           
            loop.close()
            print("Worker thread event loop closed.")

    thread = threading.Thread(target=run_loop, daemon=True, name="PlaywrightWorkerThread")
    thread.start()
    print("→ Playwright worker thread started.")
    return thread

worker_thread = start_playwright_worker_thread()


# ───────────── 3) SOCKETIO EVENT HANDLERS ───────────────────────────────────
@app.route("/")
def index():
    return "Flask-SocketIO + Async Playwright Worker is UP."

@socketio.on("connect")
def on_connect():
    sid = request.sid
    clients_state[sid] = {
        "df_list": [],
        "preview_list": [],
        "cancel_process": False,
        "job_running": False,
        "current_context": None, # Will be set by handle_one_job
        "current_page": None,    # Will be set by handle_one_job
    }
    print(f"Client connected: {sid}")

@socketio.on("disconnect")
def on_disconnect():
    sid = request.sid
    print(f"Client disconnected: {sid}")
    state = clients_state.get(sid)
    if state:
        state["cancel_process"] = True # Signal cancellation to any running job
      
        if state.get("current_context"):
            print(f"[{sid}] Disconnect: current_context exists. Cancellation flag set. Worker will handle close.")
           

    clients_state.pop(sid, None)


@socketio.on("process_data")
def handle_process_data(payload):
    sid = request.sid
    state = clients_state.get(sid)
    if not state:
        emit("process_data_response", {"message": "Error: Client state not found. Please reconnect.", "error": "StateNotFound"}, room=sid)
        return

    # Guard against double-submit: reject if a job is already running
    if state.get("job_running"):
        emit("process_data_response", {"message": "A job is already running. Please wait or reset first.", "error": "JobAlreadyRunning"}, room=sid)
        return

    state["job_running"] = True
    # Reset cancellation & clear previous results for a new job
    state["cancel_process"] = False
    state["df_list"].clear()
    state["preview_list"].clear()
    # current_context/page are managed by handle_one_job, no need to clear here explicitly unless for sanity.
    state["current_context"] = None
    state["current_page"] = None


    try:
        domains_str = payload.get('domains', '')
        # Using original get_domain, ensure it's defined globally
        domains_list = [get_domain(d) for d in domains_str.splitlines() if d.strip() and get_domain(d)]


        designations_payload = payload.get('designations', '')
        # downloadFileName is used for Snov list name, not actual file download here
        downloadFileName_from_payload = payload.get('downloadFileName', '').strip() or 'Scraped_Prospects_List'
        
        designations_list_raw = [d.strip() for d in designations_payload.split(',') if d.strip()]
        
        location_payload = payload.get('location', '')
        location_list_parsed = [l.strip().lower() for l in location_payload.split(',') if l.strip()]
        location_list_parsed = [' '.join(l.split()) for l in location_list_parsed]


        array_data_str = payload.get('arrayData', '[]')
        num_results_from_payload = int(payload.get('numResults', 10)) # Default to 10 if not provided

        # Cookie parsing
        converted_cookies_list = []
        try:
            converted_cookies_list = json.loads(array_data_str)
            if not isinstance(converted_cookies_list, list):
                raise ValueError("Cookie data is not a list.")
        except Exception as e_cookie:
            emit('process_data_response', {"message": f"Invalid cookie data format: {e_cookie}", "error": "CookieParsingFailed"}, room=sid)
            return

        # Build required_counts and clean designations list
        required_counts_map = {}
        parsed_designations_list = []
        pattern = re.compile(r'^\s*(.+?)\s*(\d+)\s*$')
        for item_designation in designations_list_raw:
            match = pattern.search(item_designation)
            if match:
                designation_name = match.group(1).strip().lower() # Use lower for consistency
                count = int(match.group(2))
                parsed_designations_list.append(designation_name)
                required_counts_map[designation_name] = count
            else: # No count, just designation name
                parsed_designations_list.append(item_designation.strip().lower())
                # required_counts_map[item_designation.strip().lower()] = float('inf') # Or some default large number / handle in logic


        print(f"[{sid}] Job to queue: Domains: {len(domains_list)}, Designations: {parsed_designations_list}, Locations: {location_list_parsed}, Cookies: {len(converted_cookies_list)}")
        print(f"[{sid}] Required counts: {required_counts_map}")

        # Prepare job tuple for the worker
        job = (
            sid,
            domains_list,
            parsed_designations_list, # Send the cleaned list of designation names
            location_list_parsed,
            converted_cookies_list,
            required_counts_map, # Send the map
            num_results_from_payload,
            downloadFileName_from_payload
        )

        if playwright_job_queue is None or WORKER_EVENT_LOOP is None:
            emit("process_data_response", {"message": "Error: Worker queue not ready.", "error": "WorkerNotReady"}, room=sid)
            return

        # Enqueue job using the worker's event loop
        WORKER_EVENT_LOOP.call_soon_threadsafe(playwright_job_queue.put_nowait, job)
        
        emit("process_data_response", {"message": "Playwright job queued successfully."}, room=sid)

    except Exception as e_payload:
        print(f"[{sid}] Error processing payload for process_data: {e_payload}")
        import traceback
        traceback.print_exc()
        emit("process_data_response", {"message": f"Error in submitted data: {e_payload}", "error": "PayloadError"}, room=sid)


@socketio.on("refresh")
def handle_refresh():
    sid = request.sid
    state = clients_state.get(sid)
    if not state:
        return

    print(f"[{sid}] Refresh request received.")
    state["cancel_process"] = True  # Signal cancellation
    state["job_running"] = False     # Allow resubmission after reset

    if state.get("current_context"):
        print(f"[{sid}] Refresh: current_context exists. Cancellation flag set. Worker will handle close.")

    state["current_context"] = None
    state["current_page"] = None
    state["df_list"].clear()
    state["preview_list"].clear()

    emit("refresh_response", {"message": "Application state refreshed successfully. Ongoing process will be cancelled."}, room=sid)


# ─────────────────────────────────────────────────────────────────────────────
# 4) RUN THE SERVER
#─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import os
    is_debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    socketio.run(
        app,
        debug=is_debug,
        host="0.0.0.0",
        port=5003,
        allow_unsafe_werkzeug=True,
        use_reloader=False  # Important: Werkzeug reloader causes issues with threads/asyncio setup
    )
