# advanced_ml_engine.py
# 고급 ML 엔진: 앙상블 + LSTM 통합

import numpy as np
import pandas as pd
import pyupbit
import pickle
import logging
import os
import warnings
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional

# 설정 로드
try:
    from config import ADVANCED_ML_CONFIG
except ImportError:
    ADVANCED_ML_CONFIG = {'training': {'auto_retrain_days': 3}}

# sklearn
from sklearn.ensemble import RandomForestClassifier, VotingClassifier
from sklearn.preprocessing import StandardScaler, RobustScaler
from sklearn.model_selection import train_test_split, TimeSeriesSplit
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
from sklearn.utils.class_weight import compute_class_weight

# Gradient Boosting models - 선택적 import (없어도 동작)
# DLL 로딩 실패 등 모든 예외 처리
XGB_AVAILABLE = False
LGB_AVAILABLE = False
TORCH_AVAILABLE = False

try:
    import xgboost as xgb
    XGB_AVAILABLE = True
except Exception:
    # ImportError, XGBoostLibraryNotFound 등 모든 예외 처리
    xgb = None

try:
    import lightgbm as lgb
    LGB_AVAILABLE = True
except Exception:
    # ImportError, DLL 로딩 실패 등 모든 예외 처리
    lgb = None

# PyTorch for LSTM - 선택적 import
try:
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, TensorDataset
    TORCH_AVAILABLE = True
except Exception:
    # ImportError, DLL 로딩 실패 등 모든 예외 처리
    torch = None
    nn = None

warnings.filterwarnings('ignore')
os.environ['LOKY_MAX_CPU_COUNT'] = '4'

logger = logging.getLogger(__name__)

# 사용 가능한 라이브러리 로깅
_lib_status = []
if XGB_AVAILABLE:
    _lib_status.append("XGBoost")
if LGB_AVAILABLE:
    _lib_status.append("LightGBM")
if TORCH_AVAILABLE:
    _lib_status.append("PyTorch")
if _lib_status:
    logger.info(f"고급 ML 라이브러리 로드됨: {', '.join(_lib_status)}")
else:
    logger.warning("고급 ML 라이브러리 없음 - RandomForest만 사용합니다")


# ============================================================
# LSTM 모델 정의
# ============================================================
if TORCH_AVAILABLE:
    class LSTMModel(nn.Module):
        """LSTM 기반 시계열 예측 모델"""

        def __init__(self, input_size, hidden_size=64, num_layers=2, dropout=0.2):
            super(LSTMModel, self).__init__()

            self.hidden_size = hidden_size
            self.num_layers = num_layers

            self.lstm = nn.LSTM(
                input_size=input_size,
                hidden_size=hidden_size,
                num_layers=num_layers,
                batch_first=True,
                dropout=dropout if num_layers > 1 else 0
            )

            self.fc = nn.Sequential(
                nn.Linear(hidden_size, 32),
                nn.ReLU(),
                nn.Dropout(dropout),
                nn.Linear(32, 1),
                nn.Sigmoid()
            )

        def forward(self, x):
            # LSTM 출력
            lstm_out, _ = self.lstm(x)
            # 마지막 시점의 출력만 사용
            last_output = lstm_out[:, -1, :]
            # FC 레이어 통과
            out = self.fc(last_output)
            return out
else:
    # PyTorch가 없으면 더미 클래스 정의
    LSTMModel = None


# ============================================================
# 고급 피처 엔지니어링
# ============================================================
class AdvancedFeatureEngine:
    """고급 피처 엔지니어링"""

    def __init__(self):
        self.feature_names = []

    def create_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """종합 피처 생성 (50+ 피처)"""
        features = pd.DataFrame(index=df.index)

        # ==========================================
        # 1. 기본 가격 특성
        # ==========================================
        for period in [1, 4, 8, 12, 24, 48]:
            features[f'returns_{period}h'] = df['close'].pct_change(period)

        # ==========================================
        # 2. 이동평균 (SMA, EMA)
        # ==========================================
        for period in [5, 10, 20, 50, 100]:
            features[f'sma_{period}'] = df['close'].rolling(period).mean()
            features[f'ema_{period}'] = df['close'].ewm(span=period).mean()
            features[f'price_to_sma_{period}'] = df['close'] / features[f'sma_{period}']
            features[f'price_to_ema_{period}'] = df['close'] / features[f'ema_{period}']

        # 이동평균 크로스
        features['sma_cross_10_50'] = features['sma_10'] - features['sma_50']
        features['ema_cross_10_50'] = features['ema_10'] - features['ema_50']

        # ==========================================
        # 3. RSI (다중 기간)
        # ==========================================
        for period in [7, 14, 21]:
            features[f'rsi_{period}'] = self._calculate_rsi(df['close'], period)

        # RSI 기반 파생 피처
        features['rsi_14_overbought'] = (features['rsi_14'] > 70).astype(int)
        features['rsi_14_oversold'] = (features['rsi_14'] < 30).astype(int)

        # ==========================================
        # 4. MACD
        # ==========================================
        ema_12 = df['close'].ewm(span=12).mean()
        ema_26 = df['close'].ewm(span=26).mean()
        features['macd'] = ema_12 - ema_26
        features['macd_signal'] = features['macd'].ewm(span=9).mean()
        features['macd_histogram'] = features['macd'] - features['macd_signal']
        features['macd_cross'] = (features['macd'] > features['macd_signal']).astype(int)

        # ==========================================
        # 5. Stochastic Oscillator
        # ==========================================
        for period in [14, 21]:
            low_min = df['low'].rolling(period).min()
            high_max = df['high'].rolling(period).max()
            features[f'stoch_k_{period}'] = 100 * (df['close'] - low_min) / (high_max - low_min + 1e-10)
            features[f'stoch_d_{period}'] = features[f'stoch_k_{period}'].rolling(3).mean()

        # ==========================================
        # 6. Bollinger Bands
        # ==========================================
        for period in [20]:
            sma = df['close'].rolling(period).mean()
            std = df['close'].rolling(period).std()
            features[f'bb_upper_{period}'] = sma + (std * 2)
            features[f'bb_lower_{period}'] = sma - (std * 2)
            features[f'bb_width_{period}'] = (features[f'bb_upper_{period}'] - features[f'bb_lower_{period}']) / sma
            features[f'bb_position_{period}'] = (df['close'] - features[f'bb_lower_{period}']) / \
                                                 (features[f'bb_upper_{period}'] - features[f'bb_lower_{period}'] + 1e-10)

        # ==========================================
        # 7. ATR (Average True Range)
        # ==========================================
        for period in [14, 21]:
            features[f'atr_{period}'] = self._calculate_atr(df, period)
            features[f'atr_pct_{period}'] = features[f'atr_{period}'] / df['close']

        # ==========================================
        # 8. ADX (Average Directional Index)
        # ==========================================
        features['adx'] = self._calculate_adx(df, 14)
        features['adx_strong_trend'] = (features['adx'] > 25).astype(int)

        # ==========================================
        # 9. OBV (On-Balance Volume)
        # ==========================================
        features['obv'] = self._calculate_obv(df)
        features['obv_sma'] = features['obv'].rolling(20).mean()
        features['obv_trend'] = (features['obv'] > features['obv_sma']).astype(int)

        # ==========================================
        # 10. 거래량 분석
        # ==========================================
        features['volume_sma_20'] = df['volume'].rolling(20).mean()
        features['volume_ratio'] = df['volume'] / (features['volume_sma_20'] + 1e-10)
        features['volume_change'] = df['volume'].pct_change()
        features['volume_momentum'] = df['volume'].rolling(5).mean() / (df['volume'].rolling(20).mean() + 1e-10)

        # VWAP (Volume Weighted Average Price)
        features['vwap'] = (df['close'] * df['volume']).cumsum() / (df['volume'].cumsum() + 1e-10)
        features['price_to_vwap'] = df['close'] / (features['vwap'] + 1e-10)

        # ==========================================
        # 11. 모멘텀 지표
        # ==========================================
        for period in [5, 10, 20]:
            features[f'momentum_{period}'] = df['close'] / df['close'].shift(period) - 1
            features[f'roc_{period}'] = df['close'].pct_change(period) * 100

        # ==========================================
        # 12. 캔들 패턴
        # ==========================================
        features['candle_body'] = (df['close'] - df['open']) / (df['open'] + 1e-10)
        features['candle_body_abs'] = features['candle_body'].abs()
        features['upper_shadow'] = (df['high'] - df[['open', 'close']].max(axis=1)) / (df['open'] + 1e-10)
        features['lower_shadow'] = (df[['open', 'close']].min(axis=1) - df['low']) / (df['open'] + 1e-10)
        features['candle_range'] = (df['high'] - df['low']) / (df['open'] + 1e-10)

        # 연속 양봉/음봉
        features['consecutive_green'] = (df['close'] > df['open']).rolling(3).sum()
        features['consecutive_red'] = (df['close'] < df['open']).rolling(3).sum()

        # ==========================================
        # 13. 변동성
        # ==========================================
        features['volatility_20'] = df['close'].pct_change().rolling(20).std()
        features['volatility_50'] = df['close'].pct_change().rolling(50).std()
        features['volatility_ratio'] = features['volatility_20'] / (features['volatility_50'] + 1e-10)

        # ==========================================
        # 14. 지지/저항 레벨
        # ==========================================
        features['high_20'] = df['high'].rolling(20).max()
        features['low_20'] = df['low'].rolling(20).min()
        features['price_position_20'] = (df['close'] - features['low_20']) / \
                                         (features['high_20'] - features['low_20'] + 1e-10)

        # ==========================================
        # 15. 시간 특성
        # ==========================================
        features['hour'] = df.index.hour
        features['day_of_week'] = df.index.dayofweek
        features['is_weekend'] = (df.index.dayofweek >= 5).astype(int)

        # 시간대별 구분 (아시아/유럽/미국)
        features['session_asia'] = ((features['hour'] >= 0) & (features['hour'] < 8)).astype(int)
        features['session_europe'] = ((features['hour'] >= 8) & (features['hour'] < 16)).astype(int)
        features['session_us'] = ((features['hour'] >= 16) & (features['hour'] < 24)).astype(int)

        # 피처 이름 저장
        self.feature_names = list(features.columns)

        return features

    def _calculate_rsi(self, prices, period=14):
        """RSI 계산"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / (loss + 1e-10)
        return 100 - (100 / (1 + rs))

    def _calculate_atr(self, df, period=14):
        """ATR 계산"""
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        return true_range.rolling(period).mean()

    def _calculate_adx(self, df, period=14):
        """ADX 계산"""
        plus_dm = df['high'].diff()
        minus_dm = df['low'].diff()

        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm > 0] = 0
        minus_dm = minus_dm.abs()

        tr = self._calculate_atr(df, 1)

        plus_di = 100 * (plus_dm.rolling(period).mean() / (tr.rolling(period).mean() + 1e-10))
        minus_di = 100 * (minus_dm.rolling(period).mean() / (tr.rolling(period).mean() + 1e-10))

        dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)
        adx = dx.rolling(period).mean()

        return adx

    def _calculate_obv(self, df):
        """OBV 계산"""
        obv = [0]
        for i in range(1, len(df)):
            if df['close'].iloc[i] > df['close'].iloc[i - 1]:
                obv.append(obv[-1] + df['volume'].iloc[i])
            elif df['close'].iloc[i] < df['close'].iloc[i - 1]:
                obv.append(obv[-1] - df['volume'].iloc[i])
            else:
                obv.append(obv[-1])
        return pd.Series(obv, index=df.index)


# ============================================================
# 앙상블 모델
# ============================================================
class EnsembleModel:
    """앙상블 모델 (RF + XGBoost + LightGBM) - 라이브러리 없으면 RF만 사용"""

    def __init__(self):
        self.models = {}
        # 가중치는 사용 가능한 라이브러리에 따라 동적 조정
        self._init_weights()
        self.scaler = RobustScaler()
        self.is_trained = False

    def _init_weights(self):
        """사용 가능한 라이브러리에 따라 가중치 설정"""
        if XGB_AVAILABLE and LGB_AVAILABLE:
            self.weights = {'rf': 0.25, 'xgb': 0.40, 'lgb': 0.35}
            logger.info("앙상블 모드: RF + XGBoost + LightGBM")
        elif XGB_AVAILABLE:
            self.weights = {'rf': 0.40, 'xgb': 0.60}
            logger.info("앙상블 모드: RF + XGBoost")
        elif LGB_AVAILABLE:
            self.weights = {'rf': 0.40, 'lgb': 0.60}
            logger.info("앙상블 모드: RF + LightGBM")
        else:
            self.weights = {'rf': 1.0}
            logger.info("앙상블 모드: RandomForest만 사용")

    def train(self, X: pd.DataFrame, y: pd.Series) -> Dict:
        """앙상블 모델 학습"""
        logger.info("🎯 앙상블 모델 학습 시작...")

        # 클래스 가중치 계산 (불균형 처리)
        classes = np.unique(y)
        class_weights = compute_class_weight('balanced', classes=classes, y=y)
        class_weight_dict = dict(zip(classes, class_weights))

        # 스케일링
        X_scaled = self.scaler.fit_transform(X)

        # 학습/테스트 분할 (시계열 고려)
        X_train, X_test, y_train, y_test = train_test_split(
            X_scaled, y, test_size=0.2, shuffle=False  # 시계열이므로 셔플 안함
        )

        results = {}

        # 1. Random Forest (항상 사용)
        logger.info("  📊 Random Forest 학습...")
        self.models['rf'] = RandomForestClassifier(
            n_estimators=200,
            max_depth=12,
            min_samples_split=10,
            min_samples_leaf=5,
            class_weight=class_weight_dict,
            random_state=42,
            n_jobs=-1
        )
        self.models['rf'].fit(X_train, y_train)
        rf_pred = self.models['rf'].predict(X_test)
        results['rf'] = {
            'accuracy': accuracy_score(y_test, rf_pred),
            'precision': precision_score(y_test, rf_pred, zero_division=0),
            'recall': recall_score(y_test, rf_pred, zero_division=0),
            'f1': f1_score(y_test, rf_pred, zero_division=0)
        }

        # 2. XGBoost (사용 가능한 경우)
        if XGB_AVAILABLE and xgb is not None:
            logger.info("  📊 XGBoost 학습...")
            scale_pos_weight = len(y[y == 0]) / (len(y[y == 1]) + 1)
            self.models['xgb'] = xgb.XGBClassifier(
                n_estimators=200,
                max_depth=8,
                learning_rate=0.05,
                subsample=0.8,
                colsample_bytree=0.8,
                scale_pos_weight=scale_pos_weight,
                random_state=42,
                verbosity=0,
                use_label_encoder=False,
                eval_metric='logloss'
            )
            self.models['xgb'].fit(X_train, y_train)
            xgb_pred = self.models['xgb'].predict(X_test)
            results['xgb'] = {
                'accuracy': accuracy_score(y_test, xgb_pred),
                'precision': precision_score(y_test, xgb_pred, zero_division=0),
                'recall': recall_score(y_test, xgb_pred, zero_division=0),
                'f1': f1_score(y_test, xgb_pred, zero_division=0)
            }
        else:
            logger.info("  ⚠️ XGBoost 사용 불가 - 스킵")

        # 3. LightGBM (사용 가능한 경우)
        if LGB_AVAILABLE and lgb is not None:
            logger.info("  📊 LightGBM 학습...")
            self.models['lgb'] = lgb.LGBMClassifier(
                n_estimators=200,
                max_depth=8,
                learning_rate=0.05,
                subsample=0.8,
                colsample_bytree=0.8,
                class_weight=class_weight_dict,
                random_state=42,
                verbosity=-1
            )
            self.models['lgb'].fit(X_train, y_train)
            lgb_pred = self.models['lgb'].predict(X_test)
            results['lgb'] = {
                'accuracy': accuracy_score(y_test, lgb_pred),
                'precision': precision_score(y_test, lgb_pred, zero_division=0),
                'recall': recall_score(y_test, lgb_pred, zero_division=0),
                'f1': f1_score(y_test, lgb_pred, zero_division=0)
            }
        else:
            logger.info("  ⚠️ LightGBM 사용 불가 - 스킵")

        # 앙상블 예측
        ensemble_proba = self._ensemble_predict_proba(X_test)
        ensemble_pred = (ensemble_proba > 0.5).astype(int)
        results['ensemble'] = {
            'accuracy': accuracy_score(y_test, ensemble_pred),
            'precision': precision_score(y_test, ensemble_pred, zero_division=0),
            'recall': recall_score(y_test, ensemble_pred, zero_division=0),
            'f1': f1_score(y_test, ensemble_pred, zero_division=0)
        }

        self.is_trained = True

        # 결과 로깅
        logger.info("\n📊 모델별 성능:")
        for name, metrics in results.items():
            logger.info(f"  {name.upper()}: Acc={metrics['accuracy']:.1%}, "
                        f"Prec={metrics['precision']:.1%}, "
                        f"F1={metrics['f1']:.1%}")

        return results

    def _ensemble_predict_proba(self, X) -> np.ndarray:
        """앙상블 확률 예측"""
        probas = []
        for name, model in self.models.items():
            proba = model.predict_proba(X)[:, 1]
            probas.append(proba * self.weights[name])

        return np.sum(probas, axis=0)

    def predict(self, X: np.ndarray) -> Tuple[int, float]:
        """예측 (앙상블)"""
        if not self.is_trained:
            return 0, 0.0

        X_scaled = self.scaler.transform(X.reshape(1, -1))
        proba = self._ensemble_predict_proba(X_scaled)[0]
        prediction = int(proba > 0.5)

        return prediction, proba


# ============================================================
# LSTM 래퍼
# ============================================================
class LSTMWrapper:
    """LSTM 모델 래퍼 - PyTorch 없으면 비활성화"""

    def __init__(self, sequence_length=24, hidden_size=64, num_layers=2):
        self.sequence_length = sequence_length
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.model = None
        self.scaler = RobustScaler()
        self.is_trained = False
        self.torch_available = TORCH_AVAILABLE

        if TORCH_AVAILABLE:
            self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        else:
            self.device = None
            logger.warning("PyTorch 사용 불가 - LSTM 비활성화")

    def _create_sequences(self, X: np.ndarray, y: np.ndarray = None) -> Tuple:
        """시퀀스 데이터 생성"""
        sequences = []
        labels = []

        for i in range(len(X) - self.sequence_length):
            seq = X[i:i + self.sequence_length]
            sequences.append(seq)
            if y is not None:
                labels.append(y[i + self.sequence_length])

        sequences = np.array(sequences)

        if y is not None:
            labels = np.array(labels)
            return sequences, labels
        return sequences

    def train(self, X: pd.DataFrame, y: pd.Series, epochs=50, batch_size=32) -> Dict:
        """LSTM 학습"""
        if not self.torch_available:
            logger.warning("⚠️ PyTorch 없음 - LSTM 학습 스킵")
            return {'accuracy': 0, 'precision': 0, 'recall': 0, 'f1': 0}

        logger.info("🧠 LSTM 모델 학습 시작...")

        # 스케일링
        X_scaled = self.scaler.fit_transform(X)
        y_values = y.values

        # 시퀀스 생성
        X_seq, y_seq = self._create_sequences(X_scaled, y_values)

        # 학습/테스트 분할
        split_idx = int(len(X_seq) * 0.8)
        X_train, X_test = X_seq[:split_idx], X_seq[split_idx:]
        y_train, y_test = y_seq[:split_idx], y_seq[split_idx:]

        # 텐서 변환
        X_train_t = torch.FloatTensor(X_train).to(self.device)
        y_train_t = torch.FloatTensor(y_train).unsqueeze(1).to(self.device)
        X_test_t = torch.FloatTensor(X_test).to(self.device)
        y_test_t = torch.FloatTensor(y_test).unsqueeze(1).to(self.device)

        # 데이터로더
        train_dataset = TensorDataset(X_train_t, y_train_t)
        train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)

        # 모델 생성
        input_size = X.shape[1]
        self.model = LSTMModel(
            input_size=input_size,
            hidden_size=self.hidden_size,
            num_layers=self.num_layers
        ).to(self.device)

        # 클래스 불균형 처리
        pos_weight = torch.tensor([len(y_train[y_train == 0]) / (len(y_train[y_train == 1]) + 1)]).to(self.device)
        criterion = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
        optimizer = torch.optim.Adam(self.model.parameters(), lr=0.001)
        scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=5, factor=0.5)

        # 학습
        best_loss = float('inf')
        patience_counter = 0

        for epoch in range(epochs):
            self.model.train()
            total_loss = 0

            for batch_X, batch_y in train_loader:
                optimizer.zero_grad()
                outputs = self.model(batch_X)
                loss = criterion(outputs, batch_y)
                loss.backward()
                optimizer.step()
                total_loss += loss.item()

            avg_loss = total_loss / len(train_loader)
            scheduler.step(avg_loss)

            # Early stopping
            if avg_loss < best_loss:
                best_loss = avg_loss
                patience_counter = 0
            else:
                patience_counter += 1
                if patience_counter >= 10:
                    logger.info(f"  Early stopping at epoch {epoch + 1}")
                    break

            if (epoch + 1) % 10 == 0:
                logger.info(f"  Epoch {epoch + 1}/{epochs}, Loss: {avg_loss:.4f}")

        # 평가
        self.model.eval()
        with torch.no_grad():
            test_outputs = self.model(X_test_t)
            test_proba = torch.sigmoid(test_outputs).cpu().numpy().flatten()
            test_pred = (test_proba > 0.5).astype(int)

        results = {
            'accuracy': accuracy_score(y_test, test_pred),
            'precision': precision_score(y_test, test_pred, zero_division=0),
            'recall': recall_score(y_test, test_pred, zero_division=0),
            'f1': f1_score(y_test, test_pred, zero_division=0)
        }

        self.is_trained = True

        logger.info(f"\n📊 LSTM 성능: Acc={results['accuracy']:.1%}, "
                    f"Prec={results['precision']:.1%}, F1={results['f1']:.1%}")

        return results

    def predict(self, X: np.ndarray) -> Tuple[int, float]:
        """예측"""
        if not self.torch_available or not self.is_trained or self.model is None:
            return 0, 0.0

        self.model.eval()
        X_scaled = self.scaler.transform(X)

        # 시퀀스 생성
        if len(X_scaled) < self.sequence_length:
            return 0, 0.0

        seq = X_scaled[-self.sequence_length:]
        seq_tensor = torch.FloatTensor(seq).unsqueeze(0).to(self.device)

        with torch.no_grad():
            output = self.model(seq_tensor)
            proba = torch.sigmoid(output).cpu().numpy()[0, 0]

        prediction = int(proba > 0.5)
        return prediction, float(proba)


# ============================================================
# 통합 ML 엔진
# ============================================================
class AdvancedMLEngine:
    """통합 고급 ML 엔진"""

    def __init__(self):
        self.feature_engine = AdvancedFeatureEngine()
        self.ensemble_model = EnsembleModel()
        self.lstm_model = LSTMWrapper(sequence_length=24)
        self.is_trained = False

        # 모델 가중치 (앙상블 vs LSTM)
        self.model_weights = {'ensemble': 0.6, 'lstm': 0.4}

        # 파일 경로
        self.model_dir = 'ml_models'
        os.makedirs(self.model_dir, exist_ok=True)

        # 학습 파라미터
        self.prediction_horizon = 6  # 6시간 후 예측
        self.min_profit_threshold = 0.015  # 1.5%

        # 주기적 재학습 관련
        self.last_trained_at = None  # 마지막 학습 시점
        self.auto_retrain_days = ADVANCED_ML_CONFIG.get('training', {}).get('auto_retrain_days', 3)

        # 모델 로드 시도
        self._load_models()

    def train(self, symbols: List[str], retrain=False) -> Dict:
        """전체 모델 학습"""
        if self.is_trained and not retrain:
            logger.info("이미 학습된 모델이 있습니다. retrain=True로 재학습하세요.")
            return {}

        logger.info("=" * 60)
        logger.info("🚀 고급 ML 엔진 학습 시작")
        logger.info("=" * 60)

        # 데이터 수집
        all_features = []
        all_labels = []

        for symbol in symbols:
            logger.info(f"📊 {symbol} 데이터 수집 중...")
            features, labels = self._prepare_data(symbol)

            if features is not None and len(features) > 100:
                all_features.append(features)
                all_labels.append(labels)
                logger.info(f"  ✅ {symbol}: {len(features)}개 샘플")
            else:
                logger.warning(f"  ⚠️ {symbol}: 데이터 부족")

        if not all_features:
            logger.error("학습 데이터가 없습니다!")
            return {}

        # 데이터 결합
        X = pd.concat(all_features, ignore_index=True)
        y = pd.concat(all_labels, ignore_index=True)

        logger.info(f"\n총 학습 데이터: {len(X)}개")
        logger.info(f"긍정 샘플 비율: {y.mean():.1%}")

        results = {}

        # 1. 앙상블 모델 학습
        logger.info("\n" + "=" * 40)
        results['ensemble'] = self.ensemble_model.train(X, y)

        # 2. LSTM 모델 학습
        logger.info("\n" + "=" * 40)
        results['lstm'] = self.lstm_model.train(X, y)

        self.is_trained = True
        self.last_trained_at = datetime.now()  # 학습 완료 시점 기록

        # 모델 저장
        self._save_models()

        logger.info("\n" + "=" * 60)
        logger.info(f"✅ 고급 ML 엔진 학습 완료! ({self.last_trained_at.strftime('%Y-%m-%d %H:%M')})")
        logger.info("=" * 60)

        return results

    def _prepare_data(self, symbol: str) -> Tuple[Optional[pd.DataFrame], Optional[pd.Series]]:
        """학습 데이터 준비"""
        try:
            ticker = f"KRW-{symbol}"
            df = pyupbit.get_ohlcv(ticker, interval="minute60", count=2000)

            if df is None or len(df) < 200:
                return None, None

            # 피처 생성
            features = self.feature_engine.create_features(df)

            # 레이블 생성
            future_returns = df['close'].shift(-self.prediction_horizon) / df['close'] - 1
            labels = (future_returns > self.min_profit_threshold).astype(int)

            # NaN 제거
            valid_idx = ~(features.isna().any(axis=1) | labels.isna())
            features = features[valid_idx]
            labels = labels[valid_idx]

            return features, labels

        except Exception as e:
            logger.error(f"{symbol} 데이터 준비 실패: {e}")
            return None, None

    def predict(self, symbol: str) -> Optional[Dict]:
        """예측 실행"""
        if not self.is_trained:
            logger.warning("모델이 학습되지 않았습니다.")
            return None

        try:
            ticker = f"KRW-{symbol}"
            df = pyupbit.get_ohlcv(ticker, interval="minute60", count=200)

            if df is None or len(df) < 100:
                return None

            # 피처 생성
            features = self.feature_engine.create_features(df)

            # NaN 체크
            if features.iloc[-1:].isna().any().any():
                return None

            # 앙상블 예측
            ensemble_pred, ensemble_proba = self.ensemble_model.predict(
                features.iloc[-1].values
            )

            # LSTM 예측
            lstm_pred, lstm_proba = self.lstm_model.predict(features.values)

            # 통합 예측
            final_proba = (ensemble_proba * self.model_weights['ensemble'] +
                           lstm_proba * self.model_weights['lstm'])
            final_pred = int(final_proba > 0.5)

            return {
                'symbol': symbol,
                'prediction': bool(final_pred),
                'probability': float(final_proba),
                'ensemble_prob': float(ensemble_proba),
                'lstm_prob': float(lstm_proba),
                'confidence': float(max(final_proba, 1 - final_proba)),
                'timestamp': datetime.now()
            }

        except Exception as e:
            logger.error(f"{symbol} 예측 실패: {e}")
            return None

    def get_signal(self, symbol: str, confidence_threshold: float = 0.60) -> Tuple[bool, str]:
        """거래 신호 생성"""
        prediction = self.predict(symbol)

        if not prediction:
            return False, "예측 불가"

        if prediction['prediction'] and prediction['probability'] >= confidence_threshold:
            return True, (f"🤖 ML 매수 신호 (확률: {prediction['probability']:.1%}, "
                          f"앙상블: {prediction['ensemble_prob']:.1%}, "
                          f"LSTM: {prediction['lstm_prob']:.1%})")

        return False, f"ML 신호 약함 (확률: {prediction['probability']:.1%})"

    def needs_retraining(self, retrain_days: int = None) -> Tuple[bool, str]:
        """
        재학습 필요 여부 확인

        Args:
            retrain_days: 재학습 주기 (일). None이면 self.auto_retrain_days 사용

        Returns:
            (재학습 필요 여부, 사유)
        """
        if retrain_days is None:
            retrain_days = self.auto_retrain_days

        # 모델이 없으면 학습 필요
        if not self.is_trained:
            return True, "모델이 학습되지 않음"

        # 학습 시점 정보가 없으면 재학습 권장
        if self.last_trained_at is None:
            return True, "학습 시점 정보 없음 (재학습 권장)"

        # 경과 시간 계산
        elapsed = datetime.now() - self.last_trained_at
        elapsed_days = elapsed.total_seconds() / (24 * 3600)

        if elapsed_days >= retrain_days:
            return True, f"마지막 학습 후 {elapsed_days:.1f}일 경과 (기준: {retrain_days}일)"

        return False, f"재학습 불필요 ({elapsed_days:.1f}일/{retrain_days}일)"

    def get_training_status(self) -> Dict:
        """학습 상태 정보 반환"""
        status = {
            'is_trained': self.is_trained,
            'last_trained_at': self.last_trained_at.isoformat() if self.last_trained_at else None,
            'auto_retrain_days': self.auto_retrain_days,
            'needs_retraining': False,
            'reason': ''
        }

        needs, reason = self.needs_retraining()
        status['needs_retraining'] = needs
        status['reason'] = reason

        if self.last_trained_at:
            elapsed = datetime.now() - self.last_trained_at
            status['days_since_training'] = elapsed.total_seconds() / (24 * 3600)

        return status

    def auto_retrain_if_needed(self, symbols: List[str], retrain_days: int = None) -> Dict:
        """
        필요시 자동 재학습 수행

        Args:
            symbols: 학습에 사용할 심볼 목록
            retrain_days: 재학습 주기 (일)

        Returns:
            학습 결과 또는 스킵 정보
        """
        needs, reason = self.needs_retraining(retrain_days)

        if not needs:
            logger.info(f"🔄 재학습 체크: {reason}")
            return {'retrained': False, 'reason': reason}

        logger.info(f"🔄 자동 재학습 시작: {reason}")
        result = self.train(symbols, retrain=True)
        result['retrained'] = True
        result['trigger_reason'] = reason

        return result

    def _save_models(self):
        """모델 저장"""
        try:
            # 앙상블 모델 (학습 타임스탬프 포함)
            with open(f"{self.model_dir}/ensemble_model.pkl", 'wb') as f:
                pickle.dump({
                    'models': self.ensemble_model.models,
                    'weights': self.ensemble_model.weights,
                    'scaler': self.ensemble_model.scaler,
                    'feature_names': self.feature_engine.feature_names,
                    'trained_at': datetime.now().isoformat()  # 학습 시점 저장
                }, f)

            # LSTM 모델 (PyTorch 있을 때만)
            if TORCH_AVAILABLE and self.lstm_model.model is not None:
                torch.save({
                    'model_state': self.lstm_model.model.state_dict(),
                    'scaler': self.lstm_model.scaler,
                    'config': {
                        'input_size': len(self.feature_engine.feature_names),
                        'hidden_size': self.lstm_model.hidden_size,
                        'num_layers': self.lstm_model.num_layers,
                        'sequence_length': self.lstm_model.sequence_length
                    }
                }, f"{self.model_dir}/lstm_model.pt")

            logger.info(f"✅ 모델 저장 완료: {self.model_dir}/")

        except Exception as e:
            logger.error(f"모델 저장 실패: {e}")

    def _load_models(self):
        """모델 로드"""
        try:
            # 앙상블 모델
            ensemble_path = f"{self.model_dir}/ensemble_model.pkl"
            if os.path.exists(ensemble_path):
                with open(ensemble_path, 'rb') as f:
                    data = pickle.load(f)
                    self.ensemble_model.models = data['models']
                    self.ensemble_model.weights = data['weights']
                    self.ensemble_model.scaler = data['scaler']
                    self.feature_engine.feature_names = data['feature_names']
                    self.ensemble_model.is_trained = True
                    # 학습 타임스탬프 로드
                    if 'trained_at' in data:
                        self.last_trained_at = datetime.fromisoformat(data['trained_at'])
                        logger.info(f"✅ 앙상블 모델 로드 완료 (학습일: {self.last_trained_at.strftime('%Y-%m-%d %H:%M')})")
                    else:
                        self.last_trained_at = None
                        logger.info("✅ 앙상블 모델 로드 완료 (학습일 정보 없음)")

            # LSTM 모델 (PyTorch 있을 때만)
            lstm_path = f"{self.model_dir}/lstm_model.pt"
            if TORCH_AVAILABLE and os.path.exists(lstm_path):
                # PyTorch 2.6+ 호환: weights_only=False 사용 (신뢰할 수 있는 로컬 모델)
                checkpoint = torch.load(lstm_path, map_location=self.lstm_model.device, weights_only=False)
                config = checkpoint['config']

                self.lstm_model.model = LSTMModel(
                    input_size=config['input_size'],
                    hidden_size=config['hidden_size'],
                    num_layers=config['num_layers']
                ).to(self.lstm_model.device)
                self.lstm_model.model.load_state_dict(checkpoint['model_state'])
                self.lstm_model.scaler = checkpoint['scaler']
                self.lstm_model.is_trained = True
                logger.info("✅ LSTM 모델 로드 완료")
            elif not TORCH_AVAILABLE:
                logger.info("PyTorch 없음 - LSTM 모델 로드 스킵")

            # 앙상블 모델만 있어도 사용 가능
            if self.ensemble_model.is_trained:
                self.is_trained = True
                if not self.lstm_model.is_trained:
                    logger.warning("⚠️ LSTM 모델 없음 - 앙상블 모델만 사용")
                    # LSTM 가중치를 0으로, 앙상블 가중치를 1로 조정
                    self.model_weights = {'ensemble': 1.0, 'lstm': 0.0}

        except FileNotFoundError:
            logger.info("저장된 ML 모델이 없습니다. 학습이 필요합니다.")
        except Exception as e:
            logger.error(f"모델 로드 실패: {e}")


# ============================================================
# 싱글톤 인스턴스
# ============================================================
_engine_instance = None


def get_advanced_ml_engine() -> AdvancedMLEngine:
    """싱글톤 인스턴스 반환"""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = AdvancedMLEngine()
    return _engine_instance
