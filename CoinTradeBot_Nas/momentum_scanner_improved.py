# momentum_scanner_improved.py - 횡보장 대응 버전

import pyupbit
import pandas as pd
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class ImprovedMomentumScanner:
    """개선된 모멘텀 스캐너 - 횡보장 대응"""
    
    def __init__(self):
        # 완화된 기준
        self.min_volume = 300_000_000   # 300억 (기존 500억)
        self.max_volatility = 0.07         # 7% (기존 5%)
        self.min_change_24h = 2.0          # 2% (기존 3%)
        self.min_score = 4.0               # 4점 (기존 5점)
        
        # 캐싱
        self.last_scan_result = []
        self.last_scan_time = None
        self.cache_duration = 1800  # 30분
        
    def scan_top_performers(self, top_n=3):
        """24시간 기준 상위 코인 검색 (완화된 기준)"""
        
        # 캐시 확인
        if self.last_scan_time:
            elapsed = (datetime.now() - self.last_scan_time).total_seconds()
            if elapsed < self.cache_duration:
                logger.info(f"캐시된 결과 사용 (스캔: {elapsed/60:.0f}분 전)")
                return self.last_scan_result
        
        logger.info("="*60)
        logger.info("🔥 모멘텀 코인 스캔 시작")
        logger.info("="*60)
        
        try:
            # 원화 마켓 티커
            tickers = pyupbit.get_tickers(fiat="KRW")
            
            # 제외 리스트
            exclude_list = [
                'KRW-USDT', 'KRW-USDC', 'KRW-BUSD', 'KRW-DAI',  # 스테이블
                'KRW-BTC', 'KRW-ETH', 'KRW-SOL',  # 이미 STABLE_PAIRS에 있음
            ]
            
            candidates = []
            total_checked = 0
            
            logger.info(f"총 {len(tickers[:50])}개 코인 스캔 중...")
            
            for ticker in tickers[:50]:  # 상위 50개
                if ticker in exclude_list:
                    continue
                
                total_checked += 1
                
                try:
                    # 데이터 가져오기
                    df = pyupbit.get_ohlcv(ticker, interval="day", count=3)
                    
                    if df is None or len(df) < 2:
                        continue
                    
                    # 변동률
                    change_24h = ((df['close'].iloc[-1] - df['close'].iloc[-2]) / 
                                 df['close'].iloc[-2] * 100)
                    
                    # 거래량 (KRW)
                    volume_krw = df['close'].iloc[-1] * df['volume'].iloc[-1]
                    
                    # 변동성
                    volatility = (df['high'].iloc[-1] - df['low'].iloc[-1]) / df['close'].iloc[-1]
                    
                    # 모멘텀 점수
                    score = self.calculate_momentum_score(df)
                    
                    # 필터링
                    if (volume_krw > self.min_volume and 
                        volatility < self.max_volatility and
                        change_24h > self.min_change_24h and 
                        score > self.min_score):
                        
                        candidates.append({
                            'symbol': ticker.replace('KRW-', ''),
                            'change_24h': change_24h,
                            'volume': volume_krw,
                            'volatility': volatility,
                            'score': score,
                            'final_score': change_24h + score  # 정렬용
                        })
                
                except Exception as e:
                    logger.debug(f"{ticker} 스캔 실패: {e}")
                    continue
            
            logger.info(f"검사 완료: {total_checked}개 중 {len(candidates)}개 후보")
            
            # 정렬
            candidates.sort(key=lambda x: x['final_score'], reverse=True)
            
            # 상위 N개 선택
            selected = []
            for coin in candidates[:top_n]:
                selected.append(coin['symbol'])
                logger.info(
                    f"✅ 선택: {coin['symbol']} | "
                    f"24h: {coin['change_24h']:+.1f}% | "
                    f"점수: {coin['score']:.1f} | "
                    f"거래량: {coin['volume']/1e9:.0f}억"
                )
            
            if not selected:
                logger.warning("⚠️ 조건을 만족하는 코인이 없습니다")
                logger.info("현재 기준:")
                logger.info(f"  - 최소 변동: {self.min_change_24h}%")
                logger.info(f"  - 최소 점수: {self.min_score}")
                logger.info(f"  - 최소 거래량: {self.min_volume/1e9:.0f}억")
            
            # 캐시 업데이트
            self.last_scan_result = selected
            self.last_scan_time = datetime.now()
            
            logger.info("="*60)
            return selected
            
        except Exception as e:
            logger.error(f"모멘텀 스캔 실패: {e}")
            return []
    
    def calculate_momentum_score(self, df):
        """개선된 모멘텀 점수 계산"""
        score = 0
        
        try:
            # 1. 연속 상승 (최대 3점)
            if len(df) >= 3:
                if df['close'].iloc[-1] > df['close'].iloc[-2]:
                    score += 1
                    if df['close'].iloc[-2] > df['close'].iloc[-3]:
                        score += 2  # 2일 연속 상승
            
            # 2. 거래량 증가 (최대 2점)
            if len(df) >= 2:
                vol_ratio = df['volume'].iloc[-1] / df['volume'].iloc[-2]
                if vol_ratio > 1.5:
                    score += 2
                elif vol_ratio > 1.2:
                    score += 1
            
            # 3. 양봉 강도 (최대 3점)
            if df['close'].iloc[-1] > df['open'].iloc[-1]:
                body_ratio = (df['close'].iloc[-1] - df['open'].iloc[-1]) / df['open'].iloc[-1]
                score += min(body_ratio * 100, 3)
            
            # 4. 고점 갱신 (최대 2점)
            if len(df) >= 5:
                recent_high = df['high'].iloc[-5:].max()
                if df['high'].iloc[-1] >= recent_high:
                    score += 2
            
        except Exception as e:
            logger.debug(f"점수 계산 오류: {e}")
        
        return score
    
    def get_detailed_analysis(self, symbol):
        """특정 코인의 상세 분석"""
        ticker = f"KRW-{symbol}"
        
        try:
            df = pyupbit.get_ohlcv(ticker, interval="day", count=7)
            
            if df is None:
                return None
            
            # 7일 평균 변동률
            avg_change = df['close'].pct_change().mean() * 100
            
            # 7일 평균 거래량
            avg_volume = (df['close'] * df['volume']).mean()
            
            # 최근 추세
            if df['close'].iloc[-1] > df['close'].iloc[-3]:
                trend = "상승"
            elif df['close'].iloc[-1] < df['close'].iloc[-3]:
                trend = "하락"
            else:
                trend = "횡보"
            
            return {
                'symbol': symbol,
                'avg_change_7d': avg_change,
                'avg_volume_7d': avg_volume,
                'trend': trend,
                'current_price': df['close'].iloc[-1]
            }
        
        except Exception as e:
            logger.error(f"{symbol} 상세 분석 실패: {e}")
            return None
    
    def force_refresh(self):
        """캐시 무시하고 강제 갱신"""
        logger.info("🔄 강제 갱신 요청")
        self.last_scan_time = None
        return self.scan_top_performers()

# 테스트 함수
def test_scanner():
    """스캐너 테스트"""
    scanner = ImprovedMomentumScanner()
    
    print("\n" + "="*60)
    print("🧪 개선된 모멘텀 스캐너 테스트")
    print("="*60)
    
    selected = scanner.scan_top_performers(top_n=5)
    
    if selected:
        print(f"\n✅ {len(selected)}개 코인 발견:")
        for symbol in selected:
            detail = scanner.get_detailed_analysis(symbol)
            if detail:
                print(f"\n{symbol}:")
                print(f"  - 7일 평균 변동: {detail['avg_change_7d']:+.2f}%")
                print(f"  - 7일 평균 거래량: {detail['avg_volume_7d']/1e9:.0f}억")
                print(f"  - 추세: {detail['trend']}")
    else:
        print("\n❌ 조건 충족 코인 없음")
    
    print("="*60)

if __name__ == "__main__":
    test_scanner()