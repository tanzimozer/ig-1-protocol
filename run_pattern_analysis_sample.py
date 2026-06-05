#!/usr/bin/env python3
"""
IG-1 Pattern Analysis — Quick Sample Run
Test with 50 handles to validate the pattern analyzer works.
"""

import sys
import time
from pathlib import Path
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
import gspread
from ig1_pattern_analyzer import IG1PatternAnalyzer

def main():
    # Load OAuth
    token_path = Path.home() / '.hermes' / 'google_token.json'
    creds = Credentials.from_authorized_user_file(str(token_path))
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    
    client = gspread.authorize(creds)
    
    # Open IG-1 sheet
    print("Opening IG-1 Protocol Results sheet...")
    ig1_sheet_id = '1Wo0kl-vcalbflt3sUgjwVNaP3ZbtRfaNmH0NqA0j5mw'
    ig1_sheet = client.open_by_key(ig1_sheet_id)
    ws = ig1_sheet.worksheet('Consolidated Handles')
    
    # Load data
    print("Loading consolidated handles...")
    all_data = ws.get_all_values()
    headers = all_data[0]
    data_rows = all_data[1:]
    
    # Take first 50 only
    sample_rows = data_rows[:50]
    sample_handles = [row[0] for row in sample_rows if row[0]]
    
    print(f"Loaded {len(sample_handles)} sample handles\n")
    
    # Initialize analyzer
    analyzer = IG1PatternAnalyzer(batch_size=50, delay_between_requests=3)
    
    print(f"=== SAMPLE ANALYSIS (50 HANDLES) ===\n")
    
    try:
        # Analyze sample
        results = analyzer.analyze_batch(sample_handles)
        
        # Update sheet
        print(f"\nUpdating sheet...")
        for i, handle in enumerate(sample_handles):
            row_num = i + 2
            if handle in results:
                analysis = results[handle]
                ws.update(f'D{row_num}', analysis.get('followers_estimate', ''))
                ws.update(f'E{row_num}', analysis.get('follower_velocity', ''))
                ws.update(f'F{row_num}', analysis.get('account_age_estimate', ''))
                ws.update(f'G{row_num}', analysis.get('bio_signal_strength', ''))
                ws.update(f'H{row_num}', analysis.get('business_likelihood', ''))
                ws.update(f'I{row_num}', analysis.get('female_score_predicted', ''))
        
        print(f"\n✓ Sample analysis complete!")
        print(f"  Updated: 50 handles")
        print(f"  Check 'Consolidated Handles' tab in Google Sheet")
        print(f"\nTo analyze all 1,975 handles:")
        print(f"  $ python run_pattern_analysis.py")
        print(f"  (Runs ~2 hours, quota-safe)")
    
    except Exception as e:
        print(f"✗ Error: {e}")

if __name__ == '__main__':
    main()
