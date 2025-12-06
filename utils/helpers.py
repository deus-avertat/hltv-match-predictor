import json
import os
import platform
import subprocess
import tkinter as tk
import winreg
from datetime import date, datetime
from tkinter import filedialog

from dateutil.relativedelta import relativedelta

class Utils:
    @staticmethod
    def status_cb(msg, result_text, progress_var, level='good'):
        timestamp = datetime.now().strftime('%H:%M:%S')
        line = f"[{timestamp}] {msg}\n"
        tag = 'good' if level == 'good' else (
            'info' if level == 'info' else ('warn' if level == 'warn' else 'error'))  # Horrid way to code this :>
        result_text.insert(tk.END, line, tag)
        result_text.see(tk.END)
        progress_var.set(msg)


    @staticmethod
    # Get the date range where range = months to subtract
    def get_date_range(range):
        delta = date.today() - relativedelta(months=range)
        date_range = (
            f"?startDate={delta.strftime('%Y-%m-%d')}&endDate={date.today().strftime('%Y-%m-%d')}"
        )
        return date_range

    @staticmethod
    # Ensure the directory path
    def ensure_directory(path):
        try:
            os.makedirs(path, exist_ok=True)
            return True
        except OSError:
            return False

    @staticmethod
    # Detect theme of OS and apply GUI theme based on that
    def detect_dark_mode():
        system = platform.system()

        # WINDOWS
        if system == "Windows":
            try:
                registry = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
                key = winreg.OpenKey(
                    registry,
                    r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
                )
                value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
                return value == 0  # 0 = Dark, 1 = Light
            except:
                return False  # fallback: assume light mode

        # MACOS
        elif system == "Darwin":
            try:
                output = subprocess.run(
                    ["defaults", "read", "-g", "AppleInterfaceStyle"],
                    capture_output=True, text=True
                )
                return "Dark" in output.stdout
            except:
                return False

        # LINUX (GNOME)
        elif system == "Linux":
            try:
                output = subprocess.run(
                    ["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"],
                    capture_output=True, text=True
                )
                return "dark" in output.stdout.lower()
            except:
                return False

        # FALLBACK
        return False

class Cache:
    @staticmethod
    def normalize_cache_expiry(expiry_value, default_expiry_value):
        try:
            hours = int(expiry_value)
            if hours <= 0:
                raise ValueError
        except (TypeError, ValueError):
            hours = default_expiry_value
        return hours

    @staticmethod
    def validate_cache_db_path(path, default_cache_db, base_dir):
        candidate = os.path.abspath(path) if path else default_cache_db
        directory = os.path.dirname(candidate) or base_dir
        if Utils.ensure_directory(directory):
            return candidate
        print(f"Invalid cache DB directory for '{candidate}', falling back to default.")
        Utils.ensure_directory(os.path.dirname(default_cache_db))
        return default_cache_db

    @staticmethod
    def validate_model_path(path, default_model_dir):
        if path:
            candidate = os.path.abspath(path)
            if os.path.isfile(candidate):
                return candidate
            print(f"Model path '{candidate}' is invalid. Falling back to default model.")

        default_candidate = os.path.abspath(default_model_dir)
        if os.path.isfile(default_candidate):
            return default_candidate
        return default_candidate

class Settings:
    @staticmethod
    # Create settings path
    def settings_path(directory, path="settings.json"):
        return os.path.join(directory, path)

    @staticmethod
    def get_active_settings(ceh, cdb, mdir, headless=False):
        return {
            "cache_expiry_hours": ceh,
            "cache_db_path": cdb,
            "model_path": mdir,
            "headless": headless,
        }
