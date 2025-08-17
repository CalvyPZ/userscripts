#!/usr/bin/env python3
"""
This script reads a list of article titles from a file named `search_results.txt`,
logs into the configured MediaWiki site using Pywikibot, and reverts the most recent
edit for each article. This is typically used to undo erroneous bot edits.

Each reversion is saved with the edit summary "Revert bot error" and tagged as a bot edit.
A tqdm progress bar is displayed to show progress through the list.
"""

import pywikibot
from tqdm import tqdm

def main():
    site = pywikibot.Site()
    site.login()

    with open("search_results.txt", encoding="utf-8") as f:
        titles = [line.strip() for line in f if line.strip()]

    for title in tqdm(titles, desc="Reverting pages"):
        page = pywikibot.Page(site, title)

        try:
            revisions = list(page.revisions(total=2, content=True))
            if len(revisions) < 2:
                print(f"Skipping {title}: not enough history to revert.")
                continue

            prev_rev = revisions[1]
            page.text = prev_rev.text
            page.save(summary="Revert bot error", tags=["bot"])

        except Exception as e:
            print(f"Failed to revert {title}: {e}")

if __name__ == "__main__":
    main()
