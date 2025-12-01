import json
import time
import undetected_chromedriver as uc

class Driver:
    @staticmethod
    def get_driver(headless=False):
        options = uc.ChromeOptions()
        options.headless = headless
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-infobars")
        options.add_argument("--lang=en-US,en")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36")
        return uc.Chrome(options=options)

    @staticmethod
    def injectCookies(driver, cookie_file="../config/cookies.json"):
        from pathlib import Path

        if not Path(cookie_file).exists():
            print("[WARN] Cookie file not found")
            return

        driver.get("https://www.hltv.org")
        time.sleep(3)

        with open(cookie_file, "r") as f:
            cookies = json.load(f)

        for cookie in cookies:
            cookie_copy = {k: v for k, v in cookie.items() if k in ["name", "value", "domain", "path"]}
            driver.add_cookie(cookie_copy)

        driver.refresh()
        print("[INFO] Cookies injected and page refreshed")

class HTMLUtils:
    @staticmethod
    def get_team_line_expanded(html):
        item = html.find(class_='teamLineExpanded')
        if item is None:
            item = html.find_all(class_='points')[-1]
            pts = int(item.text.split(' ')[0].split('(')[1]) - 1
        else:
            pts = int(item.find(class_='points').text.split(' ')[0].split('(')[1])
        return pts