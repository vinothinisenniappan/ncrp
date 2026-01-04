"""
Strict PDF Processor for NCRP Complaint Files
Follows STEP 2–4 exactly as requested:
- Save file first (handled in app.py)
- Open PDF, get total pages, loop every page, extract text per page
- DO NOT write Excel or output inside the page loop
- After loop, consolidate text and extract only the required fields
- Return ONE complaint dictionary; leave missing fields blank

Beginner-friendly comments included throughout.
"""

import pdfplumber
import re
from typing import Callable, Dict, List

# Helper: safely extract using label patterns
def _extract_after_label(text: str, label_patterns: List[str]) -> str:
    """
    Searches for any of the provided label patterns (case-insensitive).
    If found, captures the text immediately following the label up to the end of line.
    Returns an empty string if not found.
    """
    for lbl in label_patterns:
        # Match like: "Label: value" or on next line
        pattern_inline = rf"{lbl}\s*:\s*(.+)"
        pattern_nextline = rf"{lbl}\s*\n\s*(.+)"
        m = re.search(pattern_inline, text, re.IGNORECASE)
        if not m:
            m = re.search(pattern_nextline, text, re.IGNORECASE)
        if m:
            # Only take first line; strip spaces
            value = m.group(1).strip()
            if "\n" in value:
                value = value.split("\n")[0].strip()
            return value
    return ""

# Helper: generic number/currency cleanup
def _cleanup_amount(raw: str) -> str:
    if not raw:
        return ""
    # keep digits and dot/commas
    cleaned = re.sub(r"[^0-9.,]", "", raw)
    # normalize commas
    cleaned = cleaned.replace(",", "")
    return cleaned

# Main processor
def process_pdf_strict(filepath: str, update_progress: Callable[[int, int], None] = None) -> Dict:
    """
    STEP 2: PDF processing logic
      - Open with pdfplumber
      - Get total pages
      - Loop EVERY page from 1..N
      - Extract text and append to a list
      - Do NOT write Excel/output inside loop
    STEP 3: After loop, combine text into a single block and then extract fields
    STEP 4: Extract ONLY the requested fields. If missing, leave blank.

    Returns ONE complaint dictionary.
    """
    page_texts: List[str] = []

    # Open and read all pages
    with pdfplumber.open(filepath) as pdf:
        total_pages = len(pdf.pages)
        if total_pages == 0:
            # No content; return empty complaint dict
            return {
                'Complaint_ID': '',
                'Complaint_Date_Time': '',
                'Complainant_Name': '',
                'Mobile_Number': '',
                'Email': '',
                'District': '',
                'Police_Station': '',
                'Type_of_Cybercrime': '',
                'Platform_Involved': '',
                'Amount_Lost': '',
                'Current_Status': ''
            }

        # Loop through EVERY page and collect text
        for idx, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            page_texts.append(text)
            # Update progress (UI shows "Analyzing page x of y")
            if update_progress:
                update_progress(idx, total_pages)

    # STEP 3: Consolidate text AFTER reading all pages
    combined_text = "\n".join(page_texts)

    # STEP 4: Strict field extraction (labels vary; try multiple patterns)
    complaint_id = _extract_after_label(combined_text, [
        r"Acknowledgement\s*Number", r"Complaint\s*ID", r"Ack\s*No"
    ])

    complaint_date_time = _extract_after_label(combined_text, [
        r"Complaint\s*Date\s*\/?\s*Time", r"Complaint\s*Date", r"Registration\s*Date"
    ])

    complainant_name = _extract_after_label(combined_text, [
        r"Complainant\s*Name", r"Name\s*of\s*Complainant"
    ])

    mobile_number = _extract_after_label(combined_text, [
        r"Mobile\s*Number", r"Mobile\s*No", r"Phone\s*Number"
    ])

    email = _extract_after_label(combined_text, [
        r"Email", r"E\-?mail"
    ])

    district = _extract_after_label(combined_text, [
        r"District"
    ])

    police_station = _extract_after_label(combined_text, [
        r"Police\s*Station", r"PS\s*Name"
    ])

    type_of_cybercrime = _extract_after_label(combined_text, [
        r"Type\s*of\s*Cyber\s*Crime", r"Category\s*of\s*complaint"
    ])

    platform_involved = _extract_after_label(combined_text, [
        r"Platform\s*involved", r"Bank\/Platform", r"Platform"
    ])

    amount_lost_raw = _extract_after_label(combined_text, [
        r"Amount\s*Lost", r"Total\s*Fraudulent\s*Amount", r"Loss\s*Amount"
    ])
    amount_lost = _cleanup_amount(amount_lost_raw)

    current_status = _extract_after_label(combined_text, [
        r"Status", r"Current\s*Status"
    ])

    # STEP 5: Return ONE dictionary; leave missing fields blank
    complaint = {
        'Complaint_ID': complaint_id,
        'Complaint_Date_Time': complaint_date_time,
        'Complainant_Name': complainant_name,
        'Mobile_Number': mobile_number,
        'Email': email,
        'District': district,
        'Police_Station': police_station,
        'Type_of_Cybercrime': type_of_cybercrime,
        'Platform_Involved': platform_involved,
        'Amount_Lost': amount_lost,
        'Current_Status': current_status,
    }

    return complaint
