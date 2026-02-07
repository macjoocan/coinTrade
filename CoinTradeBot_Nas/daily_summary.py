# daily_summary.py
import json
import os
from datetime import datetime, timedelta
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)

class DailySummary:
    """일일 거래 요약 관리"""
    
    def __init__(self):
        self.summary_file = "daily_summaries.json"
        self.current_day_file = "today_trades.json"
        self.summaries = self.load_summaries()
        self.today_trades = []
        
    def load_summaries(self):
        """기존 요약 데이터 로드"""
        if os.path.exists(self.summary_file):
            try:
                with open(self.summary_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def save_summaries(self):
        """요약 데이터 저장"""
        with open(self.summary_file, 'w', encoding='utf-8') as f:
            json.dump(self.summaries, f, indent=2, ensure_ascii=False)
    
    def record_trade(self, trade_data):
        """거래 기록"""
        trade = {
            'timestamp': datetime.now().isoformat(),
            'symbol': trade_data['symbol'],
            'type': trade_data['type'],  # buy/sell
            'price': trade_data['price'],
            'quantity': trade_data.get('quantity', 0),
            'pnl': trade_data.get('pnl', 0),
            'pnl_rate': trade_data.get('pnl_rate', 0)
        }
        
        self.today_trades.append(trade)
        
        # 실시간 저장
        with open(self.current_day_file, 'w', encoding='utf-8') as f:
            json.dump(self.today_trades, f, indent=2)
    
    def finalize_day(self, date=None):
        """일일 요약 생성"""
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        
        # 오늘 거래 분석
        total_trades = len(self.today_trades)
        buy_trades = [t for t in self.today_trades if t['type'] == 'buy']
        sell_trades = [t for t in self.today_trades if t['type'] == 'sell']
        
        # 손익 계산
        profits = [t['pnl'] for t in sell_trades if 'pnl' in t]
        wins = [p for p in profits if p > 0]
        losses = [p for p in profits if p < 0]
        
        # 일일 요약
        summary = {
            'date': date,
            'total_trades': total_trades,
            'buy_count': len(buy_trades),
            'sell_count': len(sell_trades),
            'winning_trades': len(wins),
            'losing_trades': len(losses),
            'total_pnl': sum(profits),
            'win_rate': len(wins) / len(profits) * 100 if profits else 0,
            'avg_win': sum(wins) / len(wins) if wins else 0,
            'avg_loss': sum(losses) / len(losses) if losses else 0,
            'max_win': max(wins) if wins else 0,
            'max_loss': min(losses) if losses else 0,
            'traded_symbols': list(set([t['symbol'] for t in self.today_trades]))
        }
        
        # 저장
        self.summaries[date] = summary
        self.save_summaries()
        
        # 오늘 거래 초기화
        self.today_trades = []
        if os.path.exists(self.current_day_file):
            os.remove(self.current_day_file)
        
        logger.info(f"일일 요약 저장 완료: {date}")
        return summary
    
    def get_statistics(self, days=30):
        """최근 N일 통계"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        stats = {
            'period_days': days,
            'total_pnl': 0,
            'total_trades': 0,
            'winning_days': 0,
            'losing_days': 0,
            'best_day': None,
            'worst_day': None,
            'avg_daily_pnl': 0,
            'avg_win_rate': 0
        }
        
        daily_pnls = []
        win_rates = []
        
        for date_str, summary in self.summaries.items():
            date = datetime.strptime(date_str, '%Y-%m-%d')
            if start_date <= date <= end_date:
                pnl = summary['total_pnl']
                daily_pnls.append(pnl)
                win_rates.append(summary['win_rate'])
                
                stats['total_pnl'] += pnl
                stats['total_trades'] += summary['total_trades']
                
                if pnl > 0:
                    stats['winning_days'] += 1
                else:
                    stats['losing_days'] += 1
                
                # 최고/최악 일
                if stats['best_day'] is None or pnl > self.summaries[stats['best_day']]['total_pnl']:
                    stats['best_day'] = date_str
                if stats['worst_day'] is None or pnl < self.summaries[stats['worst_day']]['total_pnl']:
                    stats['worst_day'] = date_str
        
        # 평균 계산
        if daily_pnls:
            stats['avg_daily_pnl'] = sum(daily_pnls) / len(daily_pnls)
            stats['avg_win_rate'] = sum(win_rates) / len(win_rates)
        
        return stats
    
    def export_csv(self, filename="trading_summary.csv"):
        """CSV로 내보내기"""
        import csv
        
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            if not self.summaries:
                return
            
            # 헤더
            fieldnames = list(next(iter(self.summaries.values())).keys())
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            # 데이터
            for summary in self.summaries.values():
                writer.writerow(summary)
        
        logger.info(f"CSV 내보내기 완료: {filename}")