# check_pyupbit.py - 정확한 함수 확인

import pyupbit

print("pyupbit 버전:", pyupbit.__version__)

# orderbook 올바른 사용법
ticker = "KRW-BTC"
orderbook = pyupbit.get_orderbook(ticker)

print("\norderbook 타입:", type(orderbook))
if isinstance(orderbook, list):
    print("orderbook은 리스트입니다")
    if len(orderbook) > 0:
        print("첫 번째 요소 타입:", type(orderbook[0]))
        print("키들:", list(orderbook[0].keys())[:10])
elif isinstance(orderbook, dict):
    print("orderbook은 딕셔너리입니다")
    print("키들:", list(orderbook.keys())[:10])

# 일봉 데이터로 변동률 계산
df = pyupbit.get_ohlcv(ticker, interval="day", count=2)
if len(df) >= 2:
    yesterday_close = df['close'].iloc[-2]
    today_close = df['close'].iloc[-1]
    change_rate = ((today_close - yesterday_close) / yesterday_close) * 100
    print(f"\n변동률 계산: {change_rate:.2f}%")