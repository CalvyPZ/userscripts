import pywikibot
from tqdm import tqdm
import time
import concurrent.futures
import queue
import re

# Queue to hold pages that need editing
edit_queue = queue.Queue()


def apply_mappings(text, mappings):
    """
    Apply all (pattern -> replacement) mappings using regex.
    This function will use re.sub with DOTALL so '.' matches across lines.
    If you don't need '.' to match newlines, you could use re.MULTILINE or no flag.
    """
    for pattern, replacement in mappings.items():
        # If you want literal matching (where pattern is not a regex):
        #   pattern = re.escape(pattern)
        #
        # By default, we assume the pattern is a valid regex.
        text = re.sub(pattern, replacement, text, flags=re.DOTALL)
    return text


def find_and_replace(site, page_title, mappings):
    """
    Checks the page for any text changes (based on regex patterns),
    and returns the page title if an edit is needed.
    """
    try:
        page = pywikibot.Page(site, page_title)
        if not page.exists():
            print(f"Page {page_title} does not exist.")
            return None

        original_text = page.text
        new_text = apply_mappings(original_text, mappings)

        # Return the page title if changes are found
        if new_text != original_text:
            return page_title
        return None

    except Exception as e:
        print(f"An error occurred while checking {page_title}: {e}")
        return None


def process_edit_queue(site, mappings):
    """
    Pull pages from the queue, apply the mappings, and save the changes.
    Uses a progress bar to track queue processing.
    """
    queue_size = edit_queue.qsize()  # Get the initial size of the queue
    with tqdm(total=queue_size, desc="Processing edit queue") as pbar:
        while not edit_queue.empty():
            page_title = edit_queue.get()
            try:
                page = pywikibot.Page(site, page_title)
                if page.exists():
                    original_text = page.text
                    new_text = apply_mappings(original_text, mappings)

                    if new_text != original_text:
                        page.text = new_text
                        page.save(summary="add context to recipes.",
                                  minor=True, tags="bot")

                pbar.update(1)

            except Exception as e:
                print(f"An error occurred while processing {page_title}: {e}")
            finally:
                edit_queue.task_done()


def main():
    site = pywikibot.Site()
    site.login()

    mappings = {
        re.escape('''==Obtaining==
===Recipes===
{{Crafting/sandbox|'''): r'''==Obtaining==
===Recipes===
It is a product in the following recipes.
{{Crafting/sandbox|''',
        re.escape('''==Obtaining==
===Recipes===
It is a product in the following recipes.s
{{Crafting/sandbox|'''): r'''==Obtaining==
===Recipes===
It is a product in the following recipes.
{{Crafting/sandbox|''',
    }

    try:
        with open("search_results.txt", "r", encoding='utf-8') as file:
            pages = [page.strip() for page in file.readlines()]

        # Using ThreadPoolExecutor for multi-threaded find/check
        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
            futures = {
                executor.submit(find_and_replace, site, page_title, mappings): page_title
                for page_title in pages
            }

            # Collect results and add to queue if changes are needed
            for future in tqdm(concurrent.futures.as_completed(futures),
                               total=len(futures),
                               desc="Checking pages"):
                result = future.result()
                if result:
                    edit_queue.put(result)

        # Sort the queue alphabetically
        sorted_pages = sorted(list(edit_queue.queue))
        # Clear the queue
        while not edit_queue.empty():
            edit_queue.get()
        # Re-populate the queue with sorted items
        for page in sorted_pages:
            edit_queue.put(page)

        # Process the queue single-threaded with rate-limiting
        print("Processing edit queue...")
        process_edit_queue(site, mappings)

    except FileNotFoundError:
        print("search_results.txt file not found.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


if __name__ == "__main__":
    main()
