"""Add AI Skill models

Revision ID: i89fg123
Revises: h67de891
Create Date: 2025-03-19 20:05:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision = 'i89fg123'
down_revision = 'h67de891'
branch_labels = None
depends_on = None


def upgrade():
    # Create AI skill model table
    op.create_table(
        'ai_skills',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('category', sa.String(length=50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('icon', sa.String(length=50), nullable=True),
        sa.Column('difficulty', sa.Integer(), nullable=False, default=1),  # 1-5 scale
        sa.Column('prerequisites', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # Create AI training session table
    op.create_table(
        'ai_training_sessions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('skill_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('start_time', sa.DateTime(), nullable=False),
        sa.Column('end_time', sa.DateTime(), nullable=True),
        sa.Column('success', sa.Boolean(), nullable=True),
        sa.Column('progress', sa.Float(), nullable=False, default=0.0),  # 0-1 scale
        sa.Column('training_parameters', JSONB, nullable=True),
        sa.Column('result_metrics', JSONB, nullable=True),
        sa.ForeignKeyConstraint(['skill_id'], ['ai_skills.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create AI achievements table
    op.create_table(
        'ai_achievements',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('skill_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('points', sa.Integer(), nullable=False, default=0),
        sa.Column('icon', sa.String(length=50), nullable=True),
        sa.Column('achieved_at', sa.DateTime(), nullable=False),
        sa.Column('details', JSONB, nullable=True),
        sa.ForeignKeyConstraint(['skill_id'], ['ai_skills.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create AI models table
    op.create_table(
        'ai_models',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('category', sa.String(length=50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('performance_metrics', JSONB, nullable=True),
        sa.Column('model_hash', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),  # 'training', 'active', 'archived'
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create skill progress tracking table
    op.create_table(
        'ai_skill_progress',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('skill_id', sa.Integer(), nullable=False),
        sa.Column('level', sa.Integer(), nullable=False, default=1),
        sa.Column('experience_points', sa.Integer(), nullable=False, default=0),
        sa.Column('last_practiced', sa.DateTime(), nullable=True),
        sa.Column('completion_percentage', sa.Float(), nullable=False, default=0.0),  # 0-1 scale
        sa.ForeignKeyConstraint(['skill_id'], ['ai_skills.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'skill_id')
    )


def downgrade():
    op.drop_table('ai_skill_progress')
    op.drop_table('ai_models')
    op.drop_table('ai_achievements')
    op.drop_table('ai_training_sessions')
    op.drop_table('ai_skills')