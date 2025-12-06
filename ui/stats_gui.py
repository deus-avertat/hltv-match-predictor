import json
import os
from collections import Counter, defaultdict
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_FILE = os.path.join(BASE_DIR, "data", "hltv_data.json")
THEME_FILE = os.path.join(BASE_DIR, "ui", "forest-dark.tcl")


class StatsData:
    """Load and aggregate match, team, and player statistics."""

    def __init__(self, data_path: str = DATA_FILE):
        self.data_path = data_path
        self.matches = self._load_matches()
        self.teams = self._build_teams()

    def _load_matches(self):
        if not os.path.exists(self.data_path):
            raise FileNotFoundError(f"Data file not found: {self.data_path}")

        with open(self.data_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            raise ValueError("hltv_data.json should contain a list of matches")

        return data

    def _build_teams(self):
        teams = {}
        for match in self.matches:
            date = match.get("date")
            map_name = match.get("map", "Unknown")
            result = match.get("result", "")

            for side, opponent_side in (("team1", "team2"), ("team2", "team1")):
                team_data = match.get(side, {}) or {}
                opponent = match.get(opponent_side, {}) or {}
                name = (team_data.get("name") or "Unknown").strip()

                team_record = teams.setdefault(
                    name,
                    {
                        "meta": self._extract_team_meta(team_data),
                        "matches": [],
                        "players": defaultdict(lambda: {"stats": []}),
                    },
                )

                team_record["matches"].append(
                    {
                        "date": date,
                        "opponent": opponent.get("name", "Unknown"),
                        "map": map_name,
                        "result": result,
                    }
                )

                for player in team_data.get("players", []) or []:
                    player_name = player.get("name") or "Unknown"
                    dated_stats = []

                    for stat in player.get("stats", []) or []:
                        stat_copy = dict(stat)
                        stat_copy.setdefault("date", date)
                        dated_stats.append(stat_copy)

                    team_record["players"][player_name]["stats"].extend(dated_stats)

        for team in teams.values():
            team["matches"].sort(key=lambda m: self._parse_date(m.get("date")))

        return teams

    @staticmethod
    def _parse_date(date_str):
        try:
            return datetime.strptime(date_str, "%Y-%m-%d")
        except Exception:
            return datetime.min

    @staticmethod
    def _extract_team_meta(team_data):
        return {
            "valve_points": team_data.get("valve_points"),
            "win_rate": team_data.get("win_rate"),
            "map_win_rate": team_data.get("map_win_rate"),
            "recent_matches": team_data.get("recent_matches", []),
        }

    @property
    def total_matches(self):
        return len(self.matches)

    @property
    def total_teams(self):
        return len(self.teams)

    def team_names(self):
        def sort_key(name):
            meta = self.teams[name]["meta"]
            points = meta.get("valve_points")
            normalized = points if isinstance(points, (int, float)) else -1
            return -normalized, name.lower()

        return sorted(self.teams.keys(), key=sort_key)

    def team_details(self, name):
        return self.teams.get(name)

    def player_summary(self, team_name, player_name):
        team = self.team_details(team_name)
        if not team:
            return {}

        player = team["players"].get(player_name)
        if not player:
            return {}

        stats = player["stats"]
        if not stats:
            return {"maps": Counter(), "average_kd": 0, "average_rating": 0, "matches": []}

        average_kd = sum(s.get("kd", 0) for s in stats) / len(stats)
        average_rating = sum(s.get("rating2.0", 0) for s in stats) / len(stats)
        maps = Counter(s.get("map", "Unknown") for s in stats)

        return {
            "maps": maps,
            "average_kd": round(average_kd, 2),
            "average_rating": round(average_rating, 2),
            "matches": stats,
        }


class StatsGUI:
    def __init__(self, data: StatsData):
        self.data = data
        self.root = tk.Tk()
        self.root.title("HLTV Model Stats")
        self._setup_theme()
        self._build_layout()
        self._populate_summary()

    def _setup_theme(self):
        if os.path.exists(THEME_FILE):
            self.root.tk.call("source", THEME_FILE)
            ttk.Style(self.root).theme_use("forest-dark")

    def _build_layout(self):
        self.root.geometry("1100x750")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        summary_frame = ttk.Frame(self.root, padding=10)
        summary_frame.grid(row=0, column=0, sticky="ew")
        summary_frame.columnconfigure((0, 1, 2), weight=1)

        self.total_matches_var = tk.StringVar()
        self.total_teams_var = tk.StringVar()
        self.data_file_var = tk.StringVar(value=f"Data: {self.data.data_path}")

        ttk.Label(summary_frame, textvariable=self.total_matches_var, font=("Arial", 12, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(summary_frame, textvariable=self.total_teams_var, font=("Arial", 12, "bold")).grid(row=0, column=1, sticky="w")
        ttk.Label(summary_frame, textvariable=self.data_file_var).grid(row=0, column=2, sticky="e")

        notebook = ttk.Notebook(self.root)
        notebook.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)

        self.team_tab = ttk.Frame(notebook, padding=10)
        notebook.add(self.team_tab, text="Teams & Matches")

        self._build_team_tab()

    def _build_team_tab(self):
        self.team_tab.columnconfigure(1, weight=1)
        self.team_tab.rowconfigure(1, weight=1)

        selector_frame = ttk.LabelFrame(self.team_tab, text="Select Team", padding=10)
        selector_frame.grid(row=0, column=0, sticky="new")
        selector_frame.columnconfigure(0, weight=1)

        ttk.Label(selector_frame, text="Team").grid(row=0, column=0, sticky="w")
        self.team_combo = ttk.Combobox(selector_frame, values=self.data.team_names(), state="readonly")
        self.team_combo.grid(row=1, column=0, sticky="ew", pady=5)
        self.team_combo.bind("<<ComboboxSelected>>", self._on_team_change)

        self.team_info = ttk.LabelFrame(self.team_tab, text="Team Stats", padding=10)
        self.team_info.grid(row=1, column=0, sticky="nsw", padx=(0, 10))
        for i in range(4):
            self.team_info.rowconfigure(i, weight=0)
        self.team_info.columnconfigure(0, weight=1)

        self.valve_points_var = tk.StringVar()
        self.win_rate_var = tk.StringVar()
        self.map_win_rate_var = tk.StringVar()
        self.team_matches_var = tk.StringVar()

        ttk.Label(self.team_info, textvariable=self.valve_points_var).grid(row=0, column=0, sticky="w", pady=2)
        ttk.Label(self.team_info, textvariable=self.win_rate_var).grid(row=1, column=0, sticky="w", pady=2)
        ttk.Label(self.team_info, textvariable=self.map_win_rate_var).grid(row=2, column=0, sticky="w", pady=2)
        ttk.Label(self.team_info, textvariable=self.team_matches_var).grid(row=3, column=0, sticky="w", pady=2)

        players_frame = ttk.LabelFrame(self.team_tab, text="Players", padding=10)
        players_frame.grid(row=2, column=0, sticky="nsew", pady=(10, 0))
        players_frame.columnconfigure(0, weight=1)

        self.player_combo = ttk.Combobox(players_frame, state="readonly")
        self.player_combo.grid(row=0, column=0, sticky="ew")
        self.player_combo.bind("<<ComboboxSelected>>", self._on_player_change)

        self.player_summary_var = tk.StringVar()
        ttk.Label(players_frame, textvariable=self.player_summary_var, justify=tk.LEFT).grid(row=1, column=0, sticky="w", pady=5)

        self.player_stats_tree = ttk.Treeview(
            players_frame, columns=("map", "kd", "rating", "date"), show="headings", height=6
        )
        self.player_stats_tree.heading("map", text="Map")
        self.player_stats_tree.heading("kd", text="K/D")
        self.player_stats_tree.heading("rating", text="Rating")
        self.player_stats_tree.heading("date", text="Date")
        self.player_stats_tree.column("map", width=80)
        self.player_stats_tree.column("kd", width=80, anchor="center")
        self.player_stats_tree.column("rating", width=80, anchor="center")
        self.player_stats_tree.column("date", width=80, anchor="center")
        self.player_stats_tree.grid(row=2, column=0, sticky="nsew")

        matches_frame = ttk.LabelFrame(self.team_tab, text="Matches", padding=10)
        matches_frame.grid(row=0, column=1, rowspan=3, sticky="nsew")
        matches_frame.columnconfigure(0, weight=1)
        matches_frame.rowconfigure(0, weight=1)

        columns = ("date", "opponent", "map", "result")
        self.matches_tree = ttk.Treeview(matches_frame, columns=columns, show="headings")
        for col, text, width in (
            ("date", "Date", 100),
            ("opponent", "Opponent", 200),
            ("map", "Map", 120),
            ("result", "Result", 120),
        ):
            self.matches_tree.heading(col, text=text)
            self.matches_tree.column(col, width=width, anchor="center")

        self.matches_tree.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(matches_frame, orient=tk.VERTICAL, command=self.matches_tree.yview)
        self.matches_tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.grid(row=0, column=1, sticky="ns")

    def _populate_summary(self):
        self.total_matches_var.set(f"Total matches scraped: {self.data.total_matches}")
        self.total_teams_var.set(f"Total teams scraped: {self.data.total_teams}")
        if self.data.team_names():
            self.team_combo.set(self.data.team_names()[0])
            self._on_team_change()

    def _on_team_change(self, event=None):
        team_name = self.team_combo.get()
        team = self.data.team_details(team_name)
        if not team:
            messagebox.showwarning("Unknown team", "No data available for the selected team")
            return

        meta = team["meta"]
        self.valve_points_var.set(f"Valve points: {meta.get('valve_points', 'N/A')}")
        self.win_rate_var.set(f"Win rate: {meta.get('win_rate', 'N/A')}%")
        self.map_win_rate_var.set(f"Map win rate: {meta.get('map_win_rate', 'N/A')}%")
        self.team_matches_var.set(f"Matches scraped: {len(team['matches'])}")

        for row in self.matches_tree.get_children():
            self.matches_tree.delete(row)

        for match in team["matches"]:
            self.matches_tree.insert(
                "",
                tk.END,
                values=(match.get("date", "Unknown"), match.get("opponent", "Unknown"), match.get("map", ""), match.get("result", "")),
            )

        player_names = sorted(team["players"].keys())
        self.player_combo["values"] = player_names
        if player_names:
            self.player_combo.set(player_names[0])
            self._on_player_change()
        else:
            self.player_combo.set("")
            self._clear_player_stats()

    def _clear_player_stats(self):
        self.player_summary_var.set("No player data available")
        for row in self.player_stats_tree.get_children():
            self.player_stats_tree.delete(row)

    def _on_player_change(self, event=None):
        team_name = self.team_combo.get()
        player_name = self.player_combo.get()
        summary = self.data.player_summary(team_name, player_name)
        if not summary:
            self._clear_player_stats()
            return

        map_breakdown = ", ".join(f"{map_name}: {count}" for map_name, count in summary["maps"].most_common())
        self.player_summary_var.set(
            f"{player_name}\nAverage K/D: {summary['average_kd']} | Rating: {summary['average_rating']}\nMaps: {map_breakdown}"
        )

        for row in self.player_stats_tree.get_children():
            self.player_stats_tree.delete(row)

        for stat in summary["matches"]:
            self.player_stats_tree.insert(
                "",
                tk.END,
                values=(stat.get("map", "Unknown"), stat.get("kd", ""), stat.get("rating2.0", ""), stat.get("date", "Unknown")),
            )

    def run(self):
        self.root.mainloop()


def main():
    data = StatsData()
    gui = StatsGUI(data)
    gui.run()


if __name__ == "__main__":
    main()