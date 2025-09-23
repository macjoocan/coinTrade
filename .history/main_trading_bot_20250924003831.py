# main_trading_bot.py

import pyupbit
import time
import logging
from datetime import datetime
import pandas as pd
import numpy as np
from improved_strategy import ImprovedStrategy
from risk_manager import RiskManager
from config import TRADING_PAIRS

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('trading.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class TradingBot:
    def __init__(self, access_key, secret_key):
        self.upbit = pyupbit.Upbit(access_key, secret_key)
        self.balance = self.get_balance()
        
        # 전략 및 리스크 매니저 초기화
        self.strategy = ImprovedStrategy()
        self.risk_manager = RiskManager(self.balance)
        
        logger.info(f"봇 초기화 완료. 초기 자본: {self.balance:,.0f} KRW")
        
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
    
    def execute_trade(self, symbol, trade_type, current_price=None):
        """거래 실행 (개선된 로직)"""
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
            
            # 실제 매수 실행
            try:
                order = self.upbit.buy_market_order(ticker, order_amount)
                if order:
                    self.strategy.record_trade(symbol, 'buy')
                    self.risk_manager.update_position(symbol, current_price, quantity, 'buy')
                    logger.info(f"✅ 매수 완료: {symbol} @ {current_price:,.0f} KRW")
                    return True
            except Exception as e:
                logger.error(f"매수 실패: {e}")
                
        elif trade_type == 'sell':
            # 매도 조건 체크
            if not self.strategy.can_exit_position(symbol):
                logger.info(f"{symbol}: 최소 보유시간 미충족")
                return False
            
            # 보유 수량 조회
            quantity = self.get_position_quantity(symbol)
            if quantity == 0:
                return False
            
            # 실제 매도 실행
            try:
                order = self.upbit.sell_market_order(ticker, quantity)
                if order:
                    self.strategy.record_trade(symbol, 'sell')
                    self.risk_manager.update_position(symbol, current_price, quantity, 'sell')
                    logger.info(f"🔴 매도 완료: {symbol} @ {current_price:,.0f} KRW")
                    return True
            except Exception as e:
                logger.error(f"매도 실패: {e}")
                
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
        """모든 포지션의 청산 조건 체크"""
        for symbol in list(self.risk_manager.positions.keys()):
            ticker = f"KRW-{symbol}"
            current_price = pyupbit.get_current_price(ticker)
            
            if not current_price:
                continue
            
            position = self.risk_manager.positions[symbol]
            entry_price = position['entry_price']
            
            # 1. 추적 손절 체크
            if self.risk_manager.check_trailing_stop(symbol, current_price):
                logger.info(f"{symbol}: 추적 손절 발동")
                self.execute_trade(symbol, 'sell', current_price)
                continue
            
            # 2. 일반 손절 체크
            if self.risk_manager.check_stop_loss(symbol, current_price):
                logger.info(f"{symbol}: 손절 발동")
                self.execute_trade(symbol, 'sell', current_price)
                continue
            
            # 3. 목표 수익 달성 체크
            if self.strategy.check_profit_target(entry_price, current_price):
                logger.info(f"{symbol}: 목표 수익 달성")
                self.execute_trade(symbol, 'sell', current_price)
    
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
                self.execute_trade(symbol, 'buy', indicators['price