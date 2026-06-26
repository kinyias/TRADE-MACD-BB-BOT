import os
import logging

from binance_sdk_derivatives_trading_usds_futures.derivatives_trading_usds_futures import (
    DerivativesTradingUsdsFutures,
    ConfigurationRestAPI,
    DERIVATIVES_TRADING_USDS_FUTURES_REST_API_PROD_URL,
)


# Configure logging
logging.basicConfig(level=logging.INFO)

# Create configuration for the REST API
configuration_rest_api = ConfigurationRestAPI(
    api_key=os.getenv("API_KEY", ""),
    api_secret=os.getenv("API_SECRET", ""),
    base_path=os.getenv(
        "BASE_PATH", DERIVATIVES_TRADING_USDS_FUTURES_REST_API_PROD_URL
    ),
)

# Initialize DerivativesTradingUsdsFutures client
client = DerivativesTradingUsdsFutures(config_rest_api=configuration_rest_api)


def order_book(symbol="SOLUSDC", limit=100):
    """
    Get order book data for a symbol
    
    Args:
        symbol (str): Trading pair symbol (e.g., "SOLUSDC", "BTCUSDT")
        limit (int): Order book depth limit (default: 100)
    
    Returns:
        dict: Order book data or None if error occurs
    """
    try:
        response = client.rest_api.order_book(
            symbol=symbol,
            limit=limit
        )

        rate_limits = response.rate_limits
        logging.info(f"order_book() rate limits: {rate_limits}")

        data = response.data()
        logging.info(f"order_book() response: {data}")
        
        # Convert Pydantic model to dictionary for JSON serialization
        if hasattr(data, 'dict'):
            return data.dict()
        elif hasattr(data, 'model_dump'):
            return data.model_dump()
        else:
            # Fallback: manually convert bids and asks
            return {
                "bids": [[bid.root[0], bid.root[1]] for bid in data.bids],
                "asks": [[ask.root[0], ask.root[1]] for ask in data.asks]
            }
    except Exception as e:
        logging.error(f"order_book() error: {e}")
        return None


if __name__ == "__main__":
    order_book()