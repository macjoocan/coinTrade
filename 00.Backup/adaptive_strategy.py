# adaptive_strategy.py (새 파일)
class AdaptiveStrategy:
    """시장 상황에 따라 자동 조정되는 전략"""
    
    def analyze_market_trend(self):
        """최근 24시간 시장 전체 트렌드"""
        btc_change = self.get_24h_change('BTC')
        
        if btc_change < -3:
            return 'bear_market'
        elif btc_change > 3:
            return 'bull_market'
        else:
            return 'neutral'
    
    def adjust_parameters(self, market_trend):
        """시장에 따른 파라미터 조정"""
        if market_trend == 'bear_market':
            return {
                'entry_threshold': 7,     # 엄격
                'stop_loss': 0.01,        # 타이트
                'position_size': 0.15     # 축소
            }
        elif market_trend == 'bull_market':
            return {
                'entry_threshold': 5,      # 완화
                'stop_loss': 0.02,        # 여유
                'position_size': 0.3      # 확대
            }
        else:
            return {
                'entry_threshold': 6,
                'stop_loss': 0.015,
                'position_size': 0.25
            }