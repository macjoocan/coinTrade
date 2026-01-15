# slippage_manager.py - 슬리피지 관리 및 보호 시스템

import logging
import pyupbit
from datetime import datetime, timedelta
from collections import deque

logger = logging.getLogger(__name__)

class SlippageManager:
    """
    슬리피지 관리자
    - 시장가 주문 시 예상 슬리피지 계산
    - 과도한 슬리피지 방지
    - 실제 슬리피지 추적 및 통계
    """

    def __init__(self):
        # 슬리피지 기록 (최근 100건)
        self.slippage_history = deque(maxlen=100)

        # 코인별 평균 슬리피지
        self.symbol_slippage = {}

        # 설정
        self.max_slippage_rate = 0.003  # 최대 허용 슬리피지 0.3%
        self.min_orderbook_depth = 5    # 최소 호가 깊이 체크

        logger.info("✅ SlippageManager 초기화 완료")
        logger.info(f"   최대 허용 슬리피지: {self.max_slippage_rate:.2%}")

    def estimate_slippage(self, ticker, order_type, order_amount):
        """
        예상 슬리피지 계산

        Args:
            ticker: KRW-BTC 형식의 티커
            order_type: 'buy' or 'sell'
            order_amount: 주문 금액 (KRW)

        Returns:
            (is_safe, estimated_slippage_rate, message)
        """
        try:
            # 호가 정보 조회
            orderbook = pyupbit.get_orderbook(ticker)

            if not orderbook:
                return False, 0, "호가 정보 조회 실패"

            # 매수/매도 호가 선택
            if order_type == 'buy':
                asks = orderbook['orderbook_units']
                prices = [item['ask_price'] for item in asks]
                sizes = [item['ask_size'] for item in asks]
            else:  # sell
                bids = orderbook['orderbook_units']
                prices = [item['bid_price'] for item in bids]
                sizes = [item['bid_size'] for item in bids]

            if not prices or not sizes:
                return False, 0, "호가 데이터 없음"

            # 현재가 (중간값)
            current_price = pyupbit.get_current_price(ticker)
            if not current_price:
                return False, 0, "현재가 조회 실패"

            # 1. 호가 깊이 체크
            if len(prices) < self.min_orderbook_depth:
                return False, 0, f"호가 깊이 부족 ({len(prices)}/{self.min_orderbook_depth})"

            # 2. 예상 체결가 계산
            remaining_amount = order_amount
            total_cost = 0
            total_quantity = 0

            for price, size in zip(prices, sizes):
                available_value = price * size

                if remaining_amount <= available_value:
                    # 이 호가에서 주문 완료
                    qty = remaining_amount / price
                    total_cost += remaining_amount
                    total_quantity += qty
                    break
                else:
                    # 이 호가 전부 소진
                    total_cost += available_value
                    total_quantity += size
                    remaining_amount -= available_value

            if total_quantity == 0:
                return False, 0, "호가 유동성 부족"

            # 평균 체결가
            avg_fill_price = total_cost / total_quantity

            # 슬리피지율 계산
            if order_type == 'buy':
                slippage_rate = (avg_fill_price - current_price) / current_price
            else:
                slippage_rate = (current_price - avg_fill_price) / current_price

            # 3. 허용 범위 체크
            is_safe = slippage_rate <= self.max_slippage_rate

            if is_safe:
                message = f"안전 (예상 슬리피지: {slippage_rate:.3%})"
            else:
                message = f"⚠️ 슬리피지 과다 (예상: {slippage_rate:.3%} > 한도: {self.max_slippage_rate:.2%})"

            return is_safe, slippage_rate, message

        except Exception as e:
            logger.error(f"슬리피지 추정 실패: {e}")
            return False, 0, f"오류: {str(e)}"

    def record_actual_slippage(self, symbol, expected_price, actual_price, order_type, order_amount):
        """
        실제 슬리피지 기록

        Args:
            symbol: 심볼 (예: BTC)
            expected_price: 예상 체결가 (현재가)
            actual_price: 실제 체결가
            order_type: 'buy' or 'sell'
            order_amount: 주문 금액 (KRW)
        """
        if expected_price == 0:
            return

        # 슬리피지율 계산
        if order_type == 'buy':
            slippage_rate = (actual_price - expected_price) / expected_price
        else:
            slippage_rate = (expected_price - actual_price) / expected_price

        # 기록 저장
        record = {
            'timestamp': datetime.now(),
            'symbol': symbol,
            'order_type': order_type,
            'expected_price': expected_price,
            'actual_price': actual_price,
            'slippage_rate': slippage_rate,
            'order_amount': order_amount
        }

        self.slippage_history.append(record)

        # 심볼별 평균 업데이트
        if symbol not in self.symbol_slippage:
            self.symbol_slippage[symbol] = []

        self.symbol_slippage[symbol].append(slippage_rate)

        # 최근 20건만 유지
        if len(self.symbol_slippage[symbol]) > 20:
            self.symbol_slippage[symbol].pop(0)

        # 로그 출력
        if abs(slippage_rate) > 0.001:  # 0.1% 이상만 출력
            logger.info(f"📊 {symbol} 슬리피지: {slippage_rate:+.3%}")
            logger.info(f"   예상가: {expected_price:,.0f} → 실제: {actual_price:,.0f}")

    def get_statistics(self, symbol=None):
        """
        슬리피지 통계 조회

        Args:
            symbol: 특정 심볼 (None이면 전체)

        Returns:
            dict: 통계 정보
        """
        if symbol and symbol in self.symbol_slippage:
            data = self.symbol_slippage[symbol]
        elif symbol:
            return None
        else:
            data = [r['slippage_rate'] for r in self.slippage_history]

        if not data:
            return None

        import numpy as np

        return {
            'count': len(data),
            'avg_slippage': np.mean(data),
            'max_slippage': np.max(data),
            'min_slippage': np.min(data),
            'std_slippage': np.std(data)
        }

    def should_use_limit_order(self, ticker, order_type, order_amount):
        """
        지정가 주문 사용 권장 여부

        Args:
            ticker: KRW-BTC
            order_type: 'buy' or 'sell'
            order_amount: 주문 금액

        Returns:
            (should_use_limit, reason)
        """
        # 슬리피지 추정
        is_safe, slippage_rate, message = self.estimate_slippage(
            ticker, order_type, order_amount
        )

        if not is_safe:
            return True, f"슬리피지 과다로 지정가 권장 ({message})"

        # 대량 주문 체크
        current_price = pyupbit.get_current_price(ticker)
        if current_price:
            order_ratio = order_amount / (current_price * 1000000)  # 1백만 코인 대비
            if order_ratio > 0.01:  # 1% 이상
                return True, f"대량 주문으로 지정가 권장 (비율: {order_ratio:.2%})"

        # 심볼별 과거 슬리피지 체크
        symbol = ticker.replace('KRW-', '')
        stats = self.get_statistics(symbol)

        if stats and stats['avg_slippage'] > 0.002:  # 평균 0.2% 이상
            return True, f"과거 슬리피지 높음 (평균: {stats['avg_slippage']:.3%})"

        return False, "시장가 주문 안전"

    def adjust_order_for_slippage(self, order_amount, slippage_rate):
        """
        슬리피지 고려한 주문 금액 조정

        Args:
            order_amount: 원래 주문 금액
            slippage_rate: 예상 슬리피지율

        Returns:
            adjusted_amount: 조정된 주문 금액
        """
        # 슬리피지만큼 금액 축소 (매수 시)
        # 예: 100,000원 주문, 슬리피지 0.3% → 99,700원으로 조정
        adjusted_amount = order_amount * (1 - slippage_rate)

        return max(adjusted_amount, 5500)  # 최소 주문 금액 보장

    def print_statistics(self):
        """슬리피지 통계 출력"""
        if not self.slippage_history:
            logger.info("📊 슬리피지 기록 없음")
            return

        logger.info("")
        logger.info("="*60)
        logger.info("📊 슬리피지 통계")
        logger.info("="*60)

        stats = self.get_statistics()
        if stats:
            logger.info(f"총 거래 수: {stats['count']}회")
            logger.info(f"평균 슬리피지: {stats['avg_slippage']:+.3%}")
            logger.info(f"최대 슬리피지: {stats['max_slippage']:+.3%}")
            logger.info(f"최소 슬리피지: {stats['min_slippage']:+.3%}")
            logger.info(f"표준편차: {stats['std_slippage']:.3%}")

        logger.info("")
        logger.info("코인별 평균 슬리피지:")
        for symbol, rates in self.symbol_slippage.items():
            if rates:
                avg = sum(rates) / len(rates)
                logger.info(f"  {symbol}: {avg:+.3%} (거래: {len(rates)}회)")

        logger.info("="*60)
        logger.info("")
