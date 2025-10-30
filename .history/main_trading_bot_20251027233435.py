# main_trading_bot.py - 수정 완료 버전

import pyupbit
import time
import logging
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import sys
import io
from improved_strategy import ImprovedStrategy
from risk_manager import RiskManager
from position_recovery import PositionRecovery
from daily_summary import DailySummary
from momentum_scanner_improved import ImprovedMomentumScanner
from partial_exit_manager import PartialExitManager
from pyramiding_manager import PyramidingManager
from adaptive_preset_manager import AdaptivePresetManager
from config import ADAPTIVE_PRESET_CONFIG
from trade_history_manager import TradeHistoryManager
from averaging_down_manager import AveragingDownManager        

from config import (
    TRADING_PAIRS,
    STRATEGY_CONFIG, 
    RISK_CONFIG,
    ADVANCED_CONFIG,
    STABLE_PAIRS,
    DYNAMIC_COIN_CONFIG,
    AVERAGING_DOWN_CONFIG,
    apply_preset,  # ✅ 함수 import
    ACTIVE_PRESET  # ✅ 활성 프리셋 import
)

# 한글/이모지 인코딩 문제 해결
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 로깅 설정 - 인코딩 추가
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('trading.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class TradingBot:
    def __init__(self, access_key, secret_key):
        apply_preset(ACTIVE_PRESET)
        logger.info(f"🎯 프리셋 적용: {ACTIVE_PRESET}")
        
        self.upbit = pyupbit.Upbit(access_key, secret_key)
        self.balance = self.get_balance()
        
        # 추매 매니저 초기화
        self.pyramid_manager = PyramidingManager()
        
        # ✅ 거래 기록 관리자 추가
        self.trade_history = TradeHistoryManager()
        logger.info("✅ 거래 기록 시스템 초기화")

        # 전략 및 리스크 매니저 초기화
        self.strategy = ImprovedStrategy()
        self.risk_manager = RiskManager(self.balance)
        
        # 동적 모멘텀 스캐너 초기화
        self.momentum_scanner = ImprovedMomentumScanner()
        self.dynamic_coins = []
        self.last_scan_time = 0
        self.daily_summary = DailySummary()
        
        # 포지션 복구 시스템 추가
        self.position_recovery = PositionRecovery(self.upbit)
        self.recover_existing_positions()

        # ✅ 거래 기록 관리자 추가
        self.trade_history = TradeHistoryManager()
        logger.info("✅ 거래 기록 시스템 초기화")

        # ✅ 자동 프리셋 매니저 추가
        if ADAPTIVE_PRESET_CONFIG['enabled']:
            self.preset_manager = AdaptivePresetManager(ADAPTIVE_PRESET_CONFIG)
            logger.info("🤖 자동 프리셋 전환 시스템 활성화")
        else:
            self.preset_manager = None
        
        self.last_preset_check = time.time()
        
        self.partial_exit_manager = PartialExitManager()
        
        logger.info(f"봇 초기화 완료. 초기 자본: {self.balance:,.0f} KRW")


    def recover_existing_positions(self):
        """기존 포지션 복구"""
        logger.info("="*50)
        logger.info("기존 포지션 확인 중...")
        
        # 1. 저장된 포지션 로드
        saved_positions = self.position_recovery.load_positions()
        
        # 2. 거래소와 동기화
        recovered = self.position_recovery.sync_with_exchange(saved_positions)
        
        if recovered:
            # 3. 복구된 포지션을 리스크 매니저에 등록
            for symbol, pos in recovered.items():
                self.risk_manager.positions[symbol] = {
                    'entry_price': pos['entry_price'],
                    'quantity': pos['quantity'],
                    'value': pos['entry_price'] * pos['quantity'],
                    'entry_time': datetime.fromisoformat(pos['entry_time']) if isinstance(pos['entry_time'], str) else pos['entry_time'],
                    'highest_price': pos['entry_price']
                }
                
                # 전략에도 등록
                self.strategy.position_entry_time[symbol] = time.time()
                
                logger.info(f"✅ 포지션 복구: {symbol} @ {pos['entry_price']:,.0f}")
        
        logger.info(f"복구 완료: {len(recovered)}개 포지션")
        logger.info("="*50)
    
    def save_current_positions(self):
        """현재 포지션 저장 (주기적으로 호출)"""
        self.position_recovery.save_positions(self.risk_manager.positions)
                
    def get_balance(self):
        """KRW 잔고 조회"""
        try:
            balances = self.upbit.get_balances()
            for b in balances:
                if b['currency'] == 'KRW':
                    return float(b['balance'])
        except Exception as e:
            logger.error(f"잔고 조회 실패: {e}")
        return 0
    
    def calculate_indicators(self, ticker):
        """강화된 기술적 지표 계산"""
        try:
            # OHLCV 데이터 가져오기
            df = pyupbit.get_ohlcv(ticker, interval="minute60", count=100)
            if df is None or len(df) < 50:
                return None
            
            # 현재가
            current_price = df['close'].iloc[-1]
            
            # 이동평균선
            df['sma_20'] = df['close'].rolling(window=20).mean()
            df['sma_50'] = df['close'].rolling(window=50).mean()
            
            # RSI 계산
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            df['rsi'] = 100 - (100 / (1 + rs))
            
            # MACD
            df['ema_12'] = df['close'].ewm(span=12, adjust=False).mean()
            df['ema_26'] = df['close'].ewm(span=26, adjust=False).mean()
            df['macd'] = df['ema_12'] - df['ema_26']
            df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
            
            # 볼륨 비율
            avg_volume = df['volume'].rolling(window=20).mean().iloc[-1]
            current_volume = df['volume'].iloc[-1]
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1
            
            # 변동성 (ATR)
            high_low = df['high'] - df['low']
            high_close = np.abs(df['high'] - df['close'].shift())
            low_close = np.abs(df['low'] - df['close'].shift())
            ranges = pd.concat([high_low, high_close, low_close], axis=1)
            true_range = np.max(ranges, axis=1)
            atr = true_range.rolling(14).mean().iloc[-1]
            volatility = atr / current_price
            
            # 예상 수익률 계산 (단순 모멘텀 기반)
            momentum = (current_price - df['close'].iloc[-20]) / df['close'].iloc[-20]
            expected_return = momentum * 0.3  # 보수적 추정
            
            # 추세 판단
            if df['sma_20'].iloc[-1] > df['sma_50'].iloc[-1] and current_price > df['sma_20'].iloc[-1]:
                trend = 'strong_up'
            elif df['sma_20'].iloc[-1] > df['sma_50'].iloc[-1]:
                trend = 'up'
            elif df['sma_20'].iloc[-1] < df['sma_50'].iloc[-1]:
                trend = 'down'
            else:
                trend = 'sideways'
            
            return {
                'price': current_price,
                'sma_20': df['sma_20'].iloc[-1],
                'sma_50': df['sma_50'].iloc[-1],
                'rsi': df['rsi'].iloc[-1],
                'macd': df['macd'].iloc[-1],
                'macd_signal': df['macd_signal'].iloc[-1],
                'volume_ratio': volume_ratio,
                'volatility': volatility,
                'expected_return': expected_return,
                'trend': trend
            }
            
        except Exception as e:
            logger.error(f"지표 계산 실패 {ticker}: {e}")
            return None

    def update_trading_pairs(self):
        """거래 대상 동적 업데이트"""
        
        if not DYNAMIC_COIN_CONFIG['enabled']:
            return
        
        now = time.time()
        
        # 갱신 시간 체크
        if now - self.last_scan_time < DYNAMIC_COIN_CONFIG['refresh_interval']:
            return
        
        logger.info("="*50)
        logger.info("모멘텀 코인 스캔 시작...")
        
        # 새로운 모멘텀 코인 검색
        momentum_coins = self.momentum_scanner.scan_top_performers(
            top_n=DYNAMIC_COIN_CONFIG['max_dynamic_coins']
        )
        
        # 기존 동적 코인 포지션 체크
        for coin in self.dynamic_coins:
            if coin not in momentum_coins and coin not in STABLE_PAIRS:
                # 포지션 있으면 청산
                if coin in self.risk_manager.positions:
                    logger.info(f"모멘텀 상실: {coin} 청산")
                    self.execute_trade(coin, 'sell')
        
        # 새로운 리스트 구성
        self.dynamic_coins = momentum_coins
        
        # 글로벌 거래 리스트 업데이트
        global TRADING_PAIRS
        TRADING_PAIRS = STABLE_PAIRS + self.dynamic_coins
        
        logger.info(f"거래 대상 업데이트: {', '.join(TRADING_PAIRS)}")
        self.last_scan_time = now
    
    def execute_trade(self, symbol, trade_type, current_price=None, force_stop_loss=False):
        """거래 실행 (개선된 로직) - ✅ 1번 수정: 실제 체결가 반영"""
        ticker = f"KRW-{symbol}"
        
        if current_price is None:
            current_price = pyupbit.get_current_price(ticker)
            if not current_price:
                return False
        
        if trade_type == 'buy':
            # 지표 계산
            indicators = self.calculate_indicators(ticker)
            if not indicators:
                logger.warning(f"{symbol}: 지표 계산 실패")
                return False
            
            # 진입 조건 체크
            can_enter, reason = self.strategy.should_enter_position(symbol, indicators)
            if not can_enter:
                logger.info(f"{symbol}: {reason}")
                return False
            
            # 리스크 체크
            can_trade, risk_reason = self.risk_manager.can_open_new_position()
            if not can_trade:
                logger.warning(f"리스크 제한: {risk_reason}")
                return False
                                
            # 포지션 크기 계산
            self.balance = self.get_balance()
            self.risk_manager.current_balance = self.balance
            
            quantity = self.risk_manager.calculate_position_size(
                self.balance, symbol, current_price,
                volatility=indicators.get('volatility'),
                indicators=indicators
            )
            
            if quantity == 0:
                logger.info("포지션 크기가 너무 작음")
                return False
            
            # 주문 금액 계산
            order_amount = min(current_price * quantity, self.balance * 0.95)
            
            # ✅ 실제 매수 실행 - 체결 정보 받기
            try:
                order = self.upbit.buy_market_order(ticker, order_amount)
                
                if order:
                    # ✅ 실제 체결 정보 파싱
                    # 주문 상세 정보 조회
                    time.sleep(0.5)  # 체결 대기
                    order_detail = self.upbit.get_order(order['uuid'])
                    
                    if order_detail:
                        # 실제 체결 가격과 수량 계산
                        executed_volume = float(order_detail.get('executed_volume', quantity))
                        paid_fee = float(order_detail.get('paid_fee', 0))
                        trades_count = float(order_detail.get('trades_count', 0))
                        
                        # 평균 체결가 계산
                        if trades_count > 0 and executed_volume > 0:
                            total_paid = order_amount - paid_fee
                            actual_price = total_paid / executed_volume
                            actual_quantity = executed_volume
                        else:
                            # 체결 정보를 못 받은 경우 예상값 사용
                            actual_price = current_price
                            actual_quantity = quantity
                    else:
                        actual_price = current_price
                        actual_quantity = quantity
                    
                    # ✅ 실제 체결 정보로 업데이트
                    self.strategy.record_trade(symbol, 'buy')
                    self.risk_manager.update_position(symbol, actual_price, actual_quantity, 'buy')
                    
                    self.daily_summary.record_trade({
                        'symbol': symbol,
                        'type': 'buy',
                        'price': actual_price,
                        'quantity': actual_quantity
                    })
                    
                    logger.info(f"✅ 매수 완료: {symbol} @ {actual_price:,.0f} KRW (수량: {actual_quantity:.8f})")
                    return True
                    
            except Exception as e:
                logger.error(f"매수 실패: {e}")
                
        elif trade_type == 'sell':
            # ✅ 손절 시 보유시간 무시
            if not force_stop_loss:
                if not self.strategy.can_exit_position(symbol):
                    logger.info(f"{symbol}: 최소 보유시간 미충족")
                    return False
            else:
                logger.warning(f"🚨 손절 강제 실행 (보유시간 무시)")

            # 보유 수량 조회
            quantity = self.get_position_quantity(symbol)
            if quantity == 0:
                return False

            # 현재 포지션 정보 확보
            position = self.risk_manager.positions.get(symbol)
            if not position or 'entry_price' not in position:
                logger.error(f"{symbol}: 포지션 정보가 없어 PnL 계산 불가")
                return False

            # ✅ 진입 정보 미리 저장
            entry_price = float(position['entry_price'])
            entry_quantity = float(position['quantity'])
            
            logger.info(f"매도 시작: {symbol}, 진입가={entry_price:,.2f}, 진입수량={entry_quantity:.8f}")

            # 실제 매도 실행
            try:
                order = self.upbit.sell_market_order(ticker, quantity)
                
                if order:
                    # ✅ 주문 UUID 확인
                    order_uuid = order.get('uuid')
                    if not order_uuid:
                        logger.error("주문 UUID 없음")
                        return False
                    
                    logger.info(f"주문 UUID: {order_uuid}")
                    
                    # 체결 대기
                    time.sleep(1.0)  # 0.5초 → 1초로 증가
                    
                    # 주문 상세 조회
                    order_detail = self.upbit.get_order(order_uuid)
                    
                    if not order_detail:
                        logger.error("주문 상세 정보 조회 실패")
                        # 현재가로 추정
                        actual_price = pyupbit.get_current_price(ticker)
                        actual_quantity = quantity
                    elif order_detail.get('state') != 'done':
                        logger.warning(f"주문 미체결 상태: {order_detail.get('state')}")
                        actual_price = pyupbit.get_current_price(ticker)
                        actual_quantity = quantity
                    else:
                        # ✅ 체결 완료 - 정확한 정보 파싱
                        if order_detail:
                            executed_volume = float(order_detail.get('executed_volume', 0))
                            paid_fee = float(order_detail.get('paid_fee', 0))
                            
                            trades = order_detail.get('trades', [])
                            
                            logger.info(f"체결 정보: executed_volume={executed_volume:.8f}, paid_fee={paid_fee:.2f}")
                            logger.info(f"trades 개수: {len(trades)}")
                            
                            if trades and executed_volume > 0:
                                total_received = 0
                                total_fee = 0
                                
                                for i, trade in enumerate(trades):
                                    trade_price = float(trade.get('price', 0))
                                    trade_volume = float(trade.get('volume', 0))
                                    trade_fee = float(trade.get('fee', 0))
                                    
                                    trade_amount = trade_price * trade_volume
                                    total_received += trade_amount
                                    total_fee += trade_fee
                                
                                # ✅ 안전한 계산
                                if executed_volume > 0:
                                    actual_price = total_received / executed_volume
                                    actual_quantity = executed_volume
                                    net_received = total_received - total_fee
                                    
                                    logger.info(f"합계: 받은금액={total_received:,.2f}, 수수료={total_fee:,.2f}")
                                    logger.info(f"평균 매도가: {actual_price:,.2f}")
                                else:
                                    logger.error("❌ 체결 수량이 0 - 현재가로 추정")
                                    actual_price = current_price
                                    actual_quantity = quantity
                                    net_received = actual_price * actual_quantity * 0.9995
                                
                            else:
                                # trades 없으면 기본 계산
                                logger.warning("trades 정보 없음, 기본 계산 사용")
                                price_str = order_detail.get('price', '0')
                                actual_price = float(price_str) if price_str else current_price
                                actual_quantity = executed_volume if executed_volume > 0 else quantity
                                net_received = actual_price * actual_quantity - paid_fee
                        else:
                            # ✅ order_detail이 없는 경우도 처리
                            logger.error("주문 상세 정보 조회 실패 - 현재가로 추정")
                            actual_price = current_price
                            actual_quantity = quantity
                            net_received = actual_price * actual_quantity * 0.9995
                    
                    # ✅ PnL 계산 (수수료 포함)
                    # 매수 시 지불한 금액 (실제 매도한 수량에 대한 원가만 계산!)
                    buy_cost = entry_price * actual_quantity  # ✅ 핵심 수정!

                    hold_time = (datetime.now() - position['entry_time']).total_seconds() / 3600

                    # 매도 시 받은 금액 (수수료 차감 후)
                    if 'net_received' in locals():
                        sell_revenue = net_received
                    else:
                        sell_revenue = actual_price * actual_quantity * 0.9995  # 수수료 0.05% 차감

                    # 실제 손익
                    real_pnl = sell_revenue - buy_cost
                    pnl_rate = (real_pnl / buy_cost) if buy_cost > 0 else 0.0

                    self.trade_history.add_trade({
                        'timestamp': datetime.now().isoformat(),  # ✅ ISO 문자열로
                        'symbol': symbol,
                        'type': 'sell',
                        'entry_price': entry_price,
                        'exit_price': actual_price,
                        'quantity': actual_quantity,
                        'pnl': real_pnl,
                        'pnl_rate': pnl_rate,
                        'fee': paid_fee if 'paid_fee' in locals() else 0,
                        'hold_time_hours': hold_time
                    })                 

                    # ✅ 상세 로그 출력
                    logger.info(f"\n{'='*60}")
                    logger.info(f"💰 PnL 계산 상세")
                    logger.info(f"{'='*60}")
                    logger.info(f"진입가: {entry_price:,.2f} KRW")
                    logger.info(f"매도 수량: {actual_quantity:.8f}")  # ✅ entry_quantity → actual_quantity
                    logger.info(f"매수 원가: {buy_cost:,.2f} KRW")
                    logger.info(f"")
                    logger.info(f"매도가: {actual_price:,.2f} KRW")
                    logger.info(f"매도 수익: {sell_revenue:,.2f} KRW")
                    logger.info(f"")
                    logger.info(f"순손익: {real_pnl:+,.2f} KRW")
                    logger.info(f"수익률: {pnl_rate:+.2%}")
                    logger.info(f"{'='*60}\n")
                    
                    # ✅ 기록 업데이트 (actual_price는 실제 매도가!)
                    self.strategy.record_trade(symbol, 'sell')
                    self.risk_manager.update_position(symbol, actual_price, actual_quantity, 'sell')

                    self.daily_summary.record_trade({
                        'symbol': symbol,
                        'type': 'sell',
                        'price': actual_price,        # ✅ 실제 매도가 (양수!)
                        'quantity': actual_quantity,
                        'pnl': real_pnl,
                        'pnl_rate': pnl_rate
                    })
                    
                    # 프리셋 매니저에 거래 기록
                    if self.preset_manager:
                        self.preset_manager.record_trade({
                            'symbol': symbol,
                            'pnl': real_pnl,
                            'pnl_rate': pnl_rate
                        })

                    logger.info(f"🔴 매도 완료: {symbol} @ {actual_price:,.2f} KRW "
                                f"(PnL {real_pnl:+,.2f}, {pnl_rate:+.2%})")
                    return True
                    
            except Exception as e:
                logger.error(f"매도 실패: {e}")
                import traceback
                logger.error(traceback.format_exc())

        return False
    
    def get_position_quantity(self, symbol):
        """보유 수량 조회"""
        try:
            balances = self.upbit.get_balances()
            for b in balances:
                if b['currency'] == symbol:
                    return float(b['balance'])
        except Exception as e:
            logger.error(f"포지션 조회 실패: {e}")
        return 0
    
    def check_exit_conditions(self):
        """개선된 청산 조건 체크"""
        
        for symbol in list(self.risk_manager.positions.keys()):
            ticker = f"KRW-{symbol}"
            current_price = pyupbit.get_current_price(ticker)
            
            if not current_price:
                continue
            
            position = self.risk_manager.positions[symbol]
            entry_price = position['entry_price']
            entry_time = position['entry_time']
            
            # 현재 손실률 계산
            loss_rate = (current_price - entry_price) / entry_price
            
            # 현재 보유 수량
            current_quantity = self.get_position_quantity(symbol)
            
            # 1. 부분 매도 체크 (최우선)
            partial_exit, sold_quantity = self.partial_exit_manager.check_partial_exit(
                symbol, entry_price, entry_time, current_price, current_quantity, self.upbit
            )
            
            if partial_exit:
                remaining = current_quantity - sold_quantity
                
                if remaining < 0.0001:
                    self.partial_exit_manager.reset_position(symbol)
                    self.risk_manager.update_position(symbol, current_price, current_quantity, 'sell')
                    logger.info(f"✅ {symbol} 전량 청산 완료")
                else:
                    self.risk_manager.positions[symbol]['quantity'] = remaining
                    logger.info(f"ℹ️ {symbol} 남은 수량: {remaining:.8f}")
                
                continue
            
            # 2. ✅ 손절 체크 (보유시간 무시) - force_stop_loss=True 전달
            if self.risk_manager.check_stop_loss(symbol, current_price):
                logger.warning(f"{symbol}: 🚨 손절 발동 (손실률: {loss_rate:.2%}) - 즉시 실행")
                self.execute_trade(symbol, 'sell', current_price, force_stop_loss=True)  # ✅ 수정!
                self.partial_exit_manager.reset_position(symbol)
                continue
            
            # 3. 추적 손절 체크
            if self.risk_manager.check_trailing_stop(symbol, current_price):
                if self.strategy.can_exit_position(symbol):
                    logger.info(f"{symbol}: 추적 손절 발동")
                    self.execute_trade(symbol, 'sell', current_price)
                    self.partial_exit_manager.reset_position(symbol)
                    continue
            
            # 4. 목표 수익 체크 (남은 수량 전량 매도)
            if self.strategy.check_profit_target(entry_price, current_price):
                if self.strategy.can_exit_position(symbol):
                    logger.info(f"{symbol}: 최종 목표 수익 달성")
                    self.execute_trade(symbol, 'sell', current_price)
                    self.partial_exit_manager.reset_position(symbol)
    
    def analyze_and_trade(self):
        """시장 분석 및 거래"""
        for symbol in TRADING_PAIRS:
            ticker = f"KRW-{symbol}"
            
            try:
                # 기존 포지션 확인
                if symbol in self.risk_manager.positions:
                    continue  # 이미 포지션이 있으면 스킵
                
                # 지표 계산
                indicators = self.calculate_indicators(ticker)
                if not indicators:
                    continue
                
                # 매수 시도
                self.execute_trade(symbol, 'buy', indicators['price'])
                
            except Exception as e:
                logger.error(f"{symbol} 분석 실패: {e}")
                continue

    def get_accurate_balance(self):
        """업비트 실제 잔고 기반 정확한 자산 계산"""
        try:
            balances = self.upbit.get_balances()
            total_value = 0
            
            for b in balances:
                if b['currency'] == 'KRW':
                    total_value += float(b['balance'])
                else:
                    qty = float(b['balance']) + float(b['locked'])
                    if qty > 0:
                        current_price = pyupbit.get_current_price(
                            f"KRW-{b['currency']}"
                        )
                        if current_price:
                            total_value += current_price * qty
            
            return total_value
        except Exception as e:
            logger.error(f"자산 계산 실패: {e}")
            return self.balance
    
    def print_status(self):
        """현재 상태 출력"""
        print("\n" + "="*60)
        print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*60)
        
        # 시장 상황 표시
        from market_condition_check import MarketAnalyzer
        analyzer = MarketAnalyzer()
        market = analyzer.analyze_market(TRADING_PAIRS)
        
        market_emoji = {
            'bullish': '🐂',
            'bearish': '🐻', 
            'neutral': '➡️'
        }
        
        print(f"📈 시장 상황: {market_emoji.get(market, '')} {market.upper()}")
        
        # ✅ 프리셋 상태 표시
        if self.preset_manager:
            print(f"🎯 활성 프리셋: {self.preset_manager.current_preset.upper()}")
        
        # 계좌 정보
        # self.balance = self.get_balance()
        # print(f"💰 KRW 잔고: {self.balance:,.0f} 원")
        real_total_value = self.get_accurate_balance()
       
        # 리스크 상태
        risk_status = self.risk_manager.get_risk_status()
        # print(f"📊 총 자산가치: {risk_status['total_value']:,.0f} 원")
        print(f"📊 총 자산가치: {real_total_value:,.0f} 원 (업비트 기준)")
        print(f"📈 일일 손익: {risk_status['daily_pnl']:+,.0f} 원 ({risk_status['daily_pnl_rate']:+.2%})")
        print(f"🎯 승률: {risk_status['win_rate']:.1%} / Kelly: {risk_status['kelly_fraction']:.1%}")
        
        # 거래 통계
        trade_stats = self.strategy.get_trade_statistics()
        print(f"🔄 오늘 거래: {trade_stats['trades_today']}/{self.strategy.max_trades_per_day}")
        print(f"📦 활성 포지션: {trade_stats['active_positions']}/{self.risk_manager.max_positions}")
        
        # 포지션 상태
        if self.risk_manager.positions:
            print("\n📌 보유 포지션:")
            for symbol, position in self.risk_manager.positions.items():
                current_price = pyupbit.get_current_price(f"KRW-{symbol}")
                if current_price:
                    pnl = (current_price - position['entry_price']) / position['entry_price'] * 100
                    holding_time = (datetime.now() - position['entry_time']).total_seconds() / 3600
                    print(f"  {symbol}: {pnl:+.2f}% (보유 {holding_time:.1f}시간)")
        
        # 경고 메시지
        if risk_status['consecutive_losses'] > 0:
            print(f"⚠️ 연속 손실: {risk_status['consecutive_losses']}회")
        
        if risk_status['daily_pnl_rate'] < -0.03:
            print("⚠️ 일일 손실 주의!")
        
        print("="*60)
    
    def run(self):
        """메인 실행 루프 - ✅ 2번 수정: Adaptive Preset Manager 통합"""
        logger.info("="*60)
        logger.info("트레이딩 봇 시작")
        logger.info(f"초기 자본: {self.balance:,.0f} KRW")
        logger.info(f"거래 대상: {', '.join(TRADING_PAIRS)}")
        logger.info("="*60)
        
        last_status_time = time.time()
        status_interval = 300  # 5분마다 상태 출력
        last_save_time = time.time()
        save_interval = 60  # 1분마다 포지션 저장
        preset_check_interval = ADAPTIVE_PRESET_CONFIG.get('check_interval', 3600)  # ✅ 추가!
    
        
        # ✅ 프리셋 자동 조정 간격
        preset_check_interval = ADAPTIVE_PRESET_CONFIG.get('check_interval', 3600)  # 기본 1시간
        
        while True:
            try:
                # 일일 손실 한도 체크
                if self.risk_manager.check_daily_loss_limit():
                    logger.warning("일일 손실 한도 도달. 거래 중단.")
                    time.sleep(3600)  # 1시간 대기
                    continue
                
                # ✅ Adaptive Preset Manager - 자동 프리셋 조정
                if self.preset_manager and ADAPTIVE_PRESET_CONFIG['enabled']:
                    current_time = time.time()
                    
                    # 주기적 체크 (기본 1시간)
                    if current_time - self.last_preset_check >= preset_check_interval:
                        logger.info("\n" + "="*60)
                        logger.info("🔍 자동 프리셋 조정 체크")
                        logger.info("="*60)
                        
                        try:
                            # 시장 분석 및 프리셋 추천
                            recommendation = self.preset_manager.auto_adjust_preset(TRADING_PAIRS)
                            self.last_preset_check = current_time
                            
                            # ✅ 강제 전환 조건 체크
                            force_config = ADAPTIVE_PRESET_CONFIG.get('force_conservative_on', {})
                            
                            # 1. 연속 손실로 인한 강제 전환
                            consecutive = recommendation.get('consecutive_result', {})
                            if consecutive.get('type') == 'loss':
                                loss_count = consecutive.get('count', 0)
                                threshold = force_config.get('consecutive_losses', 4)
                                
                                if loss_count >= threshold:
                                    logger.warning(f"\n{'='*60}")
                                    logger.warning(f"🚨 연속 {loss_count}회 손실 감지!")
                                    logger.warning(f"   임계값: {threshold}회")
                                    logger.warning(f"   → 즉시 보수적 모드로 강제 전환")
                                    logger.warning(f"{'='*60}\n")
                                    
                                    self.preset_manager.switch_preset('conservative', force=True)
                            
                            # 2. 일일 손실률로 인한 강제 전환
                            risk_status = self.risk_manager.get_risk_status()
                            daily_loss_rate = abs(risk_status.get('daily_pnl_rate', 0))
                            loss_threshold = force_config.get('daily_loss_rate', 0.03)
                            
                            if daily_loss_rate >= loss_threshold:
                                logger.warning(f"\n{'='*60}")
                                logger.warning(f"🚨 일일 손실률 {daily_loss_rate:.1%} 초과!")
                                logger.warning(f"   임계값: {loss_threshold:.1%}")
                                logger.warning(f"   → 즉시 보수적 모드로 강제 전환")
                                logger.warning(f"{'='*60}\n")
                                
                                self.preset_manager.switch_preset('conservative', force=True)
                            
                            # 3. 고변동성으로 인한 강제 전환
                            market_analysis = self.preset_manager.analyze_market_condition(TRADING_PAIRS)
                            volatility = market_analysis.get('volatility', 0)
                            vol_threshold = force_config.get('high_volatility', 0.05)
                            
                            if volatility >= vol_threshold:
                                logger.warning(f"\n{'='*60}")
                                logger.warning(f"🚨 고변동성 감지: {volatility:.1%}")
                                logger.warning(f"   임계값: {vol_threshold:.1%}")
                                logger.warning(f"   → 즉시 보수적 모드로 강제 전환")
                                logger.warning(f"{'='*60}\n")
                                
                                self.preset_manager.switch_preset('conservative', force=True)
                            
                        except Exception as e:
                            logger.error(f"프리셋 조정 중 오류: {e}")
                            import traceback
                            logger.error(traceback.format_exc())
                
                # 동적 코인 업데이트 (6시간마다)
                self.update_trading_pairs()
                
                # 청산 조건 체크
                self.check_exit_conditions()
                
                # 새로운 거래 기회 탐색
                if self.strategy.can_trade_today():
                    self.analyze_and_trade()
                
                # 주기적 상태 출력
                if time.time() - last_status_time > status_interval:
                    self.print_status()
                    last_status_time = time.time()
                
                # 주기적으로 포지션 저장
                if time.time() - last_save_time > save_interval:
                    self.save_current_positions()
                    last_save_time = time.time()
                
                # 대기
                time.sleep(60)  # 1분 대기
                
                # 매일 자정 리셋
                current_time = datetime.now()
                if current_time.hour == 0 and current_time.minute == 0:
                    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
                    self.daily_summary.finalize_day(yesterday)                    
                    self.risk_manager.reset_daily_stats()
                    logger.info("일일 통계 리셋 및 저장 완료")
                
            except KeyboardInterrupt:
                logger.info("봇 종료 중... 포지션 저장")
                self.save_current_positions()
                break
                
            except Exception as e:
                logger.error(f"예상치 못한 오류: {e}")
                time.sleep(60)
        
        # 종료 시 최종 상태 출력
        self.print_status()
        logger.info("트레이딩 봇 종료")

    def force_sell(self, symbol, current_price):
        """강제 매도 (보유시간 무시)"""
        ticker = f"KRW-{symbol}"
        quantity = self.get_position_quantity(symbol)
        
        if quantity > 0:
            try:
                order = self.upbit.sell_market_order(ticker, quantity)
                if order:
                    self.strategy.record_trade(symbol, 'sell')
                    self.risk_manager.update_position(symbol, current_price, quantity, 'sell')
                    logger.info(f"🔴 강제 손절: {symbol} @ {current_price:,.0f} KRW")
                    
                    # 보유시간 기록 제거
                    if symbol in self.strategy.position_entry_time:
                        del self.strategy.position_entry_time[symbol]
                    
                    return True
            except Exception as e:
                logger.error(f"강제 손절 실패: {e}")
        
        return False

    def force_sell_all_positions(self):
        """강제로 모든 포지션 청산 (보유시간 무시)"""
        logger.info("강제 청산 모드 시작")
        
        for symbol in list(self.risk_manager.positions.keys()):
            ticker = f"KRW-{symbol}"
            
            try:
                # 보유 수량 조회
                quantity = self.get_position_quantity(symbol)
                
                if quantity > 0:
                    # 직접 매도 주문 실행 (strategy 체크 우회)
                    order = self.upbit.sell_market_order(ticker, quantity)
                    
                    if order:
                        logger.info(f"✅ 강제 청산 완료: {symbol}")
                        
                        # 포지션 정보 제거
                        if symbol in self.risk_manager.positions:
                            del self.risk_manager.positions[symbol]
                        if symbol in self.strategy.position_entry_time:
                            del self.strategy.position_entry_time[symbol]
                    else:
                        logger.error(f"❌ 강제 청산 실패: {symbol}")
                else:
                    logger.info(f"{symbol}: 보유 수량 없음")
                    
            except Exception as e:
                logger.error(f"{symbol} 청산 오류: {e}")
        
        logger.info("강제 청산 완료")

def test_run(bot):
    """테스트 모드 실행"""
    print("\n테스트 모드 - 실제 거래 없이 신호만 확인")
    print("종료하려면 Ctrl+C를 누르세요.\n")
    
    while True:
        try:
            print(f"\n⏰ {datetime.now().strftime('%H:%M:%S')}")
            
            for symbol in TRADING_PAIRS:
                ticker = f"KRW-{symbol}"
                indicators = bot.calculate_indicators(ticker)
                
                if indicators:
                    print(f"\n📊 {symbol} 분석:")
                    print(f"   가격: {indicators['price']:,.0f}")
                    print(f"   RSI: {indicators['rsi']:.1f}")
                    print(f"   추세: {indicators['trend']}")
                    print(f"   변동성: {indicators['volatility']:.3f}")
                    print(f"   거래량 비율: {indicators['volume_ratio']:.1f}")
                    
                    # 진입 신호 체크
                    can_enter, reason = bot.strategy.should_enter_position(symbol, indicators)
                    
                    if can_enter:
                        print(f"   🟢 매수 신호! - {reason}")
                        print(f"   기대수익: {indicators['expected_return']:.1%}")
                    else:
                        print(f"   ⚪ {reason}")
            
            print("\n" + "-"*60)
            time.sleep(60)  # 1분 대기
            
        except KeyboardInterrupt:
            print("\n테스트 종료")
            break
        except Exception as e:
            print(f"오류: {e}")
            time.sleep(60)

# 실행 스크립트
if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    
    # 환경변수 로드
    load_dotenv()
    
    access_key = os.getenv('UPBIT_ACCESS_KEY')
    secret_key = os.getenv('UPBIT_SECRET_KEY')
    
    if not access_key or not secret_key:
        print("❌ API 키를 설정해주세요.")
        print("\n설정 방법:")
        print("1. .env 파일 생성")
        print("2. UPBIT_ACCESS_KEY=your_key")
        print("3. UPBIT_SECRET_KEY=your_secret")
        exit(1)
    
    print("="*60)
    print("🤖 업비트 자동매매 봇 v2.0 (개선판)")
    print("="*60)
    print("\n주요 개선사항:")
    print("✅ 거래 빈도 최적화 - 일 10회 제한, 최소 1시간 홀딩")
    print("✅ 진입 조건 강화 - 7점 이상 스코어링 시스템")
    print("✅ 리스크 관리 강화 - Kelly Criterion, 추적손절, 연속손실 관리")
    print("✅ 실제 체결가 반영 - 정확한 PnL 계산")
    print("✅ 자동 프리셋 전환 - 시장 상황에 따라 자동 조정")
    
    # 봇 초기화
    bot = TradingBot(access_key, secret_key)
    
    # 기존 포지션 처리 옵션
    if bot.risk_manager.positions:
        print("\n" + "="*50)
        print("📦 기존 포지션 발견:")
        for symbol, pos in bot.risk_manager.positions.items():
            current_price = pyupbit.get_current_price(f"KRW-{symbol}")
            if current_price:
                pnl = (current_price - pos['entry_price']) / pos['entry_price'] * 100
                print(f"  {symbol}: {pnl:+.2f}% (진입가: {pos['entry_price']:,.0f})")
        
        print("\n어떻게 처리하시겠습니까?")
        print("1. 기존 포지션 유지하고 계속")
        print("2. 모든 포지션 강제 청산 (보유시간 무시)")
        print("3. 선택적으로 청산")
        
        choice = input("\n선택 (1/2/3): ").strip()
        
        if choice == '2':
            print("모든 포지션 강제 청산 중...")
            bot.force_sell_all_positions()
            
        elif choice == '3':
            for symbol in list(bot.risk_manager.positions.keys()):
                sell = input(f"{symbol} 청산? (y/n): ").strip().lower()
                if sell == 'y':
                    # 개별 강제 청산
                    ticker = f"KRW-{symbol}"
                    quantity = bot.get_position_quantity(symbol)
                    if quantity > 0:
                        bot.upbit.sell_market_order(ticker, quantity)
                        del bot.risk_manager.positions[symbol]
            
        print("="*50)
    
    # 테스트 모드 선택
    print("\n실행 모드를 선택하세요:")
    print("1. 테스트 모드 (거래 없이 신호만 확인)")
    print("2. 실전 모드 (실제 거래 실행)")
    
    mode = input("\n선택 (1 또는 2): ").strip()
    
    if mode == '1':
        print("\n📊 테스트 모드로 실행합니다...")
        test_run(bot)
    elif mode == '2':
        print("\n⚠️ 실제 자금으로 거래가 실행됩니다!")
        confirm = input("정말 실전 거래를 시작하시겠습니까? (yes 입력): ")
        if confirm.lower() == 'yes':
            print("\n🚀 실전 모드로 실행합니다...")
            bot.run()
        else:
            print("거래 취소")
    else:
        print("잘못된 선택입니다.")