from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import json

app = FastAPI()

# Allow requests from your Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store bot state
bot_state = {
    "running": False,
    "balance": 10000,
    "equity": 10000,
    "trades": [],
    "status": "Idle"
}

@app.get("/api/status")
async def get_status():
    return bot_state

@app.post("/api/start")
async def start_bot():
    bot_state["running"] = True
    bot_state["status"] = "Running"
    return {"message": "Bot started"}

@app.post("/api/stop")
async def stop_bot():
    bot_state["running"] = False
    bot_state["status"] = "Stopped"
    return {"message": "Bot stopped"}

@app.get("/api/trades")
async def get_trades():
    return bot_state["trades"]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)