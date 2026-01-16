import pyupbit
import os
from dotenv import load_dotenv

load_dotenv()

upbit = pyupbit.Upbit(os.getenv('UPBIT_ACCESS_KEY'), os.getenv('UPBIT_SECRET_KEY'))
balances = upbit.get_balances()

print("=" * 60)
print("현재 보유 코인")
print("=" * 60)

has_coins = False
for b in balances:
    if b['currency'] != 'KRW' and float(b['balance']) > 0:
        has_coins = True
        print(f"{b['currency']}: {b['balance']}")

if not has_coins:
    print("보유 코인 없음")

print("=" * 60)
