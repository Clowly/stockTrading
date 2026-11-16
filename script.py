#!/usr/bin/env python3
"""
Turtle-style stock alerts: 20-day breakout to BUY, 10-day low to SELL.

Setup:
    pip install yfinance pandas
    # optional phone push: install the free "ntfy" app, subscribe to a
    # private topic name, then:  export NTFY_TOPIC=your-secret-topic-name

Commands:
    python turtle_alerts.py add AAPL MSFT NVDA   # add to watchlist
    python turtle_alerts.py remove MSFT          # remove from watchlist
    python turtle_alerts.py bought AAPL          # you bought it (now watching exit)
    python turtle_alerts.py sold AAPL            # you sold it (back to watching entry)
    python turtle_alerts.py list                 # show watchlist + positions
    python turtle_alerts.py run                  # check signals + notify

Schedule `run` once per weekday after the US market closes (~4:30pm ET).
Then place the trade by hand in Cash App.
"""
import json
import os
import sys
import urllib.request
from pathlib import Path

import pandas as pd
import yfinance as yf

ENTRY_DAYS = 20   # buy when close breaks above the prior 20-day high
EXIT_DAYS = 10    # sell when close breaks below the prior 10-day low
STATE_FILE = Path(__file__).with_name("state.json")


def load():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"watchlist": [], "holding": []}


def save(state):
    STATE_FILE.write_text(json.dumps(state, indent=2))


def notify(title, message):
    print(f"[{title}] {message}")
    topic = os.environ.get("NTFY_TOPIC")
    if not topic:
        return
    try:
        req = urllib.request.Request(
            f"https://ntfy.sh/{topic}",
            data=message.encode("utf-8"),
            headers={"Title": title},
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f"  (notification failed: {e})")


def get_levels(symbol):
    df = yf.download(symbol, period="4mo", interval="1d",
                     auto_adjust=False, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.dropna()
    if len(df) < ENTRY_DAYS + 2:
        return None
    prior = df.iloc[:-1]  # exclude today so "breakout" means beating past days
    return {
        "close": float(df["Close"].iloc[-1]),
        "high20": float(prior["High"].tail(ENTRY_DAYS).max()),
        "low10": float(prior["Low"].tail(EXIT_DAYS).min()),
    }


def run():
    state = load()
    if not state["watchlist"]:
        print("Watchlist is empty. Try: python turtle_alerts.py add AAPL")
        return
    for sym in state["watchlist"]:
        try:
            lv = get_levels(sym)
        except Exception as e:
            print(f"{sym}: data error ({e})")
            continue
        if lv is None:
            print(f"{sym}: not enough data")
            continue
        held = sym in state["holding"]
        status = "HOLDING" if held else "watching"
        print(f"{sym} ({status}): close {lv['close']:.2f} | "
              f"20d high {lv['high20']:.2f} | 10d low {lv['low10']:.2f}")
        if not held and lv["close"] > lv["high20"]:
            notify(f"BUY signal: {sym}",
                   f"{sym} closed at {lv['close']:.2f}, above its 20-day high "
                   f"of {lv['high20']:.2f}. Buy in Cash App, then run: "
                   f"turtle_alerts.py bought {sym}")
        elif held and lv["close"] < lv["low10"]:
            notify(f"SELL signal: {sym}",
                   f"{sym} closed at {lv['close']:.2f}, below its 10-day low "
                   f"of {lv['low10']:.2f}. Sell in Cash App, then run: "
                   f"turtle_alerts.py sold {sym}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    cmd, args = sys.argv[1].lower(), [a.upper() for a in sys.argv[2:]]
    state = load()
    if cmd == "add":
        for s in args:
            if s not in state["watchlist"]:
                state["watchlist"].append(s)
    elif cmd == "remove":
        for s in args:
            state["watchlist"] = [x for x in state["watchlist"] if x != s]
            state["holding"] = [x for x in state["holding"] if x != s]
    elif cmd == "bought":
        for s in args:
            if s not in state["watchlist"]:
                state["watchlist"].append(s)
            if s not in state["holding"]:
                state["holding"].append(s)
    elif cmd == "sold":
        state["holding"] = [x for x in state["holding"] if x not in args]
    elif cmd == "list":
        print("Watchlist:", ", ".join(state["watchlist"]) or "(empty)")
        print("Holding:  ", ", ".join(state["holding"]) or "(none)")
        return
    elif cmd == "run":
        run()
        return
    else:
        print(__doc__)
        return
    save(state)
    print("Watchlist:", ", ".join(state["watchlist"]) or "(empty)")
    print("Holding:  ", ", ".join(state["holding"]) or "(none)")


if __name__ == "__main__":
    main()
