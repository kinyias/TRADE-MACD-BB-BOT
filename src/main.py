from flask import Flask, jsonify
import asyncio
import logging
import threading
from datetime import datetime
from src.config.settings import *
from src.exchange.binance_rest import BinanceRestClient
from src.exchange.binance_ws import BinanceWebSocketClient
from src.models.candle import Candle
from src.notifications.telegram import TelegramNotifier
from src.indicator.macd import MACDIndicator
from src.indicator.ema import EMAIndicator

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Flask app
app = Flask(__name__)

# Bot status tracking
bot_status = {
    "running": False,
    "started_at": None,
    "last_candle": None,
    "total_candles": 0
}

# Global data storage
candles_data = []
macd_indicator = MACDIndicator(fast_period=12, slow_period=26, signal_period=9)
ema_indicator = EMAIndicator(period=200)


@app.route('/')
def home():
    """Health check endpoint"""
    return jsonify({
        "status": "ok",
        "service": "Crypto Trading Bot",
        "timestamp": datetime.now().isoformat()
    })


@app.route('/status')
def status():
    """Bot status endpoint"""
    return jsonify(bot_status)


@app.route('/health')
def health():
    """Health check for deployment platforms"""
    return jsonify({"status": "healthy"}), 200


@app.route('/macd')
def get_macd():
    """Get current MACD information"""
    if not candles_data:
        return jsonify({
            "error": "No candle data available yet",
            "message": "Bot is still collecting data"
        }), 404
    
    # Lấy giá close từ candles
    close_prices = [float(candle.close) for candle in candles_data]
    
    # Tính MACD signal
    macd_signal = macd_indicator.get_latest_signal(close_prices)
    
    if not macd_signal:
        return jsonify({
            "error": "Not enough data to calculate MACD",
            "message": f"Need at least {macd_indicator.slow_period + macd_indicator.signal_period} candles"
        }), 404
    
    return jsonify({
        "symbol": SYMBOL,
        "last_candle": candles_data[-1].dict(),
        "timeframe": TIMEFRAME,
        "macd": {
            "macd": macd_signal.macd,
            "signal": macd_signal.signal,
            "histogram": macd_signal.histogram,
            "is_bullish": macd_signal.is_bullish,
            "is_bearish": macd_signal.is_bearish,
            "is_bullish_crossover": macd_signal.is_bullish_crossover,
            "is_bearish_crossover": macd_signal.is_bearish_crossover,
            "histogram_increasing": macd_signal.histogram_increasing,
            "histogram_decreasing": macd_signal.histogram_decreasing
        },
        "indicator_params": {
            "fast_period": macd_indicator.fast_period,
            "slow_period": macd_indicator.slow_period,
            "signal_period": macd_indicator.signal_period
        },
        "candles_count": len(candles_data),
        "timestamp": datetime.now().isoformat()
    })


@app.route('/macd/peak')
def check_macd_peak():
    """Check for MACD peak reversal signal"""
    if not candles_data:
        return jsonify({
            "error": "No candle data available yet",
            "message": "Bot is still collecting data"
        }), 404
    
    # Lấy giá close từ candles
    close_prices = [float(candle.close) for candle in candles_data]
    
    # Kiểm tra peak (lookback = 3 candles)
    is_peak, peak_info = macd_indicator.detect_macd_peak(close_prices, lookback=3)
    
    # Kiểm tra trough (lookback = 3 candles)
    is_trough, trough_info = macd_indicator.detect_macd_trough(close_prices, lookback=3)
    
    # Kiểm tra reversal tổng quát
    reversal_info = macd_indicator.detect_macd_reversal(close_prices, lookback=3)
    
    return jsonify({
        "symbol": SYMBOL,
        "timeframe": TIMEFRAME,
        "peak": {
            "detected": is_peak,
            "info": peak_info if is_peak else None
        },
        "trough": {
            "detected": is_trough,
            "info": trough_info if is_trough else None
        },
        "reversal": reversal_info,
        "candles_count": len(candles_data),
        "timestamp": datetime.now().isoformat()
    })


@app.route('/ema')
def get_ema():
    """Get current EMA 200 information"""
    if not candles_data:
        return jsonify({
            "error": "No candle data available yet",
            "message": "Bot is still collecting data"
        }), 404
    
    # Lấy giá close từ candles
    close_prices = [float(candle.close) for candle in candles_data]
    
    # Tính EMA signal
    ema_signal = ema_indicator.get_latest_signal(close_prices)
    
    if not ema_signal:
        return jsonify({
            "error": "Not enough data to calculate EMA",
            "message": f"Need at least {ema_indicator.period} candles"
        }), 404
    
    # Phát hiện crossover
    has_crossover, crossover_type = ema_indicator.detect_crossover(close_prices)
    
    # Kiểm tra xu hướng mạnh
    is_strong, trend_type = ema_indicator.is_strong_trend(close_prices, threshold=3.0)
    
    # Lấy slope
    slope = ema_indicator.get_slope(close_prices, lookback=5)
    
    # Kiểm tra bounce
    bounce = ema_indicator.is_price_bouncing_off_ema(close_prices, lookback=3, bounce_threshold=0.5)
    
    # Lấy support/resistance level
    support_resistance = ema_indicator.get_support_resistance_level(close_prices)
    
    return jsonify({
        "symbol": SYMBOL,
        "last_candle": candles_data[-1].dict(),
        "timeframe": TIMEFRAME,
        "ema": {
            "period": ema_indicator.period,
            "value": ema_signal.ema_value,
            "current_price": ema_signal.current_price,
            "distance_percent": ema_signal.distance_to_ema,
            "distance_absolute": ema_signal.distance_absolute,
            "price_position": ema_signal.price_position,
            "is_bullish": ema_signal.is_bullish,
            "is_bearish": ema_signal.is_bearish,
            "is_far_from_ema": ema_signal.is_far_from_ema
        },
        "crossover": {
            "detected": has_crossover,
            "type": crossover_type
        },
        "trend": {
            "is_strong": is_strong,
            "type": trend_type
        },
        "slope": slope,
        "bounce": bounce,
        "support_resistance": support_resistance,
        "candles_count": len(candles_data),
        "timestamp": datetime.now().isoformat()
    })


async def main():
    """Main function"""
    global bot_status, candles_data
    
    bot_status["running"] = True
    bot_status["started_at"] = datetime.now().isoformat()
    
    logger.info(f"Starting bot for {SYMBOL} {TIMEFRAME}")
    
    # Initialize Telegram Notifier
    telegram = TelegramNotifier(
        bot_token=TELEGRAM_BOT_TOKEN,
        chat_id=TELEGRAM_CHAT_ID,
        enabled=bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)
    )
    
    # Gửi tin nhắn test để kiểm tra kết nối
    test_message = f"🤖 <b>Bot Started</b>\n\n"
    test_message += f"📊 Symbol: <b>{SYMBOL}</b>\n"
    test_message += f"⏱️ Timeframe: <b>{TIMEFRAME}</b>\n"
    test_message += f"📈 Lookback: <b>{LOOKBACK_CANDLES}</b> candles\n"
    telegram.send_message(test_message)
    
    # 1. Lấy historical candles
    logger.info("=" * 50)
    logger.info("Fetching historical candles...")
    
    rest_client = BinanceRestClient()
    candles_data = rest_client.get_klines(
        symbol=SYMBOL,
        interval=TIMEFRAME,
        limit=LOOKBACK_CANDLES  # Lấy LOOKBACK_CANDLES nến gần nhất
    )
    
    logger.info(f"✅ Got {len(candles_data)} historical candles")
    if candles_data:
        latest = candles_data[-1]
        logger.info(f"Latest candle: Close=${latest.close:.2f} at {latest.datetime}")
    
    # Tạo callback function có thể truy cập vào candles list
    def on_new_candle(symbol: str, interval: str, candle: Candle):
        """Callback khi nhận candle mới từ WebSocket"""
        global bot_status, candles_data
        
        # Thêm candle mới vào list
        candles_data.append(candle)
        # Giữ số lượng candles không vượt quá limit để tránh tốn bộ nhớ
        if len(candles_data) > LOOKBACK_CANDLES:
            candles_data.pop(0)
        
        latest = candles_data[-1]
        logger.info(f"Latest candle: Close=${latest.close:.2f} at {latest.datetime}")
        
        # Update bot status
        bot_status["total_candles"] += 1
        bot_status["last_candle"] = {
            "symbol": symbol,
            "close": candle.close,
            "time": str(candle.datetime)
        }
        
        # Kiểm tra điều kiện gửi signal
        if len(candles_data) >= macd_indicator.slow_period + macd_indicator.signal_period:
            # Lấy giá close từ candles
            close_prices = [float(c.close) for c in candles_data]
            
            # Phát hiện MACD reversal
            macd_reversal = macd_indicator.detect_macd_reversal(close_prices, lookback=3)
            
            # Lấy EMA signal
            ema_signal = ema_indicator.get_latest_signal(close_prices)
            
            # Chỉ gửi signal khi EMA và MACD reversal cùng trend
            if macd_reversal and ema_signal:
                signal_type = None
                
                # MACD bullish reversal (trough) + EMA bullish (giá trên EMA) = BUY
                if macd_reversal['direction'] == 'bullish' and ema_signal.is_bullish:
                    signal_type = 'BUY'
                
                # MACD bearish reversal (peak) + EMA bearish (giá dưới EMA) = SELL
                elif macd_reversal['direction'] == 'bearish' and ema_signal.is_bearish:
                    signal_type = 'SELL'
                
                # Gửi signal nếu có
                if signal_type:
                    message = f"🚨 <b>TRADING SIGNAL</b> 🚨\n\n"
                    message += f"📊 Symbol: <b>{symbol}</b> ({interval})\n"
                    message += f"🎯 Signal: <b>{signal_type}</b>\n\n"
                    message += f"💵 Price: <code>${candle.close:.2f}</code>\n"
                    message += f"🕐 Time: {candle.datetime}\n\n"
                    message += f"📈 <b>MACD Reversal</b>\n"
                    message += f"  • Type: {macd_reversal['type']}\n"
                    message += f"  • Direction: {macd_reversal['direction']}\n"
                    message += f"  • Strength: {macd_reversal['strength']:.4f}\n\n"
                    message += f"📊 <b>EMA {ema_indicator.period}</b>\n"
                    message += f"  • Value: ${ema_signal.ema_value:.2f}\n"
                    message += f"  • Distance: {ema_signal.distance_to_ema:+.2f}%\n"
                    message += f"  • Position: {ema_signal.price_position}"
                    
                    telegram.send_message(message)
                    logger.info(f"🎯 {signal_type} SIGNAL sent for {symbol} at ${candle.close:.2f}")
    
    # 2. Stream real-time candles
    logger.info("=" * 50)
    logger.info("Starting real-time WebSocket stream...")
    
    ws_client = BinanceWebSocketClient(
        on_kline=on_new_candle
    )
    
    try:
        await ws_client.run_forever(
            symbol=SYMBOL,
            interval=TIMEFRAME
        )
    except KeyboardInterrupt:
        logger.info("Stopping bot...")
        await ws_client.close()


# 1. Thêm hàm này để làm cổng vào cho Poetry
def run_bot():
    """Hàm đồng bộ làm điểm chạy cho Poetry - chỉ chạy bot"""
    asyncio.run(main())


def run_bot_in_background():
    """Run bot in a background thread"""

    def bot_thread():
        asyncio.run(main())
    
    thread = threading.Thread(target=bot_thread, daemon=True)
    thread.start()


def run_flask_server(host='0.0.0.0', port=5000):
    """Run Flask web server"""
    logger.info(f"Starting Flask server on {host}:{port}")
    app.run(host=host, port=port, debug=False)


def run_with_flask(host='0.0.0.0', port=5000):
    """Run both bot and Flask server"""
    # Start bot in background thread
    run_bot_in_background()
    
    # Run Flask in main thread (blocking)
    run_flask_server(host=host, port=port)


# 2. Sửa lại đoạn này để nếu chạy python trực tiếp vẫn hoạt động
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    run_with_flask(port=port)
