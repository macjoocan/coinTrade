# multi_timeframe_analyzer.py

import pyupbit
import pandas as pd
import numpy as np
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class MultiTimeframeAnalyzer:
    """멀티 타임프레임 분석 모듈"""
    
    def __init__(self):
        self.timeframes = {
            '1h': {'interval': 'minute60', 'weight': 0.3, 'count': 100},
            '4h': {'interval': 'minute240', 'weight': 0.4, 'count': 100},
            '1d': {'interval': 'day', 'weight': 0.3, 'count': 50}
        }
        
        # 합의(confluence) 임계값
        self.consensus_threshold = 0.65  # 65% 이상 일치 시 강한 신호
        
    def analyze(self, symbol):
        """전체 타임프레임 분석"""
        ticker = f"KRW-{symbol}"
        
        timeframe_results = {}
        
        # 각 타임프레임 분석
        for tf_name, tf_config in self.timeframes.items():
            result = self._analyze_timeframe(
                ticker, 
                tf_config['interval'],
                tf_config['count']
            )
            
            if result:
                timeframe_results[tf_name] = result
                logger.debug(f"{symbol} {tf_name}: 점수={result['score']:.1f}, "
                           f"추세={result['trend']}")
        
        if not timeframe_results:
            return None
        
        # 종합 분석
        consensus = self._calculate_consensus(timeframe_results)
        
        return consensus
    
    def _analyze_timeframe(self, ticker, interval, count):
        """개별 타임프레임 분석"""
        try:
            df = pyupbit.get_ohlcv(ticker, interval=interval, count=count)
            
            if df is None or len(df) < 50:
                return None
            
            # 기술적 지표 계산
            indicators = self._calculate_indicators(df)
            
            # 점수 계산
            score = self._calculate_timeframe_score(indicators)
            
            return {
                'score': score,
                'trend': indicators['trend'],
                'strength': indicators['trend_strength'],
                'rsi': indicators['rsi'],
                'macd_signal': indicators['macd_signal'],
                'volume_trend': indicators['volume_trend']
            }
            
        except Exception as e:
            logger.error(f"타임프레임 분석 실패 {ticker} {interval}: {e}")
            return None
    
    def _calculate_indicators(self, df):
        """기술적 지표 계산"""
        # 이동평균선
        df['sma_20'] = df['close'].rolling(window=20).mean()
        df['sma_50'] = df['close'].rolling(window=50).mean()
        df['ema_12'] = df['close'].ewm(span=12).mean()
        df['ema_26'] = df['close'].ewm(span=26).mean()
        
        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # MACD
        df['macd'] = df['ema_12'] - df['ema_26']
        df['macd_signal'] = df['macd'].ewm(span=9).mean()
        df['macd_histogram'] = df['macd'] - df['macd_signal']
        
        # 볼륨 트렌드
        df['volume_sma'] = df['volume'].rolling(window=20).mean()
        
        # 최신 값 추출
        current = df.iloc[-1]
        prev = df.iloc[-2]
        
        # 추세 판단
        trend = self._determine_trend(df)
        trend_strength = self._calculate_trend_strength(df)
        
        # 볼륨 트렌드
        volume_trend = 'increasing' if current['volume'] > current['volume_sma'] else 'decreasing'
        
        return {
            'price': current['close'],
            'sma_20': current['sma_20'],
            'sma_50': current['sma_50'],
            'rsi': current['rsi'],
            'macd': current['macd'],
            'macd_signal': current['macd_signal'],
            'macd_histogram': current['macd_histogram'],
            'trend': trend,
            'trend_strength': trend_strength,
            'volume_trend': volume_trend,
            'volume_ratio': current['volume'] / current['volume_sma']
        }
    
    def _determine_trend(self, df):
        """추세 판단"""
        current = df.iloc[-1]
        
        # 단기/장기 이평선 관계
        sma_20 = current['sma_20']
        sma_50 = current['sma_50']
        price = current['close']
        
        # MACD 확인
        macd_bullish = current['macd'] > current['macd_signal']
        
        if sma_20 > sma_50 and price > sma_20 and macd_bullish:
            return 'strong_uptrend'
        elif sma_20 > sma_50 and price > sma_20:
            return 'uptrend'
        elif sma_20 < sma_50 and price < sma_20:
            return 'downtrend'
        elif sma_20 < sma_50 and price < sma_20 and not macd_bullish:
            return 'strong_downtrend'
        else:
            return 'sideways'
    
    def _calculate_trend_strength(self, df):
        """추세 강도 계산 (0~1)"""
        # ADX 간이 버전 - 최근 20개 봉의 방향성
        closes = df['close'].tail(20)
        
        # 상승/하락 일관성
        price_changes = closes.diff().dropna()
        
        if len(price_changes) == 0:
            return 0.5
        
        # 같은 방향 비율
        positive_days = (price_changes > 0).sum()
        negative_days = (price_changes < 0).sum()
        
        total_days = len(price_changes)
        consistency = max(positive_days, negative_days) / total_days
        
        return consistency
    
    def _calculate_timeframe_score(self, indicators):
        """타임프레임별 점수 계산 (0~10)"""
        score = 0
        
        # 1. 추세 점수 (0~3점)
        trend = indicators['trend']
        if trend == 'strong_uptrend':
            score += 3
        elif trend == 'uptrend':
            score += 2
        elif trend == 'sideways':
            score += 1
        
        # 2. 추세 강도 (0~2점)
        score += indicators['trend_strength'] * 2
        
        # 3. RSI (0~2점)
        rsi = indicators['rsi']
        if 30 < rsi < 40:
            score += 2
        elif 40 < rsi < 50:
            score += 1.5
        elif 50 < rsi < 60:
            score += 1
        
        # 4. MACD (0~2점)
        if indicators['macd'] > indicators['macd_signal']:
            if indicators['macd_histogram'] > 0:
                score += 2
            else:
                score += 1.5
        
        # 5. 볼륨 (0~1점)
        if indicators['volume_trend'] == 'increasing':
            score += 1
        
        return min(score, 10)
    
    def _calculate_consensus(self, timeframe_results):
        """타임프레임 간 합의 계산"""
        
        if not timeframe_results:
            return None
        
        # 가중 평균 점수
        weighted_score = 0
        total_weight = 0
        
        # 추세 방향 카운트
        trend_votes = {'up': 0, 'down': 0, 'sideways': 0}
        
        for tf_name, result in timeframe_results.items():
            weight = self.timeframes[tf_name]['weight']
            
            # 점수 가중합
            weighted_score += result['score'] * weight
            total_weight += weight
            
            # 추세 투표
            if 'uptrend' in result['trend']:
                trend_votes['up'] += weight
            elif 'downtrend' in result['trend']:
                trend_votes['down'] += weight
            else:
                trend_votes['sideways'] += weight
        
        # 최종 점수
        final_score = weighted_score / total_weight if total_weight > 0 else 0
        
        # 합의 수준 계산
        max_trend_vote = max(trend_votes.values())
        consensus_level = max_trend_vote / total_weight if total_weight > 0 else 0
        
        # 주도 추세
        dominant_trend = max(trend_votes, key=trend_votes.get)
        
        # 신호 강도
        signal_strength = self._calculate_signal_strength(
            final_score, 
            consensus_level,
            timeframe_results
        )
        
        return {
            'final_score': final_score,
            'consensus_level': consensus_level,
            'dominant_trend': dominant_trend,
            'signal_strength': signal_strength,
            'is_strong_signal': consensus_level >= self.consensus_threshold,
            'timeframe_details': timeframe_results
        }
    
    def _calculate_signal_strength(self, score, consensus, tf_results):
        """신호 강도 계산 (weak/moderate/strong)"""
        
        # 모든 타임프레임이 일치하는가?
        all_aligned = consensus >= 0.8
        
        # 점수가 높은가?
        high_score = score >= 7.0
        
        # 장기 타임프레임(1d)이 동의하는가?
        if '1d' in tf_results:
            daily_agrees = tf_results['1d']['score'] >= 6.0
        else:
            daily_agrees = False
        
        if all_aligned and high_score and daily_agrees:
            return 'strong'
        elif consensus >= self.consensus_threshold and score >= 6.0:
            return 'moderate'
        else:
            return 'weak'
    
    def get_entry_recommendation(self, symbol):
        """진입 추천 여부"""
        analysis = self.analyze(symbol)
        
        if not analysis:
            return False, "분석 실패"
        
        # 강한 신호만 추천
        if analysis['is_strong_signal'] and analysis['signal_strength'] in ['strong', 'moderate']:
            return True, (f"MTF 신호 강함 (점수: {analysis['final_score']:.1f}, "
                         f"합의: {analysis['consensus_level']:.1%}, "
                         f"강도: {analysis['signal_strength']})")
        
        return False, (f"MTF 신호 약함 (점수: {analysis['final_score']:.1f}, "
                      f"합의: {analysis['consensus_level']:.1%})")
    
    def print_analysis(self, symbol):
        """분석 결과 출력 (디버깅용)"""
        analysis = self.analyze(symbol)
        
        if not analysis:
            print(f"{symbol}: 분석 불가")
            return
        
        print(f"\n{'='*60}")
        print(f"🔍 {symbol} 멀티 타임프레임 분석")
        print(f"{'='*60}")
        print(f"최종 점수: {analysis['final_score']:.1f}/10")
        print(f"합의 수준: {analysis['consensus_level']:.1%}")
        print(f"주도 추세: {analysis['dominant_trend']}")
        print(f"신호 강도: {analysis['signal_strength']}")
        print(f"강한 신호: {'✅ YES' if analysis['is_strong_signal'] else '❌ NO'}")
        
        print(f"\n📊 타임프레임별 상세:")
        for tf_name, result in analysis['timeframe_details'].items():
            print(f"  {tf_name:3s}: 점수={result['score']:.1f}, "
                  f"추세={result['trend']}, "
                  f"RSI={result['rsi']:.1f}")
        print(f"{'='*60}\n")