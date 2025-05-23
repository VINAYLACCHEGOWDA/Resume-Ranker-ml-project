import os
import logging
import tempfile
import pandas as pd
import uuid
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file, jsonify
from werkzeug.utils import secure_filename
from werkzeug.middleware.proxy_fix import ProxyFix
from resume_ranker import extract_text_from_pdf, preprocess_text, rank_resumes, filter_resumes_by_rank, generate_ats_friendly_resume, create_resume_template
from models import db, JobDescription, Resume, AnalysisSession, ResumeRanking, UserSession

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev_secret_key")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Configure database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Initialize database
db.init_app(app)

# Create database tables
with app.app_context():
    db.create_all()

# Configure upload settings
ALLOWED_EXTENSIONS = {'pdf'}
UPLOAD_FOLDER = tempfile.gettempdir()
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max size

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_or_create_user_session():
    """Get or create a user session for tracking"""
    if 'user_session_id' not in session:
        session['user_session_id'] = str(uuid.uuid4())
    
    user_session = UserSession.query.filter_by(session_id=session['user_session_id']).first()
    if not user_session:
        user_session = UserSession(session_id=session['user_session_id'])
        db.session.add(user_session)
        db.session.commit()
    else:
        user_session.last_accessed = datetime.utcnow()
        db.session.commit()
    
    return user_session

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_files():
    # Get or create user session
    user_session = get_or_create_user_session()
    
    # Check if job description is provided
    job_description_text = request.form.get('job_description', '').strip()
    if not job_description_text:
        flash('Please provide a job description', 'danger')
        return redirect(url_for('index'))
    
    # Check if files are uploaded
    if 'resumes' not in request.files:
        flash('No files uploaded', 'danger')
        return redirect(url_for('index'))
    
    files = request.files.getlist('resumes')
    
    if not files or not files[0].filename:
        flash('No files selected', 'danger')
        return redirect(url_for('index'))
    
    try:
        # Create job description record
        preprocessed_job_desc = preprocess_text(job_description_text)
        job_desc = JobDescription(
            title=f"Job Analysis {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            description=job_description_text,
            preprocessed_text=preprocessed_job_desc
        )
        db.session.add(job_desc)
        db.session.flush()  # Get the ID
        
        # Create analysis session
        analysis_session = AnalysisSession(
            job_description_id=job_desc.id,
            session_name=f"Analysis {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )
        db.session.add(analysis_session)
        db.session.flush()  # Get the ID
        
        # Process uploaded resumes
        resume_data = []
        resume_records = []
        
        for file in files:
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                
                try:
                    # Extract text from PDF
                    extracted_text = extract_text_from_pdf(filepath)
                    
                    if not extracted_text:
                        flash(f'Could not extract text from {filename}', 'warning')
                        continue
                    
                    # Create resume record
                    resume_record = Resume(
                        filename=filename,
                        original_text=extracted_text,
                        preprocessed_text=preprocess_text(extracted_text),
                        file_size=len(extracted_text)
                    )
                    db.session.add(resume_record)
                    db.session.flush()  # Get the ID
                    resume_records.append(resume_record)
                    
                    # Add to resume data list for ranking
                    resume_data.append({
                        'filename': filename,
                        'text': extracted_text,
                        'preprocessed_text': resume_record.preprocessed_text,
                        'resume_id': resume_record.id
                    })
                    
                except Exception as e:
                    logging.error(f"Error processing {filename}: {str(e)}")
                    flash(f'Error processing {filename}: {str(e)}', 'danger')
                finally:
                    # Clean up the temporary file
                    if os.path.exists(filepath):
                        os.remove(filepath)
        
        if not resume_data:
            flash('No valid resumes were uploaded', 'danger')
            db.session.rollback()
            return redirect(url_for('index'))
        
        # Rank resumes
        ranked_resumes = rank_resumes(resume_data, preprocessed_job_desc)
        
        # Store rankings in database
        for resume_data_item in ranked_resumes:
            ranking = ResumeRanking(
                analysis_session_id=analysis_session.id,
                resume_id=resume_data_item.get('resume_id'),
                rank=resume_data_item['rank'],
                score=resume_data_item['score'],
                match_percentage=resume_data_item['match_percentage'],
                skill_count=resume_data_item['skill_count'],
                is_ats_friendly=resume_data_item['is_ats_friendly']
            )
            ranking.set_key_skills(resume_data_item['key_skills'])
            db.session.add(ranking)
        
        # Update analysis session
        analysis_session.total_resumes = len(resume_data)
        
        # Update user session
        user_session.analysis_session_id = analysis_session.id
        
        # Commit all changes
        db.session.commit()
        
        # Store analysis session ID in Flask session
        session['analysis_session_id'] = analysis_session.id
        
        flash(f'Successfully analyzed {len(resume_data)} resumes!', 'success')
        return redirect(url_for('results'))
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Database error: {str(e)}")
        flash('An error occurred while saving the analysis. Please try again.', 'danger')
        return redirect(url_for('index'))

@app.route('/results')
def results():
    if 'analysis_session_id' not in session:
        flash('No analysis results available', 'warning')
        return redirect(url_for('index'))
    
    analysis_session_id = session['analysis_session_id']
    analysis_session = AnalysisSession.query.get_or_404(analysis_session_id)
    
    # Get all rankings for this session
    all_rankings = ResumeRanking.query.filter_by(
        analysis_session_id=analysis_session_id
    ).join(Resume).order_by(ResumeRanking.rank).all()
    
    # Convert to the format expected by templates
    all_resumes = []
    for ranking in all_rankings:
        resume_data = {
            'rank': ranking.rank,
            'filename': ranking.resume.filename,
            'score': ranking.score,
            'match_percentage': ranking.match_percentage,
            'skill_count': ranking.skill_count,
            'is_ats_friendly': ranking.is_ats_friendly,
            'key_skills': ranking.get_key_skills(),
            'text': ranking.resume.original_text,
            'resume_id': ranking.resume_id,
            'ranking_id': ranking.id
        }
        all_resumes.append(resume_data)
    
    # Default to showing all resumes
    min_rank = request.args.get('min_rank', 1, type=int)
    max_rank = request.args.get('max_rank', None, type=int)
    
    # Filter resumes by rank if requested
    if min_rank > 1 or max_rank:
        filtered_resumes = filter_resumes_by_rank(all_resumes, min_rank, max_rank)
    else:
        filtered_resumes = all_resumes
    
    return render_template('results.html', 
                           resumes=filtered_resumes,
                           all_resumes=all_resumes,
                           job_description=analysis_session.job_description.description,
                           analysis_session=analysis_session,
                           min_rank=min_rank,
                           max_rank=max_rank)

@app.route('/download_report')
def download_report():
    if 'analysis_session_id' not in session:
        flash('No analysis results available', 'warning')
        return redirect(url_for('index'))
    
    analysis_session_id = session['analysis_session_id']
    
    # Get rankings from database
    all_rankings = ResumeRanking.query.filter_by(
        analysis_session_id=analysis_session_id
    ).join(Resume).order_by(ResumeRanking.rank).all()
    
    # Convert to list of dictionaries for CSV
    report_data = []
    for ranking in all_rankings:
        report_data.append({
            'Rank': ranking.rank,
            'Resume_Filename': ranking.resume.filename,
            'Match_Score': ranking.score,
            'Match_Percentage': ranking.match_percentage,
            'Skills_Count': ranking.skill_count,
            'ATS_Friendly': ranking.is_ats_friendly,
            'Key_Skills': ', '.join(ranking.get_key_skills()),
            'Upload_Date': ranking.resume.uploaded_at.strftime('%Y-%m-%d %H:%M')
        })
    
    # Get filter parameters if they exist
    min_rank = request.args.get('min_rank', 1, type=int)
    max_rank = request.args.get('max_rank', None, type=int)
    
    # Filter by rank if requested
    if min_rank > 1 or max_rank:
        if max_rank:
            report_data = [r for r in report_data if min_rank <= r['Rank'] <= max_rank]
        else:
            report_data = [r for r in report_data if r['Rank'] >= min_rank]
    
    # Create a dataframe and save as CSV
    df = pd.DataFrame(report_data)
    
    # Create temporary CSV file
    temp_csv = os.path.join(app.config['UPLOAD_FOLDER'], 'resume_ranking_report.csv')
    df.to_csv(temp_csv, index=False)
    
    # Send file to client
    return send_file(
        temp_csv,
        mimetype='text/csv',
        as_attachment=True,
        download_name='resume_ranking_report.csv'
    )

@app.route('/ats_resume/<int:resume_index>')
def ats_resume(resume_index):
    if 'ranked_resumes' not in session or 'job_description' not in session:
        flash('No analysis results available', 'warning')
        return redirect(url_for('index'))
        
    ranked_resumes = session['ranked_resumes']
    job_description = session['job_description']
    
    # Verify resume index is valid
    if resume_index < 0 or resume_index >= len(ranked_resumes):
        flash('Invalid resume selection', 'danger')
        return redirect(url_for('results'))
    
    # Get the selected resume
    resume = ranked_resumes[resume_index]
    
    # Generate ATS-friendly version
    ats_friendly_content = generate_ats_friendly_resume(
        resume['text'], 
        job_description, 
        resume['key_skills']
    )
    
    return render_template('ats_resume.html', 
        resume=resume, 
        ats_content=ats_friendly_content,
        job_description=job_description
    )

@app.route('/resume_template')
def resume_template():
    """Display a blank resume template that users can customize"""
    template_content = create_resume_template()
    
    return render_template('resume_template.html', 
        template_content=template_content
    )

@app.route('/filter_resumes', methods=['POST'])
def filter_resumes():
    """Handle resume filtering form submission"""
    if 'ranked_resumes' not in session:
        flash('No analysis results available', 'warning')
        return redirect(url_for('index'))
    
    # Get filter parameters
    min_rank = request.form.get('min_rank', 1, type=int)
    max_rank = request.form.get('max_rank', None)
    
    # Convert empty string to None for max_rank
    if max_rank == '':
        max_rank = None
    elif max_rank is not None:
        max_rank = int(max_rank)
    
    # Redirect to results with filter params
    return redirect(url_for('results', min_rank=min_rank, max_rank=max_rank))

@app.route('/clear_session')
def clear_session():
    session.clear()
    return redirect(url_for('index'))

@app.errorhandler(413)
def too_large(e):
    flash('The file is too large. Maximum size is 16MB.', 'danger')
    return redirect(url_for('index'))

@app.errorhandler(500)
def server_error(e):
    flash('An internal server error occurred. Please try again.', 'danger')
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
