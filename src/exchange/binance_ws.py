import asyncio
import os
import logging
from typing import Callable, Optional
from datetime import datetime

from binance_sdk_derivatives_trading_usds_futures.derivatives_trading_usds_futures import (
    DerivativesTradingUsdsFutures,
    DERIVATIVES_TRADING_USDS_FUTURES_WS_STREAMS_PROD_URL,
    ConfigurationWebSocketStreams,
)

from src.models.candle import Candle


logger = logging.getLogger(__name__)


class BinanceWebSocketClient:
    """WebSocket client for Binance Futures để stream real-time kline data"""
    
    def __init__(
        self,
        on_kline: Optional[Callable[[str, str, Candle], None]] = None
    ):
        """
        Khởi tạo WebSocket client
        
        Args:
            on_kline: Callback function được gọi khi có candle mới hoàn tất
                     Nhận 3 tham số: (symbol, interval, candle)
        """
        self.on_kline = on_kline
        
        # Chọn URL dựa trên production
        stream_url = DERIVATIVES_TRADING_USDS_FUTURES_WS_STREAMS_PROD_URL
        
        # Tạo configuration cho WebSocket
        self.config_ws = ConfigurationWebSocketStreams(stream_url=stream_url)
        
        # Khởi tạo client
        self.client = DerivativesTradingUsdsFutures(config_ws_streams=self.config_ws)
        
        # Lưu connection và stream để có thể close sau
        self.connection = None
        self.stream = None
        self._running = False
        
    def _parse_kline_to_candle(self, kline_data) -> Candle:
        """
        Parse dữ liệu kline từ Binance thành Candle object
        
        Args:
            kline_data: KlineCandlestickStreamsResponse object từ WebSocket
            
        Returns:
            Candle object
        """
        # Convert Pydantic model to dict nếu cần
        if hasattr(kline_data, 'model_dump'):
            data = kline_data.model_dump()
        elif hasattr(kline_data, 'dict'):
            data = kline_data.dict()
        else:
            data = kline_data
            
        k = data.get('k', {})
        
        return Candle(
            timestamp=k['t'],  # Kline start time
            open=float(k['o']),
            high=float(k['h']),
            low=float(k['l']),
            close=float(k['c']),
            volume=float(k['v']),
            quote_volume=float(k['q']),
            number_of_trades=k['n'],
            taker_buy_base_volume=float(k['V']),
            taker_buy_quote_volume=float(k['Q'])
        )
    
    def _handle_kline_message(self, symbol: str, interval: str, data):
        """
        Xử lý message từ WebSocket stream
        
        Args:
            symbol: Trading symbol (e.g., 'BTCUSDT')
            interval: Kline interval (e.g., '1m', '15m')
            data: KlineCandlestickStreamsResponse object từ WebSocket
        """
        try:
            # Convert Pydantic model to dict nếu cần
            if hasattr(data, 'model_dump'):
                data_dict = data.model_dump()
            elif hasattr(data, 'dict'):
                data_dict = data.dict()
            else:
                data_dict = data
            
            # Kiểm tra xem candle đã đóng chưa
            k = data_dict.get('k', {})
            is_closed = k.get('x', False)
            
            if is_closed and self.on_kline:
                # Parse thành Candle object
                candle = self._parse_kline_to_candle(data)
                
                # Gọi callback
                self.on_kline(symbol, interval, candle)
                
        except Exception as e:
            logger.error(f"Error handling kline message: {e}", exc_info=True)
    
    async def run_forever(self, symbol: str, interval: str):
        """
        Chạy WebSocket stream và lắng nghe kline data
        
        Args:
            symbol: Trading symbol (e.g., 'BTCUSDT')
            interval: Kline interval (e.g., '1m', '5m', '15m', '1h', etc.)
        """
        self._running = True
        
        try:
            # Tạo connection
            self.connection = await self.client.websocket_streams.create_connection()
            logger.info(f"✅ WebSocket connected for {symbol} {interval}")
            
            # Subscribe to kline stream
            self.stream = await self.connection.kline_candlestick_streams(
                symbol=symbol.lower(),
                interval=interval
            )
            
            # Set up message handler
            self.stream.on(
                "message",
                lambda data: self._handle_kline_message(symbol, interval, data)
            )
            
            logger.info(f"🔄 Streaming {symbol} {interval} klines...")
            
            # Keep running until stopped
            while self._running:
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"WebSocket error: {e}", exc_info=True)
            raise
        finally:
            await self.close()
    
    async def close(self):
        """Đóng WebSocket connection"""
        self._running = False
        
        try:
            if self.stream:
                await self.stream.unsubscribe()
                logger.info("Unsubscribed from stream")
                
            if self.connection:
                await self.connection.close_connection(close_session=True)
                logger.info("WebSocket connection closed")
                
        except Exception as e:
            logger.error(f"Error closing WebSocket: {e}", exc_info=True)