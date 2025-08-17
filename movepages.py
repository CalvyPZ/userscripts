import pywikibot
from tqdm import tqdm
import time

def move_page(page, new_title):
    page_name = page.title()
    summary = f"Moving page to {new_title}"
    try:
        page.move(new_title, reason=summary)
        return True
    except Exception as e:
        print(f"Error moving page {page_name}: {e}")
        return False

def main():
    site = pywikibot.Site()
    site.login()

    with open("search_results.txt", "r", encoding="utf-8") as f:
        lines = f.readlines()

    total_articles = len(lines)
    progress_bar = tqdm(total=total_articles, desc="Processing Articles", unit="article")

    for line in lines:
        page_name = line.strip()
        # Extract the last part of the page name after "/"
        new_title = page_name.split("/")[-1]
        new_title = f"{new_title} (scripts item parameter)"

        page = pywikibot.Page(site, page_name)
        if move_page(page, new_title):
            time.sleep(6)  # Rate limit
        progress_bar.update(1)

    progress_bar.close()

if __name__ == "__main__":
    main()
