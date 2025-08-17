#!/usr/bin/env python3
"""
This script reads a list of article titles from a file named `search_results.txt`,
logs into the configured MediaWiki site using Pywikibot, and deletes each page
along with any redirects that point to those pages.

Features:
- Interactive menu system to choose between Phase 1, Phase 2, or both
- Phase 1: Uses multithreading (25 threads) to find redirects and saves data to JSON
- Phase 2: Reads from saved JSON and processes deletions single-threaded with progress bar
- JSON output shows each page and all its redirects for review

Note: This script requires administrator privileges to delete pages.
"""

import pywikibot
from tqdm import tqdm
import concurrent.futures
import queue
import json

# Global queue to hold pages that need deletion
deletion_queue = queue.Queue()


def find_redirects_to_page(site, target_page_title):
    """
    Find all redirects that point to the target page.
    Returns a list of redirect page titles.
    """
    redirects = []
    try:
        target_page = pywikibot.Page(site, target_page_title)

        # Get all pages that link to this page
        referring_pages = target_page.getReferences(
            follow_redirects=False, filter_redirects=True
        )

        for referring_page in referring_pages:
            try:
                # Check if it's a redirect by examining the page text
                if referring_page.isRedirectPage():
                    redirect_target = referring_page.getRedirectTarget()
                    # Verify it redirects to our target page
                    if redirect_target.title() == target_page.title():
                        redirects.append(referring_page.title())
            except (
                pywikibot.exceptions.IsRedirectPageError,
                pywikibot.exceptions.NoPageError,
                pywikibot.exceptions.InvalidTitleError,
            ):
                # Skip problematic pages
                continue
            except Exception as e:
                tqdm.write(f"Error checking redirect {referring_page.title()}: {e}")
                continue

    except Exception as e:
        tqdm.write(f"Error finding redirects for {target_page_title}: {e}")

    return redirects


def check_page_edit_safety(site, page_title):
    """
    Check if a page has been edited only by CalvyBot or Calvy.
    Returns True if safe to delete (only edited by allowed users), False otherwise.
    """
    allowed_editors = {"CalvyBot", "Calvy"}

    try:
        page = pywikibot.Page(site, page_title)

        if not page.exists():
            return False  # Skip non-existent pages

        # Get page revision history
        revisions = page.revisions()

        # Check all editors
        for revision in revisions:
            editor = revision.user
            if editor and editor not in allowed_editors:
                return False  # Found unauthorized editor

        return True  # Only authorized editors found

    except Exception as e:
        tqdm.write(f"Error checking edit history for {page_title}: {e}")
        return False  # If can't check, err on the side of caution


def process_page_for_redirects(site, page_title):
    """
    Process a single page to find its redirects and add all to deletion queue.
    Only processes pages that have been edited exclusively by CalvyBot or Calvy.
    Returns tuple of (page_title, redirects_list, safety_status)
    """
    try:
        # First check if page is safe to delete (edit history check)
        is_safe = check_page_edit_safety(site, page_title)

        if not is_safe:
            tqdm.write(f"SKIPPED {page_title}: edited by unauthorized users")
            return (page_title, [], "SKIPPED_UNSAFE")

        # If safe, proceed with redirect finding
        redirects = find_redirects_to_page(site, page_title)

        # Add the main page to deletion queue
        deletion_queue.put(page_title)

        # Add all redirects to deletion queue
        for redirect in redirects:
            deletion_queue.put(redirect)

        return (page_title, redirects, "SAFE")

    except Exception as e:
        tqdm.write(f"Error processing {page_title}: {e}")
        return (page_title, [], "ERROR")


def process_deletion_queue(site, deletion_reason):
    """
    Process the deletion queue single-threaded with progress tracking.
    """
    queue_size = deletion_queue.qsize()
    successful_deletions = 0
    failed_deletions = 0

    with tqdm(total=queue_size, desc="Deleting pages") as pbar:
        while not deletion_queue.empty():
            page_title = deletion_queue.get()

            try:
                page = pywikibot.Page(site, page_title)

                if not page.exists():
                    tqdm.write(f"Skipping {page_title}: page does not exist")
                    continue

                # Delete the page
                page.delete(reason=deletion_reason, mark=True)
                successful_deletions += 1

            except pywikibot.exceptions.NoPageError:
                tqdm.write(f"Skipping {page_title}: page does not exist")
            except pywikibot.exceptions.LockedPageError:
                tqdm.write(f"Failed to delete {page_title}: page is protected")
                failed_deletions += 1
            except pywikibot.exceptions.PageNotSavedError as e:
                tqdm.write(f"Failed to delete {page_title}: {e}")
                failed_deletions += 1
            except pywikibot.exceptions.PermissionError:
                tqdm.write(f"Failed to delete {page_title}: insufficient permissions")
                failed_deletions += 1
            except Exception as e:
                error_msg = str(e)
                if "permission" in error_msg.lower() or "right" in error_msg.lower():
                    tqdm.write(
                        f"Failed to delete {page_title}: insufficient permissions - {e}"
                    )
                else:
                    tqdm.write(f"Failed to delete {page_title}: {e}")
                failed_deletions += 1
            finally:
                pbar.update(1)
                deletion_queue.task_done()

    return successful_deletions, failed_deletions


def save_redirect_data(redirect_data, filename="redirect_data.json"):
    """
    Save redirect data to JSON file.
    """
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(redirect_data, f, indent=2, ensure_ascii=False)
        print(f"Redirect data saved to {filename}")
    except Exception as e:
        print(f"Error saving redirect data: {e}")


def load_redirect_data(filename="redirect_data.json"):
    """
    Load redirect data from JSON file.
    """
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: {filename} not found. Please run Phase 1 first.")
        return None
    except Exception as e:
        print(f"Error loading redirect data: {e}")
        return None


def get_bot_capabilities():
    """
    Get the actual API capabilities and permissions of the current bot user.
    """
    try:
        site = pywikibot.Site()
        site.login()

        # Get user info
        user_info = site.userinfo
        username = site.username()

        # Get user rights
        user_rights = user_info.get("rights", [])

        # Get user groups
        user_groups = user_info.get("groups", [])

        return {"username": username, "rights": user_rights, "groups": user_groups}
    except Exception as e:
        return {"error": str(e), "username": "Unknown", "rights": [], "groups": []}


def show_main_menu():
    """
    Display main menu and get user choice.
    """
    print("\n" + "=" * 60)
    print("PAGE DELETION SCRIPT WITH REDIRECT DETECTION")
    print("=" * 60)

    # Get and display bot capabilities
    bot_info = get_bot_capabilities()

    print(f"\n🤖 BOT USER: {bot_info['username']}")
    print("━" * 40)

    if "error" in bot_info:
        print(f"❌ Error getting bot info: {bot_info['error']}")
    else:
        print(f"👥 USER GROUPS: {', '.join(bot_info['groups'])}")
        print("\n🔑 API PERMISSIONS:")
        if bot_info["rights"]:
            # Show important rights first
            important_rights = [
                "delete",
                "sysop",
                "bot",
                "autoconfirmed",
                "edit",
                "move",
                "upload",
            ]
            shown_rights = []

            for right in important_rights:
                if right in bot_info["rights"]:
                    if right == "delete":
                        print(f"   ✅ {right} - CAN DELETE PAGES")
                    elif right == "sysop":
                        print(f"   ✅ {right} - ADMINISTRATOR")
                    elif right == "bot":
                        print(f"   ✅ {right} - BOT ACCOUNT")
                    else:
                        print(f"   ✅ {right}")
                    shown_rights.append(right)

            # Show other rights
            other_rights = [r for r in bot_info["rights"] if r not in shown_rights]
            if other_rights:
                print(f"   📋 Other rights: {', '.join(other_rights)}")
        else:
            print("   ❌ No permissions found")

    print(f"\n   Total permissions: {len(bot_info.get('rights', []))}")

    print("\n📋 MENU OPTIONS:")
    print("━" * 40)
    print("1. Phase 1: Find redirects and save to JSON")
    print("   → Analyzes pages and creates 'redirect_data.json'")
    print("   → Safe to run multiple times, no deletions performed")

    print("\n2. Phase 2: Delete pages from saved JSON data")
    print("   → Requires 'redirect_data.json' from Phase 1")
    print("   → Deletes original pages + all discovered redirects")
    print("   → Requires administrator/delete permissions")

    print("\n3. Run both phases (Phase 1 + Phase 2)")
    print("   → Complete workflow: analyze then delete")
    print("   → Recommended for one-time bulk deletions")

    print("\n4. Exit")
    print("   → Quit the script safely")

    print("\n" + "=" * 60)
    print("⚠️  WARNING: Phase 2 requires administrator privileges!")
    print("📁 INPUT: Reads from 'search_results.txt'")
    print("💾 OUTPUT: Creates 'redirect_data.json' after Phase 1")
    print("=" * 60)

    while True:
        choice = input("\nEnter your choice (1-4): ").strip()
        if choice in ["1", "2", "3", "4"]:
            return choice
        print("❌ Invalid choice. Please enter 1, 2, 3, or 4.")


def phase_1():
    """
    Phase 1: Find redirects and save to JSON.
    """
    site = pywikibot.Site()
    site.login()

    try:
        with open("search_results.txt", encoding="utf-8") as f:
            titles = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print("Error: search_results.txt file not found.")
        return False

    if not titles:
        print("No pages found in search_results.txt")
        return False

    print(f"Found {len(titles)} pages to analyze for redirects.")

    print("\nPhase 1: Searching for redirects using 25 threads...")

    # Dictionary to store redirect data
    redirect_data = {}
    total_redirects_found = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=25) as executor:
        # Submit all tasks
        futures = {
            executor.submit(process_page_for_redirects, site, page_title): page_title
            for page_title in titles
        }

        # Process completed tasks with progress bar
        skipped_unsafe = 0
        processed_safe = 0

        for future in tqdm(
            concurrent.futures.as_completed(futures),
            total=len(futures),
            desc="Checking safety & finding redirects",
        ):
            try:
                page_title, redirects_list, safety_status = future.result()

                if safety_status == "SKIPPED_UNSAFE":
                    skipped_unsafe += 1
                    # Don't add unsafe pages to redirect_data
                    continue
                elif safety_status == "SAFE":
                    processed_safe += 1
                    redirect_data[page_title] = redirects_list
                    total_redirects_found += len(redirects_list)
                    if len(redirects_list) > 0:
                        tqdm.write(
                            f"Found {len(redirects_list)} redirects for: {page_title}"
                        )
                else:  # ERROR case
                    redirect_data[page_title] = []

            except Exception as e:
                page_title = futures[future]
                tqdm.write(f"Error processing {page_title}: {e}")
                redirect_data[page_title] = []

    print("\nPhase 1 complete!")
    print("📊 SAFETY CHECK RESULTS:")
    print(f"   ✅ Safe pages (CalvyBot/Calvy only): {processed_safe}")
    print(f"   ⚠️  Skipped unsafe pages: {skipped_unsafe}")
    print(f"   🔗 Total redirects found: {total_redirects_found}")
    print(f"   📁 Pages to be saved to JSON: {len(redirect_data)}")

    # Save redirect data to JSON
    save_redirect_data(redirect_data)

    return True


def phase_2():
    """
    Phase 2: Delete pages from saved JSON data.
    """
    site = pywikibot.Site()
    site.login()

    print("Warning: This phase requires administrator/delete permissions.")
    print(
        "If you don't have delete rights, the script will fail gracefully for each page."
    )

    # Load redirect data from JSON
    redirect_data = load_redirect_data()
    if redirect_data is None:
        return False

    # Clear the deletion queue and populate from JSON data
    while not deletion_queue.empty():
        deletion_queue.get()

    total_pages = 0
    for page_title, redirects in redirect_data.items():
        deletion_queue.put(page_title)
        total_pages += 1
        for redirect in redirects:
            deletion_queue.put(redirect)
            total_pages += 1

    print(f"Loaded data for {len(redirect_data)} main pages.")
    print(f"Total pages to delete: {total_pages}")

    confirm = input(
        "Are you sure you want to delete these pages and their redirects? (yes/no): "
    )
    if confirm.lower() != "yes":
        print("Operation cancelled.")
        return False

    deletion_reason = input(
        "Enter deletion reason (or press Enter for default): "
    ).strip()
    if not deletion_reason:
        deletion_reason = "Batch deletion via script (including redirects)"

    print("\nPhase 2: Processing deletions single-threaded...")

    # Process deletions single-threaded
    successful_deletions, failed_deletions = process_deletion_queue(
        site, deletion_reason
    )

    print("\nDeletion complete!")
    print(f"Successfully deleted: {successful_deletions} pages")
    print(f"Failed deletions: {failed_deletions} pages")

    return True


def main():
    """
    Main function with menu system.
    """
    while True:
        choice = show_main_menu()

        if choice == "1":
            phase_1()
        elif choice == "2":
            phase_2()
        elif choice == "3":
            if phase_1():
                print("\nPhase 1 completed successfully. Starting Phase 2...")
                phase_2()
        elif choice == "4":
            print("Exiting...")
            break

        print("\nReturning to main menu...")
        input("Press Enter to continue...")


if __name__ == "__main__":
    main()
