#!/usr/bin/env python3
"""
IG-1 Protocol Live Crawler
Discovery + Enrichment + Filter + Score → Google Sheets (new tab per run)
Zero-token runtime, all regex-based filtering
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

# Load Instagram session & credentials
vault = json.load(open(Path.home() / '.hermes' / 'vault.json'))['instagram']
CSRF_TOKEN = vault.get('csrf_token', vault.get('csrftoken', ''))
COOKIES = vault.get('cookies', {})

# Config
CITIES = ['Seattle', 'Los Angeles', 'Dallas', 'Chicago', 'London']
HASHTAGS_PER_CITY = 8
HASHTAGS = {
    'Seattle': ['seattlefitness', 'seattlegirl', 'seattlewomen', 'pnwlife', 'seattleoutdoor', 'seattlecoffee', 'seattleblogger', 'seattleyoga'],
    'Los Angeles': ['lafitness', 'lagirl', 'lawomen', 'lalifestyle', 'laoutdoor', 'lacoffee', 'lablogger', 'layoga'],
    'Dallas': ['dallasfitness', 'dallasgirl', 'dallaswomen', 'dallaslife', 'dallasoutdoor', 'dallascoffee', 'dallasblogger', 'dallasyoga'],
    'Chicago': ['chicagofitness', 'chicagogirl', 'chicagowomen', 'chicagolife', 'chicagooutdoor', 'chicagocoffee', 'chicagoblogger', 'chicagoyoga'],
    'London': ['londonfitness', 'londongirl', 'londonwomen', 'londonlife', 'londonoutdoor', 'londoncoffee', 'londonblogger', 'londonyoga'],
}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15',
    'X-CSRF-Token': CSRF_TOKEN,
    'X-Requested-With': 'XMLHttpRequest',
    'Accept': 'application/json',
}

# Female detection (from v1.3)
FEMALE_PRONOUNS = {
    r'\bshe\b': 3,
    r'\bher\b': 3,
    r'\bshe/her\b': 3,
    r'\bthey/them\b': 1,
    r'\bthey\b': 1,
}

FEMALE_NOUNS = {
    r'\bgirl\b': 2,
    r'\bwoman\b': 2,
    r'\blady\b': 2,
    r'\bwoman\s+entrepreneur\b': 3,
    r'\bfitness\s+girl\b': 3,
    r'\byoga\s+instructor\b': 3,
}

FEMALE_RELATIONSHIPS = {
    r'\bmom\b': 1.5,
    r'\bmother\b': 1.5,
    r'\bwife\b': 1.5,
    r'\bsister\b': 1.5,
}

# Business detection (from v1.3)
BUSINESS_KEYWORDS = {
    r'\bcertified\b': 10,
    r'\binstructor\b': 10,
    r'\btrainer\b': 10,
    r'\bcoach\b': 10,
    r'\bowner\b': 8,
    r'\bfoundress\b': 8,
    r'\bfounder\b': 8,
    r'\bmanager\b': 8,
    r'\bdirector\b': 8,
    r'\bspecialist\b': 5,
    r'\bprofessional\b': 5,
}

def fetch_tag(tag, pages=8):
    """Fetch users from Instagram hashtag (discover)"""
    results = []
    url = f'https://www.instagram.com/api/v1/ig_hashtag_search/?user_id=&ig_sig_key_version=4&hl=en'
    
    for page in range(pages):
        params = {'search_surface': 'hashtag_search_page', 'count': 50, 'query': tag}
        try:
            r = requests.get(url, params=params, headers=HEADERS, cookies=COOKIES, timeout=15)
            if r.status_code == 200:
                data = r.json()
                if 'hashtags' in data and data['hashtags']:
                    hashtag_id = data['hashtags'][0]['id']
                    
                    # Fetch posts from this hashtag
                    posts_url = f'https://www.instagram.com/api/v1/ig_hashtag_posts/?ig_hashtag_id={hashtag_id}'
                    pr = requests.get(posts_url, headers=HEADERS, cookies=COOKIES, timeout=15)
                    if pr.status_code == 200:
                        posts_data = pr.json()
                        if 'edge_hashtag_to_media' in posts_data:
                            for edge in posts_data['edge_hashtag_to_media']['edges'][:20]:
                                user = edge['node']['owner']
                                results.append({
                                    'username': user['username'],
                                    'user_id': user['id'],
                                })
            time.sleep(2)
        except Exception as e:
            print(f"  ⚠ Tag fetch error: {e}")
            time.sleep(5)
    
    return results

def enrich_user(username):
    """Fetch user profile data"""
    try:
        url = f'https://www.instagram.com/api/v1/users/web_profile_info/?username={username}'
        r = requests.get(url, headers=HEADERS, cookies=COOKIES, timeout=15)
        
        if r.status_code == 200:
            data = r.json()
            if 'data' in data and 'user' in data['data']:
                user = data['data']['user']
                return {
                    'username': user.get('username', ''),
                    'full_name': user.get('full_name', ''),
                    'biography': user.get('biography', ''),
                    'follower_count': user.get('edge_followed_by', {}).get('total_count', 0),
                    'is_business': user.get('is_business_account', False),
                    'category': user.get('category_name', ''),
                }
        time.sleep(1)
    except Exception as e:
        print(f"  ⚠ Enrich error for @{username}: {e}")
        time.sleep(3)
    
    return None

def calc_female_score(full_name, bio):
    """Calculate female demographic score (v1.3)"""
    text = f"{full_name} {bio}".lower()[:500]
    score = 0.0
    
    for pattern, points in FEMALE_PRONOUNS.items():
        if re.search(pattern, text, re.IGNORECASE):
            score += points
    
    for pattern, points in FEMALE_NOUNS.items():
        if re.search(pattern, text, re.IGNORECASE):
            score += points
    
    for pattern, points in FEMALE_RELATIONSHIPS.items():
        if re.search(pattern, text, re.IGNORECASE):
            score += points
    
    return min(score, 10.0)

def calc_business_score(full_name, bio):
    """Calculate business likelihood score (v1.3)"""
    text = f"{full_name} {bio}".lower()[:500]
    score = 0
    
    for pattern, points in BUSINESS_KEYWORDS.items():
        if re.search(pattern, text, re.IGNORECASE):
            score += points
    
    return min(score, 10)

def passes_filter(result):
    """Apply IG-1 filters"""
    foll = result.get('follower_count', 0)
    is_biz = result.get('is_business', False)
    female_score = result.get('female_score', 0)
    business_score = result.get('business_score', 0)
    
    # Follower range filter
    if foll < 500 or foll > 3500:
        return False
    
    # Female filter (primary)
    if female_score < 3.0:
        # If business, apply Q4 logic
        if is_biz and business_score >= 3.5 and female_score >= 3.5:
            return True
        return False
    
    return True

def main():
    # Setup Google Sheets
    token_path = Path.home() / '.hermes' / 'google_token.json'
    creds = Credentials.from_authorized_user_file(str(token_path))
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    
    client = gspread.authorize(creds)
    ig1_sheet_id = '1Wo0kl-vcalbflt3sUgjwVNaP3ZbtRfaNmH0NqA0j5mw'
    ig1_sheet = client.open_by_key(ig1_sheet_id)
    
    # Create new tab for this run
    run_id = datetime.now().strftime('%Y%m%d-%H%M%S')
    tab_name = f'Crawl-{run_id}'
    
    try:
        ws = ig1_sheet.add_worksheet(title=tab_name, rows=1000, cols=10)
    except:
        ws = ig1_sheet.worksheet(tab_name)
    
    # Headers
    headers = ['Username', 'Full Name', 'Followers', 'Female Score', 'Business Score', 'Bio Preview', 'Is Business', 'Follower Velocity', 'Signal Strength', 'Crawled At']
    ws.append_row(headers)
    
    print(f"\n🔍 IG-1 LIVE CRAWLER — Running crawl {run_id}\n")
    print(f"Creating new tab: {tab_name}\n")
    
    all_results = []
    seen_usernames = set()
    
    # Discovery phase
    for city in CITIES:
        print(f"📍 {city}")
        city_results = []
        
        for hashtag in HASHTAGS[city][:HASHTAGS_PER_CITY]:
            print(f"  #{hashtag}...", end=' ', flush=True)
            users = fetch_tag(hashtag, pages=5)
            print(f"found {len(users)}")
            
            for user in users:
                if user['username'] not in seen_usernames:
                    city_results.append(user)
                    seen_usernames.add(user['username'])
            
            time.sleep(3)
        
        print(f"  → {len(city_results)} new users discovered\n")
        
        # Enrichment phase
        print(f"  Enriching {len(city_results)} profiles...")
        enriched = []
        for i, user in enumerate(city_results[:50]):  # Limit to 50 per city
            username = user['username']
            profile = enrich_user(username)
            
            if profile:
                # Scoring
                profile['female_score'] = calc_female_score(profile['full_name'], profile['biography'])
                profile['business_score'] = calc_business_score(profile['full_name'], profile['biography'])
                
                # Filtering
                if passes_filter(profile):
                    enriched.append(profile)
                    print(f"    [{i+1:2d}] @{username:25s} ✓ female:{profile['female_score']:4.1f} | followers:{profile['follower_count']:5d}")
            
            time.sleep(1)
        
        print(f"  → {len(enriched)} passed filters\n")
        all_results.extend(enriched)
    
    # Save to sheet
    print(f"\n📊 Saving {len(all_results)} results to Google Sheet...\n")
    
    for result in all_results:
        bio_preview = result['biography'][:50] if result['biography'] else ''
        row = [
            result['username'],
            result['full_name'],
            result['follower_count'],
            round(result['female_score'], 2),
            round(result['business_score'], 2),
            bio_preview,
            'Yes' if result['is_business'] else 'No',
            'N/A',  # Follower velocity (not in live data)
            'N/A',  # Signal strength
            datetime.now().isoformat(),
        ]
        ws.append_row(row)
    
    print(f"✓ Crawl complete!")
    print(f"  Total discovered: {len(seen_usernames)}")
    print(f"  Passed filters: {len(all_results)}")
    print(f"  Tab created: {tab_name}")
    print(f"  Sheet: IG-1 Protocol Results")

if __name__ == '__main__':
    main()
