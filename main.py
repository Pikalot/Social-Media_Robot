from playwright.sync_api import sync_playwright
from dotenv import load_dotenv
import os

load_dotenv()  # loads .env into environment variables

def screen_web(url):
    print("do something")
    browser_name = os.getenv('BROWSER', 'chrome')
    print("browser_name: " + browser_name)
    with sync_playwright() as p:
        browser = getattr(p, browser_name).launch(headless=False)
        page = browser.new_page()
        page.goto(url)
        print("goto url: " + url)
        content = page.content()
        browser.close()
        return content
    
def main():
    url = "https://playwright.dev/"
    html_content = screen_web(url)
    print(html_content)

if __name__ == "__main__":
    main()