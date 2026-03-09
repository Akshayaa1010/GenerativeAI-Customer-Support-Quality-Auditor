import re
import spacy

# Load spaCy model for NER
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    print("Warning: spaCy model 'en_core_web_sm' not found. Falling back to a blank model for NER.")
    nlp = spacy.blank("en")
def redact_pii(text):
    """
    Redacts PII such as names, credit card numbers, and email addresses from the text.
    Returns a dictionary with redacted content and masking statistics.
    """
    if not text:
        return {"redacted_text": text, "masking_score": 100, "analysis": "Empty text provided."}

    masked_details = []
    
    # 1. Redact Aadhaar Number (12 digits, including formats like 1234 5678 9012 or 1234-5678-9012)
    aadhaar_pattern = r'\b\d{4}[ -]?\d{4}[ -]?\d{4}\b'
    aadhaars = re.findall(aadhaar_pattern, text)
    if aadhaars:
        masked_details.append(f"Masked {len(aadhaars)} Aadhaar Number(s)")
    text = re.sub(aadhaar_pattern, "[AADHAAR REDACTED]", text)

    # 2. Redact Mobile Number (Indian 10-digit, including +91/0 prefix and various formats)
    # This pattern catches +91 9999999999, 99999-99999, 09999999999, etc.
    mobile_pattern = r'\b(?:\+91|0)?[ -]?\d{5}[ -]?\d{5}\b'
    mobiles = re.findall(mobile_pattern, text)
    if mobiles:
        masked_details.append(f"Masked {len(mobiles)} Mobile Number(s)")
    text = re.sub(mobile_pattern, "[MOBILE REDACTED]", text)

    # 3. Redact IFSC Code (4 chars, 0, then 6 chars - e.g. SBIN0001234)
    ifsc_pattern = r'\b[A-Z]{4}0[A-Z0-9]{6}\b'
    ifscs = re.findall(ifsc_pattern, text)
    if ifscs:
        masked_details.append(f"Masked {len(ifscs)} IFSC Code(s)")
    text = re.sub(ifsc_pattern, "[IFSC REDACTED]", text)

    # 4. Redact Credit Card Numbers (Simple regex for 13-16 digits)
    card_pattern = r'\b(?:\d[ -]*?){13,16}\b'
    cards = re.findall(card_pattern, text)
    if cards:
        masked_details.append(f"Masked {len(cards)} Credit Card Number(s)")
    text = re.sub(card_pattern, "[CARD REDACTED]", text)

    # 5. Redact Email Addresses
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    emails = re.findall(email_pattern, text)
    if emails:
        masked_details.append(f"Masked {len(emails)} Email Address(es)")
    text = re.sub(email_pattern, "[EMAIL REDACTED]", text)

    # 3. Redact Names using spaCy NER
    doc = nlp(text)
    redacted_text = text
    
    # We sort entities by start position in reverse order to replace without affecting indices
    entities = sorted(doc.ents, key=lambda x: x.start_char, reverse=True)
    
    names_count = 0
    for ent in entities:
        if ent.label_ == "PERSON":
            redacted_text = redacted_text[:ent.start_char] + "[NAME REDACTED]" + redacted_text[ent.end_char:]
            names_count += 1
        elif ent.label_ == "ORG" and ent.text.lower() not in ["agent", "customer"]:
            # Optionally redact organizations if they seem like sensitive info
            pass
    
    if names_count > 0:
        masked_details.append(f"Masked {names_count} Name(s)")

    analysis = " | ".join(masked_details) if masked_details else "No PII detected."
    # A simple score: 100 if no PII or all PII handled. We can lower it if we detect potential PII leaks.
    masking_score = 100 

    return {
        "redacted_text": redacted_text,
        "masking_score": masking_score,
        "analysis": analysis
    }

if __name__ == "__main__":
    test_text = "Hello, my name is John Doe and my credit card number is 1234-5678-9012-3456. You can email me at john.doe@example.com. I work for Google."
    print("Original:", test_text)
    print("Redacted:", redact_pii(test_text))
