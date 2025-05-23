# AI Resume Ranker Project Guide

## Overview

This project is an AI-powered resume ranking system built with Flask. It allows users to upload multiple PDF resumes and a job description, then uses natural language processing to rank the resumes based on their relevance to the job description. The system extracts text from PDFs, preprocesses it, and uses TF-IDF vectorization with cosine similarity to determine the best matches.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

The application follows a simple web application architecture:

1. **Frontend**: HTML templates with Bootstrap 5 for styling, with dark theme enabled
2. **Backend**: Flask Python web framework
3. **Data Processing**: Uses scikit-learn for TF-IDF vectorization and SpaCy for NLP
4. **Database**: No persistent database currently implemented
5. **Deployment**: Configured for Gunicorn deployment with autoscaling

The architecture is designed to be lightweight and focused on the core resume ranking functionality. File uploads are temporarily stored and processed in memory rather than being persisted to a database.

## Key Components

### Flask Application (app.py)
- Handles HTTP requests and routing
- Manages file uploads and session data
- Renders templates and returns responses
- Current endpoints include:
  - `/` - Main page for uploading resumes and job descriptions
  - `/upload` - Endpoint for processing resume uploads

### Resume Ranker (resume_ranker.py)
- Core NLP and ranking functionality
- PDF text extraction using PyPDF2
- Text preprocessing and analysis using SpaCy
- TF-IDF vectorization and cosine similarity calculation

### Templates
- `index.html` - Upload form for resumes and job description
- `results.html` - Displays ranked resumes with visualization

### Static Assets
- CSS for styling (style.css)
- JavaScript for frontend interactivity (script.js)

## Data Flow

1. User uploads multiple PDF resumes and enters a job description
2. The system extracts text from each PDF
3. Both resume text and job description are preprocessed using NLP techniques
4. TF-IDF vectorization is applied to convert text to numerical features
5. Cosine similarity is calculated between each resume and the job description
6. Resumes are ranked based on similarity scores
7. Results are displayed to the user with an option to download a CSV report

## External Dependencies

### Python Packages
- Flask (web framework)
- PyPDF2 (PDF text extraction)
- SpaCy (natural language processing)
- pandas (data manipulation)
- scikit-learn (ML utilities for vectorization and similarity)
- gunicorn (WSGI HTTP server)

### Frontend Libraries
- Bootstrap 5 (CSS framework)
- Bootstrap Icons (icon set)
- Chart.js (for visualizations)

## Deployment Strategy

The application is configured for deployment on Replit with the following characteristics:

1. **Runtime**: Python 3.11
2. **WSGI Server**: Gunicorn
3. **Deployment Target**: Autoscale
4. **Dependencies**: 
   - OpenSSL
   - PostgreSQL (installed but not currently used)

Run command: `gunicorn --bind 0.0.0.0:5000 main:app`

## Future Enhancements

1. **Database Integration**: Implement PostgreSQL database for storing resume data and results
2. **User Authentication**: Add user accounts to save analysis history
3. **Enhanced Analytics**: More detailed resume analysis with skill extraction
4. **Candidate Comparison**: Side-by-side comparison of multiple candidates
5. **Bulk Processing**: Background job processing for large batches of resumes

## Development Notes

- The SpaCy model 'en_core_web_sm' is downloaded automatically if not available
- File uploads are temporarily stored in the system temp directory
- Maximum upload size is limited to 16MB
- Debug mode is enabled in development but should be disabled in production