"""
Market Analyzer - Tích hợp tất cả dữ liệu thị trường và phân tích bằng AI
"""
import os
import logging
import requests
from typing import Optional, List, Dict
from datetime import datetime

# Import các module có sẵn
from src.exchange.order_book import order_book
from src.exchange.volume_profile import VolumeProfileAnalyzer
from src.exchange.recent_trades_list import RecentTradesClient
from src.exchange.taker_buy_sell_volume import TakerBuySellVolumeClient
from src.exchange.funding_rate import FundingRateClient
from src.indicator.ai import analyze_market_with_ai
from src.config.settings import SYMBOL, TIMEFRAME

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class MarketAnalyzer:
    """
    Lớp tích hợp để thu thập dữ liệu từ nhiều nguồn và phân tích bằng AI
    """
    
    def __init__(self, symbol: str = SYMBOL, timeframe: str = TIMEFRAME):
        """
        Khởi tạo Market Analyzer
        
        Args:
            symbol: Cặp giao dịch (VD: SOLUSDC, BTCUSDT)
            timeframe: Khung thời gian (VD: 1m, 5m, 1h)
        """
        self.symbol = symbol
        self.timeframe = timeframe
        
        # Khởi tạo các client
        self.recent_trades_client = RecentTradesClient()
        self.taker_volume_client = TakerBuySellVolumeClient()
        self.funding_rate_client = FundingRateClient()
        self.volume_profile_analyzer = VolumeProfileAnalyzer(num_bins=24, value_area_percent=0.70)
        
        logger.info(f"MarketAnalyzer initialized for {symbol} on {timeframe}")
    
    def get_klines_data(self, limit: int = 100) -> Optional[List[List]]:
        """
        Lấy dữ liệu nến từ Binance API
        
        Args:
            limit: Số nến cần lấy (max: 1500)
            
        Returns:
            List các nến hoặc None nếu lỗi
        """
        try:
            url = "https://fapi.binance.com/fapi/v1/klines"
            params = {
                'symbol': self.symbol,
                'interval': self.timeframe,
                'limit': limit
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            klines = response.json()
            logger.info(f"Fetched {len(klines)} klines for {self.symbol}")
            return klines
            
        except Exception as e:
            logger.error(f"Error fetching klines: {e}")
            return None
    
    def get_current_price(self) -> Optional[float]:
        """
        Lấy giá hiện tại từ klines hoặc recent trades
        
        Returns:
            float: Giá hiện tại hoặc None nếu lỗi
        """
        try:
            klines = self.get_klines_data(limit=1)
            if klines and len(klines) > 0:
                # Close price của nến cuối cùng
                return float(klines[-1][4])
            return None
        except Exception as e:
            logger.error(f"Error getting current price: {e}")
            return None
    
    def collect_all_data(self, klines_limit: int = 100) -> Optional[Dict]:
        """
        Thu thập tất cả dữ liệu cần thiết cho phân tích
        
        Args:
            klines_limit: Số nến cần lấy
            
        Returns:
            Dict chứa tất cả dữ liệu hoặc None nếu lỗi
        """
        try:
            logger.info("Collecting market data from all sources...")
            
            # 1. Lấy dữ liệu nến
            klines = self.get_klines_data(limit=klines_limit)
            if not klines:
                logger.error("Failed to fetch klines data")
                return None
            
            # 2. Lấy order book
            order_book_data = order_book(symbol=self.symbol, limit=100)
            if not order_book_data:
                logger.error("Failed to fetch order book data")
                return None
            
            # 3. Tính volume profile từ klines
            highs = [float(k[2]) for k in klines]
            lows = [float(k[3]) for k in klines]
            closes = [float(k[4]) for k in klines]
            volumes = [float(k[5]) for k in klines]
            
            volume_profile_result = self.volume_profile_analyzer.analyze(
                highs=highs,
                lows=lows,
                closes=closes,
                volumes=volumes
            )
            
            if volume_profile_result:
                volume_profile_data = {
                    'poc': volume_profile_result.poc,
                    'value_area_high': volume_profile_result.value_area_high,
                    'value_area_low': volume_profile_result.value_area_low,
                    'total_volume': volume_profile_result.total_volume,
                    'value_area_volume_percent': volume_profile_result.value_area_volume_percent,
                    'volume_by_price': {str(k): v for k, v in volume_profile_result.volume_by_price.items()}
                }
            else:
                logger.warning("Failed to calculate volume profile")
                volume_profile_data = {}
            
            # 4. Lấy recent trades
            recent_trades_data = self.recent_trades_client.get_recent_trades(
                symbol=self.symbol, 
                limit=100
            )
            if not recent_trades_data:
                logger.warning("Failed to fetch recent trades")
                recent_trades_data = []
            
            # 5. Lấy taker buy/sell volume
            # Convert timeframe to period format (1m -> 5m, 5m -> 5m, 1h -> 1h)
            period_map = {
                '1m': '5m',
                '5m': '5m',
                '15m': '15m',
                '30m': '30m',
                '1h': '1h',
                '4h': '4h'
            }
            period = period_map.get(self.timeframe, '5m')
            
            taker_volume_data = self.taker_volume_client.get_taker_buy_sell_volume(
                symbol=self.symbol,
                period=period,
                limit=30
            )
            if not taker_volume_data:
                logger.warning("Failed to fetch taker volume")
                taker_volume_data = []
            
            # 6. Lấy funding rate
            funding_rate_data = self.funding_rate_client.get_funding_rate(
                symbol=self.symbol,
                limit=10
            )
            if not funding_rate_data:
                logger.warning("Failed to fetch funding rate")
                funding_rate_data = []
            
            # 7. Lấy giá hiện tại
            current_price = float(klines[-1][4]) if klines else 0.0
            
            logger.info("✅ All market data collected successfully")
            
            return {
                'klines': klines,
                'order_book': order_book_data,
                'volume_profile': volume_profile_data,
                'recent_trades': recent_trades_data,
                'taker_volume': taker_volume_data,
                'funding_rate': funding_rate_data,
                'current_price': current_price
            }
            
        except Exception as e:
            logger.error(f"Error collecting market data: {e}")
            return None
    
    def analyze(self, model: str = "openrouter/owl-alpha") -> Optional[str]:
        """
        Thu thập dữ liệu và phân tích bằng AI
        
        Args:
            model: Model AI sử dụng
            
        Returns:
            str: Kết quả phân tích dạng text có format hoặc None nếu lỗi
        """
        try:
            # Thu thập dữ liệu
            data = self.collect_all_data()
            if not data:
                logger.error("Failed to collect market data")
                return None
            
            logger.info("🤖 Analyzing market with AI...")
            
            # Gọi AI phân tích
            analysis_result = analyze_market_with_ai(
                klines_data=data['klines'],
                order_book_data=data['order_book'],
                volume_profile_data=data['volume_profile'],
                recent_trades_data=data['recent_trades'],
                taker_volume_data=data['taker_volume'],
                funding_rate_data=data['funding_rate'],
                current_price=data['current_price'],
                symbol=self.symbol,
                timeframe=self.timeframe,
                model=model
            )
            
            return analysis_result
            
        except Exception as e:
            logger.error(f"Error during analysis: {e}")
            return None


def main():
    """
    Main function để test MarketAnalyzer
    """
    try:
        # Khởi tạo analyzer
        analyzer = MarketAnalyzer(symbol=SYMBOL, timeframe=TIMEFRAME)
        
        print("\n" + "="*70)
        print(f"🚀 BẮT ĐẦU PHÂN TÍCH THỊ TRƯỜNG")
        print(f"📊 Symbol: {SYMBOL}")
        print(f"⏰ Timeframe: {TIMEFRAME}")
        print(f"🕐 Thời gian: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*70 + "\n")
        
        # Phân tích
        result = analyzer.analyze()
        
        if result:
            print(result)
            print("\n" + "="*70)
            print("✅ HOÀN THÀNH PHÂN TÍCH")
            print("="*70 + "\n")
        else:
            print("\n❌ PHÂN TÍCH THẤT BẠI - Vui lòng kiểm tra logs\n")
            
    except Exception as e:
        logger.error(f"Error in main: {e}")
        print(f"\n❌ LỖI: {e}\n")


if __name__ == "__main__":
    main()
