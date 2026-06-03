"""
Binance REST API Client
Wrapper cho Binance Futures REST API
"""
import os
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

from binance_sdk_derivatives_trading_usds_futures.derivatives_trading_usds_futures import (
    DerivativesTradingUsdsFutures,
    ConfigurationRestAPI,
    DERIVATIVES_TRADING_USDS_FUTURES_REST_API_PROD_URL,
)
from binance_sdk_derivatives_trading_usds_futures.rest_api.models import (
    MarkPriceKlineCandlestickDataIntervalEnum,
)

from ..models.candle import Candle

logger = logging.getLogger(__name__)


class BinanceRestClient:
    """
    Binance Futures REST API Client
    
    Wrapper để tương tác với Binance Futures API:
    - Lấy dữ liệu giá (klines/candlesticks)
    - Quản lý orders (tạo, hủy, query)
    - Quản lý positions
    - Lấy thông tin tài khoản
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
    ):
        """
        Args:
            api_key: Binance API key
            api_secret: Binance API secret
        """
        self.api_key = api_key or os.getenv("BINANCE_API_KEY", "")
        self.api_secret = api_secret or os.getenv("BINANCE_API_SECRET", "")
        
        # Determine base URL
        base_url = DERIVATIVES_TRADING_USDS_FUTURES_REST_API_PROD_URL
        
        # Create configuration
        self.config = ConfigurationRestAPI(
            api_key=self.api_key,
            api_secret=self.api_secret,
            base_path=base_url,
        )
        
        # Initialize client
        self.client = DerivativesTradingUsdsFutures(config_rest_api=self.config)
        
        logger.info(f"Binance REST client initialized")
    
    def get_klines(
        self,
        symbol: str,
        interval: str,
        limit: int = 500
    ) -> List[Candle]:
        """
        Lấy dữ liệu nến (klines/candlesticks)
        
        Args:
            symbol: Cặp giao dịch (VD: BTCUSDT)
            interval: Khung thời gian (1m, 5m, 15m, 1h, 4h, 1d)
            limit: Số nến (tối đa 1500)
        
        Returns:
            List[Candle]
        """
        try:
            # Map interval string to enum
            interval_map = {
                "1m": MarkPriceKlineCandlestickDataIntervalEnum.INTERVAL_1m,
                "3m": MarkPriceKlineCandlestickDataIntervalEnum.INTERVAL_3m,
                "5m": MarkPriceKlineCandlestickDataIntervalEnum.INTERVAL_5m,
                "15m": MarkPriceKlineCandlestickDataIntervalEnum.INTERVAL_15m,
                "30m": MarkPriceKlineCandlestickDataIntervalEnum.INTERVAL_30m,
                "1h": MarkPriceKlineCandlestickDataIntervalEnum.INTERVAL_1h,
                "2h": MarkPriceKlineCandlestickDataIntervalEnum.INTERVAL_2h,
                "4h": MarkPriceKlineCandlestickDataIntervalEnum.INTERVAL_4h,
                "6h": MarkPriceKlineCandlestickDataIntervalEnum.INTERVAL_6h,
                "8h": MarkPriceKlineCandlestickDataIntervalEnum.INTERVAL_8h,
                "12h": MarkPriceKlineCandlestickDataIntervalEnum.INTERVAL_12h,
                "1d": MarkPriceKlineCandlestickDataIntervalEnum.INTERVAL_1d,
                "3d": MarkPriceKlineCandlestickDataIntervalEnum.INTERVAL_3d,
                "1w": MarkPriceKlineCandlestickDataIntervalEnum.INTERVAL_1w,
                "1M": MarkPriceKlineCandlestickDataIntervalEnum.INTERVAL_1M,
            }
            
            interval_enum = interval_map.get(interval)
            if not interval_enum:
                raise ValueError(f"Invalid interval: {interval}")
            
            response = self.client.rest_api.mark_price_kline_candlestick_data(
                symbol=symbol.upper(),
                interval=interval_enum.value,
                limit=limit
            )
            
            data = response.data()
            
            # Convert to Candle objects
            candles = []
            for kline in data:
                candle = Candle(
                    timestamp=kline[0],  # Open time
                    open=float(kline[1]),
                    high=float(kline[2]),
                    low=float(kline[3]),
                    close=float(kline[4]),
                    volume=float(kline[5]),
                )
                candles.append(candle)
            
            logger.info(f"Fetched {len(candles)} candles for {symbol} {interval}")
            return candles
            
        except Exception as e:
            logger.error(f"Failed to get klines for {symbol}: {e}")
            raise
    
    def get_account_info(self) -> Dict[str, Any]:
        """
        Lấy thông tin tài khoản
        
        Returns:
            Dict với account information
        """
        try:
            response = self.client.rest_api.account_information_v2()
            data = response.data()
            
            logger.info(f"Account balance: ${data.get('totalWalletBalance', 0)}")
            return data
            
        except Exception as e:
            logger.error(f"Failed to get account info: {e}")
            raise
    
    def get_balance(self, asset: str = "USDT") -> float:
        """
        Lấy số dư của asset cụ thể
        
        Args:
            asset: Asset (VD: USDT, BTC)
        
        Returns:
            Số dư available
        """
        try:
            account_info = self.get_account_info()
            
            for balance in account_info.get("assets", []):
                if balance.get("asset") == asset:
                    return float(balance.get("availableBalance", 0))
            
            return 0.0
            
        except Exception as e:
            logger.error(f"Failed to get balance for {asset}: {e}")
            raise
    
    def place_market_order(
        self,
        symbol: str,
        side: str,
        quantity: float
    ) -> Dict[str, Any]:
        """
        Đặt lệnh Market
        
        Args:
            symbol: Cặp giao dịch
            side: BUY hoặc SELL
            quantity: Số lượng
        
        Returns:
            Order response
        """
        try:
            response = self.client.rest_api.new_order(
                symbol=symbol.upper(),
                side=side.upper(),
                type="MARKET",
                quantity=quantity
            )
            
            data = response.data()
            logger.info(f"Market order placed: {side} {quantity} {symbol}")
            return data
            
        except Exception as e:
            logger.error(f"Failed to place market order: {e}")
            raise
    
    def place_limit_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float
    ) -> Dict[str, Any]:
        """
        Đặt lệnh Limit
        
        Args:
            symbol: Cặp giao dịch
            side: BUY hoặc SELL
            quantity: Số lượng
            price: Giá limit
        
        Returns:
            Order response
        """
        try:
            response = self.client.rest_api.new_order(
                symbol=symbol.upper(),
                side=side.upper(),
                type="LIMIT",
                quantity=quantity,
                price=price,
                time_in_force="GTC"  # Good Till Cancel
            )
            
            data = response.data()
            logger.info(f"Limit order placed: {side} {quantity} {symbol} @ ${price}")
            return data
            
        except Exception as e:
            logger.error(f"Failed to place limit order: {e}")
            raise
    
    def cancel_order(self, symbol: str, order_id: int) -> bool:
        """
        Hủy order
        
        Args:
            symbol: Cặp giao dịch
            order_id: Order ID
        
        Returns:
            True nếu hủy thành công
        """
        try:
            response = self.client.rest_api.cancel_order(
                symbol=symbol.upper(),
                order_id=order_id
            )
            
            logger.info(f"Order {order_id} cancelled")
            return True
            
        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            return False
    
    def set_leverage(self, symbol: str, leverage: int) -> bool:
        """
        Đặt đòn bẩy cho symbol
        
        Args:
            symbol: Cặp giao dịch
            leverage: Đòn bẩy (1-125)
        
        Returns:
            True nếu thành công
        """
        try:
            response = self.client.rest_api.change_initial_leverage(
                symbol=symbol.upper(),
                leverage=leverage
            )
            
            logger.info(f"Leverage set to {leverage}x for {symbol}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to set leverage: {e}")
            return False
