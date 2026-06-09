# 📊 Options Trading Platform v3.1

A professional-grade options trading dashboard built on **Kotak Neo API** with live market data, strategy automation, and zero brokerage execution.

---

## 🚀 Features

### Trading
- ✅ **Zero Brokerage** — orders via Kotak Neo API - Kotak charges 0 brokerage on API orders
- ✅ **Bulk Order Entry** — place multiple orders in one click
- ✅ **One-Click Square Off All** — close all positions instantly
- ✅ **Single & Bulk Order Management**
- ✅ **Multi-User Support** — manage two accounts simultaneously - configurable to increase n number of accounts

### Analytics
- ✅ **Live PCR Monitor** — Put-Call Ratio tracked every 2 minutes - strikes count can be configured
- ✅ **OI Change Tracking** — Call & Put OI with delta
- ✅ **Market Direction Signal** — Strong Bullish to Strong Bearish 
- ✅ **Historical OI Data** — auto-saved every 2 minutes, 9:15 AM to 3:30 PM - batch file runs to download 
- ✅ **Auto Option Chain Backup** — zipped daily at 3:35 PM

### Strategy Engine
- ✅ **Custom Strategy Builder** — up to 8 legs
- ✅ **Pre-built Strategies** — Short Straddle, Short Strangle, Bull Call Spread etc
- ✅ **Stop Loss** — Combined Points, Combined %, Leg Points, Leg %
- ✅ **Trailing Stop Loss**
- ✅ **PANIC Button** — emergency exit all strategies and all users

### Reporting & Logs
- ✅ **Auto Excel Order Reports** — per user, per day
- ✅ **Complete Audit Trail** — every order logged with full details
- ✅ **Telegram Notifications** — real-time order alerts
- ✅ **Websocket Live Feed** — logged per user per day
- ✅ **Date-wise folder organisation** — going back to day one

### MCX Support
- ✅ **MCX Dashboard** — Gold, Silver, Crude Oil, Natural Gas
- ✅ **MCX Strike Selection**
- ✅ **MCX Report Download**

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11, Flask |
| Broker API | Kotak Neo API |
| Live Feed | Websocket |
| Frontend | HTML, CSS, JavaScript |
| Notifications | Telegram Bot API |
| Data Storage | YAML, SQLite, Excel |
| Logging | Python logging, date-wise folders |

---

## 📁 Project Structure

```
options-trading-ver3/
├── client_subscribe/     ← Kotak API login & websocket
├── helper/               ← Core business logic
├── options_trading/      ← Flask app, routes, templates, static
│   ├── templates/        ← HTML pages
│   └── static/           ← CSS & JS files
├── strategy/             ← Strategy engine
├── symbol_creation/      ← Symbol & token management
├── utils/                ← Shared utilities
├── variables/            ← YAML config files
├── trading_setup.py           ← App entry point
└── START_TRADING.bat     ← Windows launcher

```

---

## ⚙️ Setup

### Prerequisites
- Windows OS
- Python 3.11
- Kotak Neo API access
 

### Installation
```bash
pip install -r requirements.txt
```

### Configuration
Create the following files with your credentials:
```
get in touch for this
```

### Running
- Double-click `START_TRADING.bat`
- exe file available - so none of above required
Browser opens automatically at `http://localhost:5000`

---

## 📊 Pages

| Page | Description |
|------|-------------|
| `/` | Login — select index, account, 2FA |
| `/dashboard` | Live symbols, LTP, bulk order entry |
| `/positions` | Live P&L, trade history, order report |
| `/strategies` | Strategy builder and deployment |
| `/analytics` | PCR monitor, OI change tracker |
| `/mcx` | MCX commodities dashboard |

---

## 🔐 Security

- All credentials stored in `.env` files outside project
- `.gitignore` protects all sensitive files
- Session-based authentication
- No credentials ever committed to repository

---

## 📈 Live Performance

- Working live with NIFTY/BANKNIFTY/SENSEX/MCX options on Kotak Neo 
- PCR data collected daily since Mar 2026
- 180+ option chain snapshots per trading day
- Orders executed in under 1 seconds

---

## 📝 License

Private — All rights reserved.
