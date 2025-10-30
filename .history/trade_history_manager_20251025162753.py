# trade_history_manager.py
import json
import os
from datetime import datetime, timedelta
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)

class TradeHistoryManager:
    """거래 기록 관리 - Dashboard용 데이터 제공"""
    
    def __init__(self, filename='trade_history.json'):
        self.filename = filename
        # ✅ 초기화 시에는 빈 리스트로 시작 (매번 로드할 것이므로)
        self.trades = []
    
    def _load_history(self):
        """기존 거래 기록 로드"""
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"거래 기록 로드 실패: {e}")
                return []
        return []
    
    def _save_history(self):
        """거래 기록 저장"""
        try:
            with open(self.filename, 'w', encoding='utf-8') as f:
                json.dump(self.trades, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"거래 기록 저장 실패: {e}")
    
    def add_trade(self, trade_data):
        """
        새 거래 추가
        
        Args:
            trade_data: {
                'timestamp': '2025-01-15 14:30:00',
                'symbol': 'BTC',
                'type': 'sell',
                'entry_price': 50000000,
                'exit_price': 51000000,
                'quantity': 0.001,
                'pnl': 1000,
                'pnl_rate': 0.02,
                'fee': 50,
                'hold_time_hours': 2.5
            }
        """
        if isinstance(trade_data['timestamp'], datetime):
            trade_data['timestamp'] = trade_data['timestamp'].isoformat()
        
        # ✅ 최신 데이터 로드 후 추가
        self.trades = self._load_history()
        self.trades.append(trade_data)
        self._save_history()
        
        logger.info(f"거래 기록 추가: {trade_data['symbol']} "
                   f"PnL: {trade_data['pnl']:+,.0f}")
    
    def get_period_stats(self, days):
        """
        기간별 통계 계산
        
        Args:
            days: 1(24h), 7(7d), 30(30d)
        
        Returns:
            dict: 통계 정보
        """
        # ✅ 매번 최신 데이터 로드
        self.trades = self._load_history()
        
        now = datetime.now()
        cutoff = now - timedelta(days=days)
        
        # 기간 내 거래 필터링
        period_trades = [
            t for t in self.trades
            if datetime.fromisoformat(t['timestamp']) > cutoff
        ]
        
        if not period_trades:
            return self._empty_stats()
        
        # 통계 계산
        wins = [t for t in period_trades if t['pnl'] > 0]
        losses = [t for t in period_trades if t['pnl'] <= 0]
        
        total_pnl = sum(t['pnl'] for t in period_trades)
        total_fee = sum(t.get('fee', 0) for t in period_trades)
        
        stats = {
            'total_pnl': total_pnl,
            'net_pnl': total_pnl - total_fee,
            'total_fee': total_fee,
            'trade_count': len(period_trades),
            'win_count': len(wins),
            'loss_count': len(losses),
            'win_rate': (len(wins) / len(period_trades) * 100) if period_trades else 0,
            'avg_win': sum(t['pnl'] for t in wins) / len(wins) if wins else 0,
            'avg_loss': abs(sum(t['pnl'] for t in losses) / len(losses)) if losses else 0,
            'max_win': max(t['pnl'] for t in wins) if wins else 0,
            'max_loss': min(t['pnl'] for t in losses) if losses else 0,
            'avg_hold_time': sum(t.get('hold_time_hours', 0) for t in period_trades) / len(period_trades),
            'best_symbol': self._get_best_symbol(period_trades),
            'worst_symbol': self._get_worst_symbol(period_trades)
        }
        
        # Profit Factor 계산
        total_wins = sum(t['pnl'] for t in wins) if wins else 0
        total_losses = abs(sum(t['pnl'] for t in losses)) if losses else 1
        stats['profit_factor'] = total_wins / total_losses if total_losses > 0 else 0
        
        return stats
    
    def _empty_stats(self):
        """빈 통계 반환"""
        return {
            'total_pnl': 0,
            'net_pnl': 0,
            'total_fee': 0,
            'trade_count': 0,
            'win_count': 0,
            'loss_count': 0,
            'win_rate': 0,
            'avg_win': 0,
            'avg_loss': 0,
            'max_win': 0,
            'max_loss': 0,
            'avg_hold_time': 0,
            'profit_factor': 0,
            'best_symbol': '-',
            'worst_symbol': '-'
        }
    
    def _get_best_symbol(self, trades):
        """최고 수익 종목"""
        by_symbol = defaultdict(float)
        for t in trades:
            by_symbol[t['symbol']] += t['pnl']
        
        if by_symbol:
            best = max(by_symbol.items(), key=lambda x: x[1])
            return f"{best[0]} (+{best[1]:,.0f})"
        return '-'
    
    def _get_worst_symbol(self, trades):
        """최악 손실 종목"""
        by_symbol = defaultdict(float)
        for t in trades:
            by_symbol[t['symbol']] += t['pnl']
        
        if by_symbol:
            worst = min(by_symbol.items(), key=lambda x: x[1])
            if worst[1] < 0:
                return f"{worst[0]} ({worst[1]:,.0f})"
        return '-'
    
    def get_recent_trades(self, limit=10):
        """최근 거래 내역 - ✅ 항상 최신 데이터"""
        # ✅ 매번 파일에서 다시 로드
        self.trades = self._load_history()
        
        return sorted(
            self.trades,
            key=lambda x: x['timestamp'],
            reverse=True
        )[:limit]
    
    def cleanup_old_trades(self, days=90):
        """오래된 거래 기록 정리"""
        # ✅ 최신 데이터 로드
        self.trades = self._load_history()
        
        cutoff = datetime.now() - timedelta(days=days)
        
        self.trades = [
            t for t in self.trades
            if datetime.fromisoformat(t['timestamp']) > cutoff
        ]
        
        self._save_history()
        logger.info(f"90일 이전 거래 기록 정리 완료")