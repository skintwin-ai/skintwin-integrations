
from typing import List, Dict, Optional
import numpy as np

class SalonStatistics:
    @staticmethod
    def calculate_revenue_metrics(transactions: List[Dict]) -> Dict:
        """Calculate revenue-related metrics"""
        amounts = [t.get('amount', 0) for t in transactions]
        
        return {
            'total': sum(amounts),
            'average': np.mean(amounts) if amounts else 0,
            'median': np.median(amounts) if amounts else 0,
            'max': max(amounts) if amounts else 0,
            'min': min(amounts) if amounts else 0
        }
    
    @staticmethod
    def calculate_retention_rate(total_clients: int, returning_clients: int) -> float:
        """Calculate client retention rate"""
        return (returning_clients / total_clients * 100) if total_clients > 0 else 0
    
    @staticmethod
    def predict_next_visit(visit_dates: List[str]) -> Optional[str]:
        """Predict next likely visit based on historical patterns"""
        if len(visit_dates) < 2:
            return None
            
        # Convert dates to numerical intervals
        from datetime import datetime
        dates = [datetime.fromisoformat(d) for d in visit_dates]
        intervals = [(dates[i+1] - dates[i]).days for i in range(len(dates)-1)]
        
        # Predict next interval using moving average
        predicted_interval = sum(intervals[-3:]) / len(intervals[-3:]) if len(intervals) >= 3 else intervals[-1]
        next_date = dates[-1] + timedelta(days=int(predicted_interval))
        
        return next_date.isoformat()
