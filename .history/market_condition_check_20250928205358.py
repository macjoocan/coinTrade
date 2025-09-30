# market_condition_check.py

import pyupbit
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class MarketAnalyzer:
    def __init__(self):
        self._market_condition = 'neutral'
        self._market_condition_time = datetime.now()
        self._cache_duration = 1800  # 30분
    
    def analyze_market(self, trading_pairs):
        """시장 상황 분석"""
        
        # 캐시 확인
        now = datetime.now()
        if hasattr(self, '_market_condition_time'):
            if (now - self._market_condition_time).seconds < self._cache_duration:
                return self._market_condition
        
        coins = trading_pairs[:3]  # 상위 3개만
        market_signals = {'bullish': 0, 'bearish': 0, 'neutral': 0}
        
        for coin in coins:
            ticker = f"KRW-{coin}"
            try:
                df = pyupbit.get_ohlcv(ticker, interval="day", count=3)
                if df is not None and len(df) >= 3:
                    change = ((df['close'].iloc[-1] - df['close'].iloc[0]) 
                             / df['close'].iloc[0] * 100)
                    
                    if change > 3:
                        market_signals['bullish'] += 1
                    elif change < -3:
                        market_signals['bearish'] += 1
                    else:
                        market_signals['neutral'] += 1
            except:
                market_signals['neutral'] += 1
        
        # 판단
        if market_signals['bearish'] >= 2:
            self._market_condition = 'bearish'
        elif market_signals['bullish'] >= 2:
            self._market_condition = 'bullish'
        else:
            self._market_condition = 'neutral'
        
        self._market_condition_time = now
        
        logger.info(f"시장 상황 업데이트: {self._market_condition}")
        return self._market_condition
    
    def get_score_adjustment(self, base_score):
        """시장 상황에 따른 점수 조정"""
        if self._market_condition == 'bullish':
            return base_score - 0.5  # 진입 기준 완화
        elif self._market_condition == 'bearish':
            return base_score + 1.0  # 진입 기준 강화
        return base_score
    
    def get_position_size_multiplier(self):
        """시장 상황에 따른 포지션 크기 배수"""
        if self._market_condition == 'bearish':
            return 0.7  # 30% 축소
        elif self._market_condition == 'bullish':
            return 1.1  # 10% 증가
        return 1.0