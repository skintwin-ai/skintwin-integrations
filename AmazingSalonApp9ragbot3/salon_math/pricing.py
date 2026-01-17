
class DynamicPricing:
    @staticmethod
    def calculate_surge_multiplier(
        current_bookings: int,
        total_capacity: int,
        base_multiplier: float = 1.0,
        max_multiplier: float = 1.5
    ) -> float:
        """Calculate surge pricing multiplier based on demand"""
        utilization = current_bookings / total_capacity if total_capacity > 0 else 0
        
        if utilization < 0.5:
            return base_multiplier
        elif utilization < 0.75:
            return min(base_multiplier * 1.2, max_multiplier)
        elif utilization < 0.9:
            return min(base_multiplier * 1.35, max_multiplier)
        else:
            return max_multiplier
    
    @staticmethod
    def calculate_loyalty_discount(
        points: int,
        tier: str,
        base_price: float
    ) -> float:
        """Calculate price after loyalty discounts"""
        tier_discounts = {
            'bronze': 0.05,
            'silver': 0.10,
            'gold': 0.15,
            'platinum': 0.20
        }
        
        # Base tier discount
        discount = tier_discounts.get(tier.lower(), 0)
        
        # Additional points-based discount
        points_discount = min((points // 1000) * 0.01, 0.10)  # Max 10% additional discount
        
        total_discount = min(discount + points_discount, 0.30)  # Cap at 30% total discount
        return base_price * (1 - total_discount)
