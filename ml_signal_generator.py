# ml_signal_generator.py

import numpy as np
import pandas as pd
import pyupbit
import pickle
import logging
from datetime import datetime, timedelta
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
import warnings
import os

# sklearn parallel 경고 억제
os.environ['LOKY_MAX_CPU_COUNT'] = '4'
warnings.filterwarnings('ignore', category=UserWarning, module='sklearn')
warnings.filterwarnings('ignore')
logger = logging.getLogger(__name__)

class MLSignalGenerator:
    """머신러닝 기반 진입 신호 생성기"""
    
    def __init__(self, model_type='random_forest'):
        self.model_type = model_type
        self.model = None
        self.scaler = StandardScaler()
        self.feature_names = []
        self.is_trained = False
        
        # 모델 파일 경로
        self.model_file = f'ml_model_{model_type}.pkl'
        self.scaler_file = 'ml_scaler.pkl'
        
        # 학습 파라미터
        self.lookback_hours = 168  # 1주일
        self.prediction_horizon = 6  # 6시간 후 예측
        self.min_profit_threshold = 0.015  # 1.5% 이상을 성공으로 간주
        
        # 모델 로드 시도
        self._load_model()
    
    def train_model(self, symbols, retrain=False):
        """모델 학습"""
        
        if self.is_trained and not retrain:
            logger.info("이미 학습된 모델이 있습니다.")
            return
        
        logger.info("="*60)
        logger.info("🤖 머신러닝 모델 학습 시작")
        logger.info("="*60)
        
        all_features = []
        all_labels = []
        
        # 각 심볼별 데이터 수집
        for symbol in symbols:
            logger.info(f"데이터 수집 중: {symbol}")
            
            features, labels = self._prepare_training_data(symbol)
            
            if features is not None and len(features) > 0:
                all_features.append(features)
                all_labels.append(labels)
                logger.info(f"  ✅ {symbol}: {len(features)}개 샘플 수집")
            else:
                logger.warning(f"  ⚠️ {symbol}: 데이터 부족")
        
        if not all_features:
            logger.error("학습 데이터가 없습니다!")
            return False
        
        # 데이터 결합
        X = pd.concat(all_features, ignore_index=True)
        y = pd.concat(all_labels, ignore_index=True)
        
        logger.info(f"\n총 학습 데이터: {len(X)}개")
        logger.info(f"긍정 샘플: {y.sum()}개 ({y.mean():.1%})")
        
        # 학습/테스트 분할
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        
        # 스케일링
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        # 모델 학습
        logger.info("\n모델 학습 중...")
        
        if self.model_type == 'random_forest':
            self.model = RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                min_samples_split=20,
                min_samples_leaf=10,
                random_state=42,
                n_jobs=1  # 병렬 처리 비활성화 (경고 방지)
            )
        else:  # gradient_boosting
            self.model = GradientBoostingClassifier(
                n_estimators=100,
                max_depth=5,
                learning_rate=0.1,
                random_state=42
            )
        
        self.model.fit(X_train_scaled, y_train)
        
        # 평가
        train_score = self.model.score(X_train_scaled, y_train)
        test_score = self.model.score(X_test_scaled, y_test)
        
        logger.info(f"\n✅ 학습 완료!")
        logger.info(f"  학습 정확도: {train_score:.1%}")
        logger.info(f"  테스트 정확도: {test_score:.1%}")
        
        # 특성 중요도
        if hasattr(self.model, 'feature_importances_'):
            importance = pd.DataFrame({
                'feature': X.columns,
                'importance': self.model.feature_importances_
            }).sort_values('importance', ascending=False)
            
            logger.info(f"\n주요 특성 (Top 5):")
            for idx, row in importance.head(5).iterrows():
                logger.info(f"  {row['feature']}: {row['importance']:.3f}")
        
        self.feature_names = list(X.columns)
        self.is_trained = True
        
        # 모델 저장
        self._save_model()
        
        logger.info("="*60)
        return True
    
    def _prepare_training_data(self, symbol):
        """학습 데이터 준비"""
        try:
            ticker = f"KRW-{symbol}"
            
            # 과거 데이터 수집 (최대한 많이)
            df = pyupbit.get_ohlcv(ticker, interval="minute60", count=2000)
            
            if df is None or len(df) < 200:
                return None, None
            
            # 특성 생성
            features_df = self._create_features(df)
            
            # 레이블 생성 (미래 수익률)
            future_returns = df['close'].shift(-self.prediction_horizon) / df['close'] - 1
            labels = (future_returns > self.min_profit_threshold).astype(int)
            
            # NaN 제거
            valid_idx = ~(features_df.isna().any(axis=1) | labels.isna())
            
            features_df = features_df[valid_idx]
            labels = labels[valid_idx]
            
            return features_df, labels
            
        except Exception as e:
            logger.error(f"데이터 준비 실패 {symbol}: {e}")
            return None, None
    
    def _create_features(self, df):
        """특성 생성"""
        features = pd.DataFrame(index=df.index)
        
        # 1. 가격 특성
        features['returns_1h'] = df['close'].pct_change(1)
        features['returns_4h'] = df['close'].pct_change(4)
        features['returns_24h'] = df['close'].pct_change(24)
        
        # 2. 이동평균
        for period in [10, 20, 50]:
            features[f'sma_{period}'] = df['close'].rolling(period).mean()
            features[f'price_to_sma_{period}'] = df['close'] / features[f'sma_{period}']
        
        # 3. RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        features['rsi'] = 100 - (100 / (1 + rs))
        
        # 4. MACD
        ema_12 = df['close'].ewm(span=12).mean()
        ema_26 = df['close'].ewm(span=26).mean()
        features['macd'] = ema_12 - ema_26
        features['macd_signal'] = features['macd'].ewm(span=9).mean()
        features['macd_histogram'] = features['macd'] - features['macd_signal']
        
        # 5. 볼린저 밴드
        sma_20 = df['close'].rolling(20).mean()
        std_20 = df['close'].rolling(20).std()
        features['bb_upper'] = sma_20 + (std_20 * 2)
        features['bb_lower'] = sma_20 - (std_20 * 2)
        features['bb_position'] = (df['close'] - features['bb_lower']) / (features['bb_upper'] - features['bb_lower'])
        
        # 6. 변동성
        features['volatility'] = df['close'].pct_change().rolling(20).std()
        features['atr'] = self._calculate_atr(df)
        
        # 7. 볼륨 특성
        features['volume_sma'] = df['volume'].rolling(20).mean()
        features['volume_ratio'] = df['volume'] / features['volume_sma']
        features['volume_change'] = df['volume'].pct_change(1)
        
        # 8. 모멘텀
        features['momentum_10'] = df['close'] / df['close'].shift(10) - 1
        features['momentum_20'] = df['close'] / df['close'].shift(20) - 1
        
        # 9. 캔들 패턴 (간단한 버전)
        features['candle_body'] = (df['close'] - df['open']).abs() / df['open']
        features['candle_upper_shadow'] = (df['high'] - df[['open', 'close']].max(axis=1)) / df['open']
        features['candle_lower_shadow'] = (df[['open', 'close']].min(axis=1) - df['low']) / df['open']
        
        # 10. 시간 특성
        features['hour'] = df.index.hour
        features['day_of_week'] = df.index.dayofweek
        
        return features
    
    def _calculate_atr(self, df, period=14):
        """ATR 계산"""
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = np.max(ranges, axis=1)
        atr = true_range.rolling(period).mean()
        
        return atr / df['close']  # 정규화
    
    def predict(self, symbol):
        """예측 실행"""
        
        if not self.is_trained:
            logger.warning("모델이 학습되지 않았습니다.")
            return None
        
        try:
            ticker = f"KRW-{symbol}"
            
            # 최신 데이터 가져오기
            df = pyupbit.get_ohlcv(ticker, interval="minute60", count=200)
            
            if df is None or len(df) < 100:
                return None
            
            # 특성 생성
            features_df = self._create_features(df)
            
            # 최신 데이터만 사용
            latest_features = features_df.iloc[-1:][self.feature_names]
            
            # NaN 체크
            if latest_features.isna().any().any():
                logger.warning(f"{symbol}: 특성에 NaN 값 존재")
                return None
            
            # 스케일링
            features_scaled = self.scaler.transform(latest_features)
            
            # 예측
            probability = self.model.predict_proba(features_scaled)[0]
            prediction = self.model.predict(features_scaled)[0]
            
            return {
                'symbol': symbol,
                'prediction': bool(prediction),
                'buy_probability': float(probability[1]),
                'confidence': float(max(probability)),
                'timestamp': datetime.now()
            }
            
        except Exception as e:
            logger.error(f"예측 실패 {symbol}: {e}")
            return None
    
    def get_signal(self, symbol, confidence_threshold=0.65):
        """거래 신호 생성"""
        
        prediction = self.predict(symbol)
        
        if not prediction:
            return False, "예측 불가"
        
        if prediction['prediction'] and prediction['buy_probability'] >= confidence_threshold:
            return True, (f"ML 매수 신호 (확률: {prediction['buy_probability']:.1%}, "
                         f"신뢰도: {prediction['confidence']:.1%})")
        
        return False, f"ML 신호 약함 (확률: {prediction['buy_probability']:.1%})"
    
    def _save_model(self):
        """모델 저장"""
        try:
            with open(self.model_file, 'wb') as f:
                pickle.dump({
                    'model': self.model,
                    'feature_names': self.feature_names,
                    'model_type': self.model_type
                }, f)
            
            with open(self.scaler_file, 'wb') as f:
                pickle.dump(self.scaler, f)
            
            logger.info(f"모델 저장 완료: {self.model_file}")
            
        except Exception as e:
            logger.error(f"모델 저장 실패: {e}")
    
    def _load_model(self):
        """모델 로드"""
        try:
            with open(self.model_file, 'rb') as f:
                data = pickle.load(f)
                self.model = data['model']
                self.feature_names = data['feature_names']
                self.model_type = data['model_type']
            
            with open(self.scaler_file, 'rb') as f:
                self.scaler = pickle.load(f)
            
            self.is_trained = True
            logger.info(f"✅ 저장된 모델 로드 성공: {self.model_file}")
            
        except FileNotFoundError:
            logger.info("저장된 모델이 없습니다. 새로 학습이 필요합니다.")
        except Exception as e:
            logger.error(f"모델 로드 실패: {e}")
    
    def evaluate_recent_performance(self, symbols, days=7):
        """최근 성능 평가"""
        
        if not self.is_trained:
            logger.warning("모델이 학습되지 않았습니다.")
            return
        
        logger.info(f"\n{'='*60}")
        logger.info(f"📊 최근 {days}일 모델 성능 평가")
        logger.info(f"{'='*60}")
        
        total_signals = 0
        successful_signals = 0
        
        for symbol in symbols:
            ticker = f"KRW-{symbol}"
            
            try:
                # 최근 데이터
                df = pyupbit.get_ohlcv(ticker, interval="minute60", count=24*days)
                
                if df is None or len(df) < 100:
                    continue
                
                # 특성 생성
                features_df = self._create_features(df)
                
                # 각 시점에서 예측
                for i in range(len(df) - self.prediction_horizon - 50):
                    current_features = features_df.iloc[i:i+1][self.feature_names]
                    
                    if current_features.isna().any().any():
                        continue
                    
                    # 예측
                    features_scaled = self.scaler.transform(current_features)
                    probability = self.model.predict_proba(features_scaled)[0][1]
                    
                    if probability >= 0.65:  # 신호 발생
                        total_signals += 1
                        
                        # 실제 결과 확인
                        future_price = df.iloc[i + self.prediction_horizon]['close']
                        current_price = df.iloc[i]['close']
                        actual_return = (future_price - current_price) / current_price
                        
                        if actual_return > self.min_profit_threshold:
                            successful_signals += 1
                
            except Exception as e:
                logger.error(f"{symbol} 평가 실패: {e}")
                continue
        
        if total_signals > 0:
            success_rate = successful_signals / total_signals
            logger.info(f"\n총 신호: {total_signals}개")
            logger.info(f"성공: {successful_signals}개")
            logger.info(f"성공률: {success_rate:.1%}")
        else:
            logger.info("\n평가 기간 동안 신호 없음")
        
        logger.info(f"{'='*60}\n")