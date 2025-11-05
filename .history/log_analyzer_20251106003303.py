"""
Trading Log Analyzer
trading.log 파일을 분석하여 최적의 설정값을 제안합니다.
"""

import re
import json
from datetime import datetime
from collections import defaultdict
from typing import List, Dict, Tuple
import pyupbit
import pandas as pd
import numpy as np
from dataclasses import dataclass


@dataclass
class Trade:
    """거래 정보"""
    timestamp: datetime
    action: str  # BUY, SELL
    symbol: str
    price: float
    quantity: float
    amount: float
    reason: str = ""
    score: float = 0.0
    market_condition: str = ""


@dataclass
class TradeResult:
    """거래 결과"""
    symbol: str
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    quantity: float
    profit_loss: float
    profit_rate: float
    hold_duration: float  # hours
    entry_score: float
    market_condition: str
    exit_reason: str


class LogAnalyzer:
    def __init__(self, log_file: str = "trading.log"):
        self.log_file = log_file
        self.trades: List[Trade] = []
        self.trade_results: List[TradeResult] = []
        self.open_positions: Dict[str, Trade] = {}
        
    def parse_log(self):
        """로그 파일 파싱"""
        print("📄 로그 파일 파싱 중...")
        
        with open(self.log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        for line in lines:
            try:
                # 매수 로그 파싱
                if "매수 체결" in line or "BUY order filled" in line:
                    trade = self._parse_buy_log(line)
                    if trade:
                        self.trades.append(trade)
                        self.open_positions[trade.symbol] = trade
                
                # 매도 로그 파싱
                elif "매도 체결" in line or "SELL order filled" in line:
                    trade = self._parse_sell_log(line)
                    if trade:
                        self.trades.append(trade)
                        # 포지션 청산 → 결과 계산
                        if trade.symbol in self.open_positions:
                            result = self._calculate_result(
                                self.open_positions[trade.symbol],
                                trade
                            )
                            self.trade_results.append(result)
                            del self.open_positions[trade.symbol]
                            
            except Exception as e:
                continue
        
        print(f"✅ 총 {len(self.trades)}개 거래 파싱 완료")
        print(f"✅ 총 {len(self.trade_results)}개 완료된 거래 분석")
        
    def _parse_buy_log(self, line: str) -> Trade:
        """매수 로그 파싱"""
        try:
            # 타임스탬프 추출
            timestamp_match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
            timestamp = datetime.strptime(timestamp_match.group(1), '%Y-%m-%d %H:%M:%S')
            
            # 심볼 추출 (KRW-XXX 형태)
            symbol_match = re.search(r'KRW-([A-Z0-9]+)', line)
            symbol = f"KRW-{symbol_match.group(1)}" if symbol_match else ""
            
            # 가격, 수량, 금액 추출
            price_match = re.search(r'가격[:\s]+([0-9,.]+)', line)
            quantity_match = re.search(r'수량[:\s]+([0-9.]+)', line)
            amount_match = re.search(r'금액[:\s]+([0-9,.]+)', line)
            
            # 점수 추출
            score_match = re.search(r'점수[:\s]+([0-9.]+)', line)
            score = float(score_match.group(1)) if score_match else 0.0
            
            # 시장 상황 추출
            market_match = re.search(r'시장[:\s]+(BULLISH|BEARISH|NEUTRAL)', line)
            market = market_match.group(1) if market_match else "UNKNOWN"
            
            return Trade(
                timestamp=timestamp,
                action="BUY",
                symbol=symbol,
                price=float(price_match.group(1).replace(',', '')) if price_match else 0.0,
                quantity=float(quantity_match.group(1)) if quantity_match else 0.0,
                amount=float(amount_match.group(1).replace(',', '')) if amount_match else 0.0,
                score=score,
                market_condition=market
            )
        except Exception as e:
            return None
    
    def _parse_sell_log(self, line: str) -> Trade:
        """매도 로그 파싱"""
        try:
            timestamp_match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
            timestamp = datetime.strptime(timestamp_match.group(1), '%Y-%m-%d %H:%M:%S')
            
            symbol_match = re.search(r'KRW-([A-Z0-9]+)', line)
            symbol = f"KRW-{symbol_match.group(1)}" if symbol_match else ""
            
            price_match = re.search(r'가격[:\s]+([0-9,.]+)', line)
            quantity_match = re.search(r'수량[:\s]+([0-9.]+)', line)
            amount_match = re.search(r'금액[:\s]+([0-9,.]+)', line)
            
            # 청산 이유 추출
            reason = ""
            if "익절" in line or "take_profit" in line:
                reason = "TAKE_PROFIT"
            elif "손절" in line or "stop_loss" in line:
                reason = "STOP_LOSS"
            elif "추적" in line or "trailing" in line:
                reason = "TRAILING_STOP"
            
            return Trade(
                timestamp=timestamp,
                action="SELL",
                symbol=symbol,
                price=float(price_match.group(1).replace(',', '')) if price_match else 0.0,
                quantity=float(quantity_match.group(1)) if quantity_match else 0.0,
                amount=float(amount_match.group(1).replace(',', '')) if amount_match else 0.0,
                reason=reason
            )
        except Exception as e:
            return None
    
    def _calculate_result(self, buy_trade: Trade, sell_trade: Trade) -> TradeResult:
        """거래 결과 계산"""
        profit_loss = sell_trade.amount - buy_trade.amount
        profit_rate = (sell_trade.price - buy_trade.price) / buy_trade.price
        hold_duration = (sell_trade.timestamp - buy_trade.timestamp).total_seconds() / 3600
        
        return TradeResult(
            symbol=buy_trade.symbol,
            entry_time=buy_trade.timestamp,
            exit_time=sell_trade.timestamp,
            entry_price=buy_trade.price,
            exit_price=sell_trade.price,
            quantity=buy_trade.quantity,
            profit_loss=profit_loss,
            profit_rate=profit_rate,
            hold_duration=hold_duration,
            entry_score=buy_trade.score,
            market_condition=buy_trade.market_condition,
            exit_reason=sell_trade.reason
        )
    
    def analyze_results(self):
        """거래 결과 분석"""
        print("\n" + "="*60)
        print("📊 거래 결과 분석")
        print("="*60)
        
        if not self.trade_results:
            print("⚠️  분석할 거래 결과가 없습니다.")
            return
        
        df = pd.DataFrame([{
            'symbol': r.symbol,
            'entry_time': r.entry_time,
            'exit_time': r.exit_time,
            'entry_price': r.entry_price,
            'exit_price': r.exit_price,
            'profit_loss': r.profit_loss,
            'profit_rate': r.profit_rate * 100,
            'hold_duration': r.hold_duration,
            'entry_score': r.entry_score,
            'market_condition': r.market_condition,
            'exit_reason': r.exit_reason
        } for r in self.trade_results])
        
        # 기본 통계
        total_trades = len(df)
        winning_trades = len(df[df['profit_rate'] > 0])
        losing_trades = len(df[df['profit_rate'] < 0])
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        total_profit = df['profit_loss'].sum()
        avg_profit = df[df['profit_rate'] > 0]['profit_rate'].mean()
        avg_loss = df[df['profit_rate'] < 0]['profit_rate'].mean()
        
        print(f"\n📈 기본 통계:")
        print(f"   총 거래: {total_trades}회")
        print(f"   승리: {winning_trades}회 ({win_rate:.1f}%)")
        print(f"   패배: {losing_trades}회 ({100-win_rate:.1f}%)")
        print(f"   총 손익: {total_profit:,.0f}원")
        print(f"   평균 수익률: {avg_profit:.2f}%")
        print(f"   평균 손실률: {avg_loss:.2f}%")
        print(f"   평균 보유 시간: {df['hold_duration'].mean():.1f}시간")
        
        # 진입 점수별 분석
        print(f"\n📊 진입 점수별 승률:")
        score_bins = [0, 6.5, 7.0, 7.5, 8.0, 8.5, 9.0, 10.0]
        df['score_range'] = pd.cut(df['entry_score'], bins=score_bins)
        score_analysis = df.groupby('score_range').agg({
            'profit_rate': ['count', lambda x: (x > 0).sum(), 'mean']
        })
        score_analysis.columns = ['거래수', '승리', '평균수익률']
        score_analysis['승률(%)'] = (score_analysis['승리'] / score_analysis['거래수'] * 100).round(1)
        print(score_analysis)
        
        # 시장 상황별 분석
        print(f"\n🌍 시장 상황별 분석:")
        market_analysis = df.groupby('market_condition').agg({
            'profit_rate': ['count', lambda x: (x > 0).sum(), 'mean']
        })
        market_analysis.columns = ['거래수', '승리', '평균수익률(%)']
        market_analysis['승률(%)'] = (market_analysis['승리'] / market_analysis['거래수'] * 100).round(1)
        print(market_analysis)
        
        # 청산 이유별 분석
        print(f"\n🎯 청산 이유별 분석:")
        exit_analysis = df.groupby('exit_reason').agg({
            'profit_rate': ['count', 'mean']
        })
        exit_analysis.columns = ['거래수', '평균수익률(%)']
        print(exit_analysis)
        
        return df
    
    def fetch_market_data(self, symbol: str, start_date: datetime, end_date: datetime):
        """업비트에서 과거 시장 데이터 가져오기"""
        try:
            # 일봉 데이터
            df = pyupbit.get_ohlcv(symbol, interval="day", count=200)
            if df is None or df.empty:
                return None
            
            # 시작/종료 날짜 범위 필터링
            df = df.loc[start_date:end_date]
            
            return df
        except Exception as e:
            print(f"⚠️  {symbol} 데이터 가져오기 실패: {e}")
            return None
    
    def backtest_with_params(self, entry_threshold: float, stop_loss: float, 
                            take_profit: float, market_adjustments: Dict[str, float]):
        """특정 파라미터로 백테스팅"""
        results = []
        
        for result in self.trade_results:
            # 새로운 진입 기준 적용
            adjusted_threshold = entry_threshold + market_adjustments.get(result.market_condition, 0)
            
            # 진입했을까?
            if result.entry_score < adjusted_threshold:
                continue  # 진입 안함
            
            # 청산 가격 시뮬레이션
            max_profit_rate = result.profit_rate  # 실제 최대 도달 수익률
            
            # 익절 먼저 체크
            if max_profit_rate >= take_profit:
                simulated_profit_rate = take_profit
                exit_type = "TAKE_PROFIT"
            # 손절 체크
            elif max_profit_rate <= -stop_loss:
                simulated_profit_rate = -stop_loss
                exit_type = "STOP_LOSS"
            # 그 외
            else:
                simulated_profit_rate = max_profit_rate
                exit_type = "OTHER"
            
            results.append({
                'symbol': result.symbol,
                'profit_rate': simulated_profit_rate,
                'exit_type': exit_type,
                'market': result.market_condition
            })
        
        # 결과 계산
        if not results:
            return None
        
        df = pd.DataFrame(results)
        total_trades = len(df)
        winning = len(df[df['profit_rate'] > 0])
        win_rate = winning / total_trades * 100 if total_trades > 0 else 0
        avg_profit = df['profit_rate'].mean()
        
        return {
            'entry_threshold': entry_threshold,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'market_adjustments': market_adjustments,
            'total_trades': total_trades,
            'win_rate': win_rate,
            'avg_profit': avg_profit,
            'total_profit': df['profit_rate'].sum()
        }
    
    def optimize_parameters(self):
        """최적 파라미터 탐색"""
        print("\n" + "="*60)
        print("🔍 최적 파라미터 탐색 중...")
        print("="*60)
        
        # 탐색 범위
        entry_thresholds = [6.5, 7.0, 7.5, 8.0, 8.5]
        stop_losses = [0.01, 0.015, 0.02, 0.025, 0.03]  # 1% ~ 3%
        take_profits = [0.015, 0.02, 0.025, 0.03, 0.04]  # 1.5% ~ 4%
        
        # 시장 상황별 조정값 패턴
        market_adjustment_patterns = [
            {'BULLISH': -1.0, 'NEUTRAL': 0.0, 'BEARISH': +1.5},  # 보수적
            {'BULLISH': -1.5, 'NEUTRAL': 0.0, 'BEARISH': +1.0},  # 중간
            {'BULLISH': -2.0, 'NEUTRAL': 0.0, 'BEARISH': +0.5},  # 공격적
        ]
        
        best_result = None
        best_score = float('-inf')
        all_results = []
        
        total_combinations = len(entry_thresholds) * len(stop_losses) * len(take_profits) * len(market_adjustment_patterns)
        print(f"총 {total_combinations}개 조합 테스트 중...\n")
        
        count = 0
        for entry_th in entry_thresholds:
            for sl in stop_losses:
                for tp in take_profits:
                    # 손익비 체크 (최소 1:2)
                    if tp < sl * 1.5:
                        continue
                    
                    for market_adj in market_adjustment_patterns:
                        count += 1
                        result = self.backtest_with_params(entry_th, sl, tp, market_adj)
                        
                        if result and result['total_trades'] >= 5:  # 최소 5개 거래
                            # 점수 계산: 승률 40% + 평균수익 40% + 총수익 20%
                            score = (
                                result['win_rate'] * 0.4 +
                                result['avg_profit'] * 100 * 0.4 +
                                result['total_profit'] * 100 * 0.2
                            )
                            result['score'] = score
                            all_results.append(result)
                            
                            if score > best_score:
                                best_score = score
                                best_result = result
                        
                        if count % 20 == 0:
                            print(f"진행: {count}/{total_combinations} ({count/total_combinations*100:.1f}%)")
        
        print(f"\n✅ 탐색 완료!")
        
        # 상위 5개 결과
        all_results.sort(key=lambda x: x['score'], reverse=True)
        
        print("\n" + "="*60)
        print("🏆 최적 파라미터 TOP 5")
        print("="*60)
        
        for i, result in enumerate(all_results[:5], 1):
            print(f"\n[{i}위] 점수: {result['score']:.2f}")
            print(f"   진입 점수: {result['entry_threshold']}")
            print(f"   손절: {result['stop_loss']*100:.1f}%")
            print(f"   익절: {result['take_profit']*100:.1f}%")
            print(f"   손익비: 1:{result['take_profit']/result['stop_loss']:.1f}")
            print(f"   시장 조정: {result['market_adjustments']}")
            print(f"   총 거래: {result['total_trades']}회")
            print(f"   승률: {result['win_rate']:.1f}%")
            print(f"   평균 수익률: {result['avg_profit']*100:.2f}%")
            print(f"   누적 수익률: {result['total_profit']*100:.2f}%")
        
        return all_results[:5]
    
    def generate_config(self, optimal_params: Dict):
        """최적 파라미터로 config.py 생성"""
        config_template = f'''"""
자동 생성된 최적 설정값
생성 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""

# 진입 점수 기준
ENTRY_SCORE_THRESHOLD = {optimal_params['entry_threshold']}

# 손절/익절
STOP_LOSS = {optimal_params['stop_loss']}
MIN_PROFIT_TARGET = {optimal_params['take_profit']}
PROFIT_TARGET_RATIO = {optimal_params['take_profit']/optimal_params['stop_loss']:.1f}

# 시장 상황별 조정값
MARKET_ADJUSTMENTS = {{
    'bullish': {optimal_params['market_adjustments']['BULLISH']},
    'bearish': {optimal_params['market_adjustments']['BEARISH']},
    'neutral': {optimal_params['market_adjustments']['NEUTRAL']}
}}

# 통계
# 예상 승률: {optimal_params['win_rate']:.1f}%
# 평균 수익률: {optimal_params['avg_profit']*100:.2f}%
# 총 거래 수: {optimal_params['total_trades']}회
'''
        
        with open('/home/claude/optimized_config.py', 'w', encoding='utf-8') as f:
            f.write(config_template)
        
        print("\n✅ 최적 설정 파일 생성: optimized_config.py")


def main():
    print("="*60)
    print("🤖 Trading Log Analyzer")
    print("="*60)
    
    # 로그 파일 경로 입력
    log_file = input("\n로그 파일 경로를 입력하세요 (기본: trading.log): ").strip()
    if not log_file:
        log_file = "trading.log"
    
    analyzer = LogAnalyzer(log_file)
    
    # 1단계: 로그 파싱
    analyzer.parse_log()
    
    # 2단계: 거래 결과 분석
    df = analyzer.analyze_results()
    
    if df is None or df.empty:
        print("\n❌ 분석할 데이터가 없습니다.")
        return
    
    # 3단계: 최적 파라미터 탐색
    proceed = input("\n최적 파라미터 탐색을 시작할까요? (y/n): ").strip().lower()
    if proceed == 'y':
        top_results = analyzer.optimize_parameters()
        
        if top_results:
            # 4단계: 설정 파일 생성
            generate = input("\n최적 설정으로 config 파일을 생성할까요? (y/n): ").strip().lower()
            if generate == 'y':
                analyzer.generate_config(top_results[0])
    
    print("\n" + "="*60)
    print("✅ 분석 완료!")
    print("="*60)


if __name__ == "__main__":
    main()