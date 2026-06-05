"""
IG1 Feedback Loop — checks who followed back and updates patterns.
Run this after each follow batch to refine scoring.
Usage: python3 ig1_feedback.py
"""

import requests, json, time
from pathlib import Path
from datetime import datetime

BASE = Path.home() / '.hermes' / 'ig1'
FEEDBACK_FILE = BASE / 'feedback.json'
RESULTS_DIR = BASE / 'results'

COOKIES = json.load(open(Path.home() / '.hermes' / 'vault.json'))['instagram']
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15',
    'X-CSRFToken': COOKIES['csrftoken'],
    'X-IG-App-ID': '936619743392459',
}

def check_follows_back(uid):
    """Check if account is now following @tanzim.ozer back."""
    try:
        r = requests.get(
            f'https://www.instagram.com/api/v1/friendships/show/{uid}/',
            cookies=COOKIES, headers=HEADERS, timeout=12
        )
        if r.status_code == 200:
            return r.json().get('followed_by_viewer', False) or r.json().get('following', False)
    except:
        pass
    return None

def extract_bio_patterns(followed_back_entries, all_entries):
    """Find bio words/phrases that correlate with following back."""
    from collections import Counter

    fb_words = Counter()
    nonfb_words = Counter()

    for e in all_entries:
        bio = e.get('bio','').lower().split()
        if e.get('followed_back'):
            fb_words.update(bio)
        elif e.get('followed_back') is False:
            nonfb_words.update(bio)

    # Words that appear more in follow-backs than non
    signals = []
    for word, count in fb_words.items():
        if len(word) < 3:
            continue
        noncount = nonfb_words.get(word, 0)
        if count > 1 and count > noncount * 1.5:
            signals.append(word)

    return signals[:20]

# Load all results
all_results = []
for f in RESULTS_DIR.glob('*.json'):
    try:
        all_results.extend(json.loads(f.read_text()))
    except:
        pass

# Find accounts with unknown follow-back status (followed but not yet checked)
to_check = [r for r in all_results if r.get('followed_back') is None and r.get('uid')]
print(f'Accounts to check: {len(to_check)}')

updated = 0
for account in to_check[:50]:  # check up to 50 at a time
    uid = account['uid']
    result = check_follows_back(uid)
    if result is not None:
        account['followed_back'] = result
        account['checked_at'] = datetime.utcnow().isoformat()
        updated += 1
        status = 'FOLLOWED BACK' if result else 'no follow-back'
        print(f'  @{account["username"]}: {status}')
    time.sleep(random.uniform(2, 4))

# Save updated results back
by_city = {}
for r in all_results:
    city = r['city']
    by_city.setdefault(city, []).append(r)

for city, entries in by_city.items():
    f = RESULTS_DIR / f'{city.lower().replace(" ","_")}.json'
    f.write_text(json.dumps(entries, indent=2))

# Update feedback patterns
followed_back = [r for r in all_results if r.get('followed_back')]
total_checked = [r for r in all_results if r.get('followed_back') is not None]
rate = len(followed_back) / max(len(total_checked), 1)

bio_patterns = extract_bio_patterns(followed_back, all_results)

feedback = {
    'total_followed': len(all_results),
    'total_checked': len(total_checked),
    'total_followed_back': len(followed_back),
    'follow_back_rate': rate,
    'patterns': {
        'bio_signals': bio_patterns,
    },
    'followed_back': [{'username': r['username'], 'city': r['city'],
                       'followers': r['followers'], 'account_score': r.get('account_score',0)}
                      for r in followed_back],
    'updated_at': datetime.utcnow().isoformat(),
}

FEEDBACK_FILE.write_text(json.dumps(feedback, indent=2))
print(f'\nFollow-back rate: {rate:.1%} ({len(followed_back)}/{len(total_checked)} checked)')
print(f'Bio patterns that predict follow-back: {bio_patterns}')
print(f'Updated {updated} accounts.')
