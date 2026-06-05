"""
IG-1 Business Profile Detection — 3-Layer Filter
Fast, cost-efficient, token-zero business flagging for Instagram profiles.

Layers:
  1. Hard signals (bio, name, username keywords) — 10ms
  2. Hashtag density + patterns — 20ms
  3. Account naming conventions — 5ms

Combined score >70 = business account.
Zero API calls. Regex-only. <50ms per profile.
"""

import re
from typing import Tuple

# ═══════════════════════════════════════════════════════
# SIGNAL LISTS (Business keywords)
# ═══════════════════════════════════════════════════════

BUSINESS_KEYWORDS = {
    'services': ['studio', 'salon', 'spa', 'gym', 'clinic', 'academy', 'school',
                 'agency', 'boutique', 'shop', 'store', 'brand', 'official'],
    'specific': ['eyelash', 'lash', 'lashes', 'nails', 'hair', 'makeup', 'mua',
                 'beautician', 'trainer', 'coach', 'photographer', 'realtor'],
    'format': ['co.', 'ltd', 'inc', 'pty', 'llc', 'corp'],
    'roles': ['ceo', 'founder', 'owner', 'director', 'manager', 'partner'],
}

COMMERCIAL_HASHTAGS = {
    'sponsorship': ['#ad', '#sponsored', '#partner', '#ambassador', '#collaboration',
                    '#affiliate', '#promotion', '#deals', '#discount', '#collab'],
    'branded': ['#mybeautyline', '#fitnessgear', '#gymwear', '#beautyproducts',
                '#skincare', '#wellness', '#supplement'],
}

# ═══════════════════════════════════════════════════════
# LAYER 1: Hard Signals (Bio + Name + Username)
# ═══════════════════════════════════════════════════════

def score_hard_signals(username: str, full_name: str, bio: str) -> int:
    """Scan for obvious business keywords. Returns 0–60 points."""
    score = 0
    combined = f"{username} {full_name} {bio}".lower()
    
    # Business type keywords
    for category, keywords in BUSINESS_KEYWORDS.items():
        if category == 'roles':
            # Match possessive patterns: "CEO of X", "Founder of X"
            for role in keywords:
                if re.search(rf'\b{role}\s+of\b', combined, re.IGNORECASE):
                    score += 20
                    break
        else:
            # Match direct keywords
            for keyword in keywords:
                if keyword.lower() in combined:
                    score += 15
                    break
    
    # Format patterns: "XYZ Ltd", "XYZ Inc"
    if re.search(r'\b\w+\s+(ltd|inc|pty|llc|corp|co\.)\b', combined, re.IGNORECASE):
        score += 20
    
    return min(score, 60)


# ═══════════════════════════════════════════════════════
# LAYER 2: Hashtag Density + Patterns
# ═══════════════════════════════════════════════════════

def extract_hashtags(bio: str) -> list:
    """Extract hashtags from bio. Returns list of hashtags (lowercase, no #)."""
    return [tag[1:].lower() for tag in re.findall(r'#\w+', bio)]


def score_hashtag_patterns(bio: str) -> int:
    """Analyze hashtag density and commercial patterns. Returns 0–50 points."""
    score = 0
    hashtags = extract_hashtags(bio)
    
    if not hashtags:
        return 0
    
    # Commercial hashtag ratio
    commercial_count = sum(
        1 for tag in hashtags 
        if any(tag == ch[1:].lower() for ch in COMMERCIAL_HASHTAGS['sponsorship'] + COMMERCIAL_HASHTAGS['branded'])
    )
    commercial_ratio = commercial_count / len(hashtags)
    
    if commercial_ratio > 0.4:
        score += 30
    elif commercial_ratio > 0.2:
        score += 15
    
    # Repeated hashtags (broadcast signal)
    if len(hashtags) != len(set(hashtags)):
        score += 15
    
    # All hashtags are branded (100% commercial)
    if commercial_count == len(hashtags) and len(hashtags) >= 3:
        score += 10
    
    return min(score, 50)


# ═══════════════════════════════════════════════════════
# LAYER 3: Account Naming Conventions
# ═══════════════════════════════════════════════════════

def score_account_naming(username: str) -> int:
    """Detect generic business account naming patterns. Returns 0–25 points."""
    score = 0
    username_lower = username.lower()
    
    # Generic business structure: lowercase_with_underscores + numbers
    if re.match(r'^[a-z_]+_\d+$', username_lower):
        score += 15
    
    # City + service pattern: melbourne_gym, london_nails
    if re.search(r'\b(melbourne|sydney|london|tallinn|brisbane|anchorage|edmonton|dallas|chicago|salt lake|portland|warsaw|kyiv|moscow)\b', username_lower):
        if re.search(r'\b(gym|salon|studio|spa|beauty|fitness|nails|lash|coach|trainer)\b', username_lower):
            score += 20
    
    # Consecutive numbers at end (trendy for businesses: beautysalon_2024)
    if re.search(r'\d{4}$', username_lower):
        score += 10
    
    return min(score, 25)


# ═══════════════════════════════════════════════════════
# MAIN DECISION FUNCTION
# ═══════════════════════════════════════════════════════

def is_business_account(username: str, full_name: str, bio: str) -> Tuple[bool, int, dict]:
    """
    Determine if account is business. Returns (is_business, score, breakdown).
    
    Score >70 = business account.
    Zero API calls. Pure regex.
    """
    if not username or not bio:
        return False, 0, {}
    
    # Calculate layer scores
    layer1 = score_hard_signals(username, full_name, bio)
    layer2 = score_hashtag_patterns(bio)
    layer3 = score_account_naming(username)
    
    total_score = layer1 + layer2 + layer3
    
    breakdown = {
        'hard_signals': layer1,
        'hashtag_patterns': layer2,
        'account_naming': layer3,
        'total': total_score,
        'threshold': 70,
        'is_business': total_score > 70,
    }
    
    return total_score > 70, total_score, breakdown


# ═══════════════════════════════════════════════════════
# INTEGRATION: Filter pipeline entry point
# ═══════════════════════════════════════════════════════

def passes_business_filter(username: str, full_name: str, bio: str, is_business_account_flag: bool = False) -> Tuple[bool, dict]:
    """
    Combined business detection: structured flag + intelligent scoring.
    Returns (passes_filter, detection_details).
    
    Passes filter = NOT a business (False = good personal account).
    """
    # Shortcut: if Instagram marks it as business, auto-reject
    if is_business_account_flag:
        return False, {'method': 'instagram_flag', 'is_business': True}
    
    # Otherwise, run 3-layer filter
    is_biz, score, breakdown = is_business_account(username, full_name, bio)
    
    return not is_biz, {
        'method': '3_layer_filter',
        'is_business': is_biz,
        'score': score,
        'breakdown': breakdown,
    }
