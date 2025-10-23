"use client";

import { useState, useEffect } from "react";
import {
  Play,
  Square,
  TrendingUp,
  DollarSign,
  Activity,
  Settings,
  X,
  Save,
} from "lucide-react";

export default function Dashboard() {
  const [status, setStatus] = useState(null);
  const [trades, setTrades] = useState([]);
  const [loading, setLoading] = useState(false);
  const [config, setConfig] = useState(null);
  const [showSettings, setShowSettings] = useState(false);
  const [formData, setFormData] = useState({});
  const [saveMessage, setSaveMessage] = useState("");
  const [performance, setPerformance] = useState(null);

  const API_URL = "http://localhost:8000/api";

  useEffect(() => {
    fetchStatus();
    fetchConfig();
    fetchPerformance();
    const interval = setInterval(() => {
      fetchStatus();
      fetchPerformance();
    }, 2000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (config) {
      setFormData(config);
    }
  }, [config]);

  const fetchStatus = async () => {
    try {
      const res = await fetch(`${API_URL}/status`);
      const data = await res.json();
      setStatus(data);
    } catch (err) {
      console.error("Failed to fetch status:", err);
    }
  };

  const fetchConfig = async () => {
    try {
      const res = await fetch(`${API_URL}/config`);
      const data = await res.json();
      setConfig(data);
    } catch (err) {
      console.error("Failed to fetch config:", err);
    }
  };

  const fetchPerformance = async () => {
    try {
      const res = await fetch(`${API_URL}/performance`);
      const data = await res.json();
      setPerformance(data);
    } catch (err) {
      console.error("Failed to fetch performance:", err);
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

  const handleInputChange = (e) => {
    const { name, value, type, checked } = e.target;
    setFormData({
      ...formData,
      [name]: type === "checkbox" ? checked : value === "" ? null : value,
    });
  };

  const saveConfig = async () => {
    setLoading(true);
    try {
      const updateData = {
        symbol: formData.symbol,
        timeframe_entry: formData.timeframe_entry,
        capital: parseFloat(formData.capital),
        risk_pct: parseFloat(formData.risk_pct),
        backtest: formData.backtest_mode,
        max_concurrent_trades: parseInt(formData.max_concurrent_trades),
        use_manual_trend: formData.manual_trend_enabled,
        manual_trend: formData.manual_trend,
      };

      const res = await fetch(`${API_URL}/config/update`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(updateData),
      });

      if (res.ok) {
        setSaveMessage("✅ Configuration saved successfully!");
        await fetchConfig();
        setTimeout(() => setSaveMessage(""), 3000);
      } else {
        setSaveMessage("❌ Failed to save configuration");
      }
    } catch (err) {
      console.error("Failed to save config:", err);
      setSaveMessage("❌ Error saving configuration");
    }
    setLoading(false);
  };

  if (!status || !config) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-900">
        <div className="text-white">Loading...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-gray-800 to-black p-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex justify-between items-center mb-8">
          <div>
            <h1 className="text-4xl font-bold text-white mb-2">
              MT5 Trading Bot
            </h1>
            <p className="text-gray-400">Automated trading dashboard</p>
          </div>
          <button
            onClick={() => setShowSettings(!showSettings)}
            className="bg-gray-700 hover:bg-gray-600 text-white p-3 rounded-lg transition"
          >
            <Settings className="w-6 h-6" />
          </button>
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

          {/* Trend */}
          <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-400 text-sm">Current Trend</p>
                <p
                  className={`text-2xl font-bold mt-2 capitalize ${
                    status.trend === "bullish"
                      ? "text-green-500"
                      : status.trend === "bearish"
                      ? "text-red-500"
                      : "text-yellow-500"
                  }`}
                >
                  {status.trend}
                </p>
              </div>
              <TrendingUp className="w-8 h-8 text-yellow-500" />
            </div>
          </div>
        </div>

        {/* Performance Cards */}
        {performance && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
            <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
              <p className="text-gray-400 text-sm">Win Rate</p>
              <p className="text-2xl font-bold text-green-500 mt-2">
                {performance.win_rate.toFixed(1)}%
              </p>
              <p className="text-xs text-gray-400 mt-1">
                {performance.win_count}W / {performance.loss_count}L
              </p>
            </div>
            <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
              <p className="text-gray-400 text-sm">Total P&L</p>
              <p
                className={`text-2xl font-bold mt-2 ${
                  performance.total_pnl >= 0 ? "text-green-500" : "text-red-500"
                }`}
              >
                ${performance.total_pnl.toFixed(2)}
              </p>
            </div>
            <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
              <p className="text-gray-400 text-sm">Active Trades</p>
              <p className="text-2xl font-bold text-blue-500 mt-2">
                {performance.open_trades}
              </p>
            </div>
          </div>
        )}

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
            <button
              onClick={fetchTrades}
              className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-6 py-3 rounded-lg font-semibold transition"
            >
              Refresh Trades
            </button>
          </div>
        </div>

        {/* Settings Panel */}
        {showSettings && (
          <div className="fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center p-4 z-50">
            <div className="bg-gray-800 rounded-lg border border-gray-700 max-w-2xl w-full max-h-96 overflow-y-auto">
              <div className="flex justify-between items-center p-6 border-b border-gray-700">
                <h2 className="text-xl font-bold text-white">Bot Settings</h2>
                <button
                  onClick={() => setShowSettings(false)}
                  className="text-gray-400 hover:text-white"
                >
                  <X className="w-6 h-6" />
                </button>
              </div>

              <div className="p-6 space-y-4">
                {/* Trading Mode */}
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-semibold text-white mb-2">
                      Trading Mode
                    </label>
                    <select
                      name="backtest_mode"
                      value={formData.backtest_mode ? "backtest" : "live"}
                      onChange={(e) =>
                        setFormData({
                          ...formData,
                          backtest_mode: e.target.value === "backtest",
                        })
                      }
                      className="w-full bg-gray-700 text-white px-3 py-2 rounded border border-gray-600"
                    >
                      <option value="live">Live Trading</option>
                      <option value="backtest">Backtest</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-sm font-semibold text-white mb-2">
                      Symbol
                    </label>
                    <input
                      type="text"
                      name="symbol"
                      value={formData.symbol || ""}
                      onChange={handleInputChange}
                      placeholder="e.g., EURUSD"
                      className="w-full bg-gray-700 text-white px-3 py-2 rounded border border-gray-600"
                    />
                  </div>
                </div>

                {/* Timeframe & Capital */}
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-semibold text-white mb-2">
                      Timeframe
                    </label>
                    <select
                      name="timeframe_entry"
                      value={formData.timeframe_entry || ""}
                      onChange={handleInputChange}
                      className="w-full bg-gray-700 text-white px-3 py-2 rounded border border-gray-600"
                    >
                      <option value="M15">M15</option>
                      <option value="M30">M30</option>
                      <option value="H1">H1</option>
                      <option value="H4">H4</option>
                      <option value="D1">D1</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-sm font-semibold text-white mb-2">
                      Capital ($)
                    </label>
                    <input
                      type="number"
                      name="capital"
                      value={formData.capital || ""}
                      onChange={handleInputChange}
                      placeholder="5000"
                      className="w-full bg-gray-700 text-white px-3 py-2 rounded border border-gray-600"
                    />
                  </div>
                </div>

                {/* Risk & Max Trades */}
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-semibold text-white mb-2">
                      Risk per Trade (%)
                    </label>
                    <input
                      type="number"
                      name="risk_pct"
                      value={formData.risk_pct || ""}
                      onChange={handleInputChange}
                      step="0.1"
                      placeholder="0.5"
                      className="w-full bg-gray-700 text-white px-3 py-2 rounded border border-gray-600"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-semibold text-white mb-2">
                      Max Concurrent Trades
                    </label>
                    <input
                      type="number"
                      name="max_concurrent_trades"
                      value={formData.max_concurrent_trades || ""}
                      onChange={handleInputChange}
                      placeholder="10"
                      className="w-full bg-gray-700 text-white px-3 py-2 rounded border border-gray-600"
                    />
                  </div>
                </div>

                {/* Trend Settings */}
                <div className="border-t border-gray-700 pt-4">
                  <label className="flex items-center gap-3 cursor-pointer mb-4">
                    <input
                      type="checkbox"
                      name="manual_trend_enabled"
                      checked={formData.manual_trend_enabled || false}
                      onChange={handleInputChange}
                      className="w-4 h-4"
                    />
                    <span className="text-sm font-semibold text-white">
                      Use Manual Trend Override
                    </span>
                  </label>

                  {formData.manual_trend_enabled && (
                    <div>
                      <label className="block text-sm font-semibold text-white mb-2">
                        Trend Direction
                      </label>
                      <select
                        name="manual_trend"
                        value={formData.manual_trend || ""}
                        onChange={handleInputChange}
                        className="w-full bg-gray-700 text-white px-3 py-2 rounded border border-gray-600"
                      >
                        <option value="bullish">Bullish</option>
                        <option value="bearish">Bearish</option>
                        <option value="neutral">Neutral</option>
                      </select>
                    </div>
                  )}
                </div>

                {/* Save Message */}
                {saveMessage && (
                  <div
                    className={`p-3 rounded ${
                      saveMessage.includes("✅")
                        ? "bg-green-900 text-green-200"
                        : "bg-red-900 text-red-200"
                    }`}
                  >
                    {saveMessage}
                  </div>
                )}

                {/* Save Button */}
                <div className="flex gap-2">
                  <button
                    onClick={saveConfig}
                    disabled={loading}
                    className="flex items-center gap-2 flex-1 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 text-white px-6 py-3 rounded-lg font-semibold transition"
                  >
                    <Save className="w-5 h-5" />
                    Save Configuration
                  </button>
                  <button
                    onClick={() => setShowSettings(false)}
                    className="flex-1 bg-gray-700 hover:bg-gray-600 text-white px-6 py-3 rounded-lg font-semibold transition"
                  >
                    Close
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Trades Table */}
        <div className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
          <div className="p-6 border-b border-gray-700">
            <h2 className="text-xl font-bold text-white">Recent Trades</h2>
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
                  <th className="px-6 py-3 text-left text-gray-400 text-sm font-semibold">
                    Status
                  </th>
                </tr>
              </thead>
              <tbody>
                {trades.length === 0 ? (
                  <tr>
                    <td
                      colSpan="6"
                      className="px-6 py-8 text-center text-gray-400"
                    >
                      No trades yet
                    </td>
                  </tr>
                ) : (
                  trades.slice(0, 20).map((trade, idx) => (
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
                      <td className="px-6 py-4 text-white">
                        {trade.entry_price?.toFixed(5)}
                      </td>
                      <td className="px-6 py-4 text-white">
                        {trade.exit_price?.toFixed(5) || "-"}
                      </td>
                      <td
                        className={`px-6 py-4 font-semibold ${
                          trade.pnl >= 0 ? "text-green-400" : "text-red-400"
                        }`}
                      >
                        ${trade.pnl?.toFixed(2)}
                      </td>
                      <td className="px-6 py-4">
                        <span
                          className={`px-3 py-1 rounded text-xs font-semibold ${
                            trade.status === "OPEN"
                              ? "bg-blue-900 text-blue-200"
                              : "bg-gray-700 text-gray-200"
                          }`}
                        >
                          {trade.status}
                        </span>
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
