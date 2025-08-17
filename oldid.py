import pywikibot
from pywikibot import pagegenerators
from concurrent.futures import ThreadPoolExecutor, as_completed
import queue
import time
from tqdm import tqdm
import re  # Add this import

# Define the template strings to check for
TEMPLATE_STRING = '{{Page version|41.78.16}}'
PAGE_VERSION_TEMPLATE = '{{Page version'
REVISION_PARAM = '|2='
QUEUE_FILE = 'search_results.txt'
BLACKLIST_FILE = 'revision_blacklist.txt'
BATCH_SIZE = 50

def check_article(page):
    """
    Check if a given Wikipedia page contains a specific template.

    Args:
        page (pywikibot.Page): The Wikipedia page to check.

    Returns:
        str or None: The title of the page if it needs processing, or None otherwise.
    """
    try:
        if page.isRedirectPage() or "/" in page.title() or "(disambiguation)" in page.title():
            return None
        text = page.get()
        if PAGE_VERSION_TEMPLATE not in text:
            return None
        if TEMPLATE_STRING not in text:
            return page.title()
    except Exception as e:
        print(f"Error processing page {page.title()}: {e}")
    return None

def process_queue(q, site, pbar):
    """
    Process pages in the queue, updating their templates with revision IDs.

    Args:
        q (queue.Queue): Queue containing page titles to process.
        site (pywikibot.Site): The Pywikibot site object.
        pbar (tqdm.tqdm): Progress bar to track processing progress.
    """
    while not q.empty():
        page_title = q.get()
        pbar.update(1)
        page = pywikibot.Page(site, page_title)
        try:
            text = page.get()
            revision_id = find_revision_with_template(page)
            if revision_id:
                updated_text = update_template(text, revision_id)
                if updated_text != text:
                    page.put(updated_text, "Added revision ID to page version.")
                    time.sleep(6)  # Rate limit of 6 seconds
        except Exception as e:
            print(f"Error processing page {page_title}: {e}")

def find_revision_with_template(page):
    """
    Find a revision containing the specific template on a given page.

    Args:
        page (pywikibot.Page): The Wikipedia page to check.

    Returns:
        int or None: The revision ID if found, or None otherwise.
    """
    for revision in page.revisions(total=1000):
        rev_text = page.getOldVersion(revision.revid)
        if TEMPLATE_STRING in rev_text:
            return revision.revid
    return None

def update_template(text, revision_id):
    """
    Update the template in the page text with the given revision ID.

    Args:
        text (str): The current page text.
        revision_id (int): The revision ID to insert into the template.

    Returns:
        str: The updated page text.
    """
    start_idx = text.find('{{Page version|')
    if start_idx == -1:
        return text
    end_idx = text.find('}}', start_idx)
    if end_idx == -1:
        return text

    template = text[start_idx:end_idx + 2]

    if REVISION_PARAM in template:
        updated_template = re.sub(r'(\|2=)\d+', f'|2={revision_id}', template)
    else:
        updated_template = template[:-2] + f'|2={revision_id}}}}}'

    return text.replace(template, updated_template)

def save_queue_to_file(q, filename):
    """
    Save all items in a queue to a file.

    Args:
        q (queue.Queue): Queue containing items to save.
        filename (str): The file path to save the queue.
    """
    with open(filename, 'w', encoding='utf-8') as f:
        while not q.empty():
            f.write(q.get() + '\n')

def append_queue_to_file(batch, filename):
    """
    Append a batch of items to a file.

    Args:
        batch (list): List of items to append.
        filename (str): The file path to append the items.
    """
    with open(filename, 'a', encoding='utf-8') as f:
        for title in batch:
            f.write(title + '\n')

def load_queue_from_file(filename):
    """
    Load items from a file into a queue, using UTF-8 encoding.

    Args:
        filename (str): The file path to load items from.

    Returns:
        queue.Queue: A queue populated with items from the file.
    """
    q = queue.Queue()
    with open(filename, 'r', encoding='utf-8') as f:
        for line in f:
            q.put(line.strip())
    return q


def load_blacklist(filename):
    """
    Load a set of blacklisted items from a file.

    Args:
        filename (str): The file path to load blacklisted items from.

    Returns:
        set: A set of blacklisted items.
    """
    blacklist = set()
    with open(filename, 'r') as f:
        for line in f:
            blacklist.add(line.strip())
    return blacklist

def filter_queue(q, blacklist):
    """
    Filter a queue to exclude blacklisted items.

    Args:
        q (queue.Queue): The original queue.
        blacklist (set): Set of blacklisted items.

    Returns:
        queue.Queue: A filtered queue excluding blacklisted items.
    """
    filtered_q = queue.Queue()
    remaining_titles = []

    while not q.empty():
        item = q.get()
        if item not in blacklist:
            filtered_q.put(item)
            remaining_titles.append(item)

    # Rewrite the revision list file without blacklisted articles
    with open(QUEUE_FILE, 'w', encoding='utf-8') as f:
        for title in remaining_titles:
            f.write(title + '\n')

    return filtered_q

def main():
    """
    Main function to manage the workflow of the script.

    It allows the user to create a queue of articles or use an existing queue file,
    applies a blacklist to filter the queue, and processes articles to update templates.
    """
    site = pywikibot.Site()
    site.login()

    print("Please choose a starting option:")
    print("1. Create queue")
    print("2. Use queue file")

    choice = input("Enter 1 or 2: ").strip()
    if choice == '1':
        q = queue.Queue()
        gen = pagegenerators.AllpagesPageGenerator(namespace=0, site=site)
        pages = list(gen)

        # Clear the file at the start
        open(QUEUE_FILE, 'w').close()

        batch = []
        with ThreadPoolExecutor(max_workers=75) as executor:
            futures = {executor.submit(check_article, page): page for page in pages}
            for future in tqdm(as_completed(futures), total=len(futures), desc="Checking Articles"):
                result = future.result()
                if result:
                    q.put(result)
                    batch.append(result)
                    if len(batch) >= BATCH_SIZE:
                        append_queue_to_file(batch, QUEUE_FILE)
                        batch = []

        # Append any remaining titles in the last batch
        if batch:
            append_queue_to_file(batch, QUEUE_FILE)

    elif choice == '2':
        q = load_queue_from_file(QUEUE_FILE)

    else:
        print("Invalid choice. Please enter 1 or 2.")
        return

    # Load blacklist and filter the queue
    blacklist = load_blacklist(BLACKLIST_FILE)
    q = filter_queue(q, blacklist)

    # Process the queue with a progress bar
    with tqdm(total=q.qsize(), desc="Processing Queue") as pbar:
        process_queue(q, site, pbar)

if __name__ == "__main__":
    main()
