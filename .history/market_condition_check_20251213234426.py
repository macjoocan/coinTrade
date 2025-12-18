# market_condition_check.py - 전체 교체 추천

import pyupbit
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class MarketAnalyzer:
    def __init__(self):
        self._market_condition = 'neutral'
        self._market_condition_time = None
        # ⚠️ 캐시 시간을 30분 -> 5분으로 대폭 단축
        self._cache_duration = 300  
    
    def analyze_market(self, trading_pairs):
        """시장 상황 분석 (단기 추세 반영 버전)"""
        
        now = datetime.now()
        # 캐시 확인
        if self._market_condition_time:
            elapsed = (now - self._market_condition_time).total_seconds()
            if elapsed < self._cache_duration:
                return self._market_condition
        
        coins = trading_pairs[:3]  # BTC, ETH, SOL 등 대장주
        market_scores = []
        
        for coin in coins:
            ticker = f"KRW-{coin}"
            try:
                # ⚠️ 핵심 변경: 'day'(일봉) -> 'minute240'(4시간봉)으로 변경
                # 최근 24시간(4시간봉 6개) 데이터를 봅니다.
                df = pyupbit.get_ohlcv(ticker, interval="minute240", count=7)
                
                if df is not None and len(df) >= 6:
                    # 1. 단기 추세 (현재가 vs 24시간 전 가격)
                    price_change = ((df['close'].iloc[-1] - df['close'].iloc[-6]) 
                                   / df['close'].iloc[-6] * 100)
                    
                    # 2. 초단기 모멘텀 (현재가 vs 4시간 전 가격)
                    momentum = ((df['close'].iloc[-1] - df['close'].iloc[-2]) 
                               / df['close'].iloc[-2] * 100)
                    
                    # 3. 변동성 확인 (박스권 감지용)
                    high_low_diff = (df['high'].max() - df['low'].min()) / df['low'].min()
                    
                    score = 0
                    # 추세 점수
                    if price_change > 1.0: score += 1
                    elif price_change < -1.0: score -= 1
                    
                    # 모멘텀 점수 (가중치 높음)
                    if momentum > 0.5: score += 1
                    elif momentum < -0.5: score -= 1
                    
                    market_scores.append(score)
                    
            except Exception as e:
                logger.error(f"시장 분석 실패 ({coin}): {e}")
                continue
        
        # 종합 판단
        total_score = sum(market_scores)
        
        if total_score >= 2:
            self._market_condition = 'bullish' # 상승장
        elif total_score <= -2:
            self._market_condition = 'bearish' # 하락장
        else:
            self._market_condition = 'neutral' # 횡보/박스권
            
        self._market_condition_time = now
        logger.info(f"⚡ 시장 상황 갱신 (4시간 기준): {self._market_condition} (점수: {total_score})")
        
        return self._market_condition

    def get_score_adjustment(self, base_score):
        if self._market_condition == 'bullish':
            return base_score - 0.5
        elif self._market_condition == 'bearish':
            return base_score + 1.5  # 하락장에서는 더 보수적으로
        return base_score

    def get_position_size_multiplier(self):
        # 횡보장(neutral)일 때도 적극적으로 단타를 치도록 1.0 유지
        if self._market_condition == 'bearish':
            return 0.5
        elif self._market_condition == 'bullish':
            return 1.2
        return 1.0