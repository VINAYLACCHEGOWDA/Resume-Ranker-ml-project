from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
import json

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

class JobDescription(db.Model):
    """Model for storing job descriptions"""
    __tablename__ = 'job_descriptions'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=False)
    preprocessed_text = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship with analysis sessions
    analysis_sessions = db.relationship('AnalysisSession', backref='job_description', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<JobDescription {self.title}>'

class Resume(db.Model):
    """Model for storing resume information"""
    __tablename__ = 'resumes'
    
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    original_text = db.Column(db.Text, nullable=False)
    preprocessed_text = db.Column(db.Text)
    file_size = db.Column(db.Integer)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship with resume rankings
    rankings = db.relationship('ResumeRanking', backref='resume', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Resume {self.filename}>'

class AnalysisSession(db.Model):
    """Model for storing analysis sessions"""
    __tablename__ = 'analysis_sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    job_description_id = db.Column(db.Integer, db.ForeignKey('job_descriptions.id'), nullable=False)
    session_name = db.Column(db.String(255))
    total_resumes = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship with resume rankings
    rankings = db.relationship('ResumeRanking', backref='analysis_session', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<AnalysisSession {self.session_name}>'

class ResumeRanking(db.Model):
    """Model for storing resume ranking results"""
    __tablename__ = 'resume_rankings'
    
    id = db.Column(db.Integer, primary_key=True)
    analysis_session_id = db.Column(db.Integer, db.ForeignKey('analysis_sessions.id'), nullable=False)
    resume_id = db.Column(db.Integer, db.ForeignKey('resumes.id'), nullable=False)
    
    # Ranking data
    rank = db.Column(db.Integer, nullable=False)
    score = db.Column(db.Float, nullable=False)
    match_percentage = db.Column(db.Float, nullable=False)
    skill_count = db.Column(db.Integer, default=0)
    is_ats_friendly = db.Column(db.Boolean, default=False)
    
    # Store skills as JSON
    key_skills = db.Column(db.Text)  # JSON string
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def set_key_skills(self, skills_list):
        """Convert list of skills to JSON string"""
        self.key_skills = json.dumps(skills_list) if skills_list else json.dumps([])
    
    def get_key_skills(self):
        """Get skills as a list"""
        return json.loads(self.key_skills) if self.key_skills else []
    
    def __repr__(self):
        return f'<ResumeRanking Rank:{self.rank} Score:{self.score}>'

class UserSession(db.Model):
    """Model for tracking user sessions and history"""
    __tablename__ = 'user_sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(255), unique=True, nullable=False)
    analysis_session_id = db.Column(db.Integer, db.ForeignKey('analysis_sessions.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_accessed = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<UserSession {self.session_id}>'