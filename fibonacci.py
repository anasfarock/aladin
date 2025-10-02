"""
ICT Fibonacci Strategy Module - FIXED VERSION
Handles swing point identification, Fibonacci calculations, and setup detection
with proper index handling for sliced dataframes
"""

import logging
from config import CONFIG

logger = logging.getLogger(__name__)

# --------------------------- ICT FIBONACCI ----------------------------

def identify_swing_points(df, lookback=10):
    """
    Identify swing highs and lows
    
    Returns swing points with indices RELATIVE to the input dataframe
    """
    if len(df) < lookback * 2 + 1:
        return []
    
    swing_points = []
    
    for i in range(lookback, len(df) - lookback):
        current_high = df.iloc[i]['high']
        current_low = df.iloc[i]['low']
        
        is_swing_high = True
        for j in range(i - lookback, i + lookback + 1):
            if j != i and df.iloc[j]['high'] > current_high:
                is_swing_high = False
                break
        
        if is_swing_high:
            swing_points.append({
                'index': i,  # Index relative to input df
                'time': df.iloc[i]['time'],
                'price': current_high,
                'type': 'high'
            })
        
        is_swing_low = True
        for j in range(i - lookback, i + lookback + 1):
            if j != i and df.iloc[j]['low'] < current_low:
                is_swing_low = False
                break
        
        if is_swing_low:
            swing_points.append({
                'index': i,  # Index relative to input df
                'time': df.iloc[i]['time'],
                'price': current_low,
                'type': 'low'
            })
    
    return swing_points

def calculate_fibonacci_levels(high_price, low_price, direction='bullish'):
    """Calculate Fibonacci retracement levels"""
    price_range = high_price - low_price
    
    if abs(price_range) < CONFIG['min_swing_size']:
        return None
    
    fib_levels = {}
    
    if direction == 'bullish':
        # For bullish: retracing DOWN from high to low
        # Fib 0.0 = low, Fib 1.0 = high
        for level in CONFIG['fib_levels']:
            fib_levels[level] = high_price - (price_range * level)
    else:
        # For bearish: retracing UP from low to high
        # Fib 0.0 = high, Fib 1.0 = low
        for level in CONFIG['fib_levels']:
            fib_levels[level] = low_price + (price_range * level)
    
    return fib_levels

def validate_fibonacci_setup(point1, point2, setup_type):
    """
    Validate Fibonacci setup based on price relationships
    
    Standard Fibonacci Logic:
    - Bullish: Fib 0.0 (swing low) < Fib 1.0 (swing high)
    - Bearish: Fib 0.0 (swing high) > Fib 1.0 (swing low)
    
    Returns:
        tuple: (is_valid, fib_0_price, fib_1_price)
    """
    if setup_type == 'bullish_retracement':
        # Point1 = swing low, Point2 = swing high
        fib_0_price = point1['price']  # Swing low
        fib_1_price = point2['price']  # Swing high
        
        # Valid if swing low < swing high
        is_valid = fib_0_price < fib_1_price
        
    elif setup_type == 'bearish_retracement':
        # Point1 = swing high, Point2 = swing low
        fib_0_price = point1['price']  # Swing high
        fib_1_price = point2['price']  # Swing low
        
        # Valid if swing high > swing low
        is_valid = fib_0_price > fib_1_price
    
    else:
        return False, 0, 0
    
    return is_valid, fib_0_price, fib_1_price

def find_fibonacci_setups(df, swing_points, current_bar_index=None):
    """
    Find valid Fibonacci setups with proper validation
    
    Args:
        df: Price dataframe
        swing_points: List of swing points (indices relative to df)
        current_bar_index: Index of current bar in df (default: last bar)
    
    Returns:
        List of valid Fibonacci setups
    """
    if len(swing_points) < 2:
        return []
    
    fib_setups = []
    
    # Use last bar if current_bar_index not specified
    if current_bar_index is None:
        current_bar_index = len(df) - 1
    
    swing_points = sorted(swing_points, key=lambda x: x['index'])
    
    for i in range(len(swing_points) - 1):
        for j in range(i + 1, len(swing_points)):
            point1 = swing_points[i]
            point2 = swing_points[j]
            
            # FIXED: Calculate age using indices relative to same dataframe
            age = current_bar_index - point2['index']
            
            if age > CONFIG['max_fib_age']:
                continue
            
            if point1['type'] == 'low' and point2['type'] == 'high':
                # Potential bullish retracement
                setup_type = 'bullish_retracement'
                is_valid, fib_0_price, fib_1_price = validate_fibonacci_setup(
                    point1, point2, setup_type
                )
                
                if not is_valid:
                    continue
                
                high_price = point2['price']
                low_price = point1['price']
                fib_levels = calculate_fibonacci_levels(high_price, low_price, 'bullish')
                
                if fib_levels:
                    fib_setups.append({
                        'type': setup_type,
                        'swing_low': point1,
                        'swing_high': point2,
                        'fib_levels': fib_levels,
                        'fib_0_price': fib_0_price,
                        'fib_1_price': fib_1_price,
                        'age': age,
                        'valid': True,
                        'tested_levels': set()
                    })
            
            elif point1['type'] == 'high' and point2['type'] == 'low':
                # Potential bearish retracement
                setup_type = 'bearish_retracement'
                is_valid, fib_0_price, fib_1_price = validate_fibonacci_setup(
                    point1, point2, setup_type
                )
                
                if not is_valid:
                    continue
                
                high_price = point1['price']
                low_price = point2['price']
                fib_levels = calculate_fibonacci_levels(high_price, low_price, 'bearish')
                
                if fib_levels:
                    fib_setups.append({
                        'type': setup_type,
                        'swing_high': point1,
                        'swing_low': point2,
                        'fib_levels': fib_levels,
                        'fib_0_price': fib_0_price,
                        'fib_1_price': fib_1_price,
                        'age': age,
                        'valid': True,
                        'tested_levels': set()
                    })
    
    return fib_setups

def check_fibonacci_reaction(df, fib_setup, current_index):
    """
    Check if price is reacting at Fibonacci levels
    
    Args:
        df: Price dataframe
        fib_setup: Fibonacci setup dictionary
        current_index: Index of current bar in df
    """
    if current_index < CONFIG['fib_confirmation_bars']:
        return None
    
    recent_bars = df.iloc[max(0, current_index - CONFIG['fib_confirmation_bars']):current_index + 1]
    current_bar = df.iloc[current_index]
    
    fib_levels = fib_setup['fib_levels']
    setup_type = fib_setup['type']
    
    for level_value, fib_price in fib_levels.items():
        if level_value in fib_setup['tested_levels']:
            continue
        
        price_touched = False
        for _, bar in recent_bars.iterrows():
            if abs(bar['low'] - fib_price) <= CONFIG['fib_tolerance'] or \
               abs(bar['high'] - fib_price) <= CONFIG['fib_tolerance'] or \
               (bar['low'] <= fib_price <= bar['high']):
                price_touched = True
                break
        
        if not price_touched:
            continue
        
        fib_setup['tested_levels'].add(level_value)
        
        if setup_type == 'bullish_retracement':
            if (current_bar['close'] > fib_price and 
                any(bar['low'] <= fib_price + CONFIG['fib_tolerance'] for _, bar in recent_bars.iterrows())):
                
                return {
                    'type': 'long',
                    'fib_level': level_value,
                    'fib_price': fib_price,
                    'entry_price': current_bar['close'],
                    'setup': fib_setup
                }
        
        elif setup_type == 'bearish_retracement':
            if (current_bar['close'] < fib_price and 
                any(bar['high'] >= fib_price - CONFIG['fib_tolerance'] for _, bar in recent_bars.iterrows())):
                
                return {
                    'type': 'short',
                    'fib_level': level_value,
                    'fib_price': fib_price,
                    'entry_price': current_bar['close'],
                    'setup': fib_setup
                }
    
    return None

def check_fibonacci_entry(fib_setups, df, current_index, trend):
    """
    Check for Fibonacci entry signals aligned with trend
    
    Args:
        fib_setups: List of Fibonacci setups
        df: Price dataframe
        current_index: Index of current bar in df
        trend: Current market trend ('bullish', 'bearish', or 'neutral')
    """
    if not fib_setups:
        return None
    
    for setup in fib_setups:
        if not setup['valid']:
            continue
        
        fib_reaction = check_fibonacci_reaction(df, setup, current_index)
        
        if fib_reaction is None:
            continue
        
        signal_type = fib_reaction['type']
        
        # FIXED: Proper trend alignment check
        if trend == 'bullish' and signal_type != 'long':
            continue
        elif trend == 'bearish' and signal_type != 'short':
            continue
        elif trend == 'neutral':
            # In neutral trend, we could allow both or be more selective
            # For now, let's be conservative and skip neutral trends
            continue
        
        return fib_reaction
    
    return None

class FibonacciTracker:
    """Track Fibonacci setups in live trading"""
    
    def __init__(self):
        self.fib_setups = []
        self.last_analysis_time = None
    
    def update_fibonacci_setups(self, df):
        """Update Fibonacci setups"""
        if len(df) < CONFIG['fib_lookback'] * 2:
            return
        
        current_time = df.iloc[-1]['time']
        if (self.last_analysis_time is None or 
            (current_time - self.last_analysis_time).total_seconds() > 300):
            
            recent_df = df.tail(CONFIG['fib_lookback'] * 3).copy()
            recent_df = recent_df.reset_index(drop=True)  # Reset indices for clean calculation
            
            swing_points = identify_swing_points(recent_df, lookback=8)
            
            # Pass current bar index (last bar of recent_df)
            new_fib_setups = find_fibonacci_setups(
                recent_df, 
                swing_points,
                current_bar_index=len(recent_df) - 1
            )
            
            self.fib_setups = new_fib_setups
            self.last_analysis_time = current_time
            
            # Log validation info
            logger.debug(f"Found {len(new_fib_setups)} valid Fibonacci setups")
            for setup in new_fib_setups:
                logger.debug(
                    f"  {setup['type']}: "
                    f"Fib 0.0={setup['fib_0_price']:.5f}, "
                    f"Fib 1.0={setup['fib_1_price']:.5f}, "
                    f"Age={setup['age']} bars"
                )
    
    def get_valid_setups(self):
        """Get valid Fibonacci setups"""
        return [setup for setup in self.fib_setups if setup['valid']]