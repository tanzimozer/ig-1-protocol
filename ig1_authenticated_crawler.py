#!/usr/bin/env python3
"""
IG-1 Authenticated Crawler
Uses real Instagram session from vault to discover 50 new handles
with full profile enrichment (followers, bio, etc.)
"""

import requests
import json
import time
import re
from pathlib import Path
from datetime import datetime
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
import gspread

# Load Instagram session
vault = json.load(open(Path.home() / '.hermes' / 'vault.json'))
ig_vault = vault['instagram']

# Build cookies dict from vault
COOKIES = {
    'sessionid': ig_vault.get('sessionid', ''),
    'csrftoken': ig_vault.get('csrftoken', ''),
    'datr': ig_vault.get('datr', ''),
    'mid': ig_vault.get('mid', ''),
    'ig_did': ig_vault.get('ig_did', ''),
}
COOKIES.update(ig_vault.get('cookies', {}))

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15',
    'X-CSRFToken': ig_vault.get('csrftoken', ig_vault.get('csrf_token', '')),
    'X-Instagram-AJAX': '1',
    'Referer': 'https://www.instagram.com/',
}

# Filter settings
FEMALE_PATTERNS = {
    r'\bshe\b': 3, r'\bher\b': 3, r'\bgirl\b': 2, r'\bwoman\b': 2,
    r'\byoga\b': 1.5, r'\bfitness\b': 1, r'\bcoffee\b': 1,
}

HASHTAGS = [
    # Seattle
    'seattlefitness', 'seattlegirl', 'seattlewomen', 'seattleyoga',
    # LA
    'lafitness', 'lagirl', 'layoga', 'lalifestyle',
    # Dallas
    'dallasfitness', 'dallasgirl', 'dallasyoga',
    # Chicago
    'chicagofitness', 'chicagogirl', 'chicagoyoga',
]

def calc_female_score(full_name, bio):
    """Calculate female likelihood from name + bio"""
    text = f"{full_name or ''} {bio or ''}".lower()[:300]
    score = 0.0
    
    for pattern, points in FEMALE_PATTERNS.items():
        matches = len(re.findall(pattern, text))
        if matches:
            score += points * matches
    
    return min(score, 10.0)

def fetch_user(username):
    """Fetch user profile data using authenticated session"""
    try:
        url = f'https://www.instagram.com/api/v1/users/web_profile_info/'
        params = {'username': username}
        
        r = requests.get(url, params=params, headers=HEADERS, cookies=COOKIES, timeout=10)
        
        if r.status_code == 200:
            data = r.json()
            if 'data' in data and 'user' in data['data']:
                user = data['data']['user']
                return {
                    'username': user.get('username', username),
                    'full_name': user.get('full_name', ''),
                    'biography': user.get('biography', ''),
                    'followers': user.get('edge_followed_by', {}).get('total_count', 0),
                    'is_business': user.get('is_business_account', False),
                    'verified': user.get('is_verified', False),
                }
        
        if r.status_code == 429:
            print(f"    Rate limited on @{username}")
            return None
            
    except Exception as e:
        pass
    
    return None

def fetch_hashtag_users(hashtag, limit=20):
    """Fetch users from hashtag feed"""
    users = []
    try:
        url = f'https://www.instagram.com/api/v1/ig_hashtag_search/'
        params = {'user_id': ig_vault.get('ds_user_id', '123'), 'q': hashtag}
        
        r = requests.get(url, params=params, headers=HEADERS, cookies=COOKIES, timeout=10)
        
        if r.status_code == 200:
            data = r.json()
            if 'hashtags' in data and len(data['hashtags']) > 0:
                hashtag_id = data['hashtags'][0]['id']
                
                # Fetch recent posts from hashtag
                feed_url = f'https://www.instagram.com/api/v1/feed/tag/{hashtag_id}/recent/'
                feed_r = requests.get(feed_url, headers=HEADERS, cookies=COOKIES, timeout=10)
                
                if feed_r.status_code == 200:
                    feed_data = feed_r.json()
                    if 'items' in feed_data:
                        for item in feed_data['items'][:limit]:
                            if 'user' in item:
                                users.append(item['user']['username'])
        
        time.sleep(1)
    except Exception as e:
        pass
    
    return users

def main():
    # Google Sheets setup
    token_path = Path.home() / '.hermes' / 'google_token.json'
    creds = Credentials.from_authorized_user_file(str(token_path))
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    
    client = gspread.authorize(creds)
    ig1_sheet_id = '1Wo0kl-vcalbflt3sUgjwVNaP3ZbtRfaNmH0NqA0j5mw'
    ig1_sheet = client.open_by_key(ig1_sheet_id)
    
    run_id = datetime.now().strftime('%Y%m%d-%H%M%S')
    date_tab = datetime.now().strftime('%b %d').lstrip('0')
    
    results_ws = ig1_sheet.worksheet('Results')
    
    try:
        dated_ws = ig1_sheet.add_worksheet(title=date_tab, rows=1000, cols=11)
    except:
        dated_ws = ig1_sheet.worksheet(date_tab)
        dated_ws.clear()
    
    headers = ['Username', 'Full Name', 'Followers', 'Female Score', 'Business Score', 'Bio Preview', 'Is Business', 'Verified', 'Status', 'Crawled At', 'Run ID']
    dated_ws.append_row(headers)
    
    print(f"\n🔍 IG-1 AUTHENTICATED CRAWLER")
    print(f"Run ID: {run_id}")
    print(f"Date Tab: {date_tab}\n")
    
    all_results = []
    seen = set()
    
    # Discover from hashtags
    print("📍 Discovering from hashtags...\n")
    
    for hashtag in HASHTAGS:
        print(f"  #{hashtag}...", end=' ', flush=True)
        
        users = fetch_hashtag_users(hashtag)
        print(f"found {len(users)}")
        
        for username in users:
            if username in seen:
                continue
            
            seen.add(username)
            
            # Fetch & enrich
            profile = fetch_user(username)
            
            if not profile:
                continue
            
            # Calculate scores
            female_score = calc_female_score(profile['full_name'], profile['biography'])
            
            # Apply filters
            if profile['followers'] < 500 or profile['followers'] > 3500:
                continue
            if female_score < 3.0:
                continue
            
            all_results.append({
                'username': profile['username'],
                'full_name': profile['full_name'],
                'followers': profile['followers'],
                'female_score': female_score,
                'bio': profile['biography'],
                'is_business': profile['is_business'],
                'verified': profile['verified'],
            })
            
            if len(all_results) >= 50:
                break
        
        if len(all_results) >= 50:
            break
        
        time.sleep(2)
    
    # Save to sheets
    print(f"\n📊 Appending {len(all_results)} results to Results + {date_tab}...\n")
    
    for result in all_results:
        bio_preview = result['bio'][:40] if result['bio'] else ''
        row = [
            result['username'],
            result['full_name'],
            result['followers'],
            round(result['female_score'], 2),
            0,  # Business score placeholder
            bio_preview,
            'Yes' if result['is_business'] else 'No',
            'Yes' if result['verified'] else 'No',
            'discovered',
            datetime.now().isoformat(),
            run_id,
        ]
        results_ws.append_row(row)
        dated_ws.append_row(row)
        time.sleep(0.2)
    
    print(f"✓ Crawl complete!")
    print(f"  Discovered: {len(seen)}")
    print(f"  Passed filters: {len(all_results)}")
    print(f"  Master: Results tab")
    print(f"  Dated: {date_tab}")
    print(f"  Run ID: {run_id}")

if __name__ == '__main__':
    main()
