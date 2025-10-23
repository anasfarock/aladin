import { useState, useEffect } from "react";
import { Play, Square, TrendingUp, DollarSign, Activity } from "lucide-react";

export default function TradingBotDashboard() {
  const [status, setStatus] = useState(null);
  const [trades, setTrades] = useState([]);
  const [loading, setLoading] = useState(false);

  const API_URL = "http://localhost:8000/api";

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 2000);
    return () => clearInterval(interval);
  }, []);

  const fetchStatus = async () => {
    try {
      const res = await fetch(`${API_URL}/status`);
      const data = await res.json();
      setStatus(data);
    } catch (err) {
      console.error("Failed to fetch status:", err);
    }
  };

  const fetchTrades = async () => {
    try {
      const res = await fetch(`${API_URL}/trades`);
      const data = await res.json();
      setTrades(data);
    } catch (err) {
      console.error("Failed to fetch trades:", err);
    }
  };

  const startBot = async () => {
    setLoading(true);
    try {
      await fetch(`${API_URL}/start`, { method: "POST" });
      await fetchStatus();
      await fetchTrades();
    } catch (err) {
      console.error("Failed to start bot:", err);
    }
    setLoading(false);
  };

  const stopBot = async () => {
    setLoading(true);
    try {
      await fetch(`${API_URL}/stop`, { method: "POST" });
      await fetchStatus();
    } catch (err) {
      console.error("Failed to stop bot:", err);
    }
    setLoading(false);
  };

  if (!status) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-900">
        <div className="text-white">Loading...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-gray-800 to-black p-8">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-4xl font-bold text-white mb-2">
            MT5 Trading Bot
          </h1>
          <p className="text-gray-400">Automated trading dashboard</p>
        </div>

        {/* Status Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          {/* Bot Status */}
          <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-400 text-sm">Bot Status</p>
                <p className="text-2xl font-bold text-white mt-2">
                  {status.status}
                </p>
              </div>
              <Activity
                className={`w-8 h-8 ${
                  status.running ? "text-green-500" : "text-red-500"
                }`}
              />
            </div>
          </div>

          {/* Balance */}
          <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-400 text-sm">Balance</p>
                <p className="text-2xl font-bold text-white mt-2">
                  ${status.balance.toFixed(2)}
                </p>
              </div>
              <DollarSign className="w-8 h-8 text-blue-500" />
            </div>
          </div>

          {/* Equity */}
          <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-400 text-sm">Equity</p>
                <p className="text-2xl font-bold text-white mt-2">
                  ${status.equity.toFixed(2)}
                </p>
              </div>
              <TrendingUp className="w-8 h-8 text-green-500" />
            </div>
          </div>

          {/* Profit/Loss */}
          <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-400 text-sm">P&L</p>
                <p
                  className={`text-2xl font-bold mt-2 ${
                    status.equity - status.balance >= 0
                      ? "text-green-500"
                      : "text-red-500"
                  }`}
                >
                  ${(status.equity - status.balance).toFixed(2)}
                </p>
              </div>
              <TrendingUp
                className={`w-8 h-8 ${
                  status.equity - status.balance >= 0
                    ? "text-green-500"
                    : "text-red-500"
                }`}
              />
            </div>
          </div>
        </div>

        {/* Controls */}
        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700 mb-8">
          <div className="flex gap-4">
            <button
              onClick={startBot}
              disabled={status.running || loading}
              className="flex items-center gap-2 bg-green-600 hover:bg-green-700 disabled:bg-gray-600 text-white px-6 py-3 rounded-lg font-semibold transition"
            >
              <Play className="w-5 h-5" />
              Start Bot
            </button>
            <button
              onClick={stopBot}
              disabled={!status.running || loading}
              className="flex items-center gap-2 bg-red-600 hover:bg-red-700 disabled:bg-gray-600 text-white px-6 py-3 rounded-lg font-semibold transition"
            >
              <Square className="w-5 h-5" />
              Stop Bot
            </button>
          </div>
        </div>

        {/* Trades Table */}
        <div className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
          <div className="p-6 border-b border-gray-700">
            <div className="flex justify-between items-center">
              <h2 className="text-xl font-bold text-white">Recent Trades</h2>
              <button
                onClick={fetchTrades}
                className="text-sm bg-gray-700 hover:bg-gray-600 text-white px-4 py-2 rounded transition"
              >
                Refresh
              </button>
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-900">
                <tr>
                  <th className="px-6 py-3 text-left text-gray-400 text-sm font-semibold">
                    Pair
                  </th>
                  <th className="px-6 py-3 text-left text-gray-400 text-sm font-semibold">
                    Type
                  </th>
                  <th className="px-6 py-3 text-left text-gray-400 text-sm font-semibold">
                    Entry
                  </th>
                  <th className="px-6 py-3 text-left text-gray-400 text-sm font-semibold">
                    Exit
                  </th>
                  <th className="px-6 py-3 text-left text-gray-400 text-sm font-semibold">
                    P&L
                  </th>
                </tr>
              </thead>
              <tbody>
                {trades.length === 0 ? (
                  <tr>
                    <td
                      colSpan="5"
                      className="px-6 py-8 text-center text-gray-400"
                    >
                      No trades yet
                    </td>
                  </tr>
                ) : (
                  trades.map((trade, idx) => (
                    <tr
                      key={idx}
                      className="border-t border-gray-700 hover:bg-gray-700/50"
                    >
                      <td className="px-6 py-4 text-white">{trade.pair}</td>
                      <td className="px-6 py-4">
                        <span
                          className={`px-3 py-1 rounded text-sm font-semibold ${
                            trade.type === "BUY"
                              ? "bg-green-900 text-green-200"
                              : "bg-red-900 text-red-200"
                          }`}
                        >
                          {trade.type}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-white">{trade.entry}</td>
                      <td className="px-6 py-4 text-white">
                        {trade.exit || "-"}
                      </td>
                      <td
                        className={`px-6 py-4 font-semibold ${
                          trade.pnl >= 0 ? "text-green-400" : "text-red-400"
                        }`}
                      >
                        ${trade.pnl?.toFixed(2) || "0.00"}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
