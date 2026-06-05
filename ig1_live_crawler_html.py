#!/usr/bin/env python3
"""
IG-1 Live Crawler — HTML Scraping Edition
Bypasses API rate limits via public profile HTML scraping
Fast, reliable, zero quota concerns
"""

import requests
from bs4 import BeautifulSoup
import json
import re
import time
from pathlib import Path
from datetime import datetime
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
import gspread

# Config
CITIES = [
    ('Seattle', ['seattlefitness', 'seattlegirl', 'seattleyoga']),
    ('Los Angeles', ['lafitness', 'lagirl', 'layoga']),
    ('Dallas', ['dallasfitness', 'dallasgirl', 'dallasyoga']),
    ('Chicago', ['chicagofitness', 'chicagogirl', 'chicagoyoga']),
]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
}

# Filters
FEMALE_PRONOUNS = {
    r'\bshe\b': 3, r'\bher\b': 3, r'\bshe/her\b': 3,
    r'\bthey/them\b': 1, r'\bthey\b': 1,
}
FEMALE_NOUNS = {
    r'\bgirl\b': 2, r'\bwoman\b': 2, r'\byoga\s+instructor\b': 3,
    r'\bfitness\s+coach\b': 3,
}
FEMALE_RELATIONSHIPS = {
    r'\bmom\b': 1.5, r'\bmother\b': 1.5, r'\bwife\b': 1.5, r'\bsister\b': 1.5,
}

BUSINESS_KEYWORDS = {
    r'\bcertified\b': 10, r'\binstructor\b': 10, r'\btrainer\b': 10, r'\bcoach\b': 10,
    r'\bowner\b': 8, r'\bmanager\b': 8, r'\bdirector\b': 8,
}

def scrape_hashtag_users(hashtag, max_users=30):
    """Scrape users from hashtag page (public HTML)"""
    results = []
    url = f'https://www.instagram.com/explore/tags/{hashtag}/'
    
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'html.parser')
            
            # Extract user links from posts
            for link in soup.find_all('a', href=re.compile(r'^/[^/]+/$')):
                username = link['href'].strip('/')
                if username and not username.startswith('explore'):
                    results.append(username)
                    if len(results) >= max_users:
                        break
        
        time.sleep(2)
    except Exception as e:
        print(f"  ⚠ Hashtag scrape error: {e}")
    
    return list(set(results))[:max_users]

def scrape_profile(username):
    """Scrape user profile via public HTML"""
    try:
        url = f'https://www.instagram.com/{username}/'
        r = requests.get(url, headers=HEADERS, timeout=15)
        
        if r.status_code == 200:
            # Extract JSON from HTML (Instagram embeds user data in script tags)
            match = re.search(r'"user":({.*?"username":"' + username + r'".*?})', r.text)
            if match:
                try:
                    user_data = json.loads(match.group(1))
                    return {
                        'username': user_data.get('username', ''),
                        'full_name': user_data.get('full_name', ''),
                        'biography': user_data.get('biography', ''),
                        'follower_count': user_data.get('edge_followed_by', {}).get('total_count', 0),
                        'is_business': user_data.get('is_business_account', False),
                    }
                except:
                    pass
        
        time.sleep(1)
    except Exception as e:
        print(f"  ⚠ Profile scrape error for @{username}: {e}")
    
    return None

def calc_female_score(full_name, bio):
    """Female score calculation"""
    text = f"{full_name} {bio}".lower()[:500]
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
    text = f"{full_name} {bio}".lower()[:500]
    score = 0
    for pattern, points in BUSINESS_KEYWORDS.items():
        if re.search(pattern, text):
            score += points
    return min(score, 10)

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
    # Setup Google Sheets
    token_path = Path.home() / '.hermes' / 'google_token.json'
    creds = Credentials.from_authorized_user_file(str(token_path))
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    
    client = gspread.authorize(creds)
    ig1_sheet_id = '1Wo0kl-vcalbflt3sUgjwVNaP3ZbtRfaNmH0NqA0j5mw'
    ig1_sheet = client.open_by_key(ig1_sheet_id)
    # Get Results tab (master) + create dated tab
    run_id = datetime.now().strftime('%Y%m%d-%H%M%S')
    date_tab = datetime.now().strftime('%b %d').lstrip('0')
    
    results_ws = ig1_sheet.worksheet('Results')
    
    try:
        dated_ws = ig1_sheet.add_worksheet(title=date_tab, rows=500, cols=11)
    except:
        dated_ws = ig1_sheet.worksheet(date_tab)
        dated_ws.clear()
    
    headers = ['Username', 'Full Name', 'Followers', 'Female Score', 'Business Score', 'Bio Preview', 'Is Business', 'City', 'Status', 'Crawled At', 'Run ID']
    dated_ws.append_row(headers)
    
    print(f"\n🔍 IG-1 LIVE CRAWLER (HTML SCRAPING)")
    print(f"Run ID: {run_id}")
    print(f"Date Tab: {date_tab}\n")
    
    all_results = []
    seen = set()
    
    for city, hashtags in CITIES:
        print(f"📍 {city}")
        city_results = []
        
        for hashtag in hashtags[:5]:
            print(f"  #{hashtag}...", end=' ', flush=True)
            users = scrape_hashtag_users(hashtag, max_users=15)
            print(f"found {len(users)}")
            
            for username in users:
                if username not in seen:
                    profile = scrape_profile(username)
                    
                    if profile:
                        profile['female_score'] = calc_female_score(profile['full_name'], profile['biography'])
                        profile['business_score'] = calc_business_score(profile['full_name'], profile['biography'])
                        profile['city'] = city
                        
                        if passes_filter(profile):
                            city_results.append(profile)
                            seen.add(username)
                            print(f"    ✓ @{username:25s} | female:{profile['female_score']:4.1f} | followers:{profile['follower_count']:5d}")
        
        print(f"  → {len(city_results)} passed filters\n")
        all_results.extend(city_results)
    
    # Save to Results tab (master) and dated tab
    print(f"\n📊 Appending {len(all_results)} results to Results + {date_tab}...")
    
    for result in all_results:
        bio_preview = result['biography'][:40] if result['biography'] else ''
        row = [
            result['username'],
            result['full_name'],
            result['follower_count'],
            round(result['female_score'], 2),
            round(result['business_score'], 2),
            bio_preview,
            'Yes' if result['is_business'] else 'No',
            result['city'],
            'analyzed',
            datetime.now().isoformat(),
            run_id,
        ]
        results_ws.append_row(row)
        dated_ws.append_row(row)
        time.sleep(0.5)
    
    print(f"✓ Complete!")
    print(f"  Total found: {len(seen)}")
    print(f"  Passed filters: {len(all_results)}")
    print(f"  Master: Results tab")
    print(f"  Dated: {date_tab}")
    print(f"  Run ID: {run_id}")

if __name__ == '__main__':
    main()
