import os
import ccxt
import pandas as pd
import numpy as np
import time
import requests
from datetime import datetime
import ta
import json
from typing import Optional, Dict, List


# ==================== 설정 ====================
class Config:
"""전역 설정 보강"""
    MODE = "simulation"  # "simulation", "testnet", "mainnet"
    
    # ========== API 보안 강화 ==========
    # ✅ 하드코딩된 키를 제거하고 환경 변수에서 로드
    API_KEY = os.getenv("BINANCE_API_KEY")
    API_SECRET = os.getenv("BINANCE_API_SECRET")
    
    # 거래 코인
    SYMBOLS = ['BTC/USDT', 'SOL/USDT', 'ETH/USDT', 'DOGE/USDT']
    
    # ========== 리스크 관리 보강 ==========
    MAX_POSITION_SIZE = 0.02 
    LEVERAGE = 3             # ✅ 레버리지를 10배에서 3배로 하향 (안전 제일)
    STOP_LOSS_PCT = 0.02     
    TAKE_PROFIT_PCT = 0.04   
    
    # ========== 전략 및 MTF 설정 ==========
    STRATEGY_THRESHOLD = 3   
    BASE_TIMEFRAME = '1h'    # 진입 타점용
    TREND_TIMEFRAME = '4h'   # ✅ 추세 확인용 (멀티 타임프레임)
    SCAN_INTERVAL = 300      
    
    LOG_FILE = 'binance_trading.log'
    TRADE_HISTORY_FILE = 'binance_history.json'
    
    @classmethod
    def get_api_credentials(cls):
        """현재 모드에 맞는 API 키 반환"""
        if cls.MODE == "testnet":
            return cls.TESTNET_API_KEY, cls.TESTNET_API_SECRET
        elif cls.MODE == "mainnet":
            return cls.MAINNET_API_KEY, cls.MAINNET_API_SECRET
        else:
            return None, None
    
    @classmethod
    def get_mode_name(cls):
        """현재 모드 이름"""
        if cls.MODE == "simulation":
            return "💻 시뮬레이션 모드 (가상 거래)"
        elif cls.MODE == "testnet":
            return "🎮 연습 모드 (데모 API)"
        else:
            return "⚠️ 실전 모드 (실제 거래)"


# ==================== 유틸리티 ====================
class Logger:
    """로깅"""
    def __init__(self, log_file: str):
        self.log_file = log_file
        self.trade_history = []
    
    def _log(self, message: str, level: str = 'INFO'):
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_msg = f"[{timestamp}] [{level}] {message}"
        print(log_msg)
        
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(log_msg + '\n')
    
    def info(self, msg: str): self._log(msg, 'INFO')
    def warning(self, msg: str): self._log(msg, 'WARNING')
    def error(self, msg: str): self._log(msg, 'ERROR')
    def success(self, msg: str): self._log(msg, 'SUCCESS')
    
    def save_trade(self, trade_data: dict):
        """거래 기록 저장"""
        self.trade_history.append(trade_data)
        with open(Config.TRADE_HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.trade_history, f, indent=2, ensure_ascii=False)


# ==================== API ====================
class BinanceAPI:
    """바이낸스 API"""
    def __init__(self, logger: Logger):
        self.logger = logger
        self.simulation_balance = Config.SIMULATION_BALANCE  # 시뮬레이션 잔고
        
        if Config.MODE == "simulation":
            self.logger.info("💻 시뮬레이션 모드 - API 연결 없이 가상 거래")
            self.exchange = None
        else:
            self._init_exchange()
    
    def _init_exchange(self):
        """거래소 초기화"""
        api_key, api_secret = Config.get_api_credentials()
        
        self.exchange = ccxt.binance({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
            'options': {'defaultType': 'future', 'adjustForTimeDifference': True}
        })
        
        if Config.MODE == "testnet":
            # 데모 트레이딩 모드
            self.exchange.urls['api'] = {
                'public': 'https://testnet.binancefuture.com/fapi/v1',
                'private': 'https://testnet.binancefuture.com/fapi/v1',
                'v1': 'https://testnet.binancefuture.com/fapi/v1',
                'v2': 'https://testnet.binancefuture.com/fapi/v2',
            }
            self.exchange.urls['fapiPublic'] = 'https://testnet.binancefuture.com/fapi/v1'
            self.exchange.urls['fapiPrivate'] = 'https://testnet.binancefuture.com/fapi/v1'
            self.logger.info("🎮 연습 모드 (데모 트레이딩)")
        else:
            # 실전 모드
            self.logger.warning("=" * 60)
            self.logger.warning("⚠️ 실전 모드 활성화 - 실제 자금이 사용됩니다!")
            self.logger.warning("⚠️ 모든 거래는 실제 비용이 발생합니다!")
            self.logger.warning("=" * 60)
            time.sleep(3)  # 경고 확인 시간
    
    def get_balance(self) -> float:
        """USDT 잔고"""
        if Config.MODE == "simulation":
            return self.simulation_balance
        
        try:
            balance = self.exchange.fetch_balance()
            return balance['USDT']['free']
        except Exception as e:
            self.logger.error(f"잔고 조회 실패: {e}")
            return 0
    
    def update_simulation_balance(self, amount: float):
        """시뮬레이션 잔고 업데이트"""
        if Config.MODE == "simulation":
            self.simulation_balance += amount
    
    def get_price(self, symbol: str) -> Optional[float]:
        """현재가"""
        if Config.MODE == "simulation":
            # 시뮬레이션: 실시간 가격 조회
            try:
                url = f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={symbol.replace('/', '')}"
                response = requests.get(url)
                data = response.json()
                return float(data['price'])
            except Exception as e:
                self.logger.error(f"{symbol} 가격 조회 실패: {e}")
                return None
        
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            return ticker['last']
        except Exception as e:
            self.logger.error(f"{symbol} 가격 조회 실패: {e}")
            return None
    
    def get_candles(self, symbol: str, timeframe: str = '1h', limit: int = 100) -> Optional[pd.DataFrame]:
        """캔들 데이터"""
        try:
            symbol_formatted = symbol.replace('/', '')
            params = {'symbol': symbol_formatted, 'interval': timeframe, 'limit': limit}
            
            # 시뮬레이션과 연습 모드는 공개 API 사용
            if Config.MODE in ["simulation", "testnet"]:
                url = 'https://fapi.binance.com/fapi/v1/klines' if Config.MODE == "simulation" else 'https://testnet.binancefuture.com/fapi/v1/klines'
                response = requests.get(url, params=params)
                data = response.json()
            else:
                data = self.exchange.fapiPublicGetKlines(params)
            
            df = pd.DataFrame(data, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_volume', 'trades', 'taker_buy_base',
                'taker_buy_quote', 'ignore'
            ])
            
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = df[col].astype(float)
            
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            return df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
            
        except Exception as e:
            self.logger.error(f"{symbol} 캔들 조회 실패: {e}")
            return None
    
    def set_leverage(self, symbol: str, leverage: int) -> bool:
        """레버리지 설정"""
        if Config.MODE == "simulation":
            self.logger.info(f"💻 [시뮬레이션] {symbol} 레버리지 {leverage}x 설정")
            return True
        
        try:
            self.exchange.fapiPrivate_post_leverage({
                'symbol': symbol.replace('/', ''),
                'leverage': leverage
            })
            return True
        except Exception as e:
            self.logger.error(f"레버리지 설정 실패: {e}")
            return False
    
    def create_order(self, symbol: str, side: str, amount: float) -> Optional[dict]:
        """주문 생성"""
        if Config.MODE == "simulation":
            # 시뮬레이션: 가상 주문
            price = self.get_price(symbol)
            if not price:
                return None
            
            self.logger.success(f"💻 [시뮬레이션] 주문 체결: {symbol} {side.upper()} {amount}")
            return {
                'average': price,
                'price': price,
                'amount': amount,
                'side': side,
                'symbol': symbol
            }
        
        try:
            order = self.exchange.create_market_order(symbol, side, amount)
            self.logger.success(f"✅ 주문 체결: {symbol} {side.upper()} {amount}")
            return order
        except Exception as e:
            self.logger.error(f"주문 실패: {e}")
            return None


# ==================== 전략 ====================
class Strategy:
    """트레이딩 전략"""
    
    @staticmethod
    def rsi(df: pd.DataFrame) -> Optional[str]:
        """RSI 전략"""
        if len(df) < 20: return None
        df['rsi'] = ta.momentum.RSIIndicator(df['close'], window=14).rsi()
        rsi = df['rsi'].iloc[-1]
        if rsi < 30: return 'BUY'
        if rsi > 70: return 'SELL'
        return None
    
    @staticmethod
    def ma_cross(df: pd.DataFrame) -> Optional[str]:
        """이동평균 교차"""
        if len(df) < 50: return None
        df['ma20'] = df['close'].rolling(20).mean()
        df['ma50'] = df['close'].rolling(50).mean()
        
        if df['ma20'].iloc[-2] <= df['ma50'].iloc[-2] and df['ma20'].iloc[-1] > df['ma50'].iloc[-1]:
            return 'BUY'
        if df['ma20'].iloc[-2] >= df['ma50'].iloc[-2] and df['ma20'].iloc[-1] < df['ma50'].iloc[-1]:
            return 'SELL'
        return None
    
    @staticmethod
    def macd(df: pd.DataFrame) -> Optional[str]:
        """MACD"""
        if len(df) < 35: return None
        macd_indicator = ta.trend.MACD(df['close'])
        df['macd'] = macd_indicator.macd()
        df['signal'] = macd_indicator.macd_signal()
        
        if df['macd'].iloc[-2] <= df['signal'].iloc[-2] and df['macd'].iloc[-1] > df['signal'].iloc[-1]:
            return 'BUY'
        if df['macd'].iloc[-2] >= df['signal'].iloc[-2] and df['macd'].iloc[-1] < df['signal'].iloc[-1]:
            return 'SELL'
        return None
    
    @staticmethod
    def bollinger(df: pd.DataFrame) -> Optional[str]:
        """볼린저 밴드"""
        if len(df) < 20: return None
        bb = ta.volatility.BollingerBands(df['close'], window=20, window_dev=2)
        df['bb_high'] = bb.bollinger_hband()
        df['bb_low'] = bb.bollinger_lband()
        price = df['close'].iloc[-1]
        
        if price <= df['bb_low'].iloc[-1]: return 'BUY'
        if price >= df['bb_high'].iloc[-1]: return 'SELL'
        return None
    
    @staticmethod
    def stochastic(df: pd.DataFrame) -> Optional[str]:
        """스토캐스틱"""
        if len(df) < 20: return None
        stoch = ta.momentum.StochasticOscillator(df['high'], df['low'], df['close'])
        df['stoch_k'] = stoch.stoch()
        df['stoch_d'] = stoch.stoch_signal()
        
        k, d = df['stoch_k'].iloc[-1], df['stoch_d'].iloc[-1]
        k_prev, d_prev = df['stoch_k'].iloc[-2], df['stoch_d'].iloc[-2]
        
        if k < 20 and d < 20 and k_prev <= d_prev and k > d: return 'BUY'
        if k > 80 and d > 80 and k_prev >= d_prev and k < d: return 'SELL'
        return None
    
    @classmethod
    def analyze(cls, df: pd.DataFrame) -> Dict[str, Optional[str]]:
        """모든 전략 분석"""
        return {
            'RSI': cls.rsi(df),
            'MA_Cross': cls.ma_cross(df),
            'MACD': cls.macd(df),
            'Bollinger': cls.bollinger(df),
            'Stochastic': cls.stochastic(df)
        }


# ==================== 포지션 ====================
class Position:
    """포지션 정보"""
    def __init__(self, symbol: str, side: str, quantity: float, entry_price: float):
        self.symbol = symbol
        self.side = side
        self.quantity = quantity
        self.entry_price = entry_price
        self.stop_loss = entry_price * (1 - Config.STOP_LOSS_PCT) if side == 'BUY' else entry_price * (1 + Config.STOP_LOSS_PCT)
        self.take_profit = entry_price * (1 + Config.TAKE_PROFIT_PCT) if side == 'BUY' else entry_price * (1 - Config.TAKE_PROFIT_PCT)
        self.timestamp = datetime.now()
    
    def calculate_pnl(self, current_price: float) -> float:
        """손익률 계산"""
        if self.side == 'BUY':
            return ((current_price - self.entry_price) / self.entry_price) * 100 * Config.LEVERAGE
        else:
            return ((self.entry_price - current_price) / self.entry_price) * 100 * Config.LEVERAGE
    
    def should_close(self, current_price: float) -> Optional[str]:
        """청산 조건 확인"""
        if self.side == 'BUY':
            if current_price <= self.stop_loss: return '손절'
            if current_price >= self.take_profit: return '익절'
        else:
            if current_price >= self.stop_loss: return '손절'
            if current_price <= self.take_profit: return '익절'
        return None


class PositionManager:
    """포지션 관리"""
    def __init__(self, api: BinanceAPI, logger: Logger):
        self.api = api
        self.logger = logger
        self.positions: Dict[str, Position] = {}
    
    def calculate_quantity(self, symbol: str) -> float:
        """주문 수량 계산"""
        try:
            balance = self.api.get_balance()
            price = self.api.get_price(symbol)
            if not price: return 0
            
            position_value = balance * Config.MAX_POSITION_SIZE * Config.LEVERAGE
            quantity = position_value / price
            
            if Config.MODE == "simulation":
                # 시뮬레이션: 간단한 정밀도
                return round(quantity, 6)
            
            market = self.api.exchange.market(symbol)
            min_amount = market['limits']['amount']['min']
            
            if quantity < min_amount:
                quantity = min_amount
            
            return float(self.api.exchange.amount_to_precision(symbol, quantity))
        except Exception as e:
            self.logger.error(f"수량 계산 실패: {e}")
            return 0
    
    def open(self, symbol: str, side: str) -> bool:
        """포지션 오픈"""
        if symbol in self.positions:
            return False
        
        # 레버리지 설정
        self.api.set_leverage(symbol, Config.LEVERAGE)
        
        # 수량 계산
        quantity = self.calculate_quantity(symbol)
        if quantity == 0:
            return False
        
        # 주문
        order_side = 'buy' if side == 'BUY' else 'sell'
        order = self.api.create_order(symbol, order_side, quantity)
        if not order:
            return False
        
        entry_price = float(order['average'] or order['price'])
        
        # 포지션 저장
        position = Position(symbol, side, quantity, entry_price)
        self.positions[symbol] = position
        
        self.logger.success(
            f"📈 {symbol} {side} 포지션 오픈\n"
            f"   진입가: {entry_price:.4f} | 수량: {quantity} | "
            f"손절: {position.stop_loss:.4f} | 익절: {position.take_profit:.4f}"
        )
        return True
    
    def close(self, symbol: str, reason: str = "수동") -> bool:
        """포지션 청산"""
        if symbol not in self.positions:
            return False
        
        position = self.positions[symbol]
        
        # 반대 주문
        order_side = 'sell' if position.side == 'BUY' else 'buy'
        order = self.api.create_order(symbol, order_side, position.quantity)
        if not order:
            return False
        
        exit_price = float(order['average'] or order['price'])
        pnl = position.calculate_pnl(exit_price)
        
        # 시뮬레이션 모드: 잔고 업데이트
        if Config.MODE == "simulation":
            pnl_amount = (position.quantity * exit_price * pnl / 100) / Config.LEVERAGE
            self.api.update_simulation_balance(pnl_amount)
            balance = self.api.get_balance()
            self.logger.success(
                f"📉 {symbol} 포지션 청산 ({reason})\n"
                f"   진입: {position.entry_price:.4f} → 청산: {exit_price:.4f} | "
                f"손익: {pnl:+.2f}% ({pnl_amount:+.2f} USDT) | 잔고: {balance:.2f} USDT"
            )
        else:
            self.logger.success(
                f"📉 {symbol} 포지션 청산 ({reason})\n"
                f"   진입: {position.entry_price:.4f} → 청산: {exit_price:.4f} | "
                f"손익: {pnl:+.2f}%"
            )
        
        # 거래 기록
        self.logger.save_trade({
            'symbol': symbol,
            'side': position.side,
            'entry_price': position.entry_price,
            'exit_price': exit_price,
            'quantity': position.quantity,
            'pnl_pct': pnl,
            'reason': reason,
            'mode': Config.MODE,
            'timestamp': datetime.now().isoformat()
        })
        
        del self.positions[symbol]
        return True
    
    def check_exits(self):
        """청산 조건 확인"""
        for symbol in list(self.positions.keys()):
            price = self.api.get_price(symbol)
            if not price:
                continue
            
            reason = self.positions[symbol].should_close(price)
            if reason:
                self.close(symbol, reason)
    
    def print_status(self):
        """포지션 현황"""
        if not self.positions:
            self.logger.info("\n📭 활성 포지션 없음")
            return
        
        self.logger.info(f"\n📊 활성 포지션: {len(self.positions)}개")
        for symbol, pos in self.positions.items():
            price = self.api.get_price(symbol)
            if price:
                pnl = pos.calculate_pnl(price)
                self.logger.info(
                    f"  {symbol}: {pos.side} @ {pos.entry_price:.4f} | "
                    f"현재: {price:.4f} | 손익: {pnl:+.2f}%"
                )


# ==================== 메인 봇 ====================
class TradingBot:
    """트레이딩 봇"""
    def __init__(self):
        self.logger = Logger(Config.LOG_FILE)
        self.api = BinanceAPI(self.logger)
        self.positions = PositionManager(self.api, self.logger)
        
        self._print_header()
    
    def _print_header(self):
        """시작 정보"""
        self.logger.info("=" * 60)
        self.logger.info("🚀 Binance Futures Auto Trader")
        self.logger.info("=" * 60)
        self.logger.info(f"모드: {Config.get_mode_name()}")
        self.logger.info(f"거래 코인: {', '.join([s.replace('/USDT', '') for s in Config.SYMBOLS])}")
        self.logger.info(f"레버리지: {Config.LEVERAGE}x | 손절: {Config.STOP_LOSS_PCT*100}% | 익절: {Config.TAKE_PROFIT_PCT*100}%")
        balance = self.api.get_balance()
        self.logger.info(f"💰 잔고: {balance:.2f} USDT")
        self.logger.info("=" * 60)
        
        if Config.MODE == "mainnet":
            self.logger.warning("\n⚠️⚠️⚠️ 실전 모드입니다 - 실제 자금이 사용됩니다! ⚠️⚠️⚠️\n")
            self.logger.warning("5초 후 시작됩니다. 중단하려면 Ctrl+C를 누르세요...")
            time.sleep(5)
    
    def scan(self):
        """시장 스캔"""
        self.logger.info(f"\n{'='*60}")
        self.logger.info(f"📊 시장 스캔: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        for symbol in Config.SYMBOLS:
            try:
                # 청산 조건 확인
                self.positions.check_exits()
                
                # 신규 진입 확인
                if symbol not in self.positions.positions:
                    df = self.api.get_candles(symbol, Config.TIMEFRAME)
                    if df is None:
                        continue
                    
                    signals = Strategy.analyze(df)
                    buy_count = sum(1 for s in signals.values() if s == 'BUY')
                    sell_count = sum(1 for s in signals.values() if s == 'SELL')
                    
                    self.logger.info(
                        f"{symbol}: {signals} "
                        f"(매수:{buy_count} 매도:{sell_count})"
                    )
                    
                    # 신호 판단
                    if buy_count >= Config.STRATEGY_THRESHOLD:
                        self.positions.open(symbol, 'BUY')
                    elif sell_count >= Config.STRATEGY_THRESHOLD:
                        self.positions.open(symbol, 'SELL')
                
                time.sleep(2)
                
            except Exception as e:
                self.logger.error(f"{symbol} 처리 중 오류: {e}")
    
    def run(self):
        """봇 실행"""
        try:
            while True:
                self.scan()
                self.positions.print_status()
                
                self.logger.info(f"\n⏰ {Config.SCAN_INTERVAL}초 후 다음 스캔...")
                time.sleep(Config.SCAN_INTERVAL)
                
        except KeyboardInterrupt:
            self.logger.warning("\n⚠️ 봇 중지")
            self.logger.info(f"활성 포지션: {len(self.positions.positions)}개")


# ==================== 실행 ====================
if __name__ == "__main__":
    print("\n" + "="*60)
    print("  Binance Futures Auto Trader")
    print("="*60)
    print(f"\n현재 모드: {Config.get_mode_name()}\n")
    
    if Config.MODE == "simulation":
        print("💻 시뮬레이션 모드로 실행합니다")
        print("   - API 연결 없이 가상 거래")
        print("   - 실시간 가격으로 시뮬레이션")
        print(f"   - 초기 자금: {Config.SIMULATION_BALANCE} USDT")
        print("   - 실제 손실 없음\n")
        
    elif Config.MODE == "testnet":
        print("🎮 연습 모드로 실행합니다")
        print("   - 데모 API 사용")
        print("   - 가상 자금 사용")
        print("   - 실제 손실 없음")
        print("   - 데모 API: https://testnet.binancefuture.com\n")
        
    else:
        print("⚠️  실전 모드로 실행합니다!")
        print("   - 실제 API 사용")
        print("   - 실제 자금 사용")
        print("   - 실제 손실 발생 가능")
        print("   - 신중하게 사용하세요!\n")
        
        response = input("정말 실전 모드로 실행하시겠습니까? (yes 입력): ")
        if response.lower() != 'yes':
            print("\n❌ 실행 취소됨")
            exit()
    
    print("\n봇을 시작합니다...\n")
    
    bot = TradingBot()
    bot.run()