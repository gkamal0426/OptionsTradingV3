"""
Options Trading v3.1 - Setup & Launcher GUI
Run this instead of START_TRADING.bat for a proper setup experience.
Requires: tkinter (built into Python 3.11)
"""

import tkinter as tk
from tkinter import ttk, messagebox
import os
import sys
import threading
import webbrowser
import time
from variables.start_from_here import config_file_path, flask_excel_names, client_fields


# ── Colors ────────────────────────────────────────────────────────────────────
BG          = "#0f1117"
BG2         = "#1a1d2e"
BG3         = "#252840"
ACCENT      = "#667eea"
ACCENT2     = "#764ba2"
GREEN       = "#48bb78"
RED         = "#fc8181"
TEXT        = "#e2e8f0"
TEXT2       = "#a0aec0"
BORDER      = "#2d3748"


def ensure_folders(base, env_dir, exl_dir, env_files, fields):
    """Create all required folders and empty env files if they dont exist."""

    flask_env, excel_files = flask_excel_names()

    os.makedirs(env_dir, exist_ok=True)
    os.makedirs(base, exist_ok=True)

    # Create empty env files if they dont exist yet
    for tab_name, filepath in env_files.items():
        if not os.path.exists(filepath):
            with open(filepath, "w") as f:
                for key, label, _ in fields:
                    if key == "E":
                        f.write("E=prod\n")
                    else:
                        f.write(f"{key}=\n")
            print(f"Created empty env file: {filepath}")

    if not os.path.exists(flask_env):
        import secrets
        with open(flask_env, "w") as f:
            f.write(f"FLASK_SECRET_KEY={secrets.token_hex(32)}\n")
    
    # Create Excel input files with headers if they don't exist
    import openpyxl


    os.makedirs(exl_dir, exist_ok=True)

    for filepath, headers in excel_files.items():
        if not os.path.exists(filepath):
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.append(headers)
            wb.save(filepath)
            print(f"Created Excel file: {filepath}")



def read_env(filepath):
    """Read env file into dict."""
    data = {}
    if os.path.exists(filepath):
        with open(filepath, "r") as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    data[k.strip()] = v.strip()
    return data


def write_env(filepath, data):
    """Write dict to env file."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w") as f:
        for k, v in data.items():
            f.write(f"{k}={v}\n")


def credentials_exist(env_files):
    """Check if at least one env file has USER filled."""
    for path in env_files.values():
        d = read_env(path)
        if d.get("USER", "").strip():
            return True
    return False


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN APPLICATION
# ══════════════════════════════════════════════════════════════════════════════

class TradingSetupApp:
    def __init__(self):
        base, env_dir, exl_dir, self.env_files = config_file_path()
        self.fields = client_fields()
        ensure_folders(base, env_dir, exl_dir, self.env_files, self.fields)
        self.root = tk.Tk()
        self.root.title("Options Trading v3.1")
        self.root.geometry("720x600")
        self.root.configure(bg=BG)
        self.root.resizable(False, False)

        # Center window
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() - 720) // 2
        y = (self.root.winfo_screenheight() - 720) // 2
        self.root.geometry(f"720x720+{x}+{y}")

        self._style()
        self._header()
        if credentials_exist(self.env_files):
            self._show_launcher()
        else:
            self._show_setup()

        self.root.mainloop()


    def _style(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TNotebook",
                        background=BG2, borderwidth=0)
        style.configure("TNotebook.Tab",
                        background=BG3, foreground=TEXT2,
                        padding=[16, 8], font=("Segoe UI", 10))
        style.map("TNotebook.Tab",
                  background=[("selected", ACCENT)],
                  foreground=[("selected", "white")])
        style.configure("TFrame", background=BG2)
        style.configure("TLabel", background=BG2, foreground=TEXT,
                        font=("Segoe UI", 10))
        style.configure("TEntry", fieldbackground=BG3,
                        foreground=TEXT, insertcolor=TEXT,
                        borderwidth=1, relief="flat")
        style.configure("TScrollbar", background=BG3,
                        troughcolor=BG2, borderwidth=0)


    def _header(self):
        header = tk.Frame(self.root, bg=BG, height=70)
        header.pack(fill="x")
        header.pack_propagate(False)

        tk.Label(header,
                 text="📊 Options Trading v3.1",
                 bg=BG, fg=TEXT,
                 font=("Segoe UI", 18, "bold")).pack(side="left", padx=24, pady=16)

        tk.Label(header,
                 text="Kotak Neo API",
                 bg=BG, fg=TEXT2,
                 font=("Segoe UI", 10)).pack(side="right", padx=24)


    # ── SETUP SCREEN ──────────────────────────────────────────────────────────

    def _show_setup(self):
        self.main_frame = tk.Frame(self.root, bg=BG2)
        self.main_frame.pack(fill="both", expand=True, padx=0, pady=0)

        tk.Label(self.main_frame,
                 text="First time setup — enter your Kotak Neo credentials",
                 bg=BG2, fg=TEXT2,
                 font=("Segoe UI", 10)).pack(pady=(12, 4))

        # Notebook tabs
        self.notebook = ttk.Notebook(self.main_frame)
        self.notebook.pack(fill="both", expand=True, padx=16, pady=4)

        self.entries = {}
        for tab_name, filepath in self.env_files.items():
            self._build_tab(tab_name, filepath)

        # Buttons
        btn_frame = tk.Frame(self.main_frame, bg=BG2)
        btn_frame.pack(fill="x", padx=16, pady=12)

        tk.Button(btn_frame,
                  text="💾  Save Credentials",
                  command=self._save_credentials,
                  bg=ACCENT, fg="white",
                  font=("Segoe UI", 11, "bold"),
                  relief="flat", cursor="hand2",
                  padx=24, pady=10).pack(side="left")

        tk.Button(btn_frame,
                  text="▶  Save & Start Trading",
                  command=self._save_and_start,
                  bg=GREEN, fg="white",
                  font=("Segoe UI", 11, "bold"),
                  relief="flat", cursor="hand2",
                  padx=24, pady=10).pack(side="left", padx=12)

        self.status_label = tk.Label(btn_frame,
                                     text="",
                                     bg=BG2, fg=GREEN,
                                     font=("Segoe UI", 10))
        self.status_label.pack(side="left", padx=8)


    def _build_tab(self, tab_name, filepath):
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text=f"  {tab_name}  ")

        # Scrollable canvas
        canvas = tk.Canvas(frame, bg=BG2, highlightthickness=0)
        scrollbar = ttk.Scrollbar(frame, orient="vertical",
                                   command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg=BG2)

        scroll_frame.bind("<Configure>",
            lambda e: canvas.configure(
                scrollregion=canvas.bbox("all")))

        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Read existing values
        existing = read_env(filepath)
        self.entries[tab_name] = {}

        for i, (key, label, is_secret) in enumerate(self.fields):
            row = tk.Frame(scroll_frame, bg=BG2)
            row.pack(fill="x", padx=16, pady=4)

            tk.Label(row, text=label,
                     bg=BG2, fg=TEXT2,
                     font=("Segoe UI", 9),
                     width=22, anchor="w").pack(side="left")

            # E field is hardcoded to prod
            if key == "E":
                val = tk.StringVar(value="prod")
                entry = tk.Entry(row,
                                 textvariable=val,
                                 bg=BG3, fg=TEXT2,
                                 insertbackground=TEXT,
                                 relief="flat",
                                 font=("Segoe UI", 10),
                                 state="disabled",
                                 disabledbackground=BG3,
                                 disabledforeground=TEXT2)
            else:
                show = "*" if is_secret else ""
                val = tk.StringVar(value=existing.get(key, ""))
                entry = tk.Entry(row,
                                 textvariable=val,
                                 show=show,
                                 bg=BG3, fg=TEXT,
                                 insertbackground=TEXT,
                                 relief="flat",
                                 font=("Segoe UI", 10))

            entry.pack(side="left", fill="x", expand=True, ipady=6, padx=(8, 0))
            self.entries[tab_name][key] = val

        # Telegram note
        tk.Label(scroll_frame,
                 text="ℹ️  Telegram fields are optional but recommended for order alerts.",
                 bg=BG2, fg=TEXT2,
                 font=("Segoe UI", 8),
                 wraplength=580,
                 justify="left").pack(anchor="w", padx=16, pady=(8, 4))


    def _save_credentials(self):
        try:
            for tab_name, filepath in self.env_files.items():
                data = {}
                for key, label, _ in self.fields:
                    val = self.entries[tab_name][key].get().strip()
                    if key == "E":
                        val = "prod"
                    data[key] = val
                write_env(filepath, data)
            self.status_label.config(text="✅ Saved successfully!", fg=GREEN)
            self.root.after(1500, self._back_to_launcher)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save: {e}")

    def _back_to_launcher(self):
        self.main_frame.destroy()
        self._show_launcher()


    def _save_and_start(self):
        self._save_credentials()
        #self.main_frame.destroy()
        #self._show_launcher()


    # ── LAUNCHER SCREEN ───────────────────────────────────────────────────────

    def _show_launcher(self):
        self.launch_frame = tk.Frame(self.root, bg=BG2)
        self.launch_frame.pack(fill="both", expand=True)

        # Status area
        tk.Label(self.launch_frame,
                 text="Ready to trade",
                 bg=BG2, fg=TEXT,
                 font=("Segoe UI", 16, "bold")).pack(pady=(40, 4))

        tk.Label(self.launch_frame,
                 text="Your credentials are configured. Click Start to launch.",
                 bg=BG2, fg=TEXT2,
                 font=("Segoe UI", 10)).pack()

        # Server status
        self.server_status = tk.Label(self.launch_frame,
                                      text="⚪  Server not started",
                                      bg=BG2, fg=TEXT2,
                                      font=("Segoe UI", 11))
        self.server_status.pack(pady=20)

        # Log box
        log_frame = tk.Frame(self.launch_frame, bg=BG3,
                             relief="flat", bd=0)
        log_frame.pack(fill="both", expand=True,
                       padx=24, pady=(0, 16))

        self.log_text = tk.Text(log_frame,
                                bg=BG3, fg=TEXT2,
                                font=("Consolas", 9),
                                relief="flat",
                                state="disabled",
                                wrap="word",
                                height=10)
        self.log_text.pack(fill="both", expand=True, padx=8, pady=8)

        # Buttons
        btn_frame = tk.Frame(self.launch_frame, bg=BG2)
        btn_frame.pack(pady=(0, 20))

        self.start_btn = tk.Button(btn_frame,
                                   text="▶  Start Trading",
                                   command=self._start_trading,
                                   bg=GREEN, fg="white",
                                   font=("Segoe UI", 12, "bold"),
                                   relief="flat", cursor="hand2",
                                   padx=32, pady=12)
        self.start_btn.pack(side="left", padx=8)

        tk.Button(btn_frame,
                  text="⚙  Edit Credentials",
                  command=self._edit_credentials,
                  bg=BG3, fg=TEXT,
                  font=("Segoe UI", 10),
                  relief="flat", cursor="hand2",
                  padx=16, pady=12).pack(side="left", padx=8)

        tk.Button(btn_frame,
                  text="🌐  Open Browser",
                  command=lambda: webbrowser.open("http://localhost:5000"),
                  bg=BG3, fg=TEXT,
                  font=("Segoe UI", 10),
                  relief="flat", cursor="hand2",
                  padx=16, pady=12).pack(side="left", padx=8)
        
        tk.Button(btn_frame,
                text="✕  Close",
                command=self._close_app,
                bg=RED, fg="white",
                font=("Segoe UI", 10),
                relief="flat", cursor="hand2",
                padx=16, pady=12).pack(side="left", padx=8)


    def _close_app(self):
        result = messagebox.askquestion(
            "Close Options Trading",
            "Are you sure you want to close the Options Trading app?",
            icon="warning"
        )
        if result == "no":
            return
        
        # Show closing message
        self.server_status.config(
            text="🔴  Closing application... Please close the browser tab manually.",
            fg=RED
        )
        self.root.after(3000, self._force_close)

    def _force_close(self):
        self.root.destroy()
        sys.exit(0)

    def _log(self, message):
        self.log_text.config(state="normal")
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")


    def _start_trading(self):
        self.start_btn.config(state="disabled",
                              text="⏳  Starting...",
                              bg=TEXT2)
        self.server_status.config(text="🟡  Starting server...",
                                  fg="#ECC94B")
        threading.Thread(target=self._launch_server,
                         daemon=True).start()


    def _launch_server(self):
        try:
            # Set working directory to project root
            project_root = os.path.dirname(os.path.abspath(__file__))
            os.chdir(project_root)
            sys.path.insert(0, project_root)

            self._log("📁 Loading project...")

            from options_trading.app3 import OptionsTrading

            self._log("🔧 Initializing trading system...")

            try:
                if hasattr(self, '_app') and self._app:
                    app = OptionsTrading(self._app)
                else:
                    raise Exception("No existing session")
            except Exception:
                app = OptionsTrading()
                self._app = app

            self._log("✅ System initialized successfully!")
            self._log("🚀 Starting Flask server on port 5000...")

            # Update UI
            self.root.after(0, lambda: self.server_status.config(
                text="🟢  Server running — http://localhost:5000",
                fg=GREEN))
            self.root.after(0, lambda: self.start_btn.config(
                text="🟢  Running",
                bg=GREEN,
                state="disabled"))

            # Open browser
            time.sleep(2.5)
            self._log("🌐 Opening browser...")
            webbrowser.open("http://localhost:5000")

            # Start Flask (blocking)
            app.start(port=5000)

            # Keep alive
            while True:
                time.sleep(1)

        except ImportError as e:
            self._log(f"❌ Import error: {e}")
            self.root.after(0, lambda: self.server_status.config(
                text="🔴  Failed to start", fg=RED))
            self.root.after(0, lambda: self.start_btn.config(
                text="▶  Retry",
                bg=GREEN,
                state="normal"))

        except Exception as e:
            self._log(f"❌ Error: {e}")
            self.root.after(0, lambda: self.server_status.config(
                text="🔴  Error — check log", fg=RED))
            self.root.after(0, lambda: self.start_btn.config(
                text="▶  Retry",
                bg=GREEN,
                state="normal"))


    def _edit_credentials(self):
        self.launch_frame.destroy()
        self._show_setup()


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    TradingSetupApp()
