#!/usr/bin/env python3
"""
IG-1 Batch Crawler — Process Consolidated Handles
Takes real handles from Consolidated Handles tab,
enriches them, applies filters, saves to new crawl tab.
"""

from pathlib import Path
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
import gspread
import requests
import re
import time
import json
from datetime import datetime

# Filters
FEMALE_PRONOUNS = {
    r'\bshe\b': 3, r'\bher\b': 3, r'\bshe/her\b': 3,
    r'\bthey/them\b': 1, r'\bthey\b': 1,
}
FEMALE_NOUNS = {
    r'\bgirl\b': 2, r'\bwoman\b': 2, r'\blady\b': 2,
    r'\byoga\s+instructor\b': 3, r'\bfitness\s+coach\b': 3,
}
FEMALE_RELATIONSHIPS = {
    r'\bmom\b': 1.5, r'\bmother\b': 1.5, r'\bwife\b': 1.5,
}

BUSINESS_KEYWORDS = {
    r'\bcertified\b': 10, r'\binstructor\b': 10, r'\btrainer\b': 10,
    r'\bcoach\b': 10, r'\bowner\b': 8, r'\bmanager\b': 8, r'\bdirector\b': 8,
}

HEADERS = {'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0)'}

def calc_female_score(full_name, bio):
    """Female score calculation"""
    text = f"{full_name} {bio}".lower()[:500] if bio else full_name.lower()
    score = 0.0
    
    for pattern, points in FEMALE_PRONOUNS.items():
        if re.search(pattern, text):
            score += points
    for pattern, points in FEMALE_NOUNS.items():
        if re.search(pattern, text):
            score += points
    for pattern, points in FEMALE_RELATIONSHIPS.items():
        if re.search(pattern, text):
            score += points
    
    return min(score, 10.0)

def calc_business_score(full_name, bio):
    """Business score calculation"""
    text = f"{full_name} {bio}".lower()[:500] if bio else full_name.lower()
    score = 0
    for pattern, points in BUSINESS_KEYWORDS.items():
        if re.search(pattern, text):
            score += points
    return min(score, 10)

def enrich_profile(username, vault_ig):
    """Try to fetch real profile data from Instagram"""
    try:
        # Construct request with stored Instagram creds
        headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0)',
            'X-CSRF-Token': vault_ig.get('csrf_token', vault_ig.get('csrftoken', '')),
        }
        cookies = vault_ig.get('cookies', {})
        
        url = f'https://www.instagram.com/api/v1/users/web_profile_info/?username={username}'
        r = requests.get(url, headers=headers, cookies=cookies, timeout=10)
        
        if r.status_code == 200:
            data = r.json()
            if 'data' in data and 'user' in data['data']:
                user = data['data']['user']
                return {
                    'username': user.get('username', username),
                    'full_name': user.get('full_name', ''),
                    'biography': user.get('biography', ''),
                    'follower_count': user.get('edge_followed_by', {}).get('total_count', 0),
                    'is_business': user.get('is_business_account', False),
                }
        
        time.sleep(1)
    except Exception as e:
        pass
    
    return None

def passes_filter(profile):
    """Apply IG-1 filters"""
    foll = profile.get('follower_count', 0)
    female_score = profile.get('female_score', 0)
    
    if foll < 500 or foll > 3500:
        return False
    if female_score < 3.0:
        return False
    return True

def main():
    # Load vault & sheets
    vault = json.load(open(Path.home() / '.hermes' / 'vault.json'))
    vault_ig = vault.get('instagram', {})
    
    token_path = Path.home() / '.hermes' / 'google_token.json'
    creds = Credentials.from_authorized_user_file(str(token_path))
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    
    client = gspread.authorize(creds)
    ig1_sheet_id = '1Wo0kl-vcalbflt3sUgjwVNaP3ZbtRfaNmH0NqA0j5mw'
    ig1_sheet = client.open_by_key(ig1_sheet_id)
    
    # Load consolidated handles
    print("Loading consolidated handles...")
    cons_ws = ig1_sheet.worksheet('Consolidated Handles')
    all_data = cons_ws.get_all_values()
    handles = [row[0] for row in all_data[1:] if row and row[0]]  # Skip header
    
    print(f"Loaded {len(handles)} handles\n")
    
    # Get Results tab (master cumulative) + create dated tab
    run_id = datetime.now().strftime('%Y%m%d-%H%M%S')
    date_tab = datetime.now().strftime('%b %d').lstrip('0')  # "Jun 05" format
    
    results_ws = ig1_sheet.worksheet('Results')
    
    # Create or clear dated tab
    try:
        dated_ws = ig1_sheet.add_worksheet(title=date_tab, rows=5000, cols=11)
    except:
        dated_ws = ig1_sheet.worksheet(date_tab)
        dated_ws.clear()
    
    # Add headers to dated tab
    headers = [
        'Username', 'Full Name', 'Followers', 'Female Score', 'Business Score',
        'Bio Preview', 'Is Business', 'Source', 'Status', 'Crawled At', 'Run ID'
    ]
    dated_ws.append_row(headers)
    
    print(f"🔍 IG-1 BATCH CRAWLER\nRun ID: {run_id}\nDate Tab: {date_tab}\n")
    
    results = []
    
    # Process first 50 handles (sample)
    print("Processing first 50 consolidated handles...")
    for i, username in enumerate(handles[:50]):
        print(f"  [{i+1:2d}/50] @{username:30s}", end=' ', flush=True)
        
        profile = enrich_profile(username, vault_ig)
        
        if profile:
            profile['female_score'] = calc_female_score(profile['full_name'], profile['biography'])
            profile['business_score'] = calc_business_score(profile['full_name'], profile['biography'])
            
            if passes_filter(profile):
                results.append(profile)
                print(f"✓ female:{profile['female_score']:4.1f} | followers:{profile['follower_count']:5d}")
            else:
                print(f"✗ filtered")
        else:
            print(f"✗ no data")
        
        time.sleep(1)
    
    # Save to both Results tab (master) and dated tab
    print(f"\n📊 Appending {len(results)} results to Results + {date_tab}...\n")
    
    for result in results:
        bio_preview = result['biography'][:40] if result['biography'] else ''
        row = [
            result['username'],
            result['full_name'],
            result['follower_count'],
            round(result['female_score'], 2),
            round(result['business_score'], 2),
            bio_preview,
            'Yes' if result['is_business'] else 'No',
            'consolidated',
            'analyzed',
            datetime.now().isoformat(),
            run_id,
        ]
        results_ws.append_row(row)
        dated_ws.append_row(row)
        time.sleep(0.2)
    
    print(f"✓ Batch crawl complete!")
    print(f"  Processed: 50 handles")
    print(f"  Passed filters: {len(results)}")
    print(f"  Master: Results tab")
    print(f"  Dated: {date_tab}")
    print(f"  Run ID: {run_id}")

if __name__ == '__main__':
    main()
