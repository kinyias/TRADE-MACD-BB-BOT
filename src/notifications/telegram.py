"""
Telegram Notification Service
Gửi thông báo giao dịch và cảnh báo qua Telegram bot
"""
import asyncio
import logging
from typing import Optional, Dict, Any
from datetime import datetime
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """
    Telegram Bot Notifier
    
    Gửi thông báo về:
    - Tín hiệu giao dịch mới
    - Vị thế được mở/đóng
    - Stop loss / Take profit triggered
    - Lỗi hệ thống
    - Báo cáo hiệu suất
    """
    
    def __init__(
        self,
        bot_token: str,
        chat_id: str,
        enabled: bool = True,
        timeout: int = 10
    ):
        """
        Args:
            bot_token: Telegram bot token (từ @BotFather)
            chat_id: Telegram chat ID (user hoặc group)
            enabled: Bật/tắt notifications
            timeout: Timeout cho API calls (seconds)
        """
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.enabled = enabled
        self.timeout = timeout
        
        # Setup session với retry logic
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        self.api_url = f"https://api.telegram.org/bot{bot_token}"
        
        # Verify connection
        if self.enabled:
            self._verify_connection()
    
    def _verify_connection(self) -> bool:
        """Kiểm tra kết nối với Telegram API"""
        try:
            response = self.session.get(
                f"{self.api_url}/getMe",
                timeout=self.timeout
            )
            response.raise_for_status()
            bot_info = response.json()
            
            if bot_info.get("ok"):
                bot_name = bot_info["result"]["username"]
                logger.info(f"✅ Telegram bot connected: @{bot_name}")
                return True
            else:
                logger.error(f"❌ Telegram bot verification failed: {bot_info}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Failed to verify Telegram connection: {e}")
            self.enabled = False
            return False
    
    def send_message(
        self,
        text: str,
        parse_mode: str = "HTML",
        disable_notification: bool = False
    ) -> bool:
        """
        Gửi message text đến Telegram
        
        Args:
            text: Nội dung message
            parse_mode: HTML hoặc Markdown
            disable_notification: Silent notification
        
        Returns:
            True nếu gửi thành công
        """
        if not self.enabled:
            logger.debug("Telegram notifications disabled, skipping message")
            return False
        
        try:
            payload = {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": parse_mode,
                "disable_notification": disable_notification
            }
            
            response = self.session.post(
                f"{self.api_url}/sendMessage",
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()
            result = response.json()
            
            if result.get("ok"):
                logger.debug(f"✅ Telegram message sent successfully")
                return True
            else:
                logger.error(f"❌ Telegram API error: {result}")
                return False
                
        except requests.exceptions.Timeout:
            logger.error(f"⏱️ Telegram API timeout after {self.timeout}s")
            return False
        except Exception as e:
            logger.error(f"❌ Failed to send Telegram message: {e}")
            return False
    
    def send_signal_alert(
        self,
        signal_type: str,
        symbol: str,
        price: float,
        confidence: float,
        reason: str,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None
    ) -> bool:
        """
        Gửi thông báo tín hiệu giao dịch
        
        Args:
            signal_type: BUY, SELL, HOLD
            symbol: Cặp giao dịch
            price: Giá hiện tại
            confidence: Độ tin cậy (0-1)
            reason: Lý do tín hiệu
            stop_loss: Giá stop loss
            take_profit: Giá take profit
        """
        emoji = {"BUY": "🟢", "SELL": "🔴", "HOLD": "⚪"}.get(signal_type, "⚪")
        
        message = f"{emoji} <b>{signal_type} SIGNAL</b>\n\n"
        message += f"📊 Symbol: <b>{symbol}</b>\n"
        message += f"💰 Price: <code>${price:.2f}</code>\n"
        message += f"📈 Confidence: <b>{confidence:.0%}</b>\n"
        message += f"💡 Reason: {reason}\n"
        
        if stop_loss:
            message += f"\n🛑 Stop Loss: <code>${stop_loss:.2f}</code>"
        if take_profit:
            message += f"\n🎯 Take Profit: <code>${take_profit:.2f}</code>"
        
        message += f"\n\n🕐 Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        return self.send_message(message)
    
    def send_position_opened(
        self,
        symbol: str,
        side: str,
        quantity: float,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        position_value: float
    ) -> bool:
        """Thông báo vị thế được mở"""
        emoji = "🟢" if side == "LONG" else "🔴"
        
        message = f"{emoji} <b>POSITION OPENED</b>\n\n"
        message += f"📊 {symbol} - <b>{side}</b>\n"
        message += f"📦 Quantity: <code>{quantity:.8f}</code>\n"
        message += f"💰 Entry: <code>${entry_price:.2f}</code>\n"
        message += f"💵 Value: <code>${position_value:.2f}</code>\n"
        message += f"\n🛑 Stop Loss: <code>${stop_loss:.2f}</code>"
        message += f"\n🎯 Take Profit: <code>${take_profit:.2f}</code>"
        
        risk = abs(entry_price - stop_loss)
        reward = abs(take_profit - entry_price)
        rr_ratio = reward / risk if risk > 0 else 0
        message += f"\n📊 R:R = <b>1:{rr_ratio:.2f}</b>"
        
        message += f"\n\n🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        return self.send_message(message)
    
    def send_position_closed(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        exit_price: float,
        quantity: float,
        pnl: float,
        pnl_percent: float,
        exit_reason: str
    ) -> bool:
        """Thông báo vị thế được đóng"""
        emoji = "✅" if pnl > 0 else "❌"
        
        message = f"{emoji} <b>POSITION CLOSED</b>\n\n"
        message += f"📊 {symbol} - <b>{side}</b>\n"
        message += f"📦 Quantity: <code>{quantity:.8f}</code>\n"
        message += f"📥 Entry: <code>${entry_price:.2f}</code>\n"
        message += f"📤 Exit: <code>${exit_price:.2f}</code>\n"
        
        pnl_emoji = "💰" if pnl > 0 else "💸"
        message += f"\n{pnl_emoji} PnL: <b>${pnl:.2f}</b> ({pnl_percent:+.2f}%)\n"
        message += f"📝 Reason: {exit_reason}"
        
        message += f"\n\n🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        return self.send_message(message)
    
    def send_error_alert(self, error_type: str, error_message: str) -> bool:
        """Gửi cảnh báo lỗi"""
        message = f"⚠️ <b>ERROR ALERT</b>\n\n"
        message += f"🔴 Type: <b>{error_type}</b>\n"
        message += f"📝 Message:\n<code>{error_message}</code>"
        message += f"\n\n🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        return self.send_message(message)
    
    def send_daily_summary(self, summary: Dict[str, Any]) -> bool:
        """Gửi báo cáo hằng ngày"""
        message = f"📊 <b>DAILY SUMMARY</b>\n\n"
        
        total_trades = summary.get("total_trades", 0)
        winning_trades = summary.get("winning_trades", 0)
        losing_trades = summary.get("losing_trades", 0)
        
        message += f"📈 Total Trades: <b>{total_trades}</b>\n"
        message += f"✅ Wins: <b>{winning_trades}</b>\n"
        message += f"❌ Losses: <b>{losing_trades}</b>\n"
        
        if total_trades > 0:
            win_rate = (winning_trades / total_trades) * 100
            message += f"🎯 Win Rate: <b>{win_rate:.1f}%</b>\n"
        
        total_pnl = summary.get("total_pnl", 0)
        pnl_emoji = "💰" if total_pnl > 0 else "💸"
        message += f"\n{pnl_emoji} Total PnL: <b>${total_pnl:.2f}</b>"
        
        balance = summary.get("balance", 0)
        message += f"\n💵 Balance: <code>${balance:.2f}</code>"
        
        message += f"\n\n🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        return self.send_message(message)
    
    def disable(self):
        """Tắt notifications"""
        self.enabled = False
        logger.info("Telegram notifications disabled")
    
    def enable(self):
        """Bật notifications"""
        self.enabled = True
        logger.info("Telegram notifications enabled")
