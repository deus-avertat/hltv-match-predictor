import os
import subprocess
import sys
import threading
import sqlite3
import pickle
import joblib
import numpy as np
import pandas as pd
from bs4 import BeautifulSoup
import undetected_chromedriver as uc
from datetime import datetime, timedelta
import tkinter as tk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from tkinter import filedialog, messagebox, ttk
import json

from utils.helpers import Utils, Cache, Settings
from utils.dictionary import Dictionary
from utils.driver import HTMLUtils, Driver
from utils.database import Database as DB

# --------------------------
# GLOBAL VARS
# --------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_MODEL_DIR = os.path.join(BASE_DIR, "model", "cs2_model.pkl")
DEFAULT_CACHE_DB = os.path.join(BASE_DIR, "data", "cache.db")
DEFAULT_CACHE_EXPIRY_HOURS = 12

CACHE_EXPIRY_HOURS = DEFAULT_CACHE_EXPIRY_HOURS
CACHE_DB = DEFAULT_CACHE_DB
MODEL_DIR = DEFAULT_MODEL_DIR

# --------------------------
# SETTINGS
# --------------------------
def _normalize_settings(settings):
    dev = settings.get("cache_expiry_hours", DEFAULT_CACHE_EXPIRY_HOURS)
    dcdb = settings.get("cache_db_path", DEFAULT_CACHE_DB)
    dmd = settings.get("model_path", DEFAULT_MODEL_DIR)
    normalized = {
        "cache_expiry_hours": Cache.normalize_cache_expiry(dev, DEFAULT_CACHE_EXPIRY_HOURS),
        "cache_db_path": Cache.validate_cache_db_path(dcdb, DEFAULT_CACHE_DB, BASE_DIR),
        "model_path": Cache.validate_model_path(dmd, DEFAULT_MODEL_DIR),
    }
    return normalized

def apply_settings(settings):
    global CACHE_EXPIRY_HOURS, CACHE_DB, MODEL_DIR
    normalized = _normalize_settings(settings)
    CACHE_EXPIRY_HOURS = normalized["cache_expiry_hours"]
    CACHE_DB = normalized["cache_db_path"]
    MODEL_DIR = normalized["model_path"]
    return normalized

def persist_settings(settings):
    normalized = apply_settings(settings)
    with open(Settings.settings_path(BASE_DIR), 'w') as f:
        json.dump(normalized, f, indent=4)
    DB.initialize_cache_db(CACHE_DB)
    return normalized

def load_settings():
    settings_path = Settings.settings_path(BASE_DIR)
    if os.path.exists(settings_path):
        try:
            with open(settings_path, 'r') as f:
                file_settings = json.load(f)
        except (OSError, json.JSONDecodeError):
            print("Failed to load settings.json, using defaults.")
            file_settings = {}
    else:
        file_settings = {}

    return apply_settings(file_settings)


load_settings()

def _format_model_metadata(path):
    metadata = {"path": os.path.abspath(path) if path else ""}

    if not path or not os.path.isfile(path):
        metadata["error"] = "Model file not found."
        return metadata

    try:
        stats = os.stat(path)
        metadata.update({
            "size_mb": round(stats.st_size / (1024 * 1024), 2),
            "modified": datetime.fromtimestamp(stats.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
        })

        model_obj = joblib.load(path)
        metadata.update({
            "estimator": type(model_obj).__name__,
            "estimator_module": getattr(model_obj, "__module__", ""),
        })
    except Exception as e:
        metadata["error"] = f"Failed to read model metadata: {e}"

    return metadata


def _model_metadata_text(metadata):
    if "error" in metadata:
        return f"Status: {metadata['error']}\nPath: {metadata.get('path', 'N/A')}"

    return "\n".join([
        f"Path: {metadata['path']}",
        f"Estimator: {metadata.get('estimator', 'Unknown')}",
        f"Module: {metadata.get('estimator_module', 'Unknown')}",
        f"Size: {metadata.get('size_mb', '0')} MB",
        f"Last Modified: {metadata.get('modified', 'Unknown')}",
    ])


# --------------------------
# DICTIONARY
# --------------------------
month_dict = Dictionary.month_dict
map_player_dict = Dictionary.map_player_dict
map_team_dict = Dictionary.map_team_dict
reverse_map_team_dict = {v: k for k, v in map_team_dict.items()}

# --------------------------
# CHROME DRIVER
# --------------------------
driver = Driver.get_driver()
driver.execute_cdp_cmd("Network.enable", {})
driver.execute_cdp_cmd("Network.setBlockedURLs", {"urls": Dictionary.adblock_list})

def fetch_page(url):
    driver.get(url)
    html = driver.page_source
    return BeautifulSoup(html, "html.parser")


# --------------------------
# SCRAPER FUNCTIONS
# --------------------------
def get_valve_points(url):
    db_key = f"valve::{url}"
    cached = DB.cache_get(db_key, CACHE_DB, CACHE_EXPIRY_HOURS)
    if cached is not None:
        return cached

    html = fetch_page(url)
    pts = HTMLUtils.get_team_line_expanded(html)
    DB.cache_set(db_key, pts, CACHE_DB)
    return pts


def get_winrate(url):
    db_key = f"winrate::{url}"
    cached = DB.cache_get(db_key, CACHE_DB, CACHE_EXPIRY_HOURS)
    if cached is not None:
        return cached

    html = fetch_page(url)
    stats = html.find_all(class_='large-strong')[1].text
    w, d, l = map(int, stats.split(" / "))
    winrate = 0 if (w + d + l) == 0 else round(w / (w + d + l) * 100, 1)

    DB.cache_set(db_key, winrate, CACHE_DB)
    return winrate


def get_map_winrate(url):
    db_key = f"mapwin::{url}"
    cached = DB.cache_get(db_key, CACHE_DB, CACHE_EXPIRY_HOURS)
    if cached is not None:
        return cached

    html = fetch_page(url)
    map_stats = html.find_all(class_='stats-row')[1].find_all('span')[1].text
    w, d, l = map(int, map_stats.split(" / "))
    winrate = 0 if (w + d + l) == 0 else round(w / (w + d + l) * 100, 1)

    DB.cache_set(db_key, winrate, CACHE_DB)
    return winrate


def get_player_stats(name, player_id, date):
    key_date = date.strftime('%Y-%m-%d')
    db_key = f"player::{player_id}::{key_date}"
    cached = DB.cache_get(db_key, CACHE_DB, CACHE_EXPIRY_HOURS)
    if cached is not None:
        return cached

    url = f"https://www.hltv.org/stats/players/matches/{player_id}/{name}?startDate={(date - timedelta(days=90)).strftime('%Y-%m-%d')}&endDate={key_date}"
    html = fetch_page(url)

    table = html.find(class_='stats-table')
    if table is None:
        print(f"[ERROR] No player stats-table found for {name} ({player_id})")
        DB.cache_set(db_key, [], CACHE_DB)
        return []
    matches = table.find_all("tr", class_=["group-1", "group-2"], limit=10)

    stats = []
    for match in matches:
        map_name = match.find(class_='statsMapPlayed').text.strip()
        k, d = map(int, match.find(class_='statsCenterText').text.strip().split('-'))
        d = max(d, 1)
        rating = float(match.find(class_=["match-lost", "match-won"]).text.strip())
        stats.append({
            "rating2.0": rating,
            "kd": round(k / d, 2),
            "map": map_player_dict.get(map_name, map_name)
        })

    DB.cache_set(db_key, stats, CACHE_DB)
    return stats


def get_head_to_head_stats(url):
    db_key = f"h2h::{url}"
    cached = DB.cache_get(db_key, CACHE_DB, CACHE_EXPIRY_HOURS)
    if cached is not None:
        return cached

    html = fetch_page(url)
    item = html.find(class_='head-to-head')
    stats = item.find_all(class_='bold')
    w1, ot, w2 = [int(s.text) for s in stats]
    result = [w1, w2]
    DB.cache_set(db_key, result, CACHE_DB)
    return result


def get_recent_matches(name, team_id, date):
    key_date = date.strftime('%Y-%m-%d')
    db_key = f"recent::{team_id}::{key_date}::{name}"
    cached = DB.cache_get(db_key, CACHE_DB, CACHE_EXPIRY_HOURS)
    if cached is not None:
        return cached

    url = f"https://www.hltv.org/stats/teams/matches/{team_id}/{name}?startDate={(date - timedelta(days=90)).strftime('%Y-%m-%d')}&endDate={key_date}"
    html = fetch_page(url)
    matches = html.find(class_='stats-table').find_all("tr", class_=["group-1", "group-2"], limit=10)
    lst = [m.find(class_=["match-lost", "match-won"]).text.strip() for m in matches]
    lst.reverse()

    DB.cache_set(db_key, lst, CACHE_DB)
    return lst


# --------------------------
# MAIN LOGIC
# --------------------------
def prepare_match_all_maps(url):
    db_key = f"match::{url}"
    cached = DB.cache_get(db_key, CACHE_DB, CACHE_EXPIRY_HOURS)
    if cached is not None:
        if Utils.status_cb:
            Utils.status_cb("Loaded match data from cache.", result_text, progress_var, level="good")
        return cached

    if Utils.status_cb:
        Utils.status_cb("Loading match page...", result_text, progress_var, level="good")

    html = fetch_page(url)
    unix = int(html.find(class_='date')['data-unix']) / 1000
    date = datetime.fromtimestamp(unix) - timedelta(days=1)

    team1 = html.find(class_='team1-gradient')
    team1_name = team1.find('a')['href'].split('/')[-1]
    team1_id = team1.find('a')['href'].split('/')[-2]

    team2 = html.find(class_='team2-gradient')
    team2_name = team2.find('a')['href'].split('/')[-1]
    team2_id = team2.find('a')['href'].split('/')[-2]

    # Fetch cached stats
    if Utils.status_cb:
        Utils.status_cb("Fetching team rankings and recent performance...", result_text, progress_var, level="good")

    #value = 1
    #if date.day - 1 == 0:
    #    value = 1

    team1_valve_pts = get_valve_points(
        f"https://www.hltv.org/valve-ranking/teams/{date.year}/{month_dict[date.month]}/{date.day - 1}?teamId={team1_id}")
    team2_valve_pts = get_valve_points(
        f"https://www.hltv.org/valve-ranking/teams/{date.year}/{month_dict[date.month]}/{date.day - 1}?teamId={team2_id}")
    team1_winrate = get_winrate(
        f'https://www.hltv.org/stats/teams/{team1_id}/{team1_name}?startDate={(date - timedelta(days=90)).strftime("%Y-%m-%d")}&endDate={date.strftime("%Y-%m-%d")}')
    team2_winrate = get_winrate(
        f'https://www.hltv.org/stats/teams/{team2_id}/{team2_name}?startDate={(date - timedelta(days=90)).strftime("%Y-%m-%d")}&endDate={date.strftime("%Y-%m-%d")}')
    head_to_head_stats = get_head_to_head_stats(url)
    team1_recent_matches = get_recent_matches(team1_name, team1_id, date)
    team2_recent_matches = get_recent_matches(team2_name, team2_id, date)

    # Players
    if Utils.status_cb:
        Utils.status_cb("Fetching player statistics...", result_text, progress_var, level="good")

    team1_players = html.find_all(class_='lineup')[0].find(class_='players').find_all('tr')[1].find_all(
        class_='player-compare')
    team2_players = html.find_all(class_='lineup')[1].find(class_='players').find_all('tr')[1].find_all(
        class_='player-compare')

    team1_players_stats = []
    for player in team1_players:
        pid = player['data-player-id']
        pname = player.text.strip()
        stats = get_player_stats(pname, pid, date)
        team1_players_stats.append({"name": pname, "stats": stats})

    team2_players_stats = []
    for player in team2_players:
        pid = player['data-player-id']
        pname = player.text.strip()
        stats = get_player_stats(pname, pid, date)
        team2_players_stats.append({"name": pname, "stats": stats})

    if Utils.status_cb:
        Utils.status_cb("Fetching map stats and running predictions...", result_text, progress_var,  level="good")

    predictions = []
    for map_name in map_team_dict.keys():
        if Utils.status_cb:
            Utils.status_cb(f"Processing map {map_name}...", result_text, progress_var)
        map_code = map_team_dict[map_name]
        team1_map_winrate = get_map_winrate(
            f'https://www.hltv.org/stats/teams/map/{map_code}/{team1_id}/{team1_name}?startDate={(date - timedelta(days=90)).strftime("%Y-%m-%d")}&endDate={date.strftime("%Y-%m-%d")}')
        team2_map_winrate = get_map_winrate(
            f'https://www.hltv.org/stats/teams/map/{map_code}/{team2_id}/{team2_name}?startDate={(date - timedelta(days=90)).strftime("%Y-%m-%d")}&endDate={date.strftime("%Y-%m-%d")}')

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
                "team1_winrate": 0 if head_to_head_stats[0] + head_to_head_stats[1] == 0 else round(
                    head_to_head_stats[0] / (head_to_head_stats[0] + head_to_head_stats[1]) * 100, 1),
                "team2_winrate": 0 if head_to_head_stats[0] + head_to_head_stats[1] == 0 else round(
                    head_to_head_stats[1] / (head_to_head_stats[0] + head_to_head_stats[1]) * 100, 1)
            }
        }

        features = process_match(match_data)
        probabilities = model.predict_proba(pd.DataFrame([features]))[0]
        t1p = probabilities[1] * 100
        t2p = probabilities[0] * 100
        winner = team1_name if t1p > t2p else team2_name
        predictions.append({"map": map_name, "predicted_winner": winner, "team1_prob": t1p, "team2_prob": t2p})

    match_code = url.split('/')[-2]
    output = {"match_code": match_code, "date": date.strftime('%Y-%m-%d'), "teams": [team1_name, team2_name],
              "predictions": predictions}

    if Utils.status_cb:
        Utils.status_cb("Caching match data and finishing...", result_text, progress_var, level="good")

    DB.cache_set(db_key, output, CACHE_DB)
    return output


def average_player_stats(team):
    avg_rating = np.mean([stat['rating2.0'] for player in team['players'] for stat in player['stats']])
    avg_kd = np.mean([stat['kd'] for player in team['players'] for stat in player['stats']])
    return avg_rating, avg_kd


def process_match(match):
    f = {'team1_valve_points': match['team1']['valve_points'], 'team2_valve_points': match['team2']['valve_points'],
         'team1_win_rate': match['team1']['win_rate'], 'team2_win_rate': match['team2']['win_rate'],
         'team1_map_win_rate': match['team1']['map_win_rate'], 'team2_map_win_rate': match['team2']['map_win_rate'],
         'team1_h2h_winrate': match['head_to_head']['team1_winrate'],
         'team2_h2h_winrate': match['head_to_head']['team2_winrate'],
         'team1_recent_wins': sum(1 for r in match['team1']['recent_matches'] if r == 'W'),
         'team2_recent_wins': sum(1 for r in match['team2']['recent_matches'] if r == 'W'),
         'team1_avg_rating': (average_player_stats(match['team1']))[0],
         'team1_avg_kd': (average_player_stats(match['team1']))[1],
         'team2_avg_rating': (average_player_stats(match['team2']))[0],
         'team2_avg_kd': (average_player_stats(match['team2']))[1]}
    return f

def predict_all_maps():
    url = url_entry.get()
    if not url:
        result_text.insert(tk.END, "Please enter a URL.\n")
        return
    result_text.delete(1.0, tk.END)  # Clear previous results
    if Utils.status_cb:
        Utils.status_cb("Fetching data...", result_text, progress_var, level="good")
    progressbar.grid()
    progressbar.start(10)

    try:
        match_results = prepare_match_all_maps(url)
        team1, team2 = match_results['teams']
        result_text.insert(tk.END, f"Match: {team1} vs {team2} on {match_results['date']}\n")
        avg_team1 = np.mean([p['team1_prob'] for p in match_results['predictions']])
        avg_team2 = np.mean([p['team2_prob'] for p in match_results['predictions']])
        overall_winner = team1 if avg_team1 > avg_team2 else team2
        result_text.insert(tk.END, f"Overall Winner Prediction: {overall_winner} ({avg_team1:.1f}% vs {avg_team2:.1f}%)\n\n")

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

        progressbar.stop()
        progressbar.grid_remove()
        progress_var.set("Done")
        save_button.config(state=tk.NORMAL)
        global current_results
        current_results = match_results
    except Exception as e:
        progressbar.stop()
        progressbar.grid_remove()
        progress_var.set("Error")
        if Utils.status_cb:
            Utils.status_cb(f"Error: {str(e)}", result_text, progress_var, level="error")


def save_to_json():
    global current_results
    if not current_results:
        return
    file_path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON files", "*.json")])
    if file_path:
        with open(file_path, 'w') as f:
            json.dump(current_results, f, indent=4)
        result_text.insert(tk.END, f"Results saved to {file_path}\n")

# --------------------------
# GRAPHS
# --------------------------
def show_probability_chart():
    clear_graph()
    if not current_results:
        return
    maps = [p['map'] for p in current_results['predictions']]
    t1 = [p['team1_prob'] for p in current_results['predictions']]
    t2 = [p['team2_prob'] for p in current_results['predictions']]
    x = np.arange(len(maps))

    fig = plt.Figure(figsize=(8,4), dpi=100)
    ax = fig.add_subplot(111)
    ax.plot(x, t1, marker='o', label=current_results['teams'][0])
    ax.plot(x, t2, marker='o', label=current_results['teams'][1])
    ax.set_xticks(x)
    ax.set_xticklabels(maps)
    ax.set_ylabel('Win Probability %')
    ax.set_title('Map Probability Comparison')
    ax.legend()
    ax.grid(True)

    canvas = FigureCanvasTkAgg(fig, master=graph_frame)
    canvas.draw()
    canvas.get_tk_widget().pack(fill='both', expand=True)

def show_spider_chart():
    clear_graph()
    if not current_results:
        return
    categories = [p['map'] for p in current_results['predictions']]
    N = len(categories)
    t1 = [p['team1_prob'] for p in current_results['predictions']]
    t2 = [p['team2_prob'] for p in current_results['predictions']]

    angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
    t1_cycle = t1 + t1[:1]
    t2_cycle = t2 + t2[:1]
    angles_cycle = angles + angles[:1]

    fig = plt.Figure(figsize=(6,6), dpi=100)
    ax = fig.add_subplot(111, polar=True)

    ax.plot(angles_cycle, t1_cycle, label=current_results['teams'][0])
    ax.fill(angles_cycle, t1_cycle, alpha=0.25)
    ax.plot(angles_cycle, t2_cycle, label=current_results['teams'][1])
    ax.fill(angles_cycle, t2_cycle, alpha=0.25)
    ax.set_xticks(angles)
    ax.set_xticklabels(categories)
    ax.set_title('Map Strength Spider Chart')
    ax.legend()

    canvas = FigureCanvasTkAgg(fig, master=graph_frame)
    canvas.draw()
    canvas.get_tk_widget().pack(fill='both', expand=True)

# --------------------------
# GUI
# --------------------------
root = tk.Tk()
root.title("CS2 Match Predictor - HLTV")

# Set UI Theme
style = ttk.Style(root)
root.tk.call('source', os.path.join(BASE_DIR, "ui", "forest-light.tcl"))
root.tk.call('source', os.path.join(BASE_DIR, "ui", "forest-dark.tcl"))
is_dark = Utils.detect_dark_mode()
ttk.Style(root).theme_use("forest-dark" if is_dark else "forest-light")

# Windows
def open_settings_window():
    win = tk.Toplevel(root)
    win.title("Settings")
    win.geometry("430x460")

    settings = Settings.get_active_settings(CACHE_EXPIRY_HOURS, CACHE_DB, MODEL_DIR)

    tk.Label(win, text="Settings Panel", font=("Arial", 14, "bold")).pack(pady=10)

    # Cache Expiry
    tk.Label(win, text="Cache Expiry (hours):").pack()
    expiry_var = tk.StringVar(value=str(settings.get("cache_expiry_hours", CACHE_EXPIRY_HOURS)))
    tk.Entry(win, textvariable=expiry_var).pack()

    # Cache Directory
    tk.Label(win, text="Cache DB Path:").pack()
    cache_var = tk.StringVar(value=settings.get("cache_db_path", CACHE_DB))
    cache_entry = tk.Entry(win, textvariable=cache_var, width=40)
    cache_entry.pack()
    ttk.Button(win, text="Browse", style="Accent.TButton", command=lambda: cache_var.set(filedialog.askopenfilename())).pack(pady=2)

    # Model Directory
    tk.Label(win, text="Model File (.pkl):").pack()
    model_var = tk.StringVar(value=settings.get("model_path", MODEL_DIR))
    model_entry = tk.Entry(win, textvariable=model_var, width=40)
    model_entry.pack()
    ttk.Button(win, text="Browse", style="Accent.TButton", command=lambda: model_var.set(filedialog.askopenfilename())).pack(pady=2)

    # Model Metadata
    model_info_frame = ttk.LabelFrame(win, text="Model Info")
    model_info_frame.pack(fill="x", padx=10, pady=10)
    model_info_var = tk.StringVar()
    model_info_label = tk.Label(model_info_frame, textvariable=model_info_var, justify="left", anchor="w")
    model_info_label.pack(fill="x", padx=10, pady=5)

    def refresh_model_info():
        metadata = _format_model_metadata(model_var.get())
        model_info_var.set(_model_metadata_text(metadata))

    refresh_model_info()

    def save_settings():
        new_settings = {
            "cache_expiry_hours": expiry_var.get(),
            "cache_db_path": cache_var.get(),
            "model_path": model_var.get()
        }
        normalized = persist_settings(new_settings)
        expiry_var.set(str(normalized["cache_expiry_hours"]))
        cache_var.set(normalized["cache_db_path"])
        model_var.set(normalized["model_path"])
        refresh_model_info()
        Utils.status_cb("Settings updated and saved.", result_text, progress_var,  level="good")
        win.destroy()

    ttk.Button(win, text="Save Settings", style="Accent.TButton", command=save_settings).pack(pady=10)
    ttk.Button(win, text="Close", style="Accent.TButton", command=win.destroy).pack(pady=5)

def close_main_window():
    try:
        driver.quit()
    except:
        pass
    root.destroy()

def open_stats_window():
    stats_path = os.path.join(BASE_DIR, "ui", "stats_gui.py")
    if not os.path.isfile(stats_path):
        messagebox.showerror("Error", f"Stats file not found at {stats_path}")
        return

    try:
        Utils.status_cb("Opening HLTV Data Statistics", result_text, progress_var, level="good")
        subprocess.Popen([sys.executable, stats_path])
    except Exception as e:
        messagebox.showerror("Error", f"Error opening stats GUI: {e}")

# Menu Bar
menubar = tk.Menu(root)
menubar.config(fg="white")
root.config(menu=menubar)

# File Menu
file_menu = tk.Menu(menubar, tearoff=False)
menubar.add_cascade(label="File", menu=file_menu)
file_menu.add_command(label="Settings", command=open_settings_window)
file_menu.add_command(label="Exit", command=close_main_window)

# Data Menu
data_menu = tk.Menu(menubar, tearoff=False)
menubar.add_cascade(label="Data", menu=data_menu)
data_menu.add_command(label="HLTV Stats", command=open_stats_window)

# Clear previous embedded graph
def clear_graph():
    for widget in graph_frame.winfo_children():
        widget.destroy()

url_label = tk.Label(root, text="Match URL:")
url_label.pack()

url_entry = tk.Entry(root, width=50)
url_entry.pack()

predict_button = ttk.Button(root, text="Predict All Maps", style="Accent.TButton", command=lambda: (clear_graph(), threading.Thread(target=predict_all_maps).start()))
predict_button.pack(pady=5)

# Set monospaced font and increased width
result_text = tk.Text(root, height=20, width=100, font=('Courier', 10))
result_text.tag_config('good', background='green')
result_text.tag_config('info', background='white')
result_text.tag_config('warn', background='yellow')
result_text.tag_config('error', background='red3')
result_text.pack()

# Button Frame
buttons_top = tk.Frame(root)
buttons_top.pack()

buttons_btm = tk.Frame(root)
buttons_btm.pack()

# Save Button
save_button = ttk.Button(buttons_top, text="Save to JSON", style="Accent.TButton", command=save_to_json, state=tk.DISABLED)
save_button.grid(row=0, column=0, padx=5, pady=5)

# Clear Cache Button
clear_cache_button = ttk.Button(buttons_top, text="Clear Cache", style="Accent.TButton", command=lambda: DB.clear_cache(CACHE_DB, result_text, progress_var))
clear_cache_button.grid(row=0, column=1, padx=5, pady=5)

# View Cache Stats Button
view_cache_button = ttk.Button(buttons_top, text="View Cache Stats", style="Accent.TButton", command=lambda: DB.view_cache_stats(CACHE_DB, root))
view_cache_button.grid(row=0, column=2, padx=5, pady=5)

# Graph Buttons
prob_chart_button = ttk.Button(buttons_btm, text="Probability Chart", style="Accent.TButton", command=show_probability_chart)
prob_chart_button.grid(row=0, column=0, padx=5, pady=5)
spider_chart_button = ttk.Button(buttons_btm, text="Spider Chart", style="Accent.TButton", command=show_spider_chart)
spider_chart_button.grid(row=0, column=1, padx=5, pady=5)

# Progress Bar
progress_frame = tk.Frame(root)
progress_frame.pack()
progress_var = tk.StringVar(value="Idle")
progress_label = tk.Label(progress_frame, textvariable=progress_var)
progress_label.grid(row=0, column=0, padx=5, pady=5)

progressbar = ttk.Progressbar(progress_frame, mode="indeterminate")
progressbar.grid(row=0, column=1, padx=5, pady=5)

graph_frame = tk.Frame(root)
graph_frame.pack(fill='both', expand=True)

current_results = None

# --------------------------
# FINAL
# --------------------------
def on_closing():
    try:
        driver.quit()
    except:
        pass
    root.destroy()


root.protocol("WM_DELETE_WINDOW", on_closing)

def load_model_file():
    if not os.path.isfile(MODEL_DIR):
        raise FileNotFoundError(f"Model file not found at {MODEL_DIR}")
    return joblib.load(MODEL_DIR)

# Load the model
model = load_model_file()

root.mainloop()