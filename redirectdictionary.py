#!/usr/bin/env python3
"""
This script reads a list of Wikipedia article titles from a file called 'search_results.txt'.
For each article, it retrieves all the redirect pages that link to it, and stores them in a dictionary
where the key is the original page name and the value is a list of redirect pages. The final output is
written in both CSV and JSON formats. The script uses the Pywikibot library to interact with Wikipedia
and includes a progress bar to show the total progress of processed articles. The script utilizes
concurrent futures to process articles in parallel using 75 threads.
"""

import pywikibot
import csv
import json
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed

def process_article(site, title):
    """
    Function to process a single article and return the article's title and its redirects.
    """
    title = title.strip()  # Clean up the title
    if not title:
        return title, []  # Skip empty titles

    # Get the page object
    page = pywikibot.Page(site, title)

    # Fetch the list of redirects pointing to the current page
    try:
        redirects = page.backlinks(filter_redirects=True)
        redirect_list = [redirect.title() for redirect in redirects]
    except Exception as e:
        print(f"Error processing page {title}: {e}")
        redirect_list = []

    return title, redirect_list

def main():
    # Login to the site (no parameters required with site.login())
    site = pywikibot.Site()
    site.login()

    # Initialize an empty dictionary to store the results
    redirect_dict = {}

    # Open the file with the list of article titles
    with open('search_results.txt', 'r', encoding='utf-8') as file:
        article_titles = file.readlines()

    # Initialize a progress bar with tqdm for the total amount of articles
    with tqdm(total=len(article_titles), desc="Processing articles") as pbar:
        # Using ThreadPoolExecutor for parallel processing with 75 threads
        with ThreadPoolExecutor(max_workers=75) as executor:
            # Create a list to store the futures
            futures = {executor.submit(process_article, site, title): title for title in article_titles}

            # As each future completes, we update the dictionary and progress bar
            for future in as_completed(futures):
                title, redirect_list = future.result()  # Get the result of the completed future
                if title:
                    redirect_dict[title] = redirect_list  # Save the results in the dictionary
                pbar.update(1)

    # Output results to CSV file
    with open('redirects.csv', 'w', newline='', encoding='utf-8') as csv_file:
        writer = csv.writer(csv_file)
        # Write header row
        writer.writerow(['Page Name', 'Redirect 1', 'Redirect 2', 'Redirect 3', '...'])
        # Write each page and its redirects
        for page_name, redirects in redirect_dict.items():
            writer.writerow([page_name] + redirects)

    # Output results to JSON file
    with open('redirects.json', 'w', encoding='utf-8') as json_file:
        json_output = []
        for page_name, redirects in redirect_dict.items():
            json_output.append({
                "page": page_name,
                "redirects": redirects
            })
        json.dump(json_output, json_file, ensure_ascii=False, indent=4)

if __name__ == '__main__':
    main()
