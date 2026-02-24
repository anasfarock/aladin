import torch
import pandas as pd
import numpy as np
import logging
from config import CONFIG

logger = logging.getLogger(__name__)

def evaluate_exits_gpu(highs, lows, closes, p_entry_idx, p_entry_prices, p_sides, p_tps, p_sls, p_units):
    """
    Evaluates all potential trade exits on the GPU simultaneously.
    
    Args:
        highs, lows, closes: 1D PyTorch Tensors of price data.
        p_entry_idx: list of indices where entries occur
        p_entry_prices: tensor of entry prices
        p_sides: tensor of sides (1 for long, -1 for short)
        p_tps, p_sls: tensors of initial TP and SL levels
        p_units: tensor of trade sizes
    
    Returns:
        List of dictionaries with calculated exits and P&Ls.
    """
    num_trades = len(p_entry_idx)
    num_bars = len(closes)
    
    if num_trades == 0:
        return []
    
    device = highs.device
    trailing_step = CONFIG.get('trailing_step', 0.001)
    use_trailing = CONFIG.get('trailing_stop', True)
    
    results = []
    
    # We iterate over trades. Wait, we can parallelize trades too if we use a 2D mask,
    # but since trades have different starting indices and lengths, a loop over trades
    # running 1D tensor ops is blazing fast directly on PyTorch GPU.
    for i in range(num_trades):
        e_idx = p_entry_idx[i]
        
        # We only care about prices AFTER the entry index
        # We add +1 because entry happens at the 'open' of e_idx,
        # so evaluating exits starts from the high/low of e_idx itself.
        if e_idx >= num_bars:
            e_idx = num_bars - 1
            
        h = highs[e_idx:]
        l = lows[e_idx:]
        c = closes[e_idx:]
        
        steps_remaining = len(c)
        if steps_remaining == 0:
            continue
            
        side = p_sides[i]
        ep = p_entry_prices[i]
        tp = p_tps[i]
        sl = p_sls[i]
        units = p_units[i]
        
        # Create exit masks
        if side == 1: # LONG
            if use_trailing:
                # Calculate running max close
                max_close, _ = torch.cummax(c, dim=0)
                # Trailing SL triggers when MaxClose >= Entry+Step
                # New SL = MaxClose - Step
                trailing_level = max_close - trailing_step
                active_mask = max_close >= (ep + trailing_step)
                
                # Dynamic SL is either the rolling trailing level or the initial SL
                dynamic_sl = torch.where(active_mask, trailing_level, sl)
                
                sl_hit = l <= dynamic_sl
            else:
                sl_hit = l <= sl
                dynamic_sl = torch.full_like(l, sl)
                
            tp_hit = h >= tp
            
        else: # SHORT
            if use_trailing:
                # Calculate running min close
                min_close, _ = torch.cummin(c, dim=0)
                # Trailing SL triggers when MinClose <= Entry-Step
                trailing_level = min_close + trailing_step
                active_mask = min_close <= (ep - trailing_step)
                
                dynamic_sl = torch.where(active_mask, trailing_level, sl)
                
                sl_hit = h >= dynamic_sl
            else:
                sl_hit = h >= sl
                dynamic_sl = torch.full_like(h, sl)
                
            tp_hit = l <= tp
            
        # Combine hits
        exit_mask = sl_hit | tp_hit
        
        # Find first index where exit_mask is True
        if exit_mask.any():
            exit_offset = torch.argmax(exit_mask.int()).item()
            exit_bar_idx = e_idx + exit_offset
            
            # Did it hit SL or TP at this bar?
            is_tp = tp_hit[exit_offset].item()
            is_sl = sl_hit[exit_offset].item()
            
            # Determine precise exit reason and price
            # If both hit in same bar (rare but possible), pessimistic assumption favors SL
            if is_sl:
                exit_price = dynamic_sl[exit_offset].item()
                exit_reason = 'trailing_stop' if (use_trailing and active_mask[exit_offset].item()) else 'stop_loss'
            else:
                exit_price = tp.item()
                exit_reason = 'take_profit'
                
        else:
            # Reached end of data without exit
            exit_bar_idx = num_bars - 1
            exit_price = c[-1].item()
            exit_reason = 'end_of_data'
            
        # Calculate P&L
        if side == 1:
            pl = (exit_price - ep.item()) * units.item()
        else:
            pl = (ep.item() - exit_price) * units.item()
            
        results.append({
            'trade_id': i,
            'entry_idx': e_idx,
            'exit_idx': exit_bar_idx,
            'exit_price': exit_price,
            'pl': pl,
            'exit_reason': exit_reason
        })
        
    return results
