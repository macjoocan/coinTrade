"""
Paper Trading 시뮬레이터
실제 돈을 사용하지 않고 실시간 데이터로 거래 시뮬레이션
"""

import sys
import os
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List
import pandas as pd

# 메인 모듈 import
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from upbit_trader import *

class PaperTradingAccount:
    """가상 계좌 관리"""
    
    def __init__(self, initial_krw=1000000, initial_holdings=None):
        self.initial_krw = initial_krw
        self.krw_balance = initial_krw
        self.holdings = initial_holdings or {}  # {'BTC': 0.001, 'ETH': 0.1}
        self.trade_history = []
        self.order_history = []
        
    def buy(self, symbol: str, krw_amount: float, price: float, fee_rate=0.0005):
        """매수 시뮬레이션"""
        if krw_amount > self.krw_balance:
            return {'error': '잔고 부족', 'available': self.krw_balance}
        
        fee = krw_amount * fee_rate
        net_amount = krw_amount - fee
        quantity = net_amount / price
        
        # 잔고 업데이트
        self.krw_balance -= krw_amount
        if symbol in self.holdings:
            self.holdings[symbol] += quantity
        else:
            self.holdings[symbol] = quantity
        
        # 거래 기록
        trade = {
            'timestamp': datetime.now(),
            'type': 'buy',
            'symbol': symbol,
            'price': price,
            'quantity': quantity,
            'krw_amount': krw_amount,
            'fee': fee,
            'balance_after': self.krw_balance
        }
        self.trade_history.append(trade)
        
        return {
            'success': True,
            'trade': trade,
            'message': f"매수 완료: {quantity:.8f} {symbol} @ {price:,.0f} KRW"
        }
    
    def sell(self, symbol: str, quantity: float, price: float, fee_rate=0.0005):
        """매도 시뮬레이션"""
        if symbol not in self.holdings or self.holdings[symbol] < quantity:
            return {'error': '보유 수량 부족', 'available': self.holdings.get(symbol, 0)}
        
        krw_amount = quantity * price
        fee = krw_amount * fee_rate
        net_amount = krw_amount - fee
        
        # 잔고 업데이트
        self.holdings[symbol] -= quantity
        if self.holdings[symbol] == 0:
            del self.holdings[symbol]
        self.krw_balance += net_amount
        
        # 거래 기록
        trade = {
            'timestamp': datetime.now(),
            'type': 'sell',
            'symbol': symbol,
            'price': price,
            'quantity': quantity,
            'krw_amount': krw_amount,
            'fee': fee,
            'balance_after': self.krw_balance
        }
        self.trade_history.append(trade)
        
        return {
            'success': True,
            'trade': trade,
            'message': f"매도 완료: {quantity:.8f} {symbol} @ {price:,.0f} KRW"
        }
    
    def get_portfolio_value(self, current_prices: Dict[str, float]) -> float:
        """총 포트폴리오 가치 계산"""
        total_value = self.krw_balance
        
        for symbol, quantity in self.holdings.items():
            if symbol in current_prices:
                total_value += quantity * current_prices[symbol]
        
        return total_value
    
    def get_performance(self, current_prices: Dict[str, float]) -> Dict:
        """성과 분석"""
        current_value = self.get_portfolio_value(current_prices)
        total_return = (current_value - self.initial_krw) / self.initial_krw * 100
        
        # 거래 통계
        total_trades = len(self.trade_history)
        buy_trades = [t for t in self.trade_history if t['type'] == 'buy']
        sell_trades = [t for t in self.trade_history if t['type'] == 'sell']
        
        # 수수료 총액
        total_fees = sum(t['fee'] for t in self.trade_history)
        
        return {
            'total_value': current_value,
            'total_return_pct': total_return,
            'total_trades': total_trades,
            'buy_trades': len(buy_trades),
            'sell_trades': len(sell_trades),
            'total_fees': total_fees,
            'krw_balance': self.krw_balance,
            'holdings': self.holdings
        }

class PaperTradingSimulator:
    """Paper Trading 시뮬레이터"""
    
    def __init__(self, markets: List[str], initial_capital=1000000):
        # 설정
        self.config = self._create_config()
        self.markets = markets
        
        # 컴포넌트 초기화
        self.trader = UpbitTrader(self.config)
        self.risk_manager = RiskManager(self.config)
        self.strategies = {}
        
        # 각 마켓별 전략 생성
        for market in markets:
            self.strategies[market] = AdvancedTradingStrategy(
                self.trader, 
                self.risk_manager
            )
        
        # 가상 계좌
        self.account = PaperTradingAccount(initial_capital)
        
        # 포지션 추적
        self.positions = {}  # {market: {'type': 'long', 'entry_price': 50000000, ...}}
        
        # 로깅
        self.log_file = f"paper_trading_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        # 세션 재사용 추가
        self.trader.session = requests.Session()

        # 연결 재사용 비활성화
        self.trader.session.keep_alive = False  # 연결 재사용 비활성화
        
    def _create_config(self):
        """설정 생성"""
        class Config:
            def __init__(self):
                self.access_key = ""
                self.secret_key = ""
                self.trading_params = {
                    'initial_capital': 1000000,
                    'max_position_size': 0.2,
                    'commission': 0.0005
                }
                self.risk_params = {
                    'stop_loss_pct': 0.02,
                    'take_profit_pct': 0.04,
                    'max_daily_loss': 0.02,
                    'risk_per_trade': 0.02
                }
        
        return Config()
    
    def analyze_market(self, market: str) -> Dict:
        """시장 분석"""
        try:
            # 15분봉 데이터로 변경
            candles = self.trader.get_candles(market, interval='minutes', unit=15, count=200)
            
            if not candles:
                return {'error': '데이터 수집 실패'}
            
            # DataFrame 변환
            df = pd.DataFrame(candles)
            df['candle_date_time_kst'] = pd.to_datetime(df['candle_date_time_kst'])
            df = df.sort_values('candle_date_time_kst').reset_index(drop=True)
            
            # 컬럼명 정리
            df = df[['candle_date_time_kst', 'opening_price', 'high_price', 
                    'low_price', 'trade_price', 'candle_acc_trade_volume']]
            df.columns = ['date', 'open', 'high', 'low', 'close', 'volume']
            
            if df.empty:
                return {'error': '데이터 수집 실패'}
            
            # 지표 계산
            strategy = self.strategies[market]
            df = strategy.calculate_indicators(df)
            df = strategy.generate_signals(df)
            
            # 최신 데이터
            latest = df.iloc[-1]
            
            # 현재가 조회
            ticker = self.trader.get_ticker(market)
            current_price = float(ticker['trade_price'])
            
            if 'DOGE' in market:
                # DOGE는 변동성이 높으므로 타이트하게
                self.risk_manager.stop_loss_pct = 0.015
            elif 'ETH' in market:
                # ETH는 안정적이므로 여유있게
                self.risk_manager.stop_loss_pct = 0.025
        
            return {
                'market': market,
                'current_price': current_price,
                'signal': latest['signal'],
                'position_size': latest.get('position_size', 0),
                'rsi': latest['rsi'],
                'trend': 'up' if latest['sma_20'] > latest['sma_50'] else 'down',
                'bb_position': (latest['close'] - latest['bb_lower']) / 
                            (latest['bb_upper'] - latest['bb_lower']),
                'volume_ratio': latest['volume'] / df['volume'].mean()
            }
            
        except Exception as e:
            logger.error(f"시장 분석 실패 {market}: {e}")
            return {'error': str(e)}
    
    def check_positions(self, current_prices: Dict[str, float]):
        """포지션 체크 (손절/익절)"""
        # 딕셔너리 복사본으로 순회
        positions_to_check = list(self.positions.items())
        
        for market, position in positions_to_check:
            if market not in current_prices:
                continue
            
            current_price = current_prices[market]
            entry_price = position['entry_price']
            position_type = position['type']
            
            # 손절 체크
            if self.risk_manager.check_stop_loss(
                entry_price, current_price, 
                PositionType.LONG if position_type == 'long' else PositionType.SHORT
            ):
                print(f"⚠️ {market} 손절매 신호!")
                self.execute_trade(market, 'sell', current_price)
            
            # 익절 체크
            elif self.risk_manager.check_take_profit(
                entry_price, current_price,
                PositionType.LONG if position_type == 'long' else PositionType.SHORT
            ):
                print(f"✅ {market} 익절매 신호!")
                self.execute_trade(market, 'sell', current_price)
    
    def execute_trade(self, market: str, signal: str, price: float):
        if signal == 'buy':
            # 자본 보호: 잔고가 초기 자본의 20% 미만이면 거래 중지
            if self.account.krw_balance < self.account.initial_krw * 0.2:
                print("⚠️ 자본 보호 모드: 잔여 자금 20% 미만")
                return
        
        """거래 실행"""
        symbol = market.split('-')[1]
        
        if signal == 'buy':
            
            # 포지션 수 제한 추가
            MAX_POSITIONS = 3
            if len(self.positions) >= MAX_POSITIONS:
                return  # 3개 이상 보유 시 추가 매수 금지
        
            # 이미 포지션이 있으면 스킵
            if market in self.positions:
                return
            
            # 매수 금액 계산 (자본의 20%)
            buy_amount = self.account.krw_balance * 0.2
            
            if buy_amount < 5000:  # 최소 주문 금액
                return
            
            result = self.account.buy(symbol, buy_amount, price)
            
            if result.get('success'):
                self.positions[market] = {
                    'type': 'long',
                    'entry_price': price,
                    'quantity': result['trade']['quantity'],
                    'entry_time': datetime.now()
                }
                print(f"🟢 {result['message']}")
        
        elif signal == 'sell':
            # 포지션이 없으면 스킵
            if market not in self.positions:
                return
            
            position = self.positions[market]
            result = self.account.sell(symbol, position['quantity'], price)
            
            if result.get('success'):
                # PnL 계산
                pnl = (price - position['entry_price']) * position['quantity']
                pnl_pct = (price - position['entry_price']) / position['entry_price'] * 100
                
                print(f"🔴 {result['message']}")
                print(f"   PnL: {pnl:+,.0f} KRW ({pnl_pct:+.2f}%)")
                
                del self.positions[market]
    
    def run_simulation(self, duration_minutes=60, interval_seconds=30):
        """시뮬레이션 실행"""
        print("🚀 Paper Trading 시작")
        print(f"초기 자본: {self.account.initial_krw:,.0f} KRW")
        print(f"거래 마켓: {', '.join(self.markets)}")
        print(f"실행 시간: {duration_minutes}분")
        print(f"체크 간격: {interval_seconds}초")
        print("=" * 60)
        
        start_time = datetime.now()
        end_time = start_time + timedelta(minutes=duration_minutes)
        consecutive_errors = 0
        
        try:
            while datetime.now() < end_time:
                try:
                # 기존 코드...
                    consecutive_errors = 0  # 성공 시 리셋
                except Exception as e:
                    consecutive_errors += 1
                    print(f"오류 발생 ({consecutive_errors}회): {e}")
                    if consecutive_errors > 5:
                        print("연속 오류 5회 초과 - 시뮬레이션 중단")
                        break
                    time.sleep(interval_seconds * 2)  # 대기 시간 증가                
                
                print(f"\n⏰ {datetime.now().strftime('%H:%M:%S')}")
                
                # 현재가 수집
                current_prices = {}
                for market in self.markets:
                    try:
                        ticker = self.trader.get_ticker(market)
                        if ticker:
                            current_prices[market] = float(ticker['trade_price'])
                            symbol = market.split('-')[1]
                            current_prices[symbol] = current_prices[market]
                        consecutive_errors = 0  # 성공 시 리셋
                    except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError) as e:
                        print(f"⚠️ 네트워크 타임아웃: {market}")
                        consecutive_errors += 1
                        if consecutive_errors > 5:
                            print("연속 에러 5회 초과 - 잠시 대기")
                            time.sleep(30)
                        continue  # 다음 마켓으로
                    except Exception as e:
                        print(f"❌ 오류: {market} - {e}")
                        continue
                
                # 포트폴리오 가치
                portfolio_value = self.account.get_portfolio_value(current_prices)
                print(f"💼 포트폴리오: {portfolio_value:,.0f} KRW "
                      f"({(portfolio_value/self.account.initial_krw-1)*100:+.2f}%)")
                
                # 포지션 체크 (손절/익절)
                self.check_positions(current_prices)
                
                # 각 마켓 분석
                for market in self.markets:
                    analysis = self.analyze_market(market)
                    
                    if 'error' not in analysis:
                        print(f"\n📊 {market}:")
                        print(f"   가격: {analysis['current_price']:,.0f} KRW")
                        print(f"   신호: {analysis['signal']}")
                        print(f"   RSI: {analysis['rsi']:.2f}")
                        print(f"   트렌드: {analysis['trend']}")
                        
                        # 매매 신호 처리
                        if analysis['signal'] in ['buy', 'sell']:
                            self.execute_trade(
                                market, 
                                analysis['signal'], 
                                analysis['current_price']
                            )
                
                # 현재 포지션 상태
                if self.positions:
                    print("\n📍 보유 포지션:")
                    for market, pos in self.positions.items():
                        current = current_prices.get(market, pos['entry_price'])
                        pnl_pct = (current - pos['entry_price']) / pos['entry_price'] * 100
                        print(f"   {market}: {pnl_pct:+.2f}%")
                
                # 로그 저장
                self.save_log()
                
                # 대기
                print(f"\n다음 체크까지 {interval_seconds}초 대기...")
                time.sleep(interval_seconds)
                
        except KeyboardInterrupt:
            print("\n\n⛔ 시뮬레이션 중단")
        
        finally:
            # 최종 결과
            self.print_final_results(current_prices)
    
    def save_log(self):
        """로그 저장"""
        log_data = {
            'timestamp': datetime.now().isoformat(),
            'account': {
                'krw_balance': self.account.krw_balance,
                'holdings': self.account.holdings
            },
            'positions': self.positions,
            'trades': [
                {
                    'timestamp': t['timestamp'].isoformat(),
                    'type': t['type'],
                    'symbol': t['symbol'],
                    'price': t['price'],
                    'quantity': t['quantity'],
                    'fee': t['fee']
                }
                for t in self.account.trade_history
            ]
        }
        
        with open(self.log_file, 'w') as f:
            json.dump(log_data, f, indent=2, default=str)  # ← default=str 추가
    
    def print_final_results(self, current_prices: Dict[str, float]):
        """최종 결과 출력"""
        print("\n" + "=" * 60)
        print("📊 Paper Trading 최종 결과")
        print("=" * 60)
        
        # 가격 조회 실패 시 처리
        if not current_prices:
            print("⚠️ 가격 조회 실패 - 네트워크 오류")
            # 마지막 알려진 가격 사용
            for market in self.markets:
                try:
                    ticker = self.trader.get_ticker(market)
                    if ticker:
                        symbol = market.split('-')[1]
                        current_prices[symbol] = float(ticker['trade_price'])
                except:
                    print(f"❌ {market} 가격 조회 실패")
                    continue
        
        # 가격이 여전히 없으면 기본값 사용
        if not current_prices:
            print("⚠️ 모든 가격 조회 실패")
            return

        # 네트워크 오류 시 재시도
        max_retries = 3
        for retry in range(max_retries):
            try:
                for market in self.markets:
                    ticker = self.trader.get_ticker(market)
                    if ticker:
                        symbol = market.split('-')[1]
                        current_prices[symbol] = float(ticker['trade_price'])
                break
            except Exception as e:
                print(f"가격 조회 실패 (시도 {retry+1}/{max_retries}): {e}")
                time.sleep(2)
                if retry == max_retries - 1:
                    print("⚠️ 최종 가격을 조회할 수 없어 마지막 거래 가격 사용")
                    # 포지션 entry_price 사용
                    for market, pos in self.positions.items():
                        symbol = market.split('-')[1]
                        current_prices[symbol] = pos['entry_price']
        
        performance = self.account.get_performance(current_prices)
        
        print(f"초기 자본: {self.account.initial_krw:,.0f} KRW")
        print(f"최종 가치: {performance['total_value']:,.0f} KRW")
        print(f"총 수익률: {performance['total_return_pct']:+.2f}%")
        print(f"\n총 거래: {performance['total_trades']}회")
        print(f"  - 매수: {performance['buy_trades']}회")
        print(f"  - 매도: {performance['sell_trades']}회")
        print(f"총 수수료: {performance['total_fees']:,.0f} KRW")
        
        if performance['holdings']:
            print(f"\n보유 자산:")
            for symbol, quantity in performance['holdings'].items():
                value = quantity * current_prices.get(symbol, 0)
                print(f"  {symbol}: {quantity:.8f} ({value:,.0f} KRW)")
        
        # 거래 내역 요약
        if self.account.trade_history:
            print(f"\n최근 거래 5개:")
            for trade in self.account.trade_history[-5:]:
                print(f"  [{trade['timestamp'].strftime('%H:%M:%S')}] "
                      f"{trade['type'].upper()} {trade['symbol']} "
                      f"@ {trade['price']:,.0f}")
        
        print(f"\n로그 파일: {self.log_file}")

def main():
    """메인 실행"""
    print("=" * 60)
    print("Paper Trading 시뮬레이터")
    print("실제 돈을 사용하지 않는 모의 거래")
    print("=" * 60)
    
    # 설정
    # markets = ["KRW-BTC", "KRW-ETH", "KRW-XRP", "KRW-DOGE", "KRW-SOL"]
    markets = ["KRW-ETH", "KRW-XRP", "KRW-DOGE", "KRW-SOL"]  # BTC 제외
    initial_capital = 1000000  # 초기 자본
    
    # 시뮬레이터 생성
    simulator = PaperTradingSimulator(markets, initial_capital)
    
    # 실행 옵션
    print("\n실행 옵션:")
    print("1. 빠른 테스트 (5분)")
    print("2. 표준 테스트 (30분)")
    print("3. 장시간 테스트 (60분)")
    print("4. 커스텀 설정")
    
    choice = input("\n선택 (1-4): ") or "1"
    
    if choice == "1":
        duration = 5
        interval = 30
    elif choice == "2":
        duration = 30
        interval = 30
    elif choice == "3":
        duration = 60
        interval = 60
    elif choice == "4":
        duration = int(input("실행 시간 (분): ") or "10")
        interval = int(input("체크 간격 (초): ") or "30")
    else:
        duration = 5
        interval = 10
    
    # 시뮬레이션 실행
    simulator.run_simulation(duration, interval)

if __name__ == "__main__":
    main()