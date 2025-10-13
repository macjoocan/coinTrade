"""
Binance Futures Auto Trading System
BTC, SOL, ETH, DOGE 선물 자동매매 시스템
"""

import ccxt
import pandas as pd
import numpy as np
import time
from datetime import datetime, timedelta
import ta
import json

class Config:
    """설정 관리 클래스"""
    def __init__(self):
        # API 설정 (바이낸스 선물 데모 트레이딩 API 키 필요)
        # 발급: https://testnet.binancefuture.com/
        self.API_KEY = "fdfa6b341eca3fc3eef65b6550b7638dedebf5648c55ec64d697cd39204c520f"
        self.API_SECRET = "9a230bee486637d04f54f351776d553984a34d9573338ac47cc91426d0c7a6f4"
        self.USE_TESTNET = True  # 데모 트레이딩 사용 여부
        
        # 거래 대상 코인
        self.SYMBOLS = ['BTC/USDT', 'SOL/USDT', 'ETH/USDT', 'DOGE/USDT']
        
        # 리스크 관리
        self.MAX_POSITION_SIZE = 0.02  # 계좌의 2%
        self.LEVERAGE = 10  # 레버리지
        self.STOP_LOSS_PCT = 0.02  # 2% 손절
        self.TAKE_PROFIT_PCT = 0.04  # 4% 익절
        
        # 전략 설정
        self.STRATEGY_THRESHOLD = 3  # 신호 최소 개수 (5개 전략 중 3개 이상)
        self.TIMEFRAME = '1h'  # 캔들 타임프레임
        self.SCAN_INTERVAL = 300  # 스캔 주기 (초)
        
        # 로그 설정
        self.LOG_FILE = 'trading_log.txt'
        self.SAVE_TRADES = True  # 거래 기록 저장 여부


class Logger:
    """로깅 클래스"""
    def __init__(self, log_file='trading_log.txt'):
        self.log_file = log_file
        self.trade_history = []
    
    def log(self, message, level='INFO'):
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_message = f"[{timestamp}] [{level}] {message}"
        print(log_message)
        
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(log_message + '\n')
    
    def info(self, message):
        self.log(message, 'INFO')
    
    def warning(self, message):
        self.log(message, 'WARNING')
    
    def error(self, message):
        self.log(message, 'ERROR')
    
    def success(self, message):
        self.log(message, 'SUCCESS')
    
    def save_trade(self, trade_data):
        self.trade_history.append(trade_data)
        with open('trade_history.json', 'w', encoding='utf-8') as f:
            json.dump(self.trade_history, f, indent=2, ensure_ascii=False)


class BinanceAPI:
    """바이낸스 API 연결 클래스"""
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger
        
        # CCXT 초기화
        if config.USE_TESTNET:
            # 바이낸스 선물 데모 트레이딩 사용
            self.exchange = ccxt.binance({
                'apiKey': config.API_KEY,
                'secret': config.API_SECRET,
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'future',
                    'adjustForTimeDifference': True,
                }
            })
            # 데모 트레이딩 URL로 변경
            self.exchange.urls['api'] = {
                'public': 'https://testnet.binancefuture.com/fapi/v1',
                'private': 'https://testnet.binancefuture.com/fapi/v1',
            }
            self.logger.info("데모 트레이딩 모드로 연결 (testnet.binancefuture.com)")
        else:
            self.exchange = ccxt.binance({
                'apiKey': config.API_KEY,
                'secret': config.API_SECRET,
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'future',
                    'adjustForTimeDifference': True
                }
            })
            self.logger.warning("⚠️ 실제 거래 모드로 연결 - 실제 자금이 사용됩니다!")
    
    def get_balance(self):
        """잔고 조회"""
        try:
            balance = self.exchange.fetch_balance()
            return balance['USDT']['free']
        except Exception as e:
            self.logger.error(f"잔고 조회 실패: {e}")
            return 0
    
    def get_current_price(self, symbol):
        """현재가 조회"""
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            return ticker['last']
        except Exception as e:
            self.logger.error(f"{symbol} 가격 조회 실패: {e}")
            return None
    
    def get_ohlcv(self, symbol, timeframe='1h', limit=100):
        """캔들 데이터 조회"""
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            return df
        except Exception as e:
            self.logger.error(f"{symbol} OHLCV 조회 실패: {e}")
            return None
    
    def set_leverage(self, symbol, leverage):
        """레버리지 설정"""
        try:
            self.exchange.fapiPrivate_post_leverage({
                'symbol': symbol.replace('/', ''),
                'leverage': leverage
            })
            self.logger.info(f"{symbol} 레버리지 {leverage}x 설정")
            return True
        except Exception as e:
            self.logger.error(f"레버리지 설정 실패: {e}")
            return False
    
    def create_order(self, symbol, side, amount):
        """주문 생성"""
        try:
            order = self.exchange.create_market_order(symbol, side, amount)
            self.logger.success(f"주문 체결: {symbol} {side.upper()} {amount}")
            return order
        except Exception as e:
            self.logger.error(f"주문 실패: {e}")
            return None


class TradingStrategy:
    """트레이딩 전략 클래스"""
    def __init__(self, logger):
        self.logger = logger
    
    def rsi_strategy(self, df):
        """RSI 전략"""
        if len(df) < 20:
            return None
        
        df['rsi'] = ta.momentum.RSIIndicator(df['close'], window=14).rsi()
        current_rsi = df['rsi'].iloc[-1]
        
        if current_rsi < 30:
            return 'BUY'
        elif current_rsi > 70:
            return 'SELL'
        return None
    
    def ma_cross_strategy(self, df):
        """이동평균 교차 전략"""
        if len(df) < 50:
            return None
        
        df['ma_short'] = df['close'].rolling(window=20).mean()
        df['ma_long'] = df['close'].rolling(window=50).mean()
        
        if df['ma_short'].iloc[-2] <= df['ma_long'].iloc[-2] and \
           df['ma_short'].iloc[-1] > df['ma_long'].iloc[-1]:
            return 'BUY'
        
        if df['ma_short'].iloc[-2] >= df['ma_long'].iloc[-2] and \
           df['ma_short'].iloc[-1] < df['ma_long'].iloc[-1]:
            return 'SELL'
        
        return None
    
    def macd_strategy(self, df):
        """MACD 전략"""
        if len(df) < 35:
            return None
        
        macd = ta.trend.MACD(df['close'])
        df['macd'] = macd.macd()
        df['macd_signal'] = macd.macd_signal()
        
        if df['macd'].iloc[-2] <= df['macd_signal'].iloc[-2] and \
           df['macd'].iloc[-1] > df['macd_signal'].iloc[-1]:
            return 'BUY'
        
        if df['macd'].iloc[-2] >= df['macd_signal'].iloc[-2] and \
           df['macd'].iloc[-1] < df['macd_signal'].iloc[-1]:
            return 'SELL'
        
        return None
    
    def bollinger_strategy(self, df):
        """볼린저 밴드 전략"""
        if len(df) < 20:
            return None
        
        bollinger = ta.volatility.BollingerBands(df['close'], window=20, window_dev=2)
        df['bb_high'] = bollinger.bollinger_hband()
        df['bb_low'] = bollinger.bollinger_lband()
        
        current_price = df['close'].iloc[-1]
        
        if current_price <= df['bb_low'].iloc[-1]:
            return 'BUY'
        elif current_price >= df['bb_high'].iloc[-1]:
            return 'SELL'
        
        return None
    
    def stochastic_strategy(self, df):
        """스토캐스틱 전략"""
        if len(df) < 20:
            return None
        
        stoch = ta.momentum.StochasticOscillator(df['high'], df['low'], df['close'])
        df['stoch_k'] = stoch.stoch()
        df['stoch_d'] = stoch.stoch_signal()
        
        k = df['stoch_k'].iloc[-1]
        d = df['stoch_d'].iloc[-1]
        
        if k < 20 and d < 20 and df['stoch_k'].iloc[-2] <= df['stoch_d'].iloc[-2] and k > d:
            return 'BUY'
        
        if k > 80 and d > 80 and df['stoch_k'].iloc[-2] >= df['stoch_d'].iloc[-2] and k < d:
            return 'SELL'
        
        return None
    
    def analyze(self, df, symbol):
        """전체 전략 분석"""
        signals = {
            'RSI': self.rsi_strategy(df),
            'MA_Cross': self.ma_cross_strategy(df),
            'MACD': self.macd_strategy(df),
            'Bollinger': self.bollinger_strategy(df),
            'Stochastic': self.stochastic_strategy(df)
        }
        
        buy_count = sum(1 for s in signals.values() if s == 'BUY')
        sell_count = sum(1 for s in signals.values() if s == 'SELL')
        
        self.logger.info(f"{symbol} 신호: {signals} (매수:{buy_count} 매도:{sell_count})")
        
        return signals, buy_count, sell_count


class PositionManager:
    """포지션 관리 클래스"""
    def __init__(self, config, api, logger):
        self.config = config
        self.api = api
        self.logger = logger
        self.positions = {}
    
    def calculate_position_size(self, symbol):
        """포지션 크기 계산"""
        try:
            balance = self.api.get_balance()
            current_price = self.api.get_current_price(symbol)
            
            if not current_price:
                return 0
            
            position_value = balance * self.config.MAX_POSITION_SIZE * self.config.LEVERAGE
            quantity = position_value / current_price
            
            # 최소 주문 수량 확인
            market = self.api.exchange.market(symbol)
            min_amount = market['limits']['amount']['min']
            
            if quantity < min_amount:
                quantity = min_amount
            
            quantity = self.api.exchange.amount_to_precision(symbol, quantity)
            return float(quantity)
            
        except Exception as e:
            self.logger.error(f"포지션 크기 계산 실패: {e}")
            return 0
    
    def open_position(self, symbol, signal):
        """포지션 오픈"""
        if symbol in self.positions:
            self.logger.warning(f"{symbol} 이미 포지션 보유 중")
            return False
        
        try:
            # 레버리지 설정
            self.api.set_leverage(symbol, self.config.LEVERAGE)
            
            # 포지션 크기 계산
            quantity = self.calculate_position_size(symbol)
            if quantity == 0:
                return False
            
            # 주문 실행
            side = 'buy' if signal == 'BUY' else 'sell'
            order = self.api.create_order(symbol, side, quantity)
            
            if not order:
                return False
            
            entry_price = float(order['average']) if order['average'] else float(order['price'])
            
            # 손절/익절 계산
            if signal == 'BUY':
                stop_loss = entry_price * (1 - self.config.STOP_LOSS_PCT)
                take_profit = entry_price * (1 + self.config.TAKE_PROFIT_PCT)
            else:
                stop_loss = entry_price * (1 + self.config.STOP_LOSS_PCT)
                take_profit = entry_price * (1 - self.config.TAKE_PROFIT_PCT)
            
            # 포지션 정보 저장
            self.positions[symbol] = {
                'side': signal,
                'quantity': quantity,
                'entry_price': entry_price,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'timestamp': datetime.now().isoformat()
            }
            
            self.logger.success(f"✅ {symbol} {signal} 포지션 오픈 | 수량: {quantity} | 진입가: {entry_price:.4f}")
            return True
            
        except Exception as e:
            self.logger.error(f"포지션 오픈 실패: {e}")
            return False
    
    def close_position(self, symbol, reason="수동청산"):
        """포지션 청산"""
        if symbol not in self.positions:
            self.logger.warning(f"{symbol} 포지션 없음")
            return False
        
        try:
            position = self.positions[symbol]
            
            # 반대 주문
            side = 'sell' if position['side'] == 'BUY' else 'buy'
            order = self.api.create_order(symbol, side, position['quantity'])
            
            if not order:
                return False
            
            exit_price = float(order['average']) if order['average'] else float(order['price'])
            
            # 손익 계산
            if position['side'] == 'BUY':
                pnl_pct = ((exit_price - position['entry_price']) / position['entry_price']) * 100
            else:
                pnl_pct = ((position['entry_price'] - exit_price) / position['entry_price']) * 100
            
            pnl_pct *= self.config.LEVERAGE
            
            self.logger.success(f"🔴 {symbol} 포지션 청산 ({reason}) | 손익: {pnl_pct:.2f}%")
            
            # 거래 기록
            trade_data = {
                'symbol': symbol,
                'side': position['side'],
                'entry_price': position['entry_price'],
                'exit_price': exit_price,
                'quantity': position['quantity'],
                'pnl_pct': pnl_pct,
                'reason': reason,
                'timestamp': datetime.now().isoformat()
            }
            self.logger.save_trade(trade_data)
            
            del self.positions[symbol]
            return True
            
        except Exception as e:
            self.logger.error(f"포지션 청산 실패: {e}")
            return False
    
    def check_exit_conditions(self, symbol):
        """청산 조건 확인"""
        if symbol not in self.positions:
            return
        
        try:
            position = self.positions[symbol]
            current_price = self.api.get_current_price(symbol)
            
            if not current_price:
                return
            
            # 손절/익절 확인
            if position['side'] == 'BUY':
                if current_price <= position['stop_loss']:
                    self.close_position(symbol, "손절")
                elif current_price >= position['take_profit']:
                    self.close_position(symbol, "익절")
            else:
                if current_price >= position['stop_loss']:
                    self.close_position(symbol, "손절")
                elif current_price <= position['take_profit']:
                    self.close_position(symbol, "익절")
                    
        except Exception as e:
            self.logger.error(f"청산 조건 확인 실패: {e}")


class TradingBot:
    """메인 트레이딩 봇 클래스"""
    def __init__(self):
        self.config = Config()
        self.logger = Logger(self.config.LOG_FILE)
        self.api = BinanceAPI(self.config, self.logger)
        self.strategy = TradingStrategy(self.logger)
        self.position_manager = PositionManager(self.config, self.api, self.logger)
        
        self.logger.info("="*60)
        self.logger.info("🚀 Binance Futures Auto Trader 시작")
        self.logger.info("="*60)
        self.print_config()
    
    def print_config(self):
        """설정 정보 출력"""
        self.logger.info(f"거래 코인: {', '.join(self.config.SYMBOLS)}")
        self.logger.info(f"레버리지: {self.config.LEVERAGE}x")
        self.logger.info(f"손절: {self.config.STOP_LOSS_PCT*100}% | 익절: {self.config.TAKE_PROFIT_PCT*100}%")
        self.logger.info(f"스캔 주기: {self.config.SCAN_INTERVAL}초")
        self.logger.info(f"테스트넷: {self.config.USE_TESTNET}")
        balance = self.api.get_balance()
        self.logger.info(f"💰 현재 잔고: {balance:.2f} USDT")
        self.logger.info("="*60)
    
    def scan_market(self):
        """시장 스캔 및 매매 신호 분석"""
        self.logger.info(f"\n{'='*60}")
        self.logger.info(f"📊 시장 스캔 시작: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        for symbol in self.config.SYMBOLS:
            try:
                # 기존 포지션 청산 조건 확인
                self.position_manager.check_exit_conditions(symbol)
                
                # 신규 진입 신호 확인
                if symbol not in self.position_manager.positions:
                    df = self.api.get_ohlcv(symbol, self.config.TIMEFRAME)
                    
                    if df is not None:
                        signals, buy_count, sell_count = self.strategy.analyze(df, symbol)
                        
                        # 신호 판단
                        if buy_count >= self.config.STRATEGY_THRESHOLD:
                            self.position_manager.open_position(symbol, 'BUY')
                        elif sell_count >= self.config.STRATEGY_THRESHOLD:
                            self.position_manager.open_position(symbol, 'SELL')
                
                time.sleep(2)  # API 제한 방지
                
            except Exception as e:
                self.logger.error(f"{symbol} 스캔 중 오류: {e}")
                continue
    
    def print_status(self):
        """현재 상태 출력"""
        positions = self.position_manager.positions
        
        if positions:
            self.logger.info(f"\n📈 활성 포지션: {len(positions)}개")
            for symbol, pos in positions.items():
                current_price = self.api.get_current_price(symbol)
                if current_price:
                    if pos['side'] == 'BUY':
                        pnl = ((current_price - pos['entry_price']) / pos['entry_price']) * 100 * self.config.LEVERAGE
                    else:
                        pnl = ((pos['entry_price'] - current_price) / pos['entry_price']) * 100 * self.config.LEVERAGE
                    
                    self.logger.info(f"  {symbol}: {pos['side']} @ {pos['entry_price']:.4f} | 현재: {current_price:.4f} | 손익: {pnl:+.2f}%")
        else:
            self.logger.info("\n📭 활성 포지션 없음")
    
    def run(self):
        """봇 실행"""
        try:
            while True:
                self.scan_market()
                self.print_status()
                
                self.logger.info(f"\n⏰ 다음 스캔까지 {self.config.SCAN_INTERVAL}초 대기...")
                time.sleep(self.config.SCAN_INTERVAL)
                
        except KeyboardInterrupt:
            self.logger.warning("\n⚠️ 봇 중지 요청")
            self.logger.info(f"활성 포지션: {len(self.position_manager.positions)}개")
            self.logger.info("거래 기록은 trade_history.json에서 확인하세요")


# ==================== 실행 ====================
if __name__ == "__main__":
    # 설정을 직접 수정하거나 Config 클래스에서 변경
    bot = TradingBot()
    
    # 봇 실행
    bot.run()