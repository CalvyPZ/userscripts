import pywikibot
import time
from tqdm import tqdm

TARGET_STRINGS = ['==Body part==', '{{Body part|body_location=']

def main():
    file_path = 'search_results.txt'
    site = pywikibot.Site()
    site.login()

    with open(file_path, 'r') as file:
        lines = file.readlines()

    for line in tqdm(lines, desc="Processing Pages"):
        page_title = line.strip()
        try:
            page = pywikibot.Page(site, page_title)

            # Check if any of the TARGET_STRINGS are in the page text
            if any(target in page.text for target in TARGET_STRINGS):
                filtered_content = [line for line in page.text.split('\n') if not any(target in line for target in TARGET_STRINGS)]
                page.text = '\n'.join(filtered_content)
                page.save(summary=f'Remove line(s).', tags='bot')
                time.sleep(7)
        except Exception as e:
            print(f"An error occurred while processing page {page_title}: {e}")
            continue  # Skip to the next page if an error occurs

if __name__ == "__main__":
    main()