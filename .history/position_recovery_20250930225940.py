import json
import pyupbit
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class PositionRecovery:
    """봇 재시작 시 포지션 복구"""
    
    def __init__(self, upbit):
        self.upbit = upbit
        self.position_file = "active_positions.json"
        
    def save_positions(self, positions):
        """현재 포지션을 파일에 저장"""
        try:
            data = {
                'timestamp': datetime.now().isoformat(),
                'positions': {}
            }
            
            for symbol, pos in positions.items():
                data['positions'][symbol] = {
                    'entry_price': pos['entry_price'],
                    'quantity': pos['quantity'],
                    'entry_time': pos['entry_time'].isoformat() if hasattr(pos['entry_time'], 'isoformat') else str(pos['entry_time'])
                }
            
            with open(self.position_file, 'w') as f:
                json.dump(data, f, indent=2)
                
            logger.info(f"포지션 저장 완료: {len(positions)}개")
            
        except Exception as e:
            logger.error(f"포지션 저장 실패: {e}")
    
    def load_positions(self):
        """저장된 포지션 로드"""
        try:
            with open(self.position_file, 'r') as f:
                data = json.load(f)
                
            logger.info(f"저장된 포지션 파일 발견: {data['timestamp']}")
            return data['positions']
            
        except FileNotFoundError:
            logger.info("저장된 포지션 없음")
            return {}
        except Exception as e:
            logger.error(f"포지션 로드 실패: {e}")
            return {}
    
    def sync_with_exchange(self, saved_positions):
        """거래소 잔고와 동기화"""
        
        # 실제 보유 잔고 조회
        actual_balances = {}
        try:
            balances = self.upbit.get_balances()
            
            for balance in balances:
                if balance['currency'] != 'KRW':
                    actual_balances[balance['currency']] = {
                        'balance': float(balance['balance']),
                        'avg_buy_price': float(balance['avg_buy_price'])
                    }
        except Exception as e:
            logger.error(f"잔고 조회 실패: {e}")
            return {}
        
        # 저장된 포지션과 실제 잔고 비교
        recovered_positions = {}
        
        for symbol, actual in actual_balances.items():
            if actual['balance'] > 0:
                if symbol in saved_positions:
                    # 저장된 포지션 정보 사용
                    recovered_positions[symbol] = {
                        'entry_price': saved_positions[symbol]['entry_price'],
                        'quantity': actual['balance'],
                        'entry_time': saved_positions[symbol]['entry_time']
                    }
                    logger.info(f"포지션 복구: {symbol} - 저장된 정보 사용")
                else:
                    # 새로 발견된 포지션 (평균 매수가 사용)
                    recovered_positions[symbol] = {
                        'entry_price': actual['avg_buy_price'],
                        'quantity': actual['balance'],
                        'entry_time': datetime.now().isoformat()
                    }
                    logger.warning(f"새 포지션 발견: {symbol} - 평균 매수가 사용")
        
        return recovered_positions