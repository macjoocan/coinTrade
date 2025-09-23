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