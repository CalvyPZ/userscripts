import os
import re
import json
import time
import pywikibot
from pywikibot import pagegenerators
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
from tqdm import tqdm

# ---------------------------
# File & Cache Validity Helpers
# ---------------------------
def is_file_valid(file_path, max_age_seconds):
    """Return True if file_path exists and is less than max_age_seconds old."""
    if not os.path.exists(file_path):
        return False
    mod_time = os.path.getmtime(file_path)
    return (time.time() - mod_time) < max_age_seconds

def is_cache_valid(cache_file, max_age_seconds=86400):
    """Cache is valid if the file exists and is less than 4 hours old."""
    return is_file_valid(cache_file, max_age_seconds)

def is_wiki_directory_valid(directory_file, max_age_seconds=86400):
    """Wiki directory is valid if the file exists and is less than 48 hours old."""
    return is_file_valid(directory_file, max_age_seconds)

def load_cache(cache_file):
    """Load the wiki cache dictionary from cache_file."""
    with open(cache_file, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_cache(cache, cache_file):
    """Save the wiki cache dictionary to cache_file."""
    with open(cache_file, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False)

# ---------------------------
# Wiki Directory Creation
# ---------------------------
def update_wiki_directory(site, directory_file):
    """
    Generate a wiki directory file (one title per line) for pages in the main namespace.
    This function writes to directory_file.
    """
    # For efficiency, we iterate only over the main namespace.
    with open(directory_file, 'w', encoding='utf-8') as f:
        for page in site.allpages(namespace=0, total=None, filterredir=False):
            f.write(page.title() + "\n")

# ---------------------------
# Wiki Cache Functions
# ---------------------------
def load_batch(batch, site):
    """
    Given a list of page titles (batch) and a site object, preload pages using
    PreloadingGenerator (groupsize=500) and return a dictionary mapping titles to text.
    """
    pages = [pywikibot.Page(site, title) for title in batch]
    preloaded_gen = pagegenerators.PreloadingGenerator(pages, groupsize=500)
    return {page.title(): page.text for page in preloaded_gen}

def update_wiki_cache(site, all_titles, cache_file):
    """
    Update the wiki cache by splitting all_titles into batches of 500,
    preloading them concurrently (using 8 threads), saving the combined dictionary to cache_file,
    and returning the wiki cache dictionary.
    """
    batch_size = 500
    batches = [all_titles[i:i+batch_size] for i in range(0, len(all_titles), batch_size)]
    print(f"Total batches for cache update: {len(batches)} (each with up to {batch_size} pages)")
    wiki_cache = {}
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(load_batch, batch, site) for batch in batches]
        for future in tqdm(as_completed(futures), total=len(futures), desc="Loading cache batches"):
            try:
                batch_dict = future.result()
                wiki_cache.update(batch_dict)
            except Exception as e:
                print("Error loading a batch for cache:", e)
    print(f"Preloaded {len(wiki_cache)} pages into memory for cache.")
    save_cache(wiki_cache, cache_file)
    print(f"Cache saved to {cache_file}")
    return wiki_cache

# ---------------------------
# Multi-line & Operator String Processing
# ---------------------------
def process_multiline_string(s):
    """
    Replace literal "\n" or "/n" with an actual newline character.
    This allows multi-line search patterns.
    """
    return s.replace("\\n", "\n").replace("/n", "\n")

def matches_operator(term, text, case_sensitive):
    """
    Check if the given term matches the text.
    Supports ~OR~ and ~AND~ operators.
      - If term contains "~OR~", at least one of the subterms must match.
      - If term contains "~AND~" (and not "~OR~"), all subterms must match.
      - Otherwise, perform a simple substring match.
    """
    if "~OR~" in term:
        parts = [part.strip() for part in term.split("~OR~") if part.strip()]
        for part in parts:
            if "~AND~" in part:
                subparts = [sub.strip() for sub in part.split("~AND~") if sub.strip()]
                if case_sensitive:
                    if all(sub in text for sub in subparts):
                        return True
                else:
                    if all(sub.lower() in text.lower() for sub in subparts):
                        return True
            else:
                if case_sensitive:
                    if part in text:
                        return True
                else:
                    if part.lower() in text.lower():
                        return True
        return False
    elif "~AND~" in term:
        subparts = [sub.strip() for sub in term.split("~AND~") if sub.strip()]
        if case_sensitive:
            return all(sub in text for sub in subparts)
        else:
            return all(sub.lower() in text.lower() for sub in subparts)
    else:
        if case_sensitive:
            return term in text
        else:
            return term.lower() in text.lower()

def matches_search(search_str, text, case_sensitive):
    """Wrapper for matching search terms using the operator logic."""
    return matches_operator(search_str, text, case_sensitive)

def matches_ignore(ignore_str, text, case_sensitive):
    """Wrapper for matching ignore strings using the operator logic."""
    return matches_operator(ignore_str, text, case_sensitive)

# ---------------------------
# Page Search Function
# ---------------------------
def search_page(task):
    """
    Search a page's text for any given search terms.
    :param task: Tuple containing:
         (title, text, search_terms_list, case_sensitive, ignore_strings,
          ignore_country_codes, country_code_pattern)
    :return: The page title if a match is found; otherwise, None.
    """
    title, text, search_terms_list, case_sensitive, ignore_strings, ignore_country_codes, country_code_pattern = task

    # Optionally skip pages whose title indicates a language variant.
    if ignore_country_codes and country_code_pattern.search(title):
        return None

    # Skip pages that match any ignore string.
    for ignore_str in ignore_strings:
        if ignore_str and matches_ignore(ignore_str, text, case_sensitive):
            return None

    # Check for a match among search terms.
    if any(matches_search(term, text, case_sensitive) for term in search_terms_list):
        return title

    return None

# ---------------------------
# Main Script
# ---------------------------
def main():
    cache_file = "wiki_cache.json"
    wiki_directory_file = "wiki_directory.txt"
    site = pywikibot.Site()
    site.login()

    # Create a background executor for updating the wiki directory and cache.
    bg_executor = ThreadPoolExecutor(max_workers=8)

    # --- Step 1: Ensure Wiki Directory is up-to-date ---
    if not is_wiki_directory_valid(wiki_directory_file):
        print("Wiki directory updating in background")
        wiki_dir_future = bg_executor.submit(update_wiki_directory, site, wiki_directory_file)
    else:
        wiki_dir_future = None

    # --- Step 2: Prompt User for Search Settings ---
    search_terms_input = input("Enter search terms (comma-separated): ")
    search_terms_list = [process_multiline_string(term.strip()) for term in search_terms_input.split(',') if term.strip()]

    ignore_string_input = input("Enter strings to ignore (comma-separated, optional): ")
    ignore_strings = [process_multiline_string(s.strip()) for s in ignore_string_input.split(',') if s.strip()] if ignore_string_input else []

    ignore_country_codes_input = input("Ignore language pages? (Y/N) [default: Y]: ") or "Y"
    ignore_country_codes = (ignore_country_codes_input.strip().upper() == 'Y')

    case_sensitive_input = input("Case sensitive search? (Y/N) [default: N]: ") or "N"
    case_sensitive = (case_sensitive_input.strip().upper() == 'Y')

    # Regex to check for language suffixes (e.g., "/fr", "/pt-br", "/zh-hans", or "/zh-hant")
    country_code_pattern = re.compile(r"/([a-z]{2}|pt-br|zh-hans|zh-hant)$", re.IGNORECASE)

    # --- Step 3: Wait for Wiki Directory Update if Needed and Load It ---
    if wiki_dir_future is not None:
        print("Waiting for wiki directory")
        wiki_dir_future.result()
    with open(wiki_directory_file, 'r', encoding='utf-8') as f:
        all_titles = [line.strip() for line in f if line.strip()]
    print(f"Total page titles loaded: {len(all_titles)}")

    # --- Step 4: Ensure Wiki Cache is up-to-date ---
    if is_cache_valid(cache_file):
        wiki_cache = load_cache(cache_file)
    else:
        print("Cache updating in background")
        future_cache = bg_executor.submit(update_wiki_cache, site, all_titles, cache_file)
        print("Waiting for cache")
        wiki_cache = future_cache.result()

    # --- Step 5: Build Search Tasks ---
    tasks = [
        (title, text, search_terms_list, case_sensitive, ignore_strings, ignore_country_codes, country_code_pattern)
        for title, text in wiki_cache.items()
    ]

    # --- Step 6: Search Pages Concurrently Using a Process Pool ---
    matching_titles = []
    with ProcessPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(search_page, task) for task in tasks]
        for future in tqdm(as_completed(futures), total=len(futures), desc="Searching pages"):
            try:
                result = future.result()
                if result:
                    matching_titles.append(result)
            except Exception as e:
                print("Error searching a page:", e)

    matching_titles.sort()
    with open('search_results.txt', 'w', encoding='utf-8') as f:
        for title in matching_titles:
            f.write(f"{title}\n")
    print(f"Search complete. {len(matching_titles)} articles matched. Results saved in 'search_results.txt'.")

    bg_executor.shutdown()

if __name__ == "__main__":
    main()
