# risk_manager.py - 완전한 버전

from datetime import datetime
import pyupbit
from collections import defaultdict
from config import RISK_CONFIG
from config import STABLE_PAIRS
from config import ADVANCED_CONFIG
import logging
import numpy as np
from market_condition_check import MarketAnalyzer

logger = logging.getLogger(__name__)

class RiskManager:
    def __init__(self, initial_balance):
        self.initial_balance = initial_balance
        self.current_balance = initial_balance
        self.max_position_size = RISK_CONFIG['max_position_size']
        self.stop_loss = RISK_CONFIG['stop_loss']
        self.daily_loss_limit = RISK_CONFIG['daily_loss_limit']
        self.max_positions = RISK_CONFIG['max_positions']
        
        # MarketAnalyzer는 선택적으로
        try:
            from market_condition_check import MarketAnalyzer
            self.market_analyzer = MarketAnalyzer()
        except ImportError:
            self.market_analyzer = None
            logger.warning("MarketAnalyzer를 로드할 수 없습니다")
        
        # 일일 손익 추적
        self.daily_pnl = defaultdict(float)
        self.positions = {}
        
        # 리스크 메트릭
        self.consecutive_losses = 0
        self.max_consecutive_losses = ADVANCED_CONFIG.get('max_consecutive_losses', 3)
        self.daily_trades = defaultdict(list)
        
        # 전체 거래 기록 (승률 계산용)
        self.all_trades_history = []
       
        # 디버그 정보
        self.last_calculated_win_rate = 0.5
        self.total_wins = 0
        self.total_losses = 0
        self.total_win_amount = 0.0
        self.total_loss_amount = 0.0
        
        # Kelly Criterion 파라미터
        self.win_rate = 0.5
        self.avg_win_loss_ratio = 1.5

    def should_stop_trading(self):
        """거래 중단 여부 판단"""
        # 연속 손실 체크
        if self.consecutive_losses >= 2:
            logger.warning(f"연속 손실 {self.consecutive_losses}회 - 거래 중단 권고")
            return True, "연속 손실로 인한 거래 중단"
        
        # 일일 손실 한도 체크
        if self.check_daily_loss_limit():
            return True, "일일 손실 한도 도달"
        
        # 자본 손실 체크
        if self.current_balance < self.initial_balance * 0.95:
            return True, "자본 5% 손실 - 보호 모드"
        
        return False, "정상"

    def get_position_health(self, symbol, current_price):
        """포지션 건전성 평가"""
        if symbol not in self.positions:
            return "no_position"
        
        position = self.positions[symbol]
        entry_price = position['entry_price']
        pnl_rate = (current_price - entry_price) / entry_price
        
        if pnl_rate < -0.008:  # -0.8% 이하
            return "critical"  # 즉시 손절 필요
        elif pnl_rate < -0.005:  # -0.5% 이하
            return "warning"   # 주의 필요
        elif pnl_rate > 0.01:  # +1% 이상
            return "profit"    # 익절 고려
        else:
            return "normal"    # 정상
    
    def calculate_position_size(self, balance, symbol, current_price, volatility=None, indicators=None):
        """포지션 크기 계산"""
        
        # Kelly Criterion
        kelly_fraction = self._calculate_kelly_fraction()
        base_position_value = balance * min(self.max_position_size, kelly_fraction)
        
        # 동적 코인 체크
        if symbol not in STABLE_PAIRS:
            base_position_value *= 0.6
            logger.info(f"{symbol}: 동적 코인 - 포지션 60% 축소")
        
        # 시장 상황별 조정
        if self.market_analyzer:
            multiplier = self.market_analyzer.get_position_size_multiplier()
            base_position_value *= multiplier
        
        # 변동성 조정
        if volatility and volatility > 0:
            vol_adjustment = min(1.0, 0.02 / volatility)
            base_position_value *= vol_adjustment
        
        # 연속 손실 조정
        if self.consecutive_losses > 0:
            loss_adjustment = 1.0 / (1 + self.consecutive_losses * 0.2)
            base_position_value *= loss_adjustment
            logger.info(f"연속 손실 {self.consecutive_losses}회 - 포지션 {loss_adjustment:.1%}로 조정")
        
        # 최종 계산
        min_order_amount = 5000
        max_order_amount = balance * self.max_position_size
        
        final_position_value = max(min_order_amount, min(base_position_value, max_order_amount))
        
        if final_position_value < min_order_amount:
            return 0
        
        return final_position_value / current_price
    
    def _calculate_kelly_fraction(self):
        """Kelly Criterion 계산"""
        if self.win_rate <= 0 or self.avg_win_loss_ratio <= 0:
            return 0.02  # 기본값 2%
        
        p = self.win_rate
        q = 1 - p
        b = self.avg_win_loss_ratio
        
        kelly = (p * b - q) / b
        conservative_kelly = kelly * 0.25  # 보수적 접근
        
        return min(max(conservative_kelly, 0.01), 0.1)
    
    def check_stop_loss(self, symbol, current_price, averaging_manager=None):
        """손절 체크 - ✅ 물타기 고려"""
        if symbol not in self.positions:
            return False
        
        position = self.positions[symbol]
        entry_price = position['entry_price']
        
        # ✅ 기본 손절 기준
        base_stop_loss = self.stop_loss  # 1.5% 또는 1.0%
        
        # ✅ 물타기 횟수에 따라 손절 기준 확대
        if averaging_manager:
            avg_info = averaging_manager.get_averaging_info(symbol)
            avg_count = avg_info['count']
            
            if avg_count > 0:
                # 물타기 1회당 손절 기준 +1.0%p 확대
                adjustment = avg_count * 0.010  # 1.0% × 횟수
                adjusted_stop_loss = base_stop_loss + adjustment
                
                logger.debug(f"{symbol} 손절 기준 조정: "
                        f"{base_stop_loss:.1%} → {adjusted_stop_loss:.1%} "
                        f"(물타기 {avg_count}회)")
            else:
                adjusted_stop_loss = base_stop_loss
        else:
            adjusted_stop_loss = base_stop_loss
        
        loss_rate = (current_price - entry_price) / entry_price
        
        if loss_rate <= -adjusted_stop_loss:
            logger.warning(f"{symbol} 손절 신호: {loss_rate:.1%} "
                        f"(기준: -{adjusted_stop_loss:.1%})")
            return True
        
        return False
        
        position = self.positions[symbol]
        entry_price = position['entry_price']
        
        # 시간에 따른 손절 조정
        if 'entry_time' in position:
            # holding_time = (datetime.now() - position['entry_time']).total_seconds() / 3600
            # time_adjusted_stop_loss = self.stop_loss * (1 - min(holding_time / 24, 0.3))
            time_adjusted_stop_loss = self.stop_loss  # 항상 1.0%
        else:
            time_adjusted_stop_loss = self.stop_loss
        
        loss_rate = (current_price - entry_price) / entry_price
        
        if loss_rate <= -time_adjusted_stop_loss:
            logger.warning(f"{symbol} 손절 신호: {loss_rate:.1%}")
            return True
        
        return False
    
    def check_trailing_stop(self, symbol, current_price):
        """강화된 추적 손절 - 수익 보호"""
        
        if symbol not in self.positions:
            return False
        
        position = self.positions[symbol]
        entry_price = position['entry_price']
        highest_price = position.get('highest_price', entry_price)
        
        # 최고가 업데이트
        if current_price > highest_price:
            self.positions[symbol]['highest_price'] = current_price
            highest_price = current_price
            logger.debug(f"{symbol} 최고가 갱신: {highest_price:,.0f}")
        
        profit_rate = (highest_price - entry_price) / entry_price
        
        # ✅ 수익률별 차등 추적 손절
        if profit_rate > 0.025:  # +2.5% 이상
            trailing_pct = 0.008  # 0.8%
        elif profit_rate > 0.015:  # +1.5% 이상
            trailing_pct = 0.010  # 1.0%
        elif profit_rate > 0.010:  # +1.0% 이상
            trailing_pct = 0.012  # 1.2%
        else:
            return False  # 수익 없으면 작동 안 함
        
        trailing_stop = highest_price * (1 - trailing_pct)
        
        if current_price <= trailing_stop:
            logger.warning(f"🎯 {symbol} 추적 손절 발동!")
            logger.info(f"   최고가: {highest_price:,.0f}")
            logger.info(f"   현재가: {current_price:,.0f}")
            logger.info(f"   수익률: {profit_rate:.1%}")
            logger.info(f"   하락폭: {(1 - current_price/highest_price)*100:.1f}%")
            return True
        
        return False
    
    def check_daily_loss_limit(self):
        """일일 손실 한도 체크 - 누락된 메서드 추가"""
        today = datetime.now().strftime('%Y-%m-%d')
        
        if self.initial_balance <= 0:
            return False
        
        daily_loss_rate = self.daily_pnl[today] / self.initial_balance
        
        # 일일 손실이 한도를 초과했는지 체크
        is_over_limit = daily_loss_rate <= -self.daily_loss_limit
        
        if is_over_limit:
            logger.warning(f"일일 손실 한도 도달: {daily_loss_rate:.1%}")
        
        return is_over_limit
    
    def update_position(self, symbol, entry_price, quantity, trade_type):
        """포지션 업데이트 - 개선된 버전"""
        if trade_type == 'buy':
            self.positions[symbol] = {
                'entry_price': entry_price,
                'quantity': quantity,
                'value': entry_price * quantity,
                'entry_time': datetime.now(),
                'highest_price': entry_price
            }
            logger.info(f"포지션 추가: {symbol} @ {entry_price:,.0f}")
            
        elif trade_type == 'sell' and symbol in self.positions:
            position = self.positions[symbol]
            pnl = (entry_price - position['entry_price']) * quantity
            pnl_rate = (pnl / (position['entry_price'] * quantity) 
                    if position['entry_price'] * quantity > 0 else 0)
            
            # 거래 기록
            today = datetime.now().strftime('%Y-%m-%d')
            trade_record = {
                'symbol': symbol,
                'pnl': pnl,
                'pnl_rate': pnl_rate,
                'timestamp': datetime.now()
            }
            
            self.daily_pnl[today] += pnl
            self.daily_trades[today].append(trade_record)
            self.all_trades_history.append(trade_record)
            
            # ✅ 증분 업데이트 (O(1) 시간 복잡도)
            if pnl > 0:
                self.total_wins += 1
                self.total_win_amount += abs(pnl)
                self.consecutive_losses = max(0, self.consecutive_losses - 1)
            else:
                self.total_losses += 1
                self.total_loss_amount += abs(pnl)
                self.consecutive_losses += 1
            
            # ✅ 즉시 계산 (리스트 순회 없음!)
            total_trades = self.total_wins + self.total_losses
            if total_trades > 0:
                self.win_rate = self.total_wins / total_trades
            
            if self.total_wins > 0 and self.total_losses > 0:
                avg_win = self.total_win_amount / self.total_wins
                avg_loss = self.total_loss_amount / self.total_losses
                self.avg_win_loss_ratio = avg_win / avg_loss if avg_loss > 0 else 1.5
            
            # 로깅
            logger.info(f"포지션 청산: {symbol}, PnL: {pnl:+,.0f} ({pnl_rate:+.1%})")
            logger.info(f"통계: {self.total_wins}승 {self.total_losses}패 "
                    f"(승률: {self.win_rate:.1%})")
            
            del self.positions[symbol]

    # def _update_statistics(self):
    #     """통계 업데이트 - 실시간 반영"""
    #     total_trades = len(self.all_trades_history)
        
    #     if total_trades > 0:
    #         wins = [t for t in self.all_trades_history if t['pnl'] > 0]
    #         losses = [t for t in self.all_trades_history if t['pnl'] <= 0]
            
    #         # 승률 실시간 업데이트
    #         self.win_rate = len(wins) / total_trades
            
    #         # 손익비 계산
    #         if wins and losses:
    #             avg_win = np.mean([abs(t['pnl']) for t in wins])
    #             avg_loss = np.mean([abs(t['pnl']) for t in losses])
    #             self.avg_win_loss_ratio = avg_win / avg_loss if avg_loss > 0 else 1.5
            
    #         logger.debug(f"통계 업데이트: 승률={self.win_rate:.1%}, "
    #                     f"손익비={self.avg_win_loss_ratio:.2f}, "
    #                     f"총거래={total_trades}")
    
    def can_open_new_position(self):
        """새 포지션 오픈 가능 여부"""
        # 일일 손실 한도 체크
        if self.check_daily_loss_limit():
            return False, "일일 손실 한도 도달"
        
        # 연속 손실 체크
        if self.consecutive_losses >= self.max_consecutive_losses:
            return False, f"연속 손실 {self.consecutive_losses}회 - 거래 중단"
        
        # 최대 포지션 개수 체크
        if len(self.positions) >= self.max_positions:
            return False, "최대 포지션 수 도달"
        
        # 자본 보호 체크
        if self.current_balance < self.initial_balance * 0.7:
            return False, "자본 30% 손실 - 보호 모드"
        
        return True, "거래 가능"
    
    def get_position_info(self, symbol):
        """특정 심볼의 포지션 정보 반환"""
        return self.positions.get(symbol, None)
    
    def get_risk_status(self):
        """현재 리스크 상태 - 실시간 가치 반영"""
        today = datetime.now().strftime('%Y-%m-%d')
        
        # 현재 가격으로 포지션 가치 재계산
        total_value = self.current_balance
        for symbol, pos in self.positions.items():
            try:
                current_price = pyupbit.get_current_price(f"KRW-{symbol}")
                if current_price:
                    total_value += current_price * pos['quantity']
                else:
                    total_value += pos['value']
            except:
                total_value += pos['value']
        
        return {
            'current_balance': self.current_balance,
            'total_value': total_value,
            'daily_pnl': self.daily_pnl[today],
            'daily_pnl_rate': (self.daily_pnl[today] / self.initial_balance 
                              if self.initial_balance > 0 else 0),
            'consecutive_losses': self.consecutive_losses,
            'active_positions': len(self.positions),
            'win_rate': self.win_rate,
            'kelly_fraction': self._calculate_kelly_fraction(),
            'total_trades': len(self.all_trades_history),
            'wins': self.total_wins,
            'losses': self.total_losses
        }
    
    def reset_daily_stats(self):
        """일일 통계 리셋"""
        today = datetime.now().strftime('%Y-%m-%d')
        self.daily_pnl[today] = 0
        self.daily_trades[today] = []
        logger.info("일일 통계 리셋")
    
    def _assess_market_condition(self, indicators):
        """시장 상황 평가"""
        score = 1.0
        
        # 추세 확인
        if indicators.get('trend') == 'strong_up':
            score *= 1.2
        elif indicators.get('trend') == 'down':
            score *= 0.8
        
        # RSI 확인
        rsi = indicators.get('rsi', 50)
        if rsi > 70:  # 과매수
            score *= 0.7
        elif rsi < 30:  # 과매도
            score *= 1.1
        
        return min(max(score, 0.5), 1.5)