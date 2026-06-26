import os
import logging
from typing import List, Dict, Optional

from binance_sdk_derivatives_trading_usds_futures.derivatives_trading_usds_futures import (
    DerivativesTradingUsdsFutures,
    ConfigurationRestAPI,
    DERIVATIVES_TRADING_USDS_FUTURES_REST_API_PROD_URL,
)

logger = logging.getLogger(__name__)


class RecentTradesClient:
    """Client for fetching recent trades data from Binance Futures API"""
    
    def __init__(self, api_key: str = "", api_secret: str = "", base_path: str = ""):
        """
        Initialize the RecentTradesClient
        
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
    
    def get_recent_trades(self, symbol: str, limit: int = 500) -> Optional[List[Dict]]:
        """
        Get recent trades list for a symbol
        
        Args:
            symbol: Trading pair symbol (e.g., 'BTCUSDT')
            limit: Number of records to fetch (default: 500, max: 1000)
        
        Returns:
            List of recent trades records or None if request fails
        """
        try:
            logger.info(f"Fetching recent trades for {symbol}, limit={limit}")
            response = self.client.rest_api.recent_trades_list(
                symbol=symbol,
                limit=limit,
            )
            
            rate_limits = response.rate_limits
            logger.info(f"get_recent_trades() rate limits: {rate_limits}")
            
            data = response.data()
            logger.info(f"Successfully fetched {len(data) if data else 0} recent trades records")
            return data
            
        except Exception as e:
            logger.error(f"Error fetching recent trades: {e}")
            return None
    
    def get_latest_trade(self, symbol: str) -> Optional[Dict]:
        """
        Get the latest trade for a symbol
        
        Args:
            symbol: Trading pair symbol (e.g., 'BTCUSDT')
        
        Returns:
            Latest trade record or None if request fails
        """
        data = self.get_recent_trades(symbol, limit=1)
        if data and len(data) > 0:
            return data[0]
        return None