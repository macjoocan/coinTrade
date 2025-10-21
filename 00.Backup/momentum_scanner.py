# momentum_scanner.py
import pyupbit
import pandas as pd
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class MomentumScanner:
    """상승 모멘텀 코인 스캐너"""
    
    def __init__(self):
        self.min_volume = 100_000_000  # 최소 거래량 10억
        self.max_volatility = 0.05  # 최대 변동성 5%
        
    def scan_top_performers(self, top_n=3):
        """24시간 상승률 상위 코인 검색"""
        
        try:
            # 원화 마켓 전체 티커
            tickers = pyupbit.get_tickers(fiat="KRW")
            
            # 제외할 코인 (스테이블, 위험 코인)
            exclude_list = ['KRW-USDT', 'KRW-USDC', 'KRW-BUSD', 'KRW-DAI']
            
            candidates = []
            
            for ticker in tickers[:50]:  # 상위 50개만 체크 (API 제한)
                if ticker in exclude_list:
                    continue
                    
                try:
                    # 24시간 데이터
                    df = pyupbit.get_ohlcv(ticker, interval="day", count=2)
                    
                    if df is not None and len(df) >= 2:
                        # 변동률 계산
                        change_24h = ((df['close'].iloc[-1] - df['close'].iloc[-2]) / 
                                     df['close'].iloc[-2] * 100)
                        
                        # 거래량 체크
                        volume_krw = df['close'].iloc[-1] * df['volume'].iloc[-1]
                        
                        # 변동성 체크 (고/저 차이)
                        volatility = (df['high'].iloc[-1] - df['low'].iloc[-1]) / df['close'].iloc[-1]
                        
                        if volume_krw > self.min_volume and volatility < self.max_volatility:
                            candidates.append({
                                'symbol': ticker.replace('KRW-', ''),
                                'change_24h': change_24h,
                                'volume': volume_krw,
                                'volatility': volatility,
                                'score': self.calculate_momentum_score(df)
                            })
                    
                except:
                    continue
            
            # 상승률 + 모멘텀 점수로 정렬
            candidates.sort(key=lambda x: (x['change_24h'] + x['score']), reverse=True)
            
            # 상위 N개 선택
            selected = []
            for coin in candidates[:top_n]:
                if coin['change_24h'] > 3 and coin['score'] > 5:  # 최소 기준
                    selected.append(coin['symbol'])
                    logger.info(f"모멘텀 코인 선택: {coin['symbol']} "
                              f"(24h: {coin['change_24h']:.1f}%, Score: {coin['score']:.1f})")
            
            return selected
            
        except Exception as e:
            logger.error(f"모멘텀 스캔 실패: {e}")
            return []
    
    def calculate_momentum_score(self, df):
        """모멘텀 점수 계산"""
        score = 0
        
        # 1. 연속 상승 체크
        if len(df) >= 3:
            if df['close'].iloc[-1] > df['close'].iloc[-2] > df['close'].iloc[-3]:
                score += 2  # 3일 연속 상승
        
        # 2. 거래량 증가
        if df['volume'].iloc[-1] > df['volume'].iloc[-2] * 1.5:
            score += 2  # 거래량 50% 증가
        
        # 3. 상승 강도
        if df['close'].iloc[-1] > df['open'].iloc[-1]:
            body_ratio = (df['close'].iloc[-1] - df['open'].iloc[-1]) / df['open'].iloc[-1]
            score += min(body_ratio * 100, 3)  # 최대 3점
        
        return score