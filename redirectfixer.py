#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
This Pywikibot script reads a CSV file containing item names and their respective
redirect targets. It processes each row, excluding the first row, and checks for
existing pages corresponding to the redirect targets. If the page exists but does
not redirect to the target, the script updates the page with a redirect. If the page
does not exist, it creates a new page with the redirect. A 6-second rate limit is
applied between edits where changes are made. The script uses a progress bar
(tqdm) to indicate progress.

Exclusion criteria:
- Skip columns that contain certain unwanted strings.
- Only process rows that don't have blank values or certain excluded phrases.
"""

import pywikibot
import csv
import time
from tqdm import tqdm

# Constants for exclusion
EXCLUDED_STRINGS = [
    'See [[#Variants|Variants]]',
    'Base.VHS_Home',
    'Base.VHS_Retail',
    'Base.Disc_Retail'
]


# Function to process each row in the CSV
def process_csv(site):
    with open('item_id_dictionary.csv', newline='', encoding='utf-8') as csvfile:
        csv_reader = csv.reader(csvfile)
        next(csv_reader)  # Skip the first row (header)

        # Create a progress bar for the number of rows
        rows = list(csv_reader)  # Load all rows first
        total_articles = sum(len(row[1:]) for row in rows)  # Count how many columns we need to process
        progress_bar = tqdm(total=total_articles, desc="Processing redirects")

        # Iterate over each row (excluding the first header row)
        for row in rows:
            base_page = row[0].strip()  # The base page we want to redirect to

            # Process each column after the first
            for column in row[1:]:
                progress_bar.update(1)  # Update the progress bar

                column = column.strip()

                # Skip blank columns or excluded strings
                if not column or any(excluded in column for excluded in EXCLUDED_STRINGS):
                    continue

                # Remove everything before the last '.' if it exists
                if '.' in column:
                    column = column.split('.')[-1]

                # Check if the page exists
                page = pywikibot.Page(site, column)
                original_text = page.text

                replaced_text = f'#REDIRECT [[{base_page}]]'
                # If the page doesn't exist, create it with a redirect
                if not page.exists():
                    page.text = f'#REDIRECT [[{base_page}]]'
                    page.save(summary='Redirect fix', tags="bot")
                    time.sleep(6)  # Rate limit
                else:
                    # If the page exists, check if it contains a redirect
                    if '#REDIRECT' in page.text and page.text != replaced_text and "disambiguation" not in page.text:
                        # Replace the content with the redirect
                        page.text = f'#REDIRECT [[{base_page}]]'
                        page.save(summary='Redirect fix', tags="bot")
                        time.sleep(6)  # Rate limit
                    else:
                        continue

        progress_bar.close()


# Main function for the script
def main():
    # Log in to the wiki
    site = pywikibot.Site()
    site.login()

    # Call the CSV processing function
    process_csv(site)


# Ensure the script is executed only if it's the main module
if __name__ == "__main__":
    main()
