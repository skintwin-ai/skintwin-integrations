
import json
from datetime import datetime
from typing import Dict, Any, List
import hashlib

class ModelContribution:
    """Tracks successful model implementations and their contributions"""
    
    def __init__(self, model_name: str, category: str, description: str,
                 performance_metrics: Dict[str, float], contributors: List[str]):
        self.model_name = model_name
        self.category = category
        self.description = description 
        self.performance_metrics = performance_metrics
        self.contributors = contributors
        self.timestamp = datetime.utcnow()
        self.model_hash = self._generate_hash()
        
    def _generate_hash(self) -> str:
        """Generate unique hash for the model contribution"""
        content = f"{self.model_name}{self.category}{self.description}{self.timestamp}"
        return hashlib.sha256(content.encode()).hexdigest()[:12]
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert contribution to dictionary format"""
        return {
            "model_name": self.model_name,
            "category": self.category,
            "description": self.description,
            "performance_metrics": self.performance_metrics,
            "contributors": self.contributors,
            "timestamp": self.timestamp.isoformat(),
            "model_hash": self.model_hash
        }

class ContributionRegistry:
    """Registry for tracking and managing model contributions"""
    
    CONTRIBUTION_FILE = "math/contributions_registry.json"
    
    @classmethod
    def register_contribution(cls, contribution: ModelContribution) -> bool:
        """Register a new model contribution"""
        try:
            # Load existing contributions
            try:
                with open(cls.CONTRIBUTION_FILE, 'r') as f:
                    contributions = json.load(f)
            except FileNotFoundError:
                contributions = []
                
            # Add new contribution
            contributions.append(contribution.to_dict())
            
            # Save updated registry
            with open(cls.CONTRIBUTION_FILE, 'w') as f:
                json.dump(contributions, f, indent=2)
                
            return True
            
        except Exception as e:
            print(f"Error registering contribution: {str(e)}")
            return False
            
    @classmethod
    def get_contributions(cls, category: str = None) -> List[Dict[str, Any]]:
        """Get all contributions, optionally filtered by category"""
        try:
            with open(cls.CONTRIBUTION_FILE, 'r') as f:
                contributions = json.load(f)
                
            if category:
                contributions = [c for c in contributions if c["category"] == category]
                
            return contributions
        except FileNotFoundError:
            return []
