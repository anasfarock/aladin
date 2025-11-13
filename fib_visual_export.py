"""
Fibonacci Visualization Exporter
Creates HTML/PNG charts of Fibonacci levels without requiring MT5 drawing API
Works with any MetaTrader5 version
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
    """Create Fibonacci visualizations as HTML/PNG files"""
    
    def __init__(self, symbol, output_dir="fib_charts"):
        self.symbol = symbol
        self.output_dir = output_dir
        
        # Create output directory
        os.makedirs(self.output_dir, exist_ok=True)
    
    def create_chart(self, df, valid_setups, entry_signal=None, filename=None):
        """
        Create a Fibonacci chart visualization
        
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
            # Create figure with secondary y-axis for volume
            fig = make_subplots(
                rows=2, cols=1,
                shared_xaxes=True,
                vertical_spacing=0.1,
                row_heights=[0.7, 0.3]
            )
            
            # Add candlesticks
            fig.add_trace(
                go.Candlestick(
                    x=df['time'],
                    open=df['open'],
                    high=df['high'],
                    low=df['low'],
                    close=df['close'],
                    name='Price',
                    yaxis='y1'
                ),
                row=1, col=1
            )
            
            # Add volume bars
            if 'tick_volume' in df.columns:
                volume_data = df['tick_volume']
            elif 'volume' in df.columns:
                volume_data = df['volume']
            else:
                volume_data = [0] * len(df)
            
            colors = ['red' if df['close'].iloc[i] < df['open'].iloc[i] else 'green' 
                     for i in range(len(df))]
            fig.add_trace(
                go.Bar(
                    x=df['time'],
                    y=volume_data,
                    marker_color=colors,
                    name='Volume',
                    showlegend=False,
                    yaxis='y2'
                ),
                row=2, col=1
            )
            
            # Draw Fibonacci setups
            for setup_idx, setup in enumerate(valid_setups):
                self._draw_setup_on_chart(fig, setup, setup_idx)
            
            # Draw entry signal if present
            if entry_signal:
                self._draw_entry_on_chart(fig, entry_signal)
            
            # Update layout
            fig.update_layout(
                title=f"{self.symbol} - Fibonacci Analysis ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})",
                height=800,
                template='plotly_dark',
                hovermode='x unified',
                xaxis_rangeslider_visible=False
            )
            
            fig.update_yaxes(title_text="Price (USD)", row=1, col=1)
            fig.update_yaxes(title_text="Volume", row=2, col=1)
            fig.update_xaxes(title_text="Time", row=2, col=1)
            
            # Save as HTML
            fig.write_html(filepath)
            logger.info(f"✓ Chart saved to: {filepath}")
            
            return filepath
        
        except Exception as e:
            logger.error(f"Error creating chart: {e}")
            return None
    
    def _draw_setup_on_chart(self, fig, setup, setup_idx):
        """Draw a Fibonacci setup on the chart"""
        try:
            setup_type = setup['type']
            swing_high = setup['swing_high']
            swing_low = setup['swing_low']
            fib_levels = setup['fib_levels']
            
            # Color for this setup
            setup_color = 'blue' if setup_type == 'bullish_retracement' else 'red'
            
            # Draw swing high
            fig.add_hline(
                y=swing_high['price'],
                line_dash="dash",
                line_color="red",
                line_width=2,
                annotation_text=f"SH: {swing_high['price']:.5f}",
                annotation_position="right",
                annotation_bgcolor="rgba(255,0,0,0.5)",
                row=1, col=1
            )
            
            # Draw swing low
            fig.add_hline(
                y=swing_low['price'],
                line_dash="dash",
                line_color="blue",
                line_width=2,
                annotation_text=f"SL: {swing_low['price']:.5f}",
                annotation_position="right",
                annotation_bgcolor="rgba(0,0,255,0.5)",
                row=1, col=1
            )
            
            # Draw Fibonacci levels
            fib_colors = {
                0.618: 'orange',
                0.705: 'gold',
                0.786: 'lime'
            }
            
            for level_value, level_price in fib_levels.items():
                color = fib_colors.get(level_value, 'gray')
                
                fig.add_hline(
                    y=level_price,
                    line_dash="dot",
                    line_color=color,
                    line_width=1,
                    annotation_text=f"Fib {level_value:.3f}: {level_price:.5f}",
                    annotation_position="right",
                    annotation_bgcolor=f"rgba(255,255,255,0.3)",
                    row=1, col=1
                )
        
        except Exception as e:
            logger.error(f"Error drawing setup: {e}")
    
    def _draw_entry_on_chart(self, fig, entry_signal):
        """Draw entry signal on the chart"""
        try:
            signal_type = entry_signal['type']
            fib_price = entry_signal['fib_price']
            fib_level = entry_signal['fib_level']
            
            # Draw entry line
            color = 'lime' if signal_type == 'long' else 'red'
            label = f"{'🟢 BUY' if signal_type == 'long' else '🔴 SELL'} @ Fib {fib_level:.3f}"
            
            fig.add_hline(
                y=fib_price,
                line_dash="solid",
                line_color=color,
                line_width=4,
                annotation_text=label,
                annotation_position="right",
                annotation_bgcolor=f"rgba(0,0,0,0.7)",
                annotation_font_color=color,
                row=1, col=1
            )
        
        except Exception as e:
            logger.error(f"Error drawing entry signal: {e}")


def export_fibonacci_chart(symbol, df, valid_setups, entry_signal=None, output_dir="fib_charts"):
    """
    Convenience function to create and save a Fibonacci chart
    
    Args:
        symbol: Trading symbol
        df: Price dataframe with columns: time, open, high, low, close, volume/tick_volume
        valid_setups: List of Fibonacci setups
        entry_signal: Entry signal (optional)
        output_dir: Directory to save charts (default: fib_charts)
    
    Returns:
        Path to saved chart file, or None if failed
        
    Example:
        from fib_visual_export import export_fibonacci_chart
        
        chart_file = export_fibonacci_chart(
            'AUDUSD',
            df_entry,
            valid_setups,
            entry_signal
        )
        if chart_file:
            print(f"Chart saved to: {chart_file}")
    """
    if not PLOTLY_AVAILABLE:
        logger.warning("Plotly not installed. Cannot export charts.")
        logger.info("Install with: pip install plotly kaleido")
        return None
    
    try:
        visualizer = FibonacciVisualizer(symbol, output_dir=output_dir)
        return visualizer.create_chart(df, valid_setups, entry_signal)
    
    except Exception as e:
        logger.error(f"Error exporting Fibonacci chart: {e}")
        return None