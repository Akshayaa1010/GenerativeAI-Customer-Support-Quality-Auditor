import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
import os
import subprocess
import sys
import json
import importlib

# Streamlit Cloud Deployment Helper for Playwright
if os.environ.get("STREAMLIT_RUNTIME_HOST"):
    try:
        import subprocess
        subprocess.run(["playwright", "install", "chromium"], check=True)
    except Exception as e:
        st.error(f"Playwright installation failed: {e}")

# Get the project root directory and add to path early
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)
if BACKEND_DIR not in sys.path:
    sys.path.append(BACKEND_DIR)

from dotenv import load_dotenv
from backend.redaction import redact_pii

# Load environment variables from .env
load_dotenv()

# Force reload of scoring engine to ensure updated signature is used

import backend.scoring_engine
importlib.reload(backend.scoring_engine)
from backend.scoring_engine import score_email

# DEBUG: Check scoring_engine location
print(f"DEBUG: scoring_engine loaded from {backend.scoring_engine.__file__}")

try:
    from fpdf import FPDF
except ImportError:
    # Fallback if fpdf2 is not yet installed in the current runtime
    FPDF = None

st.set_page_config(page_title="Compliance Audit Dashboard", layout="wide", initial_sidebar_state="expanded")

# Dark Mode Styling
st.markdown("""
    <style>
        :root {
            --primary-color: #1f77b4;
            --text-color: #f0f2f6;
            --background-color: #0e1117;
        }
        
        [data-testid="stAppViewContainer"] {
            background-color: #0e1117;
            color: #f0f2f6;
        }
        
        [data-testid="stSidebar"] {
            background-color: #161b22;
        }
        
        .main {
            background-color: #0e1117;
        }
        
        h1, h2, h3, h4, h5, h6 {
            color: #58a6ff !important;
        }
        
        [data-testid="stMetricValue"] {
            color: #58a6ff;
        }
        
        [data-testid="stMetricLabel"] {
            color: #f0f2f6;
        }
        
        [data-testid="stMetricContainer"] {
            border: 1px solid #30363d;
            border-radius: 8px;
            padding: 12px;
            background-color: #161b22;
        }
        
        .info-box {
            background-color: #161b22;
            border-left: 4px solid #58a6ff;
            padding: 12px;
        }
        
        .success-box {
            background-color: #161b22;
            border-left: 4px solid #3fb950;
            padding: 12px;
        }
        
        .error-box {
            background-color: #161b22;
            border-left: 4px solid #f85149;
            padding: 12px;
        }
        
        [data-testid="stDataFrame"] {
            background-color: #0e1117;
        }
        
        .stDataFrame {
            background-color: #161b22;
        }
        
        [data-testid="stDownloadButton"] {
            border: 1px solid #30363d;
        }
        
        /* Navigation and Sidebar text visibility */
        [data-testid="stSidebar"] label,
        [data-testid="stSidebar"] span,
        [data-testid="stSidebar"] p,
        .stRadio > label,
        .stSelectbox label,
        .stSelectbox span {
            color: #f0f2f6 !important;
        }
        
        /* Selectbox dropdown text */
        [data-baseweb="select"] {
            color: #f0f2f6 !important;
        }
        
        [data-baseweb="select"] > div {
            color: #f0f2f6 !important;
        }
        
        /* Ensure selectbox option text is visible */
        [data-baseweb="popover"] {
            color: #f0f2f6 !important;
        }
        
        /* Fix for all text in sidebar */
        .sidebar-text {
            color: #f0f2f6 !important;
        }
        
        /* Info/Success/Error/Warning containers text */
        [data-testid="stMarkdownContainer"] {
            color: #f0f2f6 !important;
        }
        
        [data-testid="stMarkdownContainer"] p,
        [data-testid="stMarkdownContainer"] span,
        [data-testid="stMarkdownContainer"] li,
        [data-testid="stMarkdownContainer"] strong,
        [data-testid="stMarkdownContainer"] em {
            color: #f0f2f6 !important;
        }
        
        /* Info box text */
        [data-testid="stInfo"] {
            color: #f0f2f6 !important;
        }
        
        [data-testid="stInfo"] > div {
            color: #f0f2f6 !important;
        }
        
        [data-testid="stInfo"] span,
        [data-testid="stInfo"] p,
        [data-testid="stInfo"] strong {
            color: #f0f2f6 !important;
        }
        
        /* Success box text */
        [data-testid="stSuccess"] {
            color: #f0f2f6 !important;
        }
        
        [data-testid="stSuccess"] > div,
        [data-testid="stSuccess"] span,
        [data-testid="stSuccess"] p {
            color: #f0f2f6 !important;
        }
        
        /* Error box text */
        [data-testid="stError"] {
            color: #f0f2f6 !important;
        }
        
        [data-testid="stError"] > div,
        [data-testid="stError"] span,
        [data-testid="stError"] p {
            color: #f0f2f6 !important;
        }
        
        /* Warning box text */
        [data-testid="stWarning"] {
            color: #f0f2f6 !important;
        }
        
        [data-testid="stWarning"] > div,
        [data-testid="stWarning"] span,
        [data-testid="stWarning"] p {
            color: #f0f2f6 !important;
        }
        
        /* Button styling */
        button {
            background-color: #238636 !important;
            color: #f0f2f6 !important;
            border: 1px solid #3fb950 !important;
        }
        
        button:hover {
            background-color: #2ea043 !important;
            color: #f0f2f6 !important;
        }
        
        [data-testid="stBaseButton-secondary"] {
            background-color: #238636 !important;
            color: #f0f2f6 !important;
        }
        
        [data-testid="stBaseButton-secondary"]:hover {
            background-color: #2ea043 !important;
        }
        
        /* Selectbox styling */
        [data-baseweb="select"] > div:first-child {
            background-color: #161b22 !important;
            border-color: #30363d !important;
            color: #f0f2f6 !important;
        }
        
        [data-baseweb="input"] {
            background-color: #161b22 !important;
            border-color: #30363d !important;
            color: #f0f2f6 !important;
        }
        
        /* Dropdown menu styling */
        [data-baseweb="menu"] {
            background-color: #161b22 !important;
            color: #f0f2f6 !important;
        }
        
        [data-baseweb="menu"] li {
            color: #f0f2f6 !important;
        }
        
        [data-baseweb="menu"] li:hover {
            background-color: #30363d !important;
        }
        
        /* Option styling in dropdowns */
        [data-baseweb="option"] {
            color: #f0f2f6 !important;
            background-color: #161b22 !important;
        }
        
        /* Selectbox value text */
        [data-baseweb="select"] span {
            color: #f0f2f6 !important;
        }
        
        [data-baseweb="select"] div {
            color: #f0f2f6 !important;
        }
        
        /* Dropdown options list items */
        [role="option"] {
            color: #f0f2f6 !important;
            background-color: #161b22 !important;
        }
        
        [role="option"]:hover {
            background-color: #30363d !important;
            color: #f0f2f6 !important;
        }
        
        /* Plotly chart text labels */
        text {
            fill: #f0f2f6 !important;
            color: #f0f2f6 !important;
        }
        
        .slice text,
        .pietext,
        [data-testid="plotly-chart"] text {
            fill: #f0f2f6 !important;
            font-weight: bold;
        }
        
        /* SVG text in Plotly charts */
        svg text {
            fill: #f0f2f6 !important;
            color: #f0f2f6 !important;
        }
        
        /* Selectbox dropdown content */
        [data-baseweb="select"] [role="listbox"] {
            background-color: #161b22 !important;
        }
        
        [data-baseweb="select"] [role="option"] {
            color: #f0f2f6 !important;
            background-color: #161b22 !important;
        }
        
        /* Ensure select value is readable */
        [data-baseweb="select"] > div > div {
            color: #f0f2f6 !important;
        }
        
        /* All container text */
        div {
            color: #f0f2f6 !important;
        }

        /* Bold Pastel Metric Boxes */
        .metric-container {
            border-radius: 12px;
            padding: 15px;
            text-align: center;
            margin: 5px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.3);
            border: 2px solid rgba(255,255,255,0.1);
            min-height: 140px;
            display: flex;
            flex-direction: column;
            justify-content: center;
        }
        .metric-title {
            font-size: 0.9rem;
            font-weight: 800;
            margin-bottom: 5px;
            color: #161b22 !important;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        .metric-value {
            font-size: 1.8rem;
            font-weight: 900;
            color: #161b22 !important;
        }
        .metric-sub {
            font-size: 0.8rem;
            font-weight: 600;
            color: #161b22 !important;
            opacity: 0.8;
        }
        .pastel-blue { background-color: #a2d2ff !important; }
        .pastel-green { background-color: #b9fbc0 !important; }
        .pastel-yellow { background-color: #fbf8cc !important; }
        .pastel-purple { background-color: #e2c2ff !important; }
        .pastel-orange { background-color: #ffccac !important; }
    </style>
""", unsafe_allow_html=True)

# Add a helper for PDF text cleaning (safest possible version)
def clean_pdf_text(text):
    if not text: return ""
    # Only allow standard printable ASCII characters to prevent FPDF font/layout crashes
    import string
    allowed_chars = string.printable
    cleaned = "".join(c for c in str(text) if c in allowed_chars)
    # Replace common MS-Word style curly quotes/long dashes if they slipped through
    cleaned = cleaned.replace('\u201c', '"').replace('\u201d', '"').replace('\u2018', "'").replace('\u2019', "'")
    return cleaned

st.title("📊 Compliance Audit Dashboard")

# Initialize audit results if not present
def initialize_audit_results():
    csv_path = os.path.join(PROJECT_ROOT, "data", "audit_results.csv")
    if not os.path.exists(csv_path):
        # Create an empty CSV with correct headers instead of failing
        column_order = ['Chunk', 'empathy', 'professionalism', 'compliance', 'reason', 'violations', 'suggestions', 'evaluation', 'Agent', 'masking_score', 'masking_analysis', 'Source', 'Transcript', 'Filename']
        df = pd.DataFrame(columns=column_order)
        df.to_csv(csv_path, index=False)
        st.info("No previous audit data found. Starting with a fresh dashboard.")
    return True

# Load the CSV file
@st.cache_data
def load_data():
    try:
        csv_path = os.path.join(PROJECT_ROOT, "data", "audit_results.csv")
        df = pd.read_csv(csv_path)
        # Force numeric types for scoring columns to prevent crashes on corrupted data
        if df is not None:
            df['empathy'] = pd.to_numeric(df['empathy'], errors='coerce')
            df['professionalism'] = pd.to_numeric(df['professionalism'], errors='coerce')
            # Add new columns if missing in older CSV files
            if 'masking_score' not in df.columns:
                df['masking_score'] = 100
            # Fill missing Transcripts/Source with resilience logic
            def clean_transcript(t):
                if pd.isna(t) or str(t).strip() == "" or str(t).lower() == "nan" or str(t).lower() == "none":
                    return "Historical data: Transcript not saved."
                return t
            
            if 'Transcript' not in df.columns:
                df['Transcript'] = "Historical data: Transcript not saved."
            else:
                df['Transcript'] = df['Transcript'].apply(clean_transcript)
                
            if 'Source' not in df.columns:
                df['Source'] = 'Audio'
            else:
                # Intelligent historical source tagging for any remaining NaNs or Audio-defaults
                df.loc[df['Chunk'] == 'EMAIL', 'Source'] = 'Email'
                df.loc[(df['Chunk'] == 'FINAL') & (df['Source'].isna()) & (df['reason'] != 'Final average scores'), 'Source'] = 'Email'
                df['Source'] = df['Source'].fillna('Audio')
            
            if 'Filename' not in df.columns:
                df['Filename'] = "N/A"
            else:
                df['Filename'] = df['Filename'].fillna("N/A")
                
            df['masking_score'] = pd.to_numeric(df['masking_score'], errors='coerce').fillna(100)
            # Filter out any rows that failed conversion (highly unlikely with the fixed backend)
            df = df.dropna(subset=['empathy', 'professionalism'])
        return df
    except FileNotFoundError:
        st.error("audit_results.csv not found. Please run scoring_engine.py first.")
        return None

# Initialize audit results on first run, then load
if initialize_audit_results():
    df = load_data()
    # Add Agent column if missing in old data (for backward compatibility)
    if df is not None and 'Agent' not in df.columns:
        df.insert(0, 'Agent', 'Historical Agent')
else:
    df = None

if df is not None:
    # Sidebar navigation
    st.sidebar.title("Navigation")
    page = st.sidebar.radio("Select a page:", ["🏠 Home", "📊 Reports", "📧 Email Analysis", "🕵️ Agent Wise Analysis"])
    
    st.sidebar.markdown("---")
    
    # Global Agent Filter (Optional depending on page)
    agents = df['Agent'].unique().tolist()
    if page in ["📊 Reports", "🔍 Chunk-wise Analysis"]:
        selected_agent = st.sidebar.selectbox("Filter by Agent:", agents)
        active_df = df[df['Agent'] == selected_agent].copy()
    else:
        active_df = df.copy()

    # Separate final row from chunk data for the active set
    final_rows = active_df[active_df['Chunk'] == 'FINAL']
    chunk_df = active_df[active_df['Chunk'] != 'FINAL'].copy()
    
    # Convert chunk to numeric safely
    chunk_df['Chunk'] = pd.to_numeric(chunk_df['Chunk'], errors='coerce')
    
    if not final_rows.empty:
        # Take the most recent audit if multiple exist for same agent
        latest_final = final_rows.iloc[-1]
        final_empathy = latest_final['empathy']
        final_professionalism = latest_final['professionalism']
        final_compliance = latest_final['compliance']
        final_violations = latest_final['violations'] if 'violations' in latest_final else "None"
        final_suggestions = latest_final['suggestions'] if 'suggestions' in latest_final else "None"
    else:
        final_empathy = chunk_df['empathy'].mean() if not chunk_df.empty else 0
        final_professionalism = chunk_df['professionalism'].mean() if not chunk_df.empty else 0
        final_compliance = "Pending"
        final_violations = "None"
        final_suggestions = "None"

    # Parse violations and suggestions
    violations_list = [v.strip() for v in str(final_violations).split('|') if v.strip() and v.strip() != "None"]
    suggestions_list = [s.strip() for s in str(final_suggestions).split('|') if s.strip() and s.strip() != "None"]
    
    st.sidebar.markdown("---")
    st.sidebar.title("📁 Upload & Process")
    
    # Input for Agent Name
    audio_agent = st.sidebar.text_input("Assign Agent Name for Audio:", placeholder="e.g. John Doe")
    
    # Language Selection
    languages = ["Auto-detect", "Hindi", "Spanish", "French", "English"]
    selected_language = st.sidebar.selectbox("Select Language:", languages)
    
    uploaded_file = st.sidebar.file_uploader("Upload Agent-Customer Conversation (MP3)", type=["mp3"])
    
    if uploaded_file is not None:
        if st.sidebar.button("🚀 Process & Analyze"):
            if not audio_agent:
                st.sidebar.error("Please enter an Agent Name first.")
            else:
                with st.spinner("Processing conversation..."):
                    # Save uploaded file
                    data_dir = os.path.join(PROJECT_ROOT, "data")
                    upload_dir = os.path.join(data_dir, "uploads")
                    os.makedirs(upload_dir, exist_ok=True)
                    
                    temp_path = os.path.join(upload_dir, uploaded_file.name)
                    
                    with open(temp_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    
                    # Run the pipeline
                    pipeline_script = os.path.join(PROJECT_ROOT, "backend", "pipeline.py")
                    
                    progress_bar = st.sidebar.progress(0)
                    status_text = st.sidebar.empty()
                    
                    try:
                        status_text.text("Transcribing...")
                        progress_bar.progress(20)
                        
                        # Run the pipeline as a subprocess
                        lang_arg = selected_language if selected_language != "Auto-detect" else "auto-detect"
                        process = subprocess.Popen(
                            [sys.executable, pipeline_script, temp_path, audio_agent, lang_arg],
                            cwd=PROJECT_ROOT,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True
                        )
                        
                        # Monitor progress (simplified)
                        while True:
                            output = process.stdout.readline()
                            if output == '' and process.poll() is not None:
                                break
                            if output:
                                if "Starting transcription" in output:
                                    status_text.text("Transcribing Audio...")
                                    progress_bar.progress(30)
                                elif "Starting speaker labeling" in output:
                                    status_text.text("Labeling Speakers...")
                                    progress_bar.progress(60)
                                elif "Starting compliance scoring" in output:
                                    status_text.text("Scoring Conversation...")
                                    progress_bar.progress(80)
                        
                        return_code = process.wait()
                        
                        if return_code == 0:
                            progress_bar.progress(100)
                            status_text.text("Processing Complete!")
                            st.sidebar.success("Analysis finished!")
                            
                            # Clear cache and rerun
                            st.cache_data.clear()
                            st.rerun()
                        else:
                            error_msg = process.stderr.read()
                            st.sidebar.error(f"Processing failed: {error_msg}")
                    except Exception as e:
                        st.sidebar.error(f"Error: {str(e)}")
    
    st.markdown("---")
    
            
    # ========================= FOOTER =========================
    if page == "🏠 Home":
        st.header("Welcome to Team Performance Dashboard")
        
        # Overall Team Scores
        st.subheader("🌐 Global Team Performance Averages")
        team_final = df[df['Chunk'] == 'FINAL']
        col1, col2, col3 = st.columns(3)
        
        # Calculate averages safely
        avg_empathy = team_final['empathy'].mean() if not team_final.empty else 0.0
        avg_prof = team_final['professionalism'].mean() if not team_final.empty else 0.0
        total_audits = len(team_final)
        
        with col1:
            st.metric(label="Team Empathy Score", value=f"{avg_empathy:.2f}")
        
        with col2:
            st.metric(label="Team Professionalism Score", value=f"{avg_prof:.2f}")
        
        with col3:
            st.metric(label="Total Conversations Audited", value=total_audits)
        
        st.markdown("---")
        
        # Agent Wise Performance Graph
        st.subheader("📊 Agent-Wise Performance Comparison")
        if not team_final.empty:
            # Aggregate by agent (taking average if multiple entries exist, though usually one per upload)
            agent_performances = team_final.groupby('Agent')[['empathy', 'professionalism']].mean().reset_index()
            
            fig_compare = go.Figure()
            fig_compare.add_trace(go.Bar(
                x=agent_performances['Agent'],
                y=agent_performances['empathy'],
                name='Empathy',
                marker_color='#58a6ff'
            ))
            fig_compare.add_trace(go.Bar(
                x=agent_performances['Agent'],
                y=agent_performances['professionalism'],
                name='Professionalism',
                marker_color='#3fb950'
            ))
            
            fig_compare.update_layout(
                barmode='group',
                xaxis_title="Agent",
                yaxis_title="Score (0-100)",
                plot_bgcolor='#161b22',
                paper_bgcolor='#0e1117',
                font=dict(color='#f0f2f6'),
                height=500
            )
            st.plotly_chart(fig_compare, use_container_width=True)
        else:
            st.info("No data available for agent comparison yet.")

        st.markdown("---")
        
        # Top Global Violations
        st.subheader("⚠️ Top Violations Across Portfolio")
        all_v = []
        for v_str in team_final['violations']:
            if pd.notna(v_str) and v_str != "None":
                all_v.extend([v.strip() for v in str(v_str).split('|')])
        
        if all_v:
            v_counts = pd.Series(all_v).value_counts().head(5)
            for i, (v, count) in enumerate(v_counts.items(), 1):
                st.error(f"**{i}. {v}** (Found in {count} conversations)")
        else:
            st.success("✓ No major violations across the team")
        
        st.markdown("---")
        
        # Recent Audits Summary Table
        st.subheader("📋 Recent Agent Performance Summary")
        summary_raw = team_final[['Agent', 'empathy', 'professionalism', 'compliance']].copy()
        
        # Remove rows where any of the critical columns are "None" or null
        summary_raw = summary_raw.replace("None", pd.NA)
        summary_raw = summary_raw.dropna(subset=['Agent', 'empathy', 'professionalism', 'compliance'])
        
        if not summary_raw.empty:
            # Group by agent and TAKE THE LAST (most recent) record for each
            # This ensures it matches the Comparison page logic
            summary_df = summary_raw.groupby('Agent').last().reset_index()
            
            summary_df = summary_df.rename(columns={
                'empathy': 'Empathy Score',
                'professionalism': 'Professionalism Score',
                'compliance': 'Outcome'
            })
            st.dataframe(summary_df.sort_values(by='Empathy Score', ascending=False).set_index('Agent'), use_container_width=True)
        else:
            st.info("No audit data available yet.")
    
    # ========================= REPORTS PAGE =========================
    # ========================= REPORTS PAGE =========================
    elif page == "📊 Reports":
        st.header("Advanced Agent Analytics & Leaderboard")
        
        # --- 1. 2D Performance Leaderboard ---
        st.subheader("🏆 Performance Leaderboard")
        st.info("Mapping agents based on Empathy (X) and Professionalism (Y).")
        
        team_final = df[df['Chunk'] == 'FINAL']
        if not team_final.empty:
            agent_metrics = team_final.groupby('Agent')[['empathy', 'professionalism']].mean().reset_index()
            
            # Map categories and actions
            def categorize_agent(row):
                if row['empathy'] >= 70 and row['professionalism'] >= 70:
                    return '⭐ Star', 'Promote'
                elif row['professionalism'] >= 70 and row['empathy'] < 70:
                    return '🤖 Robot', 'Soft-Skills Coaching'
                elif row['empathy'] >= 70 and row['professionalism'] < 70:
                    return '✨ Charmer', 'Process Training'
                else:
                    return '⚠️ Risk', 'Immediate Intervention'
            
            agent_metrics[['Category', 'Action']] = agent_metrics.apply(
                lambda x: pd.Series(categorize_agent(x)), axis=1
            )
            
            fig_leardboard = px.scatter(
                agent_metrics,
                x='empathy',
                y='professionalism',
                color='Category',
                text='Agent',
                hover_data=['Action'],
                labels={'empathy': 'Average Empathy', 'professionalism': 'Average Professionalism'},
                range_x=[0, 100],
                range_y=[0, 100],
                template='plotly_dark',
                color_discrete_map={
                    '⭐ Star': '#3fb950', 
                    '🤖 Robot': '#58a6ff', 
                    '✨ Charmer': '#d29922', 
                    '⚠️ Risk': '#f85149'
                }
            )
            
            fig_leardboard.update_traces(marker=dict(size=14, line=dict(width=2, color='white')), textposition='top center')
            
            # Add quadrant lines
            fig_leardboard.add_hline(y=70, line_dash="dash", line_color="gray")
            fig_leardboard.add_vline(x=70, line_dash="dash", line_color="gray")
            
            st.plotly_chart(fig_leardboard, use_container_width=True)
            
            # Category Legend/Summary
            st.subheader("📋 Leaderboard Classification & Actions")
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                stars_count = len(agent_metrics[agent_metrics['Category'] == '⭐ Star'])
                st.success(f"**Stars**: {stars_count}")
                st.caption("E>=70, P>=70 | **Action: Promote**")
            with c2:
                robots_count = len(agent_metrics[agent_metrics['Category'] == '🤖 Robot'])
                st.info(f"**Robots**: {robots_count}")
                st.caption("E<70, P>=70 | **Action: Soft-Skills Coaching**")
            with c3:
                charmers_count = len(agent_metrics[agent_metrics['Category'] == '✨ Charmer'])
                st.warning(f"**Charmers**: {charmers_count}")
                st.caption("E>=70, P<70 | **Action: Process Training**")
            with c4:
                risk_count = len(agent_metrics[agent_metrics['Category'] == '⚠️ Risk'])
                st.error(f"**Risk**: {risk_count}")
                st.caption("E<70, P<70 | **Action: Immediate Intervention**")
            
            # Detailed Leaderboard Table
            st.markdown("---")
            st.subheader("📑 Detailed Performance View")
            st.dataframe(agent_metrics[['Agent', 'empathy', 'professionalism', 'Category', 'Action']], use_container_width=True)
        else:
            st.warning("No data available for leaderboard yet.")

        st.markdown("---")

        # --- 2. AI-Driven Coaching Roadmap ---
        st.subheader("🎯 AI-Driven Coaching Roadmap")
        st.write("Generating a holistic training plan based on team-wide mistakes and suggestions...")
        
        # Aggregate all suggestions from the team
        team_suggestions = []
        for s_str in team_final['suggestions']:
            if pd.notna(s_str) and str(s_str) != "None":
                team_suggestions.extend([s.strip() for s in str(s_str).split('|') if s.strip()])
        
        if team_suggestions:
            # Check for API Key
            api_key = os.getenv("GROQ_API_KEY")
            if not api_key:
                st.warning("⚠️ GROQ_API_KEY not found. Please set it in your .env file or environment.")
                api_key = st.text_input("Or enter your Groq API Key here:", type="password")
            
            if st.button("🚀 Generate/Refresh Coaching Roadmap"):
                if not api_key:
                    st.error("API Key is required to generate the roadmap.")
                else:
                    with st.spinner("AI is clustering mistakes and defining training goals..."):
                        from groq import Groq
                        try:
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
                            """
                            
                            response = client.chat.completions.create(
                                messages=[{"role": "user", "content": prompt}],
                                model="llama-3.3-70b-versatile",
                            )
                            roadmap = response.choices[0].message.content
                            st.session_state['coaching_roadmap'] = roadmap
                            
                        except Exception as e:
                            st.error(f"Failed to generate roadmap: {e}")
            
            if 'coaching_roadmap' in st.session_state:
                st.success("Analysis Complete")
                st.markdown(st.session_state['coaching_roadmap'])
                
                # PDF Download Button
                if FPDF:
                    class CoachingPDF(FPDF):
                        def header(self):
                            self.set_font('Arial', 'B', 16)
                            self.cell(0, 10, 'AI-Driven Coaching Roadmap', 0, 1, 'C')
                            self.ln(5)
                        def footer(self):
                            self.set_y(-15)
                            self.set_font('Arial', 'I', 8)
                            self.cell(0, 10, f'Generated on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', 0, 0, 'C')

                    pdf = CoachingPDF()
                    pdf.add_page()
                    pdf.set_font("Arial", size=12)
                    
                    # Simple markdown-to-pdf conversion (handling headers and bullets)
                    lines = st.session_state['coaching_roadmap'].split('\n')
                    for line in lines:
                        try:
                            clean_line = clean_pdf_text(line)
                            if not clean_line.strip() and not line.strip():
                                pdf.ln(5)
                                continue
                                
                            if line.startswith('# '):
                                pdf.set_font("Arial", 'B', 14)
                                pdf.cell(0, 10, clean_line.replace('# ', ''), ln=1)
                                pdf.set_font("Arial", size=12)
                            elif line.startswith('## '):
                                pdf.set_font("Arial", 'B', 13)
                                pdf.cell(0, 10, clean_line.replace('## ', ''), ln=1)
                                pdf.set_font("Arial", size=12)
                            elif line.startswith('### '):
                                pdf.set_font("Arial", 'B', 12)
                                pdf.cell(0, 10, clean_line.replace('### ', ''), ln=1)
                                pdf.set_font("Arial", size=12)
                            else:
                                if clean_line.strip():
                                    pdf.multi_cell(0, 8, clean_line)
                        except Exception as line_err:
                            # Skip lines that still cause issues
                            print(f"Skipping PDF line due to error: {line_err}")
                            continue
                    
                    pdf_output = pdf.output(dest='S')
                    st.download_button(
                        label="📥 Download Roadmap as PDF",
                        data=bytes(pdf_output),
                        file_name=f"Coaching_Roadmap_{datetime.now().strftime('%Y%m%d')}.pdf",
                        mime="application/pdf"
                    )
        else:
            st.info("Add more audit results to generate a coaching roadmap.")

        st.markdown("---")
        # --- 3. Downloads Section ---
        st.subheader("📥 Data & Reports Downloads")
        st.write("Access the underlying data and historical performance reports.")
        
        dl_col1, dl_col2 = st.columns(2)
        with dl_col1:
            csv_path = os.path.join(PROJECT_ROOT, "data", "audit_results.csv")
            if os.path.exists(csv_path):
                with open(csv_path, "rb") as file:
                    st.download_button(
                        label="📄 Download Raw Audit Results (CSV)",
                        data=file,
                        file_name="audit_results.csv",
                        mime="text/csv"
                    )
        
        with dl_col2:
            if not team_final.empty:
                # Generate a simple team summary report
                class SummaryPDF(FPDF):
                    def header(self):
                        self.set_font('Arial', 'B', 14)
                        self.cell(0, 10, 'Team Compliance Summary Report', 0, 1, 'L')
                        self.ln(5)
                
                sum_pdf = SummaryPDF()
                sum_pdf.add_page()
                sum_pdf.set_font("Arial", size=11)
                
                sum_pdf.cell(0, 10, f"Total Audits: {len(team_final)}", ln=1)
                sum_pdf.cell(0, 10, f"Avg Empathy: {team_final['empathy'].mean():.2f}", ln=1)
                sum_pdf.cell(0, 10, f"Avg Professionalism: {team_final['professionalism'].mean():.2f}", ln=1)
                sum_pdf.ln(10)
                
                # Table Header
                sum_pdf.set_font("Arial", 'B', 11)
                sum_pdf.cell(60, 10, 'Agent', border=1)
                sum_pdf.cell(40, 10, 'Empathy', border=1)
                sum_pdf.cell(40, 10, 'Pro', border=1)
                sum_pdf.cell(40, 10, 'Compliance', border=1, ln=1)
                
                sum_pdf.set_font("Arial", size=10)
                agent_table = team_final.groupby('Agent')[['empathy', 'professionalism']].mean().reset_index()
                for _, row in agent_table.iterrows():
                    sum_pdf.cell(60, 10, clean_pdf_text(row['Agent']), border=1)
                    sum_pdf.cell(40, 10, f"{row['empathy']:.1f}", border=1)
                    sum_pdf.cell(40, 10, f"{row['professionalism']:.1f}", border=1)
                    
                    avg = (row['empathy'] + row['professionalism']) / 2
                    comp = "PASS" if avg >= 80 else "WARN" if avg >= 60 else "FAIL"
                    sum_pdf.cell(40, 10, comp, border=1, ln=1)

                sum_pdf_output = sum_pdf.output(dest='S')
                st.download_button(
                    label="📊 Download Team Performance Summary (PDF)",
                    data=bytes(sum_pdf_output),
                    file_name=f"Team_Audit_Summary_{datetime.now().strftime('%Y%m%d')}.pdf",
                    mime="application/pdf"
                )
    
    # ========================= EMAIL ANALYSIS PAGE =========================
    elif page == "📧 Email Analysis":
        st.header("Email Performance Analysis")
        st.write("Analyze agent-customer email interactions for quality and compliance.")
        
        email_agent = st.selectbox("Assign to Agent:", agents + ["New Agent..."])
        if email_agent == "New Agent...":
            email_agent = st.text_input("Enter new agent name:")
            
        st.markdown("---")
        
        tab1, tab2 = st.tabs(["🌐 Dynamic Browser Sync", "📝 Manual Paste"])
        
        with tab1:
            st.subheader("Connect to Webmail")
            st.info("Log in to your email client (Gmail/Outlook) and select the messages you want to analyze.")
            
            if st.button("🔗 Launch Email Browser"):
                # Use standard webbrowser for the user's local browser
                import webbrowser
                webbrowser.open("https://mail.google.com")
                st.success("Browser launched! Please navigate to the emails.")
            
            st.markdown("---")
            st.subheader("Process Selected Content")
            st.write("Ensure you have the target email(s) open or selected in the browser.")
            
            if st.button("📥 Extract & Score from Browser"):
                with st.spinner("🤖 Launching Email Assistant... Please log in and open the target email."):
                    extract_script = os.path.join(PROJECT_ROOT, "backend", "extract_emails.py")
                    try:
                        # Run the extraction script
                        result = subprocess.run(
                            [sys.executable, extract_script],
                            cwd=PROJECT_ROOT,
                            capture_output=True,
                            text=True,
                            timeout=120
                        )
                        
                        if result.returncode == 0:
                            # Load the extracted data
                            extracted_path = os.path.join(PROJECT_ROOT, "data", "extracted_email.json")
                            if os.path.exists(extracted_path):
                                with open(extracted_path, "r") as f:
                                    email_data = json.load(f)
                                
                                st.success(f"Successfully extracted: {email_data['subject']}")
                                
                                # Process for scoring
                                with st.spinner("Scoring extracted content..."):
                                    filename_label = f"Email_Browser_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                                    scoring_result = score_email(email_data['body'], agent_name=email_agent, filename=filename_label)
                                    print(f"DEBUG (extracted): violations={type(scoring_result.get('violations'))}, suggestions={type(scoring_result.get('suggestions'))}")
                                
                                # Display Results (same as manual)
                                c1, c2, c3 = st.columns(3)
                                with c1: st.metric("Empathy", f"{scoring_result['empathy']}/100")
                                with c2: st.metric("Professionalism", f"{scoring_result['professionalism']}/100")
                                with c3: st.metric("Outcome", scoring_result['compliance'])
                                
                                st.info(f"**Reason**: {scoring_result['reason']}")
                                
                                col_v, col_s = st.columns(2)
                                with col_v:
                                    st.subheader("⚠️ Violations")
                                    for v in scoring_result.get('violations', []):
                                        if v and v != "None":
                                            st.error(v)
                                        else:
                                            st.write("None")
                                with col_s:
                                    st.subheader("💡 Suggestions")
                                    for s in scoring_result.get('suggestions', []):
                                        if s and s != "None":
                                            st.success(s)
                                        else:
                                            st.write("None")
                                            
                                st.success("Analysis Complete! Graphs have been updated.")
                                # Clear cache for results to reflect
                                st.cache_data.clear()
                            else:
                                st.error("Extraction failed: Output file not produced.")
                        else:
                            st.error(f"Extraction error: {result.stderr}")
                            
                    except Exception as e:
                        st.error(f"Failed to launch assistant: {str(e)}")
        
        with tab2:
            st.subheader("Manual Analysis")
            pasted_content = st.text_area("Paste the email thread here (Include Subject, From, and Body if possible):", height=300)
            
            if st.button("⚖️ Score Pasted Email"):
                if not pasted_content:
                    st.error("Please paste some content first.")
                elif not email_agent:
                    st.error("Please assign an agent.")
                else:
                    with st.spinner("Analyzing email..."):
                        try:
                            filename_label = f"Email_Manual_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                            result = score_email(pasted_content, agent_name=email_agent, filename=filename_label)
                            print(f"DEBUG (pasted): violations={type(result.get('violations'))}, suggestions={type(result.get('suggestions'))}")
                            st.success("Email Analysis Complete!")
                            
                            # Display Results
                            c1, c2, c3 = st.columns(3)
                            with c1: st.metric("Empathy", f"{result['empathy']}/100")
                            with c2: st.metric("Professionalism", f"{result['professionalism']}/100")
                            with c3: st.metric("Outcome", result['compliance'])
                            
                            st.info(f"**Reason**: {result['reason']}")
                            
                            col_v, col_s = st.columns(2)
                            with col_v:
                                st.subheader("⚠️ Violations")
                                for v in result.get('violations', []):
                                    if v and v != "None":
                                        st.error(v)
                                    else:
                                        st.write("None")
                            with col_s:
                                st.subheader("💡 Suggestions")
                                for s in result.get('suggestions', []):
                                    if s and s != "None":
                                        st.success(s)
                                    else:
                                        st.write("None")
                                
                            # Rerun to update global stats automatically
                            st.cache_data.clear()
                            st.rerun()
                                
                        except Exception as e:
                            st.exception(e)
    
    # ========================= AGENT WISE ANALYSIS PAGE =========================
    elif page == "🕵️ Agent Wise Analysis":
        st.header("🕵️ Agent Wise Performance Analysis")
        
        # Ensure we have the absolute latest data from disk
        st.cache_data.clear()
        df = load_data()
        agents = sorted(df['Agent'].unique()) if df is not None else []
        
        if len(agents) < 1:
            st.warning("Please upload at least one conversation to see analysis.")
        else:
            selected_agent = st.selectbox("Select Agent for Deep-Dive Analysis:", agents)
            
            # Aggregate all FINAL data for this agent
            agent_all_data = df[df['Agent'] == selected_agent]
            agent_final_data = agent_all_data[agent_all_data['Chunk'] == 'FINAL']
            
            if agent_final_data.empty:
                st.warning(f"No completed audits found for {selected_agent}.")
            else:
                # Calculations
                avg_empathy = agent_final_data['empathy'].mean()
                avg_prof = agent_final_data['professionalism'].mean()
                
                # Conversation Counts
                total_audio = len(agent_final_data[agent_final_data['Source'] == 'Audio'])
                total_email = len(agent_final_data[agent_final_data['Source'] == 'Email'])
                total_convos = total_audio + total_email
                
                # Overall Compliance Logic
                overall_avg = (avg_empathy + avg_prof) / 2
                comp_status = "PASS" if overall_avg >= 80 else "WARN" if overall_avg >= 60 else "FAIL"
                comp_color = "pastel-green" if comp_status == "PASS" else "pastel-yellow" if comp_status == "WARN" else "pastel-purple"
                
                # Masking Count Logic
                total_masking_count = 0
                import re
                for m_analysis in agent_final_data.get('masking_analysis', []):
                    if pd.notna(m_analysis):
                        # Extract all numbers and sum them
                        nums = re.findall(r'\d+', str(m_analysis))
                        total_masking_count += sum(int(n) for n in nums)

                # UI Display: Bold Pastel Boxes
                st.markdown("---")
                m_col1, m_col2, m_col3, m_col4, m_col5 = st.columns(5)
                
                with m_col1:
                    st.markdown(f"""<div class="metric-container pastel-blue">
                        <div class="metric-title">Overall Empathy</div>
                        <div class="metric-value">{avg_empathy:.1f}</div>
                    </div>""", unsafe_allow_html=True)
                
                with m_col2:
                    st.markdown(f"""<div class="metric-container pastel-green">
                        <div class="metric-title">Professionalism</div>
                        <div class="metric-value">{avg_prof:.1f}</div>
                    </div>""", unsafe_allow_html=True)
                
                with m_col3:
                    st.markdown(f"""<div class="metric-container {comp_color}">
                        <div class="metric-title">Compliance</div>
                        <div class="metric-value">{comp_status}</div>
                    </div>""", unsafe_allow_html=True)
                
                with m_col4:
                    st.markdown(f"""<div class="metric-container pastel-purple">
                        <div class="metric-title">Total Masking</div>
                        <div class="metric-value">{total_masking_count}</div>
                    </div>""", unsafe_allow_html=True)
                
                with m_col5:
                    st.markdown(f"""<div class="metric-container pastel-orange">
                        <div class="metric-title">Total Conversations</div>
                        <div class="metric-value">{total_convos}</div>
                        <div class="metric-sub">Audio: {total_audio} | Email: {total_email}</div>
                    </div>""", unsafe_allow_html=True)

                st.markdown("---")
                
                v_col1, v_col2 = st.columns(2)
                from collections import Counter
                
                with v_col1:
                    st.subheader("🚨 Top 5 Major Violations")
                    all_violations = []
                    for v_str in agent_final_data['violations']:
                        if pd.notna(v_str) and v_str != "None":
                            all_violations.extend([v.strip() for v in str(v_str).split('|')])
                    
                    if all_violations:
                        # Count frequencies to get "Major" points
                        counts = Counter(all_violations)
                        top_5 = counts.most_common(5)
                        for v, count in top_5:
                            st.error(f"• **{v}** ({count} occurrences)")
                    else:
                        st.success("No violations recorded for this agent.")

                with v_col2:
                    st.subheader("💡 Top 5 Coaching Suggestions")
                    all_suggestions = []
                    for s_str in agent_final_data['suggestions']:
                        if pd.notna(s_str) and s_str != "None":
                            all_suggestions.extend([s.strip() for s in str(s_str).split('|')])
                    
                    if all_suggestions:
                        # Count frequencies to get "Major" points
                        counts = Counter(all_suggestions)
                        top_5 = counts.most_common(5)
                        for s, count in top_5:
                            st.info(f"• **{s}** ({count} occurrences)")
                    else:
                        st.write("No coaching suggestions available.")
                
                # Masked Transcript History
                st.markdown("---")
                st.subheader("📜 Masked Conversation History")
                
                # Show most recent interactions first
                recent_interactions = agent_final_data.sort_index(ascending=False).head(10)
                
                for idx, row in recent_interactions.iterrows():
                    source_emoji = "📞" if row['Source'] == 'Audio' else "📧"
                    status_emoji = "✅" if row['compliance'] == "PASS" else "⚠️" if row['compliance'] == "WARN" else "❌"
                    
                    with st.expander(f"{source_emoji} {row['Source']} Analysis | Outcome: {row['compliance']} {status_emoji}"):
                        st.markdown(f"**Empathy**: {row['empathy']:.1f} | **Professionalism**: {row['professionalism']:.1f}")
                        st.markdown("---")
                        raw_transcript = row.get('Transcript', 'No transcript available.')
                        # Apply live masking at display time as a safety net for historical records
                        if raw_transcript and raw_transcript != 'No transcript available.':
                            display_transcript = redact_pii(str(raw_transcript))['redacted_text']
                        else:
                            display_transcript = raw_transcript
                        st.code(display_transcript, language='text')
                        st.markdown("---")
                        st.caption(f"🛡️ {row.get('masking_analysis', 'No PII detected.')}")
    
    st.sidebar.markdown("---")
    st.sidebar.info("Dashboard Version 2.1\nLast Updated: " + datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

