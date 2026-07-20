import os
import sys
import uuid
import json
import pandas as pd
from datetime import datetime
from threading import Thread
from flask import Flask, request, jsonify, render_template, redirect, url_for, session, send_file, make_response
from dotenv import load_dotenv

# Get the project root directory
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.append(PROJECT_ROOT)
sys.path.append(os.path.join(PROJECT_ROOT, "backend"))

# Load environment variables
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

# Flask App Initializer with custom directories
app = Flask(
    __name__, 
    template_folder=os.path.join("frontend", "templates"),
    static_folder=os.path.join("frontend", "static")
)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "compliance-auditor-pro-secret-key-1337")

# Configure CORS for decoupled frontend deployment (Netlify/Vercel -> Northflank backend)
BACKEND_URL = os.environ.get("BACKEND_URL", "https://customer-call-auditor--29hk88kg4w4g.code.run")
try:
    from flask_cors import CORS
    CORS(app, supports_credentials=True, origins=[BACKEND_URL, "http://localhost:7860"])
except ImportError:
    pass



# Global variables for background task monitoring
TASKS = {}

# Import backend modules
from backend.scoring_engine import score_email, run_average_audit
from backend.extract_emails import extract_selected_emails
from backend.redaction import redact_pii

# Fpdf2 import
try:
    from fpdf import FPDF
except ImportError:
    FPDF = None

# PDF clean helper to prevent font errors
def clean_pdf_text(text):
    if not text: 
        return ""
    import string
    allowed_chars = string.printable
    cleaned = "".join(c for c in str(text) if c in allowed_chars)
    cleaned = cleaned.replace('\u201c', '"').replace('\u201d', '"').replace('\u2018', "'").replace('\u2019', "'")
    return cleaned
# ================= USER STORAGE & AUTHENTICATION =================
import hashlib
USERS_FILE = os.path.join(PROJECT_ROOT, "data", "users.json")

def hash_password(password):
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def load_users():
    if not os.path.exists(USERS_FILE):
        os.makedirs(os.path.dirname(USERS_FILE), exist_ok=True)
        with open(USERS_FILE, 'w') as f:
            json.dump({}, f)
        return {}
    try:
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading users: {e}")
        return {}

def save_users(users):
    try:
        with open(USERS_FILE, 'w') as f:
            json.dump(users, f, indent=4)
        return True
    except Exception as e:
        print(f"Error saving users: {e}")
        return False

def create_user(username, password, organization):
    users = load_users()
    if username in users:
        return False, "Username already exists"
    
    users[username] = {
        "password_hash": hash_password(password),
        "organization": organization
    }
    save_users(users)
    return True, "Account created successfully"

def authenticate_user(username, password):
    # First check environmental variable default admin
    env_user = os.getenv('AUTH_USERNAME', 'admin')
    env_pass = os.getenv('AUTH_PASSWORD', 'admin123')
    if username == env_user and password == env_pass:
        return True, "Default"
        
    users = load_users()
    if username in users:
        user_data = users[username]
        if user_data.get("password_hash") == hash_password(password):
            return True, user_data.get("organization", "Default")
            
    return False, None

# ================= AUTHENTICATION DECORATOR =================
def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ================= CORE WEB ROUTING =================
@app.route('/')
def index():
    if 'logged_in' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        authenticated, organization = authenticate_user(username, password)
        if authenticated:
            session['logged_in'] = True
            session['username'] = username
            session['organization'] = organization
            return redirect(url_for('dashboard'))
        else:
            return redirect(url_for('login', error=True))
            
    return render_template('login.html')

@app.route('/register', methods=['POST'])
def register():
    if request.is_json:
        data = request.get_json()
    else:
        data = request.form
        
    username = data.get('username')
    password = data.get('password')
    organization = data.get('organization')
    
    if not username or not password or not organization:
        if request.is_json:
            return jsonify({"success": False, "error": "All fields are required"})
        return redirect(url_for('login', error="All fields are required"))
        
    username = username.strip()
    organization = organization.strip()
    
    if len(username) < 3:
        if request.is_json:
            return jsonify({"success": False, "error": "Username must be at least 3 characters"})
        return redirect(url_for('login', error="Username too short"))
        
    if len(password) < 6:
        if request.is_json:
            return jsonify({"success": False, "error": "Password must be at least 6 characters"})
        return redirect(url_for('login', error="Password too short"))

    success, message = create_user(username, password, organization)
    if success:
        session['logged_in'] = True
        session['username'] = username
        session['organization'] = organization
        
        if request.is_json:
            return jsonify({"success": True, "message": message})
        return redirect(url_for('dashboard'))
    else:
        if request.is_json:
            return jsonify({"success": False, "error": message})
        return redirect(url_for('login', error=message))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    username = session.get('username', 'Administrator')
    organization = session.get('organization', 'Default')
    initials = (username[:2].upper()) if username else "AD"
    return render_template('dashboard.html', username=username, organization=organization, initials=initials)

@app.route('/api/user-info')
def user_info():
    if 'logged_in' in session:
        username = session.get('username', 'Administrator')
        organization = session.get('organization', 'Default')
        initials = (username[:2].upper()) if username else "AD"
        return jsonify({
            "logged_in": True,
            "username": username,
            "organization": organization,
            "initials": initials
        })
    return jsonify({"logged_in": False})


# ================= COMPLIANCE DATA ACCESS HELPERS =================
def initialize_audit_csv():
    csv_path = os.path.join(PROJECT_ROOT, "data", "audit_results.csv")
    if not os.path.exists(csv_path):
        os.makedirs(os.path.dirname(csv_path), exist_ok=True)
        column_order = ['Chunk', 'empathy', 'professionalism', 'compliance', 'reason', 'violations', 'suggestions', 'evaluation', 'Agent', 'masking_score', 'masking_analysis', 'Source', 'Transcript', 'Filename', 'Organization']
        df = pd.DataFrame(columns=column_order)
        df.to_csv(csv_path, index=False)

# Ensure data structure exists on app startup
initialize_audit_csv()


def read_audit_data():
    csv_path = os.path.join(PROJECT_ROOT, "data", "audit_results.csv")
    if not os.path.exists(csv_path):
        initialize_audit_csv()
        
    try:
        df = pd.read_csv(csv_path)
        if df is not None:
            df['empathy'] = pd.to_numeric(df['empathy'], errors='coerce')
            df['professionalism'] = pd.to_numeric(df['professionalism'], errors='coerce')
            if 'masking_score' not in df.columns:
                df['masking_score'] = 100
            if 'Transcript' not in df.columns:
                df['Transcript'] = "Historical data: Transcript not saved."
            if 'Source' not in df.columns:
                df['Source'] = 'Audio'
            if 'Filename' not in df.columns:
                df['Filename'] = "N/A"
            if 'Organization' not in df.columns:
                df['Organization'] = "Default"
            df['masking_score'] = pd.to_numeric(df['masking_score'], errors='coerce').fillna(100)
            df['Organization'] = df['Organization'].fillna("Default")
            df = df.dropna(subset=['empathy', 'professionalism'])
            
            # Filter by logged-in user's organization if session exists
            if 'logged_in' in session:
                org = session.get('organization', 'Default')
                df = df[df['Organization'] == org]
        return df
    except Exception as e:
        print(f"Error reading audit_results.csv: {e}")
        return pd.DataFrame()

# ================= REST API ENDPOINTS =================

@app.route('/api/default-imap', methods=['GET'])
@login_required
def default_imap():
    return jsonify({
        "server": os.getenv("IMAP_SERVER", ""),
        "port": os.getenv("IMAP_PORT", "993"),
        "email": os.getenv("IMAP_EMAIL", "")
    })

@app.route('/api/stats', methods=['GET'])
@login_required
def get_dashboard_stats():
    df = read_audit_data()
    if df.empty:
        return jsonify({
            "team_empathy_avg": 0.0,
            "team_prof_avg": 0.0,
            "total_audits": 0,
            "agent_performances": [],
            "top_violations": [],
            "recent_audits": [],
            "agents": []
        })

    # FINAL row holds overall scores for an audit session
    team_final = df[df['Chunk'] == 'FINAL']
    
    avg_empathy = team_final['empathy'].mean() if not team_final.empty else 0.0
    avg_prof = team_final['professionalism'].mean() if not team_final.empty else 0.0
    total_audits = len(team_final)

    # Agent summary metrics comparison
    agent_performances = []
    if not team_final.empty:
        grouped = team_final.groupby('Agent')[['empathy', 'professionalism']].mean().reset_index()
        agent_performances = grouped.to_dict(orient='records')

    # Top violations frequency counts
    all_violations = []
    for v_str in team_final['violations']:
        if pd.notna(v_str) and str(v_str).strip() != "None" and str(v_str).strip() != "":
            all_violations.extend([v.strip() for v in str(v_str).split('|')])
            
    top_violations = []
    if all_violations:
        vc = pd.Series(all_violations).value_counts().head(5)
        top_violations = [{"violation": v, "count": int(c)} for v, c in vc.items()]

    # Recent completed audits history
    recent_audits = []
    if not team_final.empty:
        # Sort descending by index (most recent first) and select up to 15
        summary_raw = team_final[['Agent', 'empathy', 'professionalism', 'compliance', 'Source']].copy()
        summary_raw = summary_raw.replace("None", pd.NA).dropna(subset=['Agent', 'empathy', 'professionalism'])
        # Show recent items
        recent_audits = summary_raw.tail(15).to_dict(orient='records')
        recent_audits.reverse()

    # List of all unique agents
    agents_list = sorted(df['Agent'].dropna().unique().tolist())

    return jsonify({
        "team_empathy_avg": float(avg_empathy),
        "team_prof_avg": float(avg_prof),
        "total_audits": int(total_audits),
        "agent_performances": agent_performances,
        "top_violations": top_violations,
        "recent_audits": recent_audits,
        "agents": agents_list
    })

@app.route('/api/agent-metrics/<agent_name>', methods=['GET'])
@login_required
def get_agent_metrics(agent_name):
    df = read_audit_data()
    if df.empty:
        return jsonify({"success": False, "error": "No audit records found"})

    agent_data = df[df['Agent'] == agent_name]
    agent_final = agent_data[agent_data['Chunk'] == 'FINAL']

    if agent_final.empty:
        return jsonify({"success": False, "error": f"No completed audits for {agent_name}"})

    # Calculations
    avg_empathy = agent_final['empathy'].mean()
    avg_prof = agent_final['professionalism'].mean()
    
    total_audio = len(agent_final[agent_final['Source'] == 'Audio'])
    total_email = len(agent_final[agent_final['Source'] == 'Email'])
    total_convos = total_audio + total_email

    overall_avg = (avg_empathy + avg_prof) / 2
    compliance = "PASS" if overall_avg >= 80 else "WARN" if overall_avg >= 60 else "FAIL"

    # Sum masking counts
    total_pii_masked = 0
    import re
    for m_analysis in agent_final['masking_analysis']:
        if pd.notna(m_analysis):
            nums = re.findall(r'\d+', str(m_analysis))
            total_pii_masked += sum(int(n) for n in nums)

    # Top violations logic
    all_v = []
    for v_str in agent_final['violations']:
        if pd.notna(v_str) and str(v_str).strip() != "None" and str(v_str).strip() != "":
            all_v.extend([v.strip() for v in str(v_str).split('|')])
    top_violations = []
    if all_v:
        vc = pd.Series(all_v).value_counts().head(5)
        top_violations = [[v, int(c)] for v, c in vc.items()]

    # Top suggestions logic
    all_s = []
    for s_str in agent_final['suggestions']:
        if pd.notna(s_str) and str(s_str).strip() != "None" and str(s_str).strip() != "":
            all_s.extend([s.strip() for s in str(s_str).split('|')])
    top_suggestions = []
    if all_s:
        sc = pd.Series(all_s).value_counts().head(5)
        top_suggestions = [[s, int(c)] for s, c in sc.items()]

    # History of conversations logs
    history = agent_final.sort_index(ascending=False).head(10)[['Source', 'compliance', 'empathy', 'professionalism', 'reason', 'Transcript', 'masking_analysis']].to_dict(orient='records')

    # Apply live masking display safeguard
    for h in history:
        raw_t = h.get('Transcript', '')
        if raw_t and raw_t != 'Historical data: Transcript not saved.':
            h['Transcript'] = redact_pii(str(raw_t))['redacted_text']

    return jsonify({
        "success": True,
        "empathy": float(avg_empathy),
        "professionalism": float(avg_prof),
        "compliance": compliance,
        "total_pii_masked": total_pii_masked,
        "total_convos": total_convos,
        "total_audio": total_audio,
        "total_email": total_email,
        "top_violations": top_violations,
        "top_suggestions": top_suggestions,
        "history": history
    })

# ================= BACKGROUND AUDIT PROCESSOR FOR AUDIO =================
def async_audit_pipeline(task_id, audio_path, agent_name, language, organization="Default"):
    global TASKS
    TASKS[task_id] = {"status": "Initializing modules...", "progress": 5, "complete": False, "error": None}
    
    try:
        from backend.transcribe import transcribe_audio
        from backend.clean_transcript import label_speakers
        
        # 1. Transcribe audio
        TASKS[task_id]["status"] = "Transcribing Call Audio (Groq Whisper-v3)..."
        TASKS[task_id]["progress"] = 25
        raw_text = transcribe_audio(audio_path, language=None if language == "auto-detect" else language)
        
        data_dir = os.path.join(PROJECT_ROOT, "data")
        os.makedirs(data_dir, exist_ok=True)
        raw_transcript_path = os.path.join(data_dir, "1_raw_transcript.txt")
        with open(raw_transcript_path, "w", encoding="utf-8") as f:
            f.write(raw_text)
            
        # 2. Label Speakers
        TASKS[task_id]["status"] = "Labeling Speakers (Diarization)..."
        TASKS[task_id]["progress"] = 55
        labeled_text = label_speakers(raw_text)
        
        # 3. Redact PII
        TASKS[task_id]["status"] = "Redacting Sensitive Customer PII..."
        TASKS[task_id]["progress"] = 75
        masking_result = redact_pii(labeled_text)
        redacted_text = masking_result["redacted_text"]
        
        labeled_transcript_path = os.path.join(data_dir, "3_labeled_dialogue.txt")
        with open(labeled_transcript_path, "w", encoding="utf-8") as f:
            f.write(redacted_text)
            
        # 4. Score Compliance
        TASKS[task_id]["status"] = "Running Compliance Scoring Engine..."
        TASKS[task_id]["progress"] = 90
        run_average_audit(
            labeled_transcript_path, 
            agent_name=agent_name, 
            masking_score=masking_result["masking_score"],
            masking_analysis=masking_result["analysis"],
            filename=os.path.basename(audio_path),
            redacted_transcript=masking_result["redacted_text"],
            organization=organization
        )
        
        # Cleanup uploaded temp file
        try:
            os.remove(audio_path)
        except Exception:
            pass
            
        TASKS[task_id]["status"] = "Auditing Completed!"
        TASKS[task_id]["progress"] = 100
        TASKS[task_id]["complete"] = True
        
    except Exception as e:
        TASKS[task_id]["error"] = str(e)
        TASKS[task_id]["status"] = "Audit Failed"
        print(f"CRITICAL in async thread: {e}")

@app.route('/api/upload-audio', methods=['POST'])
@login_required
def upload_audio():
    if 'audioFile' not in request.files:
        return jsonify({"success": False, "error": "No file uploaded"})
        
    file = request.files['audioFile']
    agent_name = request.form.get('agentName', 'Unknown Agent')
    language = request.form.get('language', 'auto-detect')

    if file.filename == '':
        return jsonify({"success": False, "error": "No file selected"})

    if file:
        upload_dir = os.path.join(PROJECT_ROOT, "data", "uploads")
        os.makedirs(upload_dir, exist_ok=True)
        
        # Generate temporary unique name
        temp_filename = f"{uuid.uuid4().hex}_{file.filename}"
        temp_path = os.path.join(upload_dir, temp_filename)
        file.save(temp_path)
        
        # Launch background worker
        task_id = str(uuid.uuid4())
        organization = session.get('organization', 'Default')
        thread = Thread(target=async_audit_pipeline, args=(task_id, temp_path, agent_name, language, organization))
        thread.daemon = True
        thread.start()
        
        return jsonify({"success": True, "task_id": task_id})
        
    return jsonify({"success": False, "error": "Upload failed"})

@app.route('/api/task-status/<task_id>', methods=['GET'])
@login_required
def task_status(task_id):
    task = TASKS.get(task_id, {"status": "Task not found", "progress": 0, "complete": False, "error": "Unknown Task ID"})
    return jsonify(task)

# ================= EMAIL AUDITING API ENDPOINTS =================

@app.route('/api/manual-score-email', methods=['POST'])
@login_required
def manual_score_email():
    data = request.get_json()
    if not data or 'emailText' not in data:
        return jsonify({"success": False, "error": "No email context provided"})
        
    agent_name = data.get('agentName', 'Unknown Agent')
    email_text = data.get('emailText')
    
    try:
        filename_label = f"Email_Manual_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        organization = session.get('organization', 'Default')
        result = score_email(email_text, agent_name=agent_name, filename=filename_label, organization=organization)
        
        # Return properly structured lists
        violations = result.get('violations', [])
        suggestions = result.get('suggestions', [])
        
        # Safeguards if response string formatting happens instead of lists
        if isinstance(violations, str): violations = [violations]
        if isinstance(suggestions, str): suggestions = [suggestions]

        formatted_result = {
            "empathy": result.get("empathy", 0),
            "professionalism": result.get("professionalism", 0),
            "compliance": result.get("compliance", "Fail"),
            "reason": result.get("reason", "No details"),
            "violations": violations if violations else ["None"],
            "suggestions": suggestions if suggestions else ["None"]
        }
        
        return jsonify({"success": True, "result": formatted_result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/extract-imap-email', methods=['POST'])
@login_required
def extract_imap_email():
    data = request.get_json()
    agent_name = data.get('agentName', 'Unknown Agent')
    server = data.get('server')
    port = data.get('port')
    email_user = data.get('email')
    email_pass = data.get('password')
    folder = data.get('folder', 'INBOX')

    # Connect using IMAP extractor script
    res = extract_selected_emails(
        server=server,
        port=port,
        email_user=email_user,
        email_pass=email_pass,
        folder=folder
    )
    
    if not res["success"]:
        return jsonify({"success": False, "error": res["error"]})

    email_data = res["data"]
    
    try:
        filename_label = f"Email_IMAP_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        organization = session.get('organization', 'Default')
        result = score_email(email_data["body"], agent_name=agent_name, filename=filename_label, organization=organization)
        
        violations = result.get('violations', [])
        suggestions = result.get('suggestions', [])
        
        if isinstance(violations, str): violations = [violations]
        if isinstance(suggestions, str): suggestions = [suggestions]

        formatted_result = {
            "empathy": result.get("empathy", 0),
            "professionalism": result.get("professionalism", 0),
            "compliance": result.get("compliance", "Fail"),
            "reason": result.get("reason", "No details"),
            "violations": violations if violations else ["None"],
            "suggestions": suggestions if suggestions else ["None"]
        }
        
        return jsonify({"success": True, "result": formatted_result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

# ================= AI GENERATED TRAINING ROADMAP =================

@app.route('/api/generate-roadmap', methods=['POST'])
@login_required
def generate_coaching_roadmap():
    df = read_audit_data()
    team_final = df[df['Chunk'] == 'FINAL']
    
    team_suggestions = []
    for s_str in team_final['suggestions']:
        if pd.notna(s_str) and str(s_str).strip() != "None" and str(s_str).strip() != "":
            team_suggestions.extend([s.strip() for s in str(s_str).split('|') if s.strip()])
            
    if not team_suggestions:
        return jsonify({"success": False, "error": "Add more audit logs to cluster improvement suggestions."})
        
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return jsonify({"success": False, "error": "GROQ_API_KEY is not configured in .env file"})

    try:
        from groq import Groq
        client = Groq(api_key=api_key)
        unique_suggestions = list(set(team_suggestions))
        
        prompt = f"""
        Analyze these individual coaching suggestions collected from multiple customer service agent audits:
        {unique_suggestions}
        
        Categorize these into 3-5 high-level 'Training Modules'. 
        For each module, provide:
        1. A catchy 'Module Name'
        2. A brief 'Core Objective'
        3. 3-4 'Specific Actionable Steps' for the agents to follow.
        4. Mention which specific common mistakes this module addresses.
        
        Format the response clearly using Markdown (headers, bullet points, and bold text).
        Do not add code blocks or extra text wrapper.
        """
        
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
        )
        roadmap = response.choices[0].message.content
        session['coaching_roadmap'] = roadmap
        
        return jsonify({"success": True, "roadmap": roadmap})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

# ================= DOWNLOADS GENERATION AND ROUTING =================

@app.route('/api/download-csv', methods=['GET'])
@login_required
def download_csv():
    df = read_audit_data() # Already filtered by organization!
    if df.empty:
        column_order = ['Chunk', 'empathy', 'professionalism', 'compliance', 'reason', 'violations', 'suggestions', 'evaluation', 'Agent', 'masking_score', 'masking_analysis', 'Source', 'Transcript', 'Filename', 'Organization']
        df = pd.DataFrame(columns=column_order)
    
    org_name = session.get('organization', 'Default')
    response = make_response(df.to_csv(index=False))
    response.headers.set('Content-Type', 'text/csv')
    response.headers.set('Content-Disposition', 'attachment', filename=f"audit_results_{org_name}.csv")
    return response

@app.route('/api/download-roadmap-pdf', methods=['POST'])
@login_required
def download_roadmap_pdf():
    roadmap = session.get('coaching_roadmap')
    if not roadmap:
        return make_response("No generated roadmap in session. Please run roadmap generation first.", 400)
        
    if not FPDF:
        return make_response("FPDF library is not loaded", 500)

    try:
        class CoachingPDF(FPDF):
            def header(self):
                self.set_font('Arial', 'B', 16)
                self.cell(0, 10, 'AI-Driven Coaching Roadmap', 0, 1, 'C')
                self.ln(5)
            def footer(self):
                self.set_y(-15)
                self.set_font('Arial', 'I', 8)
                self.cell(0, 10, f'Generated on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} | Page ' + str(self.page_no()), 0, 0, 'C')

        pdf = CoachingPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=11)
        
        lines = roadmap.split('\n')
        for line in lines:
            try:
                clean_line = clean_pdf_text(line)
                if not clean_line.strip() and not line.strip():
                    pdf.ln(4)
                    continue
                    
                if line.startswith('# '):
                    pdf.set_font("Arial", 'B', 14)
                    pdf.cell(0, 8, clean_line.replace('# ', ''), ln=1)
                    pdf.set_font("Arial", size=11)
                elif line.startswith('## '):
                    pdf.set_font("Arial", 'B', 13)
                    pdf.cell(0, 8, clean_line.replace('## ', ''), ln=1)
                    pdf.set_font("Arial", size=11)
                elif line.startswith('### '):
                    pdf.set_font("Arial", 'B', 12)
                    pdf.cell(0, 7, clean_line.replace('### ', ''), ln=1)
                    pdf.set_font("Arial", size=11)
                else:
                    if clean_line.strip():
                        pdf.multi_cell(0, 6, clean_line)
            except Exception as e:
                print(f"Skipping PDF row error: {e}")
                
        pdf_output = pdf.output(dest='S')
        
        response = make_response(bytes(pdf_output))
        response.headers.set('Content-Type', 'application/pdf')
        response.headers.set('Content-Disposition', 'attachment', filename=f"Coaching_Roadmap_{datetime.now().strftime('%Y%m%d')}.pdf")
        return response
    except Exception as e:
        return make_response(f"PDF creation failed: {e}", 500)

@app.route('/api/download-summary-pdf', methods=['POST'])
@login_required
def download_summary_pdf():
    df = read_audit_data()
    team_final = df[df['Chunk'] == 'FINAL']
    
    if team_final.empty:
        return make_response("No audit records to summarize.", 400)
        
    if not FPDF:
        return make_response("FPDF library is not loaded", 500)

    try:
        class SummaryPDF(FPDF):
            def header(self):
                self.set_font('Arial', 'B', 14)
                self.cell(0, 10, 'Team Compliance Summary Report', 0, 1, 'C')
                self.ln(5)
            def footer(self):
                self.set_y(-15)
                self.set_font('Arial', 'I', 8)
                self.cell(0, 10, f'Page ' + str(self.page_no()), 0, 0, 'C')

        pdf = SummaryPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=11)
        
        # Metadata
        pdf.cell(0, 8, f"Total Audits Performed: {len(team_final)}", ln=1)
        pdf.cell(0, 8, f"Team Average Empathy: {team_final['empathy'].mean():.2f}", ln=1)
        pdf.cell(0, 8, f"Team Average Professionalism: {team_final['professionalism'].mean():.2f}", ln=1)
        pdf.ln(8)
        
        # Table Header
        pdf.set_font("Arial", 'B', 11)
        pdf.cell(60, 10, 'Agent', border=1)
        pdf.cell(40, 10, 'Avg Empathy', border=1)
        pdf.cell(40, 10, 'Avg Professionalism', border=1)
        pdf.cell(40, 10, 'Compliance', border=1, ln=1)
        
        pdf.set_font("Arial", size=10)
        agent_table = team_final.groupby('Agent')[['empathy', 'professionalism']].mean().reset_index()
        
        for _, row in agent_table.iterrows():
            pdf.cell(60, 10, clean_pdf_text(row['Agent']), border=1)
            pdf.cell(40, 10, f"{row['empathy']:.1f}", border=1)
            pdf.cell(40, 10, f"{row['professionalism']:.1f}", border=1)
            
            avg = (row['empathy'] + row['professionalism']) / 2
            comp = "PASS" if avg >= 80 else "WARN" if avg >= 60 else "FAIL"
            pdf.cell(40, 10, comp, border=1, ln=1)
            
        pdf_output = pdf.output(dest='S')
        
        response = make_response(bytes(pdf_output))
        response.headers.set('Content-Type', 'application/pdf')
        response.headers.set('Content-Disposition', 'attachment', filename=f"Team_Audit_Summary_{datetime.now().strftime('%Y%m%d')}.pdf")
        return response
    except Exception as e:
        return make_response(f"PDF creation failed: {e}", 500)

# ================= RUN SERVER RUN =================
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 7860))
    # Initialize the data storage structures
    initialize_audit_csv()
    
    app.run(host='0.0.0.0', port=port, debug=True)
