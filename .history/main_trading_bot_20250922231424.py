# main_trading_bot.py 또는 기존 봇 파일 수정

import pyupbit
from improved_strategy import ImprovedStrategy
from risk_manager import RiskManager

class TradingBot:
    def __init__(self, access_key, secret_key):
        self.upbit = pyupbit.Upbit(access_key, secret_key)
        self.balance = self.get_balance()
        
        # 전략 및 리스크 매니저 초기화
        self.strategy = ImprovedStrategy()
        self.risk_manager = RiskManager(self.balance)
        
    def get_balance(self):
        """KRW 잔고 조회"""
        balances = self.upbit.get_balances()
        for b in balances:
            if b['currency'] == 'KRW':
                return float(b['balance'])
        return 0
    
    def execute_trade(self, symbol, trade_type, current_price):
        """거래 실행 (개선된 로직 적용)"""
        
        # 1. 거래 빈도 체크
        if not self.strategy.can_trade_today():
            print(f"일일 거래 한도 초과")
            return False
            
        # 2. 매도의 경우 최소 보유시간 체크
        if trade_type == 'sell':
            if not self.strategy.can_exit_position(symbol):
                print(f"{symbol}: 최소 보유시간 미충족")
                return False
                
        # 3. 매수의 경우 리스크 체크
        if trade_type == 'buy':
            can_trade, reason = self.risk_manager.can_open_new_position()
            if not can_trade:
                print(f"거래 불가: {reason}")
                return False
                
            # 포지션 크기 계산
            quantity = self.risk_manager.calculate_position_size(
                self.balance, symbol, current_price
            )
            
            if quantity == 0:
                print("포지션 크기가 너무 작음")
                return False
                
            # 실제 매수 실행
            order = self.upbit.buy_market_order(f"KRW-{symbol}", current_price * quantity)
            
            if order:
                self.strategy.record_trade(symbol, 'buy')
                self.risk_manager.update_position(symbol, current_price, quantity, 'buy')
                print(f"매수 완료: {symbol} @ {current_price}")
                return True
                
        elif trade_type == 'sell':
            # 손절 체크
            if self.risk_manager.check_stop_loss(symbol, current_price):
                print(f"{symbol}: 손절 실행")
                
            # 실제 매도 실행
            # (기존 포지션 수량 조회 로직 필요)
            quantity = self.get_position_quantity(symbol)
            order = self.upbit.sell_market_order(f"KRW-{symbol}", quantity)
            
            if order:
                self.strategy.record_trade(symbol, 'sell')
                self.risk_manager.update_position(symbol, current_price, quantity, 'sell')
                print(f"매도 완료: {symbol} @ {current_price}")
                return True
                
        return False
    
    def check_positions_for_stop_loss(self):
        """모든 포지션 손절 체크"""
        for symbol in list(self.risk_manager.positions.keys()):
            ticker = f"KRW-{symbol}"
            current_price = pyupbit.get_current_price(ticker)
            
            if self.risk_manager.check_stop_loss(symbol, current_price):
                self.execute_trade(symbol, 'sell', current_price)
    
    def run(self):
        """메인 실행 루프"""
        while True:
            try:
                # 일일 손실 한도 체크
                if self.risk_manager.check_daily_loss_limit():
                    print("일일 손실 한도 도달. 거래 중단.")
                    time.sleep(3600)  # 1시간 대기
                    continue
                
                # 손절 체크
                self.check_positions_for_stop_loss()
                
                # 기존 전략 로직 실행
                # ... (RSI, MACD 등 기술적 지표 기반 거래 로직)
                
                time.sleep(60)  # 1분마다 체크
                
            except Exception as e:
                print(f"에러 발생: {e}")
                time.sleep(60)