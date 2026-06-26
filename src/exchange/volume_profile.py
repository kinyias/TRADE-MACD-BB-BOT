import numpy as np
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass


@dataclass
class VolumeProfileResult:
    """Result of volume profile analysis"""
    poc: float  # Point of Control (price level with highest volume)
    value_area_high: float  # Upper boundary of value area
    value_area_low: float  # Lower boundary of value area
    volume_by_price: Dict[float, float]  # Volume distribution by price level
    total_volume: float
    value_area_volume_percent: float


class VolumeProfileAnalyzer:
    """
    Volume Profile Analyzer
    Analyzes volume distribution across price levels to identify:
    - Point of Control (POC): Price level with highest volume
    - Value Area: Price range where specified percentage of volume occurred
    """
    
    def __init__(self, num_bins: int = 24, value_area_percent: float = 0.70):
        """
        Initialize Volume Profile Analyzer
        
        Args:
            num_bins: Number of price bins for volume distribution
            value_area_percent: Percentage of volume for value area (default 70%)
        """
        self.num_bins = num_bins
        self.value_area_percent = value_area_percent
    
    def analyze(
        self,
        highs: List[float],
        lows: List[float],
        closes: List[float],
        volumes: List[float]
    ) -> Optional[VolumeProfileResult]:
        """
        Analyze volume profile from candle data
        
        Args:
            highs: List of high prices
            lows: List of low prices
            closes: List of close prices
            volumes: List of volumes
            
        Returns:
            VolumeProfileResult or None if insufficient data
        """
        if not highs or len(highs) < 2:
            return None
        
        if len(highs) != len(lows) != len(closes) != len(volumes):
            return None
        
        # Find price range
        min_price = min(lows)
        max_price = max(highs)
        price_range = max_price - min_price
        
        if price_range == 0:
            return None
        
        # Create price bins
        bin_size = price_range / self.num_bins
        price_bins = [min_price + i * bin_size for i in range(self.num_bins + 1)]
        
        # Initialize volume for each bin
        volume_profile = {price_bins[i]: 0.0 for i in range(self.num_bins)}
        
        # Distribute volume across price levels
        for i in range(len(highs)):
            high = highs[i]
            low = lows[i]
            volume = volumes[i]
            
            # Find which bins this candle touches
            start_bin = int((low - min_price) / bin_size)
            end_bin = int((high - min_price) / bin_size)
            
            # Clamp to valid range
            start_bin = max(0, min(start_bin, self.num_bins - 1))
            end_bin = max(0, min(end_bin, self.num_bins - 1))
            
            # Distribute volume across touched bins
            num_bins_touched = end_bin - start_bin + 1
            volume_per_bin = volume / num_bins_touched
            
            for bin_idx in range(start_bin, end_bin + 1):
                volume_profile[price_bins[bin_idx]] += volume_per_bin
        
        # Find Point of Control (POC) - price level with highest volume
        poc_price = max(volume_profile.keys(), key=lambda k: volume_profile[k])
        
        # Calculate Value Area
        total_volume = sum(volume_profile.values())
        target_volume = total_volume * self.value_area_percent
        
        # Sort price levels by volume (descending)
        sorted_prices = sorted(volume_profile.keys(), key=lambda k: volume_profile[k], reverse=True)
        
        # Build value area by adding highest volume levels
        value_area_prices = []
        accumulated_volume = 0.0
        
        for price in sorted_prices:
            value_area_prices.append(price)
            accumulated_volume += volume_profile[price]
            if accumulated_volume >= target_volume:
                break
        
        # Value area boundaries
        value_area_high = max(value_area_prices)
        value_area_low = min(value_area_prices)
        
        return VolumeProfileResult(
            poc=poc_price,
            value_area_high=value_area_high,
            value_area_low=value_area_low,
            volume_by_price=volume_profile,
            total_volume=total_volume,
            value_area_volume_percent=(accumulated_volume / total_volume * 100) if total_volume > 0 else 0
        )
    
    def get_support_resistance_levels(
        self,
        result: VolumeProfileResult,
        threshold_percent: float = 0.8
    ) -> Dict[str, List[float]]:
        """
        Extract significant support/resistance levels from volume profile
        
        Args:
            result: VolumeProfileResult from analyze()
            threshold_percent: Minimum volume percentage to consider as significant level
            
        Returns:
            Dict with 'support' and 'resistance' lists
        """
        if not result:
            return {"support": [], "resistance": []}
        
        # Find high volume nodes (HVN)
        max_volume = max(result.volume_by_price.values())
        threshold = max_volume * threshold_percent
        
        high_volume_prices = [
            price for price, volume in result.volume_by_price.items()
            if volume >= threshold
        ]
        
        # Sort by price
        high_volume_prices.sort()
        
        return {
            "poc": result.poc,
            "value_area_high": result.value_area_high,
            "value_area_low": result.value_area_low,
            "high_volume_nodes": high_volume_prices
        }
