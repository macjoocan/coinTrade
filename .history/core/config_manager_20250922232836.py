import os
import json
import logging

logger = logging.getLogger(__name__)

class Config:
    """설정 관리 클래스"""
    def __init__(self, config_file='config/config.json'):
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
                    'stop_loss_pct': 0.02,
                    'take_profit_pct': 0.03,
                    'max_daily_loss': 0.02,
                    'risk_per_trade': 0.02
                }
                
        except Exception as e:
            logger.error(f"설정 로드 실패: {e}")
            raise
