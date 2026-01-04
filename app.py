"""
NCRP Complaint Automation & Intelligence System
Main Flask Application
"""

import os
import shutil
from flask import Flask, request, render_template, jsonify, send_file
from werkzeug.utils import secure_filename
import pandas as pd
from datetime import datetime
from processors.strict_pdf_processor import process_pdf_strict
from processors.excel_builder import build_master_workbook
from processors.csv_processor import process_csv
from processors.excel_processor import process_excel
from processors.deduplicator import append_to_master_excel

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['ALLOWED_EXTENSIONS'] = {'pdf', 'csv', 'xlsx', 'xls'}

# Ensure directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('output', exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'processed'), exist_ok=True)

# Simple in-memory store for complaints across uploads (Step 5)
COMPLAINTS = []

# Progress state for UI polling (Step 7)
PROGRESS = {
    'state': 'idle',            # idle | running | completed | error
    'total_pages': 0,
    'current_page': 0,
    'message': '',
    'download_ready': False
}


def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


@app.route('/')
def index():
    """Render main upload page"""
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle file upload and processing"""
    try:
        # STEP 1: File handling — save before processing
        if 'file' not in request.files:
            return jsonify({'success': False, 'message': 'No file provided'}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({'success': False, 'message': 'No file selected'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({
                'success': False, 
                'message': 'Invalid file type. Allowed: PDF, CSV, XLSX'
            }), 400
        
        # Save uploaded file (temporary local folder)
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Determine file type and process
        file_ext = filename.rsplit('.', 1)[1].lower()
        complaints_data = []
        
        if file_ext == 'pdf':
            # Reset and start progress tracking
            PROGRESS.update({'state': 'running', 'total_pages': 0, 'current_page': 0, 'message': 'Starting PDF analysis...', 'download_ready': False})

            # Define a callback to update progress for each page
            def update_progress(current, total):
                PROGRESS['total_pages'] = total
                PROGRESS['current_page'] = current
                PROGRESS['message'] = f"Analyzing page {current} of {total}"

            # STEP 2-4: Strict PDF processing
            complaint = process_pdf_strict(filepath, update_progress)
            if complaint:
                complaints_data = [complaint]
        elif file_ext == 'csv':
            # Basic CSV mapping to required fields (fallback)
            df = pd.read_csv(filepath)
            for _, row in df.iterrows():
                complaints_data.append({
                    'Complaint_ID': str(row.get('Complaint_ID', '')).strip(),
                    'Complaint_Date_Time': str(row.get('Complaint_Date_Time', '')).strip(),
                    'Complainant_Name': str(row.get('Complainant_Name', '')).strip(),
                    'Mobile_Number': str(row.get('Mobile_Number', '')).strip(),
                    'Email': str(row.get('Email', '')).strip(),
                    'District': str(row.get('District', '')).strip(),
                    'Police_Station': str(row.get('Police_Station', '')).strip(),
                    'Type_of_Cybercrime': str(row.get('Type_of_Cybercrime', '')).strip(),
                    'Platform_Involved': str(row.get('Platform_Involved', '')).strip(),
                    'Amount_Lost': row.get('Amount_Lost', ''),
                    'Current_Status': str(row.get('Current_Status', '')).strip(),
                })
        elif file_ext in ['xlsx', 'xls']:
            # Basic Excel mapping to required fields (fallback)
            df = pd.read_excel(filepath)
            for _, row in df.iterrows():
                complaints_data.append({
                    'Complaint_ID': str(row.get('Complaint_ID', '')).strip(),
                    'Complaint_Date_Time': str(row.get('Complaint_Date_Time', '')).strip(),
                    'Complainant_Name': str(row.get('Complainant_Name', '')).strip(),
                    'Mobile_Number': str(row.get('Mobile_Number', '')).strip(),
                    'Email': str(row.get('Email', '')).strip(),
                    'District': str(row.get('District', '')).strip(),
                    'Police_Station': str(row.get('Police_Station', '')).strip(),
                    'Type_of_Cybercrime': str(row.get('Type_of_Cybercrime', '')).strip(),
                    'Platform_Involved': str(row.get('Platform_Involved', '')).strip(),
                    'Amount_Lost': row.get('Amount_Lost', ''),
                    'Current_Status': str(row.get('Current_Status', '')).strip(),
                })
        else:
            return jsonify({
                'success': False, 
                'message': 'Unsupported file type'
            }), 400
        
        if not complaints_data:
            return jsonify({
                'success': False, 
                'message': 'No complaint data extracted from file'
            }), 400
        
        # STEP 5: Append to in-memory complaints (do NOT overwrite)
        for c in complaints_data:
            COMPLAINTS.append(c)

        # STEP 6: Excel generation AFTER processing completes
        output_path = os.path.join('output', 'ncrp_master.xlsx')
        build_master_workbook(COMPLAINTS, output_path)
        PROGRESS.update({'state': 'completed', 'message': 'Excel generated successfully.', 'download_ready': True})

        new_count = len(complaints_data)
        total_count = len(COMPLAINTS)
        
        # Archive uploaded file instead of deleting
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            archive_name = f"{timestamp}_{filename}"
            archive_path = os.path.join(app.config['UPLOAD_FOLDER'], 'processed', archive_name)
            shutil.move(filepath, archive_path)
        except Exception:
            pass
        
        return jsonify({
            'success': True,
            'message': f'Successfully processed {new_count} new complaint(s). Total: {total_count}',
            'new_complaints': new_count,
            'total_complaints': total_count
        })
    
    except Exception as e:
        PROGRESS.update({'state': 'error', 'message': f'Error: {str(e)}', 'download_ready': False})
        return jsonify({
            'success': False,
            'message': f'Error processing file: {str(e)}'
        }), 500


@app.route('/progress', methods=['GET'])
def get_progress():
    """Return current processing progress for UI polling"""
    return jsonify(PROGRESS)


@app.route('/download/master', methods=['GET'])
def download_master_file():
    """Provide the master Excel file for download"""
    try:
        master_path = os.path.join('output', 'ncrp_master.xlsx')
        if not os.path.exists(master_path):
            return jsonify({'success': False, 'message': 'Master Excel not found'}), 404
        return send_file(master_path, as_attachment=True, download_name='ncrp_master.xlsx')
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error preparing download: {str(e)}'}), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

