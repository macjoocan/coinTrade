# main.py - 모든 기능을 통합한 메인 파일

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Upbit Trading Bot - Main Entry Point
"""

import sys
import argparse
from datetime import datetime

# 모듈 임포트
from core.config_manager import Config
from core.trader import UpbitTrader
from risk.risk_manager import RiskManager
from strategy.advanced_strategy import AdvancedTradingStrategy
from backtest.backtest_engine import BacktestEngine
from paper_trading.simulator import PaperTradingSimulator
from bots.main_trading_bot import TradingBot

def main():
    """메인 실행 함수"""
    parser = argparse.ArgumentParser(description='Upbit Trading Bot')
    parser.add_argument('--mode', choices=['backtest', 'paper', 'live'], 
                       default='paper', help='실행 모드')
    parser.add_argument('--market', default='KRW-ETH', 
                       help='거래할 마켓')
    parser.add_argument('--duration', type=int, default=30,
                       help='실행 시간 (분)')
    parser.add_argument('--config', default='config/config.json',
                       help='설정 파일 경로')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print(f"Upbit Trading Bot - {args.mode.upper()} Mode")
    print(f"Market: {args.market}")
    print(f"Started at: {datetime.now()}")
    print("=" * 60)
    
    # 설정 로드
    config = Config(args.config)
    
    if args.mode == 'backtest':
        run_backtest(config, args.market)
    elif args.mode == 'paper':
        run_paper_trading(config, args.market, args.duration)
    elif args.mode == 'live':
        run_live_trading(config, args.market)
    else:
        print(f"Unknown mode: {args.mode}")
        sys.exit(1)

def run_backtest(config, market):
    """백테스팅 실행"""
    from strategy.advanced_strategy import AdvancedTradingStrategy
    
    trader = UpbitTrader(config)
    risk_manager = RiskManager(config)
    strategy = AdvancedTradingStrategy(trader, risk_manager)
    
    # 데이터 수집
    df = trader.get_historical_data(market, days=100)
    if df.empty:
        print("데이터 수집 실패")
        return
    
    # 백테스트 실행
    backtest, df_signals = strategy.backtest_strategy(df)
    
    # 결과 출력
    metrics = backtest.get_performance_metrics()
    for key, value in metrics.items():
        print(f"{key}: {value}")

def run_paper_trading(config, market, duration):
    """페이퍼 트레이딩 실행"""
    markets = [market] if ',' not in market else market.split(',')
    simulator = PaperTradingSimulator(markets, 
                                     config.trading_params['initial_capital'])
    simulator.run_simulation(duration_minutes=duration, interval_seconds=30)

def run_live_trading(config, market):
    """실제 거래 실행"""
    if not config.access_key or not config.secret_key:
        print("❌ API 키가 설정되지 않았습니다!")
        return
    
    confirm = input("⚠️  실제 자금으로 거래가 실행됩니다. 계속하시겠습니까? (yes/no): ")
    if confirm.lower() != 'yes':
        print("거래 취소")
        return
    
    bot = TradingBot(config.access_key, config.secret_key)
    bot.run()

if __name__ == "__main__":
    main()