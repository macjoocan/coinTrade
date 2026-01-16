# main_trading_bot.py - 수정 완료 버전
import pyupbit
import time
import logging
from datetime import datetime, timedelta
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
from slippage_manager import SlippageManager  # 🆕 슬리피지 관리자
from volatility_monitor import VolatilityMonitor  # 🆕 변동성 모니터
from score_performance_tracker import ScorePerformanceTracker  # 🆕 점수별 성과 추적
from auto_optimizer import optimize_on_startup  # 🆕 자동 최적화
from swing_holding_enhancer import SwingHoldingEnhancer  # 🆕 스윙 홀딩 강화

from config import (
    TRADING_PAIRS,
    STRATEGY_CONFIG,
    RISK_CONFIG,
    ADVANCED_CONFIG,
    STABLE_PAIRS,
    DYNAMIC_COIN_CONFIG,
    AVERAGING_DOWN_CONFIG,
    UPBIT_CONFIG,
    apply_preset,  # ✅ 함수 import
    ACTIVE_PRESET,  # ✅ 활성 프리셋 import
    SLIPPAGE_CONFIG,  # 🆕 슬리피지 설정
    VOLATILITY_CONFIG  # 🆕 변동성 설정
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
        
        # 전략 및 리스크 매니저 초기화
        self.strategy = ImprovedStrategy()
        self.risk_manager = RiskManager(self.balance)
        
        if hasattr(self.risk_manager, 'need_total_balance_update') and \
           self.risk_manager.need_total_balance_update:
            
            total_balance = self.get_accurate_balance()
            self.risk_manager.initial_balance = total_balance
            self.risk_manager.need_total_balance_update = False
            
            logger.info("")
            logger.info("="*60)
            logger.info("✅ 총 자산 계산 완료!")
            logger.info(f"📊 KRW 잔고: {self.balance:,.0f}원")
            logger.info(f"💰 총 자산(코인 포함): {total_balance:,.0f}원")
            logger.info(f"🎉 초기 자본 최종 설정: {total_balance:,.0f}원")
            logger.info("💡 과거 손실이 무시됩니다!")
            logger.info("="*60)
            logger.info("") 
            # 파일에 저장
            try:
                with open("initial_balance.txt", 'w') as f:
                    f.write(str(total_balance))
                logger.info("✅ initial_balance.txt 파일 저장 완료")
            except Exception as e:
                logger.error(f"⚠️ 파일 저장 실패: {e}")
            
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

        # ✅ 물타기 매니저 추가 (여기에 추가!)
        self.averaging_manager = AveragingDownManager(AVERAGING_DOWN_CONFIG)
        if AVERAGING_DOWN_CONFIG['enabled']:
            logger.info("💧 물타기 시스템 활성화")
            logger.info(f"   트리거: {AVERAGING_DOWN_CONFIG['trigger_loss_rate']:.1%}")
            logger.info(f"   최대 횟수: {AVERAGING_DOWN_CONFIG['max_averaging_count']}회")
        else:
            logger.info("💧 물타기 시스템 비활성화")

        # ✅ 자동 프리셋 매니저 추가
        if ADAPTIVE_PRESET_CONFIG['enabled']:
            self.preset_manager = AdaptivePresetManager(ADAPTIVE_PRESET_CONFIG)
            logger.info("🤖 자동 프리셋 전환 시스템 활성화")
        else:
            self.preset_manager = None

        self.last_preset_check = time.time()

        # 🆕 슬리피지 관리자 추가
        if SLIPPAGE_CONFIG['enabled']:
            self.slippage_manager = SlippageManager()
            logger.info("📊 슬리피지 관리 시스템 활성화")
            logger.info(f"   최대 허용 슬리피지: {SLIPPAGE_CONFIG['max_slippage_rate']:.2%}")
        else:
            self.slippage_manager = None

        # 🆕 변동성 모니터 추가
        if VOLATILITY_CONFIG['enabled']:
            self.volatility_monitor = VolatilityMonitor(VOLATILITY_CONFIG)
            logger.info("🌡️ 변동성 모니터링 시스템 활성화")
            logger.info(f"   업데이트 간격: {VOLATILITY_CONFIG['update_interval']}초")
        else:
            self.volatility_monitor = None

        # 🆕 점수별 성과 추적 추가
        self.score_tracker = ScorePerformanceTracker()
        logger.info("📊 진입 점수별 성과 추적 시스템 활성화")

        self.partial_exit_manager = PartialExitManager()

        # 🆕 스윙 홀딩 강화 시스템 추가
        self.swing_holding = SwingHoldingEnhancer()
        logger.info("🎯 스윙 홀딩 강화 시스템 활성화")
        logger.info(f"   최소 보유: {self.swing_holding.min_swing_hold_hours}시간")
        logger.info(f"   조기 익절 기준: {self.swing_holding.min_profit_for_early_exit:.1%}")

        # ✅ iteration 카운터 초기화
        self.iteration = 0

        logger.info(f"봇 초기화 완료. 초기 자본: {self.balance:,.0f} KRW")

        # 🆕 자동 최적화 실행 (봇 시작 시)
        logger.info("")
        logger.info("🤖 자동 설정 최적화 시작...")
        try:
            optimized, recommendations = optimize_on_startup(
                self.score_tracker,
                auto_apply=False  # False: 추천만, True: 자동 적용
            )

            if optimized:
                logger.info("✅ 설정이 자동으로 최적화되었습니다!")
            elif recommendations:
                logger.info("💡 추천 사항이 있습니다. 위 메시지를 확인하세요.")
            else:
                logger.info("✅ 현재 설정이 최적입니다.")
        except Exception as e:
            logger.error(f"자동 최적화 실패: {e}")
        logger.info("")

    def recover_existing_positions(self):
        """기존 포지션 복구"""
        logger.info("="*50)
        logger.info("🔄 기존 포지션 복구 시작...")

        # 1. 저장된 포지션 로드
        saved_positions = self.position_recovery.load_positions()
        logger.info(f"📁 저장된 포지션 로드: {len(saved_positions)}개")

        # 2. 거래소와 동기화
        recovered = self.position_recovery.sync_with_exchange(saved_positions)
        logger.info(f"🔄 거래소 동기화 완료: {len(recovered)}개 복구")

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

                logger.info(f"✅ 리스크 매니저 등록 완료: {symbol} @ {pos['entry_price']:,.0f} (수량: {pos['quantity']:.8f})")

            logger.info(f"📊 현재 리스크 매니저 포지션: {list(self.risk_manager.positions.keys())}")
        else:
            logger.info("⚠️ 복구된 포지션 없음")

        logger.info(f"✅ 복구 완료: {len(recovered)}개 포지션")
        logger.info("="*50)
    
    def save_current_positions(self):
        """현재 포지션 저장 (주기적으로 호출)"""
        self.position_recovery.save_positions(self.risk_manager.positions)
                
    
    def sync_positions_with_exchange(self):
        """거래소 실제 잔고와 봇 포지션 동기화"""
        logger.info("=" * 60)
        logger.info("🔄 거래소 잔고 동기화 시작...")
        logger.info("=" * 60)
        
        try:
            # 실제 보유 중인 코인 조회
            balances = self.upbit.get_balances()
            actual_holdings = {}
            
            for balance in balances:
                if balance['currency'] != 'KRW':
                    symbol = balance['currency']
                    quantity = float(balance['balance'])
                    avg_price = float(balance['avg_buy_price'])
                    
                    if quantity > 0:
                        actual_holdings[symbol] = {
                            'quantity': quantity,
                            'avg_price': avg_price
                        }
            
            logger.info(f"거래소 실제 보유: {list(actual_holdings.keys())}")
            logger.info(f"봇 인식 포지션: {list(self.risk_manager.positions.keys())}")
            
            # 봇의 포지션과 비교
            bot_positions = set(self.risk_manager.positions.keys())
            actual_positions = set(actual_holdings.keys())
            
            # 1. 봇에는 있지만 거래소에는 없는 포지션 제거
            removed_positions = bot_positions - actual_positions
            for symbol in removed_positions:
                logger.warning(f"⚠️ {symbol}: 거래소에 없음 → 봇 포지션 제거")
                del self.risk_manager.positions[symbol]
                if symbol in self.strategy.position_entry_time:
                    del self.strategy.position_entry_time[symbol]
            
            # 2. 거래소에는 있지만 봇에는 없는 포지션 추가
            new_positions = actual_positions - bot_positions
            for symbol in new_positions:
                logger.info(f"📌 {symbol}: 거래소에서 발견 → 봇에 추가")
                self.risk_manager.positions[symbol] = {
                    'entry_price': actual_holdings[symbol]['avg_price'],
                    'quantity': actual_holdings[symbol]['quantity'],
                    'value': actual_holdings[symbol]['avg_price'] * actual_holdings[symbol]['quantity'],
                    'entry_time': datetime.now(),
                    'highest_price': actual_holdings[symbol]['avg_price']
                }
                self.strategy.position_entry_time[symbol] = time.time()
            
            # 3. 수량 불일치 수정
            for symbol in bot_positions & actual_positions:
                bot_qty = self.risk_manager.positions[symbol]['quantity']
                actual_qty = actual_holdings[symbol]['quantity']
                
                if abs(bot_qty - actual_qty) > 0.00001:  # 부동소수점 오차 고려
                    logger.warning(f"⚠️ {symbol} 수량 불일치 감지")
                    logger.warning(f"   봇 기록: {bot_qty:.8f}")
                    logger.warning(f"   실제: {actual_qty:.8f}")
                    logger.warning(f"   → 실제 수량으로 수정")
                    self.risk_manager.positions[symbol]['quantity'] = actual_qty
                    self.risk_manager.positions[symbol]['value'] =                         self.risk_manager.positions[symbol]['entry_price'] * actual_qty
            
            # 포지션 파일 저장
            self.position_recovery.save_positions(self.risk_manager.positions)
            
            logger.info("=" * 60)
            logger.info("✅ 동기화 완료")
            logger.info(f"현재 포지션: {list(self.risk_manager.positions.keys())}")
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"동기화 실패: {e}")
            import traceback
            logger.error(traceback.format_exc())

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
        import pandas as pd
        import numpy as np
        
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
                'ema_12': df['ema_12'].iloc[-1],
                'ema_26': df['ema_26'].iloc[-1],                
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
            
            # 진입 조건 체크 (🆕 점수도 받음)
            result = self.strategy.should_enter_position(symbol, indicators)
            can_enter, reason, entry_score = result if len(result) == 3 else (result[0], result[1], 0)

            if not can_enter:
                logger.info(f"{symbol}: {reason}")
                return False

            # 🆕 시장 상황 조회
            try:
                from market_condition_check import MarketAnalyzer
                market_analyzer = MarketAnalyzer()
                market_condition = market_analyzer.analyze_market(TRADING_PAIRS)
            except Exception as e:
                logger.warning(f"시장 상황 조회 실패: {e}")
                market_condition = None

            # 리스크 체크 (시장 상황 전달)
            can_trade, risk_reason = self.risk_manager.can_open_new_position(market_condition)
            if not can_trade:
                logger.warning(f"리스크 제한: {risk_reason}")
                return False
                                
            # 포지션 크기 계산
            self.balance = self.get_balance()
            self.risk_manager.current_balance = self.balance
            
            quantity = self.risk_manager.calculate_position_size(
                self.balance, symbol, current_price,
                volatility=indicators.get('volatility'),
                indicators=indicators,
                volatility_monitor=self.volatility_monitor  # 🆕 변동성 모니터 전달
            )
            
            if quantity == 0:
                logger.info("포지션 크기가 너무 작음")
                return False
            
            # 주문 금액 계산
            order_amount = min(current_price * quantity, self.balance * 0.95)

            # 🆕 슬리피지 체크
            if self.slippage_manager:
                is_safe, est_slippage, slip_msg = self.slippage_manager.estimate_slippage(
                    ticker, 'buy', order_amount
                )

                if not is_safe:
                    logger.warning(f"⚠️ {symbol} 매수 취소: {slip_msg}")
                    return False

                logger.info(f"📊 {symbol} 슬리피지 체크: {slip_msg}")

                # 슬리피지 버퍼 적용
                if SLIPPAGE_CONFIG.get('slippage_buffer', 0) > 0:
                    buffer = SLIPPAGE_CONFIG['slippage_buffer']
                    order_amount = order_amount * (1 - buffer)
                    logger.info(f"   슬리피지 버퍼 적용: -{buffer:.1%}")

            # ✅ 실제 매수 실행 - 체결 정보 받기
            try:
                expected_price = current_price  # 슬리피지 기록용
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

                    # 🆕 포지션에 진입 점수 저장
                    if symbol in self.risk_manager.positions:
                        self.risk_manager.positions[symbol]['entry_score'] = entry_score
                        logger.info(f"📊 진입 점수 기록: {entry_score:.2f}/10")

                    self.daily_summary.record_trade({
                        'symbol': symbol,
                        'type': 'buy',
                        'price': actual_price,
                        'quantity': actual_quantity
                    })

                    # 🆕 실제 슬리피지 기록
                    if self.slippage_manager:
                        self.slippage_manager.record_actual_slippage(
                            symbol, expected_price, actual_price, 'buy', order_amount
                        )

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

            # 🆕 슬리피지 체크 (매도)
            if self.slippage_manager:
                order_value = current_price * quantity
                is_safe, est_slippage, slip_msg = self.slippage_manager.estimate_slippage(
                    ticker, 'sell', order_value
                )

                if not is_safe:
                    logger.warning(f"⚠️ {symbol} 매도 슬리피지 경고: {slip_msg}")
                    # 매도는 손절/익절이므로 슬리피지가 높아도 실행
                else:
                    logger.info(f"📊 {symbol} 슬리피지 체크: {slip_msg}")

            # 실제 매도 실행
            try:
                expected_price = current_price  # 슬리피지 기록용
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
                    self.strategy.record_trade(symbol, 'sell', pnl=real_pnl)  # 🎯 손익비 개선: PnL 전달
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

                    # 🆕 실제 슬리피지 기록 (매도)
                    if self.slippage_manager:
                        self.slippage_manager.record_actual_slippage(
                            symbol, expected_price, actual_price, 'sell',
                            actual_price * actual_quantity
                        )

                    # 🆕 점수별 성과 추적 기록
                    entry_score = position.get('entry_score', 0)
                    if entry_score > 0:
                        self.score_tracker.record_trade(
                            entry_score=entry_score,
                            pnl=real_pnl,
                            pnl_rate=pnl_rate,
                            symbol=symbol,
                            entry_price=entry_price,
                            exit_price=actual_price
                        )
                        logger.info(f"📊 점수별 성과 기록: {entry_score:.2f}점 → {pnl_rate:+.2%}")

                    logger.info(f"🔴 매도 완료: {symbol} @ {actual_price:,.2f} KRW "
                                f"(PnL {real_pnl:+,.2f}, {pnl_rate:+.2%})")

                    # ✅ 물타기 기록 삭제
                    self.averaging_manager.clear_history(symbol)

                    return True
                    
            except Exception as e:
                logger.error(f"매도 실패: {e}")
                import traceback
                logger.error(traceback.format_exc())

        return False

    def check_averaging_down_opportunity(self):
        """물타기 기회 체크 - ✅ 시장 상황 체크 추가"""
        
        if not AVERAGING_DOWN_CONFIG['enabled']:
            return
        
        # ✅ 시장 상황 조회 (최우선!)
        from market_condition_check import MarketAnalyzer
        market_analyzer = MarketAnalyzer()
        market_condition = market_analyzer.analyze_market(TRADING_PAIRS)
        
        # ✅ 하락장이면 물타기 전체 건너뜀
        if AVERAGING_DOWN_CONFIG.get('disable_on_bear_market', True):
            if market_condition == 'bearish':
                logger.warning("💧 물타기 체크 건너뜀: 현재 하락장")
                logger.warning("   → 시장이 회복될 때까지 물타기 비활성화")
                return
        
        for symbol in list(self.risk_manager.positions.keys()):
            position = self.risk_manager.positions[symbol]
            ticker = f"KRW-{symbol}"
            
            try:
                # 안정 코인만 체크
                if AVERAGING_DOWN_CONFIG['only_stable_coins']:
                    if symbol not in STABLE_PAIRS:
                        continue
                
                # 현재가 조회
                current_price = pyupbit.get_current_price(ticker)
                if not current_price:
                    continue
                
                # ✅ 시장 상황을 파라미터로 전달!
                should_avg, reason = self.averaging_manager.should_average_down(
                    symbol, position, current_price, market_condition
                )
                
                if should_avg:
                    logger.info(f"💧 {symbol} 물타기 신호 발생!")
                    self.execute_averaging_down(symbol, current_price)
                
            except Exception as e:
                logger.error(f"{symbol} 물타기 체크 실패: {e}")

    def execute_averaging_down(self, symbol, current_price):
            """물타기 실행"""
            ticker = f"KRW-{symbol}"
            position = self.risk_manager.positions[symbol]
            
            try:
                # 원래 포지션 가치
                original_value = position['entry_price'] * position['quantity']
                
                # 물타기 금액 계산
                avg_amount = self.averaging_manager.calculate_averaging_size(
                    symbol, original_value
                )
                
                # 최소 주문 금액 체크 (업비트: 5,000원 초과 필요)
                MIN_ORDER_AMOUNT = UPBIT_CONFIG['min_order_amount']
                if avg_amount < MIN_ORDER_AMOUNT:
                    logger.warning(f"💧 {symbol} 물타기 불가: 최소 금액 미달")
                    logger.warning(f"   계산 금액: {avg_amount:,.0f} KRW")
                    logger.warning(f"   최소 필요: {MIN_ORDER_AMOUNT:,.0f} KRW")
                    logger.warning(f"   → 물타기 건너뜀")
                    return False
                
                # 자금 체크
                self.balance = self.get_balance()
                min_balance_ratio = AVERAGING_DOWN_CONFIG.get('min_balance_ratio', 0.3)
                
                if avg_amount > self.balance * (1 - min_balance_ratio):
                    logger.warning(f"💧 {symbol} 물타기 자금 부족")
                    logger.warning(f"   필요 금액: {avg_amount:,.0f}")
                    logger.warning(f"   사용 가능: {self.balance * (1 - min_balance_ratio):,.0f}")
                    return False
                
                logger.info(f"💧 {symbol} 물타기 실행 중...")
                logger.info(f"   원래 평단: {position['entry_price']:,.0f} KRW")
                logger.info(f"   현재가: {current_price:,.0f} KRW")
                logger.info(f"   물타기 금액: {avg_amount:,.0f} KRW")
                
                # 매수 주문
                order = self.upbit.buy_market_order(ticker, avg_amount)
                
                # ✅ 주문 실패 처리
                if not order:
                    logger.error(f"💧 {symbol} 물타기 실패: 주문 응답 없음")
                    return False
                
                # ✅ 오류 체크
                if 'error' in order:
                    error_info = order.get('error', {})
                    logger.error(f"💧 물타기 실패: {error_info.get('message')}")
                    # ❌ 아래의 포지션 정보 갱신(update) 코드들을 삭제하거나 성공 시점으로 옮겨야 합니다.
                    # error_info = order.get('error', {})
                    # error_name = error_info.get('name', 'Unknown')
                    # error_msg = error_info.get('message', 'Unknown error')
                    
                    # logger.error(f"💧 {symbol} 물타기 실패: {error_name}")
                    # logger.error(f"   메시지: {error_msg}")

                    # # 포지션 정보 갱신
                    # self.risk_manager.positions[symbol].update({
                    #     'entry_price': new_avg_price,
                    #     'quantity': new_total_quantity,
                    #     'value': new_avg_price * new_total_quantity
                    # })

                    # # ✅ 추적 손절 데이터 갱신 (새로운 평단 기준으로)
                    # if 'high_price' in self.risk_manager.positions[symbol]:
                    #     current_high = self.risk_manager.positions[symbol]['high_price']
                    #     if current_high < new_avg_price:
                    #         self.risk_manager.positions[symbol]['high_price'] = new_avg_price
                    #         logger.info(f"   추적 손절 최고가 갱신: {current_high:,.0f} → {new_avg_price:,.0f}")
                            
                    # # UnderMinTotalBid 상세 설명
                    # if 'UnderMinTotalBid' in error_name:
                    #     logger.error(f"   → 최소 주문 금액 미달!")
                    #     logger.error(f"   → 시도 금액: {avg_amount:,.0f}원")
                    #     logger.error(f"   → 최소 필요: 5,500원 이상")
                    
                    return False
                
                # ✅ uuid 체크
                if 'uuid' not in order:
                    logger.error(f"💧 {symbol} 물타기 실패: UUID 없음")
                    logger.error(f"   Order response: {order}")
                    return False
                
                time.sleep(0.5)
                order_detail = self.upbit.get_order(order['uuid'])
                
                if order_detail:
                    executed_volume = float(order_detail.get('executed_volume', 0))
                    paid_fee = float(order_detail.get('paid_fee', 0))
                    
                    if executed_volume > 0:
                        # 실제 평균 체결가
                        actual_price = (avg_amount - paid_fee) / executed_volume
                        
                        # 물타기 기록
                        self.averaging_manager.record_averaging(
                            symbol, actual_price, executed_volume, avg_amount
                        )
                        
                        # 새로운 평균가 계산
                        original_entry = position['entry_price']
                        original_qty = position['quantity']
                        
                        new_avg_price = self.averaging_manager.calculate_average_price(
                            symbol, original_entry, original_qty
                        )
                        new_total_quantity = original_qty + executed_volume
                        
                        # 포지션 정보 갱신
                        self.risk_manager.positions[symbol].update({
                            'entry_price': new_avg_price,
                            'quantity': new_total_quantity,
                            'value': new_avg_price * new_total_quantity
                        })
                        
                        # 성공 로그
                        avg_count = len(self.averaging_manager.averaging_history.get(symbol, []))
                        price_drop = ((new_avg_price - original_entry) / original_entry * 100)
                        
                        logger.info(f"")
                        logger.info(f"{'='*60}")
                        logger.info(f"💧 {symbol} 물타기 완료! ({avg_count}차)")
                        logger.info(f"{'='*60}")
                        logger.info(f"기존 평단가: {original_entry:,.0f} KRW")
                        logger.info(f"새 평단가:  {new_avg_price:,.0f} KRW")
                        logger.info(f"평단 하락:  {price_drop:.2f}%")
                        logger.info(f"기존 수량:  {original_qty:.8f}")
                        logger.info(f"추가 수량:  {executed_volume:.8f}")
                        logger.info(f"총 수량:    {new_total_quantity:.8f}")
                        logger.info(f"{'='*60}")
                        logger.info(f"")
                        
                        return True
                
            except Exception as e:
                logger.error(f"💧 {symbol} 물타기 실패: {e}")
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
    
    def _process_sell_order(self, symbol, order_uuid, entry_price, entry_time, quantity, current_price):
        """매도 주문 처리 공통 로직"""
        try:
            # 체결 대기
            time.sleep(0.5)
            
            # 주문 상세 조회
            order_detail = self.upbit.get_order(order_uuid)
            
            if not order_detail:
                logger.error("주문 상세 정보 조회 실패")
                actual_price = current_price
                actual_quantity = quantity
                paid_fee = 0
            elif order_detail.get('state') != 'done':
                logger.warning(f"주문 미체결 상태: {order_detail.get('state')}")
                actual_price = current_price
                actual_quantity = quantity
                paid_fee = 0
            else:
                # 체결 완료 - 정확한 정보 파싱
                executed_volume = float(order_detail.get('executed_volume', 0))
                paid_fee = float(order_detail.get('paid_fee', 0))
                
                trades = order_detail.get('trades', [])
                
                if trades and executed_volume > 0:
                    total_received = sum(
                        float(t.get('price', 0)) * float(t.get('volume', 0)) 
                        for t in trades
                    )
                    actual_price = total_received / executed_volume
                    actual_quantity = executed_volume
                else:
                    actual_price = current_price
                    actual_quantity = quantity
            
            # PnL 계산
            buy_cost = entry_price * actual_quantity
            sell_revenue = actual_price * actual_quantity * 0.9995  # 수수료 0.05%
            real_pnl = sell_revenue - buy_cost
            pnl_rate = (real_pnl / buy_cost) if buy_cost > 0 else 0.0
            
            # 보유 시간 계산
            if isinstance(entry_time, str):
                entry_dt = datetime.fromisoformat(entry_time)
            else:
                entry_dt = entry_time
            hold_time_hours = (datetime.now() - entry_dt).total_seconds() / 3600
            
            # 거래 기록 데이터 반환
            trade_data = {
                'timestamp': datetime.now().isoformat(),
                'symbol': symbol,
                'type': 'sell',
                'entry_price': entry_price,
                'exit_price': actual_price,
                'quantity': actual_quantity,
                'pnl': real_pnl,
                'pnl_rate': pnl_rate,
                'fee': paid_fee,
                'hold_time_hours': hold_time_hours
            }
            
            return trade_data, actual_price, real_pnl, pnl_rate
            
        except Exception as e:
            logger.error(f"매도 주문 처리 오류: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None, current_price, 0, 0

    def is_averaging_completed(self, symbol):
        """물타기가 완료되었는지 체크"""
        
        if not AVERAGING_DOWN_CONFIG['enabled']:
            return True
        
        avg_info = self.averaging_manager.get_averaging_info(symbol)
        avg_count = avg_info['count']
        max_count = AVERAGING_DOWN_CONFIG['max_averaging_count']
        
        return avg_count >= max_count

    def force_close_all_positions(self, reason=""):  # ✅ 여기부터 추가!
        """모든 포지션 강제 청산"""
        logger.warning(f"")
        logger.warning(f"{'='*60}")
        logger.warning(f"🚨 긴급 강제 청산 시작")
        logger.warning(f"사유: {reason}")
        logger.warning(f"{'='*60}")
        
        closed_count = 0
        
        for symbol in list(self.risk_manager.positions.keys()):
            try:
                ticker = f"KRW-{symbol}"
                current_price = pyupbit.get_current_price(ticker)
                
                if not current_price:
                    logger.warning(f"{symbol}: 현재가 조회 실패, 건너뜀")
                    continue
                
                position = self.risk_manager.positions[symbol]
                entry_price = position['entry_price']
                loss_rate = (current_price - entry_price) / entry_price
                
                logger.warning(f"🚨 {symbol} 강제 청산 시도 (손실률: {loss_rate:.2%})")
                
                # 강제 매도 실행
                success = self.execute_trade(symbol, 'sell', current_price, force_stop_loss=True)
                
                if success:
                    closed_count += 1
                    logger.info(f"✅ {symbol} 청산 완료")
                else:
                    logger.error(f"❌ {symbol} 청산 실패")
                    
            except Exception as e:
                logger.error(f"{symbol} 강제 청산 오류: {e}")
        
        logger.warning(f"")
        logger.warning(f"{'='*60}")
        logger.warning(f"🚨 강제 청산 완료: {closed_count}개 포지션")
        logger.warning(f"{'='*60}")
        logger.warning(f"")
        
        return closed_count
    
    def check_exit_conditions(self):
            """개선된 청산 조건 체크 - 배치 API 호출 최적화"""

            MIN_ORDER_VALUE = UPBIT_CONFIG['min_order_value']

            # 소액 포지션 경고 시간 추적
            if not hasattr(self, 'last_small_position_warning'):
                self.last_small_position_warning = {}

            # 배치 가격 조회 (최적화!)
            symbols = list(self.risk_manager.positions.keys())

            # 🔍 디버깅: 포지션 체크 시작
            if symbols:
                logger.info(f"🔍 청산 조건 체크 시작: {len(symbols)}개 포지션 ({', '.join(symbols)})")

            if not symbols:
                return
            
            tickers = [f"KRW-{s}" for s in symbols]
            current_prices = pyupbit.get_current_price(tickers)
            
            # 단일 심볼인 경우 dict로 변환
            if len(symbols) == 1 and not isinstance(current_prices, dict):
                current_prices = {tickers[0]: current_prices}
            
            for symbol in symbols:
                try:
                    ticker = f"KRW-{symbol}"
                    current_price = current_prices.get(ticker)

                    if not current_price:
                        logger.warning(f"⚠️ {symbol}: 현재가 조회 실패")
                        continue

                    position = self.risk_manager.positions[symbol]
                    entry_price = position['entry_price']
                    entry_time = position['entry_time']

                    # ✅ 현재 보유 수량 먼저 조회
                    current_quantity = self.get_position_quantity(symbol)

                    # 🔍 디버깅: 포지션 상태 출력
                    pnl_rate = (current_price - entry_price) / entry_price
                    logger.info(f"  📊 {symbol}: 진입가 {entry_price:,.0f} → 현재가 {current_price:,.0f} ({pnl_rate:+.2%}) | 수량: {current_quantity:.8f}")

                    # ✅ 소액 포지션 체크 (최우선)
                    current_value = current_price * current_quantity
                    if current_value < MIN_ORDER_VALUE:
                        # 10분마다 경고
                        now = time.time()
                        last_warn = self.last_small_position_warning.get(symbol, 0)
                        
                        if now - last_warn > 600:  # 10분(600초) 경과
                            logger.warning(f"{symbol}: 소액 포지션 ({current_value:,.0f}원 < {MIN_ORDER_VALUE:,}원)")
                            logger.warning(f"   → 매도 불가, 가격 상승 대기 중...")
                            self.last_small_position_warning[symbol] = now
                        
                        continue  # ✅ 손절/익절 시도 안함
                    
                    # 현재 손실률 계산
                    loss_rate = (current_price - entry_price) / entry_price
                    
                    # 1. 부분 매도 체크 (최우선)
                    # 분할 매도 체크 강화
                    partial_exit, sold_quantity = self.partial_exit_manager.check_partial_exit(
                        symbol, entry_price, entry_time, current_price, current_quantity, self.upbit
                    )

                    if partial_exit:
                        # 50%를 팔았으므로 리스크 매니저의 수량 갱신
                        self.risk_manager.positions[symbol]['quantity'] -= sold_quantity
                        # ✅ 중요: 분할 매도 직후 손절가를 본절가로 이동하여 남은 물량 리스크 제거
                        self.risk_manager.positions[symbol]['entry_price'] = entry_price # 평단 유지
                        self.risk_manager.stop_loss = -0.002 # 남은 물량은 본절 시 바로 던짐
                        logger.info(f"✅ {symbol} 1차 분할 익절 완료. 남은 물량 본절 방어 모드 진입")
                    
                    # 2. ✅ 손절 체크 (보유시간 무시) - force_stop_loss=True 전달
                    if self.risk_manager.check_stop_loss(
                        symbol, current_price, self.averaging_manager,
                        self.volatility_monitor  # 🆕 변동성 모니터 전달
                    ):
                        logger.warning(f"{symbol}: 🚨 손절 발동 (손실률: {loss_rate:.2%}) - 즉시 실행")
                        self.execute_trade(symbol, 'sell', current_price, force_stop_loss=True)
                        self.partial_exit_manager.reset_position(symbol)
                        continue
                    
                    # 3. 추적 손절 체크 (수정 버전) + 🆕 스윙 홀딩 통합
                    if self.risk_manager.check_trailing_stop(symbol, current_price):
                        # ✅ 현재 수익/손실 상태 확인
                        position = self.risk_manager.positions[symbol]
                        entry_price = position['entry_price']
                        current_pnl_rate = (current_price - entry_price) / entry_price

                        # 🆕 스윙 홀딩 체크 - 조기 익절 방지
                        swing_allow, swing_reason = self.swing_holding.should_allow_exit(
                            symbol, entry_time, current_pnl_rate, exit_reason='trailing_stop'
                        )

                        if not swing_allow:
                            logger.info(f"{symbol}: 추적 손절 신호이지만 스윙 홀딩 중")
                            logger.info(f"   🎯 {swing_reason}")
                            logger.info(f"   현재 수익: {current_pnl_rate:+.2%}")
                            continue  # 스윙 홀딩으로 매도 거부

                        # 🎯 수익 확정 기준 상향: 2.0% 이상에서만 강제 익절
                        # (기존 1.2%는 너무 낮아서 큰 수익 기회를 놓침)
                        if current_pnl_rate >= 0.020:  # 기존 0.012 → 0.020
                            logger.warning(f"{symbol}: 🎯 목표 수익 달성 (+{current_pnl_rate*100:.2f}%)")
                            logger.warning(f"   → 스윙 홀딩 허용: {swing_reason}")
                            self.execute_trade(symbol, 'sell', current_price)
                            self.partial_exit_manager.reset_position(symbol)
                            self.averaging_manager.clear_history(symbol)
                            continue

                        # ✅ 물타기 완료 여부에 따른 기존 처리
                        if self.is_averaging_completed(symbol):
                            # 물타기 완료 → 추적 손절 실행 (수익 보호)
                            logger.warning(f"{symbol}: 🎯 물타기 완료 후 추적 손절 실행")
                            logger.info(f"   현재 수익률: {current_pnl_rate*100:+.2f}%")
                            self.execute_trade(symbol, 'sell', current_price)
                            self.partial_exit_manager.reset_position(symbol)
                            self.averaging_manager.clear_history(symbol)
                            continue
                        else:
                            # 물타기 진행 중 → 1.2% 미만 수익이나 손실 상태에서의 처리
                            avg_info = self.averaging_manager.get_averaging_info(symbol)
                            
                            if current_pnl_rate > 0:
                                # 0% ~ 1.2% 사이의 낮은 수익 상태: 물타기 기회를 위해 일단 홀딩
                                logger.info(f"{symbol}: 추적 손절 신호 감지 (현재 수익: +{current_pnl_rate*100:.2f}%)")
                                logger.info(f"   📊 물타기 잔여: {avg_info['count']}/{AVERAGING_DOWN_CONFIG['max_averaging_count']}차")
                                logger.info(f"   ✅ 낮은 수익 구간 - 목표가 도달 혹은 추가 물타기를 위해 홀딩")
                            else:
                                # 손실 상태: 물타기 우선 고려
                                logger.info(f"{symbol}: 추적 손절 감지 (손실 상태 - 물타기 우선)")
                                logger.info(f"   📉 현재 손실률: {current_pnl_rate*100:.2f}%")
                                logger.info(f"   💧 물타기 진행: {avg_info['count']}/{AVERAGING_DOWN_CONFIG['max_averaging_count']}차")
                                logger.info(f"   🎯 평단가 낮추기 대기 중")
                    
                    # 4. 목표 수익 체크 (남은 수량 전량 매도) + 🆕 스윙 홀딩 통합
                    if self.strategy.check_profit_target(entry_price, current_price):
                        current_pnl_rate = (current_price - entry_price) / entry_price

                        # 🆕 스윙 홀딩 체크
                        swing_allow, swing_reason = self.swing_holding.should_allow_exit(
                            symbol, entry_time, current_pnl_rate, exit_reason='take_profit'
                        )

                        if not swing_allow:
                            logger.info(f"{symbol}: 목표 수익 신호이지만 스윙 홀딩 중")
                            logger.info(f"   🎯 {swing_reason}")
                            logger.info(f"   현재 수익: {current_pnl_rate:+.2%}")
                            continue  # 더 큰 수익 대기

                        if self.strategy.can_exit_position(symbol):
                            logger.info(f"{symbol}: 최종 목표 수익 달성 ({current_pnl_rate:+.2%})")
                            logger.info(f"   → 스윙 홀딩 허용: {swing_reason}")
                            self.execute_trade(symbol, 'sell', current_price)
                            self.partial_exit_manager.reset_position(symbol)
                
                except Exception as e:
                    logger.error(f"{symbol} 청산 조건 체크 오류: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
    
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

        # 🆕 변동성 현황 (간단 버전)
        if self.volatility_monitor:
            market_vol, market_grade = self.volatility_monitor.get_market_volatility(TRADING_PAIRS)
            grade_emoji = {
                'low': '🟢',
                'medium': '🟡',
                'high': '🟠',
                'extreme': '🔴'
            }
            emoji = grade_emoji.get(market_grade, '⚪')
            print(f"🌡️ 시장 변동성: {emoji} {market_vol:.2%} ({market_grade.upper()})")
        
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
        
        # 프리셋 상태 표시
        if self.preset_manager:
            print(f"🎯 활성 프리셋: {self.preset_manager.current_preset.upper()}")
        
        # 계좌 정보
        real_total_value = self.get_accurate_balance()
       
        # 리스크 상태
        risk_status = self.risk_manager.get_risk_status()
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

        # 🆕 거래 중단 상태 표시
        if self.risk_manager.trading_suspended:
            print("")
            print("🚨 거래 중단 상태")
            if self.risk_manager.suspension_start_time:
                suspended_duration = (datetime.now() - self.risk_manager.suspension_start_time).total_seconds() / 60
                print(f"   중단 시간: {suspended_duration:.0f}분 경과")
            print(f"   재개 조건: 시장 상황 개선 (상승장 전환)")
            print("")

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
        status_interval = STRATEGY_CONFIG['status_print_interval']
        last_save_time = time.time()
        save_interval = STRATEGY_CONFIG['position_save_interval']
        preset_check_interval = ADAPTIVE_PRESET_CONFIG.get('check_interval', 3600)
    
        
        # ✅ 프리셋 자동 조정 간격
        preset_check_interval = ADAPTIVE_PRESET_CONFIG.get('check_interval', 3600)  # 기본 1시간
              
        
        while True:
            try:
                self.iteration += 1
                current_time = datetime.now()    
    
                # 일일 손실 한도 체크
                daily_loss_limit_reached = self.risk_manager.check_daily_loss_limit()
                if daily_loss_limit_reached:
                    logger.warning("일일 손실 한도 도달. 신규 진입 중단, 청산은 계속")
                    # continue 제거! ← 중요!
                
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
                                    logger.warning(f"{'='*60}\n")
                                    
                                    # ✅ 추가: 기존 포지션 강제 청산
                                    if len(self.risk_manager.positions) > 0:
                                        logger.warning(f"🚨 기존 포지션 {len(self.risk_manager.positions)}개 강제 청산 시작")
                                        self.force_close_all_positions(f"연속 {loss_count}회 손실")
                                    
                                    logger.warning(f"   → 보수적 모드로 강제 전환")
                                    self.preset_manager.switch_preset('conservative', force=True)
                            
                            # 2. 일일 손실률로 인한 강제 전환
                            risk_status = self.risk_manager.get_risk_status()
                            daily_loss_rate = abs(risk_status.get('daily_pnl_rate', 0))
                            loss_threshold = force_config.get('daily_loss_rate', 0.03)
                            
                            if daily_loss_rate >= loss_threshold:
                                logger.warning(f"\n{'='*60}")
                                logger.warning(f"🚨 일일 손실률 {daily_loss_rate:.1%} 초과!")
                                logger.warning(f"   임계값: {loss_threshold:.1%}")
                                logger.warning(f"{'='*60}\n")
                                
                                # ✅ 추가: 기존 포지션 강제 청산
                                if len(self.risk_manager.positions) > 0:
                                    logger.warning(f"🚨 기존 포지션 {len(self.risk_manager.positions)}개 강제 청산 시작")
                                    self.force_close_all_positions(f"일일 손실률 {daily_loss_rate:.1%}")
                                
                                logger.warning(f"   → 보수적 모드로 강제 전환")
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
                
                # 🆕 변동성 모니터링 업데이트
                if self.volatility_monitor:
                    self.volatility_monitor.update_volatility(TRADING_PAIRS)

                    # 극단 변동성 체크
                    should_pause, pause_reason = self.volatility_monitor.should_pause_trading(TRADING_PAIRS)
                    if should_pause:
                        logger.warning(f"⚠️ {pause_reason}")
                        logger.warning("   → 신규 진입 일시 중단, 기존 포지션만 관리")
                        # 신규 진입 스킵, 청산만 계속
                        self.check_exit_conditions()
                        time.sleep(10)
                        continue

                    # 변동성 급증 감지
                    for symbol in TRADING_PAIRS:
                        is_spike, ratio = self.volatility_monitor.detect_volatility_spike(symbol)
                        if is_spike:
                            logger.warning(f"🌡️ {symbol} 변동성 급증 ({ratio:.1f}배) - 진입 보류")

                # 동적 코인 업데이트 (6시간마다)
                self.update_trading_pairs()

                self.check_averaging_down_opportunity()

                # 청산 조건 체크
                self.check_exit_conditions()
                
                # 새로운 거래 기회 탐색
                if self.strategy.can_trade_today() and not daily_loss_limit_reached:
                    self.analyze_and_trade()
                else:
                    if daily_loss_limit_reached:
                        logger.info("신규 진입 차단 중 (일일 손실 한도)")
                
                # 주기적 상태 출력
                if time.time() - last_status_time > status_interval:
                    self.print_status()
                    last_status_time = time.time()
                
                # 주기적으로 포지션 저장
                if time.time() - last_save_time > save_interval:
                    self.save_current_positions()
                    last_save_time = time.time()
                
                # 대기
                time.sleep(10)  # 10초 대기
                
                # 매일 자정 리셋
                current_time = datetime.now()
                if current_time.hour == 0 and current_time.minute == 0:
                    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
                    self.daily_summary.finalize_day(yesterday)
                    self.risk_manager.reset_daily_stats()

                    # 🆕 점수별 성과 리포트 출력 및 저장
                    self.score_tracker.print_report(min_trades=3)
                    self.score_tracker.save_data()

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
        """강제 매도 (보유시간 무시) - ✅ 거래 기록 추가"""
        ticker = f"KRW-{symbol}"
        quantity = self.get_position_quantity(symbol)
        
        if quantity > 0:
            try:
                # ✅ 포지션 정보 먼저 저장
                position = self.risk_manager.positions.get(symbol)
                if position:
                    entry_price = float(position.get('entry_price', current_price))
                    entry_time = position.get('entry_time')
                else:
                    entry_price = current_price  # 진입가 정보 없으면 현재가로
                    entry_time = datetime.now()
                
                order = self.upbit.sell_market_order(ticker, quantity)
                if order:
                    # 체결 정보 대기 및 조회
                    time.sleep(0.5)
                    order_detail = self.upbit.get_order(order['uuid'])
                    
                    # 실제 매도가 계산
                    if order_detail and order_detail.get('state') == 'done':
                        executed_volume = float(order_detail.get('executed_volume', quantity))
                        paid_fee = float(order_detail.get('paid_fee', 0))
                        
                        trades = order_detail.get('trades', [])
                        if trades and executed_volume > 0:
                            total_received = sum(float(t.get('price', 0)) * float(t.get('volume', 0)) for t in trades)
                            actual_price = total_received / executed_volume
                        else:
                            actual_price = current_price
                    else:
                        actual_price = current_price
                        executed_volume = quantity
                        paid_fee = 0
                    
                    # ✅ 손익 계산
                    pnl = (actual_price - entry_price) * executed_volume
                    pnl_rate = (actual_price - entry_price) / entry_price if entry_price > 0 else 0
                    
                    # 보유 시간 계산
                    if isinstance(entry_time, str):
                        entry_dt = datetime.fromisoformat(entry_time)
                    else:
                        entry_dt = entry_time
                    hold_time_hours = (datetime.now() - entry_dt).total_seconds() / 3600
                    
                    # ✅ 거래 기록 추가
                    self.trade_history.add_trade({
                        'timestamp': datetime.now().isoformat(),
                        'symbol': symbol,
                        'type': 'sell',
                        'entry_price': entry_price,
                        'exit_price': actual_price,
                        'quantity': executed_volume,
                        'pnl': pnl,
                        'pnl_rate': pnl_rate,
                        'fee': paid_fee,
                        'hold_time_hours': hold_time_hours
                    })

                    self.strategy.record_trade(symbol, 'sell', pnl=pnl)  # 🎯 손익비 개선: PnL 전달
                    self.risk_manager.update_position(symbol, current_price, quantity, 'sell')
                    logger.info(f"🔴 강제 손절: {symbol} @ {current_price:,.0f} KRW (PnL: {pnl:+,.0f})")
                    logger.info(f"📝 거래 기록 저장: {symbol} PnL: {pnl:+,.0f}")
                    
                    # 보유시간 기록 제거
                    if symbol in self.strategy.position_entry_time:
                        del self.strategy.position_entry_time[symbol]
                    
                    return True
            except Exception as e:
                logger.error(f"강제 손절 실패: {e}")
        
        return False

    def force_sell_all_positions(self):
        """강제로 모든 포지션 청산 (보유시간 무시) - ✅ 거래 기록 추가"""
        logger.info("강제 청산 모드 시작")
        
        for symbol in list(self.risk_manager.positions.keys()):
            ticker = f"KRW-{symbol}"
            
            try:
                # ✅ 포지션 정보 먼저 저장
                position = self.risk_manager.positions.get(symbol)
                if position:
                    entry_price = float(position.get('entry_price', 0))
                    entry_time = position.get('entry_time')
                else:
                    continue  # 포지션 정보 없으면 스킵
                
                # 보유 수량 조회
                quantity = self.get_position_quantity(symbol)
                
                if quantity > 0:
                    # 현재가 조회
                    current_price = pyupbit.get_current_price(ticker)
                    if not current_price:
                        logger.warning(f"{symbol}: 현재가 조회 실패")
                        continue
                    
                    # 직접 매도 주문 실행
                    order = self.upbit.sell_market_order(ticker, quantity)
                    
                    if order:
                        # 체결 정보 대기
                        time.sleep(0.5)
                        order_detail = self.upbit.get_order(order['uuid'])
                        
                        # 실제 매도가 계산
                        if order_detail and order_detail.get('state') == 'done':
                            executed_volume = float(order_detail.get('executed_volume', quantity))
                            paid_fee = float(order_detail.get('paid_fee', 0))
                            
                            trades = order_detail.get('trades', [])
                            if trades and executed_volume > 0:
                                total_received = sum(float(t.get('price', 0)) * float(t.get('volume', 0)) for t in trades)
                                actual_price = total_received / executed_volume
                            else:
                                actual_price = current_price
                        else:
                            actual_price = current_price
                            executed_volume = quantity
                            paid_fee = 0
                        
                        # ✅ 손익 계산
                        pnl = (actual_price - entry_price) * executed_volume
                        pnl_rate = (actual_price - entry_price) / entry_price if entry_price > 0 else 0
                        
                        # 보유 시간 계산
                        if isinstance(entry_time, str):
                            entry_dt = datetime.fromisoformat(entry_time)
                        else:
                            entry_dt = entry_time
                        hold_time_hours = (datetime.now() - entry_dt).total_seconds() / 3600
                        
                        # ✅ 거래 기록 추가
                        self.trade_history.add_trade({
                            'timestamp': datetime.now().isoformat(),
                            'symbol': symbol,
                            'type': 'sell',
                            'entry_price': entry_price,
                            'exit_price': actual_price,
                            'quantity': executed_volume,
                            'pnl': pnl,
                            'pnl_rate': pnl_rate,
                            'fee': paid_fee,
                            'hold_time_hours': hold_time_hours
                        })
                        
                        logger.info(f"✅ 강제 청산 완료: {symbol} (PnL: {pnl:+,.0f})")
                        logger.info(f"📝 거래 기록 저장: {symbol} PnL: {pnl:+,.0f}")
                        
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
        print("2. 거래소와 동기화 (수동 거래 반영)")
        print("3. 모든 포지션 강제 청산")
        print("4. 선택적으로 청산")
        
        choice = input("\n선택 (1/2/3/4): ").strip()
        
        if choice == '2':
            print("\n🔄 거래소와 동기화 중...")
            bot.sync_positions_with_exchange()
            print("✅ 동기화 완료!\n")
            input("계속하려면 Enter를 누르세요...")
            
        elif choice == '3':
            print("모든 포지션 강제 청산 중...")
            bot.force_sell_all_positions()
            
        elif choice == '4':
            for symbol in list(bot.risk_manager.positions.keys()):
                sell = input(f"{symbol} 청산? (y/n): ").strip().lower()
                if sell == 'y':
                    # ✅ 포지션 정보 먼저 저장
                    position = bot.risk_manager.positions.get(symbol)
                    if not position:
                        continue
                        
                    entry_price = float(position.get('entry_price', 0))
                    entry_time = position.get('entry_time')
                    
                    # 개별 강제 청산
                    ticker = f"KRW-{symbol}"
                    quantity = bot.get_position_quantity(symbol)
                    if quantity > 0:
                        # 현재가 조회
                        current_price = pyupbit.get_current_price(ticker)
                        
                        # 매도 실행
                        order = bot.upbit.sell_market_order(ticker, quantity)
                        
                        if order:
                            # 체결 정보 대기
                            time.sleep(0.5)
                            order_detail = bot.upbit.get_order(order['uuid'])
                            
                            # 실제 매도가 계산
                            if order_detail and order_detail.get('state') == 'done':
                                executed_volume = float(order_detail.get('executed_volume', quantity))
                                paid_fee = float(order_detail.get('paid_fee', 0))
                                
                                trades = order_detail.get('trades', [])
                                if trades and executed_volume > 0:
                                    total_received = sum(float(t.get('price', 0)) * float(t.get('volume', 0)) for t in trades)
                                    actual_price = total_received / executed_volume
                                else:
                                    actual_price = current_price
                            else:
                                actual_price = current_price
                                executed_volume = quantity
                                paid_fee = 0
                            
                            # ✅ 손익 계산
                            pnl = (actual_price - entry_price) * executed_volume
                            pnl_rate = (actual_price - entry_price) / entry_price if entry_price > 0 else 0
                            
                            # 보유 시간 계산
                            if isinstance(entry_time, str):
                                entry_dt = datetime.fromisoformat(entry_time)
                            else:
                                entry_dt = entry_time
                            hold_time_hours = (datetime.now() - entry_dt).total_seconds() / 3600
                            
                            # ✅ 거래 기록 추가
                            bot.trade_history.add_trade({
                                'timestamp': datetime.now().isoformat(),
                                'symbol': symbol,
                                'type': 'sell',
                                'entry_price': entry_price,
                                'exit_price': actual_price,
                                'quantity': executed_volume,
                                'pnl': pnl,
                                'pnl_rate': pnl_rate,
                                'fee': paid_fee,
                                'hold_time_hours': hold_time_hours
                            })
                            
                            logger.info(f"✅ 선택적 청산 완료: {symbol} (PnL: {pnl:+,.0f})")
                            logger.info(f"📝 거래 기록 저장: {symbol} PnL: {pnl:+,.0f}")
                            
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