import requests
import jwt
import uuid
import hashlib
import time
import json
import sqlite3
import os
import logging
from urllib.parse import urlencode
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import warnings
warnings.filterwarnings('ignore')

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('trading.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 거래 상태 Enum
class PositionType(Enum):
    NONE = "none"
    LONG = "long"
    SHORT = "short"

@dataclass
class Trade:
    """거래 데이터 클래스"""
    entry_date: datetime
    exit_date: Optional[datetime]
    position_type: PositionType
    entry_price: float
    exit_price: Optional[float]
    quantity: float
    pnl: Optional[float]
    commission: float

class Config:
    """설정 관리 클래스"""
    def __init__(self, config_file='config.json'):
        self.config_file = config_file
        self.load_config()
    
    def load_config(self):
        """설정 파일 로드 또는 환경변수에서 읽기"""
        try:
            # 환경변수 우선
            self.access_key = os.getenv('UPBIT_ACCESS_KEY')
            self.secret_key = os.getenv('UPBIT_SECRET_KEY')
            
            # 설정 파일에서 읽기
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    self.trading_params = config.get('trading_params', {})
                    self.risk_params = config.get('risk_params', {})
            else:
                # 기본 설정
                self.trading_params = {
                    'initial_capital': 1000000,
                    'max_position_size': 0.2,
                    'commission': 0.0005
                }
                self.risk_params = {
                    'stop_loss_pct': 0.01,
                    'take_profit_pct': 0.02,
                    'max_daily_loss': 0.02,
                    'risk_per_trade': 0.02
                }
                
        except Exception as e:
            logger.error(f"설정 로드 실패: {e}")
            raise

class TradeDatabase:
    """거래 데이터베이스 관리 클래스"""
    def __init__(self, db_path='trades.db'):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.create_tables()
    
    def create_tables(self):
        """테이블 생성"""
        cursor = self.conn.cursor()
        
        # 거래 내역 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entry_date TIMESTAMP,
                exit_date TIMESTAMP,
                market TEXT,
                position_type TEXT,
                entry_price REAL,
                exit_price REAL,
                quantity REAL,
                pnl REAL,
                commission REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 일일 성과 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE UNIQUE,
                starting_capital REAL,
                ending_capital REAL,
                total_trades INTEGER,
                winning_trades INTEGER,
                losing_trades INTEGER,
                daily_pnl REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        self.conn.commit()
    
    def save_trade(self, trade: Trade, market: str):
        """거래 저장"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO trades (
                entry_date, exit_date, market, position_type,
                entry_price, exit_price, quantity, pnl, commission
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            trade.entry_date, trade.exit_date, market,
            trade.position_type.value, trade.entry_price,
            trade.exit_price, trade.quantity, trade.pnl, trade.commission
        ))
        self.conn.commit()
        logger.info(f"거래 저장 완료: {trade}")
    
    def get_today_trades(self) -> List[Dict]:
        """오늘의 거래 조회"""
        cursor = self.conn.cursor()
        today = datetime.now().date()
        cursor.execute('''
            SELECT * FROM trades 
            WHERE DATE(entry_date) = ? OR DATE(exit_date) = ?
        ''', (today, today))
        return cursor.fetchall()
    
    def __del__(self):
        """소멸자"""
        if hasattr(self, 'conn'):
            self.conn.close()

class UpbitTrader:
    """업비트 API 트레이더 클래스"""
    def __init__(self, config: Config):
        self.config = config
        self.access_key = config.access_key
        self.secret_key = config.secret_key
        self.server_url = "https://api.upbit.com"
        self.last_api_call = time.time()
        self.api_call_interval = 0.5  # API 호출 간격 (초)
    
    def _rate_limit(self):
        """API 호출 제한 관리"""
        current_time = time.time()
        time_since_last_call = current_time - self.last_api_call
        if time_since_last_call < self.api_call_interval:
            time.sleep(self.api_call_interval - time_since_last_call)
        self.last_api_call = time.time()
    
    def _get_headers(self, query=None):
        """JWT 토큰을 생성하여 헤더 반환"""
        payload = {
            'access_key': self.access_key,
            'nonce': str(uuid.uuid4()),
        }
        
        if query:
            query_string = urlencode(query).encode()
            m = hashlib.sha512()
            m.update(query_string)
            query_hash = m.hexdigest()
            payload['query_hash'] = query_hash
            payload['query_hash_alg'] = 'SHA512'
        
        jwt_token = jwt.encode(payload, self.secret_key, algorithm='HS256')
        return {'Authorization': f'Bearer {jwt_token}'}

    def _api_call(self, method: str, endpoint: str, params=None, json_data=None, auth_required=True):
        self._rate_limit()
        
        url = f"{self.server_url}{endpoint}"  # url 정의 추가
        headers = self._get_headers(json_data or params) if auth_required else {}
        
        try:
            if method == 'GET':
                response = requests.get(url, params=params, headers=headers, timeout=30)
            elif method == 'POST':
                response = requests.post(url, json=json_data, headers=headers, timeout=30)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                logger.warning("API 호출 제한 도달. 10초 대기...")
                time.sleep(10)
                return self._api_call(method, endpoint, params, json_data, auth_required)
            logger.error(f"API 호출 실패: {e}")
            raise
        except Exception as e:
            logger.error(f"예상치 못한 에러: {e}")
            raise
    
    # def _api_call(self, method: str, endpoint: str, params=None, json_data=None, auth_required=True):
        
    #     response = requests.get(url, params=params, headers=headers, timeout=10)
        
    #     """API 호출 래퍼 (에러 처리 포함)"""
    #     self._rate_limit()
        
    #     url = f"{self.server_url}{endpoint}"
    #     headers = self._get_headers(json_data or params) if auth_required else {}
        
    #     try:
    #         if method == 'GET':
    #             response = requests.get(url, params=params, headers=headers, timeout=10)
    #         elif method == 'POST':
    #             response = requests.post(url, json=json_data, headers=headers, timeout=10)
    #         else:
    #             raise ValueError(f"Unsupported method: {method}")
            
    #         response.raise_for_status()
    #         return response.json()
            
    #     except requests.exceptions.HTTPError as e:
    #         if e.response.status_code == 429:
    #             logger.warning("API 호출 제한 도달. 10초 대기...")
    #             time.sleep(10)
    #             return self._api_call(method, endpoint, params, json_data, auth_required)
    #         logger.error(f"API 호출 실패: {e}")
    #         raise
    #     except Exception as e:
    #         logger.error(f"예상치 못한 에러: {e}")
    #         raise
    
    def get_balances(self) -> List[Dict]:
        """계좌 잔고 조회"""
        return self._api_call('GET', '/v1/accounts')
    
    def get_ticker(self, market: str) -> Dict:
        """현재가 조회"""
        params = {'markets': market}
        result = self._api_call('GET', '/v1/ticker', params=params, auth_required=False)
        return result[0] if result else {}
    
    def get_candles(self, market: str, interval='minutes', count=200, unit=1) -> List[Dict]:
        """캔들 데이터 조회"""
        if interval == 'minutes':
            endpoint = f'/v1/candles/minutes/{unit}'
        elif interval == 'days':
            endpoint = '/v1/candles/days'
        elif interval == 'weeks':
            endpoint = '/v1/candles/weeks'
        elif interval == 'months':
            endpoint = '/v1/candles/months'
        else:
            raise ValueError(f"Invalid interval: {interval}")
        
        params = {'market': market, 'count': count}
        candles = self._api_call('GET', endpoint, params=params, auth_required=False)
        
        # 데이터 유효성 검증
        if not isinstance(candles, list) or len(candles) == 0:
            logger.warning(f"Invalid candle data for {market}")
            return []
        
        return candles
    
    def get_historical_data(self, market: str, days=30) -> pd.DataFrame:
        """백테스팅용 과거 데이터 수집 (개선된 버전)"""
        all_candles = []
        
        try:
            # 일봉 데이터 수집 (최대 200개씩)
            for i in range(0, days, 200):
                count = min(200, days - i)
                candles = self.get_candles(market, 'days', count)
                
                if candles:
                    all_candles.extend(candles)
                    logger.info(f"수집된 캔들 수: {len(candles)}")
                
                if i + 200 < days:
                    time.sleep(1)  # 안전한 API 호출 간격
            
            if not all_candles:
                logger.warning("캔들 데이터를 수집할 수 없습니다.")
                return pd.DataFrame()
            
            # 데이터프레임으로 변환
            df = pd.DataFrame(all_candles)
            df['candle_date_time_kst'] = pd.to_datetime(df['candle_date_time_kst'])
            df = df.sort_values('candle_date_time_kst').reset_index(drop=True)
            
            # 필요한 컬럼만 선택
            df = df[['candle_date_time_kst', 'opening_price', 'high_price', 
                    'low_price', 'trade_price', 'candle_acc_trade_volume']]
            df.columns = ['date', 'open', 'high', 'low', 'close', 'volume']
            
            logger.info(f"데이터 수집 완료: {len(df)}개 캔들")
            return df
            
        except Exception as e:
            logger.error(f"데이터 수집 중 오류: {e}")
            return pd.DataFrame()
    
    def buy_market_order(self, market: str, price: float) -> Dict:
        """시장가 매수 주문"""
        query = {
            'market': market,
            'side': 'bid',
            'price': str(price),
            'ord_type': 'price'
        }
        
        try:
            result = self._api_call('POST', '/v1/orders', json_data=query)
            logger.info(f"매수 주문 성공: {result}")
            return result
        except Exception as e:
            logger.error(f"매수 주문 실패: {e}")
            raise
    
    def sell_market_order(self, market: str, volume: float) -> Dict:
        """시장가 매도 주문"""
        query = {
            'market': market,
            'side': 'ask',
            'volume': str(volume),
            'ord_type': 'market'
        }
        
        try:
            result = self._api_call('POST', '/v1/orders', json_data=query)
            logger.info(f"매도 주문 성공: {result}")
            return result
        except Exception as e:
            logger.error(f"매도 주문 실패: {e}")
            raise

class TechnicalIndicators:
    """기술적 지표 계산 클래스"""
    
    @staticmethod
    def sma(data: pd.Series, period: int) -> pd.Series:
        """단순이동평균"""
        return data.rolling(window=period).mean()
    
    @staticmethod
    def ema(data: pd.Series, period: int) -> pd.Series:
        """지수이동평균"""
        return data.ewm(span=period, adjust=False).mean()
    
    @staticmethod
    def rsi(data: pd.Series, period: int = 14) -> pd.Series:
        """RSI (Relative Strength Index)"""
        delta = data.diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    @staticmethod
    def macd(data: pd.Series, fast=12, slow=26, signal=9) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """MACD (Moving Average Convergence Divergence)"""
        ema_fast = TechnicalIndicators.ema(data, fast)
        ema_slow = TechnicalIndicators.ema(data, slow)
        
        macd_line = ema_fast - ema_slow
        signal_line = TechnicalIndicators.ema(macd_line, signal)
        histogram = macd_line - signal_line
        
        return macd_line, signal_line, histogram
    
    @staticmethod
    def bollinger_bands(data: pd.Series, period=20, std_dev=2) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """볼린저 밴드"""
        sma = TechnicalIndicators.sma(data, period)
        std = data.rolling(window=period).std()
        
        upper_band = sma + (std * std_dev)
        lower_band = sma - (std * std_dev)
        
        return upper_band, sma, lower_band
    
    @staticmethod
    def atr(high: pd.Series, low: pd.Series, close: pd.Series, period=14) -> pd.Series:
        """Average True Range (변동성 지표)"""
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        
        return atr
    
    @staticmethod
    def stochastic(high: pd.Series, low: pd.Series, close: pd.Series, 
                   k_period=14, d_period=3) -> Tuple[pd.Series, pd.Series]:
        """스토캐스틱"""
        lowest_low = low.rolling(window=k_period).min()
        highest_high = high.rolling(window=k_period).max()
        
        k_percent = 100 * ((close - lowest_low) / (highest_high - lowest_low))
        d_percent = k_percent.rolling(window=d_period).mean()
        
        return k_percent, d_percent

class RiskManager:
    """개선된 리스크 관리 클래스"""
    
    def __init__(self, config: Config):
        self.config = config
        self.initial_capital = config.trading_params['initial_capital']
        self.current_capital = self.initial_capital
        self.max_position_size = config.trading_params['max_position_size']
        self.stop_loss_pct = config.risk_params['stop_loss_pct']
        self.take_profit_pct = config.risk_params['take_profit_pct']
        self.max_daily_loss = config.risk_params['max_daily_loss']
        self.risk_per_trade = config.risk_params['risk_per_trade']
        self.daily_pnl = 0
        self.daily_trades = 0
        self.max_daily_trades = 10
        
        # 포지션 추적
        self.open_positions = {}
        
    def calculate_position_size(self, price: float, volatility: float = None) -> float:
        """리스크 기반 포지션 크기 계산 (Kelly Criterion 적용)"""
        # 기본 포지션 크기 (리스크 기반)
        risk_amount = self.current_capital * self.risk_per_trade
        stop_loss_amount = price * self.stop_loss_pct
        
        if stop_loss_amount > 0:
            position_size = risk_amount / stop_loss_amount
            
            # 변동성 조정 (ATR 기반)
            if volatility:
                volatility_adj = 1 / (1 + volatility * 10)  # 변동성이 클수록 포지션 감소
                position_size *= volatility_adj
            
            # 최대 포지션 크기 제한
            max_position = self.current_capital * self.max_position_size / price
            
            return min(position_size, max_position)
        return 0
    
    def should_stop_trading(self) -> bool:
        """거래 중단 여부 판단"""
        # 일일 최대 손실 도달
        if self.daily_pnl <= -self.current_capital * self.max_daily_loss:
            logger.warning("일일 최대 손실 도달")
            return True
        
        # 일일 최대 거래 횟수 도달
        if self.daily_trades >= self.max_daily_trades:
            logger.warning("일일 최대 거래 횟수 도달")
            return True
        
        return False
    
    def check_stop_loss(self, entry_price: float, current_price: float, 
                       position_type: PositionType) -> bool:
        """손절매 체크"""
        if position_type == PositionType.LONG:
            return current_price <= entry_price * (1 - self.stop_loss_pct)
        elif position_type == PositionType.SHORT:
            return current_price >= entry_price * (1 + self.stop_loss_pct)
        return False
    
    def check_take_profit(self, entry_price: float, current_price: float, 
                         position_type: PositionType) -> bool:
        """익절매 체크"""
        if position_type == PositionType.LONG:
            return current_price >= entry_price * (1 + self.take_profit_pct)
        elif position_type == PositionType.SHORT:
            return current_price <= entry_price * (1 - self.take_profit_pct)
        return False
    
    def update_daily_stats(self, pnl: float):
        """일일 통계 업데이트"""
        self.daily_pnl += pnl
        self.daily_trades += 1
        self.current_capital += pnl
        
        logger.info(f"일일 PnL: {self.daily_pnl:,.0f}, 거래 횟수: {self.daily_trades}")
    
    def reset_daily_stats(self):
        """일일 통계 리셋"""
        self.daily_pnl = 0
        self.daily_trades = 0
        logger.info("일일 통계 리셋")

class BacktestEngine:
    """개선된 백테스팅 엔진"""
    
    def __init__(self, config: Config):
        self.config = config
        self.initial_capital = config.trading_params['initial_capital']
        self.commission = config.trading_params['commission']
        self.reset()
    
    def reset(self):
        """백테스트 초기화"""
        self.capital = self.initial_capital
        self.position = PositionType.NONE
        self.position_size = 0
        self.entry_price = 0
        self.entry_date = None
        self.trades = []
        self.equity_curve = []
        
    def execute_trade(self, date: datetime, price: float, signal: str, position_size: float = None,):

        """개선된 거래 실행"""
        commission = 0
        
        # 기존 포지션 청산
        if self.position != PositionType.NONE:
            if (self.position == PositionType.LONG and signal == 'sell') or \
               (self.position == PositionType.SHORT and signal == 'buy'):
                
                # PnL 계산
                if self.position == PositionType.LONG:
                    pnl = (price - self.entry_price) * self.position_size
                else:  # SHORT
                    pnl = (self.entry_price - price) * self.position_size
                
                # 수수료 계산
                commission = price * self.position_size * self.commission
                self.capital += pnl - commission
                
                # 거래 기록
                trade = Trade(
                    entry_date=self.entry_date,
                    exit_date=date,
                    position_type=self.position,
                    entry_price=self.entry_price,
                    exit_price=price,
                    quantity=self.position_size,
                    pnl=pnl,
                    commission=commission
                )
                self.trades.append(trade)
                
                logger.debug(f"포지션 청산: {self.position.value} -> PnL: {pnl:,.0f}")
                
                self.position = PositionType.NONE
                self.position_size = 0
        
        # 새 포지션 진입
        if signal in ['buy', 'sell'] and self.position == PositionType.NONE:
            # 포지션 크기 결정
            if position_size is None:
                investment_amount = self.capital * 0.95
                position_size = investment_amount / price
            
            self.position_size = position_size
            self.entry_price = price
            self.entry_date = date
            
            if signal == 'buy':
                self.position = PositionType.LONG
            else:
                self.position = PositionType.SHORT
            
            # 진입 수수료
            commission = price * self.position_size * self.commission
            self.capital -= commission
            
            logger.debug(f"포지션 진입: {self.position.value} @ {price:,.0f}")
        
        # 자산 곡선 기록
        self.equity_curve.append({
            'date': date,
            'capital': self.capital,
            'position': self.position.value,
            'price': price
        })
    
    def get_performance_metrics(self) -> Dict:
        """개선된 성과 지표 계산"""
        if not self.trades:
            return {
                'Total Return (%)': 0,
                'Total Trades': 0,
                'Final Capital': self.capital
            }
        
        # 거래 데이터프레임
        trades_data = []
        for trade in self.trades:
            trades_data.append({
                'entry_date': trade.entry_date,
                'exit_date': trade.exit_date,
                'pnl': trade.pnl,
                'position_type': trade.position_type.value
            })
        df_trades = pd.DataFrame(trades_data)
        
        # 기본 지표
        total_return = (self.capital - self.initial_capital) / self.initial_capital * 100
        win_trades = df_trades[df_trades['pnl'] > 0]
        lose_trades = df_trades[df_trades['pnl'] < 0]
        
        win_rate = len(win_trades) / len(df_trades) * 100 if len(df_trades) > 0 else 0
        avg_win = win_trades['pnl'].mean() if len(win_trades) > 0 else 0
        avg_loss = lose_trades['pnl'].mean() if len(lose_trades) > 0 else 0
        
        # Profit Factor
        total_wins = win_trades['pnl'].sum() if len(win_trades) > 0 else 0
        total_losses = abs(lose_trades['pnl'].sum()) if len(lose_trades) > 0 else 1
        profit_factor = total_wins / total_losses if total_losses > 0 else 0
        
        # 최대 낙폭 (MDD)
        equity_df = pd.DataFrame(self.equity_curve)
        if not equity_df.empty:
            equity_df['cummax'] = equity_df['capital'].cummax()
            equity_df['drawdown'] = (equity_df['capital'] - equity_df['cummax']) / equity_df['cummax']
            max_drawdown = equity_df['drawdown'].min() * 100
            
            # 연간 수익률
            days = (equity_df['date'].max() - equity_df['date'].min()).days
            if days > 0:
                annual_return = ((self.capital / self.initial_capital) ** (365/days) - 1) * 100
            else:
                annual_return = 0
        else:
            max_drawdown = 0
            annual_return = 0
        
        # Sharpe Ratio
        if len(df_trades) > 1:
            returns = df_trades['pnl'] / self.initial_capital
            if returns.std() != 0:
                sharpe_ratio = returns.mean() / returns.std() * np.sqrt(252)
            else:
                sharpe_ratio = 0
        else:
            sharpe_ratio = 0
        
        return {
            'Total Return (%)': round(total_return, 2),
            'Annual Return (%)': round(annual_return, 2),
            'Total Trades': len(df_trades),
            'Win Rate (%)': round(win_rate, 2),
            'Profit Factor': round(profit_factor, 2),
            'Average Win': round(avg_win, 0),
            'Average Loss': round(avg_loss, 0),
            'Max Drawdown (%)': round(max_drawdown, 2),
            'Sharpe Ratio': round(sharpe_ratio, 2),
            'Final Capital': round(self.capital, 0)
        }

class AdvancedTradingStrategy:
    """개선된 트레이딩 전략"""
    
    def __init__(self, trader: UpbitTrader, risk_manager: RiskManager):
        self.trader = trader
        self.risk_manager = risk_manager
        self.indicators = TechnicalIndicators()
        self.position = PositionType.NONE
        self.entry_price = 0
        self.position_size = 0
        
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """모든 기술적 지표 계산"""
        # 이동평균
        df['sma_20'] = self.indicators.sma(df['close'], 20)
        df['sma_50'] = self.indicators.sma(df['close'], 50)
        df['ema_12'] = self.indicators.ema(df['close'], 12)
        
        # RSI
        df['rsi'] = self.indicators.rsi(df['close'])
        
        # MACD
        macd, signal, histogram = self.indicators.macd(df['close'])
        df['macd'] = macd
        df['macd_signal'] = signal
        df['macd_histogram'] = histogram
        
        # 볼린저 밴드
        upper_bb, middle_bb, lower_bb = self.indicators.bollinger_bands(df['close'])
        df['bb_upper'] = upper_bb
        df['bb_middle'] = middle_bb
        df['bb_lower'] = lower_bb
        
        # ATR (변동성)
        df['atr'] = self.indicators.atr(df['high'], df['low'], df['close'])
        
        # 스토캐스틱
        k_percent, d_percent = self.indicators.stochastic(df['high'], df['low'], df['close'])
        df['stoch_k'] = k_percent
        df['stoch_d'] = d_percent
        
        return df
    
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """개선된 신호 생성 로직"""
        signals = []
        position_sizes = []
        
        for i in range(len(df)):
            signal = 'hold'
            position_size = 0
            
            if i < 50:  # 충분한 데이터가 있을 때만
                signals.append(signal)
                position_sizes.append(position_size)
                continue
            
            # 현재 가격과 변동성
            current_price = df['close'].iloc[i]
            volatility = df['atr'].iloc[i] / current_price if current_price > 0 else 0
            
            # 매수 조건 점수 (0-10점)
            buy_score = 0
            
            # 트렌드 조건
            if df['sma_20'].iloc[i] > df['sma_50'].iloc[i]:
                buy_score += 2  # 상승 트렌드
            if df['close'].iloc[i] > df['sma_20'].iloc[i]:
                buy_score += 1  # 단기 이평선 위
            
            # 모멘텀 조건
            if 30 < df['rsi'].iloc[i] < 70:
                buy_score += 2  # RSI 적정 범위
            if df['macd'].iloc[i] > df['macd_signal'].iloc[i]:
                buy_score += 2  # MACD 골든크로스
            
            # 가격 위치
            bb_position = (df['close'].iloc[i] - df['bb_lower'].iloc[i]) / (df['bb_upper'].iloc[i] - df['bb_lower'].iloc[i])
            if 0.2 < bb_position < 0.8:
                buy_score += 1  # 볼린저밴드 중간 영역
            
            # 스토캐스틱
            if df['stoch_k'].iloc[i] < 80 and df['stoch_k'].iloc[i] > df['stoch_d'].iloc[i]:
                buy_score += 2  # 과매수 아니고 상승 신호
            
            # 매도 조건 점수
            sell_score = 0
            
            if df['sma_20'].iloc[i] < df['sma_50'].iloc[i]:
                sell_score += 2  # 하락 트렌드
            if df['close'].iloc[i] < df['sma_20'].iloc[i]:
                sell_score += 1  # 단기 이평선 아래
            if df['rsi'].iloc[i] > 70:
                sell_score += 2  # RSI 과매수
            if df['macd'].iloc[i] < df['macd_signal'].iloc[i]:
                sell_score += 2  # MACD 데드크로스
            if bb_position > 0.9:
                sell_score += 1  # 볼린저밴드 상단 근처
            if df['stoch_k'].iloc[i] > 80 and df['stoch_k'].iloc[i] < df['stoch_d'].iloc[i]:
                sell_score += 2  # 과매수이고 하락 신호
            
            # 신호 결정 (6점 이상)
            if buy_score >= 5: # 테스트 상 일단 5로 조정
                signal = 'buy'
                # 리스크 기반 포지션 크기 계산
                position_size = self.risk_manager.calculate_position_size(current_price, volatility)
            elif sell_score >= 6:
                signal = 'sell'
                position_size = self.risk_manager.calculate_position_size(current_price, volatility)
            
            signals.append(signal)
            position_sizes.append(position_size)
        
        df['signal'] = signals
        df['position_size'] = position_sizes
        
        return df
    
    def backtest_strategy(self, df: pd.DataFrame, strategy_name="Advanced Multi-Indicator Strategy"):
        """전략 백테스팅"""
        logger.info(f"백테스팅 시작: {strategy_name}")
        
        # 지표 계산
        df = self.calculate_indicators(df)
        
        # 신호 생성
        df = self.generate_signals(df)
        
        # 백테스팅 엔진 초기화
        backtest = BacktestEngine(self.risk_manager.config)
        
        # 백테스트 실행
        for i in range(len(df)):
            date = df['date'].iloc[i]
            price = df['close'].iloc[i]
            signal = df['signal'].iloc[i]
            position_size = df['position_size'].iloc[i]
            
            # 리스크 체크
            if backtest.position != PositionType.NONE:
                if self.risk_manager.check_stop_loss(backtest.entry_price, price, backtest.position):
                    # 손절매
                    exit_signal = 'sell' if backtest.position == PositionType.LONG else 'buy'
                    backtest.execute_trade(date, price, exit_signal)
                    logger.debug(f"손절매 실행: {date} @ {price:,.0f}")
                elif self.risk_manager.check_take_profit(backtest.entry_price, price, backtest.position):
                    # 익절매
                    exit_signal = 'sell' if backtest.position == PositionType.LONG else 'buy'
                    backtest.execute_trade(date, price, exit_signal)
                    logger.debug(f"익절매 실행: {date} @ {price:,.0f}")
            
            # 정규 신호
            if signal in ['buy', 'sell']:
                backtest.execute_trade(date, price, signal, position_size)
        
        # 마지막 포지션 정리
        if backtest.position != PositionType.NONE:
            last_price = df['close'].iloc[-1]
            last_date = df['date'].iloc[-1]
            exit_signal = 'sell' if backtest.position == PositionType.LONG else 'buy'
            backtest.execute_trade(last_date, last_price, exit_signal)
        
        # 성과 지표 출력
        metrics = backtest.get_performance_metrics()
        print(f"\n{'='*60}")
        print(f"{strategy_name} 백테스트 결과")
        print(f"{'='*60}")
        for key, value in metrics.items():
            print(f"{key:.<30} {value}")
        print(f"{'='*60}\n")
        
        return backtest, df
    
    def plot_backtest_results(self, backtest: BacktestEngine, df: pd.DataFrame, market: str):
        """백테스트 결과 시각화"""
        fig, axes = plt.subplots(4, 1, figsize=(15, 14))
        
        # 1. 가격 차트와 매매 신호
        ax1 = axes[0]
        ax1.plot(df['date'], df['close'], label='Price', linewidth=1, color='black')
        ax1.plot(df['date'], df['sma_20'], label='SMA 20', alpha=0.7, color='blue')
        ax1.plot(df['date'], df['sma_50'], label='SMA 50', alpha=0.7, color='red')
        
        # 볼린저 밴드
        ax1.fill_between(df['date'], df['bb_upper'], df['bb_lower'], alpha=0.1, color='gray')
        
        # 매수/매도 신호
        buy_signals = df[df['signal'] == 'buy']
        sell_signals = df[df['signal'] == 'sell']
        
        ax1.scatter(buy_signals['date'], buy_signals['close'], 
                   color='green', marker='^', s=100, label='Buy', zorder=5)
        ax1.scatter(sell_signals['date'], sell_signals['close'], 
                   color='red', marker='v', s=100, label='Sell', zorder=5)
        
        ax1.set_title(f'{market} Price Chart with Trading Signals', fontsize=12, fontweight='bold')
        ax1.set_ylabel('Price (KRW)')
        ax1.legend(loc='best')
        ax1.grid(True, alpha=0.3)
        
        # 2. RSI와 스토캐스틱
        ax2 = axes[1]
        ax2.plot(df['date'], df['rsi'], label='RSI', color='purple', linewidth=1)
        ax2.axhline(y=70, color='r', linestyle='--', alpha=0.5)
        ax2.axhline(y=30, color='g', linestyle='--', alpha=0.5)
        
        # 스토캐스틱 추가
        ax2_twin = ax2.twinx()
        ax2_twin.plot(df['date'], df['stoch_k'], label='Stoch %K', color='orange', alpha=0.5)
        ax2_twin.plot(df['date'], df['stoch_d'], label='Stoch %D', color='brown', alpha=0.5)
        
        ax2.set_title('Momentum Indicators', fontsize=12, fontweight='bold')
        ax2.set_ylabel('RSI', color='purple')
        ax2_twin.set_ylabel('Stochastic', color='orange')
        ax2.legend(loc='upper left')
        ax2_twin.legend(loc='upper right')
        ax2.grid(True, alpha=0.3)
        
        # 3. MACD
        ax3 = axes[2]
        ax3.plot(df['date'], df['macd'], label='MACD', color='blue')
        ax3.plot(df['date'], df['macd_signal'], label='Signal', color='red')
        ax3.bar(df['date'], df['macd_histogram'], label='Histogram', alpha=0.3, color='gray')
        ax3.axhline(y=0, color='black', linestyle='-', alpha=0.3)
        
        ax3.set_title('MACD', fontsize=12, fontweight='bold')
        ax3.set_ylabel('Value')
        ax3.legend(loc='best')
        ax3.grid(True, alpha=0.3)
        
        # 4. 자본 곡선과 드로다운
        ax4 = axes[3]
        equity_df = pd.DataFrame(backtest.equity_curve)
        if not equity_df.empty:
            ax4.plot(equity_df['date'], equity_df['capital'], 
                    label='Portfolio Value', color='blue', linewidth=2)
            ax4.axhline(y=backtest.initial_capital, color='gray', 
                       linestyle='--', alpha=0.5, label='Initial Capital')
            
            # 드로다운 표시
            equity_df['cummax'] = equity_df['capital'].cummax()
            equity_df['drawdown'] = (equity_df['capital'] - equity_df['cummax']) / equity_df['cummax'] * 100
            
            ax4_twin = ax4.twinx()
            ax4_twin.fill_between(equity_df['date'], 0, equity_df['drawdown'], 
                                 color='red', alpha=0.3, label='Drawdown')
            ax4_twin.set_ylabel('Drawdown (%)', color='red')
            
            ax4.set_title('Portfolio Equity Curve', fontsize=12, fontweight='bold')
            ax4.set_ylabel('Capital (KRW)', color='blue')
            ax4.set_xlabel('Date')
            ax4.legend(loc='upper left')
            ax4_twin.legend(loc='lower left')
            ax4.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.show()
        
        return fig
    
    def live_trading(self, market: str, db: TradeDatabase):
        """실제 거래 실행"""
        logger.info(f"실시간 거래 시작: {market}")
        
        try:
            # 현재 잔고 확인
            balances = self.trader.get_balances()
            krw_balance = next((b for b in balances if b['currency'] == 'KRW'), None)
            coin_symbol = market.split('-')[1]
            coin_balance = next((b for b in balances if b['currency'] == coin_symbol), None)
            
            if not krw_balance:
                logger.error("KRW 잔고를 찾을 수 없습니다.")
                return
            
            available_krw = float(krw_balance.get('balance', 0))
            available_coin = float(coin_balance.get('balance', 0)) if coin_balance else 0
            
            logger.info(f"현재 잔고 - KRW: {available_krw:,.0f}, {coin_symbol}: {available_coin:.8f}")
            
            # 최근 데이터 수집
            df = self.trader.get_historical_data(market, days=50)
            if df.empty:
                logger.error("데이터 수집 실패")
                return
            
            # 지표 계산 및 신호 생성
            df = self.calculate_indicators(df)
            df = self.generate_signals(df)
            
            # 최신 신호 확인
            latest_signal = df['signal'].iloc[-1]
            latest_price = df['close'].iloc[-1]
            latest_position_size = df['position_size'].iloc[-1]
            
            logger.info(f"최신 신호: {latest_signal} @ {latest_price:,.0f}")
            
            # 리스크 체크
            if self.risk_manager.should_stop_trading():
                logger.warning("리스크 한도 도달. 거래 중단")
                return
            
            # 현재 포지션 체크 및 리스크 관리
            if self.position != PositionType.NONE:
                # 손절/익절 체크
                ticker = self.trader.get_ticker(market)
                current_price = float(ticker['trade_price'])
                
                if self.risk_manager.check_stop_loss(self.entry_price, current_price, self.position):
                    logger.info(f"손절매 신호: {self.entry_price:,.0f} -> {current_price:,.0f}")
                    if self.position == PositionType.LONG and available_coin > 0:
                        result = self.trader.sell_market_order(market, available_coin)
                        self._handle_trade_result(result, 'sell', db, market)
                        
                elif self.risk_manager.check_take_profit(self.entry_price, current_price, self.position):
                    logger.info(f"익절매 신호: {self.entry_price:,.0f} -> {current_price:,.0f}")
                    if self.position == PositionType.LONG and available_coin > 0:
                        result = self.trader.sell_market_order(market, available_coin)
                        self._handle_trade_result(result, 'sell', db, market)
            
            # 신규 매매 신호 처리
            if latest_signal == 'buy' and self.position != PositionType.LONG:
                # 매수 가능 금액 계산
                buy_amount = min(
                    available_krw * 0.95,  # 잔고의 95%
                    latest_position_size * latest_price if latest_position_size > 0 else available_krw * 0.2
                )
                
                if buy_amount >= 5000:  # 최소 주문 금액 체크
                    logger.info(f"매수 주문: {buy_amount:,.0f} KRW")
                    result = self.trader.buy_market_order(market, buy_amount)
                    self._handle_trade_result(result, 'buy', db, market)
                else:
                    logger.warning(f"매수 금액 부족: {buy_amount:,.0f} KRW")
                    
            elif latest_signal == 'sell' and self.position == PositionType.LONG:
                if available_coin > 0:
                    logger.info(f"매도 주문: {available_coin:.8f} {coin_symbol}")
                    result = self.trader.sell_market_order(market, available_coin)
                    self._handle_trade_result(result, 'sell', db, market)
                else:
                    logger.warning("매도할 코인이 없습니다.")
                    
        except Exception as e:
            logger.error(f"실시간 거래 중 오류: {e}")
            
    def _handle_trade_result(self, result: Dict, trade_type: str, db: TradeDatabase, market: str):
        """거래 결과 처리"""
        try:
            if result and 'uuid' in result:
                logger.info(f"{trade_type} 주문 성공: {result['uuid']}")
                
                # 포지션 업데이트
                if trade_type == 'buy':
                    self.position = PositionType.LONG
                    self.entry_price = float(result.get('price', 0))
                    self.position_size = float(result.get('volume', 0))
                else:  # sell
                    # PnL 계산
                    exit_price = float(result.get('price', 0))
                    pnl = (exit_price - self.entry_price) * self.position_size
                    
                    # 거래 기록 저장
                    trade = Trade(
                        entry_date=datetime.now(),
                        exit_date=datetime.now(),
                        position_type=self.position,
                        entry_price=self.entry_price,
                        exit_price=exit_price,
                        quantity=self.position_size,
                        pnl=pnl,
                        commission=float(result.get('paid_fee', 0))
                    )
                    db.save_trade(trade, market)
                    
                    # 리스크 매니저 업데이트
                    self.risk_manager.update_daily_stats(pnl)
                    
                    # 포지션 초기화
                    self.position = PositionType.NONE
                    self.entry_price = 0
                    self.position_size = 0
            else:
                logger.error(f"{trade_type} 주문 실패: {result}")
                
        except Exception as e:
            logger.error(f"거래 결과 처리 중 오류: {e}")

def main():
    """메인 실행 함수"""
    print("=" * 60)
    print("업비트 자동거래 시스템 v2.0")
    print("=" * 60)
    
    # 설정 로드
    config = Config()
    
    # 컴포넌트 초기화
    trader = UpbitTrader(config)
    risk_manager = RiskManager(config)
    strategy = AdvancedTradingStrategy(trader, risk_manager)
    db = TradeDatabase()
    
    # 거래할 마켓
    MARKET = "KRW-BTC"
    
    # 실행 모드 선택
    mode = input("\n실행 모드 선택 (1: 백테스팅, 2: 실시간 거래): ")
    
    if mode == '1':
        # 백테스팅 모드
        print("\n백테스팅 모드 실행...")
        
        # 과거 데이터 수집
        days = int(input("백테스트 기간 (일): ") or "100")
        print(f"\n{days}일간의 데이터 수집 중...")
        
        df = trader.get_historical_data(MARKET, days=days)
        
        if df.empty:
            print("데이터 수집 실패")
            return
        
        print(f"수집 완료: {len(df)}개 캔들")
        print(f"기간: {df['date'].min().date()} ~ {df['date'].max().date()}")
        
        # 백테스팅 실행
        backtest, df_with_signals = strategy.backtest_strategy(df)
        
        # 결과 시각화
        try:
            strategy.plot_backtest_results(backtest, df_with_signals, MARKET)
        except Exception as e:
            logger.error(f"시각화 실패: {e}")
        
        # 상세 거래 내역
        if backtest.trades:
            print("\n최근 거래 내역 (상위 10개)")
            print("-" * 60)
            for i, trade in enumerate(backtest.trades[-10:], 1):
                print(f"{i:2d}. {trade.position_type.value:5s} | "
                      f"진입: {trade.entry_price:8,.0f} | "
                      f"청산: {trade.exit_price:8,.0f} | "
                      f"PnL: {trade.pnl:+8,.0f}")
                      
    elif mode == '2':
        # 실시간 거래 모드
        if not config.access_key or not config.secret_key:
            print("\n⚠️  API 키가 설정되지 않았습니다.")
            print("환경변수 또는 config.json 파일에 API 키를 설정하세요.")
            return
        
        print("\n실시간 거래 모드 실행...")
        print("⚠️  실제 자금으로 거래가 실행됩니다. 주의하세요!")
        
        confirm = input("계속하시겠습니까? (y/n): ")
        if confirm.lower() != 'y':
            print("거래 취소")
            return
        
        print(f"\n거래 시작: {MARKET}")
        print("종료하려면 Ctrl+C를 누르세요.\n")
        
        try:
            while True:
                # 매일 자정에 일일 통계 리셋
                current_time = datetime.now()
                if current_time.hour == 0 and current_time.minute == 0:
                    risk_manager.reset_daily_stats()
                
                # 거래 실행
                strategy.live_trading(MARKET, db)
                
                # 대기 (5분)
                logger.info("다음 실행까지 5분 대기...")
                time.sleep(300)
                
        except KeyboardInterrupt:
            print("\n\n거래 중단")
            
            # 오늘의 거래 결과 출력
            today_trades = db.get_today_trades()
            if today_trades:
                print("\n오늘의 거래 결과:")
                print("-" * 60)
                total_pnl = sum(t[7] for t in today_trades if t[7])  # pnl 컬럼
                print(f"총 거래: {len(today_trades)}건")
                print(f"총 손익: {total_pnl:+,.0f} KRW")
                
        except Exception as e:
            logger.error(f"예상치 못한 오류: {e}")
    
    else:
        print("잘못된 선택입니다.")
    
    print("\n프로그램 종료")

if __name__ == "__main__":
    main()