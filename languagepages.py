import os
import pywikibot
from tqdm import tqdm
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

def main():
    site = pywikibot.Site()
    site.login()

    language_code = input("Enter the language code you want to upload: ").strip()
    articles_dir = f"/mnt/data/wiki/pz-wiki_parser/output/{language_code}/articles"

    if not os.path.exists(articles_dir):
        print(f"Directory {articles_dir} does not exist. Exiting.")
        return

    wiki_code = input("Enter the wiki code to upload under: ").strip()

    search_results_file = "search_results.txt"
    failed_pages_file = "failed_language_pages.txt"

    if not os.path.isfile(search_results_file):
        print(f"File {search_results_file} does not exist. Exiting.")
        return

    with open(search_results_file, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]

    queue = []

    # Multithreaded pre-check phase with progress bar
    print("Checking for existing pages and filtering...")
    with tqdm(total=len(lines), desc="Checking pages") as pbar:
        with ThreadPoolExecutor(max_workers=75) as executor:
            futures = {
                executor.submit(filter_and_check_page, site, article_title, wiki_code, failed_pages_file): article_title
                for article_title in lines
            }
            for future in as_completed(futures):
                result = future.result()
                if result:  # Only add to queue if the result is not None
                    queue.append(result)
                pbar.update(1)

    # Processing the queue
    print(f"Processing {len(queue)} articles...")
    with tqdm(total=len(queue), desc="Processing articles") as pbar:
        for article_title in queue:
            process_article(site, article_title, wiki_code, articles_dir)
            pbar.update(1)


def filter_and_check_page(site, article_title, wiki_code, failed_pages_file):
    # List of keywords to check for partial matches anywhere in the page content
    keywords_to_skip = [
        "{{obsolete}}", "{{archive}}", "{{delete}}", "{{deletion}}",
        "{{wip}}", "{{underconstruction}}", "Base.Disc_", "Base.VHS_"
    ]

    try:
        page = pywikibot.Page(site, article_title)
        text = page.text.lower()

        # Check if any of the keywords exist as a substring in the page text
        if any(keyword.lower() in text for keyword in keywords_to_skip):
            print(f"Skipping {article_title} due to presence of keywords.")
            return None

        # Extract the item_id from the page content
        item_id = None
        for line in text.splitlines():
            if "|item_id=" in line:
                item_id = line.split("=", 1)[1].strip()
                break

        # Check if the page with the new title already exists
        new_page_title = f"{article_title}/{wiki_code}"
        new_page = pywikibot.Page(site, new_page_title)
        if new_page.exists():
            with open(failed_pages_file, 'a', encoding='utf-8') as failed_file:
                failed_file.write(f"{article_title}/{wiki_code}\n")
            return None

        return article_title

    except Exception as e:
        print(f"Error checking page {article_title}: {e}")
        return None



def process_article(site, article_title, wiki_code, articles_dir):
    try:
        # Load the page from the wiki
        page = pywikibot.Page(site, article_title)
        text = page.text

        # Extract the item_id from the page content
        item_id = None
        for line in text.splitlines():
            if "|item_id=" in line:
                item_id = line.split("=", 1)[1].strip()
                break

        # Find the corresponding article file
        article_file = os.path.join(articles_dir, f"{item_id}.txt")
        if not os.path.isfile(article_file):
            print(f"Article file for item_id {item_id} not found, skipping.")
            return

        # Load the content of the new article
        with open(article_file, 'r', encoding='utf-8') as article_f:
            new_text = article_f.read()

        # Replace the model and icon lines in the new page with those from the original page
        new_text = replace_model_icon(text, new_text)

        # Create the new page with the modified content
        new_page = pywikibot.Page(site, f"{article_title}/{wiki_code}")
        new_page.text = new_text
        new_page.save(summary="Automated language page creation", tags="bot")

        # Rate limiting
        time.sleep(8)
    except Exception as e:
        print(f"Error processing {article_title}: {e}")

def replace_model_icon(old_text, new_text):
    def get_line_value(text, key):
        for line in text.splitlines():
            if line.startswith(key):
                return line
        return None

    # Extract the model and icon lines from the old text
    old_model_line = get_line_value(old_text, "|model=")
    old_icon_line = get_line_value(old_text, "|icon=")

    new_text_lines = new_text.splitlines()

    # Only replace the model line if it exists in the old text
    if old_model_line:
        new_text_lines = [
            old_model_line if line.startswith("|model=") else line
            for line in new_text_lines
        ]
    else:
        # If no model is found in the old text, remove the model line from the new text
        new_text_lines = [
            line for line in new_text_lines if not line.startswith("|model=")
        ]

    # Always replace the icon line if found in the old text
    if old_icon_line:
        new_text_lines = [
            old_icon_line if line.startswith("|icon=") else line
            for line in new_text_lines
        ]

    return "\n".join(new_text_lines)


if __name__ == "__main__":
    main()
