import joblib
import numpy as np
import pandas as pd
from bs4 import BeautifulSoup
import undetected_chromedriver as uc
from datetime import datetime, timedelta
import tkinter as tk
from tkinter import filedialog
import json

# Dictionaries and global variables
month_dict = {1: 'january', 2: 'february', 3: 'march', 4: 'april', 5: 'may', 6: 'june', 7: 'july', 8: 'august', 9: 'september', 10: 'october', 11: 'november', 12: 'december'}
map_player_dict = {
    'trn': 'Train', 'nuke': 'Nuke', 'd2': 'Dust2', 'mrg': 'Mirage', 
    'inf': 'Inferno', 'anc': 'Ancient',
    'ovp': 'Overpass'   # Add Overpass
}

map_team_dict = {
    'Dust2': 31, 'Mirage': 32, 'Inferno': 33, 'Nuke': 34, 
    'Train': 35, 'Overpass': 36, 'Ancient': 47
}
reverse_map_team_dict = {v: k for k, v in map_team_dict.items()}

driver = uc.Chrome()

def fetch_page(url):
    driver.get(url)
    html = driver.page_source
    return BeautifulSoup(html, "html.parser")

def get_valve_points(url):
    html = fetch_page(url)
    item = html.find(class_='teamLineExpanded')
    if item is None:
        item = html.find_all(class_='points')[-1]
        pts = int(item.text.split(' ')[0].split('(')[1]) - 1
    else:
        pts = int(item.find(class_='points').text.split(' ')[0].split('(')[1])
    return pts

def get_winrate(url):
    html = fetch_page(url)
    stats = html.find_all(class_='large-strong')[1].text
    w, d, l = map(int, stats.split(" / "))
    if w + d + l == 0:
        return 0
    return round(w / (w + d + l) * 100, 1)

def get_map_winrate(url):
    html = fetch_page(url)
    map_stats = html.find_all(class_='stats-row')[1].find_all('span')[1].text
    w, d, l = map(int, map_stats.split(" / "))
    if w + d + l == 0:
        return 0
    return round(w / (w + d + l) * 100, 1)

def get_player_stats(name, player_id, date):
    url = f"https://www.hltv.org/stats/players/matches/{player_id}/{name}?startDate={(date - timedelta(days=90)).strftime('%Y-%m-%d')}&endDate={date.strftime('%Y-%m-%d')}"
    html = fetch_page(url)
    matches = html.find(class_='stats-table').find_all("tr", class_=["group-1", "group-2"], limit=10)
    stats = []
    for match in matches:
        map_name = match.find(class_='statsMapPlayed').text.strip()
        k, d = map(int, match.find(class_='statsCenterText').text.strip().split('-'))
        rating = float(match.find(class_=["match-lost", "match-won"]).text.strip())
        stats.append({"rating2.0": rating, "kd": round(k / d, 2), "map": map_player_dict[map_name]})
    return stats

def get_head_to_head_stats(url):
    html = fetch_page(url)
    head_to_head_item = html.find(class_='head-to-head')
    stats = head_to_head_item.find_all(class_='bold')
    w1, overtimes, w2 = [int(stat.text) for stat in stats]
    return [w1, w2]

def get_recent_matches(name, team_id, date):
    url = f"https://www.hltv.org/stats/teams/matches/{team_id}/{name}?startDate={(date - timedelta(days=90)).strftime('%Y-%m-%d')}&endDate={date.strftime('%Y-%m-%d')}"
    html = fetch_page(url)
    matches = html.find(class_='stats-table').find_all("tr", class_=["group-1", "group-2"], limit=10)
    recent_matches_list = []
    for match in matches:
        res = match.find(class_=["match-lost", "match-won"]).text.strip()
        recent_matches_list.append(res)
    recent_matches_list.reverse()
    return recent_matches_list

def prepare_match_all_maps(url):
    html = fetch_page(url)
    unix = int(html.find(class_='date')['data-unix']) / 1000
    date = datetime.fromtimestamp(unix) - timedelta(days=1)
    
    team1 = html.find(class_='team1-gradient')
    team1_name = team1.find('a')['href'].split('/')[-1]
    team1_id = team1.find('a')['href'].split('/')[-2]
    
    team2 = html.find(class_='team2-gradient')
    team2_name = team2.find('a')['href'].split('/')[-1]
    team2_id = team2.find('a')['href'].split('/')[-2]
    
    # Fetch common data once
    team1_valve_pts = get_valve_points(f"https://www.hltv.org/valve-ranking/teams/{date.year}/{month_dict[date.month]}/{date.day}?teamId={team1_id}")
    team2_valve_pts = get_valve_points(f"https://www.hltv.org/valve-ranking/teams/{date.year}/{month_dict[date.month]}/{date.day}?teamId={team2_id}")
    team1_winrate = get_winrate(f'https://www.hltv.org/stats/teams/{team1_id}/{team1_name}?startDate={(date - timedelta(days=90)).strftime("%Y-%m-%d")}&endDate={date.strftime("%Y-%m-%d")}')
    team2_winrate = get_winrate(f'https://www.hltv.org/stats/teams/{team2_id}/{team2_name}?startDate={(date - timedelta(days=90)).strftime("%Y-%m-%d")}&endDate={date.strftime("%Y-%m-%d")}')
    head_to_head_stats = get_head_to_head_stats(url)
    team1_recent_matches = get_recent_matches(team1_name, team1_id, date)
    team2_recent_matches = get_recent_matches(team2_name, team2_id, date)
    
    # Fetch player stats
    team1_players = html.find_all(class_='lineup')[0].find(class_='players').find_all('tr')[1].find_all(class_='player-compare')
    team2_players = html.find_all(class_='lineup')[1].find(class_='players').find_all('tr')[1].find_all(class_='player-compare')
    
    team1_players_stats = []
    for player in team1_players:
        player_id = player['data-player-id']
        player_name = player.text.strip()
        stats = get_player_stats(player_name, player_id, date)
        team1_players_stats.append({"name": player_name, "stats": stats})
    
    team2_players_stats = []
    for player in team2_players:
        player_id = player['data-player-id']
        player_name = player.text.strip()
        stats = get_player_stats(player_name, player_id, date)
        team2_players_stats.append({"name": player_name, "stats": stats})
    
    # Predict for all maps
    all_maps = list(map_team_dict.keys())
    predictions = []
    for map_name in all_maps:
        map_code = map_team_dict[map_name]
        team1_map_winrate = get_map_winrate(f'https://www.hltv.org/stats/teams/map/{map_code}/{team1_id}/{team1_name}?startDate={(date - timedelta(days=90)).strftime("%Y-%m-%d")}&endDate={date.strftime("%Y-%m-%d")}')
        team2_map_winrate = get_map_winrate(f'https://www.hltv.org/stats/teams/map/{map_code}/{team2_id}/{team2_name}?startDate={(date - timedelta(days=90)).strftime("%Y-%m-%d")}&endDate={date.strftime("%Y-%m-%d")}')
        
        match_data = {
            "date": date.strftime('%Y-%m-%d'),
            "map": map_name,
            "team1": {
                "name": team1_name,
                "valve_points": team1_valve_pts,
                "win_rate": team1_winrate,
                "map_win_rate": team1_map_winrate,
                "recent_matches": team1_recent_matches,
                "players": team1_players_stats
            },
            "team2": {
                "name": team2_name,
                "valve_points": team2_valve_pts,
                "win_rate": team2_winrate,
                "map_win_rate": team2_map_winrate,
                "recent_matches": team2_recent_matches,
                "players": team2_players_stats
            },
            "head_to_head": {
                "team1_winrate": 0 if head_to_head_stats[0] + head_to_head_stats[1] == 0 else round(head_to_head_stats[0] / (head_to_head_stats[0] + head_to_head_stats[1]) * 100, 1),
                "team2_winrate": 0 if head_to_head_stats[0] + head_to_head_stats[1] == 0 else round(head_to_head_stats[1] / (head_to_head_stats[0] + head_to_head_stats[1]) * 100, 1)
            }
        }
        
        features = process_match(match_data)
        probabilities = model.predict_proba(pd.DataFrame([features]))[0]
        team1_prob = probabilities[1] * 100
        team2_prob = probabilities[0] * 100
        predicted_winner = team1_name if team1_prob > team2_prob else team2_name
        predictions.append({
            "map": map_name,
            "predicted_winner": predicted_winner,
            "team1_prob": team1_prob,
            "team2_prob": team2_prob
        })
    
    match_code = url.split('/')[-2]
    return {
        "match_code": match_code,
        "date": date.strftime('%Y-%m-%d'),
        "teams": [team1_name, team2_name],
        "predictions": predictions
    }

def average_player_stats(team):
    avg_rating = np.mean([stat['rating2.0'] for player in team['players'] for stat in player['stats']])
    avg_kd = np.mean([stat['kd'] for player in team['players'] for stat in player['stats']])
    return avg_rating, avg_kd

def process_match(match_for_predict):
    features = {
        'team1_valve_points': match_for_predict['team1']['valve_points'],
        'team2_valve_points': match_for_predict['team2']['valve_points'],
        'team1_win_rate': match_for_predict['team1']['win_rate'],
        'team2_win_rate': match_for_predict['team2']['win_rate'],
        'team1_map_win_rate': match_for_predict['team1']['map_win_rate'],
        'team2_map_win_rate': match_for_predict['team2']['map_win_rate'],
        'team1_h2h_winrate': match_for_predict['head_to_head']['team1_winrate'],
        'team2_h2h_winrate': match_for_predict['head_to_head']['team2_winrate'],
        'team1_recent_wins': sum(1 if r == 'W' else 0 for r in match_for_predict['team1']['recent_matches']),
        'team2_recent_wins': sum(1 if r == 'W' else 0 for r in match_for_predict['team2']['recent_matches'])
    }
    features['team1_avg_rating'], features['team1_avg_kd'] = average_player_stats(match_for_predict['team1'])
    features['team2_avg_rating'], features['team2_avg_kd'] = average_player_stats(match_for_predict['team2'])
    return features

# GUI Functions
def predict_all_maps():
    url = url_entry.get()
    if not url:
        result_text.insert(tk.END, "Please enter a URL.\n")
        return
    result_text.delete(1.0, tk.END)  # Clear previous results
    result_text.insert(tk.END, "Fetching data...\n")
    try:
        match_results = prepare_match_all_maps(url)
        team1, team2 = match_results['teams']
        result_text.insert(tk.END, f"Match: {team1} vs {team2} on {match_results['date']}\n\n")
        
        # Calculate column widths dynamically
        winner_col_width = max(len('Predicted Winner'), len(team1), len(team2))
        prob_col_width_team1 = len(team1 + ' Prob')
        prob_col_width_team2 = len(team2 + ' Prob')
        
        # Create header
        header = f"{'Map':<10} | {'Predicted Winner':<{winner_col_width}} | {team1 + ' Prob':<{prob_col_width_team1}} | {team2 + ' Prob':<{prob_col_width_team2}}"
        separator = "-" * (10 + 3 + winner_col_width + 3 + prob_col_width_team1 + 3 + prob_col_width_team2)
        result_text.insert(tk.END, header + "\n")
        result_text.insert(tk.END, separator + "\n")
        
        # Insert predictions
        for pred in match_results['predictions']:
            map_name = pred['map'].ljust(10)
            winner = pred['predicted_winner'].ljust(winner_col_width)
            team1_prob = f"{pred['team1_prob']:.2f}%".ljust(prob_col_width_team1)
            team2_prob = f"{pred['team2_prob']:.2f}%".ljust(prob_col_width_team2)
            result_text.insert(tk.END, f"{map_name} | {winner} | {team1_prob} | {team2_prob}\n")
        
        save_button.config(state=tk.NORMAL)
        global current_results
        current_results = match_results
    except Exception as e:
        result_text.insert(tk.END, f"Error: {str(e)}\n")

def save_to_json():
    global current_results
    if not current_results:
        return
    file_path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON files", "*.json")])
    if file_path:
        with open(file_path, 'w') as f:
            json.dump(current_results, f, indent=4)
        result_text.insert(tk.END, f"Results saved to {file_path}\n")

# Initialize GUI
root = tk.Tk()
root.title("CS:GO Match Predictor")

url_label = tk.Label(root, text="Match URL:")
url_label.pack()

url_entry = tk.Entry(root, width=50)
url_entry.pack()

predict_button = tk.Button(root, text="Predict All Maps", command=predict_all_maps)
predict_button.pack()

# Set monospaced font and increased width
result_text = tk.Text(root, height=20, width=100, font=('Courier', 10))
result_text.pack()

save_button = tk.Button(root, text="Save to JSON", command=save_to_json, state=tk.DISABLED)
save_button.pack()

current_results = None

def on_closing():
    driver.quit()
    root.destroy()

root.protocol("WM_DELETE_WINDOW", on_closing)

# Load the model
model = joblib.load('model/cs2_model.pkl')

root.mainloop()