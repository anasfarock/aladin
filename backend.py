"""
FastAPI Backend for MT5 ICT Fibonacci Trading Bot
Serves as middleware between MT5 trading bot and Next.js frontend
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict
import json
import asyncio
from datetime import datetime
from config import CONFIG, validate_config, logger

app = FastAPI(title="MT5 Trading Bot API", version="1.0.0")

# Enable CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ======================== MODELS ========================

class TradeData(BaseModel):
    """Trade information model"""
    trade_id: int
    symbol: str
    pair: str
    type: str  # 'BUY' or 'SELL'
    entry_price: float
    entry_time: str
    exit_price: Optional[float] = None
    exit_time: Optional[str] = None
    pnl: float
    pnl_pct: float
    status: str  # 'OPEN' or 'CLOSED'
    size: float
    stop_loss: float
    take_profit: float


class BotStatus(BaseModel):
    """Bot status model"""
    running: bool
    balance: float
    equity: float
    pnl: float
    pnl_pct: float
    status: str
    trend: str
    active_trades: int
    total_trades: int
    win_rate: float
    timestamp: str


class TrendUpdate(BaseModel):
    """Manual trend update model"""
    manual_trend: str  # 'bullish', 'bearish', 'neutral'


# ======================== BOT STATE ========================

bot_state = {
    "running": False,
    "balance": CONFIG['capital'],
    "equity": CONFIG['capital'],
    "pnl": 0.0,
    "pnl_pct": 0.0,
    "status": "Idle",
    "trend": "neutral",
    "active_trades": 0,
    "total_trades": 0,
    "closed_trades": 0,
    "win_count": 0,
    "trades": [],
    "timestamp": datetime.now().isoformat(),
    "backtest_mode": CONFIG['backtest'],
    "symbol": CONFIG['symbol'],
    "manual_trend_enabled": CONFIG.get('use_manual_trend', False),
    "manual_trend": CONFIG.get('manual_trend', 'neutral'),
}

trade_counter = 0


# ======================== API ROUTES ========================

@app.get("/api/status", response_model=BotStatus)
async def get_status():
    """Get current bot status"""
    try:
        win_rate = (bot_state['win_count'] / bot_state['closed_trades'] * 100) if bot_state['closed_trades'] > 0 else 0
        
        return BotStatus(
            running=bot_state['running'],
            balance=bot_state['balance'],
            equity=bot_state['equity'],
            pnl=bot_state['pnl'],
            pnl_pct=bot_state['pnl_pct'],
            status=bot_state['status'],
            trend=bot_state['trend'],
            active_trades=bot_state['active_trades'],
            total_trades=bot_state['total_trades'],
            win_rate=win_rate,
            timestamp=datetime.now().isoformat()
        )
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/start")
async def start_bot():
    """Start the trading bot"""
    try:
        bot_state['running'] = True
        bot_state['status'] = "Running"
        bot_state['timestamp'] = datetime.now().isoformat()
        logger.info("Bot started via API")
        return {
            "message": "Bot started successfully",
            "status": "Running"
        }
    except Exception as e:
        logger.error(f"Error starting bot: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/stop")
async def stop_bot():
    """Stop the trading bot"""
    try:
        bot_state['running'] = False
        bot_state['status'] = "Stopped"
        bot_state['timestamp'] = datetime.now().isoformat()
        logger.info("Bot stopped via API")
        return {
            "message": "Bot stopped successfully",
            "status": "Stopped"
        }
    except Exception as e:
        logger.error(f"Error stopping bot: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/trades", response_model=List[TradeData])
async def get_trades(limit: int = 50, status: Optional[str] = None):
    """Get trades with optional filtering"""
    try:
        trades = bot_state['trades']
        
        if status:
            trades = [t for t in trades if t.get('status') == status]
        
        # Return most recent trades first
        return sorted(trades, key=lambda x: x.get('entry_time', ''), reverse=True)[:limit]
    except Exception as e:
        logger.error(f"Error getting trades: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/trades/open")
async def get_open_trades():
    """Get only open trades"""
    try:
        open_trades = [t for t in bot_state['trades'] if t.get('status') == 'OPEN']
        return {
            "count": len(open_trades),
            "trades": open_trades
        }
    except Exception as e:
        logger.error(f"Error getting open trades: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/trades/closed")
async def get_closed_trades():
    """Get only closed trades"""
    try:
        closed_trades = [t for t in bot_state['trades'] if t.get('status') == 'CLOSED']
        return {
            "count": len(closed_trades),
            "trades": closed_trades
        }
    except Exception as e:
        logger.error(f"Error getting closed trades: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/trades/update")
async def update_trades(trades_data: Dict):
    """Update trades from bot
    
    Expected format:
    {
        "trades": [
            {
                "trade_id": 1,
                "symbol": "USDCAD",
                "pair": "USD/CAD",
                "type": "BUY",
                "entry_price": 1.3654,
                "entry_time": "2025-10-23T10:30:00",
                "exit_price": null,
                "exit_time": null,
                "pnl": 0,
                "pnl_pct": 0,
                "status": "OPEN",
                "size": 1.0,
                "stop_loss": 1.3634,
                "take_profit": 1.3704
            }
        ]
    }
    """
    try:
        if 'trades' in trades_data:
            bot_state['trades'] = trades_data['trades']
            
            # Update counters
            bot_state['active_trades'] = len([t for t in bot_state['trades'] if t.get('status') == 'OPEN'])
            bot_state['total_trades'] = len(bot_state['trades'])
            bot_state['closed_trades'] = len([t for t in bot_state['trades'] if t.get('status') == 'CLOSED'])
            
            # Update win count
            bot_state['win_count'] = len([t for t in bot_state['trades'] if t.get('status') == 'CLOSED' and t.get('pnl', 0) > 0])
            
        bot_state['timestamp'] = datetime.now().isoformat()
        return {"message": "Trades updated successfully", "count": len(bot_state['trades'])}
    except Exception as e:
        logger.error(f"Error updating trades: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/stats/update")
async def update_stats(stats_data: Dict):
    """Update bot statistics
    
    Expected format:
    {
        "balance": 5100.50,
        "equity": 5150.75,
        "pnl": 150.75,
        "pnl_pct": 3.02,
        "trend": "bullish",
        "status": "Running - Searching for setups"
    }
    """
    try:
        if 'balance' in stats_data:
            bot_state['balance'] = stats_data['balance']
        if 'equity' in stats_data:
            bot_state['equity'] = stats_data['equity']
        if 'pnl' in stats_data:
            bot_state['pnl'] = stats_data['pnl']
        if 'pnl_pct' in stats_data:
            bot_state['pnl_pct'] = stats_data['pnl_pct']
        if 'trend' in stats_data:
            bot_state['trend'] = stats_data['trend']
        if 'status' in stats_data:
            bot_state['status'] = stats_data['status']
        
        bot_state['timestamp'] = datetime.now().isoformat()
        return {"message": "Statistics updated successfully"}
    except Exception as e:
        logger.error(f"Error updating stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/config")
async def get_config():
    """Get current bot configuration"""
    try:
        return {
            "symbol": CONFIG['symbol'],
            "timeframe_entry": CONFIG['timeframe_entry'],
            "trend_timeframes": CONFIG['trend_timeframes'],
            "risk_pct": CONFIG['risk_pct'],
            "capital": CONFIG['capital'],
            "backtest_mode": CONFIG['backtest'],
            "manual_trend_enabled": CONFIG.get('use_manual_trend', False),
            "manual_trend": CONFIG.get('manual_trend', 'neutral'),
            "max_concurrent_trades": CONFIG['max_concurrent_trades'],
            "min_rr_ratio": CONFIG['min_rr_ratio'],
        }
    except Exception as e:
        logger.error(f"Error getting config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/config/trend")
async def update_trend(trend_update: TrendUpdate):
    """Update manual trend setting"""
    try:
        valid_trends = ['bullish', 'bearish', 'neutral']
        if trend_update.manual_trend.lower() not in valid_trends:
            raise HTTPException(status_code=400, detail=f"Invalid trend. Must be one of: {', '.join(valid_trends)}")
        
        CONFIG['use_manual_trend'] = True
        CONFIG['manual_trend'] = trend_update.manual_trend.lower()
        bot_state['manual_trend_enabled'] = True
        bot_state['manual_trend'] = trend_update.manual_trend.lower()
        
        logger.info(f"Trend updated to: {trend_update.manual_trend.upper()}")
        return {
            "message": f"Trend updated to {trend_update.manual_trend.upper()}",
            "manual_trend": trend_update.manual_trend
        }
    except Exception as e:
        logger.error(f"Error updating trend: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "bot_running": bot_state['running'],
        "timestamp": datetime.now().isoformat()
    }


@app.get("/api/performance")
async def get_performance():
    """Get performance metrics"""
    try:
        closed_trades = [t for t in bot_state['trades'] if t.get('status') == 'CLOSED']
        
        if len(closed_trades) == 0:
            return {
                "total_trades": 0,
                "closed_trades": 0,
                "open_trades": bot_state['active_trades'],
                "win_count": 0,
                "loss_count": 0,
                "win_rate": 0,
                "avg_pnl": 0,
                "total_pnl": 0,
                "best_trade": 0,
                "worst_trade": 0,
            }
        
        win_trades = [t for t in closed_trades if t.get('pnl', 0) > 0]
        loss_trades = [t for t in closed_trades if t.get('pnl', 0) < 0]
        
        total_pnl = sum(t.get('pnl', 0) for t in closed_trades)
        avg_pnl = total_pnl / len(closed_trades) if len(closed_trades) > 0 else 0
        
        pnls = [t.get('pnl', 0) for t in closed_trades]
        best_trade = max(pnls) if pnls else 0
        worst_trade = min(pnls) if pnls else 0
        
        return {
            "total_trades": bot_state['total_trades'],
            "closed_trades": len(closed_trades),
            "open_trades": bot_state['active_trades'],
            "win_count": len(win_trades),
            "loss_count": len(loss_trades),
            "win_rate": (len(win_trades) / len(closed_trades) * 100) if len(closed_trades) > 0 else 0,
            "avg_pnl": round(avg_pnl, 2),
            "total_pnl": round(total_pnl, 2),
            "best_trade": round(best_trade, 2),
            "worst_trade": round(worst_trade, 2),
        }
    except Exception as e:
        logger.error(f"Error getting performance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ======================== ROOT ========================

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "MT5 Trading Bot API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "endpoints": {
            "status": "/api/status",
            "trades": "/api/trades",
            "config": "/api/config",
            "health": "/api/health",
            "performance": "/api/performance"
        }
    }


# ======================== MAIN ========================

if __name__ == "__main__":
    import uvicorn
    
    try:
        validate_config()
    except Exception as e:
        logger.error(f"Configuration error: {e}")
        exit(1)
    
    logger.info("="*70)
    logger.info("Starting MT5 Trading Bot API Server")
    logger.info("="*70)
    logger.info(f"Symbol: {CONFIG['symbol']}")
    logger.info(f"Timeframe: {CONFIG['timeframe_entry']}")
    logger.info(f"Manual Trend: {CONFIG.get('manual_trend', 'N/A')}")
    logger.info("="*70 + "\n")
    
    uvicorn.run(app, host="0.0.0.0", port=8000)