"""
Service trend prediction module
Uses statistical analysis and ML-inspired techniques to predict service trends
"""
from datetime import datetime, timedelta
from collections import Counter, defaultdict
import math

class TrendPredictor:
    """Service trend prediction using statistical analysis"""
    
    @staticmethod
    def predict_service_popularity(services_data, time_period='month'):
        """
        Predict service popularity trends based on historical data
        
        Args:
            services_data: List of service usage data (appointments, transactions)
            time_period: Time period for analysis ('week', 'month', 'quarter')
            
        Returns:
            Dict containing predictions and trend indicators
        """
        # Extract service usage over time
        service_usage = defaultdict(list)
        service_revenue = defaultdict(list)
        
        # Group by service and time period
        for data in services_data:
            service_id = data.get('service_id')
            date = data.get('date_time') or data.get('created_at')
            amount = data.get('amount', 0)
            
            if service_id and date:
                time_key = TrendPredictor._get_time_key(date, time_period)
                # Update service usage and revenue
                current_usage = service_usage.get((service_id, time_key), 0)
                service_usage[(service_id, time_key)] = current_usage + 1
                
                current_revenue = service_revenue.get((service_id, time_key), 0)
                service_revenue[(service_id, time_key)] = current_revenue + amount
        
        # Calculate trend indicators
        trends = {}
        for service_id in set(sid for (sid, _) in service_usage.keys()):
            # Get usage data points in chronological order
            time_keys = sorted(tk for (sid, tk) in service_usage.keys() if sid == service_id)
            usage_data = [service_usage.get((service_id, tk), 0) for tk in time_keys]
            revenue_data = [service_revenue.get((service_id, tk), 0) for tk in time_keys]
            
            if len(usage_data) >= 2:
                # Calculate trend metrics
                growth_rate = TrendPredictor._calculate_growth_rate(usage_data)
                revenue_growth = TrendPredictor._calculate_growth_rate(revenue_data)
                stability = TrendPredictor._calculate_stability(usage_data)
                
                # Calculate prediction for next period
                next_usage = TrendPredictor._predict_next_value(usage_data)
                next_revenue = TrendPredictor._predict_next_value(revenue_data)
                
                trends[service_id] = {
                    'current_usage': usage_data[-1] if usage_data else 0,
                    'predicted_next': int(next_usage),
                    'growth_rate': growth_rate,
                    'revenue_growth': revenue_growth,
                    'stability': stability,
                    'trend_direction': 'up' if growth_rate > 0.05 else ('down' if growth_rate < -0.05 else 'stable'),
                    'confidence': min(0.99, stability * (1 + abs(growth_rate))),
                    'historical_data': usage_data,
                    'current_revenue': revenue_data[-1] if revenue_data else 0,
                    'predicted_revenue': int(next_revenue)
                }
            else:
                # Not enough data points
                trends[service_id] = {
                    'current_usage': usage_data[-1] if usage_data else 0,
                    'predicted_next': usage_data[-1] if usage_data else 0,
                    'growth_rate': 0,
                    'revenue_growth': 0,
                    'stability': 0,
                    'trend_direction': 'stable',
                    'confidence': 0.5,
                    'historical_data': usage_data,
                    'current_revenue': revenue_data[-1] if revenue_data else 0,
                    'predicted_revenue': revenue_data[-1] if revenue_data else 0
                }
        
        return trends
    
    @staticmethod
    def predict_peak_times(appointment_data, granularity='hour'):
        """
        Predict peak booking times based on historical appointments
        
        Args:
            appointment_data: List of appointments with datetime information
            granularity: Time granularity ('hour', 'day', 'day_of_week')
            
        Returns:
            Dict with peak time predictions
        """
        time_counts = Counter()
        
        for appointment in appointment_data:
            date_time = appointment.get('date_time')
            if date_time:
                if granularity == 'hour':
                    key = date_time.hour
                elif granularity == 'day':
                    key = date_time.day
                elif granularity == 'day_of_week':
                    key = date_time.weekday()  # 0 = Monday, 6 = Sunday
                else:
                    key = date_time.hour
                    
                time_counts[key] += 1
        
        # Find peak times (top 3)
        peak_times = time_counts.most_common(3)
        
        # Calculate average count and threshold for "peak" classification
        if time_counts:
            avg_count = sum(time_counts.values()) / len(time_counts)
            peak_threshold = avg_count * 1.25  # 25% above average
        else:
            avg_count = 0
            peak_threshold = 0
        
        # Format results based on granularity
        formatted_peaks = []
        for time_key, count in peak_times:
            if count >= peak_threshold:
                # Default label
                label = f"Time {time_key}"
                
                # Set specific label based on granularity
                if granularity == 'hour':
                    label = f"{time_key}:00 - {time_key + 1}:00"
                elif granularity == 'day':
                    label = f"Day {time_key} of month"
                elif granularity == 'day_of_week':
                    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
                    if 0 <= time_key < len(days):
                        label = days[time_key]
                
                formatted_peaks.append({
                    'time': time_key,
                    'label': label,
                    'count': count,
                    'percentage': round(count / sum(time_counts.values()) * 100, 1) if time_counts else 0
                })
        
        # Calculate low-demand periods (bottom 3)
        low_times = time_counts.most_common()[:-4:-1]  # Bottom 3 in reverse
        formatted_lows = []
        
        for time_key, count in low_times:
            # Default label
            label = f"Time {time_key}"
            
            # Set specific label based on granularity
            if granularity == 'hour':
                label = f"{time_key}:00 - {time_key + 1}:00"
            elif granularity == 'day':
                label = f"Day {time_key} of month"
            elif granularity == 'day_of_week':
                days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
                if 0 <= time_key < len(days):
                    label = days[time_key]
                
            formatted_lows.append({
                'time': time_key,
                'label': label,
                'count': count,
                'percentage': round(count / sum(time_counts.values()) * 100, 1) if time_counts else 0
            })
        
        return {
            'peak_times': formatted_peaks,
            'low_demand_times': formatted_lows,
            'distribution': dict(time_counts),
            'avg_count': avg_count
        }
    
    @staticmethod
    def generate_optimization_recommendations(service_trends, peak_times_data):
        """
        Generate business optimization recommendations based on trends
        
        Args:
            service_trends: Service trend predictions 
            peak_times_data: Peak time analysis data
            
        Returns:
            List of recommendation objects
        """
        recommendations = []
        
        # Check for growing services
        growing_services = [(sid, data) for sid, data in service_trends.items() 
                          if data['growth_rate'] > 0.1 and data['confidence'] > 0.7]
        
        # Check for declining services
        declining_services = [(sid, data) for sid, data in service_trends.items() 
                            if data['growth_rate'] < -0.1 and data['confidence'] > 0.7]
        
        # Recommendations based on growing services
        if growing_services:
            for service_id, data in growing_services:
                recommendations.append({
                    'type': 'resource_allocation',
                    'service_id': service_id,
                    'confidence': data['confidence'],
                    'recommendation': f"Allocate more resources to this growing service",
                    'expected_impact': f"+{round(data['growth_rate'] * 100, 1)}% potential growth",
                    'priority': 'high' if data['growth_rate'] > 0.2 else 'medium'
                })
                
                recommendations.append({
                    'type': 'pricing_opportunity',
                    'service_id': service_id,
                    'confidence': data['confidence'] * 0.9,  # Slightly lower confidence for pricing
                    'recommendation': f"Consider premium pricing or special packages",
                    'expected_impact': f"Potential revenue increase of {round(data['growth_rate'] * 100 * 1.2, 1)}%",
                    'priority': 'medium'
                })
        
        # Recommendations based on declining services
        if declining_services:
            for service_id, data in declining_services:
                if data['stability'] > 0.7:
                    # Stable decline, not just random fluctuation
                    recommendations.append({
                        'type': 'service_improvement',
                        'service_id': service_id,
                        'confidence': data['confidence'],
                        'recommendation': f"Review and improve this declining service",
                        'expected_impact': f"Prevent further {round(abs(data['growth_rate']) * 100, 1)}% decline",
                        'priority': 'high' if data['growth_rate'] < -0.2 else 'medium'
                    })
                    
                    recommendations.append({
                        'type': 'promotion_opportunity',
                        'service_id': service_id,
                        'confidence': data['confidence'] * 0.8,
                        'recommendation': f"Consider promotional campaign or bundling with popular services",
                        'expected_impact': "Potentially reverse negative trend",
                        'priority': 'medium'
                    })
        
        # Recommendations based on peak times
        if peak_times_data and 'peak_times' in peak_times_data and peak_times_data['peak_times']:
            peak_labels = [p['label'] for p in peak_times_data['peak_times']]
            peak_text = ", ".join(peak_labels)
            
            recommendations.append({
                'type': 'scheduling_optimization',
                'confidence': 0.85,
                'recommendation': f"Optimize staffing during peak times: {peak_text}",
                'expected_impact': "Improved client satisfaction and resource utilization",
                'priority': 'high'
            })
            
            if 'low_demand_times' in peak_times_data and peak_times_data['low_demand_times']:
                low_labels = [l['label'] for l in peak_times_data['low_demand_times']]
                low_text = ", ".join(low_labels)
                
                recommendations.append({
                    'type': 'promotion_timing',
                    'confidence': 0.8,
                    'recommendation': f"Run promotions during low-demand periods: {low_text}",
                    'expected_impact': "Increase bookings during slower periods",
                    'priority': 'medium'
                })
        
        # Sort recommendations by priority
        priority_map = {'high': 3, 'medium': 2, 'low': 1}
        recommendations.sort(key=lambda x: priority_map.get(x['priority'], 0), reverse=True)
        
        return recommendations
    
    @staticmethod
    def _get_time_key(date, time_period):
        """Convert datetime to a period key"""
        if time_period == 'week':
            # ISO week number
            return f"{date.year}-W{date.isocalendar()[1]}"
        elif time_period == 'month':
            return f"{date.year}-{date.month:02d}"
        elif time_period == 'quarter':
            quarter = (date.month - 1) // 3 + 1
            return f"{date.year}-Q{quarter}"
        else:
            return f"{date.year}-{date.month:02d}"
    
    @staticmethod
    def _calculate_growth_rate(data):
        """Calculate growth rate from time series data"""
        if not data or len(data) < 2:
            return 0
            
        # Simple growth rate from first to last period
        if len(data) >= 4:
            # Use average of first half vs second half
            mid_point = len(data) // 2
            first_half_avg = sum(data[:mid_point]) / mid_point if mid_point > 0 else 0
            second_half_avg = sum(data[mid_point:]) / (len(data) - mid_point) if (len(data) - mid_point) > 0 else 0
            
            if first_half_avg > 0:
                return (second_half_avg - first_half_avg) / first_half_avg
            else:
                return 0 if second_half_avg == 0 else 1  # Full growth from zero
        else:
            # Simple first to last comparison
            if data[0] > 0:
                return (data[-1] - data[0]) / data[0]
            else:
                return 0 if data[-1] == 0 else 1  # Full growth from zero
    
    @staticmethod
    def _calculate_stability(data):
        """Calculate stability score (inverse of volatility)"""
        if not data or len(data) < 2:
            return 0.5  # Default medium stability
            
        # Calculate coefficient of variation (lower means more stable)
        mean = sum(data) / len(data)
        if mean == 0:
            return 0.5
            
        variance = sum((x - mean) ** 2 for x in data) / len(data)
        std_dev = variance ** 0.5
        cv = std_dev / mean if mean != 0 else 99  # Avoid division by zero
        
        # Convert to stability score (0-1)
        stability = 1 / (1 + cv)
        return min(0.95, stability)  # Cap at 0.95
    
    @staticmethod
    def _predict_next_value(data):
        """Predict next value in time series"""
        if not data:
            return 0
        elif len(data) == 1:
            return data[0]
            
        # For simplicity, use weighted average of recent values
        # This could be enhanced with more sophisticated time series models
        if len(data) >= 5:
            # More weight to recent data points
            weights = [0.1, 0.15, 0.2, 0.25, 0.3]
            return sum(d * w for d, w in zip(data[-5:], weights))
        elif len(data) >= 3:
            # Weighted average for 3 or 4 data points
            weights = [0.2, 0.35, 0.45][:len(data)]
            weights = [w / sum(weights) for w in weights]  # Normalize
            return sum(d * w for d, w in zip(data[-3:], weights))
        else:
            # Simple trend for 2 data points
            return data[-1] + (data[-1] - data[0]) / len(data)