"""
IG-1 Pattern Analysis Engine
Batch-fetch handle data from Instagram and analyze for patterns.
Populates Consolidated Handles sheet with analysis metrics.
"""

import requests
import json
import time
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

class IG1PatternAnalyzer:
    def __init__(self, batch_size=10, delay_between_requests=2.5):
        """
        Initialize Instagram pattern analyzer.
        
        Args:
            batch_size: Handles per batch
            delay_between_requests: Seconds between API calls (rate limiting)
        """
        self.batch_size = batch_size
        self.delay = delay_between_requests
        
        # Load Instagram session
        vault = json.load(open(Path.home() / '.hermes' / 'vault.json'))['instagram']
        self.cookies = {
            'sessionid': vault['sessionid'],
            'csrftoken': vault['csrftoken'],
            'datr': vault['datr'],
            'mid': vault['mid'],
            'ig_did': vault['ig_did'],
            'ds_user_id': vault['ds_user_id'],
        }
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1',
            'X-CSRFToken': self.cookies['csrftoken'],
            'X-IG-App-ID': '936619743392459',
            'Referer': 'https://www.instagram.com/',
        }
    
    def fetch_profile(self, handle: str) -> Optional[Dict]:
        """Fetch user profile data from Instagram."""
        try:
            r = requests.get(
                'https://www.instagram.com/api/v1/users/web_profile_info/',
                params={'username': handle},
                cookies=self.cookies,
                headers={**self.headers, 'Accept': 'application/json'},
                timeout=12
            )
            
            if r.status_code == 200:
                return r.json().get('data', {}).get('user', {})
            elif r.status_code == 429:
                return {'error': 'rate_limited'}
            elif r.status_code == 404:
                return {'error': 'not_found'}
            else:
                return {'error': f'http_{r.status_code}'}
        except Exception as e:
            return {'error': str(e)}
    
    def analyze_profile(self, handle: str, profile: Dict) -> Dict:
        """
        Analyze profile data and extract pattern metrics.
        
        Returns:
            Dict with analysis columns for spreadsheet
        """
        if 'error' in profile:
            return {
                'followers_estimate': '',
                'follower_velocity': '',
                'account_age_estimate': '',
                'bio_signal_strength': '',
                'business_likelihood': '',
                'female_score_predicted': f"ERROR: {profile['error']}"
            }
        
        # Extract fields
        followers = profile.get('edge_followed_by', {}).get('count', 0) or profile.get('follower_count', 0)
        following = profile.get('edge_follow', {}).get('count', 0) or profile.get('following_count', 0)
        posts = profile.get('edge_owner_to_timeline_media', {}).get('count', 0) or profile.get('media_count', 0)
        bio = (profile.get('biography') or '').lower()
        full_name = (profile.get('full_name') or '').lower()
        is_verified = profile.get('is_verified', False)
        is_business = profile.get('is_business_account', False)
        
        # === METRIC 1: Follower Estimate (proxy for audience size) ===
        follower_category = 'micro' if followers < 10000 else 'mid' if followers < 100000 else 'macro'
        
        # === METRIC 2: Follower Velocity (growth trajectory) ===
        # Posts per follower = higher ratio = slower growth
        posts_per_follower = posts / followers if followers > 0 else 0
        if posts_per_follower > 0.5:
            follower_velocity = 'fast_growth'  # Few posts, many followers
        elif posts_per_follower > 0.1:
            follower_velocity = 'moderate'
        else:
            follower_velocity = 'slow_growth'  # Many posts, fewer followers
        
        # === METRIC 3: Account Age Estimate ===
        # Rough: if high posts + moderate followers = older account
        if posts > 1000:
            account_age = 'established (3+ years)'
        elif posts > 300:
            account_age = 'mature (1-3 years)'
        elif posts > 50:
            account_age = 'active (6-12 months)'
        else:
            account_age = 'new (<6 months)'
        
        # === METRIC 4: Bio Signal Strength ===
        bio_signals = 0
        if re.search(r'she/her|they/them|pronouns', bio):
            bio_signals += 3
        if re.search(r'she|her|woman|women|girl|lady|female|queen|wife|sister|mom|mum', bio):
            bio_signals += 2
        if re.search(r'fitness|gym|yoga|trainer|coach|athlete|active|wellness|health', bio):
            bio_signals += 2
        if re.search(r'instagram|content|creator|influencer|blogger', bio):
            bio_signals += 1
        if len(bio) > 100:
            bio_signals += 1
        
        bio_signal_score = min(bio_signals, 9)  # Cap at 9
        
        # === METRIC 5: Business Likelihood ===
        business_score = 0
        if is_business:
            business_score += 5
        if re.search(r'official|brand|shop|store|studio|agency|services|consulting', bio):
            business_score += 3
        if is_verified:
            business_score += 2
        if profile.get('external_url'):
            business_score += 2
        if re.search(r'coach|trainer|instructor|consultant|professional|certified', bio):
            business_score += 2
        
        business_likelihood = min(business_score, 10)
        
        # === METRIC 6: Female Score Prediction ===
        female_score = 0
        
        # Pronouns (highest weight)
        if re.search(r'she/her', bio):
            female_score += 3
        elif re.search(r'they/them', bio):
            female_score += 1
        
        # Gender nouns (high weight)
        female_nouns = len(re.findall(r'\b(she|her|woman|women|girl|lady|female|queen|wife|sister|mom|mum|babe|mama)\b', bio))
        female_score += min(female_nouns * 0.5, 3)
        
        # Relationship/family terms
        if re.search(r'wife|girlfriend|daughter|sister|mom|mum|mama|queen', bio):
            female_score += 1.5
        
        # Generic feminine signals
        if re.search(r'beauty|fashion|makeup|nails|hair|skincare|wellness|yoga|pilates', bio):
            female_score += 1
        
        # Age/life stage signals
        if re.search(r'23|24|25|26|27|28|29|30|31|32|33|34|35', bio):
            female_score += 0.5
        
        female_score = round(min(female_score, 10), 1)
        
        return {
            'followers_estimate': f"{followers:,} ({follower_category})",
            'follower_velocity': follower_velocity,
            'account_age_estimate': account_age,
            'bio_signal_strength': bio_signal_score,
            'business_likelihood': business_likelihood,
            'female_score_predicted': female_score
        }
    
    def analyze_batch(self, handles: List[str]) -> Dict[str, Dict]:
        """
        Analyze a batch of handles and return results keyed by handle.
        """
        results = {}
        for i, handle in enumerate(handles, 1):
            print(f"  [{i}/{len(handles)}] @{handle}...", end=' ', flush=True)
            
            profile = self.fetch_profile(handle)
            analysis = self.analyze_profile(handle, profile)
            results[handle] = analysis
            
            if 'ERROR' not in str(analysis.get('female_score_predicted', '')):
                print(f"✓ (female_score: {analysis['female_score_predicted']})")
            else:
                print(f"⚠ {analysis['female_score_predicted']}")
            
            time.sleep(self.delay)
        
        return results

if __name__ == '__main__':
    analyzer = IG1PatternAnalyzer(batch_size=10, delay_between_requests=2.5)
    print("IG-1 Pattern Analyzer ready. Call analyze_batch() with list of handles.")
