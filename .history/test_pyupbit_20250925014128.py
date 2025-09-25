# test_pyupbit.py - pyupbit 함수 확인

import pyupbit

print("pyupbit 버전:", pyupbit.__version__)
print("\n사용 가능한 함수들:")
print([x for x in dir(pyupbit) if not x.startswith('_')][:20])

# 올바른 함수 테스트
print("\n=== 함수 테스트 ===")

# 1. 현재가 조회
ticker = "KRW-BTC"
price = pyupbit.get_current_price(ticker)
print(f"1. get_current_price('{ticker}'): {price}")

# 2. 티커 조회 (올바른 방법)
tickers = pyupbit.get_tickers(fiat="KRW")
print(f"2. get_tickers(): {tickers[:5]}...")

# 3. 시장가격 정보
orderbook = pyupbit.get_orderbook(ticker)
print(f"3. get_orderbook('{ticker}'): keys = {list(orderbook[0].keys())[:5]}...")

# 4. OHLCV
ohlcv = pyupbit.get_ohlcv(ticker, count=2)
print(f"4. get_ohlcv('{ticker}'): shape = {ohlcv.shape}")