import os
import sys
import ccxt
import pandas as pd
import numpy as np
import time
import requests
from datetime import datetime, timedelta
import ta
import json
from typing import Optional, Dict, List
import pickle

# sklearn 경고 억제
import warnings
warnings.filterwarnings('ignore', category=UserWarning)
warnings.filterwarnings('ignore', category=FutureWarning)


# ==================== 실행 경로 설정 ====================
def get_base_path():
    """exe 또는 스크립트의 실제 실행 경로 반환"""
    if getattr(sys, 'frozen', False):
        # PyInstaller로 빌드된 exe
        return os.path.dirname(sys.executable)
    else:
        # 일반 Python 스크립트
        return os.path.dirname(os.path.abspath(__file__))

BASE_PATH = get_base_path()


# ==================== .env 파일 로드 ====================
def load_env():
    """.env 파일에서 환경변수 로드 (python-dotenv 없이)"""
    env_file = os.path.join(BASE_PATH, '.env')
    if os.path.exists(env_file):
        try:
            with open(env_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    if '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        os.environ[key] = value
            print("[OK] .env 파일 로드 완료")
        except Exception as e:
            print(f"[WARN] .env 파일 로드 실패: {e}")

load_env()


# ==================== 설정 파일 로드 ====================
def load_settings():
    """settings.json 로드"""
    settings_file = os.path.join(BASE_PATH, 'binance_settings.json')
    if os.path.exists(settings_file):
        try:
            with open(settings_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[WARN] 설정 파일 로드 실패: {e}")
    return None

_settings = load_settings()

def get_setting(*keys, default=None):
    """중첩 딕셔너리에서 값 가져오기"""
    if _settings is None:
        return default
    value = _settings
    for key in keys:
        if isinstance(value, dict):
            value = value.get(key)
        else:
            return default
        if value is None:
            return default
    return value


# ==================== 설정 ====================
class Config:
    """전역 설정 - settings.json에서 로드"""
    MODE = get_setting('mode', default="simulation")  # "simulation", "testnet", "mainnet"

    SIMULATION_BALANCE = get_setting('simulation', 'initial_balance', default=10000)

    # API 키 (환경변수 또는 설정파일)
    API_KEY = os.getenv("BINANCE_API_KEY") or get_setting('api', 'key')
    API_SECRET = os.getenv("BINANCE_API_SECRET") or get_setting('api', 'secret')

    # 거래 코인
    SYMBOLS = get_setting('trading', 'symbols', default=['BTC/USDT', 'SOL/USDT', 'ETH/USDT', 'DOGE/USDT'])

    # 리스크 관리
    MAX_POSITION_SIZE = get_setting('risk', 'max_position_size', default=0.02)
    LEVERAGE = get_setting('risk', 'leverage', default=3)
    LEVERAGE_PER_SYMBOL = get_setting('risk', 'leverage_per_symbol', default={})
    STOP_LOSS_PCT = get_setting('risk', 'stop_loss', default=0.02)
    TAKE_PROFIT_PCT = get_setting('risk', 'take_profit', default=0.03)  # 4% -> 3%로 조정
    DAILY_LOSS_LIMIT = get_setting('risk', 'daily_loss_limit', default=0.05)  # 일일 손실 한도 5%
    MAX_POSITIONS = get_setting('risk', 'max_positions', default=4)

    # 트레일링 스탑
    TRAILING_STOP_ENABLED = get_setting('trailing_stop', 'enabled', default=True)
    TRAILING_STOP_ACTIVATION = get_setting('trailing_stop', 'activation', default=0.015)  # 1.5% 수익시 활성화 (2%에서 완화)
    TRAILING_STOP_DISTANCE = get_setting('trailing_stop', 'distance', default=0.008)  # 0.8% 하락 허용 (1%에서 타이트하게)

    # 전략 및 MTF 설정
    STRATEGY_THRESHOLD = get_setting('strategy', 'threshold', default=3)
    BASE_TIMEFRAME = get_setting('strategy', 'base_timeframe', default='1h')
    TREND_TIMEFRAME = get_setting('strategy', 'trend_timeframe', default='4h')
    SCAN_INTERVAL = get_setting('strategy', 'scan_interval', default=120)  # 5분 -> 2분 (트레일링 반응 속도 개선)

    # 진입 점수 기준 (완화된 조건)
    ENTRY_SCORE_THRESHOLD = get_setting('strategy', 'entry_score_threshold', default=0.2)  # 기존 0.3에서 완화
    ALLOW_SIDEWAYS_ENTRY = get_setting('strategy', 'allow_sideways_entry', default=True)  # 횡보장 진입 허용

    # ML 설정
    ML_ENABLED = get_setting('ml', 'enabled', default=True)
    ML_MIN_PROBABILITY = get_setting('ml', 'min_probability', default=0.60)
    ML_WEIGHT = get_setting('ml', 'weight', default=0.3)

    # 고급 ML 설정 (Phase 2 - v2.2)
    ADVANCED_ML_ENABLED = get_setting('advanced_ml', 'enabled', default=True)
    ADVANCED_ML_WEIGHT = get_setting('advanced_ml', 'weight', default=0.4)

    # 분할 익절 설정
    PARTIAL_EXIT_ENABLED = get_setting('partial_exit', 'enabled', default=True)
    PARTIAL_EXIT_TRIGGER = get_setting('partial_exit', 'trigger_profit', default=0.015)  # 1.5% 수익시 발동
    PARTIAL_EXIT_RATIO = get_setting('partial_exit', 'exit_ratio', default=0.5)  # 50% 청산
    ADAPTIVE_PARTIAL_EXIT = get_setting('partial_exit', 'adaptive', default=True)  # ATR 기반 적응형 트리거

    # 추세 반전 강제 청산 설정
    REVERSE_EXIT_ENABLED = get_setting('reverse_exit', 'enabled', default=True)
    REVERSE_EXIT_SCORE_THRESHOLD = get_setting('reverse_exit', 'score_threshold', default=0.3)  # 반대 점수 기준
    REVERSE_EXIT_MIN_HOLD = get_setting('reverse_exit', 'min_hold_minutes', default=30)  # 최소 보유 시간(분)

    # 데이터 경로 (Docker: /app/data, 로컬: 실행 폴더)
    DATA_PATH = os.getenv('DATA_PATH', os.path.join(BASE_PATH, 'data') if os.path.exists('/app') else BASE_PATH)

    @staticmethod
    def get_leverage(symbol: str) -> int:
        """코인별 레버리지 반환 (설정 없으면 기본값 사용)"""
        coin = symbol.replace('/USDT', '')
        return Config.LEVERAGE_PER_SYMBOL.get(coin, Config.LEVERAGE)

    # 파일 경로
    LOG_FILE = os.path.join(DATA_PATH, 'binance_trading.log')
    TRADE_HISTORY_FILE = os.path.join(DATA_PATH, 'binance_history.json')
    POSITION_FILE = os.path.join(DATA_PATH, 'binance_positions.json')
    ML_MODEL_FILE = os.path.join(BASE_PATH, 'binance_ml_model.pkl')

    @classmethod
    def get_api_credentials(cls):
        """현재 모드에 맞는 API 키 반환"""
        return cls.API_KEY, cls.API_SECRET

    @classmethod
    def get_mode_name(cls):
        """현재 모드 이름"""
        if cls.MODE == "simulation":
            return "시뮬레이션 모드 (가상 거래)"
        elif cls.MODE == "testnet":
            return "연습 모드 (데모 API)"
        else:
            return "실전 모드 (실제 거래)"


# ==================== 텔레그램 알림 ====================
class TelegramNotifier:
    """텔레그램 알림 전송"""

    def __init__(self):
        self.token = os.getenv('TELEGRAM_BOT_TOKEN', '')
        self.chat_id = os.getenv('TELEGRAM_CHAT_ID', '')
        self.enabled = bool(self.token and self.chat_id)

        if self.enabled:
            print("[OK] 텔레그램 알림 활성화")
        else:
            print("[INFO] 텔레그램 알림 비활성화 (토큰/chat_id 없음)")

    def send(self, message: str, silent: bool = False) -> bool:
        """메시지 전송"""
        if not self.enabled:
            return False

        try:
            url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            data = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': 'HTML',
                'disable_notification': silent
            }
            response = requests.post(url, data=data, timeout=10)
            return response.status_code == 200
        except Exception:
            return False

    def send_status(self, balance: float, daily_pnl: float, positions: dict):
        """상태 요약 전송"""
        pos_count = len(positions)
        pnl_pct = (daily_pnl / balance * 100) if balance > 0 else 0

        msg = f"📊 <b>상태 업데이트</b>\n"
        msg += f"━━━━━━━━━━━━━━━\n"
        msg += f"💰 잔고: {balance:.2f} USDT\n"
        msg += f"📈 일일손익: {daily_pnl:+.2f} ({pnl_pct:+.2f}%)\n"
        msg += f"📍 포지션: {pos_count}개\n"

        if positions:
            msg += f"━━━━━━━━━━━━━━━\n"
            for symbol, pos in positions.items():
                coin = symbol.replace('/USDT', '')
                msg += f"  {coin}: {pos.side} {pos.calculate_pnl(pos.entry_price):+.2f}%\n"

        self.send(msg, silent=True)

    def send_trade(self, action: str, symbol: str, side: str, price: float, pnl: float = None):
        """거래 알림"""
        coin = symbol.replace('/USDT', '')
        emoji = "🟢" if action == "진입" else "🔴"

        msg = f"{emoji} <b>{action}</b>\n"
        msg += f"━━━━━━━━━━━━━━━\n"
        msg += f"코인: {coin}\n"
        msg += f"방향: {side}\n"
        msg += f"가격: {price:.4f}\n"

        if pnl is not None:
            msg += f"손익: {pnl:+.2f}%\n"

        self.send(msg)

    def send_error(self, error: str):
        """에러 알림"""
        msg = f"⚠️ <b>에러 발생</b>\n{error}"
        self.send(msg)


# 전역 텔레그램 인스턴스
_telegram: TelegramNotifier = None

def get_telegram() -> TelegramNotifier:
    global _telegram
    if _telegram is None:
        _telegram = TelegramNotifier()
    return _telegram


# ==================== 유틸리티 ====================
class Logger:
    """로깅"""
    def __init__(self, log_file: str):
        self.log_file = log_file
        self.trade_history = self._load_trade_history()

    def _load_trade_history(self) -> list:
        """거래 기록 로드"""
        if os.path.exists(Config.TRADE_HISTORY_FILE):
            try:
                with open(Config.TRADE_HISTORY_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return []

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

    def get_period_stats(self, days: int = None) -> dict:
        """기간별 수익 통계 계산

        Args:
            days: None=전체, 1=일일, 7=주간, 30=월간

        Returns:
            dict: {trades, wins, losses, total_pnl, win_rate}
        """
        if not self.trade_history:
            return {'trades': 0, 'wins': 0, 'losses': 0, 'total_pnl': 0, 'win_rate': 0}

        now = datetime.now()
        filtered_trades = []

        for trade in self.trade_history:
            try:
                trade_time = datetime.fromisoformat(trade.get('timestamp', ''))
                if days is None or (now - trade_time).days < days:
                    filtered_trades.append(trade)
            except:
                continue

        if not filtered_trades:
            return {'trades': 0, 'wins': 0, 'losses': 0, 'total_pnl': 0, 'win_rate': 0}

        wins = sum(1 for t in filtered_trades if t.get('pnl_amount', 0) > 0)
        losses = len(filtered_trades) - wins
        total_pnl = sum(t.get('pnl_amount', 0) for t in filtered_trades)
        win_rate = (wins / len(filtered_trades) * 100) if filtered_trades else 0

        return {
            'trades': len(filtered_trades),
            'wins': wins,
            'losses': losses,
            'total_pnl': total_pnl,
            'win_rate': win_rate
        }


# ==================== API ====================
class BinanceAPI:
    """바이낸스 API"""
    def __init__(self, logger: Logger):
        self.logger = logger
        self.simulation_balance = Config.SIMULATION_BALANCE

        if Config.MODE == "simulation":
            self.logger.info("시뮬레이션 모드 - API 연결 없이 가상 거래")
            # 시뮬레이션에서도 시세 조회용 퍼블릭 API 사용
            self.exchange = ccxt.binance({
                'enableRateLimit': True,
                'options': {'defaultType': 'future'}
            })
            # ATR 기반 변동성 관리자 초기화
            get_volatility_manager(self.exchange)
        else:
            self._init_exchange()

    def _init_exchange(self):
        """거래소 초기화"""
        api_key, api_secret = Config.get_api_credentials()

        self.exchange = ccxt.binance({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future',
                'adjustForTimeDifference': True,
                'recvWindow': 60000  # 60초 허용 (기본 5초)
            }
        })

        # 시간 동기화 (Timestamp 오류 방지)
        try:
            self.exchange.load_time_difference()
            self.exchange.load_markets()
            time_offset = getattr(self.exchange, 'options', {}).get('timeDifference', 0)
            self.logger.info(f"바이낸스 시간 동기화 완료 (오프셋: {time_offset}ms)")
        except Exception as e:
            self.logger.warning(f"시간 동기화 중 오류: {e}")

        if Config.MODE == "testnet":
            self.exchange.urls['api'] = {
                'public': 'https://testnet.binancefuture.com/fapi/v1',
                'private': 'https://testnet.binancefuture.com/fapi/v1',
                'v1': 'https://testnet.binancefuture.com/fapi/v1',
                'v2': 'https://testnet.binancefuture.com/fapi/v2',
            }
            self.exchange.urls['fapiPublic'] = 'https://testnet.binancefuture.com/fapi/v1'
            self.exchange.urls['fapiPrivate'] = 'https://testnet.binancefuture.com/fapi/v1'
            self.logger.info("연습 모드 (데모 트레이딩)")
        else:
            self.logger.warning("=" * 60)
            self.logger.warning("실전 모드 활성화 - 실제 자금이 사용됩니다!")
            self.logger.warning("=" * 60)
            time.sleep(3)

        # ATR 기반 변동성 관리자 초기화
        get_volatility_manager(self.exchange)

    def _resync_time(self):
        """시간 재동기화 (Timestamp 오류 발생 시)"""
        try:
            self.exchange.load_time_difference()
            self.logger.info("시간 재동기화 완료")
        except Exception:
            pass

    def _is_timestamp_error(self, error) -> bool:
        """Timestamp 관련 오류인지 확인"""
        return '-1021' in str(error)

    def get_balance(self) -> float:
        """USDT 잔고"""
        if Config.MODE == "simulation":
            return self.simulation_balance

        for attempt in range(2):
            try:
                balance = self.exchange.fetch_balance()
                return balance['USDT']['free']
            except Exception as e:
                if attempt == 0 and self._is_timestamp_error(e):
                    self._resync_time()
                    continue
                self.logger.error(f"잔고 조회 실패: {e}")
                return 0
        return 0

    def update_simulation_balance(self, amount: float):
        """시뮬레이션 잔고 업데이트"""
        if Config.MODE == "simulation":
            self.simulation_balance += amount

    def get_price(self, symbol: str) -> Optional[float]:
        """현재가"""
        if Config.MODE == "simulation":
            try:
                url = f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={symbol.replace('/', '')}"
                response = requests.get(url, timeout=10)
                data = response.json()
                return float(data['price'])
            except Exception as e:
                self.logger.error(f"{symbol} 가격 조회 실패: {e}")
                return None

        for attempt in range(2):
            try:
                ticker = self.exchange.fetch_ticker(symbol)
                return ticker['last']
            except Exception as e:
                if attempt == 0 and self._is_timestamp_error(e):
                    self._resync_time()
                    continue
                self.logger.error(f"{symbol} 가격 조회 실패: {e}")
                return None
        return None

    def get_candles(self, symbol: str, timeframe: str = '1h', limit: int = 100) -> Optional[pd.DataFrame]:
        """캔들 데이터"""
        try:
            symbol_formatted = symbol.replace('/', '')
            params = {'symbol': symbol_formatted, 'interval': timeframe, 'limit': limit}

            if Config.MODE in ["simulation", "testnet"]:
                url = 'https://fapi.binance.com/fapi/v1/klines'
                response = requests.get(url, params=params, timeout=10)
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

    def fetch_positions(self) -> List[Dict]:
        """바이낸스 실제 포지션 조회"""
        if Config.MODE == "simulation":
            return []

        for attempt in range(2):
            try:
                positions = self.exchange.fetch_positions()
                # 실제 보유 중인 포지션만 필터 (수량 > 0)
                active = []
                for pos in positions:
                    amount = abs(float(pos.get('contracts', 0) or 0))
                    if amount > 0:
                        active.append({
                            'symbol': pos['symbol'],
                            'side': 'BUY' if pos.get('side') == 'long' else 'SELL',
                            'quantity': amount,
                            'entry_price': float(pos.get('entryPrice', 0) or 0),
                            'unrealized_pnl': float(pos.get('unrealizedPnl', 0) or 0),
                            'leverage': int(pos.get('leverage', Config.LEVERAGE) or Config.LEVERAGE),
                        })
                return active
            except Exception as e:
                if attempt == 0 and self._is_timestamp_error(e):
                    self._resync_time()
                    continue
                self.logger.error(f"포지션 조회 실패: {e}")
                return []
        return []

    def set_leverage(self, symbol: str, leverage: int) -> bool:
        """레버리지 설정"""
        if Config.MODE == "simulation":
            return True

        try:
            # ccxt 표준 메서드 사용
            self.exchange.set_leverage(leverage, symbol)
            return True
        except Exception as e:
            self.logger.error(f"레버리지 설정 실패: {e}")
            return False

    def get_min_quantity(self, symbol: str) -> float:
        """심볼별 최소 주문 수량 반환"""
        # Binance Futures 최소 수량 (정밀도)
        min_quantities = {
            'BTC/USDT': 0.001,
            'ETH/USDT': 0.001,
            'SOL/USDT': 0.01,
            'DOGE/USDT': 1.0,
        }
        return min_quantities.get(symbol, 0.001)

    def round_quantity(self, symbol: str, quantity: float) -> float:
        """심볼에 맞게 수량 반올림"""
        min_qty = self.get_min_quantity(symbol)

        # 최소 수량의 자릿수에 맞춰 반올림
        if min_qty >= 1:
            return round(quantity)
        elif min_qty >= 0.01:
            return round(quantity, 2)
        elif min_qty >= 0.001:
            return round(quantity, 3)
        else:
            return round(quantity, 6)

    def create_order(self, symbol: str, side: str, amount: float, reduce_only: bool = False) -> Optional[dict]:
        """주문 생성 (reduce_only=True면 최소 금액 제한 우회)"""
        # 수량 반올림 (심볼별 정밀도에 맞게)
        amount = self.round_quantity(symbol, amount)

        # 최소 수량 체크
        min_qty = self.get_min_quantity(symbol)
        if amount < min_qty:
            self.logger.error(f"주문 수량 부족: {amount} < {min_qty} ({symbol})")
            return None

        if Config.MODE == "simulation":
            price = self.get_price(symbol)
            if not price:
                return None

            self.logger.success(f"[시뮬레이션] 주문 체결: {symbol} {side.upper()} {amount:.6f}")
            return {
                'average': price,
                'price': price,
                'amount': amount,
                'side': side,
                'symbol': symbol
            }

        try:
            params = {'reduceOnly': True} if reduce_only else {}
            order = self.exchange.create_market_order(symbol, side, amount, params=params)
            self.logger.success(f"주문 체결: {symbol} {side.upper()} {amount}")
            return order
        except Exception as e:
            self.logger.error(f"주문 실패: {e}")
            return None

    def place_stop_loss(self, symbol: str, side: str, amount: float, stop_price: float) -> Optional[str]:
        """서버 측 손절 주문 등록 (봇 종료 시에도 보호)

        Args:
            symbol: 심볼
            side: 포지션 방향 (BUY/SELL) - 손절은 반대로 실행
            amount: 수량
            stop_price: 손절 가격

        Returns:
            주문 ID (성공 시) 또는 None
        """
        if Config.MODE == "simulation":
            return "sim_stop_" + symbol.replace('/', '')

        # 손절은 포지션 반대 방향
        close_side = 'sell' if side == 'BUY' else 'buy'

        # 가격 소수점 정리
        price_precision = 2
        if stop_price > 1000:
            price_precision = 1
        elif stop_price < 1:
            price_precision = 4
        stop_price = round(stop_price, price_precision)

        # ccxt create_stop_loss_order 사용 (Algo Order API 자동 라우팅)
        try:
            order = self.exchange.create_stop_loss_order(
                symbol, 'market', close_side, amount,
                stopLossPrice=stop_price,
                params={'reduceOnly': True, 'workingType': 'MARK_PRICE'}
            )
            order_id = order.get('id', '')
            self.logger.info(f"🛡️ 서버 손절 등록: {symbol} @ {stop_price} (ID: {order_id})")
            return order_id
        except Exception as e:
            self.logger.warning(f"서버 손절 stop_loss_order 실패: {e}")

        # fallback: create_stop_order
        try:
            order = self.exchange.create_stop_order(
                symbol, 'market', close_side, amount,
                stopPrice=stop_price,
                params={'reduceOnly': True, 'workingType': 'MARK_PRICE'}
            )
            order_id = order.get('id', '')
            self.logger.info(f"🛡️ 서버 손절 등록 (stop_order): {symbol} @ {stop_price} (ID: {order_id})")
            return order_id
        except Exception as e2:
            self.logger.error(f"서버 손절 등록 실패: {symbol} @ {stop_price} - {e2}")
            return None

    def cancel_stop_loss(self, symbol: str, order_id: str) -> bool:
        """서버 측 손절 주문 취소"""
        if Config.MODE == "simulation" or not order_id:
            return True

        if order_id.startswith('sim_'):
            return True

        try:
            self.exchange.cancel_order(order_id, symbol)
            self.logger.info(f"🛡️ 서버 손절 취소: {symbol} (ID: {order_id})")
            return True
        except Exception as e:
            # 이미 체결/취소된 경우 무시
            if 'Unknown order' in str(e) or 'UNKNOWN_ORDER' in str(e):
                return True
            self.logger.warning(f"서버 손절 취소 실패: {e}")
            return False

    def update_stop_loss(self, symbol: str, side: str, amount: float,
                         new_stop_price: float, old_order_id: str) -> Optional[str]:
        """서버 측 손절 주문 갱신 (기존 취소 → 새로 등록)"""
        self.cancel_stop_loss(symbol, old_order_id)
        return self.place_stop_loss(symbol, side, amount, new_stop_price)


# ==================== 시장 상태 분석 ====================
class MarketAnalyzer:
    """시장 상태 분석 - 급등/급락/정상 판단"""

    def __init__(self, api: 'BinanceAPI', logger: Logger):
        self.api = api
        self.logger = logger
        self._cache = {}
        self._cache_time = None
        self._cache_ttl = 60  # 60초 캐시

    def analyze_market(self, symbols: List[str]) -> Dict:
        """시장 전체 상태 분석"""
        now = datetime.now()

        # 캐시 확인
        if self._cache_time and (now - self._cache_time).total_seconds() < self._cache_ttl:
            return self._cache

        results = {
            'condition': 'normal',  # normal, crash, rally, volatile
            'crash_count': 0,
            'rally_count': 0,
            'avg_change': 0,
            'entry_allowed': True,
            'score_adjustment': 0,
            'position_multiplier': 1.0,
            'details': {}
        }

        changes = []

        for symbol in symbols:
            df = self.api.get_candles(symbol, '1h', 24)
            if df is None or len(df) < 24:
                continue

            # 1시간 변화율
            change_1h = (df['close'].iloc[-1] / df['close'].iloc[-2] - 1) * 100
            # 4시간 변화율
            change_4h = (df['close'].iloc[-1] / df['close'].iloc[-5] - 1) * 100 if len(df) >= 5 else 0
            # 24시간 변화율
            change_24h = (df['close'].iloc[-1] / df['close'].iloc[0] - 1) * 100

            changes.append(change_1h)

            coin = symbol.replace('/USDT', '')
            results['details'][coin] = {
                '1h': change_1h,
                '4h': change_4h,
                '24h': change_24h
            }

            # 급락 판정: 1시간 -3% 이하 또는 4시간 -5% 이하
            if change_1h <= -3 or change_4h <= -5:
                results['crash_count'] += 1

            # 급등 판정: 1시간 +3% 이상 또는 4시간 +5% 이상
            if change_1h >= 3 or change_4h >= 5:
                results['rally_count'] += 1

        if changes:
            results['avg_change'] = sum(changes) / len(changes)

        total = len(symbols)
        crash_ratio = results['crash_count'] / total if total > 0 else 0
        rally_ratio = results['rally_count'] / total if total > 0 else 0

        # 시장 상태 판정
        if crash_ratio >= 0.5:  # 50% 이상 급락
            results['condition'] = 'crash'
            results['entry_allowed'] = False  # LONG 진입 금지
            results['score_adjustment'] = -0.3
            results['position_multiplier'] = 0.5
            self.logger.warning(f"⚠️ 시장 급락 감지! {results['crash_count']}/{total} 코인 급락 중")
        elif rally_ratio >= 0.5:  # 50% 이상 급등
            results['condition'] = 'rally'
            results['entry_allowed'] = True
            results['score_adjustment'] = 0.1
            results['position_multiplier'] = 0.8  # 급등 시에도 조금 조심
        elif abs(results['avg_change']) > 2:  # 변동성 큼
            results['condition'] = 'volatile'
            results['entry_allowed'] = True
            results['score_adjustment'] = -0.1
            results['position_multiplier'] = 0.7

        # 캐시 업데이트
        self._cache = results
        self._cache_time = now

        return results

    def is_entry_allowed(self, side: str, symbols: List[str]) -> tuple:
        """진입 허용 여부 확인"""
        market = self.analyze_market(symbols)

        # 급락장에서 LONG 금지
        if market['condition'] == 'crash' and side == 'BUY':
            return False, "시장 급락 중 - LONG 진입 금지"

        # 급등장에서 SHORT 금지
        if market['condition'] == 'rally' and side == 'SELL':
            return False, "시장 급등 중 - SHORT 진입 금지"

        return True, ""


# ==================== ML 예측 ====================
class MLPredictor:
    """머신러닝 기반 예측"""

    def __init__(self, logger: Logger):
        self.logger = logger
        self.model = None
        self.scaler = None
        self.is_trained = False
        self._load_model()

    def _load_model(self):
        """저장된 모델 로드"""
        if os.path.exists(Config.ML_MODEL_FILE):
            try:
                with open(Config.ML_MODEL_FILE, 'rb') as f:
                    data = pickle.load(f)
                    self.model = data['model']
                    self.scaler = data['scaler']
                    self.is_trained = True
                    self.logger.info("ML 모델 로드 완료")
            except Exception as e:
                self.logger.error(f"ML 모델 로드 실패: {e}")

    def _create_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """특성 생성"""
        features = pd.DataFrame(index=df.index)

        # 수익률
        features['returns_1h'] = df['close'].pct_change(1)
        features['returns_4h'] = df['close'].pct_change(4)
        features['returns_24h'] = df['close'].pct_change(24)

        # 이동평균
        for period in [10, 20, 50]:
            features[f'sma_{period}'] = df['close'].rolling(period).mean()
            features[f'price_to_sma_{period}'] = df['close'] / features[f'sma_{period}']

        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        features['rsi'] = 100 - (100 / (1 + rs))

        # MACD
        ema_12 = df['close'].ewm(span=12).mean()
        ema_26 = df['close'].ewm(span=26).mean()
        features['macd'] = ema_12 - ema_26
        features['macd_signal'] = features['macd'].ewm(span=9).mean()

        # 볼린저 밴드
        sma_20 = df['close'].rolling(20).mean()
        std_20 = df['close'].rolling(20).std()
        features['bb_position'] = (df['close'] - (sma_20 - std_20 * 2)) / ((sma_20 + std_20 * 2) - (sma_20 - std_20 * 2))

        # 변동성
        features['volatility'] = df['close'].pct_change().rolling(20).std()

        # 거래량
        features['volume_sma'] = df['volume'].rolling(20).mean()
        features['volume_ratio'] = df['volume'] / features['volume_sma']

        return features

    def train(self, api: BinanceAPI, symbols: List[str]):
        """모델 학습"""
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.preprocessing import StandardScaler
        from sklearn.model_selection import train_test_split

        self.logger.info("ML 모델 학습 시작...")

        all_features = []
        all_labels = []

        for symbol in symbols:
            df = api.get_candles(symbol, '1h', 500)
            if df is None or len(df) < 200:
                continue

            features = self._create_features(df)

            # 레이블: 6시간 후 1.5% 이상 상승
            future_returns = df['close'].shift(-6) / df['close'] - 1
            labels = (future_returns > 0.015).astype(int)

            valid_idx = ~(features.isna().any(axis=1) | labels.isna())
            features = features[valid_idx]
            labels = labels[valid_idx]

            if len(features) > 50:
                all_features.append(features)
                all_labels.append(labels)

        if not all_features:
            self.logger.error("학습 데이터 부족")
            return False

        X = pd.concat(all_features, ignore_index=True)
        y = pd.concat(all_labels, ignore_index=True)

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        self.scaler = StandardScaler()
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)

        self.model = RandomForestClassifier(
            n_estimators=100, max_depth=10, random_state=42, n_jobs=1
        )
        self.model.fit(X_train_scaled, y_train)

        train_score = self.model.score(X_train_scaled, y_train)
        test_score = self.model.score(X_test_scaled, y_test)

        self.logger.info(f"ML 학습 완료 - 학습: {train_score:.1%}, 테스트: {test_score:.1%}")

        # 모델 저장
        with open(Config.ML_MODEL_FILE, 'wb') as f:
            pickle.dump({'model': self.model, 'scaler': self.scaler}, f)

        self.is_trained = True
        return True

    def predict(self, df: pd.DataFrame) -> Optional[Dict]:
        """예측"""
        if not self.is_trained or self.model is None:
            return None

        try:
            features = self._create_features(df)
            latest = features.iloc[-1:].dropna(axis=1)

            if latest.empty:
                return None

            # 학습 시 사용한 컬럼만 선택
            feature_cols = [c for c in latest.columns if c in features.columns]
            latest = latest[feature_cols]

            scaled = self.scaler.transform(latest)
            prob = self.model.predict_proba(scaled)[0]

            buy_prob = float(prob[1]) if len(prob) > 1 else 0.5
            sell_prob = float(prob[0]) if len(prob) > 1 else 0.5

            return {
                'buy_probability': buy_prob,
                'sell_probability': sell_prob,
                'confidence': float(max(prob))
            }
        except Exception as e:
            return None


# ==================== 고급 ML 예측 (Phase 2) ====================
class AdvancedMLPredictor:
    """고급 ML 예측 - XGBoost + LightGBM + RandomForest 앙상블"""

    def __init__(self, logger: Logger):
        self.logger = logger
        self.models = {}
        self.scaler = None
        self.is_trained = False
        self.feature_names = []

        # 모델 가중치
        self.model_weights = {
            'xgboost': 0.4,
            'lightgbm': 0.35,
            'random_forest': 0.25
        }

        self._load_models()

    def _load_models(self):
        """저장된 고급 모델 로드"""
        model_file = os.path.join(BASE_PATH, 'binance_advanced_ml.pkl')
        if os.path.exists(model_file):
            try:
                with open(model_file, 'rb') as f:
                    data = pickle.load(f)
                    self.models = data['models']
                    self.scaler = data['scaler']
                    self.feature_names = data.get('feature_names', [])
                    self.is_trained = True
                    self.logger.info("고급 ML 모델 로드 완료 (XGBoost + LightGBM + RF)")
            except Exception as e:
                self.logger.warning(f"고급 ML 로드 실패: {e}")

    def _create_advanced_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """고급 특성 생성"""
        features = pd.DataFrame(index=df.index)

        # 1. 기본 수익률
        for period in [1, 2, 4, 6, 12, 24]:
            features[f'returns_{period}h'] = df['close'].pct_change(period)

        # 2. 이동평균 및 비율
        for period in [5, 10, 20, 50, 100]:
            features[f'sma_{period}'] = df['close'].rolling(period).mean()
            features[f'ema_{period}'] = df['close'].ewm(span=period).mean()
            features[f'price_sma_ratio_{period}'] = df['close'] / features[f'sma_{period}']

        # 3. RSI (다중 기간)
        for period in [7, 14, 21]:
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
            rs = gain / (loss + 1e-10)
            features[f'rsi_{period}'] = 100 - (100 / (1 + rs))

        # 4. MACD
        ema_12 = df['close'].ewm(span=12).mean()
        ema_26 = df['close'].ewm(span=26).mean()
        features['macd'] = ema_12 - ema_26
        features['macd_signal'] = features['macd'].ewm(span=9).mean()
        features['macd_hist'] = features['macd'] - features['macd_signal']

        # 5. 볼린저 밴드
        sma_20 = df['close'].rolling(20).mean()
        std_20 = df['close'].rolling(20).std()
        features['bb_upper'] = sma_20 + (std_20 * 2)
        features['bb_lower'] = sma_20 - (std_20 * 2)
        features['bb_width'] = (features['bb_upper'] - features['bb_lower']) / sma_20
        features['bb_position'] = (df['close'] - features['bb_lower']) / (features['bb_upper'] - features['bb_lower'] + 1e-10)

        # 6. ATR (Average True Range)
        high_low = df['high'] - df['low']
        high_close = abs(df['high'] - df['close'].shift())
        low_close = abs(df['low'] - df['close'].shift())
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        features['atr_14'] = tr.rolling(14).mean()
        features['atr_ratio'] = features['atr_14'] / df['close']

        # 7. 변동성
        features['volatility_5'] = df['close'].pct_change().rolling(5).std()
        features['volatility_20'] = df['close'].pct_change().rolling(20).std()
        features['volatility_ratio'] = features['volatility_5'] / (features['volatility_20'] + 1e-10)

        # 8. 거래량 지표
        features['volume_sma_5'] = df['volume'].rolling(5).mean()
        features['volume_sma_20'] = df['volume'].rolling(20).mean()
        features['volume_ratio'] = df['volume'] / (features['volume_sma_20'] + 1e-10)
        features['volume_trend'] = features['volume_sma_5'] / (features['volume_sma_20'] + 1e-10)

        # 9. 모멘텀 지표
        features['momentum_10'] = df['close'] / df['close'].shift(10) - 1
        features['momentum_20'] = df['close'] / df['close'].shift(20) - 1

        # 10. 고가/저가 비율
        features['high_low_ratio'] = df['high'] / (df['low'] + 1e-10)
        features['close_high_ratio'] = df['close'] / (df['high'] + 1e-10)
        features['close_low_ratio'] = df['close'] / (df['low'] + 1e-10)

        # 11. 캔들 패턴
        features['candle_body'] = (df['close'] - df['open']) / (df['open'] + 1e-10)
        features['upper_shadow'] = (df['high'] - df[['close', 'open']].max(axis=1)) / (df['high'] + 1e-10)
        features['lower_shadow'] = (df[['close', 'open']].min(axis=1) - df['low']) / (df['low'] + 1e-10)

        return features

    def train(self, api: 'BinanceAPI', symbols: List[str]):
        """고급 모델 학습"""
        try:
            from xgboost import XGBClassifier
            from lightgbm import LGBMClassifier
            from sklearn.ensemble import RandomForestClassifier
            from sklearn.preprocessing import StandardScaler
            from sklearn.model_selection import train_test_split
        except ImportError as e:
            self.logger.warning(f"고급 ML 라이브러리 없음: {e}")
            self.logger.info("pip install xgboost lightgbm 실행 필요")
            return False

        self.logger.info("고급 ML 학습 시작 (XGBoost + LightGBM + RF)...")

        all_features = []
        all_labels = []

        for symbol in symbols:
            df = api.get_candles(symbol, '1h', 500)
            if df is None or len(df) < 200:
                continue

            features = self._create_advanced_features(df)

            # 레이블: 6시간 후 1.5% 이상 상승 = 2, 1.5% 이상 하락 = 0, 그 외 = 1
            # (XGBoost는 0부터 시작하는 클래스 필요: 0=하락, 1=횡보, 2=상승)
            future_returns = df['close'].shift(-6) / df['close'] - 1
            labels = pd.Series(1, index=df.index)  # 기본값: 횡보(1)
            labels[future_returns > 0.015] = 2  # 상승
            labels[future_returns < -0.015] = 0  # 하락

            valid_idx = ~(features.isna().any(axis=1) | labels.isna())
            features = features[valid_idx]
            labels = labels[valid_idx]

            if len(features) > 50:
                all_features.append(features)
                all_labels.append(labels)

        if not all_features:
            self.logger.error("학습 데이터 부족")
            return False

        X = pd.concat(all_features, ignore_index=True)
        y = pd.concat(all_labels, ignore_index=True)

        self.feature_names = list(X.columns)

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        self.scaler = StandardScaler()
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)

        # 모델 학습
        self.models = {}

        # XGBoost
        self.logger.info("  XGBoost 학습 중...")
        self.models['xgboost'] = XGBClassifier(
            n_estimators=100, max_depth=6, learning_rate=0.1,
            random_state=42, verbosity=0, use_label_encoder=False
        )
        self.models['xgboost'].fit(X_train_scaled, y_train)

        # LightGBM
        self.logger.info("  LightGBM 학습 중...")
        self.models['lightgbm'] = LGBMClassifier(
            n_estimators=100, max_depth=6, learning_rate=0.1,
            random_state=42, verbosity=-1
        )
        self.models['lightgbm'].fit(X_train_scaled, y_train)

        # RandomForest
        self.logger.info("  RandomForest 학습 중...")
        self.models['random_forest'] = RandomForestClassifier(
            n_estimators=100, max_depth=10, random_state=42, n_jobs=-1
        )
        self.models['random_forest'].fit(X_train_scaled, y_train)

        # 성능 평가
        for name, model in self.models.items():
            train_score = model.score(X_train_scaled, y_train)
            test_score = model.score(X_test_scaled, y_test)
            self.logger.info(f"  {name}: 학습 {train_score:.1%}, 테스트 {test_score:.1%}")

        # 모델 저장
        model_file = os.path.join(BASE_PATH, 'binance_advanced_ml.pkl')
        with open(model_file, 'wb') as f:
            pickle.dump({
                'models': self.models,
                'scaler': self.scaler,
                'feature_names': self.feature_names
            }, f)

        self.is_trained = True
        self.logger.success("고급 ML 학습 완료!")
        return True

    def predict(self, df: pd.DataFrame) -> Optional[Dict]:
        """앙상블 예측"""
        if not self.is_trained or not self.models:
            return None

        try:
            features = self._create_advanced_features(df)
            latest = features.iloc[-1:].copy()

            # NaN 처리
            latest = latest.fillna(0)

            # 학습 시 사용한 피처만 선택
            if self.feature_names:
                missing = set(self.feature_names) - set(latest.columns)
                for col in missing:
                    latest[col] = 0
                latest = latest[self.feature_names]

            scaled = self.scaler.transform(latest)

            # 각 모델 예측
            predictions = {}
            probabilities = {}

            for name, model in self.models.items():
                pred = model.predict(scaled)[0]
                prob = model.predict_proba(scaled)[0]
                predictions[name] = pred
                probabilities[name] = prob

            # 가중 평균 확률 계산
            weighted_prob = np.zeros(3)  # [0, 1, 2] -> [하락, 횡보, 상승]
            for name, prob in probabilities.items():
                weight = self.model_weights.get(name, 0.33)
                weighted_prob += prob * weight

            # 정규화
            weighted_prob = weighted_prob / weighted_prob.sum()

            # 클래스 매핑: 0=하락(-1), 1=횡보(0), 2=상승(1)
            sell_prob = float(weighted_prob[0])  # 하락
            hold_prob = float(weighted_prob[1])  # 횡보
            buy_prob = float(weighted_prob[2])   # 상승

            return {
                'buy_probability': buy_prob,
                'sell_probability': sell_prob,
                'hold_probability': hold_prob,
                'confidence': float(max(weighted_prob)),
                'ensemble_prediction': int(np.argmax(weighted_prob)) - 1,  # -1, 0, 1
                'model_predictions': predictions
            }

        except Exception as e:
            self.logger.error(f"고급 ML 예측 실패: {e}")
            return None


# ==================== 전략 ====================
class Strategy:
    """멀티 타임프레임 + ML 통합 전략 (고급 ML 지원)"""

    def __init__(self, ml_predictor: Optional[MLPredictor] = None,
                 advanced_ml: Optional['AdvancedMLPredictor'] = None):
        self.ml_predictor = ml_predictor
        self.advanced_ml = advanced_ml

    @staticmethod
    def get_trend(df: pd.DataFrame) -> str:
        """4시간 봉 기준 추세 판단"""
        if len(df) < 50:
            return 'NEUTRAL'

        ma50 = ta.trend.sma_indicator(df['close'], window=50)
        current_price = df['close'].iloc[-1]

        if current_price > ma50.iloc[-1]:
            return 'UP'
        elif current_price < ma50.iloc[-1]:
            return 'DOWN'
        return 'NEUTRAL'

    @staticmethod
    def rsi(df: pd.DataFrame) -> Optional[str]:
        if len(df) < 20:
            return None
        rsi = ta.momentum.RSIIndicator(df['close'], window=14).rsi().iloc[-1]
        if rsi < 30:
            return 'BUY'
        if rsi > 70:
            return 'SELL'
        return None

    @staticmethod
    def rsi_score(df: pd.DataFrame) -> float:
        """RSI 그라데이션 점수 (-1 ~ +1)"""
        if len(df) < 20:
            return 0.0
        rsi = ta.momentum.RSIIndicator(df['close'], window=14).rsi().iloc[-1]
        # 50 기준: 30이하 → +1.0, 70이상 → -1.0, 50 → 0.0
        return max(-1.0, min(1.0, (50 - rsi) / 30))

    @staticmethod
    def ma_cross(df: pd.DataFrame) -> Optional[str]:
        if len(df) < 50:
            return None
        ma20 = df['close'].rolling(20).mean()
        ma50 = df['close'].rolling(50).mean()
        if ma20.iloc[-2] <= ma50.iloc[-2] and ma20.iloc[-1] > ma50.iloc[-1]:
            return 'BUY'
        if ma20.iloc[-2] >= ma50.iloc[-2] and ma20.iloc[-1] < ma50.iloc[-1]:
            return 'SELL'
        return None

    @staticmethod
    def ma_cross_score(df: pd.DataFrame) -> float:
        """이평선 이격도 기반 점수 (-1 ~ +1)"""
        if len(df) < 50:
            return 0.0
        ma20 = df['close'].rolling(20).mean().iloc[-1]
        ma50 = df['close'].rolling(50).mean().iloc[-1]
        if ma50 == 0:
            return 0.0
        # MA20이 MA50 대비 몇 % 위/아래인지 (±2% → ±1.0)
        diff_pct = (ma20 - ma50) / ma50 * 100
        return max(-1.0, min(1.0, diff_pct / 2.0))

    @staticmethod
    def macd(df: pd.DataFrame) -> Optional[str]:
        if len(df) < 35:
            return None
        macd_ind = ta.trend.MACD(df['close'])
        macd = macd_ind.macd()
        signal = macd_ind.macd_signal()
        if macd.iloc[-2] <= signal.iloc[-2] and macd.iloc[-1] > signal.iloc[-1]:
            return 'BUY'
        if macd.iloc[-2] >= signal.iloc[-2] and macd.iloc[-1] < signal.iloc[-1]:
            return 'SELL'
        return None

    @staticmethod
    def macd_score(df: pd.DataFrame) -> float:
        """MACD 히스토그램 기반 점수 (-1 ~ +1)"""
        if len(df) < 35:
            return 0.0
        macd_ind = ta.trend.MACD(df['close'])
        histogram = macd_ind.macd_diff().iloc[-1]
        price = df['close'].iloc[-1]
        if price == 0:
            return 0.0
        # 히스토그램을 가격 대비 비율로 정규화
        normalized = (histogram / price) * 1000
        return max(-1.0, min(1.0, normalized))

    @staticmethod
    def bollinger(df: pd.DataFrame) -> Optional[str]:
        if len(df) < 20:
            return None
        bb = ta.volatility.BollingerBands(df['close'], window=20)
        if df['close'].iloc[-1] <= bb.bollinger_lband().iloc[-1]:
            return 'BUY'
        if df['close'].iloc[-1] >= bb.bollinger_hband().iloc[-1]:
            return 'SELL'
        return None

    @staticmethod
    def bollinger_score(df: pd.DataFrame) -> float:
        """볼린저밴드 %B 기반 점수 (-1 ~ +1)"""
        if len(df) < 20:
            return 0.0
        bb = ta.volatility.BollingerBands(df['close'], window=20)
        upper = bb.bollinger_hband().iloc[-1]
        lower = bb.bollinger_lband().iloc[-1]
        price = df['close'].iloc[-1]
        if upper == lower:
            return 0.0
        # %B: 0(하단)~1(상단), 0.5(중간) → 점수로 변환 (중간=0, 상단=-1, 하단=+1)
        pct_b = (price - lower) / (upper - lower)
        return max(-1.0, min(1.0, (0.5 - pct_b) * 2))

    @staticmethod
    def stochastic(df: pd.DataFrame) -> Optional[str]:
        if len(df) < 20:
            return None
        stoch = ta.momentum.StochasticOscillator(df['high'], df['low'], df['close'])
        k, d = stoch.stoch().iloc[-1], stoch.stoch_signal().iloc[-1]
        k_prev, d_prev = stoch.stoch().iloc[-2], stoch.stoch_signal().iloc[-2]
        if k < 20 and d < 20 and k_prev <= d_prev and k > d:
            return 'BUY'
        if k > 80 and d > 80 and k_prev >= d_prev and k < d:
            return 'SELL'
        return None

    @staticmethod
    def stochastic_score(df: pd.DataFrame) -> float:
        """스토캐스틱 %K 기반 점수 (-1 ~ +1)"""
        if len(df) < 20:
            return 0.0
        stoch = ta.momentum.StochasticOscillator(df['high'], df['low'], df['close'])
        k = stoch.stoch().iloc[-1]
        # 50 기준: 0 → +1.0(과매도), 100 → -1.0(과매수)
        return max(-1.0, min(1.0, (50 - k) / 50))

    def analyze(self, df_base: pd.DataFrame, df_trend: pd.DataFrame) -> Dict:
        """통합 분석 (고급 ML 지원)"""
        indicators = {
            'RSI': self.rsi(df_base),
            'MA_Cross': self.ma_cross(df_base),
            'MACD': self.macd(df_base),
            'Bollinger': self.bollinger(df_base),
            'Stochastic': self.stochastic(df_base)
        }

        market_trend = self.get_trend(df_trend)

        buy_count = sum(1 for s in indicators.values() if s == 'BUY')
        sell_count = sum(1 for s in indicators.values() if s == 'SELL')

        # 기술적 점수: 그라데이션 방식 (5개 지표 평균, -1 ~ +1)
        gradient_scores = [
            self.rsi_score(df_base),
            self.ma_cross_score(df_base),
            self.macd_score(df_base),
            self.bollinger_score(df_base),
            self.stochastic_score(df_base)
        ]
        tech_score = sum(gradient_scores) / len(gradient_scores)

        # 기본 ML 예측
        ml_score = 0
        ml_prediction = None
        if self.ml_predictor and Config.ML_ENABLED:
            ml_prediction = self.ml_predictor.predict(df_base)
            if ml_prediction:
                ml_score = (ml_prediction['buy_probability'] - 0.5) * 2  # -1 ~ 1

        # 고급 ML 예측 (XGBoost + LightGBM + RF 앙상블)
        advanced_ml_score = 0
        advanced_ml_prediction = None
        if self.advanced_ml and Config.ADVANCED_ML_ENABLED:
            advanced_ml_prediction = self.advanced_ml.predict(df_base)
            if advanced_ml_prediction:
                # 예측 클래스: -1(하락), 0(횡보), 1(상승)
                pred_class = advanced_ml_prediction.get('ensemble_prediction', 0)
                confidence = advanced_ml_prediction.get('confidence', 0.5)
                # 점수로 변환: 클래스 * 신뢰도
                advanced_ml_score = pred_class * confidence

        # 통합 점수 계산
        if Config.ADVANCED_ML_ENABLED and advanced_ml_prediction:
            # 고급 ML 활성화시: 기술적(40%) + 기본ML(20%) + 고급ML(40%)
            tech_weight = 0.4
            basic_ml_weight = Config.ML_WEIGHT * 0.5 if Config.ML_ENABLED else 0
            advanced_ml_weight = Config.ADVANCED_ML_WEIGHT

            # 가중치 정규화
            total_weight = tech_weight + basic_ml_weight + advanced_ml_weight
            final_score = (tech_score * tech_weight +
                          ml_score * basic_ml_weight +
                          advanced_ml_score * advanced_ml_weight) / total_weight
        else:
            # 기존 방식: 기술적 + 기본 ML
            final_score = tech_score * (1 - Config.ML_WEIGHT) + ml_score * Config.ML_WEIGHT

        # 최종 신호 결정
        final_signal = None
        threshold = Config.ENTRY_SCORE_THRESHOLD

        # LONG 조건
        if final_score > threshold:
            trend_ok = market_trend == 'UP' or (Config.ALLOW_SIDEWAYS_ENTRY and market_trend == 'SIDEWAYS')
            ml_ok = not Config.ML_ENABLED or (ml_prediction and ml_prediction.get('buy_probability', 0) >= Config.ML_MIN_PROBABILITY)
            # 고급 ML 체크 (활성화시)
            advanced_ml_ok = (not Config.ADVANCED_ML_ENABLED or
                             (advanced_ml_prediction and advanced_ml_prediction.get('ensemble_prediction', 0) >= 0))
            if trend_ok and ml_ok and advanced_ml_ok:
                final_signal = 'LONG'

        # SHORT 조건
        elif final_score < -threshold:
            trend_ok = market_trend == 'DOWN' or (Config.ALLOW_SIDEWAYS_ENTRY and market_trend == 'SIDEWAYS')
            ml_ok = not Config.ML_ENABLED or (ml_prediction and ml_prediction.get('sell_probability', 0) >= Config.ML_MIN_PROBABILITY)
            # 고급 ML 체크 (활성화시)
            advanced_ml_ok = (not Config.ADVANCED_ML_ENABLED or
                             (advanced_ml_prediction and advanced_ml_prediction.get('ensemble_prediction', 0) <= 0))
            if trend_ok and ml_ok and advanced_ml_ok:
                final_signal = 'SHORT'

        return {
            'signals': indicators,
            'market_trend': market_trend,
            'tech_score': tech_score,
            'ml_prediction': ml_prediction,
            'advanced_ml_prediction': advanced_ml_prediction,
            'final_score': final_score,
            'final_decision': final_signal
        }


# ==================== ATR 기반 적응형 익절 ====================
class AdaptiveVolatilityManager:
    """ATR 기반 변동성 분석 및 적응형 익절 트리거 계산"""

    def __init__(self, exchange):
        self.exchange = exchange
        self.atr_cache = {}
        self.last_update = {}
        self.cache_duration = 300  # 5분 캐시

    def get_atr(self, symbol: str, timeframe: str = '1h', period: int = 14) -> float:
        """ATR (Average True Range) 계산"""
        cache_key = f"{symbol}_{timeframe}"
        now = datetime.now()

        # 캐시 확인
        if cache_key in self.atr_cache:
            elapsed = (now - self.last_update.get(cache_key, datetime.min)).total_seconds()
            if elapsed < self.cache_duration:
                return self.atr_cache[cache_key]

        try:
            # OHLCV 데이터 가져오기
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=period + 10)
            if not ohlcv or len(ohlcv) < period:
                return 0.02  # 기본값 2%

            # True Range 계산
            true_ranges = []
            for i in range(1, len(ohlcv)):
                high = ohlcv[i][2]
                low = ohlcv[i][3]
                prev_close = ohlcv[i-1][4]

                tr = max(
                    high - low,
                    abs(high - prev_close),
                    abs(low - prev_close)
                )
                true_ranges.append(tr)

            # ATR = 평균 True Range
            atr = sum(true_ranges[-period:]) / period

            # ATR을 퍼센트로 변환 (현재가 대비)
            current_price = ohlcv[-1][4]
            atr_pct = (atr / current_price) if current_price > 0 else 0.02

            # 캐시 저장
            self.atr_cache[cache_key] = atr_pct
            self.last_update[cache_key] = now

            return atr_pct

        except Exception:
            return 0.02  # 기본값 2%

    def get_volatility_level(self, symbol: str) -> str:
        """변동성 레벨 판단"""
        atr_pct = self.get_atr(symbol)

        if atr_pct < 0.01:
            return 'low'       # 1% 미만
        elif atr_pct < 0.02:
            return 'normal'    # 1~2%
        elif atr_pct < 0.03:
            return 'high'      # 2~3%
        else:
            return 'extreme'   # 3% 이상

    def get_adaptive_partial_trigger(self, symbol: str) -> float:
        """변동성 기반 적응형 분할 익절 트리거 계산"""
        if not Config.ADAPTIVE_PARTIAL_EXIT:
            return Config.PARTIAL_EXIT_TRIGGER

        atr_pct = self.get_atr(symbol)
        level = self.get_volatility_level(symbol)

        # 변동성에 따른 트리거 조정
        triggers = {
            'low': 0.008,      # 0.8% (화면 2.4%)
            'normal': 0.012,   # 1.2% (화면 3.6%)
            'high': 0.015,     # 1.5% (화면 4.5%)
            'extreme': 0.020   # 2.0% (화면 6.0%)
        }

        trigger = triggers.get(level, Config.PARTIAL_EXIT_TRIGGER)

        return trigger


# 전역 변동성 관리자 (나중에 초기화)
_volatility_manager = None

def get_volatility_manager(exchange=None):
    """변동성 관리자 싱글톤"""
    global _volatility_manager
    if _volatility_manager is None and exchange is not None:
        _volatility_manager = AdaptiveVolatilityManager(exchange)
    return _volatility_manager


# ==================== 포지션 ====================
class Position:
    """포지션 정보 + 트레일링 스탑 + 분할 익절"""

    def __init__(self, symbol: str, side: str, quantity: float, entry_price: float):
        self.symbol = symbol
        self.side = side
        self.quantity = quantity
        self.original_quantity = quantity  # 원래 수량 (분할 익절 전)
        self.entry_price = entry_price
        self.highest_price = entry_price  # 트레일링용 최고가
        self.lowest_price = entry_price   # 트레일링용 최저가
        self.stop_loss = entry_price * (1 - Config.STOP_LOSS_PCT) if side == 'BUY' else entry_price * (1 + Config.STOP_LOSS_PCT)
        self.take_profit = entry_price * (1 + Config.TAKE_PROFIT_PCT) if side == 'BUY' else entry_price * (1 - Config.TAKE_PROFIT_PCT)
        self.trailing_active = False
        self.timestamp = datetime.now()
        # 분할 익절 관련
        self.partial_exit_done = False  # 분할 익절 완료 여부
        self.breakeven_mode = False  # 본전 보호 모드
        # 서버 손절 주문 ID
        self.stop_order_id = None

    def calculate_pnl(self, current_price: float) -> float:
        """손익률 계산 (코인별 레버리지 적용)"""
        leverage = Config.get_leverage(self.symbol)
        if self.side == 'BUY':
            return ((current_price - self.entry_price) / self.entry_price) * 100 * leverage
        else:
            return ((self.entry_price - current_price) / self.entry_price) * 100 * leverage

    def should_partial_exit(self, current_price: float) -> bool:
        """분할 익절 조건 확인 (ATR 기반 적응형)"""
        # 분할 익절 비활성화 체크
        if not Config.PARTIAL_EXIT_ENABLED:
            return False

        if self.partial_exit_done:
            return False

        # 레버리지 미적용 순수 수익률
        if self.side == 'BUY':
            pnl_rate = (current_price - self.entry_price) / self.entry_price
        else:
            pnl_rate = (self.entry_price - current_price) / self.entry_price

        # 적응형 트리거 사용
        vol_manager = get_volatility_manager()
        if vol_manager and Config.ADAPTIVE_PARTIAL_EXIT:
            trigger = vol_manager.get_adaptive_partial_trigger(self.symbol)
        else:
            trigger = Config.PARTIAL_EXIT_TRIGGER

        return pnl_rate >= trigger

    def activate_breakeven_mode(self):
        """본전 보호 모드 활성화 - 분할 익절 후 호출"""
        self.breakeven_mode = True
        # 손절가를 진입가로 이동 (본전 보호)
        if self.side == 'BUY':
            # LONG: 손절가를 진입가 약간 아래로 (수수료 고려)
            self.stop_loss = self.entry_price * 0.998  # 0.2% 버퍼
        else:
            # SHORT: 손절가를 진입가 약간 위로
            self.stop_loss = self.entry_price * 1.002

    def update_trailing_stop(self, current_price: float):
        """트레일링 스탑 업데이트"""
        if not Config.TRAILING_STOP_ENABLED:
            return

        pnl_rate = self.calculate_pnl(current_price) / Config.get_leverage(self.symbol) / 100

        if self.side == 'BUY':
            # 최고가 갱신
            if current_price > self.highest_price:
                self.highest_price = current_price

            # 트레일링 활성화 조건
            if pnl_rate >= Config.TRAILING_STOP_ACTIVATION:
                self.trailing_active = True
                new_stop = self.highest_price * (1 - Config.TRAILING_STOP_DISTANCE)
                if new_stop > self.stop_loss:
                    self.stop_loss = new_stop
        else:
            # 최저가 갱신
            if current_price < self.lowest_price:
                self.lowest_price = current_price

            # 트레일링 활성화 조건
            if pnl_rate >= Config.TRAILING_STOP_ACTIVATION:
                self.trailing_active = True
                new_stop = self.lowest_price * (1 + Config.TRAILING_STOP_DISTANCE)
                if new_stop < self.stop_loss:
                    self.stop_loss = new_stop

    def should_close(self, current_price: float) -> Optional[str]:
        """청산 조건 확인"""
        # 트레일링 스탑 업데이트
        self.update_trailing_stop(current_price)

        # 레버리지 적용 수익률 계산
        pnl_pct = self.calculate_pnl(current_price)

        if self.side == 'BUY':
            if current_price <= self.stop_loss:
                return '트레일링 손절' if self.trailing_active else '손절'
            if current_price >= self.take_profit:
                return '익절'
            # 🆕 레버리지 P&L 기준 익절 (예: 3% 설정 → 3% P&L에서 익절)
            if pnl_pct >= Config.TAKE_PROFIT_PCT * 100:
                return '목표수익 달성'
        else:
            if current_price >= self.stop_loss:
                return '트레일링 손절' if self.trailing_active else '손절'
            if current_price <= self.take_profit:
                return '익절'
            # 🆕 레버리지 P&L 기준 익절 (예: 3% 설정 → 3% P&L에서 익절)
            if pnl_pct >= Config.TAKE_PROFIT_PCT * 100:
                return '목표수익 달성'
        return None

    def to_dict(self) -> dict:
        """딕셔너리로 변환 (저장용)"""
        return {
            'symbol': self.symbol,
            'side': self.side,
            'quantity': self.quantity,
            'original_quantity': self.original_quantity,
            'entry_price': self.entry_price,
            'highest_price': self.highest_price,
            'lowest_price': self.lowest_price,
            'stop_loss': self.stop_loss,
            'take_profit': self.take_profit,
            'trailing_active': self.trailing_active,
            'partial_exit_done': self.partial_exit_done,
            'breakeven_mode': self.breakeven_mode,
            'stop_order_id': self.stop_order_id,
            'timestamp': self.timestamp.isoformat()
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Position':
        """딕셔너리에서 생성 (복구용)"""
        pos = cls(data['symbol'], data['side'], data['quantity'], data['entry_price'])
        pos.original_quantity = data.get('original_quantity', data['quantity'])
        pos.highest_price = data.get('highest_price', data['entry_price'])
        pos.lowest_price = data.get('lowest_price', data['entry_price'])
        pos.stop_loss = data.get('stop_loss', pos.stop_loss)
        pos.take_profit = data.get('take_profit', pos.take_profit)
        pos.trailing_active = data.get('trailing_active', False)
        pos.partial_exit_done = data.get('partial_exit_done', False)
        pos.breakeven_mode = data.get('breakeven_mode', False)
        pos.stop_order_id = data.get('stop_order_id', None)
        pos.timestamp = datetime.fromisoformat(data['timestamp']) if isinstance(data['timestamp'], str) else data['timestamp']
        return pos


class PositionManager:
    """포지션 관리 + 저장/복구 + 일일 손실 한도"""
    def __init__(self, api: BinanceAPI, logger: Logger):
        self.api = api
        self.logger = logger
        self.positions: Dict[str, Position] = {}
        self.daily_pnl = 0.0
        self.daily_trades = 0
        self.initial_balance = api.get_balance()
        self.last_reset_date = datetime.now().date()

        # 저장된 포지션 복구 + 거래소 동기화
        self._load_positions()
        self._sync_with_exchange()

    def _load_positions(self):
        """저장된 포지션 복구"""
        if os.path.exists(Config.POSITION_FILE):
            try:
                with open(Config.POSITION_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for symbol, pos_data in data.get('positions', {}).items():
                        self.positions[symbol] = Position.from_dict(pos_data)
                    self.daily_pnl = data.get('daily_pnl', 0)
                    self.daily_trades = data.get('daily_trades', 0)
                    self.logger.info(f"포지션 복구 완료: {len(self.positions)}개")
            except Exception as e:
                self.logger.error(f"포지션 복구 실패: {e}")

    def _sync_with_exchange(self):
        """바이낸스 실제 포지션과 동기화"""
        if Config.MODE == "simulation":
            return

        real_positions = self.api.fetch_positions()
        if real_positions is None:
            return

        # 실제 포지션을 심볼 기준 딕셔너리로 변환
        # ccxt는 'BTC/USDT:USDT' 형식으로 반환할 수 있으므로 정규화
        real_map = {}
        for rp in real_positions:
            symbol = rp['symbol']
            # 'BTC/USDT:USDT' -> 'BTC/USDT' 변환
            if ':' in symbol:
                symbol = symbol.split(':')[0]
            real_map[symbol] = rp

        synced = False

        # 1. 로컬에는 있지만 거래소에 없는 포지션 제거 (수동 청산된 것)
        for symbol in list(self.positions.keys()):
            if symbol not in real_map:
                pos = self.positions[symbol]
                self.logger.warning(f"🔄 동기화: {symbol} {pos.side} 포지션이 거래소에 없음 (수동 청산?) → 로컬 제거")
                del self.positions[symbol]
                synced = True

        # 2. 거래소에는 있지만 로컬에 없는 포지션 추가 (수동 진입된 것)
        for symbol, rp in real_map.items():
            if symbol not in self.positions and symbol in [s for s in Config.SYMBOLS]:
                self.logger.warning(
                    f"🔄 동기화: {symbol} {rp['side']} 포지션 발견 (수동 진입?) → 로컬 추가\n"
                    f"   진입가: {rp['entry_price']:.4f} | 수량: {rp['quantity']:.6f}"
                )
                new_pos = Position(symbol, rp['side'], rp['quantity'], rp['entry_price'])
                self.positions[symbol] = new_pos
                synced = True

        # 3. 양쪽 다 있지만 수량이 다른 경우 (수동 부분 청산)
        for symbol in list(self.positions.keys()):
            if symbol in real_map:
                local_qty = self.positions[symbol].quantity
                real_qty = real_map[symbol]['quantity']
                # 수량 차이가 1% 이상이면 동기화
                if abs(local_qty - real_qty) / max(local_qty, 0.0001) > 0.01:
                    self.logger.warning(
                        f"🔄 동기화: {symbol} 수량 불일치 (로컬: {local_qty:.6f} → 실제: {real_qty:.6f})"
                    )
                    self.positions[symbol].quantity = real_qty
                    synced = True

        # 4. 모든 포지션에 서버 손절 보호 확인/재등록
        for symbol, pos in self.positions.items():
            if not pos.stop_order_id or pos.stop_order_id.startswith('sim_'):
                stop_id = self.api.place_stop_loss(symbol, pos.side, pos.quantity, pos.stop_loss)
                if stop_id:
                    pos.stop_order_id = stop_id
                    self.logger.info(f"🛡️ {symbol} 서버 손절 재등록: @ {pos.stop_loss:.4f}")
                    synced = True

        if synced:
            self._save_positions()
            self.logger.info(f"🔄 거래소 동기화 완료 - 현재 포지션: {len(self.positions)}개")
        else:
            self.logger.info(f"🔄 거래소 동기화 확인 - 불일치 없음 ({len(self.positions)}개)")

    def _save_positions(self):
        """포지션 저장"""
        try:
            data = {
                'positions': {s: p.to_dict() for s, p in self.positions.items()},
                'daily_pnl': self.daily_pnl,
                'daily_trades': self.daily_trades,
                'last_updated': datetime.now().isoformat()
            }
            with open(Config.POSITION_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.error(f"포지션 저장 실패: {e}")

    def _check_daily_reset(self):
        """일일 리셋 체크"""
        today = datetime.now().date()
        if today != self.last_reset_date:
            self.logger.info(f"일일 통계 리셋 (어제 손익: {self.daily_pnl:+.2f} USDT)")
            self.daily_pnl = 0
            self.daily_trades = 0
            self.initial_balance = self.api.get_balance()
            self.last_reset_date = today

    def check_daily_loss_limit(self) -> bool:
        """일일 손실 한도 체크"""
        self._check_daily_reset()

        if self.initial_balance <= 0:
            return False

        loss_rate = -self.daily_pnl / self.initial_balance
        if loss_rate >= Config.DAILY_LOSS_LIMIT:
            self.logger.warning(f"일일 손실 한도 도달: {loss_rate:.1%} >= {Config.DAILY_LOSS_LIMIT:.1%}")
            return True
        return False

    def calculate_quantity(self, symbol: str) -> float:
        """주문 수량 계산"""
        try:
            balance = self.api.get_balance()
            price = self.api.get_price(symbol)
            if not price:
                return 0

            # 코인별 레버리지 적용
            leverage = Config.get_leverage(symbol)
            position_value = balance * Config.MAX_POSITION_SIZE * leverage
            quantity = position_value / price

            # 심볼별 정밀도에 맞게 반올림
            quantity = self.api.round_quantity(symbol, quantity)

            # 최소 주문 금액 체크 (바이낸스 최소 100 USDT)
            notional = quantity * price
            min_notional = 100
            if notional < min_notional:
                coin = symbol.replace('/USDT', '')
                # 쿨다운: 같은 코인은 10분간 경고 반복 방지
                now = time.time()
                last_warn = getattr(self, '_notional_warn_time', {})
                if coin not in last_warn or (now - last_warn[coin]) > 600:
                    self.logger.warning(
                        f"[{coin}] 💰 주문 금액 부족 ({notional:.1f} USDT < 최소 {min_notional} USDT) "
                        f"- 잔고: {balance:.1f} USDT, 배수: {leverage}x, 포지션비율: {Config.MAX_POSITION_SIZE*100:.0f}%"
                    )
                    if not hasattr(self, '_notional_warn_time'):
                        self._notional_warn_time = {}
                    self._notional_warn_time[coin] = now
                return 0

            # 최소 수량 체크
            min_qty = self.api.get_min_quantity(symbol)
            if quantity < min_qty:
                self.logger.warning(f"{symbol} 주문 수량 부족: {quantity} < {min_qty}")
                return 0

            return quantity
        except Exception as e:
            self.logger.error(f"수량 계산 실패: {e}")
            return 0

    def open(self, symbol: str, side: str) -> bool:
        """포지션 오픈"""
        # 일일 손실 한도 체크
        if self.check_daily_loss_limit():
            self.logger.warning("일일 손실 한도로 신규 진입 차단")
            return False

        # 최대 포지션 수 체크
        if len(self.positions) >= Config.MAX_POSITIONS:
            self.logger.info(f"최대 포지션 수 도달: {len(self.positions)}/{Config.MAX_POSITIONS}")
            return False

        if symbol in self.positions:
            return False

        leverage = Config.get_leverage(symbol)
        self.api.set_leverage(symbol, leverage)

        quantity = self.calculate_quantity(symbol)
        if quantity == 0:
            return False

        order_side = 'buy' if side == 'BUY' else 'sell'
        order = self.api.create_order(symbol, order_side, quantity)
        if not order:
            return False

        entry_price = float(order['average'] or order['price'])

        position = Position(symbol, side, quantity, entry_price)

        # 서버 측 손절 주문 등록
        stop_id = self.api.place_stop_loss(symbol, side, quantity, position.stop_loss)
        position.stop_order_id = stop_id

        self.positions[symbol] = position
        self.daily_trades += 1

        self._save_positions()

        self.logger.success(
            f"{symbol} {side} 포지션 오픈\n"
            f"   진입: {entry_price:.4f} | 수량: {quantity:.6f} | "
            f"손절: {position.stop_loss:.4f} | 익절: {position.take_profit:.4f}\n"
            f"   🛡️ 서버 손절 보호 {'활성화' if stop_id else '실패'}"
        )

        # 텔레그램 알림
        get_telegram().send_trade("진입", symbol, side, entry_price)
        return True

    def close(self, symbol: str, reason: str = "수동") -> bool:
        """포지션 청산"""
        if symbol not in self.positions:
            return False

        position = self.positions[symbol]

        # 서버 손절 주문 취소 (전체 청산이므로)
        if position.stop_order_id:
            self.api.cancel_stop_loss(symbol, position.stop_order_id)

        order_side = 'sell' if position.side == 'BUY' else 'buy'
        # reduceOnly=True로 최소 금액 제한 우회
        order = self.api.create_order(symbol, order_side, position.quantity, reduce_only=True)
        if not order:
            return False

        exit_price = float(order['average'] or order['price'])
        pnl_pct = position.calculate_pnl(exit_price)
        pnl_amount = (position.quantity * exit_price * pnl_pct / 100) / Config.get_leverage(symbol)

        # 일일 손익 업데이트
        self.daily_pnl += pnl_amount

        if Config.MODE == "simulation":
            self.api.update_simulation_balance(pnl_amount)

        balance = self.api.get_balance()

        self.logger.success(
            f"{symbol} 청산 ({reason})\n"
            f"   진입: {position.entry_price:.4f} -> 청산: {exit_price:.4f} | "
            f"손익: {pnl_pct:+.2f}% ({pnl_amount:+.2f} USDT) | 잔고: {balance:.2f} USDT"
        )

        # 거래 기록
        self.logger.save_trade({
            'symbol': symbol,
            'side': position.side,
            'entry_price': position.entry_price,
            'exit_price': exit_price,
            'quantity': position.quantity,
            'pnl_pct': pnl_pct,
            'pnl_amount': pnl_amount,
            'reason': reason,
            'trailing_active': position.trailing_active,
            'mode': Config.MODE,
            'timestamp': datetime.now().isoformat()
        })

        # 텔레그램 알림
        get_telegram().send_trade(f"청산({reason})", symbol, position.side, exit_price, pnl_pct)

        del self.positions[symbol]
        self._save_positions()
        return True

    def partial_close(self, symbol: str) -> bool:
        """분할 익절 (50% 청산)"""
        if symbol not in self.positions:
            return False

        position = self.positions[symbol]
        if position.partial_exit_done:
            return False

        # 청산 수량 = 원래 수량의 설정 비율
        close_quantity = position.original_quantity * Config.PARTIAL_EXIT_RATIO

        order_side = 'sell' if position.side == 'BUY' else 'buy'
        # reduceOnly=True로 최소 금액 제한 우회 (포지션 청산용)
        order = self.api.create_order(symbol, order_side, close_quantity, reduce_only=True)
        if not order:
            return False

        exit_price = float(order['average'] or order['price'])
        pnl_pct = position.calculate_pnl(exit_price)
        pnl_amount = (close_quantity * exit_price * pnl_pct / 100) / Config.get_leverage(symbol)

        # 일일 손익 업데이트
        self.daily_pnl += pnl_amount

        if Config.MODE == "simulation":
            self.api.update_simulation_balance(pnl_amount)

        # 포지션 업데이트
        position.quantity = position.original_quantity - close_quantity
        position.partial_exit_done = True
        position.activate_breakeven_mode()  # 본전 보호 모드 활성화

        # 서버 손절 갱신 (남은 수량 + 본전 보호 가격)
        new_stop_id = self.api.update_stop_loss(
            symbol, position.side, position.quantity,
            position.stop_loss, position.stop_order_id
        )
        position.stop_order_id = new_stop_id

        balance = self.api.get_balance()

        # 적응형 트리거 정보
        vol_manager = get_volatility_manager()
        if vol_manager and Config.ADAPTIVE_PARTIAL_EXIT:
            level = vol_manager.get_volatility_level(symbol)
            trigger = vol_manager.get_adaptive_partial_trigger(symbol)
            adaptive_info = f" | 변동성: {level.upper()} ({trigger*100:.1f}%)"
        else:
            adaptive_info = ""

        self.logger.success(
            f"{symbol} 분할 익절 ({Config.PARTIAL_EXIT_RATIO*100:.0f}%){adaptive_info}\n"
            f"   진입: {position.entry_price:.4f} -> 청산: {exit_price:.4f} | "
            f"손익: {pnl_pct:+.2f}% ({pnl_amount:+.2f} USDT) | 잔고: {balance:.2f} USDT\n"
            f"   🛡️ 본전 보호 + 서버 손절 갱신 - 남은 수량: {position.quantity:.6f}"
        )

        # 거래 기록
        self.logger.save_trade({
            'symbol': symbol,
            'side': position.side,
            'entry_price': position.entry_price,
            'exit_price': exit_price,
            'quantity': close_quantity,
            'pnl_pct': pnl_pct,
            'pnl_amount': pnl_amount,
            'reason': '분할익절',
            'partial': True,
            'mode': Config.MODE,
            'timestamp': datetime.now().isoformat()
        })

        self._save_positions()
        return True

    def check_reverse_exit(self, symbol: str, analysis: Dict) -> bool:
        """추세 반전 시 강제 청산 확인

        Args:
            symbol: 심볼
            analysis: Strategy.analyze() 결과

        Returns:
            True if 강제 청산 실행됨
        """
        if not Config.REVERSE_EXIT_ENABLED:
            return False

        if symbol not in self.positions:
            return False

        pos = self.positions[symbol]
        final_score = analysis.get('final_score', 0)

        # 최소 보유 시간 체크
        hold_minutes = (datetime.now() - pos.timestamp).total_seconds() / 60
        if hold_minutes < Config.REVERSE_EXIT_MIN_HOLD:
            return False

        # 반전 신호 체크
        should_exit = False
        reason = ""

        if pos.side == 'BUY':
            # LONG 포지션인데 강한 SHORT 신호
            if final_score < -Config.REVERSE_EXIT_SCORE_THRESHOLD:
                should_exit = True
                reason = f"추세반전(점수:{final_score:.2f})"
        else:
            # SHORT 포지션인데 강한 LONG 신호
            if final_score > Config.REVERSE_EXIT_SCORE_THRESHOLD:
                should_exit = True
                reason = f"추세반전(점수:{final_score:.2f})"

        if should_exit:
            self.logger.warning(f"⚠️ {symbol} 추세 반전 감지! 강제 청산 실행")
            self.close(symbol, reason)
            return True

        return False

    def check_exits(self):
        """청산 조건 확인"""
        position_updated = False

        for symbol in list(self.positions.keys()):
            price = self.api.get_price(symbol)
            if not price:
                continue

            pos = self.positions[symbol]

            # 1. 분할 익절 조건 확인 (먼저!)
            if pos.should_partial_exit(price):
                self.partial_close(symbol)
                continue

            # 2. 트레일링 스탑 업데이트 전 상태 저장
            old_stop_loss = pos.stop_loss
            old_lowest = pos.lowest_price
            old_highest = pos.highest_price
            old_trailing = pos.trailing_active

            reason = pos.should_close(price)

            # 상태가 변경되었으면 저장 필요
            if pos.lowest_price != old_lowest or pos.highest_price != old_highest or pos.trailing_active != old_trailing:
                position_updated = True

            # 3. 손절가가 변경되면 서버 손절 주문도 갱신
            if pos.stop_loss != old_stop_loss and pos.stop_order_id:
                new_stop_id = self.api.update_stop_loss(
                    symbol, pos.side, pos.quantity,
                    pos.stop_loss, pos.stop_order_id
                )
                pos.stop_order_id = new_stop_id
                position_updated = True

            if reason:
                self.close(symbol, reason)

        # 포지션 상태가 변경되었으면 저장
        if position_updated and self.positions:
            self._save_positions()

    def print_status(self):
        """포지션 현황"""
        balance = self.api.get_balance()

        self.logger.info("\n" + "=" * 60)
        pnl_pct = (self.daily_pnl / self.initial_balance * 100) if self.initial_balance > 0 else 0
        self.logger.info(f"잔고: {balance:.2f} USDT | 일일 손익: {self.daily_pnl:+.2f} USDT ({pnl_pct:+.2f}%)")

        # 📊 기간별 수익 통계
        daily = self.logger.get_period_stats(days=1)
        weekly = self.logger.get_period_stats(days=7)
        monthly = self.logger.get_period_stats(days=30)

        if daily['trades'] > 0 or weekly['trades'] > 0 or monthly['trades'] > 0:
            self.logger.info("-" * 60)
            self.logger.info("📊 기간별 수익 통계")
            if daily['trades'] > 0:
                self.logger.info(f"   일일: {daily['total_pnl']:+.2f} USDT | {daily['trades']}거래 | 승률 {daily['win_rate']:.0f}% ({daily['wins']}승/{daily['losses']}패)")
            if weekly['trades'] > 0:
                self.logger.info(f"   주간: {weekly['total_pnl']:+.2f} USDT | {weekly['trades']}거래 | 승률 {weekly['win_rate']:.0f}% ({weekly['wins']}승/{weekly['losses']}패)")
            if monthly['trades'] > 0:
                self.logger.info(f"   월간: {monthly['total_pnl']:+.2f} USDT | {monthly['trades']}거래 | 승률 {monthly['win_rate']:.0f}% ({monthly['wins']}승/{monthly['losses']}패)")

        if not self.positions:
            self.logger.info("활성 포지션 없음")
        else:
            self.logger.info(f"활성 포지션: {len(self.positions)}/{Config.MAX_POSITIONS}개")
            for symbol, pos in self.positions.items():
                price = self.api.get_price(symbol)
                if price:
                    pnl = pos.calculate_pnl(price)
                    status_tags = []

                    # 본전 보호 모드
                    if pos.breakeven_mode:
                        status_tags.append("🛡️BE")

                    # 트레일링 스탑
                    if pos.trailing_active:
                        status_tags.append(f"[T] SL:{pos.stop_loss:.4f}")
                    else:
                        # 트레일링 활성화까지 얼마나 남았는지 표시
                        pnl_rate = pnl / Config.get_leverage(symbol) / 100
                        remain = Config.TRAILING_STOP_ACTIVATION - pnl_rate
                        if remain > 0:
                            status_tags.append(f"(T까지 {remain*100:.2f}%)")

                    # 분할 익절 상태
                    if pos.partial_exit_done:
                        status_tags.append(f"잔량:{pos.quantity:.4f}")
                    elif Config.PARTIAL_EXIT_ENABLED and not pos.partial_exit_done:
                        # 적응형 트리거까지 남은 거리
                        vol_manager = get_volatility_manager()
                        if vol_manager and Config.ADAPTIVE_PARTIAL_EXIT:
                            trigger = vol_manager.get_adaptive_partial_trigger(symbol)
                            level = vol_manager.get_volatility_level(symbol)
                            remain_partial = trigger - pnl_rate
                            if remain_partial > 0:
                                status_tags.append(f"(P:{level[0].upper()} {remain_partial*100:.1f}%)")

                    status_str = " ".join(status_tags)
                    self.logger.info(
                        f"  {symbol}: {pos.side} @ {pos.entry_price:.4f} | "
                        f"현재: {price:.4f} | 손익: {pnl:+.2f}% {status_str}"
                    )
        self.logger.info("=" * 60)

        # 텔레그램 상태 알림
        telegram = get_telegram()
        telegram.send_status(balance, self.daily_pnl, self.positions)


# ==================== 메인 봇 ====================
class TradingBot:
    """트레이딩 봇"""
    def __init__(self):
        self.logger = Logger(Config.LOG_FILE)
        self.api = BinanceAPI(self.logger)

        # ML 예측기 (기본)
        self.ml_predictor = MLPredictor(self.logger) if Config.ML_ENABLED else None

        # 고급 ML 예측기 (Phase 2)
        self.advanced_ml = None
        if Config.ADVANCED_ML_ENABLED:
            self.advanced_ml = AdvancedMLPredictor(self.logger)

        # 전략
        self.strategy = Strategy(self.ml_predictor, self.advanced_ml)

        # 포지션 매니저
        self.positions = PositionManager(self.api, self.logger)

        # 시장 상태 분석기
        self.market_analyzer = MarketAnalyzer(self.api, self.logger)

        self._print_header()

        # ML 모델 학습 (없으면)
        if Config.ML_ENABLED and self.ml_predictor and not self.ml_predictor.is_trained:
            self.ml_predictor.train(self.api, Config.SYMBOLS)

        # 고급 ML 모델 학습 (없으면)
        if Config.ADVANCED_ML_ENABLED and self.advanced_ml and not self.advanced_ml.is_trained:
            self.advanced_ml.train(self.api, Config.SYMBOLS)

    def _print_header(self):
        """시작 정보"""
        self.logger.info("=" * 60)
        self.logger.info("Binance Futures Auto Trader v2.2 (Advanced ML)")
        self.logger.info("=" * 60)
        self.logger.info(f"모드: {Config.get_mode_name()}")
        self.logger.info(f"코인: {', '.join([s.replace('/USDT', '') for s in Config.SYMBOLS])}")
        if Config.LEVERAGE_PER_SYMBOL:
            lev_info = ', '.join([f"{c}:{l}x" for c, l in Config.LEVERAGE_PER_SYMBOL.items()])
            self.logger.info(f"레버리지: 기본 {Config.LEVERAGE}x ({lev_info}) | 손절: {Config.STOP_LOSS_PCT*100}% | 익절: {Config.TAKE_PROFIT_PCT*100}%")
        else:
            self.logger.info(f"레버리지: {Config.LEVERAGE}x | 손절: {Config.STOP_LOSS_PCT*100}% | 익절: {Config.TAKE_PROFIT_PCT*100}%")
        self.logger.info(f"트레일링 스탑: {'활성화' if Config.TRAILING_STOP_ENABLED else '비활성화'}")
        partial_mode = "적응형(ATR)" if Config.ADAPTIVE_PARTIAL_EXIT else f"고정({Config.PARTIAL_EXIT_TRIGGER*100:.1f}%)"
        self.logger.info(f"분할 익절: {'활성화' if Config.PARTIAL_EXIT_ENABLED else '비활성화'} ({Config.PARTIAL_EXIT_RATIO*100:.0f}% | {partial_mode})")
        self.logger.info(f"ML 예측: {'활성화' if Config.ML_ENABLED else '비활성화'}")
        # 고급 ML 상태
        if Config.ADVANCED_ML_ENABLED:
            ml_status = "활성화 (XGBoost+LightGBM+RF 앙상블)"
        else:
            ml_status = "비활성화"
        self.logger.info(f"고급 ML: {ml_status}")
        self.logger.info(f"일일 손실 한도: {Config.DAILY_LOSS_LIMIT*100}%")
        self.logger.info(f"시장 분석: 활성화 (급락/급등 감지)")
        reverse_mode = f"활성화 (임계:{Config.REVERSE_EXIT_SCORE_THRESHOLD}, 최소보유:{Config.REVERSE_EXIT_MIN_HOLD}분)" if Config.REVERSE_EXIT_ENABLED else "비활성화"
        self.logger.info(f"추세 반전 청산: {reverse_mode}")
        balance = self.api.get_balance()
        self.logger.info(f"잔고: {balance:.2f} USDT")
        self.logger.info("=" * 60)

        # 텔레그램 시작 알림
        telegram = get_telegram()
        coins = ', '.join([s.replace('/USDT', '') for s in Config.SYMBOLS])
        telegram.send(
            f"🚀 <b>봇 시작</b>\n"
            f"━━━━━━━━━━━━━━━\n"
            f"모드: {Config.get_mode_name()}\n"
            f"코인: {coins}\n"
            f"잔고: {balance:.2f} USDT"
        )

    def scan(self):
        """시장 스캔"""
        # 청산 조건 먼저 체크
        self.positions.check_exits()

        # 일일 손실 한도 체크
        if self.positions.check_daily_loss_limit():
            return

        self.logger.info("\n" + "=" * 50)
        self.logger.info("📊 시장 분석 시작")
        self.logger.info("=" * 50)

        # 시장 상태 분석
        market_state = self.market_analyzer.analyze_market(Config.SYMBOLS)
        condition_emoji = {
            'normal': '✅', 'crash': '🔴', 'rally': '🟢', 'volatile': '⚠️'
        }.get(market_state['condition'], '❓')

        self.logger.info(
            f"시장 상태: {condition_emoji} {market_state['condition'].upper()} | "
            f"급락: {market_state['crash_count']}개 | 급등: {market_state['rally_count']}개 | "
            f"평균변화: {market_state['avg_change']:+.2f}%"
        )

        if not market_state['entry_allowed']:
            self.logger.warning("⛔ 시장 상태 불안정 - 신규 진입 차단")

        for symbol in Config.SYMBOLS:
            coin = symbol.replace('/USDT', '')

            df_1h = self.api.get_candles(symbol, Config.BASE_TIMEFRAME)
            df_4h = self.api.get_candles(symbol, Config.TREND_TIMEFRAME)

            if df_1h is None or df_4h is None:
                self.logger.warning(f"[{coin}] ❌ 데이터 조회 실패")
                continue

            analysis = self.strategy.analyze(df_1h, df_4h)

            # 기존 포지션이 있으면 추세 반전 체크 후 스킵
            if symbol in self.positions.positions:
                pos = self.positions.positions[symbol]
                pnl = pos.calculate_pnl(self.api.get_price(symbol) or pos.entry_price)
                self.logger.info(f"[{coin}] 📍 보유중 ({pos.side}) | P&L: {pnl:+.2f}% | 점수: {analysis['final_score']:.2f}")

                # 추세 반전 강제 청산 체크
                if self.positions.check_reverse_exit(symbol, analysis):
                    self.logger.warning(f"[{coin}] 🔄 추세 반전으로 강제 청산됨")
                continue

            # 분석 결과 로그 출력
            signals = analysis['signals']
            buy_signals = [k for k, v in signals.items() if v == 'BUY']
            sell_signals = [k for k, v in signals.items() if v == 'SELL']

            self.logger.info(f"\n[{coin}] 분석 결과:")
            self.logger.info(f"  추세: {analysis['market_trend']} | 기술점수: {analysis['tech_score']:.2f} | 최종점수: {analysis['final_score']:.2f}")
            self.logger.info(f"  매수신호: {buy_signals if buy_signals else '없음'}")
            self.logger.info(f"  매도신호: {sell_signals if sell_signals else '없음'}")

            if analysis['ml_prediction']:
                ml = analysis['ml_prediction']
                buy_p = ml.get('buy_probability', 0) * 100
                sell_p = ml.get('sell_probability', 0) * 100
                self.logger.info(f"  ML예측: 매수 {buy_p:.1f}% / 매도 {sell_p:.1f}%")

            decision = analysis['final_decision']

            if decision == 'LONG':
                # 시장 상태 확인
                allowed, reason = self.market_analyzer.is_entry_allowed('BUY', Config.SYMBOLS)
                if allowed:
                    self.logger.success(f"[{coin}] 🟢 LONG 진입 신호!")
                    self.positions.open(symbol, 'BUY')
                else:
                    self.logger.info(f"[{coin}] 🟢 LONG 신호 발생 → ⛔ 진입 차단: {reason}")
            elif decision == 'SHORT':
                # 시장 상태 확인
                allowed, reason = self.market_analyzer.is_entry_allowed('SELL', Config.SYMBOLS)
                if allowed:
                    self.logger.success(f"[{coin}] 🔴 SHORT 진입 신호!")
                    self.positions.open(symbol, 'SELL')
                else:
                    self.logger.info(f"[{coin}] 🔴 SHORT 신호 발생 → ⛔ 진입 차단: {reason}")
            else:
                # 진입 안 되는 이유 출력
                reasons = []
                threshold = Config.ENTRY_SCORE_THRESHOLD

                if abs(analysis['final_score']) <= threshold:
                    reasons.append(f"점수 부족({analysis['final_score']:.2f}, 필요: >{threshold} 또는 <-{threshold})")

                if not Config.ALLOW_SIDEWAYS_ENTRY and analysis['market_trend'] == 'SIDEWAYS':
                    reasons.append("추세 불명확(횡보)")

                if analysis['final_score'] > threshold:
                    if analysis['market_trend'] == 'DOWN':
                        reasons.append(f"추세 불일치(점수+인데 추세=DOWN)")
                    if Config.ML_ENABLED and analysis['ml_prediction']:
                        buy_p = analysis['ml_prediction'].get('buy_probability', 0)
                        if buy_p < Config.ML_MIN_PROBABILITY:
                            reasons.append(f"ML확률 부족({buy_p*100:.1f}% < {Config.ML_MIN_PROBABILITY*100}%)")

                if analysis['final_score'] < -threshold:
                    if analysis['market_trend'] == 'UP':
                        reasons.append(f"추세 불일치(점수-인데 추세=UP)")
                    if Config.ML_ENABLED and analysis['ml_prediction']:
                        sell_p = analysis['ml_prediction'].get('sell_probability', 0)
                        if sell_p < Config.ML_MIN_PROBABILITY:
                            reasons.append(f"ML확률 부족({sell_p*100:.1f}% < {Config.ML_MIN_PROBABILITY*100}%)")

                self.logger.info(f"[{coin}] ⏸️ 대기 - {', '.join(reasons) if reasons else '신호 없음'}")

    def run(self):
        """봇 실행"""
        try:
            while True:
                self.scan()
                self.positions.print_status()

                self.logger.info(f"\n{Config.SCAN_INTERVAL}초 후 다음 스캔...")
                time.sleep(Config.SCAN_INTERVAL)

        except KeyboardInterrupt:
            self.logger.warning("\n봇 중지")
            self.positions._save_positions()
            self.logger.info(f"포지션 저장 완료: {len(self.positions.positions)}개")


# ==================== 설정 파일 생성 ====================
def create_default_settings():
    """기본 설정 파일 생성"""
    settings = {
        "_comment": "Binance Futures Bot 설정 파일",
        "_version": "2.0.0",

        "mode": "simulation",

        "api": {
            "_comment": "API 키 (환경변수 사용 권장)",
            "key": "",
            "secret": ""
        },

        "simulation": {
            "initial_balance": 10000
        },

        "trading": {
            "symbols": ["BTC/USDT", "ETH/USDT", "SOL/USDT", "DOGE/USDT"]
        },

        "risk": {
            "max_position_size": 0.02,
            "leverage": 3,
            "stop_loss": 0.02,
            "take_profit": 0.04,
            "daily_loss_limit": 0.05,
            "max_positions": 4
        },

        "trailing_stop": {
            "enabled": True,
            "activation": 0.02,
            "distance": 0.01
        },

        "strategy": {
            "threshold": 3,
            "base_timeframe": "1h",
            "trend_timeframe": "4h",
            "entry_score_threshold": 0.2,
            "allow_sideways_entry": True,
            "scan_interval": 300
        },

        "ml": {
            "enabled": True,
            "min_probability": 0.60,
            "weight": 0.3
        }
    }

    settings_file = os.path.join(BASE_PATH, 'binance_settings.json')
    with open(settings_file, 'w', encoding='utf-8') as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)

    print(f"설정 파일 생성: {settings_file}")


# ==================== 실행 ====================
if __name__ == "__main__":
    # 설정 파일 없으면 생성
    settings_file = os.path.join(BASE_PATH, 'binance_settings.json')
    if not os.path.exists(settings_file):
        create_default_settings()
        print("\n설정 파일이 생성되었습니다. binance_settings.json을 수정 후 다시 실행하세요.\n")
        input("Enter를 눌러 종료...")
        sys.exit(0)

    print("\n" + "=" * 60)
    print("  Binance Futures Auto Trader v2.0")
    print("=" * 60)
    print(f"\n현재 모드: {Config.get_mode_name()}\n")

    if Config.MODE == "mainnet":
        print("실전 모드입니다 - 실제 자금이 사용됩니다!")
        response = input("정말 실전 모드로 실행하시겠습니까? (yes 입력): ")
        if response.lower() != 'yes':
            print("\n실행 취소됨")
            sys.exit(0)

    print("\n봇을 시작합니다...\n")

    bot = TradingBot()
    bot.run()
