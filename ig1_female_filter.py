"""
IG-1 Female Signal Detection — Weighted Scoring System
Fast, cost-efficient, token-zero female profile identification.

Architecture:
  - Weighted signals: pronouns (3pts) > gender nouns (2pts) > relationship (1.5pts) > generic (0.5pts)
  - Threshold: ≥2.5 to flag as female
  - Languages: English, Estonian, Russian (combined pool)
  - Business filter integration: if business=true, skip female scoring
  - Zero API calls. Regex-only. <30ms per profile.
"""

import re
from typing import Tuple

# ═══════════════════════════════════════════════════════
# SIGNAL DEFINITIONS (English + Estonian + Russian)
# ═══════════════════════════════════════════════════════

FEMALE_SIGNALS = {
    'pronouns': {
        'signals': ['she/her', 'she /her', 'she/ her', 'she / her', 'they/them', 'they /them', 'they/ them', 'they / them'],
        'weight': 3.0,
        'description': 'Explicit pronouns — highest confidence'
    },
    'gender_nouns': {
        'signals': [
            # English
            'woman', 'women', 'girl', 'lady', 'female', 'sis', 'sister',
            # Estonian
            'naine', 'nainen', 'tüdruk',
            # Russian
            'женщина', 'девушка', ' girl', 'леди'
        ],
        'weight': 2.0,
        'description': 'Gender nouns (woman, girl, lady, etc.)'
    },
    'relationships': {
        'signals': [
            # English
            'mum', 'mom', 'mama', 'daughter', 'sister', 'wife', 'nana', 'auntie', 'grandma', 'niece',
            # Estonian
            'ema', 'isa',
            # Russian
            'мама', 'сестра', 'дочь', 'жена'
        ],
        'weight': 1.5,
        'description': 'Relationship/family terms'
    },
    'generic': {
        'signals': ['blogger', 'babe', 'queen', 'boss', 'fashionista'],
        'weight': 0.5,
        'description': 'Generic/low-value signals'
    }
}

# ═══════════════════════════════════════════════════════
# FEMALE SIGNAL SCORING
# ═══════════════════════════════════════════════════════

def score_female_signals(username: str, full_name: str, bio: str) -> Tuple[float, dict]:
    """
    Score female signals across username, full_name, and bio.
    Returns (total_score, breakdown).
    
    Score ≥2.5 = flag as female.
    All languages in one pool (English + Estonian + Russian).
    """
    combined_text = f"{username} {full_name} {bio}".lower()
    
    breakdown = {
        'pronouns': 0.0,
        'gender_nouns': 0.0,
        'relationships': 0.0,
        'generic': 0.0,
    }
    
    # Pronouns (highest weight)
    pronoun_matches = 0
    for signal in FEMALE_SIGNALS['pronouns']['signals']:
        if signal.lower() in combined_text:
            pronoun_matches += 1
    breakdown['pronouns'] = pronoun_matches * FEMALE_SIGNALS['pronouns']['weight']
    
    # Gender nouns
    gender_noun_matches = 0
    for signal in FEMALE_SIGNALS['gender_nouns']['signals']:
        # Word boundary match to avoid partial matches (e.g., "woman" in "womanizer")
        if re.search(rf'\b{re.escape(signal)}\b', combined_text, re.IGNORECASE):
            gender_noun_matches += 1
    breakdown['gender_nouns'] = gender_noun_matches * FEMALE_SIGNALS['gender_nouns']['weight']
    
    # Relationship terms
    relationship_matches = 0
    for signal in FEMALE_SIGNALS['relationships']['signals']:
        if re.search(rf'\b{re.escape(signal)}\b', combined_text, re.IGNORECASE):
            relationship_matches += 1
    breakdown['relationships'] = relationship_matches * FEMALE_SIGNALS['relationships']['weight']
    
    # Generic signals
    generic_matches = 0
    for signal in FEMALE_SIGNALS['generic']['signals']:
        if signal.lower() in combined_text:
            generic_matches += 1
    breakdown['generic'] = generic_matches * FEMALE_SIGNALS['generic']['weight']
    
    total_score = sum(breakdown.values())
    
    return total_score, breakdown


# ═══════════════════════════════════════════════════════
# FEMALE FLAG DECISION
# ═══════════════════════════════════════════════════════

def is_female_account(username: str, full_name: str, bio: str, threshold: float = 2.5) -> Tuple[bool, float, dict]:
    """
    Determine if account is likely female based on signal scoring.
    
    Args:
        username: Instagram username
        full_name: Full name from profile
        bio: Biography text
        threshold: Minimum score to flag as female (default: 2.5)
    
    Returns:
        (is_female, score, breakdown)
    """
    if not bio or not username:
        return False, 0.0, {}
    
    score, breakdown = score_female_signals(username, full_name, bio)
    is_female = score >= threshold
    
    return is_female, score, breakdown


# ═══════════════════════════════════════════════════════
# INTEGRATION: Filter pipeline entry point
# ═══════════════════════════════════════════════════════

def passes_female_filter(username: str, full_name: str, bio: str, is_business: bool = False) -> Tuple[bool, dict]:
    """
    Combined female detection with business filter integration.
    
    Returns:
        (passes_filter, detection_details)
    
    Logic:
      - If business=true, skip female scoring entirely (return False)
      - Otherwise, run female signal detection (threshold ≥2.5)
    """
    
    # Short-circuit: if business account, reject (don't score female)
    if is_business:
        return False, {
            'method': 'business_filter',
            'is_female': False,
            'reason': 'Business account — skipped female scoring'
        }
    
    # Run female signal detection
    is_female, score, breakdown = is_female_account(username, full_name, bio, threshold=2.5)
    
    return is_female, {
        'method': 'weighted_female_scoring',
        'is_female': is_female,
        'score': score,
        'breakdown': breakdown,
        'threshold': 2.5,
    }
