from playwright.sync_api import sync_playwright

AUTH_STATE_PATH = "yelp_auth.json"


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto("https://biz.yelp.com/login")

        print("A browser window has opened. Log into your Yelp business account there,")
        print("including any 2FA/CAPTCHA steps. Once you can see your Yelp for Business")
        print("dashboard, come back here and press Enter.")
        input()

        context.storage_state(path=AUTH_STATE_PATH)
        print(f"Session saved to {AUTH_STATE_PATH}. You can close the browser window now.")
        browser.close()


if __name__ == "__main__":
    main()
