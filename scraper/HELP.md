# 🧠 How to Get HLTV Cookies

1. Open your browser and go to `www.hltv.org` and load the home page.
2. Press `F12` to open Developer Tools.
3. Find the cookies:
    - **Firefox**: Go to `Storage` tab, then choose `Cookies` on the left, and select `www.hltv.org`.
    - **Chromium**: Go to `Application` tab, then choose `Cookies` on the left, and select `www.hltv.org`.
4. Find `__cf_bm` and `cf_clearance` and copy their value into their respective `"value"` tag in `config/cookies_example.json`.
5. Rename `cookies_example.json` to `cookies.json`.
6. You can now run the scraper without any issues.