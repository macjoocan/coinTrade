# risk_manager.py 파일 생성 또는 기존 파일에 추가

class RiskManager:
    def __init__(self, initial_balance):
        self.initial_balance = initial_balance
        self.max_position_size = 0.3   # 종목당 최대 30%
        self.stop_loss = 0.02           # 2% 손절
        self.daily_loss_limit = 0.05    # 일일 최대 손실 5%
        
        # 일일 손익 추적
        self.daily_pnl = defaultdict(float)
        self.positions = {}  # {symbol: {'entry_price': x, 'quantity': y, 'value': z}}
        
    def calculate_position_size(self, balance, symbol, current_price, volatility=None):
        """변동성 기반 포지션 크기 계산"""
        # 기본 포지션 크기
        max_value = balance * self.max_position_size
        
        # 변동성 조정 (옵션)
        if volatility:
            # 변동성이 높을수록 포지션 크기 감소
            volatility_multiplier = min(1.0, 0.02 / volatility)  # 2% 기준
            max_value *= volatility_multiplier
        
        # 최소 주문 금액 체크 (업비트는 5,000원)
        if max_value < 5000:
            return 0
            
        quantity = max_value / current_price
        return quantity
    
    def check_stop_loss(self, symbol, current_price):
        """손절 체크"""
        if symbol not in self.positions:
            return False
            
        entry_price = self.positions[symbol]['entry_price']
        loss_rate = (current_price - entry_price) / entry_price
        
        return loss_rate <= -self.stop_loss
    
    def check_daily_loss_limit(self):
        """일일 손실 한도 체크"""
        today = datetime.now().strftime('%Y-%m-%d')
        daily_loss_rate = self.daily_pnl[today] / self.initial_balance
        
        return daily_loss_rate <= -self.daily_loss_limit
    
    def update_position(self, symbol, entry_price, quantity, trade_type):
        """포지션 업데이트"""
        if trade_type == 'buy':
            self.positions[symbol] = {
                'entry_price': entry_price,
                'quantity': quantity,
                'value': entry_price * quantity
            }
        elif trade_type == 'sell' and symbol in self.positions:
            # 손익 계산
            pnl = (entry_price - self.positions[symbol]['entry_price']) * quantity
            today = datetime.now().strftime('%Y-%m-%d')
            self.daily_pnl[today] += pnl
            
            # 포지션 제거
            del self.positions[symbol]
            
    def can_open_new_position(self):
        """새 포지션 오픈 가능 여부"""
        # 일일 손실 한도 체크
        if self.check_daily_loss_limit():
            return False, "일일 손실 한도 도달"
        
        # 최대 포지션 개수 체크 (예: 2개)
        if len(self.positions) >= 2:
            return False, "최대 포지션 수 도달"
            
        return True, "거래 가능"