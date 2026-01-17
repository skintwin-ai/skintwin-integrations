"""
Database models for AI Skill Playground
"""
from database import db_sql
from datetime import datetime
from sqlalchemy.dialects.postgresql import JSONB


class AISkill(db_sql.Model):
    """Model to store available AI skills that can be learned"""
    __tablename__ = 'ai_skills'
    
    id = db_sql.Column(db_sql.Integer, primary_key=True)
    name = db_sql.Column(db_sql.String(100), nullable=False)
    category = db_sql.Column(db_sql.String(50), nullable=False)
    description = db_sql.Column(db_sql.Text, nullable=True)
    icon = db_sql.Column(db_sql.String(50), nullable=True)
    difficulty = db_sql.Column(db_sql.Integer, nullable=False, default=1)  # 1-5 scale
    prerequisites = db_sql.Column(db_sql.Text, nullable=True)
    created_at = db_sql.Column(db_sql.DateTime, default=datetime.utcnow)
    
    # Relationships
    training_sessions = db_sql.relationship('AITrainingSession', backref='skill', lazy=True)
    achievements = db_sql.relationship('AIAchievement', backref='skill', lazy=True)
    progress_records = db_sql.relationship('AISkillProgress', backref='skill', lazy=True)
    
    def __repr__(self):
        return f'<AISkill {self.id}: {self.name}>'


class AITrainingSession(db_sql.Model):
    """Model to track AI training sessions and results"""
    __tablename__ = 'ai_training_sessions'
    
    id = db_sql.Column(db_sql.Integer, primary_key=True)
    skill_id = db_sql.Column(db_sql.Integer, db_sql.ForeignKey('ai_skills.id'), nullable=False)
    user_id = db_sql.Column(db_sql.Integer, db_sql.ForeignKey('users.id'), nullable=False)
    start_time = db_sql.Column(db_sql.DateTime, default=datetime.utcnow, nullable=False)
    end_time = db_sql.Column(db_sql.DateTime, nullable=True)
    success = db_sql.Column(db_sql.Boolean, nullable=True)
    progress = db_sql.Column(db_sql.Float, default=0.0, nullable=False)  # 0-1 scale
    training_parameters = db_sql.Column(JSONB, nullable=True)
    result_metrics = db_sql.Column(JSONB, nullable=True)
    
    # Relationships
    user = db_sql.relationship('User', backref='training_sessions', lazy=True)
    
    def __repr__(self):
        return f'<AITrainingSession {self.id}: {self.skill.name if self.skill else "Unknown"}>'
    
    def complete(self, success=True, metrics=None):
        """Mark the training session as complete with results"""
        self.end_time = datetime.utcnow()
        self.success = success
        self.progress = 1.0 if success else self.progress
        if metrics:
            self.result_metrics = metrics
        db_sql.session.commit()
        
        # Update skill progress if successful
        if success:
            progress = AISkillProgress.query.filter_by(
                user_id=self.user_id, skill_id=self.skill_id
            ).first()
            
            if not progress:
                progress = AISkillProgress(user_id=self.user_id, skill_id=self.skill_id)
                db_sql.session.add(progress)
            
            # Add experience points based on difficulty
            xp_gained = self.skill.difficulty * 10
            progress.experience_points += xp_gained
            
            # Calculate new level
            new_level = 1 + (progress.experience_points // 100)
            if new_level > progress.level:
                progress.level = new_level
                
            progress.last_practiced = datetime.utcnow()
            progress.completion_percentage = min(1.0, progress.completion_percentage + 0.2)
            
            db_sql.session.commit()
            return xp_gained
        
        return 0


class AIAchievement(db_sql.Model):
    """Model to store AI achievements earned by users"""
    __tablename__ = 'ai_achievements'
    
    id = db_sql.Column(db_sql.Integer, primary_key=True)
    user_id = db_sql.Column(db_sql.Integer, db_sql.ForeignKey('users.id'), nullable=False)
    skill_id = db_sql.Column(db_sql.Integer, db_sql.ForeignKey('ai_skills.id'), nullable=False)
    name = db_sql.Column(db_sql.String(100), nullable=False)
    description = db_sql.Column(db_sql.Text, nullable=True)
    points = db_sql.Column(db_sql.Integer, default=0, nullable=False)
    icon = db_sql.Column(db_sql.String(50), nullable=True)
    achieved_at = db_sql.Column(db_sql.DateTime, default=datetime.utcnow, nullable=False)
    details = db_sql.Column(JSONB, nullable=True)
    
    # Relationships
    user = db_sql.relationship('User', backref='ai_achievements', lazy=True)
    
    def __repr__(self):
        return f'<AIAchievement {self.id}: {self.name}>'


class AIModel(db_sql.Model):
    """Model to store AI models created during training"""
    __tablename__ = 'ai_models'
    
    id = db_sql.Column(db_sql.Integer, primary_key=True)
    user_id = db_sql.Column(db_sql.Integer, db_sql.ForeignKey('users.id'), nullable=False)
    name = db_sql.Column(db_sql.String(100), nullable=False)
    category = db_sql.Column(db_sql.String(50), nullable=False)
    description = db_sql.Column(db_sql.Text, nullable=True)
    created_at = db_sql.Column(db_sql.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db_sql.Column(db_sql.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    performance_metrics = db_sql.Column(JSONB, nullable=True)
    model_hash = db_sql.Column(db_sql.String(64), nullable=False)
    status = db_sql.Column(db_sql.String(20), default='active', nullable=False)  # 'training', 'active', 'archived'
    
    # Relationships
    user = db_sql.relationship('User', backref='ai_models', lazy=True)
    
    def __repr__(self):
        return f'<AIModel {self.id}: {self.name}>'


class AISkillProgress(db_sql.Model):
    """Model to track user progress on specific AI skills"""
    __tablename__ = 'ai_skill_progress'
    
    id = db_sql.Column(db_sql.Integer, primary_key=True)
    user_id = db_sql.Column(db_sql.Integer, db_sql.ForeignKey('users.id'), nullable=False)
    skill_id = db_sql.Column(db_sql.Integer, db_sql.ForeignKey('ai_skills.id'), nullable=False)
    level = db_sql.Column(db_sql.Integer, default=1, nullable=False)
    experience_points = db_sql.Column(db_sql.Integer, default=0, nullable=False)
    last_practiced = db_sql.Column(db_sql.DateTime, nullable=True)
    completion_percentage = db_sql.Column(db_sql.Float, default=0.0, nullable=False)  # 0-1 scale
    
    # Relationships
    user = db_sql.relationship('User', backref='skill_progress', lazy=True)
    
    __table_args__ = (db_sql.UniqueConstraint('user_id', 'skill_id'),)
    
    def __repr__(self):
        return f'<AISkillProgress {self.id}: Level {self.level}>'