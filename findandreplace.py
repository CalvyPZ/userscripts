import pywikibot
from tqdm import tqdm
import time
import concurrent.futures
import queue

# Queue to hold pages that need editing
edit_queue = queue.Queue()


def find_and_replace(site, page_title, mappings):
    try:
        page = pywikibot.Page(site, page_title)
        if not page.exists():
            print(f"Page {page_title} does not exist.")
            return None

        text = page.text
        original_text = text[:]

        for phrase, replacement in mappings.items():
            text = text.replace(phrase, replacement)

        if text != original_text:
            # Add the page title to the queue if it needs editing
            return page_title
        return None

    except Exception as e:
        print(f"An error occurred while checking {page_title}: {e}")
        return None


def process_edit_queue(site, mappings):
    queue_size = edit_queue.qsize()  # Get the initial size of the queue
    with tqdm(total=queue_size, desc="Processing edit queue") as pbar:
        while not edit_queue.empty():
            page_title = edit_queue.get()
            try:
                page = pywikibot.Page(site, page_title)
                if page.exists():
                    text = page.text
                    original_text = text[:]

                    for phrase, replacement in mappings.items():
                        text = text.replace(phrase, replacement)

                    if text != original_text:
                        page.text = text
                        page.save(summary="update research recipe wording.", minor=True, tags="bot")

                pbar.update(1)  # Update progress bar after each processed page

            except Exception as e:
                print(f"An error occurred while processing {page_title}: {e}")
            finally:
                edit_queue.task_done()


def main():
    site = pywikibot.Site()
    site.login()

    mappings = {
        "[[Carbonated Water (fluid)|carbonated water]]": "[[Seltzer Water (fluid)|seltzer water]]",
        "[[Carbonated Water (fluid|carbonated water]]": "[[Seltzer Water (fluid)|seltzer water]]",
        "[[Tainted Water (fluid)|tainted water]]": "[[Water (Tainted) (fluid)|tainted water]]",
    }

    try:
        with open("search_results.txt", "r", encoding='utf-8') as file:
            pages = file.readlines()
            pages = [page.strip() for page in pages]

        # Using ThreadPoolExecutor for multithreading
        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
            futures = {executor.submit(find_and_replace, site, page_title, mappings): page_title for page_title in pages}

            # Wait for all threads to finish and collect the results
            for future in tqdm(concurrent.futures.as_completed(futures), total=len(futures), desc="Checking pages"):
                result = future.result()
                if result:  # If a page needs editing, add it to the queue
                    edit_queue.put(result)

        # Sort the queue alphabetically
        sorted_pages = sorted(list(edit_queue.queue))

        # Clear the queue and re-populate with sorted items
        while not edit_queue.empty():
            edit_queue.get()

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
