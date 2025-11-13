"""
Fibonacci Visualization Exporter - OPTIMIZED
Creates focused HTML charts of Fibonacci levels without unnecessary data
Works with any MetaTrader5 version
Optimized for M15 and other timeframes - shows only relevant candles
"""

import logging
import pandas as pd
import os
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False
    logger.warning("Plotly not available. Install with: pip install plotly kaleido")


class FibonacciVisualizer:
    """Create optimized Fibonacci visualizations as HTML/PNG files"""
    
    def __init__(self, symbol, output_dir="fib_charts"):
        self.symbol = symbol
        self.output_dir = output_dir
        
        # Create output directory
        os.makedirs(self.output_dir, exist_ok=True)
    
    def _get_optimal_range(self, df, valid_setups, entry_signal):
        """
        Calculate optimal data range to display
        Shows swing points + some context, not the entire history
        
        Args:
            df: Full price dataframe
            valid_setups: List of Fibonacci setups
            entry_signal: Entry signal
            
        Returns:
            start_idx, end_idx for optimal display range
        """
        # Get the most recent setup
        if not valid_setups:
            # No setups, show last 100 candles
            return max(0, len(df) - 100), len(df)
        
        # Find earliest swing point across all setups
        earliest_swing_idx = len(df)
        for setup in valid_setups:
            swing_low_idx = setup['swing_low']['index']
            swing_high_idx = setup['swing_high']['index']
            
            earliest_swing_idx = min(earliest_swing_idx, swing_low_idx, swing_high_idx)
        
        # Add buffer before the earliest swing point (30% of the range)
        current_bar_idx = len(df) - 1
        range_size = current_bar_idx - earliest_swing_idx
        buffer_bars = max(20, int(range_size * 0.3))  # At least 20 bars buffer
        
        start_idx = max(0, earliest_swing_idx - buffer_bars)
        end_idx = current_bar_idx + 1  # Include current bar
        
        # Ensure we show a reasonable minimum range
        min_bars_to_show = 80
        if (end_idx - start_idx) < min_bars_to_show:
            start_idx = max(0, end_idx - min_bars_to_show)
        
        return start_idx, end_idx
    
    def create_chart(self, df, valid_setups, entry_signal=None, filename=None):
        """
        Create an optimized Fibonacci chart visualization
        
        Args:
            df: Price dataframe with OHLC data
            valid_setups: List of valid Fibonacci setups
            entry_signal: Entry signal dict (optional)
            filename: Output filename (auto-generated if None)
        
        Returns:
            Path to saved HTML file
        """
        if not PLOTLY_AVAILABLE:
            logger.warning("Plotly not available. Cannot create visualization.")
            return None
        
        if filename is None:
            filename = f"{self.symbol}_fib_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        
        filepath = os.path.join(self.output_dir, filename)
        
        try:
            # Get optimal data range to display
            start_idx, end_idx = self._get_optimal_range(df, valid_setups, entry_signal)
            df_display = df.iloc[start_idx:end_idx].copy()
            df_display = df_display.reset_index(drop=True)
            
            logger.debug(f"Displaying {len(df_display)} candles out of {len(df)} total")
            
            # Create figure with 70% for price, 30% for volume
            fig = make_subplots(
                rows=2, cols=1,
                shared_xaxes=True,
                vertical_spacing=0.12,
                row_heights=[0.7, 0.3],
                subplot_titles=("Price Action with Fibonacci Levels", "Volume")
            )
            
            # Add candlesticks
            fig.add_trace(
                go.Candlestick(
                    x=df_display['time'],
                    open=df_display['open'],
                    high=df_display['high'],
                    low=df_display['low'],
                    close=df_display['close'],
                    name='Price',
                    increasing_line_color='green',
                    decreasing_line_color='red'
                ),
                row=1, col=1
            )
            
            # Add volume bars
            if 'tick_volume' in df_display.columns:
                volume_data = df_display['tick_volume']
            elif 'volume' in df_display.columns:
                volume_data = df_display['volume']
            else:
                volume_data = [1000] * len(df_display)  # Default if no volume
            
            colors = ['red' if df_display['close'].iloc[i] < df_display['open'].iloc[i] else 'green' 
                     for i in range(len(df_display))]
            
            fig.add_trace(
                go.Bar(
                    x=df_display['time'],
                    y=volume_data,
                    marker_color=colors,
                    name='Volume',
                    showlegend=False,
                    opacity=0.3
                ),
                row=2, col=1
            )
            
            # Draw Fibonacci setups (adjusted indices for display range)
            for setup in valid_setups:
                self._draw_setup_on_chart(fig, setup, start_idx, df_display)
            
            # Draw entry signal if present
            if entry_signal:
                self._draw_entry_on_chart(fig, entry_signal)
            
            # Calculate price range for better visibility
            price_min = df_display['low'].min()
            price_max = df_display['high'].max()
            price_range = price_max - price_min
            padding = price_range * 0.1  # 10% padding
            
            # Update layout with optimized settings
            fig.update_layout(
                title={
                    'text': f"<b>{self.symbol} - M15 Fibonacci Setup</b><br><sub>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</sub>",
                    'x': 0.5,
                    'xanchor': 'center',
                    'font': {'size': 16}
                },
                height=900,
                width=1400,
                template='plotly_dark',
                hovermode='x unified',
                xaxis_rangeslider_visible=False,
                margin=dict(l=80, r=80, t=100, b=80),
                plot_bgcolor='rgba(0, 0, 0, 0.8)',
                paper_bgcolor='rgba(0, 0, 0, 1)',
                font=dict(size=12)
            )
            
            # Set y-axis limits with padding
            fig.update_yaxes(
                title_text="Price",
                range=[price_min - padding, price_max + padding],
                row=1, col=1,
                gridcolor='rgba(128, 128, 128, 0.2)'
            )
            
            fig.update_yaxes(
                title_text="Volume",
                row=2, col=1,
                gridcolor='rgba(128, 128, 128, 0.2)'
            )
            
            fig.update_xaxes(
                title_text="Time",
                row=2, col=1,
                gridcolor='rgba(128, 128, 128, 0.2)'
            )
            
            # Improve readability
            fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='rgba(128, 128, 128, 0.2)')
            fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='rgba(128, 128, 128, 0.2)')
            
            # Save as HTML
            fig.write_html(filepath)
            logger.info(f"✓ Optimized chart saved to: {filepath}")
            logger.info(f"  Displaying {len(df_display)} candles from {df_display['time'].iloc[0]} to {df_display['time'].iloc[-1]}")
            
            return filepath
        
        except Exception as e:
            logger.error(f"Error creating chart: {e}", exc_info=True)
            return None
    
    def _draw_setup_on_chart(self, fig, setup, start_idx, df_display):
        """Draw a Fibonacci setup on the chart (adjusted for display range)"""
        try:
            setup_type = setup['type']
            swing_high = setup['swing_high']
            swing_low = setup['swing_low']
            fib_levels = setup['fib_levels']
            
            # Draw swing high
            fig.add_hline(
                y=swing_high['price'],
                line_dash="dash",
                line_color="red",
                line_width=2,
                annotation_text=f"<b>SWING HIGH</b><br>{swing_high['price']:.5f}",
                annotation_position="right",
                annotation_bgcolor="rgba(255,0,0,0.6)",
                annotation_font_color="white",
                annotation_font_size=11,
                row=1, col=1
            )
            
            # Draw swing low
            fig.add_hline(
                y=swing_low['price'],
                line_dash="dash",
                line_color="blue",
                line_width=2,
                annotation_text=f"<b>SWING LOW</b><br>{swing_low['price']:.5f}",
                annotation_position="right",
                annotation_bgcolor="rgba(0,0,255,0.6)",
                annotation_font_color="white",
                annotation_font_size=11,
                row=1, col=1
            )
            
            # Draw Fibonacci levels with custom colors
            fib_colors = {
                0.618: ('#FF6B6B', 'Fib 0.618 - 61.8%'),    # Red
                0.705: ('#FFD93D', 'Fib 0.705 - 70.5%'),    # Yellow
                0.786: ('#6BCF7F', 'Fib 0.786 - 78.6%')     # Green
            }
            
            for level_value, level_price in fib_levels.items():
                color, label = fib_colors.get(level_value, ('#808080', f'Fib {level_value:.3f}'))
                
                fig.add_hline(
                    y=level_price,
                    line_dash="dot",
                    line_color=color,
                    line_width=2,
                    annotation_text=f"<b>{label}</b><br>{level_price:.5f}",
                    annotation_position="right",
                    annotation_bgcolor="rgba(0,0,0,0.5)",
                    annotation_font_color=color,
                    annotation_font_size=10,
                    row=1, col=1
                )
        
        except Exception as e:
            logger.error(f"Error drawing setup: {e}")
    
    def _draw_entry_on_chart(self, fig, entry_signal):
        """Draw entry signal prominently on the chart"""
        try:
            signal_type = entry_signal['type']
            fib_price = entry_signal['fib_price']
            fib_level = entry_signal['fib_level']
            
            # Draw entry line - more prominent
            if signal_type == 'long':
                color = '#00FF00'  # Bright green
                label = f"🟢 BUY SIGNAL @ Fib {fib_level:.3f}"
                bgcolor = "rgba(0,255,0,0.7)"
            else:
                color = '#FF3333'  # Bright red
                label = f"🔴 SELL SIGNAL @ Fib {fib_level:.3f}"
                bgcolor = "rgba(255,50,50,0.7)"
            
            fig.add_hline(
                y=fib_price,
                line_dash="solid",
                line_color=color,
                line_width=4,
                annotation_text=f"<b>{label}</b><br>Price: {fib_price:.5f}",
                annotation_position="right",
                annotation_bgcolor=bgcolor,
                annotation_font_color="white",
                annotation_font_size=12,
                annotation_font=dict(family="Arial Black"),
                row=1, col=1
            )
        
        except Exception as e:
            logger.error(f"Error drawing entry signal: {e}")


def export_fibonacci_chart(symbol, df, valid_setups, entry_signal=None, output_dir="fib_charts"):
    """
    Convenience function to create and save an optimized Fibonacci chart
    
    Args:
        symbol: Trading symbol
        df: Price dataframe with columns: time, open, high, low, close, volume/tick_volume
        valid_setups: List of Fibonacci setups
        entry_signal: Entry signal (optional)
        output_dir: Directory to save charts (default: fib_charts)
    
    Returns:
        Path to saved chart file, or None if failed
        
    Features:
    - Shows only relevant candles (swing points + context)
    - Optimized for M15 and other timeframes
    - Clearly labeled swing points and Fibonacci levels
    - Prominent entry signal display
    - Better readability with proper spacing and colors
    """
    if not PLOTLY_AVAILABLE:
        logger.warning("Plotly not installed. Cannot export charts.")
        logger.info("Install with: pip install plotly kaleido")
        return None
    
    try:
        visualizer = FibonacciVisualizer(symbol, output_dir=output_dir)
        return visualizer.create_chart(df, valid_setups, entry_signal)
    
    except Exception as e:
        logger.error(f"Error exporting Fibonacci chart: {e}", exc_info=True)
        return None