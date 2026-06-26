# TRADE-MACD-BB-BOT 📈

An automated cryptocurrency trading bot that uses MACD reversal detection combined with EMA 200 trend confirmation to generate trading signals for Binance Futures markets.

## 🎯 Overview

This trading bot detects MACD reversal patterns (peaks and troughs) and confirms them with EMA 200 trend analysis to identify optimal entry and exit points in the cryptocurrency futures market. The bot features real-time data streaming, AI-powered market analysis, and Telegram notifications.

## ✨ Features

### Core Trading Features

- **Advanced Strategy**: MACD reversal detection with EMA 200 trend confirmation
- **Real-time Data**: WebSocket streaming for live market data from Binance
- **Multiple Indicators**: MACD reversal detection, EMA 200, Volume Profile
- **AI Analysis**: Integrated AI market analysis using OpenRouter API
- **AI-Powered Insights**: Market analysis after each signal using OpenRouter AI

### Market Data Analysis

- **Funding Rate Monitoring**: Track perpetual futures funding rates
- **Order Book Analysis**: Real-time order book depth analysis
- **Volume Profile**: Analyze volume distribution across price levels
- **Taker Buy/Sell Volume**: Monitor market participant behavior
- **Recent Trades**: Track recent market trades

### Monitoring & Notifications

- **Flask API**: RESTful API for monitoring bot status and indicators
- **Telegram Notifications**: Real-time alerts and updates
- **Backtesting**: Test strategies on historical data

## 🏗️ Project Structure

```
TRADE-MACD-BB-BOT/
├── src/
│   ├── config/              # Configuration management
│   │   ├── settings.py      # Global settings and environment variables
│   │   └── __init__.py
│   ├── exchange/            # Exchange integrations
│   │   ├── binance_rest.py  # Binance REST API client
│   │   ├── binance_ws.py    # Binance WebSocket client
│   │   ├── funding_rate.py  # Funding rate data
│   │   ├── open_interest.py # Open interest tracking
│   │   ├── order_book.py    # Order book analysis
│   │   ├── recent_trades_list.py
│   │   ├── taker_buy_sell_volume.py
│   │   └── volume_profile.py
│   ├── indicator/           # Technical indicators
│   │   ├── ai.py           # AI-powered analysis
│   │   ├── bollingerband.py
│   │   ├── ema.py
│   │   ├── macd.py
│   │   └── market_analyzer.py
│   ├── models/              # Data models
│   │   ├── candle.py       # Candlestick data structure
│   │   └── position.py     # Position management
│   ├── notifications/       # Notification services
│   │   └── telegram.py     # Telegram bot integration
│   ├── order/              # Order management
│   │   ├── executor.py     # Order execution
│   │   └── order_manager.py
│   ├── risk/               # Risk management
│   │   ├── position_size.py
│   │   └── stop_loss.py
│   ├── strategies/         # Trading strategies
│   │   └── macd_bb_strategy.py
│   ├── test/               # Testing
│   │   └── backtest.py
│   ├── utils/              # Utilities
│   │   ├── helpers.py
│   │   └── logger.py
│   └── main.py             # Main application entry point
├── .env.example            # Example environment variables
├── pyproject.toml          # Poetry dependencies
├── poetry.lock            # Lock file for dependencies
└── README.md              # This file
```

## 📋 Prerequisites

- Python 3.12 or higher (< 3.15)
- Poetry (Python package manager)
- Binance account with Futures trading enabled
- Telegram Bot Token (optional, for notifications)
- OpenRouter API Key (optional, for AI analysis)

## 🚀 Installation

1. **Clone the repository**

   ```bash
   git clone <repository-url>
   cd TRADE-MACD-BB-BOT
   ```

2. **Install Poetry** (if not already installed)

   ```bash
   curl -sSL https://install.python-poetry.org | python3 -
   ```

3. **Install dependencies**

   ```bash
   poetry install
   ```

4. **Configure environment variables**
   ```bash
   cp .env.example .env
   ```
   Edit `.env` with your configuration (see Configuration section below).

## ⚙️ Configuration

Edit the `.env` file with your settings:

```bash
# Telegram Notifications (Optional)
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# Trading Parameters
SYMBOL=SOLUSDC              # Trading pair
TIMEFRAME=1m                # Candlestick timeframe (1m, 5m, 15m, 1h, etc.)
LOOKBACK_CANDLES=200        # Number of historical candles to analyze

# AI Analysis (Optional)
OPENROUTER_API_KEY=your_openrouter_api_key
```

### Strategy Parameters

The MACD Reversal + EMA strategy can be configured in `src/main.py`:

- **MACD Parameters** (line 42):
  - `fast_period`: Fast EMA period (default: 12)
  - `slow_period`: Slow EMA period (default: 26)
  - `signal_period`: Signal line period (default: 9)

- **EMA Parameters** (line 43):
  - `period`: EMA period for trend confirmation (default: 200)

- **Reversal Detection Parameters** (line 744):
  - `lookback`: Number of candles to look back for peak/trough detection (default: 3)

## 🎮 Usage

### Start the bot

```bash
poetry run start
```

Or manually:

```bash
poetry run python -m src.main
```

The bot will:

1. Start the Flask API server (default port: 5000)
2. Connect to Binance WebSocket for real-time data
3. Begin analyzing market conditions
4. Send notifications via Telegram (if configured)

### Access the API

Once running, you can access the following endpoints:

- **Health Check**: `http://localhost:5000/`
- **Bot Status**: `http://localhost:5000/status`
- **MACD Data**: `http://localhost:5000/macd`
- **MACD Peak/Trough Detection**: `http://localhost:5000/macd/peak`

## 📊 API Endpoints

### GET /

Health check endpoint

```json
{
  "status": "ok",
  "service": "Crypto Trading Bot",
  "timestamp": "2026-06-26T10:00:00"
}
```

### GET /status

Bot status and statistics

```json
{
  "running": true,
  "started_at": "2026-06-26T10:00:00",
  "last_candle": {...},
  "total_candles": 150
}
```

### GET /macd

Current MACD indicator values

```json
{
  "symbol": "SOLUSDC",
  "timeframe": "1m",
  "macd": {
    "macd": 0.123,
    "signal": 0.11,
    "histogram": 0.013,
    "is_bullish": true,
    "is_bearish": false,
    "is_bullish_crossover": false,
    "is_bearish_crossover": false
  },
  "candles_count": 200
}
```

### GET /macd/peak

MACD peak and trough detection

```json
{
  "symbol": "SOLUSDC",
  "peak": {
    "detected": true,
    "info": {...}
  },
  "trough": {
    "detected": false,
    "info": null
  },
  "reversal": {...}
}
```

## 💡 Trading Strategy

### MACD Reversal Detection + EMA 200 Confirmation

The bot uses MACD reversal patterns combined with EMA 200 trend confirmation to generate high-probability trading signals.

#### How It Works:

**1. MACD Reversal Detection**

- Monitors MACD histogram for peaks (local maxima) and troughs (local minima)
- Uses a 3-candle lookback window to identify reversal points
- Detects both bullish reversals (troughs) and bearish reversals (peaks)

**2. EMA 200 Trend Confirmation**

- Confirms the overall market trend using 200-period EMA
- Price above EMA 200 = Bullish trend
- Price below EMA 200 = Bearish trend

#### Trading Signals:

**🟢 BUY Signal (Long Entry):**

- MACD shows bullish reversal (trough detected in histogram)
- **AND** price is above EMA 200 (bullish trend)
- Signal indicates potential upward momentum in an uptrend

**🔴 SELL Signal (Short Entry):**

- MACD shows bearish reversal (peak detected in histogram)
- **AND** price is below EMA 200 (bearish trend)
- Signal indicates potential downward momentum in a downtrend

#### Signal Flow:

1. **Data Collection**: Bot collects 200 historical candles on startup
2. **Real-time Monitoring**: WebSocket streams live candle data
3. **Reversal Detection**: Each new candle triggers MACD reversal analysis
4. **Trend Confirmation**: EMA 200 position validates the trend direction
5. **Signal Generation**: When both conditions align, trading signal is sent via Telegram
6. **AI Analysis**: After signal generation, comprehensive market analysis is performed using AI

#### Why This Strategy Works:

- **MACD Reversals**: Catch momentum shifts at optimal entry points
- **EMA 200 Filter**: Ensures trades align with the dominant trend
- **Reduced False Signals**: Dual confirmation minimizes whipsaw trades
- **Trend Following**: Only trades in the direction of the major trend

## ⚠️ Risk Warning

**IMPORTANT: Trading cryptocurrencies carries significant risk.**

- This bot is provided for educational and research purposes
- Past performance does not guarantee future results
- Always test strategies thoroughly with backtesting before live trading
- Start with small amounts and paper trading
- Never invest more than you can afford to lose
- The cryptocurrency market is highly volatile and unpredictable
- The developers are not responsible for any financial losses

**USE AT YOUR OWN RISK**

## 🔧 Development

### Run tests

```bash
poetry run pytest
```

### Run backtest

```bash
poetry run python -m src.test.backtest
```

### Code structure

- Follow PEP 8 style guidelines
- Use type hints for better code clarity
- Document complex functions and classes
- Write unit tests for new features

## 📝 Dependencies

Key dependencies (see `pyproject.toml` for full list):

- `binance-sdk-derivatives-trading-usds-futures`: Binance API integration
- `python-telegram-bot`: Telegram notifications
- `pandas-ta`: Technical analysis indicators
- `pydantic`: Data validation
- `flask`: Web API server
- `mplfinance`: Chart visualization
- `openrouter`: AI analysis integration

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

[Add your license here]

## 📧 Contact

[Add your contact information here]

---

**Disclaimer**: This software is for educational purposes only. Use at your own risk. The authors and contributors are not responsible for any financial losses incurred from using this bot.
