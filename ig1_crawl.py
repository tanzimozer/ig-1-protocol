"""
IG1 Crawler — Stage 1: Discovery + Enrichment
One process per city. Saves to ~/.hermes/ig1/results/{city}.json
Feedback loop: loads follow-back data to score and refine future selections.
"""

import requests, json, time, random, re, sys, os
from datetime import datetime
from pathlib import Path
from ig1_business_filter import passes_business_filter
from ig1_female_filter import passes_female_filter

CITY = sys.argv[1]
BASE = Path.home() / '.hermes' / 'ig1'
RESULTS_DIR = BASE / 'results'
FEEDBACK_FILE = BASE / 'feedback.json'
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
OUT = RESULTS_DIR / f'{CITY.lower().replace(" ","_")}.json'

vault = json.load(open(Path.home() / '.hermes' / 'vault.json'))['instagram']
COOKIES = {
    'sessionid': vault['sessionid'],
    'csrftoken': vault['csrftoken'],
    'datr': vault['datr'],
    'mid': vault['mid'],
    'ig_did': vault['ig_did'],
    'ds_user_id': vault['ds_user_id'],
}
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1',
    'X-CSRFToken': COOKIES['csrftoken'],
    'X-IG-App-ID': '936619743392459',
    'Referer': 'https://www.instagram.com/',
}

CITY_TAGS = {
    'Melbourne':      ['melbournegirl','melbournewomen','melbournelife','melbournestyle','melbournefoodie',
                       'melbournelifestyle','melbourneblogger','melbournediary','melbournemum','melbourne'],
    'Sydney':         ['sydneygirl','sydneywomen','sydneylife','sydneystyle','sydneyfoodie',
                       'sydneylifestyle','sydneyblogger','sydney','sydneymum','sydneyliving'],
    'London':         ['londonlife','londongirl','londonwomen','londonstyle','londonfoodie',
                       'londonlifestyle','londonblogger','londondiaries','londonmum','london'],
    'Tallinn':        ['tallinnlife','tallinnwomen','tallinnstyle','tallinngirl','tallinnblogger',
                       'eestinaised','tallinn','estonianwomen','estonianlife','eesti'],
    'Brisbane':       ['brisbanegirl','brisbanewomen','brisbanelife','brisbanestyle','brisbanefoodie',
                       'brisbanelifestyle','brisbaneblogger','brisbane','brisbanemum','brisbaneliving'],
    'Anchorage':      ['anchoragelife','anchoragewomen','alaskawomen','alaskalife','alaskagirl',
                       'anchoragegirl','alaskalifestyle','alaska','anchorageliving','alaskaliving'],
    'Edmonton':       ['edmontonlife','edmontonwomen','yeglife','yegwomen','edmontongirl',
                       'yeg','edmontonlifestyle','yeglifestyle','edmontonfoodie','yegblogger'],
    'Dallas':         ['dallaslife','dallaswomen','dallasgirl','dallasstyle','dallasfoodie',
                       'dallaslifestyle','dallasblogger','dallas','dallasmom','dfwwomen'],
    'Chicago':        ['chicagolife','chicagowomen','chicagogirl','chicagostyle','chicagofoodie',
                       'chicagolifestyle','chicagoblogger','chicago','chicagomom','chitownwomen'],
    'Salt Lake City': ['slclife','slcwomen','slcgirl','utahwomen','utahlife',
                       'utahgirl','slclifestyle','utahlifestyle','saltlakecity','utahliving'],
    'Portland':       ['portlandlife','portlandwomen','portlandgirl','portlandstyle','portlandfoodie',
                       'portlandlifestyle','portlandblogger','pdxlife','pdxwomen','pdx'],
    'Warsaw':         ['warszawalife','warszawagirl','warszawawomen','warsawlife','polska',
                       'polishgirl','warsaw','warszawa','polishwomen','warsawblogger'],
    'Kyiv':           ['kyivlife','kyivgirl','kyivwomen','ukrainianwomen','ukrainiangirl',
                       'ukraine','kyiv','kyivlifestyle','kyivblogger','kievgirl'],
    'Moscow':         ['moscowlife','moscowgirl','moscowwomen','russianwomen','russiangirl',
                       'russia','moscow','moscowlifestyle','moscowblogger','moskvagirl'],
}

FEMALE_SIGNALS = [
    'she','her','woman','women','girl','lady','female','mum','mom','mama',
    'queen','sis','sister','wife','daughter','she/her','miss','mrs',
    'nainen','naine','жен','девушка','мама','сестра','blogger','babe'
]

BUSINESS_SIGNALS = [
    'studio','official','brand','shop','store','boutique','co.','ltd',
    'pty','inc','llc','academy','clinic','agency','services','consulting'
]

def log(msg):
    print(f'[{CITY}] {msg}', flush=True)

# ── Feedback loop ────────────────────────────────────────────────────────────
def load_feedback():
    """Load follow-back patterns to score accounts."""
    try:
        return json.loads(FEEDBACK_FILE.read_text())
    except:
        return {'followed_back': [], 'patterns': {}}

def score_account(u, feedback):
    """
    Score 0–100 based on how well this account matches follow-back patterns.
    Higher = more likely to follow back based on historical data.
    """
    score = 50  # baseline
    patterns = feedback.get('patterns', {})

    fc = u.get('follower_count', 0)
    following = u.get('following_count', 0)
    ratio = following / fc if fc > 0 else 0

    # Accounts that follow more than they have followers tend to follow back
    if ratio > 1.2:
        score += 15
    elif ratio > 0.8:
        score += 8

    # Sweet spot follower range (tighter = more personal)
    if 700 <= fc <= 2000:
        score += 10
    elif 500 <= fc <= 3500:
        score += 5

    # Bio signals that matched follow-backs historically
    bio = (u.get('biography') or '').lower()
    for signal in patterns.get('bio_signals', []):
        if signal in bio:
            score += 5

    # Female signal in bio = warmer account
    if any(s in bio for s in FEMALE_SIGNALS):
        score += 10

    # Has profile pic, not default
    if u.get('profile_pic_url') and 'default' not in u.get('profile_pic_url',''):
        score += 5

    return min(score, 100)

def update_feedback(username, followed_back):
    """Record whether an account followed back — feeds future scoring."""
    feedback = load_feedback()
    entry = {'username': username, 'followed_back': followed_back, 'recorded_at': datetime.utcnow().isoformat()}
    feedback['followed_back'].append(entry)

    # Recompute patterns from follow-back data
    fb_accounts = [e['username'] for e in feedback['followed_back'] if e['followed_back']]
    feedback['total_followed_back'] = len(fb_accounts)
    feedback['follow_back_rate'] = len(fb_accounts) / max(len(feedback['followed_back']), 1)

    FEEDBACK_FILE.write_text(json.dumps(feedback, indent=2))

# ── Instagram API calls ───────────────────────────────────────────────────────
def fetch_tag(tag, max_pages=5):
    uids = {}
    url = f'https://www.instagram.com/api/v1/tags/{tag}/sections/'
    for page in range(1, max_pages+1):
        try:
            r = requests.post(url, cookies=COOKIES, headers=HEADERS,
                              data={'tab':'recent','page':page,'count':33}, timeout=15)
            if r.status_code != 200:
                break
            data = r.json()
            for section in data.get('sections', []):
                for media in section.get('layout_content', {}).get('medias', []):
                    user = media.get('media', {}).get('user', {})
                    uid = str(user.get('pk', ''))
                    uname = user.get('username', '')
                    if uid and uname:
                        uids[uid] = {
                            'username': uname,
                            'full_name': user.get('full_name',''),
                            'is_private': user.get('is_private', False),
                        }
            if not data.get('more_available'):
                break
        except Exception as e:
            log(f'tag error {tag}: {e}')
            break
        time.sleep(random.uniform(1.5, 3.0))
    return uids

def enrich_user(username, retries=3):
    """web_profile_info endpoint — returns full user JSON without enrich rate limit."""
    for attempt in range(retries):
        try:
            r = requests.get(
                'https://www.instagram.com/api/v1/users/web_profile_info/',
                params={'username': username},
                cookies=COOKIES,
                headers={**HEADERS, 'Accept': 'application/json'},
                timeout=12
            )
            if r.status_code == 200:
                data = r.json()
                return data.get('data', {}).get('user', {})
            elif r.status_code == 429:
                log(f'rate limited — sleeping 45s')
                time.sleep(45)
            elif r.status_code == 404:
                return None
            else:
                time.sleep(5)
        except Exception as e:
            log(f'enrich error {username}: {e}')
            time.sleep(3)
    return None

# ── Filters ───────────────────────────────────────────────────────────────────
def passes_filter(u):
    """Combined filter: follower range + privacy + business + female (OPTIMIZED)."""
    if not u:
        return False
    if u.get('is_private'):
        return False
    fc = u.get('edge_followed_by', {}).get('count', 0) or u.get('follower_count', 0)
    if not (500 <= fc <= 3500):
        return False
    
    # Extract fields once (avoid duplicate extraction across filters)
    username = u.get('username', '')
    full_name = u.get('full_name', '')
    bio = u.get('biography', '')
    is_biz_flag = u.get('is_business_account', False)
    
    # Business filter
    passes_biz_filter, _ = passes_business_filter(username, full_name, bio, is_biz_flag)
    if not passes_biz_filter:
        return False
    
    # Female filter (business filter result passed directly)
    is_female, _ = passes_female_filter(username, full_name, bio, is_biz_flag)
    if not is_female:
        return False
    
    return True

def female_score(u):
    """Score female signal strength for ranking (separate from filter threshold)."""
    from ig1_female_filter import score_female_signals
    username = u.get('username', '')
    full_name = u.get('full_name', '')
    bio = u.get('biography', '')
    score, _ = score_female_signals(username, full_name, bio)
    return score

# ── Main ──────────────────────────────────────────────────────────────────────
feedback = load_feedback()

# Load existing results and seen UIDs
results = []
seen = set()
try:
    with open('/tmp/ig_final_v5.json') as f:
        seeds = json.load(f)
    seen.update(str(s['uid']) for s in seeds)
except:
    pass

if OUT.exists():
    results = json.loads(OUT.read_text())
    seen.update(e['uid'] for e in results)
    log(f'resuming — {len(results)} already found')
else:
    log('starting fresh')

def save():
    OUT.write_text(json.dumps(results, indent=2))

tags = CITY_TAGS.get(CITY, [])
log(f'{len(tags)} tags | feedback rate: {feedback.get("follow_back_rate", 0):.0%}')

for tag in tags:
    if len(results) >= 50:
        log('quota reached (50)')
        break

    log(f'#{tag}')
    candidates = fetch_tag(tag)
    log(f'  {len(candidates)} candidates')

    for uid, u in candidates.items():
        if len(results) >= 50:
            break
        if uid in seen or u.get('is_private'):
            continue

        seen.add(uid)
        uname = u['username']

        # Enrich via web_profile_info
        full = enrich_user(uname)
        if not full:
            time.sleep(random.uniform(2, 4))
            continue

        if not passes_filter(full):
            time.sleep(random.uniform(1, 2))
            continue

        fc = full.get('edge_followed_by', {}).get('count', 0)
        following = full.get('edge_follow', {}).get('count', 0)
        bio = (full.get('biography') or '')[:120].replace('\n',' ')
        fscore = female_score(full)
        account_score = score_account({
            'follower_count': fc,
            'following_count': following,
            'biography': full.get('biography',''),
            'profile_pic_url': full.get('profile_pic_url',''),
        }, feedback)

        entry = {
            'city': CITY,
            'username': uname,
            'full_name': full.get('full_name',''),
            'followers': fc,
            'following': following,
            'bio': bio,
            'uid': uid,
            'female_score': fscore,
            'account_score': account_score,
            'followed_back': None,  # populated later by feedback loop
            'crawled_at': datetime.utcnow().isoformat(),
        }
        results.append(entry)
        save()
        log(f'  + @{uname} — {fc} followers | score:{account_score} | female:{fscore}')

        time.sleep(random.uniform(8, 14))  # respectful pacing on enrich

    time.sleep(random.uniform(4, 8))

# Sort by score descending before final save
results.sort(key=lambda x: x.get('account_score', 0), reverse=True)
save()
log(f'DONE — {len(results)} targets | top score: {results[0]["account_score"] if results else 0}')
