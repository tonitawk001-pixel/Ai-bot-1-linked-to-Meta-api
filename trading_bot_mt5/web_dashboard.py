"""
V22 Bot Web Dashboard
=====================
Flask web interface to start, stop, restart and monitor the bot.
Run: python web_dashboard.py
Then open: http://localhost:5000
"""

import os
import sys
import json
import subprocess
import signal
import time
from datetime import datetime, timezone
from flask import Flask, render_template, jsonify

app = Flask(__name__)

BOT_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main_mt5.py")
BOT_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot_output.log")
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot_state.json")

# Track bot process
bot_process = None
bot_pid = None

# Try to import MT5 for live balance
try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except:
    MT5_AVAILABLE = False


def get_bot_status():
    """Get current bot process status."""
    global bot_pid
    if bot_pid is None:
        return {"running": False, "pid": None}
    
    # Check if process is still alive
    try:
        os.kill(bot_pid, 0)  # signal 0 = check existence
        return {"running": True, "pid": bot_pid}
    except:
        bot_pid = None
        return {"running": False, "pid": None}


def get_mt5_info():
    """Get MT5 account info if available."""
    if not MT5_AVAILABLE:
        return None
    
    if not mt5.initialize():
        return None
    
    info = mt5.account_info()
    if info is None:
        mt5.shutdown()
        return None
    
    result = {
        "login": info.login,
        "server": info.server,
        "balance": info.balance,
        "equity": info.equity,
        "margin": info.margin,
        "free_margin": info.margin_free,
        "leverage": info.leverage,
        "currency": info.currency,
    }
    mt5.shutdown()
    return result


def get_state():
    """Get bot state from state file."""
    if not os.path.exists(STATE_FILE):
        return {"positions": 0, "trades": 0}
    try:
        with open(STATE_FILE) as f:
            state = json.load(f)
        return {
            "positions": len(state.get("positions", [])),
            "trades": len(state.get("trades_log", [])),
            "daily_pnl": state.get("daily_pnl", 0),
            "consecutive_losses": state.get("consecutive_losses", 0),
        }
    except:
        return {"positions": 0, "trades": 0}


def get_recent_logs(lines=20):
    """Get last N lines of bot log."""
    if not os.path.exists(BOT_LOG):
        return ["No log file yet"]
    try:
        with open(BOT_LOG) as f:
            all_lines = f.readlines()
        return [l.strip() for l in all_lines[-lines:]]
    except:
        return ["Could not read log"]


@app.route("/")
def index():
    """Main dashboard page."""
    status = get_bot_status()
    mt5_info = get_mt5_info()
    state = get_state()
    logs = get_recent_logs()
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>V22 Bot Dashboard</title>
        <meta http-equiv="refresh" content="10">
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{ font-family: 'Segoe UI', Tahoma, sans-serif; background: #1a1a2e; color: #eee; padding: 20px; }}
            h1 {{ color: #00d4aa; margin-bottom: 10px; }}
            h2 {{ color: #a0a0c0; font-size: 16px; margin-bottom: 20px; }}
            .card {{ background: #16213e; border-radius: 10px; padding: 20px; margin-bottom: 15px; }}
            .card h3 {{ color: #00d4aa; margin-bottom: 10px; }}
            .status {{ display: inline-block; padding: 5px 15px; border-radius: 20px; font-weight: bold; }}
            .running {{ background: #00d4aa; color: #1a1a2e; }}
            .stopped {{ background: #e74c3c; color: white; }}
            .btn {{ padding: 12px 30px; border: none; border-radius: 8px; font-size: 16px; cursor: pointer; margin: 5px; font-weight: bold; }}
            .btn-start {{ background: #00d4aa; color: #1a1a2e; }}
            .btn-stop {{ background: #e74c3c; color: white; }}
            .btn-restart {{ background: #f39c12; color: white; }}
            .btn:hover {{ opacity: 0.85; }}
            .btn:disabled {{ opacity: 0.4; cursor: not-allowed; }}
            .info-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px; }}
            .info-item {{ background: #0f3460; padding: 12px; border-radius: 8px; }}
            .info-label {{ color: #888; font-size: 12px; }}
            .info-value {{ color: #fff; font-size: 20px; font-weight: bold; }}
            .log-box {{ background: #0a0a23; padding: 10px; border-radius: 8px; max-height: 300px; overflow-y: auto; font-family: monospace; font-size: 12px; color: #0f0; }}
            .actions {{ text-align: center; padding: 20px 0; }}
            .footer {{ text-align: center; color: #666; font-size: 12px; margin-top: 20px; }}
            a {{ color: #00d4aa; text-decoration: none; }}
        </style>
    </head>
    <body>
        <h1>🤖 V22 Gold Bot</h1>
        <h2>MT5 Local Edition Dashboard</h2>
        
        <div class="card">
            <h3>Bot Status</h3>
            <span class="status {'running' if status['running'] else 'stopped'}">
                {'🟢 RUNNING' if status['running'] else '🔴 STOPPED'}
            </span>
            {f"<span style='margin-left: 10px;'>PID: {status['pid']}</span>" if status['running'] else ""}
        </div>
        
        <div class="card">
            <h3>Account Info</h3>
            <div class="info-grid">
                <div class="info-item">
                    <div class="info-label">Balance</div>
                    <div class="info-value">${mt5_info['balance']:.2f if mt5_info else 'N/A'}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Equity</div>
                    <div class="info-value">${mt5_info['equity']:.2f if mt5_info else 'N/A'}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Account</div>
                    <div class="info-value" style="font-size:14px">{mt5_info['login'] if mt5_info else 'Not connected'}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Server</div>
                    <div class="info-value" style="font-size:14px">{mt5_info['server'] if mt5_info else 'N/A'}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Open Positions</div>
                    <div class="info-value">{state['positions']}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Total Trades</div>
                    <div class="info-value">{state['trades']}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Daily P&L</div>
                    <div class="info-value" style="color:{'#00d4aa' if state.get('daily_pnl',0)>=0 else '#e74c3c'}">
                        ${state.get('daily_pnl',0):.2f}
                    </div>
                </div>
                <div class="info-item">
                    <div class="info-label">Consecutive Losses</div>
                    <div class="info-value">{state.get('consecutive_losses',0)}</div>
                </div>
            </div>
        </div>
        
        <div class="card actions">
            <h3>Controls</h3>
            <form action="/start" method="post" style="display:inline;">
                <button type="submit" class="btn btn-start" {'disabled' if status['running'] else ''}>▶ START</button>
            </form>
            <form action="/stop" method="post" style="display:inline;">
                <button type="submit" class="btn btn-stop" {'disabled' if not status['running'] else ''}>⏹ STOP</button>
            </form>
            <form action="/restart" method="post" style="display:inline;">
                <button type="submit" class="btn btn-restart">🔄 RESTART</button>
            </form>
        </div>
        
        <div class="card">
            <h3>Recent Logs</h3>
            <div class="log-box">
                {'<br>'.join(logs) if logs else 'No logs'}
            </div>
        </div>
        
        <div class="footer">
            Auto-refreshes every 10 seconds | 
            <a href="#" onclick="window.location.reload()">Refresh now</a>
        </div>
    </body>
    </html>
    """


@app.route("/start", methods=["POST"])
def start_bot():
    """Start the bot as a background process."""
    global bot_process, bot_pid
    
    status = get_bot_status()
    if status["running"]:
        return jsonify({"success": False, "reason": "Already running"})
    
    try:
        bot_process = subprocess.Popen(
            [sys.executable, BOT_SCRIPT],
            stdout=open(BOT_LOG, "a"),
            stderr=subprocess.STDOUT,
            cwd=os.path.dirname(BOT_SCRIPT),
        )
        bot_pid = bot_process.pid
        time.sleep(2)
        return jsonify({"success": True, "pid": bot_pid})
    except Exception as e:
        return jsonify({"success": False, "reason": str(e)})


@app.route("/stop", methods=["POST"])
def stop_bot():
    """Stop the bot gracefully."""
    global bot_process, bot_pid
    
    if bot_pid:
        try:
            os.kill(bot_pid, signal.SIGTERM)
            time.sleep(1)
            # Force kill if still alive
            try:
                os.kill(bot_pid, 0)
                os.kill(bot_pid, signal.SIGKILL)
            except:
                pass
        except:
            pass
        
        bot_process = None
        bot_pid = None
    
    return jsonify({"success": True, "reason": "Stopped"})


@app.route("/restart", methods=["POST"])
def restart_bot():
    """Restart the bot."""
    stop_bot()
    time.sleep(1)
    return start_bot()


@app.route("/api/status")
def api_status():
    """JSON API for dashboard status."""
    status = get_bot_status()
    mt5_info = get_mt5_info()
    state = get_state()
    logs = get_recent_logs(5)
    
    return jsonify({
        "running": status["running"],
        "pid": status["pid"],
        "mt5": mt5_info,
        "state": state,
        "logs": logs,
    })


if __name__ == "__main__":
    print("=" * 50)
    print("  V22 Bot Dashboard")
    print("  Open: http://localhost:5000")
    print("=" * 50)
    app.run(host="0.0.0.0", port=5000, debug=False)