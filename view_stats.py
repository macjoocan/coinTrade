# view_stats.py - 통계 조회용

from daily_summary import DailySummary
import pandas as pd

def view_statistics():
    """통계 보기"""
    summary = DailySummary()
    
    # 최근 30일 통계
    stats = summary.get_statistics(days=30)
    
    print("\n" + "="*50)
    print("📊 최근 30일 거래 통계")
    print("="*50)
    print(f"총 손익: {stats['total_pnl']:+,.0f} KRW")
    print(f"일 평균: {stats['avg_daily_pnl']:+,.0f} KRW")
    print(f"승률: {stats['avg_win_rate']:.1f}%")
    print(f"수익일: {stats['winning_days']}일")
    print(f"손실일: {stats['losing_days']}일")
    print(f"최고 수익일: {stats['best_day']}")
    print(f"최대 손실일: {stats['worst_day']}")
    
    # CSV 내보내기
    summary.export_csv()
    print("\n✅ trading_summary.csv 파일로 저장됨")

if __name__ == "__main__":
    view_statistics()