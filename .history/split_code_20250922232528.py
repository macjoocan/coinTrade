# split_code.py - 현재 코드를 자동으로 분리하는 스크립트

import os
import re

def create_project_structure():
    """프로젝트 구조 생성"""
    directories = [
        'config', 'core', 'strategy', 'risk', 
        'backtest', 'paper_trading', 'bots', 
        'utils', 'data', 'data/logs', 'tests'
    ]
    
    for dir_name in directories:
        os.makedirs(dir_name, exist_ok=True)
        
        # __init__.py 생성
        if not dir_name.startswith('data'):
            init_file = os.path.join(dir_name, '__init__.py')
            if not os.path.exists(init_file):
                with open(init_file, 'w') as f:
                    f.write('# -*- coding: utf-8 -*-\n')

def split_upbit_trader():
    """upbit_trader.py 분리"""
    
    # 1. core/config_manager.py
    config_code = '''
    
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
'''
    
    with open('core/config_manager.py', 'w', encoding='utf-8') as f:
        f.write(config_code)
    
    print("✅ core/config_manager.py 생성 완료")

# 실행
if __name__ == "__main__":
    create_project_structure()
    split_upbit_trader()
    print("프로젝트 구조 생성 완료!")