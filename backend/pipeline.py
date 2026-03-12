import os
import sys
import logging
from transcribe import transcribe_audio
from clean_transcript import label_speakers
from redaction import redact_pii
from scoring_engine import run_average_audit
from dotenv import load_dotenv

load_dotenv()

# Get the project root directory
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def run_pipeline(audio_path, agent_name="Unknown Agent", language=None):
    # Ensure data directory exists
    data_dir = os.path.join(PROJECT_ROOT, "data")
    os.makedirs(data_dir, exist_ok=True)
    
    try:
        # 1. Transcribe
        logger.info(f"Starting transcription for {audio_path} (Language: {language if language else 'Auto-detect'})")
        raw_text = transcribe_audio(audio_path, language=language)
        
        raw_transcript_path = os.path.join(data_dir, "1_raw_transcript.txt")
        with open(raw_transcript_path, "w", encoding="utf-8") as f:
            f.write(raw_text)
        logger.info(f"Transcription complete. Saved to {raw_transcript_path}")

        # 2. Label Speakers (Diarization)
        logger.info("Starting speaker labeling...")
        labeled_text = label_speakers(raw_text)
        
        # 3. Redact PII
        logger.info("Starting PII redaction...")
        masking_result = redact_pii(labeled_text)
        redacted_text = masking_result["redacted_text"]
        
        labeled_transcript_path = os.path.join(data_dir, "3_labeled_dialogue.txt")
        with open(labeled_transcript_path, "w", encoding="utf-8") as f:
            f.write(redacted_text)
        logger.info(f"Speaker labeling and redaction complete. Saved to {labeled_transcript_path}")

        # 4. Score
        logger.info("Starting compliance scoring...")
        run_average_audit(
            labeled_transcript_path, 
            agent_name=agent_name, 
            masking_score=masking_result["masking_score"],
            masking_analysis=masking_result["analysis"],
            filename=os.path.basename(audio_path),
            redacted_transcript=masking_result["redacted_text"]
        )
        logger.info(f"Scoring complete for {agent_name}. audit_results.csv updated.")
        
        return True
    except Exception as e:
        logger.error(f"Pipeline failed: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python pipeline.py <path_to_audio> [agent_name] [language]")
        sys.exit(1)
    
    audio_file = sys.argv[1]
    agent_name = sys.argv[2] if len(sys.argv) > 2 else os.path.splitext(os.path.basename(audio_file))[0]
    language = sys.argv[3] if len(sys.argv) > 3 else None
    
    success = run_pipeline(audio_file, agent_name, language)
    if success:
        print("Pipeline finished successfully!")
    else:
        print("Pipeline failed.")
