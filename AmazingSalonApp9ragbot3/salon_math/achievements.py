
from datetime import datetime
from database import db_sql
from database_models_ai import ChatConversation, ChatMessage
import json

class SkillAchievement:
    """Tracks and awards achievements for AI assistant skill development"""
    
    ACHIEVEMENTS = {
        'julia_master': {
            'name': 'Julia Master',
            'description': 'Successfully implemented a Julia-powered learning module',
            'points': 100,
            'icon': 'fa-gem'
        },
        'skin_analyzer': {
            'name': 'Skin Analysis Expert',
            'description': 'Mastered skin analysis pattern recognition',
            'points': 150,
            'icon': 'fa-microscope'
        },
        'treatment_optimizer': {
            'name': 'Treatment Optimization Guru',
            'description': 'Developed advanced treatment optimization algorithms',
            'points': 200,
            'icon': 'fa-chart-line'
        }
    }
    
    @classmethod
    def check_achievement(cls, skill_name, implementation_success):
        """Check if an achievement should be awarded"""
        if not implementation_success:
            return None
            
        if skill_name in cls.ACHIEVEMENTS:
            return cls.ACHIEVEMENTS[skill_name]
        return None
    
    @classmethod
    def award_achievement(cls, skill_name, user_id):
        """Award an achievement and post to news feed"""
        from models import create_news_post
        
        achievement = cls.ACHIEVEMENTS.get(skill_name)
        if not achievement:
            return
            
        # Create news feed post
        post_content = {
            'type': 'achievement',
            'achievement': achievement['name'],
            'description': achievement['description'],
            'points': achievement['points'],
            'icon': achievement['icon'],
            'awarded_at': datetime.utcnow().isoformat()
        }
        
        create_news_post(
            title=f"New Achievement Unlocked: {achievement['name']}!",
            content=json.dumps(post_content),
            post_type='achievement',
            user_id=user_id
        )
        
        return achievement
