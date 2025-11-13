"""
MT5 Fibonacci Chart Drawer
Draws Fibonacci levels, swing points, and entry signals directly on MT5 charts
Works in both live trading and backtesting modes
"""

import logging
from datetime import datetime, timedelta
from config import CONFIG

logger = logging.getLogger(__name__)

# Only import MT5 if available
MT5_AVAILABLE = True
if CONFIG.get('draw_on_chart', True):   
    try:
        import MetaTrader5 as mt5
        MT5_AVAILABLE = True
    except ImportError:
        logger.warning("MetaTrader5 not available. Chart drawing disabled.")
        MT5_AVAILABLE = False

# Color constants for MT5 (RGB format)
COLORS = {
    'swing_high': 0xFF0000,      # Red
    'swing_low': 0x0000FF,       # Blue
    'fib_618': 0xFFA500,         # Orange
    'fib_705': 0xFFD700,         # Gold
    'fib_786': 0x00FF00,         # Green
    'fib_0': 0x808080,           # Gray (100% retracement)
    'fib_1': 0x800080,           # Purple (swing point)
    'entry_long': 0x00FF00,      # Green (long entry)
    'entry_short': 0xFF0000,     # Red (short entry)
    'support': 0x0000FF,         # Blue
    'resistance': 0xFF0000,      # Red
}

# MT5 Style constants - use integers if constants not available
def get_mt5_styles():
    """Get MT5 style constants, with fallback values"""
    styles = {}
    
    if MT5_AVAILABLE:
        try:
            styles['STYLE_SOLID'] = mt5.STYLE_SOLID
            styles['STYLE_DOTS'] = mt5.STYLE_DOTS
            styles['STYLE_DASHDOT'] = mt5.STYLE_DASHDOT
            styles['STYLE_DASHED'] = mt5.STYLE_DASHED
        except (AttributeError, NameError):
            # Fallback to integer values if constants not available
            styles['STYLE_SOLID'] = 0
            styles['STYLE_DOTS'] = 1
            styles['STYLE_DASHDOT'] = 3
            styles['STYLE_DASHED'] = 2
    else:
        styles['STYLE_SOLID'] = 0
        styles['STYLE_DOTS'] = 1
        styles['STYLE_DASHDOT'] = 3
        styles['STYLE_DASHED'] = 2
    
    return styles

MT5_STYLES = get_mt5_styles()

class MT5FibonacciDrawer:
    """Draw Fibonacci levels and setup information on MT5 charts"""
    
    def __init__(self, symbol):
        self.symbol = symbol
        self.drawn_objects = []
        self.max_objects = 100  # MT5 limit precaution
        
        if not MT5_AVAILABLE:
            logger.warning("MT5 not available - chart drawing disabled")
    
    def clear_old_objects(self, keep_recent=50):
        """Remove old drawing objects to avoid clutter"""
        if not MT5_AVAILABLE:
            return False
        
        if len(self.drawn_objects) > keep_recent:
            objects_to_remove = self.drawn_objects[:-keep_recent]
            for obj_name in objects_to_remove:
                try:
                    mt5.chart_object_delete(self.symbol, mt5.CHART_TYPE_BID, obj_name)
                except Exception as e:
                    logger.debug(f"Could not delete object {obj_name}: {e}")
            self.drawn_objects = self.drawn_objects[-keep_recent:]
        
        return True
    
    def draw_horizontal_line(self, level_name, price, color, width=1, style=None):
        """Draw horizontal line for Fibonacci level"""
        if not MT5_AVAILABLE:
            return False
        
        if style is None:
            style = MT5_STYLES['STYLE_SOLID']
        
        try:
            obj_name = f"FIB_{level_name}_{datetime.now().strftime('%H%M%S%f')}"
            
            result = mt5.chart_object_create(
                self.symbol,
                obj_name,
                mt5.OBJ_HLINE,
                mt5.CHART_TYPE_BID,
                datetime.now(),
                price
            )
            
            if result:
                try:
                    mt5.chart_object_set_integer(
                        self.symbol,
                        obj_name,
                        mt5.OBJPROP_COLOR,
                        color
                    )
                    mt5.chart_object_set_integer(
                        self.symbol,
                        obj_name,
                        mt5.OBJPROP_WIDTH,
                        width
                    )
                    mt5.chart_object_set_integer(
                        self.symbol,
                        obj_name,
                        mt5.OBJPROP_STYLE,
                        style
                    )
                except Exception as e:
                    logger.debug(f"Could not set line properties: {e}")
                
                self.drawn_objects.append(obj_name)
                return True
        except Exception as e:
            logger.debug(f"Failed to draw horizontal line: {e}")
        
        return False
    
    def draw_text_label(self, label_name, price, text, color, font_size=10):
        """Draw text label on chart"""
        if not MT5_AVAILABLE:
            return False
        
        try:
            obj_name = f"LABEL_{label_name}_{datetime.now().strftime('%H%M%S%f')}"
            
            result = mt5.chart_object_create(
                self.symbol,
                obj_name,
                mt5.OBJ_TEXT,
                mt5.CHART_TYPE_BID,
                datetime.now(),
                price,
                text
            )
            
            if result:
                try:
                    mt5.chart_object_set_integer(
                        self.symbol,
                        obj_name,
                        mt5.OBJPROP_COLOR,
                        color
                    )
                    mt5.chart_object_set_integer(
                        self.symbol,
                        obj_name,
                        mt5.OBJPROP_FONTSIZE,
                        font_size
                    )
                    mt5.chart_object_set_string(
                        self.symbol,
                        obj_name,
                        mt5.OBJPROP_FONT,
                        "Arial"
                    )
                except Exception as e:
                    logger.debug(f"Could not set label properties: {e}")
                
                self.drawn_objects.append(obj_name)
                return True
        except Exception as e:
            logger.debug(f"Failed to draw text label: {e}")
        
        return False
    
    def draw_vertical_line(self, line_name, time_point, color, width=1, style=None):
        """Draw vertical line at specific time"""
        if not MT5_AVAILABLE:
            return False
        
        if style is None:
            style = MT5_STYLES['STYLE_SOLID']
        
        try:
            obj_name = f"VLINE_{line_name}_{datetime.now().strftime('%H%M%S%f')}"
            
            result = mt5.chart_object_create(
                self.symbol,
                obj_name,
                mt5.OBJ_VLINE,
                mt5.CHART_TYPE_BID,
                time_point
            )
            
            if result:
                try:
                    mt5.chart_object_set_integer(
                        self.symbol,
                        obj_name,
                        mt5.OBJPROP_COLOR,
                        color
                    )
                    mt5.chart_object_set_integer(
                        self.symbol,
                        obj_name,
                        mt5.OBJPROP_WIDTH,
                        width
                    )
                    mt5.chart_object_set_integer(
                        self.symbol,
                        obj_name,
                        mt5.OBJPROP_STYLE,
                        style
                    )
                except Exception as e:
                    logger.debug(f"Could not set line properties: {e}")
                
                self.drawn_objects.append(obj_name)
                return True
        except Exception as e:
            logger.debug(f"Failed to draw vertical line: {e}")
        
        return False
    
    def draw_rectangle(self, rect_name, time1, price1, time2, price2, color, width=1):
        """Draw rectangle (useful for highlighting swing ranges)"""
        if not MT5_AVAILABLE:
            return False
        
        try:
            obj_name = f"RECT_{rect_name}_{datetime.now().strftime('%H%M%S%f')}"
            
            result = mt5.chart_object_create(
                self.symbol,
                obj_name,
                mt5.OBJ_RECTANGLE,
                mt5.CHART_TYPE_BID,
                time1,
                price1,
                time2,
                price2
            )
            
            if result:
                try:
                    mt5.chart_object_set_integer(
                        self.symbol,
                        obj_name,
                        mt5.OBJPROP_COLOR,
                        color
                    )
                    mt5.chart_object_set_integer(
                        self.symbol,
                        obj_name,
                        mt5.OBJPROP_WIDTH,
                        width
                    )
                    mt5.chart_object_set_integer(
                        self.symbol,
                        obj_name,
                        mt5.OBJPROP_FILL,
                        False
                    )
                except Exception as e:
                    logger.debug(f"Could not set rectangle properties: {e}")
                
                self.drawn_objects.append(obj_name)
                return True
        except Exception as e:
            logger.debug(f"Failed to draw rectangle: {e}")
        
        return False
    
    def draw_fibonacci_setup(self, fib_setup, current_time):
        """
        Draw complete Fibonacci setup on chart
        
        Args:
            fib_setup: Fibonacci setup dictionary from fibonacci.py
            current_time: Current time for reference
        """
        if not MT5_AVAILABLE:
            return False
        
        try:
            setup_type = fib_setup['type']
            swing_high = fib_setup['swing_high']
            swing_low = fib_setup['swing_low']
            fib_levels = fib_setup['fib_levels']
            
            # Draw swing high point
            self.draw_horizontal_line(
                f"SWING_HIGH_{swing_high['index']}",
                swing_high['price'],
                COLORS['swing_high'],
                width=2,
                style=MT5_STYLES['STYLE_DASHDOT']
            )
            self.draw_text_label(
                f"SH_{swing_high['index']}",
                swing_high['price'] * 1.0001,
                f"SH: {swing_high['price']:.5f}",
                COLORS['swing_high'],
                font_size=8
            )
            
            # Draw swing low point
            self.draw_horizontal_line(
                f"SWING_LOW_{swing_low['index']}",
                swing_low['price'],
                COLORS['swing_low'],
                width=2,
                style=MT5_STYLES['STYLE_DASHDOT']
            )
            self.draw_text_label(
                f"SL_{swing_low['index']}",
                swing_low['price'] * 0.9999,
                f"SL: {swing_low['price']:.5f}",
                COLORS['swing_low'],
                font_size=8
            )
            
            # Draw Fibonacci levels
            fib_colors = {
                0.618: COLORS['fib_618'],
                0.705: COLORS['fib_705'],
                0.786: COLORS['fib_786'],
            }
            
            for level_value, level_price in fib_levels.items():
                color = fib_colors.get(level_value, COLORS['fib_618'])
                
                self.draw_horizontal_line(
                    f"FIB_{level_value}",
                    level_price,
                    color,
                    width=1,
                    style=MT5_STYLES['STYLE_DOTS']
                )
                
                self.draw_text_label(
                    f"FIB_LABEL_{level_value}",
                    level_price,
                    f"{level_value:.3f}: {level_price:.5f}",
                    color,
                    font_size=8
                )
            
            logger.info(f"✓ Fibonacci setup drawn on {self.symbol} chart")
            return True
        
        except Exception as e:
            logger.error(f"Error drawing Fibonacci setup: {e}")
            return False
    
    def draw_entry_signal(self, entry_signal, fib_setup):
        """
        Draw entry signal on chart with all relevant information
        
        Args:
            entry_signal: Entry signal dictionary from fibonacci.py
            fib_setup: Associated Fibonacci setup
        """
        if not MT5_AVAILABLE:
            return False
        
        try:
            signal_type = entry_signal['type']
            fib_level = entry_signal['fib_level']
            fib_price = entry_signal['fib_price']
            entry_price = entry_signal['entry_price']
            current_time = datetime.now()
            
            # Choose color based on signal type
            color = COLORS['entry_long'] if signal_type == 'long' else COLORS['entry_short']
            signal_label = "BUY" if signal_type == 'long' else "SELL"
            
            # Draw entry level
            self.draw_horizontal_line(
                f"ENTRY_{signal_type}",
                fib_price,
                color,
                width=3,
                style=MT5_STYLES['STYLE_SOLID']
            )
            
            # Draw entry signal label with details
            label_text = f"{signal_label} @ Fib {fib_level:.3f}: {fib_price:.5f}"
            self.draw_text_label(
                f"ENTRY_LABEL_{signal_type}",
                fib_price,
                label_text,
                color,
                font_size=10
            )
            
            # Draw swing range rectangle
            swing_high = fib_setup['swing_high']
            swing_low = fib_setup['swing_low']
            
            # Use time from swing points
            time_high = swing_high['time'] if isinstance(swing_high['time'], datetime) else current_time
            time_low = swing_low['time'] if isinstance(swing_low['time'], datetime) else current_time
            
            if signal_type == 'long':
                self.draw_rectangle(
                    f"RANGE_LONG",
                    time_high - timedelta(hours=1),
                    swing_high['price'],
                    current_time,
                    swing_low['price'],
                    COLORS['support'],
                    width=1
                )
            else:
                self.draw_rectangle(
                    f"RANGE_SHORT",
                    time_high - timedelta(hours=1),
                    swing_high['price'],
                    current_time,
                    swing_low['price'],
                    COLORS['resistance'],
                    width=1
                )
            
            logger.info(f"✓ Entry signal drawn on {self.symbol} chart")
            return True
        
        except Exception as e:
            logger.error(f"Error drawing entry signal: {e}")
            return False
    
    def clear_all_fibonacci_objects(self):
        """Clear all Fibonacci-related objects from chart"""
        if not MT5_AVAILABLE:
            return False
        
        try:
            for obj_name in self.drawn_objects:
                try:
                    mt5.chart_object_delete(self.symbol, mt5.CHART_TYPE_BID, obj_name)
                except Exception as e:
                    logger.debug(f"Could not delete object {obj_name}: {e}")
            
            self.drawn_objects = []
            logger.info(f"✓ Cleared all Fibonacci objects from {self.symbol} chart")
            return True
        
        except Exception as e:
            logger.error(f"Error clearing objects: {e}")
            return False


def draw_fibonacci_analysis(symbol, valid_setups, entry_signal=None):
    """
    Convenience function to draw all Fibonacci analysis on chart
    
    Usage in live_trading.py:
        from mt5_chart_drawer import draw_fibonacci_analysis
        
        # After finding entry signal
        draw_fibonacci_analysis(symbol, valid_setups, entry_signal)
    
    Args:
        symbol: Trading symbol
        valid_setups: List of valid Fibonacci setups
        entry_signal: Entry signal dict (optional)
    """
    if not MT5_AVAILABLE:
        logger.debug("MT5 not available, cannot draw on chart")
        return False
    
    try:
        drawer = MT5FibonacciDrawer(symbol)
        
        # Clear old objects
        drawer.clear_old_objects(keep_recent=30)
        
        # Draw all valid setups
        for setup in valid_setups:
            drawer.draw_fibonacci_setup(setup, datetime.now())
        
        # Draw entry signal if present
        if entry_signal:
            for setup in valid_setups:
                if setup == entry_signal['setup']:
                    drawer.draw_entry_signal(entry_signal, setup)
                    break
        
        return True
    
    except Exception as e:
        logger.error(f"Error in draw_fibonacci_analysis: {e}")
        return False