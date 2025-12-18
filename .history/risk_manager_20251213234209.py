# risk_manager.py - 중복 제거 및 최적화 완료 버전

import os
from datetime import datetime
import pyupbit
from collections import defaultdict
import logging
import numpy as np

# 설정 파일 로드
from config import RISK_CONFIG, STABLE_PAIRS, ADVANCED_CONFIG

logger = logging.getLogger(__name__)

class RiskManager:
    def __init__(self, initial_balance):
        # 1. 초기 자본 설정 로직 통합
        balance_file = "initial_balance.txt"
        self.need_total_balance_update = False
        
        if os.path.exists(balance_file):
            try:
                with open(balance_file, 'r') as f:
                    self.initial_balance = float(f.read().strip())
                    logger.info(f"✅ 저장된 초기 자본 불러옴: {self.initial_balance:,.0f}원")
            except Exception as e:
                logger.error(f"⚠️ 파일 읽기 실패: {e}")
                self.initial_balance = initial_balance
        else:
            self.initial_balance = initial_balance
            self.need_total_balance_update = True
            logger.info("🔄 초기 자본 설정 준비 중... (총 자산 계산 예정)")

        # 2. 변수 초기화 (중복 제거됨)
        self.current_balance = self.initial_balance
        self.reset_to_current_balance = True  # 첫 실행 시 재설정 플래그
        
        self.positions = {}  # 포지션 저장소
        self.daily_pnl = defaultdict(float)  # 일일 손익
        self.daily_trades = defaultdict(list)  # 일일 거래 기록
        
        # 3. 설정값 로드
        self.max_position_size = RISK_CONFIG['max_position_size']
        self.stop_loss = RISK_CONFIG['stop_loss']
        self.daily_loss_limit = RISK_CONFIG['daily_loss_limit']
        self.max_positions = RISK_CONFIG['max_positions']
        self.max_consecutive_losses = ADVANCED_CONFIG.get('max_consecutive_losses', 3)
        
        # 4. 통계 변수
        self.consecutive_losses = 0
        self.all_trades_history = []
        self.total_wins = 0
        self.total_losses = 0
        self.total_win_amount = 0.0
        self.total_loss_amount = 0.0
        
        # Kelly Criterion 파라미터
        self.win_rate = 0.5
        self.avg_win_loss_ratio = 1.5
        
        # 5. 시장 분석기 로드 (선택적)
        try:
            from market_condition_check import MarketAnalyzer
            self.market_analyzer = MarketAnalyzer()
        except ImportError:
            self.market_analyzer = None
            logger.warning("MarketAnalyzer를 로드할 수 없습니다 (기본 리스크 관리만 작동)")

    def update_balance(self, balance):
        """잔고 업데이트 및 초기 자본 재설정"""
        # 첫 실행 시 현재 잔고를 초기 자본으로 확정
        if self.reset_to_current_balance:
            self.initial_balance = balance
            self.reset_to_current_balance = False
            logger.info(f"🔄 초기 자본 확정: {balance:,.0f}원 (과거 손실 무시)")
        
        self.current_balance = balance

    def should_stop_trading(self):
        """거래 중단 여부 판단"""
        # 1. 연속 손실 체크
        if self.consecutive_losses >= 2:
            logger.warning(f"연속 손실 {self.consecutive_losses}회 - 거래 중단 권고")
            return True, "연속 손실로 인한 거래 중단"
        
        # 2. 일일 손실 한도 체크
        if self.check_daily_loss_limit():
            return True, "일일 손실 한도 도달"
        
        # 3. 자본 보호 (원금의 7% 이상 손실 시)
        if self.current_balance < self.initial_balance * 0.93:
            return True, "자본 7% 손실 - 보호 모드 발동"
        
        return False, "정상"

    def check_daily_loss_limit(self):
        """일일 손실 한도 체크"""
        today = datetime.now().strftime('%Y-%m-%d')
        
        if self.initial_balance <= 0:
            return False
        
        daily_loss_rate = self.daily_pnl[today] / self.initial_balance
        
        is_over_limit = daily_loss_rate <= -self.daily_loss_limit
        if is_over_limit:
            logger.warning(f"🚫 일일 손실 한도 도달: {daily_loss_rate:.1%} (한도: -{self.daily_loss_limit:.1%})")
        
        return is_over_limit

    def calculate_position_size(self, balance, symbol, current_price, volatility=None, indicators=None):
        """포지션 크기 계산 (Kelly + 시장상황 + 변동성)"""
        
        # 1. Kelly Criterion 기반 비중 계산
        kelly_fraction = self._calculate_kelly_fraction()
        base_position_value = balance * min(self.max_position_size, kelly_fraction)
        
        # 2. 동적 코인(알트코인) 패널티
        if symbol not in STABLE_PAIRS:
            base_position_value *= 0.6
            
        # 3. 시장 상황별 조정 (MarketAnalyzer 연동)
        if self.market_analyzer:
            multiplier = self.market_analyzer.get_position_size_multiplier()
            base_position_value *= multiplier
        
        # 4. 변동성 역비례 조정 (변동성 크면 비중 축소)
        if volatility and volatility > 0:
            vol_adjustment = min(1.0, 0.02 / volatility)
            base_position_value *= vol_adjustment
        
        # 5. 연속 손실 중이면 비중 축소
        if self.consecutive_losses > 0:
            loss_adjustment = 1.0 / (1 + self.consecutive_losses * 0.2)
            base_position_value *= loss_adjustment
            logger.info(f"연속 손실 패널티 적용: 비중 {loss_adjustment:.1%}로 축소")
        
        # 6. 최종 금액 범위 제한
        min_order_amount = 5500 # 업비트 최소 주문 + 여유
        max_order_amount = balance * self.max_position_size
        
        final_position_value = max(min_order_amount, min(base_position_value, max_order_amount))
        
        if final_position_value < min_order_amount:
            return 0
        
        return final_position_value / current_price
    
    def _calculate_kelly_fraction(self):
        """Kelly Criterion 계산 (보수적 적용)"""
        if self.win_rate <= 0 or self.avg_win_loss_ratio <= 0:
            return 0.02  # 데이터 없으면 기본 2%
        
        p = self.win_rate
        q = 1 - p
        b = self.avg_win_loss_ratio
        
        kelly = (p * b - q) / b
        conservative_kelly = kelly * 0.25  # 1/4 켈리 (안전 제일)
        
        return min(max(conservative_kelly, 0.01), 0.1) # 최소 1%, 최대 10%
    
    def check_stop_loss(self, symbol, current_price, averaging_manager=None):
        """손절 체크 (물타기 횟수에 따라 유동적)"""
        if symbol not in self.positions:
            return False
        
        position = self.positions[symbol]
        entry_price = position['entry_price']
        
        # 기본 손절 기준
        base_stop_loss = self.stop_loss
        
        # 물타기 횟수에 따른 손절 범위 확장
        if averaging_manager:
            avg_info = averaging_manager.get_averaging_info(symbol)
            avg_count = avg_info['count']
            
            if avg_count > 0:
                # 1회당 0.5%p씩 여유, 최대 2.5%까지
                adjustment = min(avg_count * 0.005, 0.010)
                adjusted_stop_loss = min(base_stop_loss + adjustment, 0.025)
            else:
                adjusted_stop_loss = base_stop_loss
        else:
            adjusted_stop_loss = base_stop_loss
        
        loss_rate = (current_price - entry_price) / entry_price
        
        if loss_rate <= -adjusted_stop_loss:
            logger.warning(f"✂️ {symbol} 손절 신호: {loss_rate:.1%} (기준: -{adjusted_stop_loss:.1%})")
            return True
        
        return False
    
    def check_trailing_stop(self, symbol, current_price):
        """추적 손절 (익절 보호) - ✅ 수수료 고려 버전"""
        
        if symbol not in self.positions:
            return False
        
        position = self.positions[symbol]
        entry_price = position['entry_price']
        highest_price = position.get('highest_price', entry_price)
        
        # 최고가 갱신
        if current_price > highest_price:
            self.positions[symbol]['highest_price'] = current_price
            highest_price = current_price
        
        # 현재 수익률 (진입가 대비)
        profit_rate = (highest_price - entry_price) / entry_price
        
        # ✅ 개선된 로직: 최소 1.2% 수익부터 작동 (수수료 방어)
        if profit_rate > 0.030:    # +3.0% 이상 (대박 구간)
            trailing_pct = 0.015   # 1.5% 여유
        elif profit_rate > 0.020:  # +2.0% 이상
            trailing_pct = 0.010   # 1.0% 여유
        elif profit_rate > 0.012:  # +1.2% 이상 (최소 마진 확보)
            trailing_pct = 0.005   # 0.5% 여유
        else:
            return False  # 아직 수익이 적으면 놔둠 (목표가 대기)
        
        # 추적 손절가 계산
        trailing_stop_price = highest_price * (1 - trailing_pct)
        
        if current_price <= trailing_stop_price:
            logger.warning(f"🎯 {symbol} 추적 손절 발동 (수익 확정)")
            logger.info(f"   최고가: {highest_price:,.0f} | 현재가: {current_price:,.0f}")
            logger.info(f"   최고 수익률: {profit_rate:.1%}")
            return True
        
        return False
    
    def update_position(self, symbol, entry_price, quantity, trade_type):
        """포지션 업데이트 및 통계 갱신"""
        if trade_type == 'buy':
            self.positions[symbol] = {
                'entry_price': entry_price,
                'quantity': quantity,
                'value': entry_price * quantity,
                'entry_time': datetime.now(),
                'highest_price': entry_price
            }
            logger.info(f"➕ 포지션 등록: {symbol}")
            
        elif trade_type == 'sell' and symbol in self.positions:
            position = self.positions[symbol]
            pnl = (entry_price - position['entry_price']) * quantity
            
            # 통계 즉시 업데이트 (O(1))
            today = datetime.now().strftime('%Y-%m-%d')
            self.daily_pnl[today] += pnl
            
            if pnl > 0:
                self.total_wins += 1
                self.total_win_amount += abs(pnl)
                self.consecutive_losses = max(0, self.consecutive_losses - 1) # 연패 초기화
            else:
                self.total_losses += 1
                self.total_loss_amount += abs(pnl)
                self.consecutive_losses += 1 # 연패 증가
            
            # 승률 및 손익비 재계산
            total_trades = self.total_wins + self.total_losses
            if total_trades > 0:
                self.win_rate = self.total_wins / total_trades
            
            if self.total_wins > 0 and self.total_losses > 0:
                avg_win = self.total_win_amount / self.total_wins
                avg_loss = self.total_loss_amount / self.total_losses
                self.avg_win_loss_ratio = avg_win / avg_loss if avg_loss > 0 else 1.5
            
            # 기록 및 삭제
            del self.positions[symbol]
            logger.info(f"➖ 포지션 삭제: {symbol} (연속 손실: {self.consecutive_losses}회)")

    def can_open_new_position(self):
        """신규 진입 가능 여부 체크"""
        if self.check_daily_loss_limit():
            return False, "일일 손실 한도 초과"
        
        if self.consecutive_losses >= self.max_consecutive_losses:
            return False, f"연속 손실 {self.consecutive_losses}회로 인한 중단"
        
        if len(self.positions) >= self.max_positions:
            return False, "최대 포지션 수 도달"
        
        return True, "가능"
    
    def get_risk_status(self):
        """현재 리스크 상태 반환 (UI 표시용)"""
        today = datetime.now().strftime('%Y-%m-%d')
        
        # 현재 보유 포지션 평가금액 합산 (API 호출 최소화: 저장된 value 사용)
        # 정확한 평가를 원하면 여기서 get_current_price를 호출해야 하지만 속도 저하 주의
        total_holding_value = sum(p['value'] for p in self.positions.values())
        
        return {
            'current_balance': self.current_balance,
            'total_value': self.current_balance + total_holding_value, # 근사치
            'daily_pnl': self.daily_pnl[today],
            'daily_pnl_rate': (self.daily_pnl[today] / self.initial_balance 
                              if self.initial_balance > 0 else 0),
            'consecutive_losses': self.consecutive_losses,
            'active_positions': len(self.positions),
            'win_rate': self.win_rate,
            'kelly_fraction': self._calculate_kelly_fraction()
        }
    
    def reset_daily_stats(self):
        """자정에 일일 통계 초기화"""
        today = datetime.now().strftime('%Y-%m-%d')
        self.daily_pnl[today] = 0
        self.daily_trades[today] = []
        logger.info("📅 일일 리스크 통계가 초기화되었습니다.")