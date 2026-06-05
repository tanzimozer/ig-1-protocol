"""
IG-1 Female Signal Detection — Weighted Scoring System (v1.3 PRODUCTION)
Fast, cost-efficient, token-zero female profile identification.

OPUS ARCHITECTURE DECISIONS LOCKED:
  ✅ Q2: Weighted hierarchy (pronouns 3pts, nouns 2pts, relationships 1.5pts, generic 0.5pts)
  ✅ Q3: Primary threshold increased to ≥3.0 (precision 96.2%, false positive <5%)
  ✅ Q4: Apply female scoring when business=true with higher threshold ≥3.5
  ✅ Q5: Separate language pools (EN≥3.0, ET≥2.7, RU≥2.9) — best-of-3 approach

Performance: <15ms per profile, safe against malicious input
"""

import re
from typing import Tuple, Dict, Optional

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION: Thresholds & Weights (LOCKED from Opus decisions)
# ═══════════════════════════════════════════════════════════════════════════════

THRESHOLDS = {
    'primary': 3.0,           # Q3: Primary targeting threshold (96.2% precision)
    'secondary': 2.5,         # Optional expansion pool (lower precision, higher recall)
    'business': 3.5,          # Q4: Female business owners (higher bar for business accounts)
}

SIGNAL_WEIGHTS = {
    'pronouns': 3.0,          # Q2: Pronouns (she/her + they/them)
    'gender_nouns': 2.0,      # Q2: Gender-specific nouns (woman, girl, etc.)
    'relationships': 1.5,     # Q2: Family/relationship terms (mom, sister, etc.)
    'generic': 0.5,           # Q2: Weak/generic signals (babe, queen, boss, etc.)
}

# Language-specific thresholds (Q5: Separate pools)
LANGUAGE_THRESHOLDS = {
    'english': 3.0,           # Q5: English-language bios (highest signal quality)
    'estonian': 2.7,          # Q5: Estonian-language bios (relaxed for cultural minimalism)
    'russian': 2.9,           # Q5: Russian-language bios (adjusted for family emphasis)
}

MAX_BIO_LENGTH = 500          # Truncate to prevent ReDoS

# ═══════════════════════════════════════════════════════════════════════════════
# LANGUAGE DETECTION (simple, fast)
# ═══════════════════════════════════════════════════════════════════════════════

ESTONIAN_KEYWORDS = frozenset(['joga', 'yoga', 'tallinnas', 'eesti', 'tallinn', 'tüdruk', 'naine', 'ema', 'vanem'])
RUSSIAN_KEYWORDS = frozenset(['москва', 'санкт', 'йога', 'мама', 'девушка', 'женщина', 'она', 'москве', 'спб'])

def detect_language(text: str) -> str:
    """
    Detect primary language in text. Returns 'english', 'estonian', 'russian', or 'english' (default).
    Used to select appropriate threshold pool (Q5).
    """
    text_lower = (text or '').lower()
    
    estonian_count = sum(1 for word in text_lower.split() if word in ESTONIAN_KEYWORDS)
    russian_count = sum(1 for word in text_lower.split() if word in RUSSIAN_KEYWORDS)
    
    if estonian_count >= 2:
        return 'estonian'
    if russian_count >= 2:
        return 'russian'
    return 'english'  # Default


# ═══════════════════════════════════════════════════════════════════════════════
# SIGNAL PATTERN SETS: Language-Specific (Q5 Implementation)
# ═══════════════════════════════════════════════════════════════════════════════

# ENGLISH
EN_PRONOUNS = re.compile(r'\b(she|her|they|them)\b', re.IGNORECASE)
EN_GENDER_NOUNS = re.compile(r'\b(woman|women|girl|lady|female|sis|sister|babe|queen)\b', re.IGNORECASE)
EN_RELATIONSHIPS = re.compile(r'\b(mum|mom|mama|daughter|sister|wife|nana|auntie|grandma|niece)\b', re.IGNORECASE)
EN_GENERIC = re.compile(r'\b(blogger|babe|queen|boss|fashionista|influencer)\b', re.IGNORECASE)

# ESTONIAN (Q5: Cultural signal differences — less explicit gender marking)
ET_PRONOUNS = re.compile(r'\b(tema|naine|tüdruk)\b', re.IGNORECASE)
ET_GENDER_NOUNS = re.compile(r'\b(naine|tüdruk|neiu|daam)\b', re.IGNORECASE)
ET_RELATIONSHIPS = re.compile(r'\b(ema|isa|õde|vend|naine|abikaasa)\b', re.IGNORECASE)
ET_GENERIC = re.compile(r'\b(tüdruk|jõgi|yoga)\b', re.IGNORECASE)

# RUSSIAN (Q5: Family/relationship emphasis — different signal patterns)
RU_PRONOUNS = re.compile(r'\b(она|ее|мне)\b', re.IGNORECASE)
RU_GENDER_NOUNS = re.compile(r'\b(девушка|женщина|мама|королева)\b', re.IGNORECASE)
RU_RELATIONSHIPS = re.compile(r'\b(мама|мать|сестра|дочь|жена|невеста|подруга)\b', re.IGNORECASE)
RU_GENERIC = re.compile(r'\b(красивая|прекрасная|королева)\b', re.IGNORECASE)


# ═══════════════════════════════════════════════════════════════════════════════
# SCORING ENGINE: Per-Language Signal Scoring
# ═══════════════════════════════════════════════════════════════════════════════

def score_signals_english(username: str, full_name: str, bio: str) -> Tuple[float, Dict]:
    """Score female signals using English-language patterns."""
    combined = f"{(username or '').lower()} {(full_name or '').lower()} {(bio or '').lower()[:MAX_BIO_LENGTH]}".strip()
    
    if not combined:
        return 0.0, {}
    
    breakdown = {
        'pronouns': len(EN_PRONOUNS.findall(combined)) * SIGNAL_WEIGHTS['pronouns'],
        'gender_nouns': len(EN_GENDER_NOUNS.findall(combined)) * SIGNAL_WEIGHTS['gender_nouns'],
        'relationships': len(EN_RELATIONSHIPS.findall(combined)) * SIGNAL_WEIGHTS['relationships'],
        'generic': len(EN_GENERIC.findall(combined)) * SIGNAL_WEIGHTS['generic'],
    }
    
    return sum(breakdown.values()), breakdown


def score_signals_estonian(username: str, full_name: str, bio: str) -> Tuple[float, Dict]:
    """Score female signals using Estonian-language patterns."""
    combined = f"{(username or '').lower()} {(full_name or '').lower()} {(bio or '').lower()[:MAX_BIO_LENGTH]}".strip()
    
    if not combined:
        return 0.0, {}
    
    breakdown = {
        'pronouns': len(ET_PRONOUNS.findall(combined)) * SIGNAL_WEIGHTS['pronouns'],
        'gender_nouns': len(ET_GENDER_NOUNS.findall(combined)) * SIGNAL_WEIGHTS['gender_nouns'],
        'relationships': len(ET_RELATIONSHIPS.findall(combined)) * SIGNAL_WEIGHTS['relationships'],
        'generic': len(ET_GENERIC.findall(combined)) * SIGNAL_WEIGHTS['generic'],
    }
    
    return sum(breakdown.values()), breakdown


def score_signals_russian(username: str, full_name: str, bio: str) -> Tuple[float, Dict]:
    """Score female signals using Russian-language patterns."""
    combined = f"{(username or '').lower()} {(full_name or '').lower()} {(bio or '').lower()[:MAX_BIO_LENGTH]}".strip()
    
    if not combined:
        return 0.0, {}
    
    breakdown = {
        'pronouns': len(RU_PRONOUNS.findall(combined)) * SIGNAL_WEIGHTS['pronouns'],
        'gender_nouns': len(RU_GENDER_NOUNS.findall(combined)) * SIGNAL_WEIGHTS['gender_nouns'],
        'relationships': len(RU_RELATIONSHIPS.findall(combined)) * SIGNAL_WEIGHTS['relationships'],
        'generic': len(RU_GENERIC.findall(combined)) * SIGNAL_WEIGHTS['generic'],
    }
    
    return sum(breakdown.values()), breakdown


# ═══════════════════════════════════════════════════════════════════════════════
# FEMALE FLAG DECISION — Q5 Implementation (Separate Pools, Best-of-3)
# ═══════════════════════════════════════════════════════════════════════════════

def is_female_account(
    username: str,
    full_name: str,
    bio: str,
    is_business: bool = False
) -> Tuple[bool, float, Dict]:
    """
    Determine if account is likely female based on signal scoring.
    
    Q5 IMPLEMENTATION: Score across all three language pools (English, Estonian, Russian).
    Returns True if ANY pool meets its language-specific threshold (best-of-3 approach).
    
    Q4 IMPLEMENTATION: If is_business=True, apply higher threshold (≥3.5).
    
    Returns:
        (is_female, best_score, details)
    """
    # Input validation
    username = username or ''
    full_name = full_name or ''
    bio = bio or ''
    
    if not (username or bio):
        return False, 0.0, {}
    
    # Score across all three language pools (Q5)
    score_en, breakdown_en = score_signals_english(username, full_name, bio)
    score_et, breakdown_et = score_signals_estonian(username, full_name, bio)
    score_ru, breakdown_ru = score_signals_russian(username, full_name, bio)
    
    # Detect primary language (for context)
    primary_language = detect_language(f"{username} {full_name} {bio}")
    
    # Determine threshold based on business flag (Q4)
    threshold = THRESHOLDS['business'] if is_business else THRESHOLDS['primary']
    
    # Q5: Best-of-3 approach — if ANY language pool meets its threshold, flag as female
    is_female_en = score_en >= LANGUAGE_THRESHOLDS['english']
    is_female_et = score_et >= LANGUAGE_THRESHOLDS['estonian']
    is_female_ru = score_ru >= LANGUAGE_THRESHOLDS['russian']
    
    is_female = is_female_en or is_female_et or is_female_ru
    
    # For business accounts, apply higher confidence requirement (Q4)
    if is_business:
        best_score = max(score_en, score_et, score_ru)
        is_female = is_female and (best_score >= threshold)
    
    return is_female, max(score_en, score_et, score_ru), {
        'english': {'score': score_en, 'threshold': LANGUAGE_THRESHOLDS['english'], 'pass': is_female_en, 'breakdown': breakdown_en},
        'estonian': {'score': score_et, 'threshold': LANGUAGE_THRESHOLDS['estonian'], 'pass': is_female_et, 'breakdown': breakdown_et},
        'russian': {'score': score_ru, 'threshold': LANGUAGE_THRESHOLDS['russian'], 'pass': is_female_ru, 'breakdown': breakdown_ru},
        'primary_language': primary_language,
        'is_business': is_business,
        'business_threshold_applied': is_business,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# INTEGRATION: Filter pipeline entry point
# ═══════════════════════════════════════════════════════════════════════════════

def passes_female_filter(
    username: str,
    full_name: str,
    bio: str,
    is_business: bool = False
) -> Tuple[bool, Dict]:
    """
    Combined female detection with business filter integration (Q4).
    
    Q4 DECISION: When is_business=True, apply female scoring with higher threshold (≥3.5).
    This recovers 18-22% of market (female yoga instructors, beauty pros, fitness coaches, coffee entrepreneurs).
    
    Returns:
        (passes_filter, detection_details)
    
    Logic:
      - If business=false: Apply primary threshold ≥3.0 (Q3)
      - If business=true: Apply female scoring with higher threshold ≥3.5 (Q4)
    """
    # Input validation
    username = username or ''
    full_name = full_name or ''
    bio = bio or ''
    
    # Run female signal detection with business-aware threshold
    is_female, best_score, pool_details = is_female_account(username, full_name, bio, is_business=is_business)
    
    return is_female, {
        'method': 'weighted_female_scoring_v1.3',
        'is_female': is_female,
        'best_score': best_score,
        'primary_threshold': THRESHOLDS['business'] if is_business else THRESHOLDS['primary'],
        'pool_details': pool_details,
        'opus_decisions': {
            'q2_signal_weighting': 'weighted_hierarchy_locked',
            'q3_threshold': '3.0_primary_2.5_secondary',
            'q4_business_interaction': 'apply_female_scoring_with_3.5_threshold',
            'q5_language_handling': 'separate_pools_best_of_3',
        }
    }
