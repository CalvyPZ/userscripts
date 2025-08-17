#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
This script logs into a MediaWiki site using Pywikibot, checks a list of article names from a file,
and processes each article to check if any subpages in different languages need header replacements.
The articles that need edits are gathered into a queue using multithreading, and then processed
one-by-one in a single-threaded manner. A rate limit is applied only if an edit is made.
"""

import pywikibot
from pywikibot import Page
import concurrent.futures
from tqdm import tqdm
import time

# Define the languages to check for subpages
language_codes = ['tr', 'it', 'th', 'hu', 'th', 'ru', 'uk', 'no', 'pl', 'pt', 'pt-br', 'fr', 'de', 'cs', 'es', 'ja', 'nl']

def check_page_for_edits(site, article_title):
    """Check if a page or its subpages need header editing."""
    page = Page(site, article_title)

    if not page.exists():
        return None  # No need to process non-existing articles

    try:
        # Get the original article content
        original_content = page.text

        # Find the header line that starts with "{{Header|"
        original_header_line = None
        for line in original_content.splitlines():
            if line.startswith('{{Header|'):
                original_header_line = line
                break

        if not original_header_line:
            return None  # Skip if no header is found

        # Check for subpages in different languages
        pages_to_edit = []
        for lang_code in language_codes:
            subpage_title = f"{article_title}/{lang_code}"
            subpage = Page(site, subpage_title)

            if subpage.exists():
                subpage_content = subpage.text
                subpage_header_line = None

                # Find the header line in the subpage
                for line in subpage_content.splitlines():
                    if line.startswith('{{Header|'):
                        subpage_header_line = line
                        break

                # If the subpage header is different, mark it for editing
                if subpage_header_line and subpage_header_line != original_header_line:
                    pages_to_edit.append((subpage, original_header_line))

        return pages_to_edit if pages_to_edit else None

    except Exception as e:
        print(f"Error checking article '{article_title}': {e}")
        return None


def process_queue(queue):
    """Process each page that requires header editing."""
    for subpage, original_header_line in tqdm(queue, desc="Processing edits"):
        try:
            subpage_content = subpage.text
            subpage_header_line = None

            # Find the existing header line
            for line in subpage_content.splitlines():
                if line.startswith('{{Header|'):
                    subpage_header_line = line
                    break

            # Replace the header if necessary
            if subpage_header_line and subpage_header_line != original_header_line:
                new_content = subpage_content.replace(subpage_header_line, original_header_line)
                subpage.text = new_content
                subpage.save(summary="Header replacement.", tags="bot")
                time.sleep(6)  # Rate limit after edit
        except Exception as e:
            print(f"Error processing subpage '{subpage.title()}': {e}")


def main():
    # Login to the site
    site = pywikibot.Site()
    site.login()

    # Open the file with the list of articles
    with open('search_results.txt', 'r', encoding='utf-8') as file:
        article_titles = [line.strip() for line in file if line.strip()]

    # Create a thread pool to check which pages need editing
    pages_to_edit_queue = []

    print("Checking pages for edits...")

    # Use concurrent futures to check each page with 75 threads
    with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
        futures = {executor.submit(check_page_for_edits, site, title): title for title in article_titles}

        # Gather results as they are completed
        for future in tqdm(concurrent.futures.as_completed(futures), total=len(futures), desc="Checking pages"):
            result = future.result()
            if result:
                pages_to_edit_queue.extend(result)

    # Process the queue single-threaded
    if pages_to_edit_queue:
        print(f"Found {len(pages_to_edit_queue)} subpages to edit. Starting edit process...")
        process_queue(pages_to_edit_queue)
    else:
        print("No pages require editing.")


if __name__ == "__main__":
    main()
