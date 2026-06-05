#!/usr/bin/env python3
"""
IG-1 Pattern Analysis Runner
Batch-analyze consolidated handles and update Google Sheet with pattern metrics.
Safe, quota-aware, resumable.
"""

import sys
import time
from pathlib import Path
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
import gspread
from ig1_pattern_analyzer import IG1PatternAnalyzer

def get_sheet_data(ws):
    """Get all values from worksheet."""
    return ws.get_all_values()

def update_sheet_row(ws, row_num, analysis_dict):
    """Update a specific row with analysis data."""
    # Row format: [Handle, Source, Crawl Status, Followers_estimate, Follower_Velocity, Account_Age_Estimate, Bio_Signal_Strength, Business_Likelihood, Female_Score_Predicted]
    ws.update(f'D{row_num}', analysis_dict.get('followers_estimate', ''))
    ws.update(f'E{row_num}', analysis_dict.get('follower_velocity', ''))
    ws.update(f'F{row_num}', analysis_dict.get('account_age_estimate', ''))
    ws.update(f'G{row_num}', analysis_dict.get('bio_signal_strength', ''))
    ws.update(f'H{row_num}', analysis_dict.get('business_likelihood', ''))
    ws.update(f'I{row_num}', analysis_dict.get('female_score_predicted', ''))

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
    all_data = get_sheet_data(ws)
    headers = all_data[0]
    data_rows = all_data[1:]
    
    print(f"Found {len(data_rows)} handles\n")
    
    # Initialize analyzer
    analyzer = IG1PatternAnalyzer(batch_size=10, delay_between_requests=2.5)
    
    # Process in batches of 10 (safe for quota)
    batch_size = 10
    for batch_idx in range(0, len(data_rows), batch_size):
        batch_end = min(batch_idx + batch_size, len(data_rows))
        batch_rows = data_rows[batch_idx:batch_end]
        handles = [row[0] for row in batch_rows if row[0]]
        
        print(f"\n=== BATCH {batch_idx//batch_size + 1} ({batch_idx+1}-{batch_end}/{len(data_rows)}) ===")
        
        try:
            # Analyze batch
            results = analyzer.analyze_batch(handles)
            
            # Update sheet
            print(f"\nUpdating sheet...")
            for i, handle in enumerate(handles):
                row_num = batch_idx + i + 2  # +2 for header and 0-indexing
                if handle in results:
                    update_sheet_row(ws, row_num, results[handle])
                    print(f"  ✓ Row {row_num}: @{handle}")
            
            # Wait between batches (avoid quota)
            if batch_end < len(data_rows):
                print(f"\nWaiting 30s before next batch...")
                time.sleep(30)
        
        except Exception as e:
            print(f"✗ Batch error: {e}")
            print(f"Pausing 60s before retry...")
            time.sleep(60)
    
    print(f"\n✓ Pattern analysis complete!")
    print(f"Sheet updated: {len(data_rows)} handles analyzed")

if __name__ == '__main__':
    main()
