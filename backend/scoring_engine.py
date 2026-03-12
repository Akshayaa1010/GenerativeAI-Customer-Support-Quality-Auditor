import os
import sys
import pandas as pd
import json
from groq import Groq
from rag_compliance import ComplianceRAG

# Get the project root directory
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
rag_system = ComplianceRAG()

def score_chunk(chunk_text):
    # Retrieve specific rules for this part of the talk
    relevant_rules = rag_system.get_rules_for_context(chunk_text)
    
    prompt = f"""
    Evaluate this chunk based on these specific rules:
    {relevant_rules}

    Conversation:
    {chunk_text}

    Return JSON ONLY:
    {{
      "empathy": 1-100,
      "professionalism": 1-100,
      "compliance": "Pass/Fail/Warn",
      "reason": "Explain violation if any",
      "violations": ["List specific policy violations"],
      "suggestions": ["List specific improvement suggestions"]
    }}
    """
    
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        response_format={ "type": "json_object" }
    )
    return json.loads(response.choices[0].message.content)

def score_email(email_text, agent_name="Unknown Agent", filename=None, **kwargs):
    print(f"DEBUG: score_email called with filename={filename}")
    if filename is None:
        from datetime import datetime
        filename = f"Email_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    # Retrieve specific rules for email context
    relevant_rules = rag_system.get_rules_for_context(email_text)
    
    prompt = f"""
    Evaluate this customer service email based on these specific rules:
    {relevant_rules}

    Email Content:
    {email_text}

    Return JSON ONLY:
    {{
      "empathy": 1-100,
      "professionalism": 1-100,
      "compliance": "Pass/Fail/Warn",
      "reason": "Explain violation if any",
      "violations": ["List specific policy violations"],
      "suggestions": ["List specific improvement suggestions"]
    }}
    """
    
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        response_format={ "type": "json_object" }
    )
    result = json.loads(response.choices[0].message.content)

    # 1. Redact Email Content
    from redaction import redact_pii
    masking_result = redact_pii(email_text)
    
    # Save to CSV
    csv_path = os.path.join(PROJECT_ROOT, "data", "audit_results.csv")
    column_order = ['Chunk', 'empathy', 'professionalism', 'compliance', 'reason', 'violations', 'suggestions', 'evaluation', 'Agent', 'masking_score', 'masking_analysis', 'Source', 'Transcript', 'Filename']
    
    new_row = {
        'Chunk': 'EMAIL', # Identifying this as an email audit
        'Source': 'Email',
        'empathy': result['empathy'],
        'professionalism': result['professionalism'],
        'compliance': result['compliance'],
        'reason': result['reason'],
        'violations': "|".join(result['violations']),
        'suggestions': "|".join(result['suggestions']),
        'evaluation': json.dumps(result),
        'Agent': agent_name,
        'masking_score': masking_result['masking_score'],
        'masking_analysis': masking_result['analysis'],
        'Transcript': masking_result['redacted_text'],
        'Filename': filename
    }
    
    # Append to cumulative results
    df = pd.DataFrame([new_row])[column_order]
    
    # Also add a FINAL row for this email to make it consistent with the dashboard's "FINAL" logic
    final_row = new_row.copy()
    final_row['Chunk'] = 'FINAL'
    final_df = pd.DataFrame([final_row])[column_order]
    
    full_df = pd.concat([df, final_df])
    
    # Append to cumulative results (Safe horizontal concat)
    if os.path.exists(csv_path):
        existing_df = pd.read_csv(csv_path)
        for col in column_order:
            if col not in existing_df.columns:
                existing_df[col] = None
        full_df = pd.concat([existing_df[column_order], full_df[column_order]], ignore_index=True)
        full_df.to_csv(csv_path, index=False)
    else:
        full_df[column_order].to_csv(csv_path, index=False)
        
    return result

def run_average_audit(file_path, agent_name="Unknown Agent", masking_score=100, masking_analysis="", filename=None, redacted_transcript=None):
    if filename is None:
        filename = os.path.basename(file_path)
    # Handle both absolute and relative paths
    if not os.path.isabs(file_path):
        file_path = os.path.join(PROJECT_ROOT, file_path)
    
    with open(file_path, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f.readlines() if line.strip().startswith(('Agent:', 'Customer:'))]
    
    # Use the redacted transcript if provided, otherwise fall back to joined lines
    if redacted_transcript is None:
        redacted_transcript = "\n".join(lines)

    # Process in chunks of 5 turns
    chunk_results = []
    for i in range(0, len(lines), 5):
        chunk = "".join(lines[i:i+5])
        chunk_results.append(score_chunk(chunk))

    # Create DataFrame with chunk results
    df = pd.DataFrame(chunk_results)
    
    # Add Chunk and Agent columns in correct order
    df.insert(0, 'Chunk', range(1, len(df) + 1))
    df['Agent'] = agent_name
    
    # Convert violations and suggestions lists to strings for CSV
    if 'violations' in df.columns:
        df['violations'] = df['violations'].apply(lambda x: ' | '.join(x) if isinstance(x, list) else str(x))
    if 'suggestions' in df.columns:
        df['suggestions'] = df['suggestions'].apply(lambda x: ' | '.join(x) if isinstance(x, list) else str(x))
    
    # Calculate averages
    final_empathy = df['empathy'].mean()
    final_professionalism = df['professionalism'].mean()
    
    # Determine overall compliance based on average scores
    avg_score = (final_empathy + final_professionalism) / 2
    if avg_score >= 80:
        overall_compliance = "PASS"
    elif avg_score >= 60:
        overall_compliance = "WARN"
    else:
        overall_compliance = "FAIL"
    
    # Aggregate violations and suggestions
    all_violations = []
    all_suggestions = []
    
    if 'violations' in df.columns:
        for vuln_str in df['violations']:
            if pd.notna(vuln_str):
                all_violations.extend([v.strip() for v in str(vuln_str).split('|')])
    
    if 'suggestions' in df.columns:
        for sugg_str in df['suggestions']:
            if pd.notna(sugg_str):
                all_suggestions.extend([s.strip() for s in str(sugg_str).split('|')])
    
    # Remove duplicates
    all_violations = list(set([v for v in all_violations if v]))
    all_suggestions = list(set([s for s in all_suggestions if s]))
    
    # Reorder columns before saving
    column_order = ['Chunk', 'empathy', 'professionalism', 'compliance', 'reason', 'violations', 'suggestions', 'evaluation', 'Agent', 'masking_score', 'masking_analysis', 'Source', 'Transcript', 'Filename']
    
    # Create final results row
    final_row_data = {
        'Agent': agent_name,
        'Chunk': 'FINAL',
        'empathy': final_empathy,
        'professionalism': final_professionalism,
        'compliance': overall_compliance,
        'reason': 'Final average scores',
        'violations': ' | '.join(all_violations) if all_violations else 'None',
        'suggestions': ' | '.join(all_suggestions) if all_suggestions else 'None',
        'evaluation': None,
        'masking_score': masking_score,
        'masking_analysis': masking_analysis,
        'Source': 'Audio',
        'Transcript': redacted_transcript,
        'Filename': filename
    }
    final_df = pd.DataFrame([final_row_data])
    
    # Ensure chunks df has all columns
    for col in column_order:
        if col not in df.columns:
            df[col] = None
    
    # Update chunk df with masking info too
    df['masking_score'] = masking_score
    df['masking_analysis'] = masking_analysis
    df['Source'] = 'Audio'
    df['Transcript'] = redacted_transcript
    df['Filename'] = filename
            
    # Standardize chunk df and concat with final
    df = pd.concat([df[column_order], final_df[column_order]], ignore_index=True)
    
    # Save to CSV (Cumulative)
    csv_filename = os.path.join(PROJECT_ROOT, "data", "audit_results.csv")
    if os.path.exists(csv_filename):
        existing_df = pd.read_csv(csv_filename)
        # Standardize existing_df to avoid concat issues
        for col in column_order:
            if col not in existing_df.columns:
                existing_df[col] = None
        df = pd.concat([existing_df[column_order], df], ignore_index=True)
        
    df.to_csv(csv_filename, index=False)
    print(f"\nCSV file saved: {csv_filename}")
    
    # Print results
    print(f"\n--- FINAL AUDIT RESULTS FOR {agent_name} ---")
    print(f"Final Empathy Score: {final_empathy}")
    print(f"Final Professionalism Score: {final_professionalism}")
    print(f"Overall Compliance: {overall_compliance}")
    
    return df

if __name__ == "__main__":
    import sys
    agent = sys.argv[2] if len(sys.argv) > 2 else "Sample Agent"
    target_file = os.path.join(PROJECT_ROOT, "data", "3_labeled_dialogue.txt")
    
    if os.path.exists(target_file):
        run_average_audit(target_file, agent)
    else:
        print(f"Error: {target_file} not found. Please run the full pipeline or process an email/audio first.")
