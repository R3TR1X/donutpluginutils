import json
import sys
import threading

from typing import Any, Dict, Optional
from pathlib import Path

import customtkinter as ctk
import requests
from tkinter import filedialog, messagebox


DOWNLOAD_ITEMS_FILE = Path(__file__).parent / "plugins.json"
CONFIG_FILE = Path(__file__).parent / "config.json"
DEPENDENCIES_FILE = Path(__file__).parent / "dependencies.json"
LOGS_DIR = Path(__file__).parent / "logs"

UPDATE_CHECK_URL = "https://api.github.com/repos/R3TR1X/donutpluginutils/releases/latest"





def load_config() -> Dict[str, Any]:
    """Load config.json."""
    cfg = {}
    try:
        if CONFIG_FILE.exists():
            text = CONFIG_FILE.read_text(encoding="utf-8")
            if text.strip():
                data = json.loads(text)
                if isinstance(data, dict):
                    cfg = data
    except Exception:
        pass
    
    # Ensure critical keys exist to prevent crashes if config is empty/missing
    if "window_width" not in cfg: cfg["window_width"] = 720
    if "window_height" not in cfg: cfg["window_height"] = 520
    if "version" not in cfg: cfg["version"] = "1.0.0"
    if "auto_check_update" not in cfg: cfg["auto_check_update"] = False
    
    return cfg


def save_config(cfg: Dict[str, Any]) -> None:
    """Persist config.json."""
    CONFIG_FILE.write_text(json.dumps(cfg, indent=4, ensure_ascii=False), encoding="utf-8")


def load_download_items():
    """Load download items from JSON file."""
    try:
        if DOWNLOAD_ITEMS_FILE.exists():
            with open(DOWNLOAD_ITEMS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        else:
            # Create default empty file if it doesn't exist
            default_items = []
            with open(DOWNLOAD_ITEMS_FILE, "w", encoding="utf-8") as f:
                json.dump(default_items, f, indent=4, ensure_ascii=False)
            return default_items
    except Exception as exc:
        messagebox.showerror(
            "Error loading downloads",
            f"Could not load plugins.json:\n{exc}\n\nUsing empty list.",
        )
        return []


def load_dependencies():
    """Load dependencies from JSON file."""
    try:
        if DEPENDENCIES_FILE.exists():
            with open(DEPENDENCIES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def check_internet_connection() -> bool:
    try:
        # Short timeout to check connectivity
        requests.get("https://www.google.com", timeout=3)
        return True
    except Exception:
        return False


def ensure_dir(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        return True
    except OSError as exc:
        messagebox.showerror("Error", f"Could not create directory:\n{exc}")
        return False



def download_file(url: str, destination: Path, log_cb, status_cb, ready_cb) -> None:
    try:
        log_cb(f"Starting download: {destination.name}")
        log_cb(f"Target path: {destination}")
        log_cb(f"Extension: {destination.suffix or 'none'}")
        status_cb(f"Retrieving: {destination.name}")
        with requests.get(url, stream=True, timeout=20) as response:
            response.raise_for_status()
            total = int(response.headers.get("Content-Length", "0"))
            downloaded = 0
            chunk_size = 8192
            next_percent_log = 5  # update every 5%
            with open(destination, "wb") as file_handle:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if not chunk:
                        continue
                    file_handle.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        percent = downloaded / total * 100
                        if percent >= next_percent_log:
                            log_cb(f"Downloading... {percent:.1f}%")
                            status_cb(f"Downloading... {percent:.1f}%")
                            next_percent_log += 5
                    else:
                        # When size unknown, surface a simple progressing message
                        if downloaded % (256 * 1024) < chunk_size:
                            status_cb(f"Downloading... {downloaded // 1024} KB")
            log_cb(f"Saved: {destination}")
        status_cb(f"Finished: {destination.name}")
        ready_cb("Ready")
    except Exception as exc:  # broad to surface to user
        log_cb(f"Failed: {exc}")
        status_cb(f"Error: {exc}")
        ready_cb("Ready")
        # Re-raise so the caller knows it failed
        raise exc


class UnsavedChangesDialog(ctk.CTkToplevel):
    def __init__(self, parent, colors, title="Unsaved Changes", message="You have unsaved changes. Save before closing?"):
        super().__init__(parent)
        self.colors = colors
        self.user_choice = None  # True (Save), False (Don't Save), None (Cancel)

        self.title(title)
        self.geometry("420x180")
        self.resizable(False, False)
        self.configure(fg_color=self.colors["bg_dark"])
        
        # Center in parent if possible (simple generic centering)
        # self.eval('tk::PlaceWindow . center') # CustomTkinter doesn't strictly follow this, so skipping complex centering logic for simplicity
        
        self.grab_set()

        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(
            content, 
            text=message, 
            font=ctk.CTkFont(size=14),
            text_color=self.colors["text_light"],
            wraplength=380
        ).pack(pady=(10, 20))

        btn_frame = ctk.CTkFrame(content, fg_color="transparent")
        btn_frame.pack(fill="x")

        # Buttons: Save, Don't Save, Cancel
        ctk.CTkButton(
            btn_frame, 
            text="Save", 
            command=self.on_save,
            fg_color=self.colors["button"],
            hover_color=self.colors["button_hover"],
            width=80
        ).pack(side="left", expand=True, padx=5)

        ctk.CTkButton(
            btn_frame, 
            text="Don't Save", 
            command=self.on_dont_save,
            fg_color=self.colors["button"],
            hover_color=self.colors["button_hover"],
            width=80
        ).pack(side="left", expand=True, padx=5)

        ctk.CTkButton(
            btn_frame, 
            text="Cancel", 
            command=self.on_cancel,
            fg_color=self.colors["button"],
            hover_color=self.colors["button_hover"],
            text_color=self.colors["text_light"],
            width=60
        ).pack(side="left", expand=True, padx=5)

    def on_save(self):
        self.user_choice = True
        self.destroy()

    def on_dont_save(self):
        self.user_choice = False
        self.destroy()

    def on_cancel(self):
        self.user_choice = None
        self.destroy()


class CustomAlertDialog(ctk.CTkToplevel):
    def __init__(self, parent, colors, title="Error", message="An error occurred."):
        super().__init__(parent)
        self.colors = colors
        self.title(title)
        self.geometry("400x180")
        self.resizable(False, False)
        self.configure(fg_color=self.colors["bg_dark"])
        self.grab_set()

        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(
            content, 
            text=message, 
            font=ctk.CTkFont(size=14),
            text_color=self.colors["text_light"],
            wraplength=360
        ).pack(pady=(10, 20))

        ctk.CTkButton(
            content, 
            text="OK", 
            command=self.destroy,
            fg_color=self.colors["button"],
            hover_color=self.colors["button_hover"],
            width=100
        ).pack()

class YesNoDialog(ctk.CTkToplevel):
    def __init__(self, parent, colors, title="Are you sure?", message="Are you sure you want to cancel?"):
        super().__init__(parent)
        self.colors = colors
        self.result = False  # True = Yes, False = No

        self.title(title)
        self.geometry("400x180")
        self.resizable(False, False)
        self.configure(fg_color=self.colors["bg_dark"])
        self.grab_set()

        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(
            content, 
            text=message, 
            font=ctk.CTkFont(size=14),
            text_color=self.colors["text_light"],
            wraplength=360
        ).pack(pady=(10, 20))

        btn_frame = ctk.CTkFrame(content, fg_color="transparent")
        btn_frame.pack(fill="x")

        ctk.CTkButton(
            btn_frame, 
            text="Yes", 
            command=self.on_yes,
            fg_color=self.colors["button"],
            hover_color=self.colors["button_hover"],
            width=80
        ).pack(side="left", expand=True, padx=10)

        ctk.CTkButton(
            btn_frame, 
            text="No", 
            command=self.on_no,
            fg_color=self.colors["button"],
            hover_color=self.colors["button_hover"],
            width=80
        ).pack(side="left", expand=True, padx=10)

    def on_yes(self):
        self.result = True
        self.destroy()

    def on_no(self):
        self.result = False
        self.destroy()

class DownloadConfirmDialog(ctk.CTkToplevel):
    def __init__(self, parent, colors, items, title="Confirm Download"):
        super().__init__(parent)
        self.colors = colors
        self.items = items
        self.action = None  # "download", "dependencies", or None (cancel)

        self.title(title)
        self.geometry("500x400")
        self.resizable(False, False)
        self.configure(fg_color=self.colors["bg_dark"])
        self.grab_set()

        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(
            content, 
            text="You are about to download:", 
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=self.colors["text_light"]
        ).pack(pady=(0, 10))

        # Scrollable list for items
        list_frame = ctk.CTkScrollableFrame(
            content, 
            fg_color=self.colors["frame_dark"],
            height=200
        )
        list_frame.pack(fill="both", expand=True, pady=(0, 20))

        for item in self.items:
            ctk.CTkLabel(
                list_frame,
                text=f"• {item}",
                text_color=self.colors["text_light"],
                anchor="w"
            ).pack(fill="x", padx=10, pady=2)

        btn_frame = ctk.CTkFrame(content, fg_color="transparent")
        btn_frame.pack(fill="x")

        # Buttons: Download, Install with dependencies, Nevermind
        ctk.CTkButton(
            btn_frame, 
            text="Download", 
            command=self.on_download,
            fg_color=self.colors["button"],
            hover_color=self.colors["button_hover"],
            width=90
        ).pack(side="left", expand=True, padx=5)

        ctk.CTkButton(
            btn_frame, 
            text="Install with dependencies", 
            command=self.on_dependencies,
            fg_color=self.colors["button"],
            hover_color=self.colors["button_hover"],
            width=160
        ).pack(side="left", expand=True, padx=5)

        ctk.CTkButton(
            btn_frame, 
            text="Nevermind", 
            command=self.on_cancel,
            fg_color=self.colors["button"],
            hover_color=self.colors["button_hover"],
            width=90
        ).pack(side="left", expand=True, padx=5)

    def on_download(self):
        self.action = "download"
        self.destroy()

    def on_dependencies(self):
        self.action = "dependencies"
        self.destroy()

    def on_cancel(self):
        # Ask "Are you sure?"
        dlg = YesNoDialog(self, self.colors)
        self.wait_window(dlg)
        if dlg.result:
            self.action = None
            self.destroy()
        # If No, do nothing (stay in DownloadConfirmDialog)

class DownloaderApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.config_data = load_config()
        ctk.set_appearance_mode(self.config_data.get("theme", "dark"))
        ctk.set_default_color_theme(self.config_data.get("color_theme", "blue"))
        
        # Cursor-inspired color palette
        self.cursor_colors = {
            "bg_dark": "#121212",
            "frame_dark": "#161616",
            "border_dark": "#2e2e2e",
            "text_light": "#d1d5db",
            "button": "#2c2c2c",  # Cursor button color (gray)
            "button_hover": "#3a3a3a",  # Cursor button hover
            "button_border": "#2e2e2e",  # Cursor button border
            "entry_bg": "#2c2c2c",
        }

        self.title(str(self.config_data.get("app_name", "Donut Downloader")))
        w = int(self.config_data.get("window_width", 720))
        h = int(self.config_data.get("window_height", 520))
        self.geometry(f"{w}x{h}")
        self.resizable(False, False)
        
        # Set Cursor-style background color
        self.configure(fg_color=self.cursor_colors["bg_dark"])

        self.download_dir = None
        self.download_items = load_download_items()
        saved_selected = self.config_data.get("last_selected_plugins", [])
        if isinstance(saved_selected, list) and saved_selected:
            self.selected_items = [str(x) for x in saved_selected]
        else:
            self.selected_items = []
        self.ready_var = ctk.StringVar(value="Ready")
        self.status_var = ctk.StringVar(value="Ready" if self.download_dir else "Pick folder")
        self.log_lines = []
        self.log_lock = threading.Lock()
        self._build_ui()
        if self.config_data.get("auto_check_update", False):
            threading.Thread(target=self._auto_check_update_worker, daemon=True).start()

    def _build_ui(self):
        padding = {"padx": 12, "pady": 5}

        dir_frame = ctk.CTkFrame(self, fg_color=self.cursor_colors["frame_dark"])
        dir_frame.pack(fill="x", **padding)

        ctk.CTkLabel(
            dir_frame, 
            text="Plugin folder:",
            text_color=self.cursor_colors["text_light"]
        ).pack(side="left", padx=(8, 6), pady=8)
        self.dir_label = ctk.CTkLabel(
            dir_frame,
            text=str(self.download_dir) if self.download_dir else "Choose plugin folder...",
            text_color=self.cursor_colors["text_light"],
            fg_color=self.cursor_colors["entry_bg"],
            corner_radius=6,
            anchor="w",
        )
        # Align text start with the end of "Plugin folder:" label; background matches entries.
        # Add a bit of inset and rounded background.
        self.dir_label.pack(side="left", fill="x", expand=True, padx=(0, 6), pady=8, ipadx=8, ipady=4)
        ctk.CTkButton(
            dir_frame, 
            text="Choose...", 
            command=self.choose_dir,
            fg_color=self.cursor_colors["button"],
            hover_color=self.cursor_colors["button_hover"]
        ).pack(side="right", padx=8, pady=8)

        selection_frame = ctk.CTkFrame(self, fg_color=self.cursor_colors["frame_dark"])
        selection_frame.pack(fill="x", **padding)

        ctk.CTkLabel(
            selection_frame, 
            text="Select plugins:",
            text_color=self.cursor_colors["text_light"]
        ).pack(side="left", padx=(8, 6), pady=8)
        self.selection_button = ctk.CTkButton(
            selection_frame, 
            text=self._selection_summary(), 
            command=self.open_picker,
            fg_color=self.cursor_colors["button"],
            hover_color=self.cursor_colors["button_hover"]
        )
        self.selection_button.pack(side="left", fill="x", expand=True, padx=6, pady=8)

        log_frame = ctk.CTkFrame(self, fg_color=self.cursor_colors["frame_dark"])
        log_frame.pack(fill="both", expand=True, **padding)
        ctk.CTkLabel(
            log_frame, 
            text="Output log:",
            text_color=self.cursor_colors["text_light"]
        ).pack(side="top", anchor="w", padx=(8, 6), pady=(8, 0))
        self.log_text = ctk.CTkTextbox(
            log_frame, 
            height=200,
            fg_color=self.cursor_colors["bg_dark"],
            text_color=self.cursor_colors["text_light"],
            border_color=self.cursor_colors["border_dark"]
        )
        self.log_text.configure(state="disabled")
        self.log_text.pack(fill="both", expand=True, padx=8, pady=8)

        status_frame = ctk.CTkFrame(self, fg_color=self.cursor_colors["frame_dark"])
        status_frame.pack(fill="x", **padding)
        ctk.CTkLabel(
            status_frame, 
            text="Status:",
            text_color=self.cursor_colors["text_light"]
        ).pack(side="left", padx=(8, 6), pady=8)
        self.status_entry = ctk.CTkEntry(
            status_frame, 
            textvariable=self.status_var, 
            state="disabled",
            fg_color=self.cursor_colors["entry_bg"],
            text_color=self.cursor_colors["text_light"],
            border_color=self.cursor_colors["border_dark"]
        )
        self.status_entry.pack(side="left", fill="x", expand=True, padx=6, pady=8)

        actions_frame = ctk.CTkFrame(self, fg_color=self.cursor_colors["frame_dark"])
        actions_frame.pack(fill="x", **padding)
        # Use grid so all four buttons share equal width without squishing.
        for col in range(4):
            actions_frame.grid_columnconfigure(col, weight=1)

        ctk.CTkButton(
            actions_frame,
            text="Download",
            command=self.start_download,
            fg_color=self.cursor_colors["button"],
            hover_color=self.cursor_colors["button_hover"],
        ).grid(row=0, column=0, padx=6, pady=8, sticky="ew")

        ctk.CTkButton(
            actions_frame,
            text="Check for update",
            command=self.check_for_update,
            fg_color=self.cursor_colors["button"],
            hover_color=self.cursor_colors["button_hover"],
        ).grid(row=0, column=1, padx=6, pady=8, sticky="ew")

        ctk.CTkButton(
            actions_frame,
            text="Settings",
            command=self.open_settings,
            fg_color=self.cursor_colors["button"],
            hover_color=self.cursor_colors["button_hover"],
        ).grid(row=0, column=2, padx=6, pady=8, sticky="ew")

        ctk.CTkButton(
            actions_frame,
            text="Quit",
            command=self.destroy,
            fg_color=self.cursor_colors["button"],
            hover_color=self.cursor_colors["button_hover"],
        ).grid(row=0, column=3, padx=6, pady=8, sticky="ew")

    def _selection_summary(self) -> str:
        if not self.selected_items:
            return "Pick plugins"
        if len(self.selected_items) == 1:
            return self.selected_items[0]
        return f"{len(self.selected_items)} downloads selected"

    def open_picker(self):
        picker = ctk.CTkToplevel(self)
        picker.title("Choose Plugins")
        picker.geometry("400x500")
        picker.grab_set()
        
        # Set Cursor-style background color
        picker.configure(fg_color=self.cursor_colors["bg_dark"])

        # "Available Plugins" Label
        ctk.CTkLabel(
            picker, 
            text="Available Plugins",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=self.cursor_colors["text_light"]
        ).pack(pady=(12, 0))

        # Checkbox frame (Scrollable)
        checkbox_frame = ctk.CTkScrollableFrame(
            picker, 
            fg_color=self.cursor_colors["frame_dark"]
        )
        checkbox_frame.pack(fill="both", expand=True, padx=12, pady=12)

        self.checkbox_vars = {}
        for item in self.download_items:
            var = ctk.BooleanVar(value=item["name"] in self.selected_items)
            cb = ctk.CTkCheckBox(
                checkbox_frame,
                text=item["name"],
                variable=var,
                onvalue=True,
                offvalue=False,
                fg_color=self.cursor_colors["button"],
                hover_color=self.cursor_colors["button_hover"],
                border_color=self.cursor_colors["button_border"],
                text_color=self.cursor_colors["text_light"]
            )
            cb.pack(anchor="w", padx=8, pady=6)
            self.checkbox_vars[item["name"]] = var

        def select_all():
             for var in self.checkbox_vars.values():
                 var.set(True)

        # Select All button above bottom buttons
        ctk.CTkButton(
            picker,
            text="Select All",
            command=select_all,
            fg_color=self.cursor_colors["button"],
            hover_color=self.cursor_colors["button_hover"]
        ).pack(fill="x", padx=12, pady=(0, 12))

        button_frame = ctk.CTkFrame(picker, fg_color=self.cursor_colors["frame_dark"])
        button_frame.pack(fill="x", padx=12, pady=12)

        def on_select():
            chosen = [name for name, var in self.checkbox_vars.items() if var.get()]
            if not chosen:
                messagebox.showerror("Error", "Select at least one download.")
                return
            self.selected_items = chosen
            self.selection_button.configure(text=self._selection_summary())
            self.config_data["last_selected_plugins"] = list(self.selected_items)
            try:
                save_config(self.config_data)
            except Exception:
                pass
            picker.destroy()

        ctk.CTkButton(
            button_frame, 
            text="Save Selection", 
            command=on_select,
            fg_color=self.cursor_colors["button"],
            hover_color=self.cursor_colors["button_hover"]
        ).pack(side="left", padx=6, pady=6, expand=True, fill="x")
        
        ctk.CTkButton(
            button_frame, 
            text="Close", 
            command=picker.destroy,
            fg_color=self.cursor_colors["button"],
            hover_color=self.cursor_colors["button_hover"]
        ).pack(side="right", padx=6, pady=6, expand=True, fill="x")

    def log(self, message: str):
        # Capture log line immediately so it is available for saving even if UI lags
        with self.log_lock:
            self.log_lines.append(message)
        self.after(0, lambda: self._append_log(message))

    def _append_log(self, message: str):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"{message}\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")
        self.status_var.set(message)

    def set_status(self, message: str):
        self.after(0, lambda: self.status_var.set(message))

    def set_ready(self, message: str):
        self.after(0, lambda: self.ready_var.set(message))

    def reset_log(self):
        with self.log_lock:
            self.log_lines = []
        self.after(0, self._clear_log_ui)

    def _clear_log_ui(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def get_log_text(self) -> str:
        with self.log_lock:
            return "\n".join(self.log_lines) + ("\n" if self.log_lines else "")

    def save_log(self, success: bool) -> str:
        base = "successlog" if success else "logerror"
        ensure_dir(LOGS_DIR)
        
        n = 1
        while True:
            candidate = LOGS_DIR / f"{base}{n}.txt"
            if not candidate.exists():
                break
            n += 1
        content = self.get_log_text()
        try:
            candidate.write_text(content, encoding="utf-8")
            return candidate.name
        except Exception as exc:
            # Surface failure in status and log
            self.log(f"Failed to save log: {exc}")
            return f"{base}{n}.txt"

    def choose_dir(self):
        initial = str(self.download_dir) if self.download_dir else str(Path.cwd())
        chosen = filedialog.askdirectory(initialdir=initial)
        if not chosen:
            return
        candidate = Path(chosen)
        if ensure_dir(candidate):
            self.download_dir = candidate
            self.dir_label.configure(text=str(candidate))
            self.status_var.set("Ready")

    def open_settings(self):
        """Open settings window."""
        settings = ctk.CTkToplevel(self)
        settings.title("Settings")
        settings.geometry("400x500")
        settings.grab_set()
        
        # Match settings background to main app theme
        settings.configure(fg_color=self.cursor_colors["bg_dark"])

        ctk.CTkLabel(
            settings, 
            text="Settings", 
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=self.cursor_colors["text_light"]
        ).pack(pady=20)

        # Version Frame
        version_frame = ctk.CTkFrame(settings, fg_color=self.cursor_colors["frame_dark"])
        version_frame.pack(fill="x", padx=12, pady=(0, 12))

        current_ver = self.config_data.get("version", "1.0.0")
        ctk.CTkLabel(
            version_frame, 
            text=f"Version {current_ver}", 
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=self.cursor_colors["text_light"]
        ).pack(pady=(20, 8), anchor="center")

        self.version_status_label = ctk.CTkLabel(
            version_frame,
            text="You are on the newest version",
            text_color=self.cursor_colors["text_light"]
        )
        self.version_status_label.pack(pady=(0, 16), anchor="center")

        self.update_button = ctk.CTkButton(
            version_frame,
            text="Check for update",
            command=self.check_update_in_settings,
            fg_color=self.cursor_colors["button"],
            hover_color=self.cursor_colors["button_hover"]
        )
        self.update_button.pack(pady=(0, 20), anchor="center")

        content = ctk.CTkFrame(settings, fg_color=self.cursor_colors["frame_dark"])
        content.pack(fill="both", expand=True, padx=12, pady=12)

        initial_auto = bool(self.config_data.get("auto_check_update", False))
        auto_var = ctk.BooleanVar(value=initial_auto)
        ctk.CTkCheckBox(
            content,
            text="Auto check for updates on start",
            variable=auto_var,
            onvalue=True,
            offvalue=False,
            fg_color=self.cursor_colors["button"],
            hover_color=self.cursor_colors["button_hover"],
            border_color=self.cursor_colors["button_border"],
            text_color=self.cursor_colors["text_light"],
        ).pack(anchor="w", padx=12, pady=(12, 6))

        def save_settings_logic():
            self.config_data["auto_check_update"] = bool(auto_var.get())
            try:
                save_config(self.config_data)
                return True
            except Exception as exc:
                messagebox.showerror("Error", f"Could not save config.json:\n{exc}")
                return False

        def on_save_click():
            if save_settings_logic():
                messagebox.showinfo("Saved", "Settings saved to config.json.")
                # Update initial state so further checks know we are clean
                nonlocal initial_auto
                initial_auto = bool(auto_var.get())

        def on_close():
            current_auto = bool(auto_var.get())
            if current_auto != initial_auto:
                # Changes detected
                dlg = UnsavedChangesDialog(settings, self.cursor_colors)
                self.wait_window(dlg)
                ans = dlg.user_choice
                
                if ans is None:
                    # Cancel
                    return
                elif ans is True:
                    # Yes -> Save
                    if save_settings_logic():
                        settings.destroy()
                else:
                    # No -> Close without saving
                    settings.destroy()
            else:
                settings.destroy()

        settings.protocol("WM_DELETE_WINDOW", on_close)

        button_frame = ctk.CTkFrame(settings, fg_color="transparent")
        button_frame.pack(fill="x", padx=12, pady=12)

        ctk.CTkButton(
            button_frame, 
            text="Save",
            command=on_save_click,
            fg_color=self.cursor_colors["button"],
            hover_color=self.cursor_colors["button_hover"]
        ).pack(side="left", padx=(0, 6), expand=True, fill="x")

        ctk.CTkButton(
            button_frame,
            text="Close",
            command=on_close,
            fg_color=self.cursor_colors["button"],
            hover_color=self.cursor_colors["button_hover"],
        ).pack(side="right", padx=(6, 0), expand=True, fill="x")

    def check_update_in_settings(self):
        self.update_button.configure(state="disabled", text="Checking...")
        threading.Thread(target=self._check_update_worker, daemon=True).start()

    def _check_update_worker(self):
        try:
            url = str(self.config_data.get("check_update_url", "")).strip()
            if not url:
                raise ValueError("No update URL configured")

            resp = requests.get(url, timeout=15, headers={"Accept": "application/vnd.github+json"})
            resp.raise_for_status()
            data = resp.json()
            latest = str(data.get("tag_name") or data.get("name") or "").strip()
            # Remove 'v' prefix if present for comparison if needed, but keeping simple for now
            
            assets = data.get("assets", [])
            download_url = ""
            for asset in assets:
                # Look for a python file or a specific asset name if we were building an exe.
                # For this script updater, we might just look for 'app.py' or 'source_code'.
                # Assuming the user wants to update the script itself, we might check for raw content
                # if the release asset isn't suitable.
                # However, for simplicity per instructions "program will update":
                # We'll try to find an asset named 'app.py' or just take the zipball/tarball?
                # Actually, simpler: just download the 'app.py' from the repo raw url if available, OR
                # if there is an asset named 'app.py'.
                if asset.get("name") == "app.py":
                    download_url = asset.get("browser_download_url")
                    break
            
            # Fallback: if no asset, maybe we just want to notify? 
            # But the user asked to "update". 
            # If we can't find a direct download, we cannot auto-update easily.
            # Let's assume for this specific tool 'Donut Downloader', we might be grabbing from a known location.
            # But relying on the release data is best.
            
            current = str(self.config_data.get("version", "1.0.0"))
            
            if latest and latest != current:
                self.after(0, lambda: self._update_ui_available(latest, download_url))
            else:
                self.after(0, lambda: self._update_ui_uptodate())

        except Exception as exc:
            error_msg = str(exc)
            self.after(0, lambda: self._update_ui_error(error_msg))

    def _update_ui_available(self, latest_ver, download_url):
        self.version_status_label.configure(text=f"New version available: {latest_ver}", text_color="yellow")
        self.update_button.configure(
            state="normal", 
            text="Update", 
            command=lambda: self.perform_update(download_url)
        )

    def _update_ui_uptodate(self):
        self.version_status_label.configure(text="You are on the newest version", text_color="green")
        self.update_button.configure(state="normal", text="Check for update", command=self.check_update_in_settings)

    def _update_ui_error(self, error):
        self.version_status_label.configure(text="Cant check for new update", text_color="red")
        # Ensure we don't show a popup for auto-checks or just keep it silent in the label as requested
        # 'also do the same error if the github link is wrong/cant find rlease... using our gui'
        # Implicitly this might mean the label, but if they want the popup:
        # CustomAlertDialog(self, self.cursor_colors, "Error", f"Update check failed:\n{error}") <-- might be too intrusive for auto
        # User said "also do the same error... using our gui" likely refers to the "Cant check for new update" text request or possibly the popup.
        # Given "change the you are on highest version text to cant check for new update", modifying the label seems primary.
        self.update_button.configure(state="normal", text="Check for update", command=self.check_update_in_settings)

    def perform_update(self, download_url):
        if not download_url:
            messagebox.showerror("Update Error", "No download URL found for this release.")
            return

        confirm = messagebox.askyesno("Confirm Update", "Download and overwrite current application?")
        if not confirm:
            return

        self.update_button.configure(state="disabled", text="Updating...")
        
        def worker():
            try:
                resp = requests.get(download_url, timeout=30)
                resp.raise_for_status()
                # Overwrite current script
                current_file = Path(__file__)
                current_file.write_bytes(resp.content)
                self.after(0, lambda: messagebox.showinfo("Update Complete", "Application updated. Please restart."))
                self.after(0, self.quit)
            except Exception as exc:
                self.after(0, lambda: messagebox.showerror("Update Failed", f"Could not update:\n{exc}"))
                self.after(0, lambda: self.update_button.configure(state="normal", text="Update"))

        threading.Thread(target=worker, daemon=True).start()

        ctk.CTkButton(
            settings,
            text="Close",
            command=settings.destroy,
            fg_color=self.cursor_colors["button"],
            hover_color=self.cursor_colors["button_hover"],
        ).pack(side="right", padx=12, pady=12)

    def _auto_check_update_worker(self):
        try:
            self._check_for_update(show_up_to_date=False)
        except Exception:
            pass

    def check_for_update(self):
        # Run in background so UI stays responsive
        threading.Thread(target=self._check_for_update, daemon=True).start()

    def _check_for_update(self, show_up_to_date: bool = True):
        url = UPDATE_CHECK_URL
        if not url:
            self.after(0, lambda: messagebox.showerror("Update check", "No update URL set in config.json."))
            return

        try:
            resp = requests.get(url, timeout=15, headers={"Accept": "application/vnd.github+json"})
            resp.raise_for_status()
            data = resp.json()
            latest = str(data.get("tag_name") or data.get("name") or "").strip()
            html = str(data.get("html_url") or "")
        except Exception as exc:
            self.after(0, lambda: messagebox.showerror("Update check", f"Update check failed:\n{exc}"))
            return

        current = str(self.config_data.get("version", "1.0.0"))
        if latest and latest != current:
            msg = f"Update available!\n\nCurrent: {current}\nLatest:  {latest}"
            if html:
                msg += f"\n\nRelease page:\n{html}"
            self.after(0, lambda: messagebox.showinfo("Update check", msg))
        else:
            if show_up_to_date:
                self.after(0, lambda: messagebox.showinfo("Update check", f"You are up to date.\n\nVersion: {current}"))

    def start_download(self):
        # Network check first
        if not check_internet_connection():
            CustomAlertDialog(self, self.cursor_colors, "Error", "Please enable wifi")
            return

        if not self.download_dir:
            CustomAlertDialog(self, self.cursor_colors, "Error", "Please choose a plugin folder.")
            return

        if not self.selected_items:
            CustomAlertDialog(self, self.cursor_colors, "Error", "Please select at least one download.")
            return

        items_to_download = [
            item for item in self.download_items if item["name"] in self.selected_items
        ]
        if not items_to_download:
            # Should not happen given check above, but safely handle
            CustomAlertDialog(self, self.cursor_colors, "Error", "No matching downloads found.")
            return

        # Show confirmation dialog
        names_only = [item["name"] for item in items_to_download]
        dlg = DownloadConfirmDialog(self, self.cursor_colors, names_only)
        self.wait_window(dlg)
        
        if not dlg.action:
            return

        # Resolve dependencies if requested
        if dlg.action == "dependencies":
            deps_map = load_dependencies() # dict matching name -> list of dep names
            extra_items = []
            
            # Helper to find item by name
            def find_item_by_name(name):
                for d in self.download_items:
                    if d["name"] == name:
                        return d
                return None

            # Simple recursion or iteration to collect deps
            # For simplicity, just 1 level or flat list loop.
            # Assuming deps_map is { "pluginA": ["pluginB", "pluginC"] }
            
            # Queue of names to process
            to_process = [item["name"] for item in items_to_download]
            processed = set(to_process)
            
            while to_process:
                current_name = to_process.pop(0)
                # Does this item have dependencies?
                if current_name in deps_map:
                    for dep_name in deps_map[current_name]:
                        if dep_name not in processed:
                            dep_item = find_item_by_name(dep_name)
                            if dep_item:
                                extra_items.append(dep_item)
                                processed.add(dep_name)
                                to_process.append(dep_name)
            
            if extra_items:
                items_to_download.extend(extra_items)
                CustomAlertDialog(self, self.cursor_colors, "Info", 
                                  f"Added {len(extra_items)} dependencies to the download queue.")

        def worker():
            self.set_ready("Busy")
            self.reset_log()
            overall_success = True
            
            self.log(f"--- Batch Download Started ---")
            self.log(f"Target Directory: {self.download_dir}")
            
            for idx, selected in enumerate(items_to_download, start=1):
                filename = Path(selected["url"]).name or "download.bin"
                target = self.download_dir / filename
                self.set_status(f"Starting download ({idx}/{len(items_to_download)}): {filename}")
                try:
                    download_file(
                        selected["url"],
                        target,
                        self.log,
                        self.set_status,
                        self.set_ready
                    )
                except Exception:
                    overall_success = False
            
            self.set_ready("Ready")
            self.set_status("Finished all downloads")
            
            self.log(f"--- Batch Download Finished ---")
            log_name = self.save_log(overall_success)
            self.log(f"Log saved to logs/{log_name}")

        threading.Thread(target=worker, daemon=True).start()



def main():
    app = DownloaderApp()
    app.mainloop()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)

