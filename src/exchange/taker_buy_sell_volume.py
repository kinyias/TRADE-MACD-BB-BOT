import os
import logging
from typing import List, Dict, Optional

from binance_sdk_derivatives_trading_usds_futures.derivatives_trading_usds_futures import (
    DerivativesTradingUsdsFutures,
    ConfigurationRestAPI,
    DERIVATIVES_TRADING_USDS_FUTURES_REST_API_PROD_URL,
)
from binance_sdk_derivatives_trading_usds_futures.rest_api.models import (
    TakerBuySellVolumePeriodEnum,
)

logger = logging.getLogger(__name__)


class TakerBuySellVolumeClient:
    """Client for fetching taker buy/sell volume data from Binance Futures API"""
    
    def __init__(self, api_key: str = "", api_secret: str = "", base_path: str = ""):
        """
        Initialize the TakerBuySellVolumeClient
        
        Args:
            api_key: Binance API key (defaults to API_KEY env var)
            api_secret: Binance API secret (defaults to API_SECRET env var)
            base_path: Base path for API (defaults to BASE_PATH env var or production URL)
        """
        configuration_rest_api = ConfigurationRestAPI(
            api_key=api_key or os.getenv("API_KEY", ""),
            api_secret=api_secret or os.getenv("API_SECRET", ""),
            base_path=base_path or os.getenv(
                "BASE_PATH", DERIVATIVES_TRADING_USDS_FUTURES_REST_API_PROD_URL
            ),
        )
        self.client = DerivativesTradingUsdsFutures(config_rest_api=configuration_rest_api)
    
    def get_taker_buy_sell_volume(
        self, 
        symbol: str, 
        period: str = "5m", 
        limit: int = 30,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None
    ) -> Optional[List[Dict]]:
        """
        Get taker buy/sell volume data for a symbol
        
        Args:
            symbol: Trading pair symbol (e.g., 'BTCUSDT')
            period: Time period (5m, 15m, 30m, 1h, 2h, 4h, 6h, 12h, 1d)
            limit: Number of records to fetch (default: 30, max: 500)
            start_time: Start time in milliseconds (optional)
            end_time: End time in milliseconds (optional)
        
        Returns:
            List of taker buy/sell volume records or None if request fails
        """
        try:
            logger.info(f"Fetching taker buy/sell volume for {symbol}, period={period}, limit={limit}")
            
            # Get period enum value
            period_key = f"PERIOD_{period}"
            if period_key not in TakerBuySellVolumePeriodEnum.__members__:
                logger.error(f"Invalid period: {period}. Valid options: 5m, 15m, 30m, 1h, 2h, 4h, 6h, 12h, 1d")
                return None
            
            period_value = TakerBuySellVolumePeriodEnum[period_key].value
            
            # Build request parameters
            kwargs = {
                'symbol': symbol,
                'period': period_value,
                'limit': limit
            }
            if start_time is not None:
                kwargs['start_time'] = start_time
            if end_time is not None:
                kwargs['end_time'] = end_time
            
            response = self.client.rest_api.taker_buy_sell_volume(**kwargs)
            
            rate_limits = response.rate_limits
            logger.info(f"get_taker_buy_sell_volume() rate limits: {rate_limits}")
            
            data = response.data()
            logger.info(f"Successfully fetched {len(data) if data else 0} taker buy/sell volume records")
            return data
            
        except Exception as e:
            logger.error(f"Error fetching taker buy/sell volume: {e}")
            return None
    
    def get_latest_volume(self, symbol: str, period: str = "5m") -> Optional[Dict]:
        """
        Get the latest taker buy/sell volume for a symbol
        
        Args:
            symbol: Trading pair symbol (e.g., 'BTCUSDT')
            period: Time period (5m, 15m, 30m, 1h, 2h, 4h, 6h, 12h, 1d)
        
        Returns:
            Latest taker buy/sell volume record or None if request fails
        """
        data = self.get_taker_buy_sell_volume(symbol, period=period, limit=1)
        if data and len(data) > 0:
            return data[0]
        return None