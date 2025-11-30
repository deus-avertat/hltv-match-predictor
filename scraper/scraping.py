import time
import logging
import json
import random
from bs4 import BeautifulSoup
import undetected_chromedriver as uc
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(filename='scraper.log', level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Dictionaries from original script
month_dict = {
    1: 'january',
    2: 'february',
    3: 'march',
    4: 'april',
    5: 'may',
    6: 'june',
    7: 'july',
    8: 'august',
    9: 'september',
    10: 'october',
    11: 'november',
    12: 'december'
}
map_player_dict = {
    'trn': 'Train',
    'nuke': 'Nuke',
    'd2': 'Dust2',
    'mrg': 'Mirage',
    'inf': 'Inferno',
    'anc': 'Ancient',
    'anb': 'Anubis',
    'vtg': 'Vertigo',
    'ovp': 'Overpass'
}
map_team_dict = {
    'Dust2': 31,
    'Mirage': 32,
    'Inferno': 33,
    'Nuke': 34,
    'Train': 35,
    'Overpass': 40,
    'Vertigo': 46,
    'Ancient': 47,
    'Anubis': 48
}
reverse_map_team_dict = {v: k for k, v in map_team_dict.items()}

# Date range for filtering
START_DATE = datetime(2025, 6, 1)
END_DATE = datetime(2025, 11, 30)

request_count = 0

def get_driver(headless=False):
    options = uc.ChromeOptions()
    options.headless = headless
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-infobars")
    options.add_argument("--lang=en-US,en")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36")
    return uc.Chrome(options=options)

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

def add_date_params(url):
    """Safely append start/end date params whether or not the URL already has ?"""
    separator = "&" if "?" in url else "?"
    return (
        f"{url}{separator}"
        f"startDate={START_DATE.strftime('%Y-%m-%d')}"
        f"&endDate={END_DATE.strftime('%Y-%m-%d')}"
    )


def fetch_page(url):
    global request_count
    request_count += 1
    
    # Pause for 2 minutes every 300 requests
    if request_count % 300 == 0:
        logging.info(f"[INFO] Pausing for 2 minutes after {request_count} requests")
        print(f"[INFO] Pausing for 2 minutes after {request_count} requests")
        time.sleep(120)
    
    time.sleep(random.uniform(2, 5))  # Random delay
    try:
        driver.get(url)
        html = driver.page_source
        logging.info("[INFO] Fetched page source")
        print("[INFO] Fetched page source")
        return BeautifulSoup(html, "html.parser")
    except Exception as e:
        logging.error(f"[ERROR] Error fetching {url}: {e}")
        return None

def load_processed_matches():
    try:
        with open('../data/processed_matches.json', 'r') as f:
            logging.info("[INFO] Loaded processed_matches.json")
            print("[INFO] Loaded processed_matches.json")
            return json.load(f)
    except FileNotFoundError:
        logging.info("[WARN] No processed_matches.json")
        print("[WARN] No processed_matches.json")
        return []

def save_processed_matches(matches):
    with open('../data/processed_matches.json', 'w') as f:
        json.dump(matches, f, indent=4)
        logging.info("[INFO] Saved processed_matches.json")
        print("[INFO] Saved processed_matches.json")

def match_exists(match_url, processed_matches):
    logging.info("[INFO] Match exists")
    print("[INFO] Match exists")
    return match_url in processed_matches

def save_match_data(match_data):
    try:
        with open("../data/hltv_data.json", "r") as f:
            existing_data = json.load(f)
            if not isinstance(existing_data, list):
                existing_data = []
    except FileNotFoundError:
        existing_data = []

    existing_data.append(match_data)
    with open("../data/hltv_data.json", "w") as f:
        json.dump(existing_data, f, indent=4)

def get_valve_points(url, name):
    logging.info(f"[INFO] Fetching valve points for: {name}")
    print(f"[INFO] Fetching valve points for: {name}")

    html = fetch_page(url)
    if html is None:
        logging.error(f"[ERROR] Couldn't fetch page: {url}")
        print(f"[ERROR] Couldn't fetch page: {url}")
        return 0
    item = html.find(class_='teamLineExpanded')
    if item is None:
        item = html.find_all(class_='points')[-1]
        pts = int(item.text.split(' ')[0].split('(')[1]) - 1
    else:
        pts = int(item.find(class_='points').text.split(' ')[0].split('(')[1])
    logging.info(f"[INFO] Fetched valve points for: {name}")
    print(f"[INFO] Fetched valve points for: {name}")
    return pts

def get_winrate(url, name):
    logging.info(f"[INFO] Fetching winrate for: {name}")
    print(f"[INFO] Fetching winrate for: {name}")

    html = fetch_page(url)
    if html is None:
        logging.error(f"[ERROR] Couldn't fetch page: {url}")
        print(f"[ERROR] Couldn't fetch page: {url}")
        return 0
    stats = html.find_all(class_='large-strong')[1].text
    w, d, l = map(int, stats.split(" / "))
    if w + d + l == 0:
        logging.error(f"[ERROR] Couldn't fetch winrate for: {name}")
        print(f"[ERROR] Couldn't fetch winrate for: {name}")
        return 0
    logging.info(f"[INFO] Fetched winrate for: {name}")
    print(f"[INFO] Fetched winrate for: {name}")
    return round(w / (w + d + l) * 100, 1)

def get_map_winrate(url, name):
    logging.info(f"[INFO] Fetching map winrate for: {name}")
    print(f"[INFO] Fetching map winrate for: {name}")

    html = fetch_page(url)
    if html is None:
        logging.error(f"[ERROR] Couldn't fetch page: {url}")
        print(f"[ERROR] Couldn't fetch page: {url}")
        return 0
    map_stats = html.find_all(class_='stats-row')[1].find_all('span')[1].text
    w, d, l = map(int, map_stats.split(" / "))
    if w + d + l == 0:
        logging.error(f"[ERROR] Couldn't fetch map winrate for {name}: {url}")
        print(f"[ERROR] Couldn't fetch map winrate for {name}: {url}")
        return 0
    logging.info(f"[INFO] Fetched map winrate for {name}")
    print(f"[INFO] Fetched map winrate for {name}")
    return round(w / (w + d + l) * 100, 1)

def get_player_stats(name, player_id):
    logging.info(f"[INFO] Fetching player stats for: {name} ({player_id})")
    print(f"[INFO] Fetching player stats: {name} ({player_id})")

    url = f"https://www.hltv.org/stats/players/matches/{player_id}/{name}?startDate={START_DATE.strftime('%Y-%m-%d')}&endDate={END_DATE.strftime('%Y-%m-%d')}"
    html = fetch_page(url)
    if html is None:
        logging.error(f"[ERROR] Couldn't fetch page: {url}")
        print(f"[ERROR] Couldn't fetch page: {url}")
        return []
    matches = html.find(class_='stats-table').find_all("tr", class_=["group-1", "group-2"], limit=10)
    stats = []
    for match in matches:
        map_name = match.find(class_='statsMapPlayed').text.strip()
        k, d = map(int, match.find(class_='statsCenterText').text.strip().split('-'))
        if d == 0:
            kd_ratio = k
        else:
            kd_ratio = round(k / d, 2)
        rating_el = match.find(class_=["match-lost", "match-won"])
        if rating_el is None:
            rating = 0.0
        else:
            rating = float(rating_el.text.strip())
        stats.append({"rating2.0": rating, "kd": kd_ratio, "map": map_player_dict.get(map_name, 'Unknown')})
    logging.info(f"[INFO] Fetched player stats for: {name} ({player_id})")
    print(f"[INFO] Fetched player stats: {name} ({player_id})")
    return stats

def get_team_stats(name, team_id, map_code):
    logging.info(f"[INFO] Fetching team stats for: {name} ({team_id})")
    print(f"[INFO] Fetching team stats for: {name} ({team_id})")

    stats_url_by_date = f"https://www.hltv.org/valve-ranking/teams/{START_DATE.year}/{month_dict[START_DATE.month]}/{START_DATE.day}?teamId={team_id}"
    valve_pts = get_valve_points(stats_url_by_date, name)
    stats_team_url = f"https://www.hltv.org/stats/teams/{team_id}/{name}?startDate={START_DATE.strftime('%Y-%m-%d')}&endDate={END_DATE.strftime('%Y-%m-%d')}"
    winrate = get_winrate(stats_team_url, name)
    stats_map_url = f"https://www.hltv.org/stats/teams/map/{map_code}/{team_id}/{name}?startDate={START_DATE.strftime('%Y-%m-%d')}&endDate={END_DATE.strftime('%Y-%m-%d')}"
    map_winrate = get_map_winrate(stats_map_url, name)
    logging.info(f"[INFO] Fetched team stats for: {name} ({team_id})")
    print(f"[INFO] Fetched team stats for: {name} ({team_id})")
    return valve_pts, winrate, map_winrate

def get_head_to_head_stats(url):
    logging.info("[INFO] Fetching head to head stats")
    print("[INFO] Fetching head to head stats")

    html = fetch_page(url)
    if html is None:
        logging.error(f"[ERROR] Couldn't fetch page: {url}")
        print(f"[ERROR] Couldn't fetch page: {url}")
        return [0, 0]
    head_to_head_item = html.find(class_='head-to-head')
    if head_to_head_item is None:
        logging.error("[ERROR] Couldn't fetch head to head stats")
        print("[ERROR] Couldn't fetch head to head stats")
        return [0, 0]
    stats = head_to_head_item.find_all(class_='bold')
    w1, overtimes, w2 = [int(stat.text) for stat in stats]
    logging.info("[INFO] Fetched head to head stats")
    print("[INFO] Fetched head to head stats")
    return [w1, w2]

def get_recent_matches(name, team_id):
    logging.info(f"[INFO] Fetching recent matches for: {name} ({team_id})")
    print(f"[INFO] Fetching recent matches for: {name} ({team_id})")

    url = f"https://www.hltv.org/stats/teams/matches/{team_id}/{name}?startDate={START_DATE.strftime('%Y-%m-%d')}&endDate={END_DATE.strftime('%Y-%m-%d')}"
    html = fetch_page(url)
    if html is None:
        logging.error(f"[ERROR] Couldn't fetch page: {url}")
        print(f"[ERROR] Couldn't fetch page: {url}")
        return []
    matches = html.find(class_='stats-table').find_all("tr", class_=["group-1", "group-2"], limit=10)
    recent_matches_list = []
    for match in matches:
        res = match.find(class_=["match-lost", "match-won"]).text.strip()
        recent_matches_list.append(res)
    recent_matches_list.reverse()
    logging.info(f"[INFO] Fetched recent matches for: {name} ({team_id})")
    print(f"[INFO] Fetched recent matches for: {name} ({team_id})")
    return recent_matches_list

def get_match_stats(url, map_code):
    logging.info(f"[INFO] Fetching match stats for: {map_code}")
    print(f"[INFO] Fetching match stats for: {map_code}")
    html = fetch_page(url)
    if html is None:
        logging.error(f"[ERROR] Couldn't fetch page: {url}")
        print(f"[ERROR] Couldn't fetch page: {url}")
        return
    unix = int(html.find("span", {"data-unix": True})["data-unix"]) / 1000
    date = datetime.fromtimestamp(unix) - timedelta(days=1)

    # Filter by date range
    if not (START_DATE <= date <= END_DATE):
        logging.info(f"[INFO] Skipping match {url}: Date {date.strftime('%Y-%m-%d')} outside range")
        return

    team1 = html.find(class_='team-left')
    team1_name = team1.find('a')['href'].split('/')[-1]
    team1_id = team1.find('a')['href'].split('/')[-2]
    team2 = html.find(class_='team-right')
    team2_name = team2.find('a')['href'].split('/')[-1]
    team2_id = team2.find('a')['href'].split('/')[-2]

    team1_stats = get_team_stats(team1_name, team1_id, map_code)
    team2_stats = get_team_stats(team2_name, team2_id, map_code)

    table1, table2 = html.find_all(class_='totalstats')
    players = [*table1.find_all(class_='st-player'), *table2.find_all(class_='st-player')]
    players_list = []

    for player in players:
        player_name = player.find("a")["href"].split('/')[-1]
        player_id = player.find("a")["href"].split('/')[-2]
        players_list.append({"name": player_name, "stats": get_player_stats(player_name, player_id)})

    result = "team1" if html.find(class_='team-left').find(class_='won') else "team2"

    head_to_head_url = html.find(class_='match-page-link')['href']
    head_to_head_stats = get_head_to_head_stats(f"https://www.hltv.org{head_to_head_url}")

    match_data = {
        "date": date.strftime('%Y-%m-%d'),
        "map": reverse_map_team_dict.get(map_code, 'Unknown'),
        "team1": {
            "name": team1_name,
            "valve_points": team1_stats[0],
            "win_rate": team1_stats[1],
            "map_win_rate": team1_stats[2],
            "recent_matches": get_recent_matches(team1_name, team1_id),
            "players": players_list[:5]
        },
        "team2": {
            "name": team2_name,
            "valve_points": team2_stats[0],
            "win_rate": team2_stats[1],
            "map_win_rate": team2_stats[2],
            "recent_matches": get_recent_matches(team2_name, team2_id),
            "players": players_list[5:]
        },
        "head_to_head": {
            "team1_winrate": 0 if head_to_head_stats[0] + head_to_head_stats[1] == 0 else round(head_to_head_stats[0] / (head_to_head_stats[0] + head_to_head_stats[1]) * 100, 1),
            "team2_winrate": 0 if head_to_head_stats[0] + head_to_head_stats[1] == 0 else round(head_to_head_stats[1] / (head_to_head_stats[0] + head_to_head_stats[1]) * 100, 1)
        },
        "result": result
    }

    logging.info(f"[INFO] Fetched match stats for: {map_code}")
    print(f"[INFO] Fetched match stats for: {map_code}")
    save_match_data(match_data)

def get_dataset_by_team_matches(url, count):
    logging.info(f"[INFO] Fetching dataset by team matches for {count} matches: URL: = {url}")
    print(f"[INFO] Fetching dataset by team matches for {count} matches: URL: = {url}")

    processed_matches = load_processed_matches()
    html = fetch_page(url)
    if html is None:
        logging.error(f"[ERROR] Couldn't fetch page: {url}")
        print(f"[ERROR] Couldn't fetch page: {url}")
        return []

    table = html.find(class_='stats-table')
    if table is None:
        logging.error(f"[ERROR] No stats-table found for URL: {url}")
        print(f"[ERROR] No stats-table found for URL: {url}")
        return []

    matches = table.find_all("tr", class_=["group-1", "group-2"], limit=count)

    for match in matches:
        start = time.time()
        match_url = match.find(class_='time').find('a')['href'].split('?')[0]
        match_url = f"https://www.hltv.org{match_url}"

        if match_exists(match_url, processed_matches):
            print(f"[INFO] Match exists: {match_url}")
            continue

        map_name = match.find(class_='statsMapPlayed').text.strip()
        map_code = map_team_dict.get(map_name, 0)
        get_match_stats(match_url, map_code)

        processed_matches.append(match_url)
        save_processed_matches(processed_matches)
        print(f"Time taken: {round(time.time() - start)} seconds")
        time.sleep(random.uniform(3, 7))

    logging.info(f"[INFO] Fetched dataset for {count} matches")
    print(f"[INFO] Fetched dataset for {count} matches")

def create_dataset(count_teams):
    logging.info(f"[INFO] Creating dataset for {count_teams} teams")
    print(f"[INFO] Creating dataset for {count_teams} teams")

    date = START_DATE
    url = f"https://www.hltv.org/valve-ranking/teams/{date.year}/{month_dict[date.month]}/{date.day}"
    html = fetch_page(url)
    if html is None:
        logging.error(f"[ERROR] Couldn't fetch page: {url}")
        print(f"[ERROR] Couldn't fetch page: {url}")
        return []
    item = html.find(class_='ranking')
    team_links = item.find_all(class_='moreLink', limit=count_teams)
    teams_match_pages = []
    for team_link in team_links: #[28:40]:
        team_id = team_link['href'].split('/')[-2]
        team_name = team_link['href'].split('/')[-1]
        print(team_name)
        base_url = f"https://www.hltv.org/stats/teams/matches/{team_id}/{team_name}"
        res_url = add_date_params(base_url)
        teams_match_pages.append(res_url)
    logging.info(f"[INFO] Fetched dataset for {count_teams} teams")
    print(f"[INFO] Fetched dataset for {count_teams} teams")
    return teams_match_pages

if __name__ == "__main__":
    logging.info("[INFO] Starting scraping")
    print("[INFO] Starting scraping")
    driver = get_driver(headless=False)
    try:
        teams_match_pages = create_dataset(40)
        for team_match_page in teams_match_pages:
            print(team_match_page.split('/')[-1])
            get_dataset_by_team_matches(team_match_page, 10)  # Reduced to 10 matches
    finally:
        logging.info("[INFO] Finished")
        print("[INFO] Finished")
        driver.quit()  # Ensure driver is closed