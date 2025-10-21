# adaptive_preset_manager.py - 자동 프리셋 전환 시스템

import pyupbit
import numpy as np
from datetime import datetime, timedelta
import logging
from collections import deque

logger = logging.getLogger(__name__)

class AdaptivePresetManager:
    """시장 상황에 따라 자동으로 프리셋 전환"""
    
    def __init__(self, config):
        self.config = config
        self.current_preset = 'balanced'  # 기본값
        self.last_switch_time = datetime.now()
        self.min_switch_interval = 3600 * 6  # 최소 6시간 간격
        
        # 히스토리 추적
        self.volatility_history = deque(maxlen=24)  # 24시간
        self.trade_history = deque(maxlen=50)  # 최근 50개 거래
        
        # 임계값 설정
        self.thresholds = {
            'high_volatility': 0.04,      # 4% 이상
            'medium_volatility': 0.02,    # 2-4%
            'low_volatility': 0.02,       # 2% 이하
            
            'high_win_rate': 0.65,        # 65% 이상
            'medium_win_rate': 0.50,      # 50-65%
            'low_win_rate': 0.50,         # 50% 이하
            
            'consecutive_losses': 3,      # 연속 손실
            'consecutive_wins': 3,        # 연속 수익
        }
    
    def analyze_market_condition(self, trading_pairs):
        """시장 상황 종합 분석"""
        
        # 1. 변동성 분석
        volatility = self._calculate_market_volatility(trading_pairs)
        
        # 2. 추세 강도 분석
        trend_strength = self._calculate_trend_strength(trading_pairs)
        
        # 3. 거래량 분석
        volume_trend = self._analyze_volume_trend(trading_pairs)
        
        # 4. 승률 분석
        win_rate = self._calculate_recent_win_rate()
        
        # 5. 연속 손익 분석
        consecutive_result = self._analyze_consecutive_results()
        
        return {
            'volatility': volatility,
            'volatility_level': self._categorize_volatility(volatility),
            'trend_strength': trend_strength,
            'volume_trend': volume_trend,
            'win_rate': win_rate,
            'consecutive_result': consecutive_result,
        }
    
    def _calculate_market_volatility(self, trading_pairs):
        """시장 전체 변동성 계산"""
        volatilities = []
        
        for symbol in trading_pairs[:5]:  # 상위 5개
            ticker = f"KRW-{symbol}"
            try:
                df = pyupbit.get_ohlcv(ticker, interval="minute60", count=24)
                if df is not None and len(df) >= 24:
                    # ATR 기반 변동성
                    high_low = df['high'] - df['low']
                    high_close = np.abs(df['high'] - df['close'].shift())
                    low_close = np.abs(df['low'] - df['close'].shift())
                    
                    ranges = np.column_stack([high_low, high_close, low_close])
                    true_range = np.max(ranges, axis=1)
                    atr = np.mean(true_range[1:])
                    
                    volatility = atr / df['close'].iloc[-1]
                    volatilities.append(volatility)
            except:
                continue
        
        if volatilities:
            avg_volatility = np.mean(volatilities)
            self.volatility_history.append(avg_volatility)
            return avg_volatility
        
        return 0.02  # 기본값
    
    def _categorize_volatility(self, volatility):
        """변동성 수준 분류"""
        if volatility >= self.thresholds['high_volatility']:
            return 'high'
        elif volatility >= self.thresholds['medium_volatility']:
            return 'medium'
        else:
            return 'low'
    
    def _calculate_trend_strength(self, trading_pairs):
        """추세 강도 계산 (0~1)"""
        trend_scores = []
        
        for symbol in trading_pairs[:5]:
            ticker = f"KRW-{symbol}"
            try:
                df = pyupbit.get_ohlcv(ticker, interval="day", count=7)
                if df is not None and len(df) >= 7:
                    # 최근 7일 방향성
                    price_changes = df['close'].diff().dropna()
                    
                    if len(price_changes) > 0:
                        positive_days = (price_changes > 0).sum()
                        consistency = positive_days / len(price_changes)
                        
                        # 0.5 기준으로 강도 계산
                        strength = abs(consistency - 0.5) * 2
                        trend_scores.append(strength)
            except:
                continue
        
        if trend_scores:
            return np.mean(trend_scores)
        
        return 0.3  # 기본값
    
    def _analyze_volume_trend(self, trading_pairs):
        """거래량 추세 분석"""
        volume_increases = 0
        total_checked = 0
        
        for symbol in trading_pairs[:5]:
            ticker = f"KRW-{symbol}"
            try:
                df = pyupbit.get_ohlcv(ticker, interval="day", count=3)
                if df is not None and len(df) >= 3:
                    total_checked += 1
                    
                    recent_volume = df['volume'].iloc[-1]
                    avg_volume = df['volume'].iloc[:-1].mean()
                    
                    if recent_volume > avg_volume * 1.2:
                        volume_increases += 1
            except:
                continue
        
        if total_checked > 0:
            return volume_increases / total_checked
        
        return 0.5  # 기본값
    
    def _calculate_recent_win_rate(self):
        """최근 승률 계산"""
        if len(self.trade_history) < 5:
            return 0.5  # 데이터 부족
        
        wins = sum(1 for trade in self.trade_history if trade['pnl'] > 0)
        return wins / len(self.trade_history)
    
    def _analyze_consecutive_results(self):
        """연속 손익 분석"""
        if len(self.trade_history) < 2:
            return {'type': 'neutral', 'count': 0}
        
        consecutive = 0
        last_result = None
        
        for trade in reversed(list(self.trade_history)):
            current_result = 'win' if trade['pnl'] > 0 else 'loss'
            
            if last_result is None:
                last_result = current_result
                consecutive = 1
            elif current_result == last_result:
                consecutive += 1
            else:
                break
        
        return {
            'type': last_result or 'neutral',
            'count': consecutive
        }
    
    def recommend_preset(self, market_analysis):
        """시장 분석 결과에 따라 프리셋 추천"""
        
        score = 0
        reasons = []
        
        # 1. 변동성 평가
        if market_analysis['volatility_level'] == 'high':
            score -= 2
            reasons.append("고변동성 감지 (-2)")
        elif market_analysis['volatility_level'] == 'low':
            score += 1
            reasons.append("안정적 변동성 (+1)")
        
        # 2. 추세 강도 평가
        if market_analysis['trend_strength'] > 0.7:
            score += 2
            reasons.append("강한 추세 (+2)")
        elif market_analysis['trend_strength'] < 0.3:
            score -= 1
            reasons.append("약한 추세 (-1)")
        
        # 3. 거래량 평가
        if market_analysis['volume_trend'] > 0.6:
            score += 1
            reasons.append("거래량 증가 (+1)")
        
        # 4. 승률 평가
        win_rate = market_analysis['win_rate']
        if win_rate >= self.thresholds['high_win_rate']:
            score += 2
            reasons.append(f"높은 승률 {win_rate:.1%} (+2)")
        elif win_rate <= self.thresholds['low_win_rate']:
            score -= 2
            reasons.append(f"낮은 승률 {win_rate:.1%} (-2)")
        
        # 5. 연속 손익 평가
        consecutive = market_analysis['consecutive_result']
        if consecutive['type'] == 'loss' and consecutive['count'] >= self.thresholds['consecutive_losses']:
            score -= 3
            reasons.append(f"연속 {consecutive['count']}회 손실 (-3)")
        elif consecutive['type'] == 'win' and consecutive['count'] >= self.thresholds['consecutive_wins']:
            score += 2
            reasons.append(f"연속 {consecutive['count']}회 수익 (+2)")
        
        # 6. 점수에 따른 프리셋 결정
        if score >= 3:
            recommended = 'aggressive'
        elif score <= -3:
            recommended = 'conservative'
        else:
            recommended = 'balanced'
        
        logger.info(f"\n{'='*60}")
        logger.info(f"🎯 프리셋 추천 분석")
        logger.info(f"{'='*60}")
        logger.info(f"변동성: {market_analysis['volatility']:.1%} ({market_analysis['volatility_level']})")
        logger.info(f"추세 강도: {market_analysis['trend_strength']:.1%}")
        logger.info(f"거래량 추세: {market_analysis['volume_trend']:.1%}")
        logger.info(f"승률: {market_analysis['win_rate']:.1%}")
        logger.info(f"연속 결과: {consecutive['type']} {consecutive['count']}회")
        logger.info(f"\n평가 내역:")
        for reason in reasons:
            logger.info(f"  • {reason}")
        logger.info(f"\n총점: {score:+d}")
        logger.info(f"추천 프리셋: {recommended.upper()}")
        logger.info(f"{'='*60}\n")
        
        return {
            'recommended_preset': recommended,
            'score': score,
            'reasons': reasons,
            'confidence': min(abs(score) / 5, 1.0)  # 0~1
        }
    
    def can_switch_preset(self):
        """프리셋 전환 가능 여부 (시간 제한)"""
        elapsed = (datetime.now() - self.last_switch_time).total_seconds()
        return elapsed >= self.min_switch_interval
    
    def switch_preset(self, new_preset, force=False):
        """프리셋 전환"""
        if not force and not self.can_switch_preset():
            time_left = self.min_switch_interval - (datetime.now() - self.last_switch_time).total_seconds()
            logger.warning(f"프리셋 전환 쿨다운: {time_left/3600:.1f}시간 남음")
            return False
        
        if new_preset != self.current_preset:
            logger.info(f"\n{'='*60}")
            logger.info(f"🔄 프리셋 전환: {self.current_preset.upper()} → {new_preset.upper()}")
            logger.info(f"{'='*60}\n")
            
            self.current_preset = new_preset
            self.last_switch_time = datetime.now()
            
            # config.py의 ACTIVE_PRESET 업데이트 (런타임)
            try:
                from config import ACTIVE_PRESET
                import config
                config.ACTIVE_PRESET = new_preset
                
                # 프리셋 재적용
                from config import apply_preset
                apply_preset(new_preset)
                
                return True
            except Exception as e:
                logger.error(f"프리셋 적용 실패: {e}")
                return False
        
        return False
    
    def record_trade(self, trade_data):
        """거래 기록 (승률 계산용)"""
        self.trade_history.append({
            'timestamp': datetime.now(),
            'symbol': trade_data.get('symbol'),
            'pnl': trade_data.get('pnl', 0),
            'pnl_rate': trade_data.get('pnl_rate', 0)
        })
    
    def auto_adjust_preset(self, trading_pairs):
        """자동 프리셋 조정 (메인 함수)"""
        
        # 시장 분석
        market_analysis = self.analyze_market_condition(trading_pairs)
        
        # 프리셋 추천
        recommendation = self.recommend_preset(market_analysis)
        
        # 신뢰도가 높고 전환 가능하면 자동 전환
        if recommendation['confidence'] >= 0.6:
            if self.can_switch_preset():
                self.switch_preset(recommendation['recommended_preset'])
            else:
                logger.info(f"프리셋 추천: {recommendation['recommended_preset'].upper()} "
                          f"(신뢰도: {recommendation['confidence']:.0%})")
                logger.info("다음 전환 가능 시간까지 대기 중...")
        else:
            logger.info(f"현재 프리셋 유지: {self.current_preset.upper()} "
                       f"(추천 신뢰도 부족: {recommendation['confidence']:.0%})")
        
        return recommendation


# ==========================================
# 사용 예시
# ==========================================
if __name__ == "__main__":
    from config import TRADING_PAIRS
    
    print("🤖 자동 프리셋 전환 시스템 테스트\n")
    
    # 매니저 초기화
    manager = AdaptivePresetManager(config={})
    
    # 시장 분석 및 프리셋 추천
    recommendation = manager.auto_adjust_preset(TRADING_PAIRS)
    
    print(f"\n추천 프리셋: {recommendation['recommended_preset']}")
    print(f"신뢰도: {recommendation['confidence']:.0%}")
    print(f"점수: {recommendation['score']}")