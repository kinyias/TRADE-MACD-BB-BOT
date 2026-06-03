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


async def main():
    """Main function"""
    global bot_status
    
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
    candles = rest_client.get_klines(
        symbol=SYMBOL,
        interval=TIMEFRAME,
        limit=LOOKBACK_CANDLES  # Lấy LOOKBACK_CANDLES nến gần nhất
    )
    
    logger.info(f"✅ Got {len(candles)} historical candles")
    if candles:
        latest = candles[-1]
        logger.info(f"Latest candle: Close=${latest.close:.2f} at {latest.datetime}")
    
    # Tạo callback function có thể truy cập vào candles list
    def on_new_candle(symbol: str, interval: str, candle: Candle):
        """Callback khi nhận candle mới từ WebSocket"""
        global bot_status
        
        logger.info(f"🔔 New candle: {symbol} {interval}")
        logger.info(f"   Open: ${candle.open:.2f} | High: ${candle.high:.2f}")
        logger.info(f"   Low: ${candle.low:.2f} | Close: ${candle.close:.2f}")
        logger.info(f"   Volume: {candle.volume:.2f}")
        logger.info(f"   Time: {candle.datetime}")
        
        # Thêm candle mới vào list
        candles.append(candle)
        # Giữ số lượng candles không vượt quá limit để tránh tốn bộ nhớ
        if len(candles) > LOOKBACK_CANDLES:
            candles.pop(0)
        
        latest = candles[-1]
        logger.info(f"Latest candle: Close=${latest.close:.2f} at {latest.datetime}")
        
        # Update bot status
        bot_status["total_candles"] += 1
        bot_status["last_candle"] = {
            "symbol": symbol,
            "close": candle.close,
            "time": str(candle.datetime)
        }
        
        # Gửi thông báo Telegram
        message = f"🕯️ <b>New Candle</b>\n\n"
        message += f"📊 Symbol: <b>{symbol}</b> ({interval})\n"
        message += f"💰 Open: <code>${candle.open:.2f}</code>\n"
        message += f"📈 High: <code>${candle.high:.2f}</code>\n"
        message += f"📉 Low: <code>${candle.low:.2f}</code>\n"
        message += f"💵 Close: <code>${candle.close:.2f}</code>\n"
        message += f"📦 Volume: <code>{candle.volume:.2f}</code>\n"
        message += f"🕐 Time: {candle.datetime}"
        
        telegram.send_message(message)
    
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
