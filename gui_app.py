
import customtkinter as ctk
import tkinter as tk
import json
import os
import sys
import subprocess
import threading
import queue
from config import CONFIG

# Set appearance mode and color theme
ctk.set_appearance_mode("Dark")  # Modes: "System" (standard), "Dark", "Light"
ctk.set_default_color_theme("blue")  # Themes: "blue" (standard), "green", "dark-blue"

class AladinGUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Aladin Trading Bot Control Panel")
        self.geometry("1100x800")

        # Bot Process
        self.bot_process = None
        self.is_running = False
        self.log_queue = queue.Queue()

        self.create_widgets()
        self.load_current_config_to_ui()
        
        # Start log updater
        self.after(100, self.update_logs)

    def create_widgets(self):
        # Configure grid layout (1x2)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Sidebar setup
        self.sidebar_frame = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(4, weight=1)

        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="Aladin Bot", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        # Status Label
        self.status_label = ctk.CTkLabel(self.sidebar_frame, text="Status: STOPPED", text_color="red")
        self.status_label.grid(row=1, column=0, padx=20, pady=10)

        # Control Buttons
        self.start_button = ctk.CTkButton(self.sidebar_frame, text="Start Bot", command=self.start_bot, fg_color="green", hover_color="darkgreen")
        self.start_button.grid(row=2, column=0, padx=20, pady=10)

        self.stop_button = ctk.CTkButton(self.sidebar_frame, text="Stop Bot", command=self.stop_bot, fg_color="darkred", hover_color="red", state="disabled")
        self.stop_button.grid(row=3, column=0, padx=20, pady=10)
        
        # Save Config Button
        self.save_button = ctk.CTkButton(self.sidebar_frame, text="Save Config", command=self.save_config)
        self.save_button.grid(row=5, column=0, padx=20, pady=10)

        # Main Content Area (Tabs)
        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=0, column=1, padx=(10, 10), pady=(10, 10), sticky="nsew")

        # Create Tabs
        self.tab_dashboard = self.tabview.add("Log Output")
        self.tab_trading = self.tabview.add("Trading")
        self.tab_risk = self.tabview.add("Risk")
        self.tab_adx = self.tabview.add("ADX Filter")
        self.tab_macro = self.tabview.add("Macro")
        self.tab_loss_limits = self.tabview.add("Daily Limits")

        # --- Dashboard Tab (Logs) ---
        self.tab_dashboard.grid_columnconfigure(0, weight=1)
        self.tab_dashboard.grid_rowconfigure(0, weight=1)
        
        self.log_textbox = ctk.CTkTextbox(self.tab_dashboard, width=800, height=600)
        self.log_textbox.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        self.log_textbox.configure(state="disabled") # Read-only initially

        # --- Trading Tab ---
        self.create_trading_inputs(self.tab_trading)

        # --- Risk Tab ---
        self.create_risk_inputs(self.tab_risk)

        # --- ADX Tab ---
        self.create_adx_inputs(self.tab_adx)
        
        # --- Macro Tab ---
        self.create_macro_inputs(self.tab_macro)

        # --- Daily Limits Tab ---
        self.create_limit_inputs(self.tab_loss_limits)

    def create_input_row(self, parent, label_text, config_key, row, type_cast=str, tooltip=None):
        label = ctk.CTkLabel(parent, text=label_text, anchor="w")
        label.grid(row=row, column=0, padx=10, pady=5, sticky="w")
        
        entry = ctk.CTkEntry(parent, width=200)
        entry.grid(row=row, column=1, padx=10, pady=5, sticky="w")
        
        # Store reference to entry to fetch value later
        if not hasattr(self, 'inputs'):
            self.inputs = {}
        
        self.inputs[config_key] = {'entry': entry, 'type': type_cast}
        return entry

    def create_checkbox_row(self, parent, label_text, config_key, row):
        # Using a StringVar to track state properly if needed, but simple ctk usage is 1/0
        checkbox = ctk.CTkCheckBox(parent, text=label_text)
        checkbox.grid(row=row, column=0, columnspan=2, padx=10, pady=5, sticky="w")
        
        if not hasattr(self, 'inputs'):
            self.inputs = {}
        
        self.inputs[config_key] = {'entry': checkbox, 'type': bool}
        return checkbox

    def create_trading_inputs(self, parent):
        self.create_input_row(parent, "Symbol:", 'symbol', 0, str)
        self.create_input_row(parent, "Entry Timeframe:", 'timeframe_entry', 1, str)
        
        ctk.CTkLabel(parent, text="Trend Analysis").grid(row=2, column=0, pady=(10,0), sticky="w")
        
        self.create_checkbox_row(parent, "Use Manual Trend Override", 'use_manual_trend', 3)
        self.create_input_row(parent, "Manual Trend (bullish/bearish):", 'manual_trend', 4, str)
        
        self.create_checkbox_row(parent, "Use Moving Averages", 'use_ma_for_trend', 5)
        self.create_checkbox_row(parent, "Use RSI", 'use_rsi_for_trend', 6)
        self.create_checkbox_row(parent, "Use VWAP", 'use_vwap_for_trend', 7)
        self.create_checkbox_row(parent, "Use Bollinger Bands", 'use_bollinger_for_trend', 8)
        
        self.create_input_row(parent, "Bullish Threshold:", 'trend_bullish_threshold', 9, int)
        self.create_input_row(parent, "Bearish Threshold:", 'trend_bearish_threshold', 10, int)

    def create_risk_inputs(self, parent):
        self.create_input_row(parent, "Capital:", 'capital', 0, float)
        self.create_input_row(parent, "Risk Percentage (%):", 'risk_pct', 1, float)
        self.create_input_row(parent, "Max Concurrent Trades:", 'max_concurrent_trades', 2, int)
        self.create_input_row(parent, "Max Concurrent Trades (Same Pair):", 'max_concurrent_trades_of_same_pair', 3, int)
        self.create_input_row(parent, "Min R:R Ratio:", 'min_rr_ratio', 4, float)
        
        self.create_checkbox_row(parent, "Trailing Stop", 'trailing_stop', 5)
        self.create_checkbox_row(parent, "Use ATR Stops", 'use_atr_stops', 6)
        self.create_input_row(parent, "ATR Multiplier:", 'atr_stop_multiplier', 7, float)
        self.create_input_row(parent, "ATR Method (wider/tighter/fibonacci):", 'atr_stop_method', 8, str)

    def create_adx_inputs(self, parent):
        self.create_checkbox_row(parent, "Enable ADX Filter", 'use_adx_filter', 0)
        self.create_input_row(parent, "ADX Period:", 'adx_period', 1, int)
        self.create_input_row(parent, "Strength Threshold:", 'adx_strength_threshold', 2, float)
        self.create_input_row(parent, "Extreme Threshold:", 'adx_extreme_threshold', 3, float)
        self.create_input_row(parent, "Weak Threshold:", 'adx_weak_threshold', 4, float)
        self.create_input_row(parent, "Confirmation Bars:", 'adx_confirmation_bars', 5, int)
        
        self.create_checkbox_row(parent, "Manual Control (Cross-Timeframe)", 'adx_manual_control', 6)
        self.create_checkbox_row(parent, "Strict Mode (Primary TF Only)", 'adx_manual_control_strict', 7)
        self.create_checkbox_row(parent, "Verbose ADX Logs", 'verbose_adx_analysis', 8)

    def create_macro_inputs(self, parent):
        self.create_checkbox_row(parent, "Enable Fundamental Analysis", 'use_fundamental_analysis', 0)
        self.create_checkbox_row(parent, "Enable Sentiment Analysis", 'use_sentiment_analysis', 1)
        self.create_checkbox_row(parent, "Enable Macro Filter (Skip Trades)", 'use_macro_filter', 2)
        
        self.create_checkbox_row(parent, "Analyze Output (COT)", 'analyze_cot_reports', 3)
        self.create_checkbox_row(parent, "Analyze Interest Rates", 'analyze_interest_rates', 4)
        self.create_checkbox_row(parent, "Analyze News", 'analyze_news', 5)
        
        self.create_input_row(parent, "Macro Confidence Min (%):", 'macro_confidence_min', 6, float)
        self.create_checkbox_row(parent, "Skip Trades Against Macro", 'skip_trades_against_macro', 7)

    def create_limit_inputs(self, parent):
        self.create_input_row(parent, "Max Daily Loss ($): (-1 for unlimited)", 'max_daily_losses', 0, float)
        self.create_input_row(parent, "Max Daily Loss Count: (-1 for unlimited)", 'max_daily_loss_count', 1, int)
        self.create_input_row(parent, "Max Daily Loss Per Symbol ($):", 'max_daily_losses_per_symbol', 2, float)
        self.create_input_row(parent, "Max Daily Loss Count Per Symbol:", 'max_daily_loss_count_per_symbol', 3, int)


    def load_current_config_to_ui(self):
        """Populate UI fields from CONFIG"""
        for key, info in self.inputs.items():
            if key in CONFIG:
                value = CONFIG[key]
                widget = info['entry']
                type_cast = info['type']
                
                if type_cast == bool:
                    if value:
                        widget.select()
                    else:
                        widget.deselect()
                else:
                    widget.delete(0, tk.END)
                    widget.insert(0, str(value))

    def save_config(self):
        """Save UI values to config.json"""
        new_config = {}
        error_fields = []
        
        for key, info in self.inputs.items():
            widget = info['entry']
            type_cast = info['type']
            
            try:
                if type_cast == bool:
                    new_config[key] = bool(widget.get())
                else:
                    val_str = widget.get()
                    if type_cast == int:
                        new_config[key] = int(val_str)
                    elif type_cast == float:
                        new_config[key] = float(val_str)
                    else:
                        new_config[key] = val_str
            except ValueError:
                error_fields.append(key)
        
        if error_fields:
            self.log_message(f"Error saving: Invalid values for {', '.join(error_fields)}")
            return
            
        # Preserve keys that are not in UI but are in CONFIG (like api keys loaded from env or secrets)
        # Actually CONFIG has everything. We just merge.
        # But we need to handle nested dicts (trailing_levels).
        # For this simple GUI, we are not editing trailing_levels yet.
        # So we should be careful not to overwrite them with nothing if we were recreating the whole dict.
        # But we are creating a partial dict `new_config` containing only UI fields.
        
        # We should merge with existing CONFIG to ensure we don't lose non-UI settings when writing to file?
        # Ideally, we only save what we changed or save everything that is legally JSON-able.
        
        # Let's save a clean dict of ALL current config + updates.
        # IMPORTANT: We need to handle `trailing_levels` which is a dict with float keys.
        # JSON only supports string keys.
        
        config_to_save = CONFIG.copy()
        config_to_save.update(new_config)
        
        # Serialize dict keys for JSON
        if 'trailing_levels' in config_to_save:
            # We don't have UI for this yet, so it stays as is in CONFIG
            # But to save to JSON, keys must be strings.
            # config.py reload logic handles string keys back to float.
            pass
            
        try:
            with open('config.json', 'w') as f:
                json.dump(config_to_save, f, indent=4)
            self.log_message("Configuration saved successfully to config.json")
            
            # Update the global CONFIG in memory too, so if we run the bot, it has latest
            CONFIG.update(new_config)
            
        except Exception as e:
            self.log_message(f"Failed to save config: {e}")

    def start_bot(self):
        if self.is_running:
            return
            
        self.save_config() # Auto-save before run
        
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal", fg_color="darkred")
        self.status_label.configure(text="Status: RUNNING", text_color="green")
        
        self.is_running = True
        self.log_message("\n--- STARTING BOT ---\n")
        
        # Run main.py with --live argument
        # We don't need to pass all args because main.py loads config.json now!
        cmd = [sys.executable, "-u", "main.py", "--live"]
        
        try:
            # Use separate process group on windows to ensure clean kill
            if os.name == 'nt':
                creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
            else:
                creationflags = 0

            self.bot_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                creationflags=creationflags
            )
            
            # Start threads to read output
            threading.Thread(target=self.read_output, args=(self.bot_process.stdout, "stdout"), daemon=True).start()
            threading.Thread(target=self.read_output, args=(self.bot_process.stderr, "stderr"), daemon=True).start()
            
            # Start thread to monitor process exit
            threading.Thread(target=self.monitor_process, daemon=True).start()
            
        except Exception as e:
            self.log_message(f"Failed to start bot: {e}")
            self.stop_bot_ui_cleanup()

    def stop_bot(self):
        if not self.is_running or not self.bot_process:
            return
            
        self.log_message("\n--- STOPPING BOT ---\n")
        
        # Send SIGTERM/SIGINT
        if os.name == 'nt':
            # Windows: use taskkill to be sure, or simply terminate
            # subprocess.terminate() on windows is essentially kill
            # But we used CREATE_NEW_PROCESS_GROUP, so we should send formatted signal if possible
            # bot_process.terminate() is usually enough.
            self.bot_process.terminate()
        else:
            self.bot_process.terminate()
            
        # UI cleanup happens in monitor_process when it detects exit

    def stop_bot_ui_cleanup(self):
        self.is_running = False
        self.bot_process = None
        self.start_button.configure(state="normal")
        self.stop_button.configure(state="disabled", fg_color="gray")
        self.status_label.configure(text="Status: STOPPED", text_color="red")

    def monitor_process(self):
        if self.bot_process:
            self.bot_process.wait()
            self.log_message(f"\nBot process exited with code {self.bot_process.returncode}")
            
            # Schedule UI update on main thread
            self.after(0, self.stop_bot_ui_cleanup)

    def read_output(self, pipe, name):
        """Read stdout/stderr and put into queue"""
        for line in iter(pipe.readline, ''):
            self.log_queue.put(line)
        pipe.close()

    def update_logs(self):
        """Check queue and update text widget"""
        try:
            while True:
                line = self.log_queue.get_nowait()
                self.log_message(line.strip(), newline=True)
        except queue.Empty:
            pass
        
        self.after(100, self.update_logs)

    def log_message(self, message, newline=True):
        self.log_textbox.configure(state="normal")
        self.log_textbox.insert("end", message + ("\n" if newline else ""))
        self.log_textbox.see("end")
        self.log_textbox.configure(state="disabled")

def main():
    app = AladinGUI()
    app.mainloop()

if __name__ == "__main__":
    main()
