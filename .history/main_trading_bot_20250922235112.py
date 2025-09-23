# main_trading_bot.py

import pyupbit
import time
import logging
from datetime import datetime
from improved_strategy import ImprovedStrategy
from risk_manager import RiskManager
from config import TRADING_PAIRS

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

class TradingBot:
    def __init__(self, access_key, secret_key):
        self.upbit = pyupbit.Upbit(access_key, secret_key)
        self.balance = self.get_balance()
        
        # 전략 및 리스크 매니저 초기화
        self.strategy = ImprovedStrategy()
        self.risk_manager = RiskManager(self.balance)
        
        logger.info(f"봇 초기화 완료. 초기 자본: {self.balance:,.0f} KRW")
        
    def get_balance(self):
        """KRW 잔고 조회"""
        try:
            balances = self.upbit.get_balances()
            for b in balances:
                if b['currency'] == 'KRW':
                    return float(b['balance'])
        except Exception as e:
            logger.error(f"잔고 조회 실패: {e}")
        return 0
    
    def get_position_quantity(self, symbol):
        """보유 수량 조회"""
        try:
            balances = self.upbit.get_balances()
            for b in balances:
                if b['currency'] == symbol:
                    return float(b['balance'])
        except Exception as e:
            logger.error(f"포지션 조회 실패: {e}")
        return 0
    
    def calculate_indicators(self, ticker):
        """기술적 지표 계산"""
        try:
            # RSI
            rsi = pyupbit.get_current_price(ticker)  # 실제로는 RSI 계산 로직 필요
            
            # 이동평균선
            df = pyupbit.get_ohlcv(ticker, interval="minute60", count=50)
            if df is not None and len(df) > 20:
                sma_20 = df['close'].rolling(window=20).mean().iloc[-1]
                current_price = df['close'].iloc[-1]
                
                return {
                    'current_price': current_price,
                    'sma_20': sma_20,
                    'trend': 'up' if current_price > sma_20 else 'down'
                }
        except Exception as e:
            logger.error(f"지표 계산 실패: {e}")
        
        return None
    
    def execute_trade(self, symbol, trade_type, current_price=None):
        """거래 실행 (개선된 로직 적용)"""
        ticker = f"KRW-{symbol}"
        
        # 현재가 조회
        if current_price is None:
            current_price = pyupbit.get_current_price(ticker)
            if current_price is None:
                logger.error(f"현재가 조회 실패: {ticker}")
                return False
        
        # 1. 거래 빈도 체크
        if not self.strategy.can_trade_today():
            logger.info("일일 거래 한도 초과")
            return False
            
        # 2. 매도의 경우 최소 보유시간 체크
        if trade_type == 'sell':
            if not self.strategy.can_exit_position(symbol):
                logger.info(f"{symbol}: 최소 보유시간 미충족")
                return False
                
        # 3. 매수의 경우 리스크 체크
        if trade_type == 'buy':
            can_trade, reason = self.risk_manager.can_open_new_position()
            if not can_trade:
                logger.info(f"거래 불가: {reason}")
                return False
                
            # 포지션 크기 계산
            self.balance = self.get_balance()  # 잔고 업데이트
            quantity = self.risk_manager.calculate_position_size(
                self.balance, symbol, current_price
            )
            
            if quantity == 0:
                logger.info("포지션 크기가 너무 작음")
                return False
            
            # 주문 금액 계산
            order_amount = current_price * quantity
            
            # 실제 매수 실행
            try:
                order = self.upbit.buy_market_order(ticker, order_amount)
                if order:
                    self.strategy.record_trade(symbol, 'buy')
                    self.risk_manager.update_position(symbol, current_price, quantity, 'buy')
                    logger.info(f"매수 완료: {symbol} @ {current_price:,.0f}")
                    return True
            except Exception as e:
                logger.error(f"매수 실패: {e}")
                
        elif trade_type == 'sell':
            # 손절 체크
            if self.risk_manager.check_stop_loss(symbol, current_price):
                logger.info(f"{symbol}: 손절 실행")
                
            # 보유 수량 조회
            quantity = self.get_position_quantity(symbol)
            if quantity == 0:
                logger.info(f"{symbol}: 보유 수량 없음")
                return False
            
            # 실제 매도 실행
            try:
                order = self.upbit.sell_market_order(ticker, quantity)
                if order:
                    self.strategy.record_trade(symbol, 'sell')
                    self.risk_manager.update_position(symbol, current_price, quantity, 'sell')
                    logger.info(f"매도 완료: {symbol} @ {current_price:,.0f}")
                    return True
            except Exception as e:
                logger.error(f"매도 실패: {e}")
                
        return False
    
    def check_positions_for_stop_loss(self):
        """모든 포지션 손절 체크"""
        for symbol in list(self.risk_manager.positions.keys()):
            ticker = f"KRW-{symbol}"
            current_price = pyupbit.get_current_price(ticker)
            
            if current_price and self.risk_manager.check_stop_loss(symbol, current_price):
                self.execute_trade(symbol, 'sell', current_price)
    
    def analyze_and_trade(self):
        """시장 분석 및 거래 실행"""
        for symbol in TRADING_PAIRS:
            ticker = f"KRW-{symbol}"
            
            try:
                # 지표 계산
                indicators = self.calculate_indicators(ticker)
                if not indicators:
                    continue
                
                current_price = indicators['current_price']
                
                # 기존 포지션 체크
                position = self.risk_manager.get_position_info(symbol)
                
                if position:
                    # 매도 조건 체크
                    entry_price = position['entry_price']
                    
                    # 수익 목표 달성 시 매도
                    if self.strategy.check_profit_target(entry_price, current_price):
                        logger.info(f"{symbol}: 목표 수익률 달성")
                        self.execute_trade(symbol, 'sell', current_price)
                    
                    # 손절 체크
                    elif self.risk_manager.check_stop_loss(symbol, current_price):
                        logger.info(f"{symbol}: 손절선 도달")
                        self.execute_trade(symbol, 'sell', current_price)
                        
                else:
                    # 매수 조건 체크 (예시: 상승 추세일 때)
                    if indicators['trend'] == 'up':
                        # 추가 조건 체크 가능
                        self.execute_trade(symbol, 'buy', current_price)
                        
            except Exception as e:
                logger.error(f"{symbol} 분석 실패: {e}")
                continue
    
    def run(self):
        """메인 실행 루프"""
        logger.info("트레이딩 봇 시작")
        
        while True:
            try:
                # 일일 손실 한도 체크
                if self.risk_manager.check_daily_loss_limit():
                    logger.warning("일일 손실 한도 도달. 거래 중단.")
                    time.sleep(3600)  # 1시간 대기
                    continue
                
                # 손절 체크
                self.check_positions_for_stop_loss()
                
                # 시장 분석 및 거래
                self.analyze_and_trade()
                
                # 대기
                time.sleep(60)  # 1분마다 체크
                
                # 매일 자정 리셋
                if datetime.now().hour == 0 and datetime.now().minute == 0:
                    self.risk_manager.reset_daily_stats()
                    logger.info("일일 통계 리셋")
                
            except Exception as e:
                logger.error(f"에러 발생: {e}")
                time.sleep(60)

# 실행 스크립트
if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    
    # 환경변수 로드
    load_dotenv()
    
    access_key = os.getenv('UPBIT_ACCESS_KEY')
    secret_key = os.getenv('UPBIT_SECRET_KEY')
    
    if not access_key or not secret_key:
        print("API 키를 설정해주세요.")
        print("1. .env 파일 생성")
        print("2. UPBIT_ACCESS_KEY=your_key")
        print("3. UPBIT_SECRET_KEY=your_secret")
        exit(1)
    
    # 봇 실행
    bot = TradingBot(access_key, secret_key)
    
    print("=" * 60)
    print("업비트 자동매매 봇 v2.0")
    print(f"초기 자본: {bot.balance:,.0f} KRW")
    print(f"거래 대상: {', '.join(TRADING_PAIRS)}")
    print("=" * 60)
    
    confirm = input("\n실제 거래를 시작하시겠습니까? (yes/no): ")
    if confirm.lower() == 'yes':
        bot.run()
    else:
        print("거래 취소")