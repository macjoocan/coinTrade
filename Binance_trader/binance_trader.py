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

    # 파일 경로 (exe 실행 위치 기준)
    LOG_FILE = os.path.join(BASE_PATH, 'binance_trading.log')
    TRADE_HISTORY_FILE = os.path.join(BASE_PATH, 'binance_history.json')
    POSITION_FILE = os.path.join(BASE_PATH, 'binance_positions.json')
    ML_MODEL_FILE = os.path.join(os.path.dirname(__file__), 'binance_ml_model.pkl')

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
            try:
                url = f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={symbol.replace('/', '')}"
                response = requests.get(url, timeout=10)
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

    def set_leverage(self, symbol: str, leverage: int) -> bool:
        """레버리지 설정"""
        if Config.MODE == "simulation":
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
            order = self.exchange.create_market_order(symbol, side, amount)
            self.logger.success(f"주문 체결: {symbol} {side.upper()} {amount}")
            return order
        except Exception as e:
            self.logger.error(f"주문 실패: {e}")
            return None


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


# ==================== 전략 ====================
class Strategy:
    """멀티 타임프레임 + ML 통합 전략"""

    def __init__(self, ml_predictor: Optional[MLPredictor] = None):
        self.ml_predictor = ml_predictor

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

    def analyze(self, df_base: pd.DataFrame, df_trend: pd.DataFrame) -> Dict:
        """통합 분석"""
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

        # 기술적 점수 (0~1)
        tech_score = buy_count / 5 if buy_count > sell_count else -sell_count / 5

        # ML 예측
        ml_score = 0
        ml_prediction = None
        if self.ml_predictor and Config.ML_ENABLED:
            ml_prediction = self.ml_predictor.predict(df_base)
            if ml_prediction:
                ml_score = (ml_prediction['buy_probability'] - 0.5) * 2  # -1 ~ 1

        # 통합 점수
        final_score = tech_score * (1 - Config.ML_WEIGHT) + ml_score * Config.ML_WEIGHT

        # 최종 신호 결정 (완화된 조건)
        final_signal = None
        threshold = Config.ENTRY_SCORE_THRESHOLD

        # LONG 조건: 점수 > 임계값 AND (상승추세 OR 횡보장허용시 횡보장도 OK)
        if final_score > threshold:
            trend_ok = market_trend == 'UP' or (Config.ALLOW_SIDEWAYS_ENTRY and market_trend == 'SIDEWAYS')
            ml_ok = not Config.ML_ENABLED or (ml_prediction and ml_prediction.get('buy_probability', 0) >= Config.ML_MIN_PROBABILITY)
            if trend_ok and ml_ok:
                final_signal = 'LONG'

        # SHORT 조건: 점수 < -임계값 AND (하락추세 OR 횡보장허용시 횡보장도 OK)
        elif final_score < -threshold:
            trend_ok = market_trend == 'DOWN' or (Config.ALLOW_SIDEWAYS_ENTRY and market_trend == 'SIDEWAYS')
            ml_ok = not Config.ML_ENABLED or (ml_prediction and ml_prediction.get('sell_probability', 0) >= Config.ML_MIN_PROBABILITY)
            if trend_ok and ml_ok:
                final_signal = 'SHORT'

        return {
            'signals': indicators,
            'market_trend': market_trend,
            'tech_score': tech_score,
            'ml_prediction': ml_prediction,
            'final_score': final_score,
            'final_decision': final_signal
        }


# ==================== 포지션 ====================
class Position:
    """포지션 정보 + 트레일링 스탑"""
    def __init__(self, symbol: str, side: str, quantity: float, entry_price: float):
        self.symbol = symbol
        self.side = side
        self.quantity = quantity
        self.entry_price = entry_price
        self.highest_price = entry_price  # 트레일링용 최고가
        self.lowest_price = entry_price   # 트레일링용 최저가
        self.stop_loss = entry_price * (1 - Config.STOP_LOSS_PCT) if side == 'BUY' else entry_price * (1 + Config.STOP_LOSS_PCT)
        self.take_profit = entry_price * (1 + Config.TAKE_PROFIT_PCT) if side == 'BUY' else entry_price * (1 - Config.TAKE_PROFIT_PCT)
        self.trailing_active = False
        self.timestamp = datetime.now()

    def calculate_pnl(self, current_price: float) -> float:
        """손익률 계산 (레버리지 적용)"""
        if self.side == 'BUY':
            return ((current_price - self.entry_price) / self.entry_price) * 100 * Config.LEVERAGE
        else:
            return ((self.entry_price - current_price) / self.entry_price) * 100 * Config.LEVERAGE

    def update_trailing_stop(self, current_price: float):
        """트레일링 스탑 업데이트"""
        if not Config.TRAILING_STOP_ENABLED:
            return

        pnl_rate = self.calculate_pnl(current_price) / Config.LEVERAGE / 100

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

        if self.side == 'BUY':
            if current_price <= self.stop_loss:
                return '트레일링 손절' if self.trailing_active else '손절'
            if current_price >= self.take_profit:
                return '익절'
        else:
            if current_price >= self.stop_loss:
                return '트레일링 손절' if self.trailing_active else '손절'
            if current_price <= self.take_profit:
                return '익절'
        return None

    def to_dict(self) -> dict:
        """딕셔너리로 변환 (저장용)"""
        return {
            'symbol': self.symbol,
            'side': self.side,
            'quantity': self.quantity,
            'entry_price': self.entry_price,
            'highest_price': self.highest_price,
            'lowest_price': self.lowest_price,
            'stop_loss': self.stop_loss,
            'take_profit': self.take_profit,
            'trailing_active': self.trailing_active,
            'timestamp': self.timestamp.isoformat()
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Position':
        """딕셔너리에서 생성 (복구용)"""
        pos = cls(data['symbol'], data['side'], data['quantity'], data['entry_price'])
        pos.highest_price = data.get('highest_price', data['entry_price'])
        pos.lowest_price = data.get('lowest_price', data['entry_price'])
        pos.stop_loss = data.get('stop_loss', pos.stop_loss)
        pos.take_profit = data.get('take_profit', pos.take_profit)
        pos.trailing_active = data.get('trailing_active', False)
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

        # 저장된 포지션 복구
        self._load_positions()

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

            position_value = balance * Config.MAX_POSITION_SIZE * Config.LEVERAGE
            quantity = position_value / price

            return round(quantity, 6)
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

        self.api.set_leverage(symbol, Config.LEVERAGE)

        quantity = self.calculate_quantity(symbol)
        if quantity == 0:
            return False

        order_side = 'buy' if side == 'BUY' else 'sell'
        order = self.api.create_order(symbol, order_side, quantity)
        if not order:
            return False

        entry_price = float(order['average'] or order['price'])

        position = Position(symbol, side, quantity, entry_price)
        self.positions[symbol] = position
        self.daily_trades += 1

        self._save_positions()

        self.logger.success(
            f"{symbol} {side} 포지션 오픈\n"
            f"   진입: {entry_price:.4f} | 수량: {quantity:.6f} | "
            f"손절: {position.stop_loss:.4f} | 익절: {position.take_profit:.4f}"
        )
        return True

    def close(self, symbol: str, reason: str = "수동") -> bool:
        """포지션 청산"""
        if symbol not in self.positions:
            return False

        position = self.positions[symbol]

        order_side = 'sell' if position.side == 'BUY' else 'buy'
        order = self.api.create_order(symbol, order_side, position.quantity)
        if not order:
            return False

        exit_price = float(order['average'] or order['price'])
        pnl_pct = position.calculate_pnl(exit_price)
        pnl_amount = (position.quantity * exit_price * pnl_pct / 100) / Config.LEVERAGE

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

        del self.positions[symbol]
        self._save_positions()
        return True

    def check_exits(self):
        """청산 조건 확인"""
        position_updated = False

        for symbol in list(self.positions.keys()):
            price = self.api.get_price(symbol)
            if not price:
                continue

            # 트레일링 스탑 업데이트 전 상태 저장
            pos = self.positions[symbol]
            old_lowest = pos.lowest_price
            old_highest = pos.highest_price
            old_trailing = pos.trailing_active

            reason = pos.should_close(price)

            # 상태가 변경되었으면 저장 필요
            if pos.lowest_price != old_lowest or pos.highest_price != old_highest or pos.trailing_active != old_trailing:
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
        self.logger.info(f"잔고: {balance:.2f} USDT | 일일 손익: {self.daily_pnl:+.2f} USDT ({self.daily_pnl/self.initial_balance*100:+.2f}%)")

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
                    trailing_info = ""
                    if pos.trailing_active:
                        trailing_info = f" [T] 손절: {pos.stop_loss:.4f}"
                    else:
                        # 트레일링 활성화까지 얼마나 남았는지 표시
                        pnl_rate = pnl / Config.LEVERAGE / 100
                        remain = Config.TRAILING_STOP_ACTIVATION - pnl_rate
                        if remain > 0:
                            trailing_info = f" (트레일링까지 {remain*100:.2f}%)"
                    self.logger.info(
                        f"  {symbol}: {pos.side} @ {pos.entry_price:.4f} | "
                        f"현재: {price:.4f} | 손익: {pnl:+.2f}%{trailing_info}"
                    )
        self.logger.info("=" * 60)


# ==================== 메인 봇 ====================
class TradingBot:
    """트레이딩 봇"""
    def __init__(self):
        self.logger = Logger(Config.LOG_FILE)
        self.api = BinanceAPI(self.logger)

        # ML 예측기
        self.ml_predictor = MLPredictor(self.logger) if Config.ML_ENABLED else None

        # 전략
        self.strategy = Strategy(self.ml_predictor)

        # 포지션 매니저
        self.positions = PositionManager(self.api, self.logger)

        self._print_header()

        # ML 모델 학습 (없으면)
        if Config.ML_ENABLED and self.ml_predictor and not self.ml_predictor.is_trained:
            self.ml_predictor.train(self.api, Config.SYMBOLS)

    def _print_header(self):
        """시작 정보"""
        self.logger.info("=" * 60)
        self.logger.info("Binance Futures Auto Trader v2.0")
        self.logger.info("=" * 60)
        self.logger.info(f"모드: {Config.get_mode_name()}")
        self.logger.info(f"코인: {', '.join([s.replace('/USDT', '') for s in Config.SYMBOLS])}")
        self.logger.info(f"레버리지: {Config.LEVERAGE}x | 손절: {Config.STOP_LOSS_PCT*100}% | 익절: {Config.TAKE_PROFIT_PCT*100}%")
        self.logger.info(f"트레일링 스탑: {'활성화' if Config.TRAILING_STOP_ENABLED else '비활성화'}")
        self.logger.info(f"ML 예측: {'활성화' if Config.ML_ENABLED else '비활성화'}")
        self.logger.info(f"일일 손실 한도: {Config.DAILY_LOSS_LIMIT*100}%")
        balance = self.api.get_balance()
        self.logger.info(f"잔고: {balance:.2f} USDT")
        self.logger.info("=" * 60)

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

        for symbol in Config.SYMBOLS:
            coin = symbol.replace('/USDT', '')

            if symbol in self.positions.positions:
                self.logger.info(f"[{coin}] ⏭️ 이미 포지션 보유중 - 스킵")
                continue

            df_1h = self.api.get_candles(symbol, Config.BASE_TIMEFRAME)
            df_4h = self.api.get_candles(symbol, Config.TREND_TIMEFRAME)

            if df_1h is None or df_4h is None:
                self.logger.warning(f"[{coin}] ❌ 데이터 조회 실패")
                continue

            analysis = self.strategy.analyze(df_1h, df_4h)

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
                self.logger.success(f"[{coin}] 🟢 LONG 진입 신호!")
                self.positions.open(symbol, 'BUY')
            elif decision == 'SHORT':
                self.logger.success(f"[{coin}] 🔴 SHORT 진입 신호!")
                self.positions.open(symbol, 'SELL')
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
