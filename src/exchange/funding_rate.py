import requests
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class FundingRateClient:
    """Client for fetching funding rate data from Binance Futures API"""
    
    BASE_URL = "https://fapi.binance.com"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json'
        })
    
    def get_funding_rate(self, symbol: str, limit: int = 10) -> Optional[List[Dict]]:
        """
        Get funding rate history for a symbol
        
        Args:
            symbol: Trading pair symbol (e.g., 'BTCUSDT')
            limit: Number of records to fetch (default: 10, max: 1000)
        
        Returns:
            List of funding rate records or None if request fails
        """
        endpoint = f"{self.BASE_URL}/fapi/v1/fundingRate"
        
        params = {
            'symbol': symbol,
            'limit': limit
        }
        
        try:
            logger.info(f"Fetching funding rate for {symbol}, limit={limit}")
            response = self.session.get(endpoint, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            logger.info(f"Successfully fetched {len(data)} funding rate records")
            return data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching funding rate: {e}")
            return None
    
    def get_latest_funding_rate(self, symbol: str) -> Optional[Dict]:
        """
        Get the latest funding rate for a symbol
        
        Args:
            symbol: Trading pair symbol (e.g., 'BTCUSDT')
        
        Returns:
            Latest funding rate record or None if request fails
        """
        data = self.get_funding_rate(symbol, limit=1)
        if data and len(data) > 0:
            return data[0]
        return None
