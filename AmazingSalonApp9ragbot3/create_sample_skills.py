"""
Script to create sample AI skills for the skill playground
"""
from database import db_sql
from database_models_skills import AISkill
from app import app

def create_sample_skills():
    """Create sample AI skills for the skill playground"""
    with app.app_context():
        # Check if skills already exist
        if AISkill.query.count() > 0:
            print("Skills already exist in the database.")
            return
        
        # Skin Analysis Skills
        skin_analyzer = AISkill(
            name="Skin Condition Analyzer",
            category="skin_analysis",
            description="Train an AI model to analyze and classify various skin conditions from diagnostic measurements.",
            icon="fa-microscope",
            difficulty=2,
            prerequisites="Basic understanding of skin conditions and diagnostic measurements."
        )
        
        advanced_analyzer = AISkill(
            name="Advanced Pattern Recognition",
            category="skin_analysis",
            description="Develop a sophisticated model to detect subtle patterns and correlations in skin conditions.",
            icon="fa-search-plus",
            difficulty=4,
            prerequisites="Completion of Skin Condition Analyzer skill."
        )
        
        # Treatment Optimization Skills
        treatment_optimizer = AISkill(
            name="Treatment Parameter Optimizer",
            category="treatment_optimization",
            description="Train an AI to determine optimal treatment parameters based on client skin sensitivity and goals.",
            icon="fa-sliders-h",
            difficulty=3,
            prerequisites="Basic understanding of skincare treatments and client sensitivity factors."
        )
        
        personalized_treatment = AISkill(
            name="Personalized Treatment Designer",
            category="treatment_optimization",
            description="Create highly personalized treatment plans tailored to individual client needs and skin conditions.",
            icon="fa-user-cog",
            difficulty=5,
            prerequisites="Completion of Treatment Parameter Optimizer skill."
        )
        
        # Ingredient Analysis Skills
        ingredient_synergy = AISkill(
            name="Ingredient Synergy Analyzer",
            category="ingredient_analysis",
            description="Train an AI to identify effective combinations of skincare ingredients with high synergy.",
            icon="fa-flask",
            difficulty=3,
            prerequisites="Basic knowledge of skincare ingredients and their interactions."
        )
        
        formulation_optimizer = AISkill(
            name="Product Formulation Optimizer",
            category="ingredient_analysis",
            description="Develop an AI that can optimize product formulations for specific skin types and concerns.",
            icon="fa-vial",
            difficulty=4,
            prerequisites="Completion of Ingredient Synergy Analyzer skill."
        )
        
        # Add all skills to the database
        skills = [
            skin_analyzer, 
            advanced_analyzer, 
            treatment_optimizer,
            personalized_treatment,
            ingredient_synergy,
            formulation_optimizer
        ]
        
        for skill in skills:
            db_sql.session.add(skill)
        
        db_sql.session.commit()
        print(f"Created {len(skills)} sample AI skills.")

if __name__ == "__main__":
    create_sample_skills()