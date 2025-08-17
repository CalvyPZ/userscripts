import webbrowser
from tqdm import tqdm


def open_page_in_browser(page_name):
    # Format the page name by replacing spaces with underscores
    formatted_page_name = page_name.replace(' ', '_')

    # Construct and open the edit URL for the full page name
    url = f"https://pzwiki.net/w/index.php?title={formatted_page_name}&action=edit"
    webbrowser.open(url)
    input(f"Opened base page {formatted_page_name}. Press Enter to continue...")


def process_page_titles(file_path):
    # Read all page names from the file and remove empty lines
    with open(file_path, 'r') as file:
        lines = [line.strip() for line in file if line.strip()]

    # Iterate over the list with a tqdm progress bar
    for page_name in tqdm(lines, desc="Processing pages", ncols=80):
        open_page_in_browser(page_name)


def main():
    file_path = 'search_results.txt'
    process_page_titles(file_path)


if __name__ == "__main__":
    main()
