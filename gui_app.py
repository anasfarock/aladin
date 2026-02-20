
import customtkinter as ctk
import tkinter as tk
import json
import os
import sys
import subprocess
import threading
import queue
import matplotlib
matplotlib.use("TkAgg")
from config import CONFIG

# Set appearance mode and color theme
ctk.set_appearance_mode("Dark")  # Modes: "System" (standard), "Dark", "Light"
ctk.set_default_color_theme("blue")  # Themes: "blue" (standard), "green", "dark-blue"

class SymbolSelector(ctk.CTkFrame):
    def __init__(self, master, symbols_list, selected_symbols=None, update_callback=None, **kwargs):
        super().__init__(master, **kwargs)
        
        self.symbols_list = symbols_list
        self.selected_symbols = set(selected_symbols) if selected_symbols else set()
        self.checkboxes = {}
        self.update_callback = update_callback
        
        # Search Bar
        self.search_var = tk.StringVar()
        self.search_var.trace("w", self.update_list)
        self.search_entry = ctk.CTkEntry(self, placeholder_text="Search Symbols...", textvariable=self.search_var)
        self.search_entry.pack(fill="x", padx=5, pady=5)
        
        # Select All / None
        self.btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.btn_frame.pack(fill="x", padx=5, pady=2)
        ctk.CTkButton(self.btn_frame, text="All", width=60, height=24, command=self.select_all).pack(side="left", padx=2)
        ctk.CTkButton(self.btn_frame, text="None", width=60, height=24, command=self.deselect_all).pack(side="left", padx=2)
        
        # Scrollable Area
        self.scroll_frame = ctk.CTkScrollableFrame(self, height=200)
        self.scroll_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.update_list()
        
    def update_list(self, *args):
        # Clear current checkboxes
        for cb in self.checkboxes.values():
            cb.destroy()
        self.checkboxes.clear()
        
        search_term = self.search_var.get().lower()
        
        for symbol in self.symbols_list:
            if search_term in symbol.lower():
                var = ctk.BooleanVar(value=symbol in self.selected_symbols)
                cb = ctk.CTkCheckBox(
                    self.scroll_frame, 
                    text=symbol, 
                    variable=var,
                    command=lambda s=symbol, v=var: self.toggle_symbol(s, v)
                )
                cb.pack(anchor="w", pady=2)
                self.checkboxes[symbol] = cb

    def toggle_symbol(self, symbol, var):
        if var.get():
            self.selected_symbols.add(symbol)
        else:
            self.selected_symbols.discard(symbol)
        if self.update_callback:
            self.update_callback()
            
    def select_all(self):
        search_term = self.search_var.get().lower()
        for symbol, cb in self.checkboxes.items():
            if search_term in symbol.lower():
                cb.select()
                self.selected_symbols.add(symbol)
        if self.update_callback:
            self.update_callback()
    
    def deselect_all(self):
        search_term = self.search_var.get().lower()
        for symbol, cb in self.checkboxes.items():
            if search_term in symbol.lower():
                cb.deselect()
                self.selected_symbols.discard(symbol)
        if self.update_callback:
            self.update_callback()

    def get_selected(self):
        return list(self.selected_symbols)

class AladinGUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Aladin Trading Bot Control Panel")
        self.geometry("1100x850")

        # Bot Process
        self.bot_process = None
        self.is_running = False
        self.log_queue = queue.Queue()
        
        # Symbol Selector Reference
        self.symbol_selector = None

        self.create_widgets()
        self.load_current_config_to_ui()
        
        # Start log updater
        self.after(100, self.update_logs)
        
        # Auto-fetch symbols on startup (delayed slightly to let UI render)
        self.after(500, lambda: threading.Thread(target=self.fetch_symbols_from_mt5, daemon=True).start())

    def create_widgets(self):
        # Configure grid layout (1x2)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Sidebar setup
        self.sidebar_frame = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(6, weight=1)

        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="Aladin Bot", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        # Status Label
        self.status_label = ctk.CTkLabel(self.sidebar_frame, text="Bot Status: STOPPED", text_color="red")
        self.status_label.grid(row=1, column=0, padx=20, pady=10)

        # Control Buttons
        self.start_button = ctk.CTkButton(self.sidebar_frame, text="Start Bot Process", command=self.start_bot, fg_color="green", hover_color="darkgreen")
        self.start_button.grid(row=2, column=0, padx=20, pady=10)

        self.stop_button = ctk.CTkButton(self.sidebar_frame, text="Stop Bot Process", command=self.stop_bot, fg_color="darkred", hover_color="red", state="disabled")
        self.stop_button.grid(row=3, column=0, padx=20, pady=10)
        
        # Trading Toggle Switch
        ctk.CTkLabel(self.sidebar_frame, text="Trading Execution:", font=ctk.CTkFont(size=12, weight="bold")).grid(row=4, column=0, padx=20, pady=(20,0))
        self.trading_switch = ctk.CTkSwitch(self.sidebar_frame, text="DISABLED", command=self.toggle_trading, onvalue="ENABLED", offvalue="DISABLED")
        self.trading_switch.grid(row=5, column=0, padx=20, pady=10)
        # Default to Config state
        if CONFIG.get('trading_enabled', False):
            self.trading_switch.select()
            self.trading_switch.configure(text="ENABLED")
        else:
            self.trading_switch.deselect()
            self.trading_switch.configure(text="DISABLED")
        
        # Save Config Button
        self.save_button = ctk.CTkButton(self.sidebar_frame, text="Save Config", command=self.save_config)
        self.save_button.grid(row=7, column=0, padx=20, pady=10)

        # Main Content Area (Tabs)
        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=0, column=1, padx=(10, 10), pady=(10, 10), sticky="nsew")

        # Create Tabs
        self.tab_dashboard = self.tabview.add("Log Output")
        self.tab_trading = self.tabview.add("Trading")
        self.tab_indicators = self.tabview.add("Indicators")
        self.tab_risk = self.tabview.add("Risk")
        self.tab_adx = self.tabview.add("ADX Filter")
        self.tab_macro = self.tabview.add("Macro")
        self.tab_loss_limits = self.tabview.add("Daily Limits")
        self.tab_charts = self.tabview.add("Charts")

        # --- Dashboard Tab (Logs) ---
        self.tab_dashboard.grid_columnconfigure(0, weight=1)
        self.tab_dashboard.grid_rowconfigure(0, weight=1)
        
        self.log_textbox = ctk.CTkTextbox(self.tab_dashboard, width=800, height=600)
        self.log_textbox.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        self.log_textbox.configure(state="disabled") # Read-only initially

        # --- Trading Tab ---
        self.create_trading_inputs(self.tab_trading)

        # --- Indicators Tab ---
        self.create_indicator_inputs(self.tab_indicators)

        # --- Risk Tab ---
        self.create_risk_inputs(self.tab_risk)

        # --- ADX Tab ---
        self.create_adx_inputs(self.tab_adx)
        
        # --- Macro Tab ---
        self.create_macro_inputs(self.tab_macro)

        # --- Daily Limits Tab ---
        self.create_limit_inputs(self.tab_loss_limits)

        # --- Charts Tab ---
        self.create_chart_tab(self.tab_charts)

    def create_chart_tab(self, parent):
        parent.grid_columnconfigure(0, weight=3) # Chart area
        parent.grid_columnconfigure(1, weight=1) # Setup list area
        parent.grid_rowconfigure(1, weight=1)
        
        # Controls Frame (Spans both columns)
        controls = ctk.CTkFrame(parent)
        controls.grid(row=0, column=0, columnspan=2, sticky="ew", padx=10, pady=5)
        
        # Symbol Selector
        ctk.CTkLabel(controls, text="Symbol:").pack(side="left", padx=5)
        self.chart_symbol_var = ctk.StringVar(value=CONFIG.get('symbol', 'USDCAD'))
        self.chart_symbol_menu = ctk.CTkOptionMenu(controls, variable=self.chart_symbol_var, values=CONFIG.get('symbols', ['USDCAD']))
        self.chart_symbol_menu.pack(side="left", padx=5)
        
        # Timeframe Selector
        ctk.CTkLabel(controls, text="Timeframe:").pack(side="left", padx=5)
        self.chart_tf_var = ctk.StringVar(value=CONFIG.get('timeframe_entry', 'M15'))
        self.chart_tf_menu = ctk.CTkOptionMenu(controls, variable=self.chart_tf_var, values=['M1', 'M5', 'M15', 'M30', 'H1', 'H4'])
        self.chart_tf_menu.pack(side="left", padx=5)
        
        # Refresh Button
        ctk.CTkButton(controls, text="Refresh Chart", command=self.update_chart).pack(side="left", padx=10)
        
        # Auto-Refresh Toggle
        self.auto_refresh_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(controls, text="Auto-Refresh (5s)", variable=self.auto_refresh_var).pack(side="left", padx=10)

        # Chart Container (Left)
        self.chart_frame = ctk.CTkFrame(parent)
        self.chart_frame.grid(row=1, column=0, sticky="nsew", padx=(10, 5), pady=5)
        
        # Setups List Container (Right)
        self.setups_frame = ctk.CTkScrollableFrame(parent, label_text="Detected Fib Setups")
        self.setups_frame.grid(row=1, column=1, sticky="nsew", padx=(5, 10), pady=5)
        
        # Placeholder for Canvas
        self.canvas = None
        self.current_setups = [] # Store setups for reference
        self.current_df = None   # Store df for reference
        self.selected_setup_signature = None # Tuple: (type, sh_time, sl_time)
        
        # Start Auto-Refresh Loop
        self.after(5000, self.auto_refresh_chart)

    def auto_refresh_chart(self):
        try:
            if not self.winfo_exists():
                return
            if self.auto_refresh_var.get() and self.tabview.get() == "Charts":
                self.update_chart()
        except Exception:
            pass
        self.after(5000, self.auto_refresh_chart)

    def update_chart(self):
        symbol = self.chart_symbol_var.get()
        tf_name = self.chart_tf_var.get()
        
        # Run in thread to avoid freezing UI
        threading.Thread(target=self._fetch_data, args=(symbol, tf_name), daemon=True).start()

    def _fetch_data(self, symbol, tf_name):
        try:
            import MetaTrader5 as mt5
            import pandas as pd
            from fibonacci import FibonacciTracker
            
            # Map TF string to variable
            tf_map = {
                'M1': mt5.TIMEFRAME_M1, 'M5': mt5.TIMEFRAME_M5,
                'M15': mt5.TIMEFRAME_M15, 'M30': mt5.TIMEFRAME_M30,
                'H1': mt5.TIMEFRAME_H1, 'H4': mt5.TIMEFRAME_H4
            }
            tf = tf_map.get(tf_name, mt5.TIMEFRAME_M15)
            
            if not mt5.initialize():
                return

            # Fetch more candles to see older setups
            rates = mt5.copy_rates_from_pos(symbol, tf, 0, 300)
            mt5.shutdown()
            
            if rates is None or len(rates) == 0:
                print(f"No data for {symbol}")
                return

            df = pd.DataFrame(rates)
            df['time'] = pd.to_datetime(df['time'], unit='s')
            
            # Identify Fib setups (needs 'time' column)
            tracker = FibonacciTracker()
            tracker.update_fibonacci_setups(df)
            valid_setups = tracker.get_valid_setups()
            
            # Set index for mplfinance
            df.set_index('time', inplace=True)
            
            # Pass data to main thread for updates
            self.after(0, lambda: self._handle_data_update(df, valid_setups))
            
        except Exception as e:
            print(f"Data fetch error: {e}")

    def _handle_data_update(self, df, valid_setups):
        self.current_df = df
        self.current_setups = valid_setups
        
        # Determine what to draw based on previous selection
        setups_to_draw = valid_setups # Default to all
        
        if self.selected_setup_signature:
            # Try to find the selected setup in the new list
            found_setup = None
            sig_type, sig_sh_time, sig_sl_time = self.selected_setup_signature
            
            for setup in valid_setups:
                s_type = setup['type']
                s_sh_time = setup['swing_high']['time']
                s_sl_time = setup['swing_low']['time']
                
                if (s_type == sig_type and 
                    s_sh_time == sig_sh_time and 
                    s_sl_time == sig_sl_time):
                    found_setup = setup
                    break
            
            if found_setup:
                setups_to_draw = [found_setup]
            else:
                # Setup no longer valid or not found, revert to all (or clear?)
                # user probably wants to know it's gone, but reverting to all is safest
                self.selected_setup_signature = None
        
        # Update Setups List UI
        self._update_setups_list_ui()
        
        # Draw chart
        self._draw_chart(df, setups_to_draw)

    def _update_setups_list_ui(self):
        # Clear existing widgets
        for widget in self.setups_frame.winfo_children():
            widget.destroy()
            
        if not self.current_setups:
            ctk.CTkLabel(self.setups_frame, text="No valid setups found").pack(pady=10)
            return

        # "Show All" Button
        def select_all():
            self.selected_setup_signature = None
            self._draw_chart(self.current_df, self.current_setups)
            
        btn_all = ctk.CTkButton(self.setups_frame, text="Show All Setups", 
                      command=select_all,
                      fg_color="gray" if self.selected_setup_signature else "green") # Highlight if selected
        btn_all.pack(pady=(0, 5), fill="x")

        # List individual setups
        for i, setup in enumerate(reversed(self.current_setups)): # Newest first
            setup_type = "Bullish" if setup['type'] == 'bullish_retracement' else "Bearish"
            age = setup['age']
            
            # Create signature
            sig = (setup['type'], setup['swing_high']['time'], setup['swing_low']['time'])
            is_selected = (self.selected_setup_signature == sig)
            
            btn_text = f"#{len(self.current_setups)-i} {setup_type}\nAge: {age} bars"
            
            def select_setup(s=setup, signature=sig):
                self.selected_setup_signature = signature
                self._draw_chart(self.current_df, [s])
                # We could trigger UI update to highlight button, but simpler to wait for next refresh 
                # or just accept that list highlighting updates slowly. 
                # Actually, let's force list update to show highlight immediately
                self._update_setups_list_ui()

            # Create a button for each setup
            btn = ctk.CTkButton(
                self.setups_frame, 
                text=btn_text,
                command=select_setup,
                fg_color="green" if is_selected else "blue" # Simple highlighting
            )
            btn.pack(pady=2, fill="x")

    def _draw_chart(self, df, setups_to_draw):
        try:
            if not self.winfo_exists():
                return

            import mplfinance as mpf
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            import matplotlib.pyplot as plt
            
            # Prepare Plot
            mc = mpf.make_marketcolors(up='green', down='red', inherit=True)
            s = mpf.make_mpf_style(base_mpf_style='nightclouds', marketcolors=mc)
            
            # Add Fib Lines
            alines = []
            
            # We need to know which setups we are drawing to label them
            drawn_setups = setups_to_draw if setups_to_draw else []
            
            t_start = df.index[0]
            t_end = df.index[-1]
            
            for setup in drawn_setups:
                swing_high = setup['swing_high']['price']
                swing_low = setup['swing_low']['price']
                levels = setup['fib_levels']
                
                # Draw lines across whole chart for visibility
                alines.append([(t_start, swing_high), (t_end, swing_high)]) # SH
                alines.append([(t_start, swing_low), (t_end, swing_low)])   # SL
                
                for lvl, price in levels.items():
                    alines.append([(t_start, price), (t_end, price)])

            # Plot to Figure
            fig, axlist = mpf.plot(df, type='candle', style=s, volume=False, 
                               returnfig=True, alines=dict(alines=alines, colors=['red', 'blue'] + ['orange']*3, linewidths=1, alpha=0.7))
            
            # Add Text Labels
            if drawn_setups:
                ax = axlist[0]
                x_pos = len(df) - 5
                
                def add_label(y, text, color, align_y='center'):
                     ax.text(x_pos, y, text, color=color, fontsize=8, va=align_y, ha='right', fontweight='bold',
                            bbox=dict(facecolor='black', alpha=0.5, edgecolor='none'))

                # Label each setup
                for setup in drawn_setups:
                    swing_high = setup['swing_high']['price']
                    swing_low = setup['swing_low']['price']
                    levels = setup['fib_levels']
                    
                    add_label(swing_high, f"SH: {swing_high:.5f}", 'white', 'bottom')
                    add_label(swing_low, f"SL: {swing_low:.5f}", 'white', 'top')
                    
                    for lvl, price in levels.items():
                        add_label(price, f"Fib {lvl}: {price:.5f}", 'orange')
            
            # Clean up old
            if hasattr(self, 'current_fig') and self.current_fig:
                plt.close(self.current_fig)
            self.current_fig = fig

            if self.canvas:
                self.canvas.get_tk_widget().destroy()
                
            self.canvas = FigureCanvasTkAgg(fig, master=self.chart_frame)
            self.canvas.draw()
            self.canvas.get_tk_widget().pack(fill="both", expand=True)

        except Exception as e:
            print(f"Drawing error: {e}")
            import traceback
            traceback.print_exc()

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

    def create_option_row(self, parent, label_text, config_key, row, options, tooltip=None):
        label = ctk.CTkLabel(parent, text=label_text, anchor="w")
        label.grid(row=row, column=0, padx=10, pady=5, sticky="w")
        
        option_menu = ctk.CTkOptionMenu(parent, values=options, width=200)
        option_menu.grid(row=row, column=1, padx=10, pady=5, sticky="w")
        
        if not hasattr(self, 'inputs'):
            self.inputs = {}
            
        self.inputs[config_key] = {'entry': option_menu, 'type': str}
        return option_menu

    def create_segmented_row(self, parent, label_text, config_key, row, options):
        label = ctk.CTkLabel(parent, text=label_text, anchor="w")
        label.grid(row=row, column=0, padx=10, pady=5, sticky="w")
        
        seg_button = ctk.CTkSegmentedButton(parent, values=options)
        seg_button.grid(row=row, column=1, padx=10, pady=5, sticky="w")
        
        if not hasattr(self, 'inputs'):
            self.inputs = {}
        
        self.inputs[config_key] = {'entry': seg_button, 'type': str}
        return seg_button

    def create_trading_inputs(self, parent):
        # Multi-Symbol Selection
        ctk.CTkLabel(parent, text="Trading Pairs", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, columnspan=2, sticky="w", padx=10)
        
        # Selected symbols display
        self.selected_symbols_label = ctk.CTkLabel(parent, text="Selected: None", wraplength=400, justify="left", text_color="gray")
        self.selected_symbols_label.grid(row=1, column=0, columnspan=2, sticky="w", padx=10)
        
        # Container for selector
        self.selector_frame = ctk.CTkFrame(parent)
        self.selector_frame.grid(row=2, column=0, columnspan=2, padx=10, pady=5, sticky="ew")
        
        self.selector_status = ctk.CTkLabel(self.selector_frame, text="Initializing MT5 connection...")
        self.selector_status.pack()
        
        # Fetch Button (Manual refresh if needed)
        self.fetch_btn = ctk.CTkButton(self.selector_frame, text="Refresh Symbols", command=lambda: threading.Thread(target=self.fetch_symbols_from_mt5, daemon=True).start())
        self.fetch_btn.pack(pady=5)
        
        # Placeholder for the actual list
        self.symbols_container = ctk.CTkFrame(self.selector_frame, fg_color="transparent")
        self.symbols_container.pack(fill="both", expand=True)

        # Other inputs
        self.create_segmented_row(parent, "Entry Timeframe:", 'timeframe_entry', 3, ['M1', 'M5', 'M15', 'M30', 'H1', 'H4'])
        
        ctk.CTkLabel(parent, text="Trend Analysis").grid(row=4, column=0, pady=(10,0), sticky="w")
        
        self.create_checkbox_row(parent, "Use Manual Trend Override", 'use_manual_trend', 5)
        self.create_option_row(parent, "Manual Trend:", 'manual_trend', 6, ['bullish', 'bearish'])
        
        self.create_checkbox_row(parent, "Use Moving Averages", 'use_ma_for_trend', 7)
        self.create_checkbox_row(parent, "Use RSI", 'use_rsi_for_trend', 8)
        self.create_checkbox_row(parent, "Use VWAP", 'use_vwap_for_trend', 9)
        self.create_checkbox_row(parent, "Use Bollinger Bands", 'use_bollinger_for_trend', 10)
        
        self.create_input_row(parent, "Bullish Threshold:", 'trend_bullish_threshold', 11, int)
        self.create_input_row(parent, "Bearish Threshold:", 'trend_bearish_threshold', 12, int)

    def create_indicator_inputs(self, parent):
        # Moving Averages
        ctk.CTkLabel(parent, text="Moving Averages", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, pady=(10,5), sticky="w", padx=10)
        self.create_input_row(parent, "Fast MA Period:", 'ma_fast', 1, int)
        self.create_input_row(parent, "Slow MA Period:", 'ma_slow', 2, int)
        
        # Bollinger Bands
        ctk.CTkLabel(parent, text="Bollinger Bands", font=ctk.CTkFont(weight="bold")).grid(row=3, column=0, pady=(10,5), sticky="w", padx=10)
        self.create_input_row(parent, "Period:", 'boll_period', 4, int)
        self.create_input_row(parent, "Std Deviation:", 'boll_std', 5, float)
        
        # RSI
        ctk.CTkLabel(parent, text="RSI", font=ctk.CTkFont(weight="bold")).grid(row=6, column=0, pady=(10,5), sticky="w", padx=10)
        self.create_input_row(parent, "Period:", 'rsi_period', 7, int)
        
        # VWAP
        ctk.CTkLabel(parent, text="VWAP", font=ctk.CTkFont(weight="bold")).grid(row=8, column=0, pady=(10,5), sticky="w", padx=10)
        self.create_input_row(parent, "Period:", 'vwap_period', 9, int)

    def fetch_symbols_from_mt5(self):
        """Connect to MT5 and fetch all symbols"""
        def _update_ui(status, btn_state):
            self.selector_status.configure(text=status)
            self.fetch_btn.configure(state=btn_state)

        def _log(msg):
            self.log_message(msg)

        try:
            # Update UI from main thread
            self.after(0, _update_ui, "Connecting to MT5...", "disabled")
            
            import MetaTrader5 as mt5
            
            if not mt5.initialize():
                err = mt5.last_error()
                self.after(0, _log, f"MT5 Init failed: {err}")
                self.after(0, _update_ui, f"Connection Failed: {err}", "normal")
                return
                
            symbols_info = mt5.symbols_get()
            if symbols_info:
                symbols_list = [s.name for s in symbols_info]
                symbols_list.sort()
                
                # Update UI in main thread
                self.after(0, lambda: self._update_selector_ui(symbols_list))
            else:
                 self.after(0, _log, "No symbols found in MT5")
                 self.after(0, _update_ui, "No symbols found", "normal")
                 
            mt5.shutdown()
            
        except Exception as e:
            self.after(0, _log, f"Error fetching symbols: {e}")
            self.after(0, _update_ui, "Error fetching symbols", "normal")
        # finally block removed because state restoration is handled in callbacks above
        # to ensure it happens in main thread in correct order

    def _update_selector_ui(self, symbols_list):
        # Create Selector
        current_selected = CONFIG.get('symbols', [])
        if not current_selected and CONFIG.get('symbol'):
            current_selected = [CONFIG['symbol']]
        
        # Check for cached selector to update or create new
        if self.symbol_selector:
            self.symbol_selector.destroy()
        
        self.symbol_selector = SymbolSelector(
            self.symbols_container, 
            symbols_list, 
            current_selected,
            update_callback=self.update_selected_label
        )
        self.symbol_selector.pack(fill="both", expand=True)
        self.selector_status.configure(text=f"Loaded {len(symbols_list)} symbols")
        self.update_selected_label()

    def update_selected_label(self):
        if self.symbol_selector:
            selected = self.symbol_selector.get_selected()
            text = ", ".join(selected)
            if not text:
                text = "None"
            self.selected_symbols_label.configure(text=f"Selected: {text}")

    def toggle_trading(self):
        """Toggle trading logic"""
        is_enabled = self.trading_switch.get() == "ENABLED"
        self.trading_switch.configure(text="ENABLED" if is_enabled else "DISABLED")
        
        # Update Config immediately
        CONFIG['trading_enabled'] = is_enabled
        self.save_config_silent()
        
        status = "ENABLED" if is_enabled else "DISABLED"
        self.log_message(f"Trading Execution {status}")

    def save_config_silent(self):
        """Save config without popup (for toggle)"""
        try:
            self.save_config(silent=True)
        except Exception as e:
            self.log_message(f"Error saving config: {e}")

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
                
                if isinstance(widget, ctk.CTkOptionMenu):
                     widget.set(str(value))
                elif isinstance(widget, ctk.CTkSegmentedButton):
                     widget.set(str(value))
                elif type_cast == bool:
                    if value:
                        widget.select()
                    else:
                        widget.deselect()
                else:
                    widget.delete(0, tk.END)
                    widget.insert(0, str(value))
        
        # Load Symbols if we have a selector (usually not until fetch, but we can init if list exists)
        current_symbols = CONFIG.get('symbols', [])
        if not current_symbols and CONFIG.get('symbol'):
             current_symbols = [CONFIG['symbol']]
             
        if current_symbols:
            txt = ", ".join(current_symbols)
            if hasattr(self, 'selected_symbols_label'):
                self.selected_symbols_label.configure(text=f"Selected: {txt}")

    def save_config(self, silent=False):
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
        
        # Get Symbols
        if self.symbol_selector:
            selected_symbols = self.symbol_selector.get_selected()
            if selected_symbols:
                 new_config['symbols'] = selected_symbols
                 # Update backwards compat 'symbol'
                 new_config['symbol'] = selected_symbols[0]
            else:
                 if not silent: self.log_message("Warning: No symbols selected!")
        
        # Get Trading Toggle state
        if hasattr(self, 'trading_switch'):
             new_config['trading_enabled'] = (self.trading_switch.get() == "ENABLED")

        if error_fields:
            if not silent: self.log_message(f"Error saving: Invalid values for {', '.join(error_fields)}")
            return
            
        try:
            # Update global CONFIG
            CONFIG.update(new_config)
            
            # Write to file
            # Handle special types if needed
            config_to_save = new_config.copy()
            # We want to keep existing config keys that are not in UI
            # But the simplest way here assuming CONFIG has everything loaded is:
            # actually we should be careful. CONFIG might have everything from file.
            # let's just use updated CONFIG
            
            # But keys in CONFIG might be python objects (not likely here, just basic types)
            
            with open('config.json', 'w') as f:
                json.dump(config_to_save, f, indent=4)
            
            if not silent: self.log_message("Configuration saved successfully to config.json")
            
        except Exception as e:
            if not silent: self.log_message(f"Failed to save config: {e}")

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
            self.bot_process.terminate()
        else:
            self.bot_process.terminate()

    def stop_bot_ui_cleanup(self):
        self.is_running = False
        self.bot_process = None
        self.start_button.configure(state="normal")
        self.stop_button.configure(state="disabled", fg_color="gray")
        self.status_label.configure(text="Status: STOPPED", text_color="red")
        
        # Disable trading switch visually if we wanted, but logic says config stays enabled?
        # User might want to keep it enabled for next run.

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
