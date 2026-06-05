#!/usr/bin/env python3
"""
Protocol Veronica — Instagram Scraper
Targets: Female fitness accounts across 14 cities globally.
Filter: 500–3,500 followers, public accounts only.
Output: JSON + CSV export.
"""

import requests
import json
import time
import csv
from datetime import datetime

# ============================================================
# Configuration
# ============================================================

CITIES = {
    'Melbourne': {
        'tags': [
            'melbournefit', 'melbournefitness', 'melbournegym', 'melbourneyoga',
            'melbournewellness', 'melbournepilates', 'melbournerunning', 'melbourneactive',
            'fitmelbourne', 'melbournebootcamp', 'melbournelifting', 'gymmelbourne',
            'yogamelbourne', 'pilatesmelbourne', 'melbournegirlswholift', 'melbournewomen',
            'melbournehealth', 'melbournedance', 'melbournespin', 'melbournecrossfit',
            'melbourneboxing', 'melbournehiit',
        ],
        'target_count': 100,
    },
    'Tallinn': {
        'tags': [
            'tallinnwomen', 'eestifitness', 'fitnesseesti', 'tallinnlife', 'estonialife',
            'eestinaised', 'tallinnlifestyle', 'estonianwomen', 'estonianfit', 'estonia',
            'estonianlife', 'tallinnactive', 'estonianwellness', 'tallinnhealth', 'estonianlifestyle',
            'tallinn', 'tallinnfit', 'tallinnfitness', 'estoniafit', 'tallinnsport',
        ],
        'target_count': 50,
    },
}

FEMALE_SIGNALS = [
    'she', 'her', 'woman', 'women', 'girl', 'lady', 'female', 'mum', 'mom', 'mama',
    'queen', 'sis', 'sister', 'wife', 'daughter', 'nainen', 'naine', 'she/her',
    'miss', 'mrs', 'fitness woman', 'female trainer', 'girl boss', 'women fitness',
]

FOLLOWER_RANGE = (500, 3500)

# ============================================================
# Functions
# ============================================================

def load_cookies(vault_path='~/.hermes/vault.json'):
    """Load Instagram cookies from vault."""
    import os
    vault_path = os.path.expanduser(vault_path)
    try:
        with open(vault_path) as f:
            vault = json.load(f)
            return vault.get('instagram', {})
    except Exception as e:
        print(f"Error loading vault: {e}")
        return {}

def is_female(user):
    """Check if user profile signals female."""
    combined = ' '.join([
        (user.get('biography') or '').lower(),
        (user.get('full_name') or '').lower(),
        (user.get('username') or '').lower(),
    ])
    return any(signal in combined for signal in FEMALE_SIGNALS)

def fetch_tag(tag, cookies, headers, max_pages=8):
    """Fetch candidates from a single hashtag."""
    uids = {}
    url = f'https://www.instagram.com/api/v1/tags/{tag}/sections/'
    
    for page in range(1, max_pages + 1):
        try:
            r = requests.post(
                url,
                cookies=cookies,
                headers=headers,
                data={'tab': 'recent', 'page': page, 'count': 33},
                timeout=15
            )
            if r.status_code != 200:
                break
            
            data = r.json()
            for section in data.get('sections', []):
                for media in section.get('layout_content', {}).get('medias', []):
                    user = media.get('media', {}).get('user', {})
                    uid = str(user.get('pk', ''))
                    uname = user.get('username', '')
                    if uid and uname:
                        uids[uid] = uname
            
            if not data.get('more_available'):
                break
        except Exception as e:
            print(f"  Tag fetch error ({tag}): {e}")
            break
        
        time.sleep(1.2)
    
    return uids

def enrich(uid, cookies, headers, retries=3):
    """Fetch full user info."""
    for attempt in range(retries):
        try:
            r = requests.get(
                f'https://www.instagram.com/api/v1/users/{uid}/info/',
                cookies=cookies,
                headers=headers,
                timeout=12
            )
            if r.status_code == 200 and r.text.strip():
                return r.json().get('user', {})
            elif r.status_code == 429:
                print(f"  Rate limited — waiting 30s")
                time.sleep(30)
            else:
                return None
        except Exception as e:
            print(f"  Enrich error ({uid}): {e}")
            time.sleep(3)
    
    return None

def run_crawler(city, config, cookies, headers):
    """Run crawler for a single city."""
    print(f"\n=== {city.upper()} ===")
    results = []
    seen = set()
    
    for tag in config['tags']:
        if len(results) >= config['target_count']:
            break
        
        print(f"#{tag}")
        raw = fetch_tag(tag, cookies, headers)
        print(f"  candidates: {len(raw)}")
        
        for uid, uname in raw.items():
            if uid in seen:
                continue
            seen.add(uid)
            
            u = enrich(uid, cookies, headers)
            if not u:
                continue
            
            if u.get('is_private'):
                continue
            
            fc = u.get('follower_count', 0)
            if not (FOLLOWER_RANGE[0] <= fc <= FOLLOWER_RANGE[1]):
                continue
            
            if not is_female(u):
                continue
            
            results.append({
                'city': city,
                'username': uname,
                'full_name': u.get('full_name', ''),
                'followers': fc,
                'bio': (u.get('biography') or '')[:120].replace('\n', ' '),
                'uid': uid,
                'verified': u.get('is_verified', False),
                'timestamp': datetime.now().isoformat(),
            })
            
            print(f"  ✓ @{uname} — {fc} followers")
            
            if len(results) >= config['target_count']:
                break
            
            time.sleep(1.5)
        
        time.sleep(2)
    
    return results

def main():
    """Run Protocol Veronica."""
    print("=" * 60)
    print("PROTOCOL VERONICA — Instagram Scraper")
    print("=" * 60)
    
    # Load credentials
    cookies = load_cookies()
    if not cookies:
        print("ERROR: No Instagram cookies found in vault.json")
        return
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
        'X-CSRFToken': cookies.get('csrftoken', ''),
        'X-IG-App-ID': '936619743392459',
        'Referer': 'https://www.instagram.com/',
    }
    
    all_results = []
    
    for city, config in CITIES.items():
        results = run_crawler(city, config, cookies, headers)
        all_results.extend(results)
        print(f"{city}: {len(results)} targets")
    
    # Save to JSON
    with open('targets.json', 'w') as f:
        json.dump(all_results, f, indent=2)
    
    # Save to CSV
    if all_results:
        with open('targets.csv', 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=all_results[0].keys())
            writer.writeheader()
            writer.writerows(all_results)
    
    print("\n" + "=" * 60)
    print(f"TOTAL: {len(all_results)} targets")
    print("=" * 60)
    print(f"JSON: targets.json")
    print(f"CSV: targets.csv")

if __name__ == '__main__':
    main()
