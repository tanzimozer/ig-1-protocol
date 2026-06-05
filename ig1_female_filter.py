"""
IG-1 Female Signal Detection — Weighted Scoring System (v1.2 PRODUCTION)
Fast, cost-efficient, token-zero female profile identification.

CRITICAL FIXES (Opus audit):
  ✅ Null/empty input handling hardened
  ✅ Early-exit logic on threshold met (immediately return on ≥2.5)
  ✅ Bio length truncation (prevent ReDoS)
  ✅ Consistent threshold semantics (≥2.5 is hard cutoff)

Performance: <15ms per profile, safe against malicious input
"""

import re
from typing import Tuple

# ═══════════════════════════════════════════════════════════════════════════════
# PRE-COMPILED SIGNAL PATTERNS (module-level, one-time cost)
# ═══════════════════════════════════════════════════════════════════════════════

# Pronouns (3 pts) — highest confidence
PRONOUNS_PATTERN = re.compile(
    r'\b(she|her|they|them)\b',  # Whole-word matching only
    re.IGNORECASE
)
PRONOUNS_WEIGHT = 3.0

# Gender nouns (2 pts) — strong indicators
GENDER_NOUNS_PATTERN = re.compile(
    r'\b(woman|women|girl|lady|female|sis|sister|naine|nainen|tüdruk|женщина|девушка)\b',
    re.IGNORECASE
)
GENDER_NOUNS_WEIGHT = 2.0

# Relationship terms (1.5 pts) — moderate indicators
RELATIONSHIPS_PATTERN = re.compile(
    r'\b(mum|mom|mama|daughter|sister|wife|nana|auntie|grandma|niece|ema|мама|сестра|дочь|жена)\b',
    re.IGNORECASE
)
RELATIONSHIPS_WEIGHT = 1.5

# Generic/low-value (0.5 pts) — weak indicators
GENERIC_PATTERN = re.compile(
    r'\b(blogger|babe|queen|boss|fashionista)\b',
    re.IGNORECASE
)
GENERIC_WEIGHT = 0.5

# Threshold for flagging as female
FEMALE_THRESHOLD = 2.5

# Input validation
MAX_BIO_LENGTH = 500  # Truncate to prevent ReDoS

# ═══════════════════════════════════════════════════════════════════════════════
# FEMALE SIGNAL SCORING — OPTIMIZED WITH EARLY-EXIT
# ═══════════════════════════════════════════════════════════════════════════════

def score_female_signals(username: str, full_name: str, bio: str, threshold: float = FEMALE_THRESHOLD) -> Tuple[float, dict]:
    """
    Score female signals across username, full_name, and bio using pre-compiled patterns.
    Returns (total_score, breakdown).
    
    EARLY-EXIT: Returns immediately upon reaching threshold (optimization).
    All languages in one pool (English + Estonian + Russian).
    Score ≥2.5 = flag as female.
    """
    # Input validation: null/empty/length checks
    username = (username or '').lower() if username else ''
    full_name = (full_name or '').lower() if full_name else ''
    bio = (bio or '').lower()[:MAX_BIO_LENGTH] if bio else ''
    
    combined = f"{username} {full_name} {bio}".strip()
    if not combined:
        return 0.0, {}
    
    breakdown = {
        'pronouns': 0.0,
        'gender_nouns': 0.0,
        'relationships': 0.0,
        'generic': 0.0,
    }
    
    # Pronouns first (highest value, early-exit opportunity)
    pronouns_matches = len(PRONOUNS_PATTERN.findall(combined))
    breakdown['pronouns'] = pronouns_matches * PRONOUNS_WEIGHT
    
    # EARLY-EXIT: Single pronoun = 3pts already exceeds 2.5 threshold
    if breakdown['pronouns'] >= threshold:
        return breakdown['pronouns'], breakdown
    
    # Gender nouns (strong signal)
    gender_noun_matches = len(GENDER_NOUNS_PATTERN.findall(combined))
    breakdown['gender_nouns'] = gender_noun_matches * GENDER_NOUNS_WEIGHT
    
    # EARLY-EXIT: Check cumulative score
    cumulative = breakdown['pronouns'] + breakdown['gender_nouns']
    if cumulative >= threshold:
        return cumulative, breakdown
    
    # Relationships (moderate signal)
    relationship_matches = len(RELATIONSHIPS_PATTERN.findall(combined))
    breakdown['relationships'] = relationship_matches * RELATIONSHIPS_WEIGHT
    
    # EARLY-EXIT: Check cumulative score again
    cumulative = sum([breakdown['pronouns'], breakdown['gender_nouns'], breakdown['relationships']])
    if cumulative >= threshold:
        return cumulative, breakdown
    
    # Generic signals (weak, but count all for completeness)
    generic_matches = len(GENERIC_PATTERN.findall(combined))
    breakdown['generic'] = generic_matches * GENERIC_WEIGHT
    
    total_score = sum(breakdown.values())
    
    return total_score, breakdown


# ═══════════════════════════════════════════════════════════════════════════════
# FEMALE FLAG DECISION
# ═══════════════════════════════════════════════════════════════════════════════

def is_female_account(username: str, full_name: str, bio: str, threshold: float = FEMALE_THRESHOLD) -> Tuple[bool, float, dict]:
    """
    Determine if account is likely female based on signal scoring.
    
    Args:
        username: Instagram username
        full_name: Full name from profile
        bio: Biography text
        threshold: Minimum score to flag as female (default: 2.5 — hard cutoff)
    
    Returns:
        (is_female, score, breakdown)
    
    Semantics: ≥threshold is FEMALE, <threshold is NOT FEMALE (no probabilistic interpretation).
    """
    # Input validation
    username = username or ''
    full_name = full_name or ''
    bio = bio or ''
    
    if not (username or bio):
        return False, 0.0, {}
    
    score, breakdown = score_female_signals(username, full_name, bio, threshold)
    is_female = score >= threshold
    
    return is_female, score, breakdown


# ═══════════════════════════════════════════════════════════════════════════════
# INTEGRATION: Filter pipeline entry point
# ═══════════════════════════════════════════════════════════════════════════════

def passes_female_filter(username: str, full_name: str, bio: str, is_business: bool = False) -> Tuple[bool, dict]:
    """
    Combined female detection with business filter integration.
    
    Returns:
        (passes_filter, detection_details)
    
    Logic:
      - If business=true, skip female scoring entirely (return False)
      - Otherwise, run female signal detection (threshold ≥2.5 = hard cutoff)
    
    Input validation: safe against null/empty/malicious input.
    """
    # Input validation
    username = username or ''
    full_name = full_name or ''
    bio = bio or ''
    
    # Short-circuit: if business account, reject (don't score female)
    if is_business:
        return False, {
            'method': 'business_filter',
            'is_female': False,
            'reason': 'Business account — skipped female scoring'
        }
    
    # Run female signal detection with early-exit optimization
    is_female, score, breakdown = is_female_account(username, full_name, bio, threshold=FEMALE_THRESHOLD)
    
    return is_female, {
        'method': 'weighted_female_scoring',
        'is_female': is_female,
        'score': score,
        'breakdown': breakdown,
        'threshold': FEMALE_THRESHOLD,
    }
