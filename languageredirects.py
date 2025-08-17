import pywikibot
import concurrent.futures
from tqdm import tqdm
import time
import re


# Function to check for illegal characters in a title
def has_illegal_chars(title):
    illegal_chars = ['{', '}', '[', ']', '<', '>', '|', ':', '?', '*', '"', '\\', '/', '#', '@', '&', '%']
    return any(char in title for char in illegal_chars)


# Function to process each line from the file
def process_line(line, site, redirect_dict):
    page = pywikibot.Page(site, line.strip())
    if not page.exists():
        return
    text = page.text
    for line in text.splitlines():
        if line.startswith("{{Title|"):
            title_value = line[8:-2].strip()  # Extract the value from {{Title|XYZ}}
            if not has_illegal_chars(title_value):  # Skip if title contains illegal characters
                redirect_dict[page.title()] = title_value
            break


# Function to create redirects
def create_redirect(site, title, target):
    if has_illegal_chars(target):
        return  # Skip if the target title contains illegal characters

    redirect_page = pywikibot.Page(site, target)
    if not redirect_page.exists():
        content = f"#REDIRECT [[{title}]]"
        redirect_page.text = content
        redirect_page.save(summary="Create language redirect", tags="bot")
        time.sleep(10)  # Rate limit after edit


def main():
    # Log in to the site
    site = pywikibot.Site()
    site.login()

    # Initialize dictionary to store redirects
    redirect_dict = {}

    # Read lines from the file and process them using multithreading
    with open("search_results.txt", "r", encoding="utf-8") as file:
        lines = file.readlines()

    with concurrent.futures.ThreadPoolExecutor(max_workers=30) as executor:
        futures = [executor.submit(process_line, line, site, redirect_dict) for line in lines]
        for future in tqdm(concurrent.futures.as_completed(futures), total=len(futures), desc="Processing articles"):
            future.result()

    # Remove dictionary entries with duplicate values
    unique_redirect_dict = {k: v for k, v in redirect_dict.items() if list(redirect_dict.values()).count(v) == 1}

    # Create redirects for remaining entries
    for page_name, target in tqdm(unique_redirect_dict.items(), desc="Creating redirects"):
        create_redirect(site, page_name, target)


if __name__ == "__main__":
    main()
