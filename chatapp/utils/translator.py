"""
Production-grade translation utility for the chat app.

This module centralizes translation, normalization, and language detection
for the supported chat languages. It supports:
- universal Indic script detection for Tamil, Hindi, Telugu, Malayalam,
  Kannada, Bengali, Gujarati, Marathi, Punjabi, Urdu
- Tanglish detection and normalization support
- English normalization and US English standardization
- explicit Gemini source/target translation guidance
- safe fallbacks and logging for production use
"""

import os
import re
import logging
import warnings
import traceback
from typing import Optional, Tuple

# Use google.generativeai for current compatibility.
warnings.filterwarnings('ignore', category=FutureWarning, module='google.generativeai')
import google.generativeai as genai

# Django imports for caching
from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger(__name__)

# =========================
# CONFIGURATION
# =========================

DEFAULT_SUPPORTED_LANGUAGES = [
    "English",
    "Tamil",
    "Hindi",
    "Telugu",
    "Malayalam",
    "Kannada",
    "Bengali",
    "Gujarati",
    "Marathi",
    "Punjabi",
    "Urdu",
]

LANGUAGE_ALIASES = {
    'en': 'English',
    'english': 'English',
    'ta': 'Tamil',
    'tamil': 'Tamil',
    'hi': 'Hindi',
    'hindi': 'Hindi',
    'te': 'Telugu',
    'telugu': 'Telugu',
    'ml': 'Malayalam',
    'malayalam': 'Malayalam',
    'kn': 'Kannada',
    'kannada': 'Kannada',
    'bn': 'Bengali',
    'bengali': 'Bengali',
    'gu': 'Gujarati',
    'gujarati': 'Gujarati',
    'mr': 'Marathi',
    'marathi': 'Marathi',
    'pa': 'Punjabi',
    'punjabi': 'Punjabi',
    'ur': 'Urdu',
    'urdu': 'Urdu',
}

# ISO code mapping for supported languages - Required for proper validation and API guidance
LANGUAGE_CODES = {
    'English': 'en',
    'Tamil': 'ta',
    'Hindi': 'hi',
    'Malayalam': 'ml',
    'Telugu': 'te',
    'Kannada': 'kn',
    'Bengali': 'bn',
    'Gujarati': 'gu',
    'Marathi': 'mr',
    'Punjabi': 'pa',
    'Urdu': 'ur'
}

RAW_SUPPORTED_LANGUAGES = os.getenv(
    'SUPPORTED_LANGUAGES',
    ','.join(DEFAULT_SUPPORTED_LANGUAGES)
)
SUPPORTED_LANGUAGES = []
for entry in RAW_SUPPORTED_LANGUAGES.split(','):
    normalized = entry.strip()
    if not normalized:
        continue
    normalized = LANGUAGE_ALIASES.get(normalized.lower(), normalized.title())
    if normalized not in SUPPORTED_LANGUAGES:
        SUPPORTED_LANGUAGES.append(normalized)

SUPPORTED_LANGUAGE_SET = {lang.lower() for lang in SUPPORTED_LANGUAGES}
API_KEY = os.getenv('GEMINI_API_KEY')
DEFAULT_LANGUAGE = os.getenv('DEFAULT_LANGUAGE', 'English').strip()
MODEL_NAME = os.getenv('TRANSLATOR_MODEL', 'gemini-2.5-flash').strip()

LANGUAGE_SCRIPT_PATTERNS = {
    'Tamil': re.compile(r'[\u0B80-\u0BFF]'),
    'Telugu': re.compile(r'[\u0C00-\u0C7F]'),
    'Kannada': re.compile(r'[\u0C80-\u0CFF]'),
    'Malayalam': re.compile(r'[\u0D00-\u0D7F]'),
    'Bengali': re.compile(r'[\u0980-\u09FF]'),
    'Gujarati': re.compile(r'[\u0A80-\u0AFF]'),
    'Devanagari': re.compile(r'[\u0900-\u097F]'),
    'Arabic': re.compile(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]'),
}

DEVANAGARI_KEYWORDS = {
    'Marathi': [
        'आहे', 'मला', 'तू', 'तो', 'ती', 'आम्ही', 'तुम्ही', 'हा', 'काय',
        'किती', 'होय', 'नाही', 'माझं', 'माझी', 'मला', 'हे', 'आहेत', 'लागेल',
    ],
    'Hindi': [
        'है', 'हूँ', 'हुआ', 'हुई', 'मैं', 'तुम', 'वह', 'यह', 'क्या',
        'कहाँ', 'क्यों', 'क्योंकि', 'नहीं', 'हाँ', 'होता', 'रहा', 'रही',
        'रहे', 'दोस्त', 'आज', 'कल', 'मैंने', 'तुम्हें', 'तुम्हारा',
    ],
}

TANGLISH_PATTERNS = [
    r'\bvanakkam\b', r'\bnamaskar\b', r'\bnamaste\b', r'\bayyo\b',
    r'\baiyyo\b', r'\bdei\b', r'\bmachi\b', r'\bmachan\b',
    r'\bsolra\b', r'\bsolla\b', r'\bthamil\b', r'\bthamizh\b',
    r'\btamizh\b', r'\bpadikalam\b', r'\bpesi\b', r'\bsandhosham\b',
    r'\bvaalkai\b', r'\bvalkai\b', r'\benna\b', r'\bappa\b',
    r'\bappa\b', r'\bpa\b', r'\bka\b', r'\bvecha\b',
]

BRITISH_TO_US_ENGLISH = {
    'colour': 'color', 'favour': 'favor', 'honour': 'honor', 'labour': 'labor',
    'harbour': 'harbor', 'centre': 'center', 'metre': 'meter', 'theatre': 'theater',
    'travelling': 'traveling', 'realise': 'realize', 'organise': 'organize',
    'recognise': 'recognize', 'apologise': 'apologize', 'analyse': 'analyze',
    'licence': 'license', 'defence': 'defense', 'offence': 'offense',
    'grey': 'gray', 'cheque': 'check', 'gaol': 'jail', 'kerb': 'curb',
    'programme': 'program',
}

logger.info('TRANSLATOR_INIT supported_languages=%s model=%s', SUPPORTED_LANGUAGES, MODEL_NAME)
if API_KEY:
    try:
        genai.configure(api_key=API_KEY)
        logger.info('TRANSLATOR_INIT Gemini API configured successfully')
    except Exception as exc:
        logger.error('TRANSLATOR_INIT Gemini configuration failed: %s', exc)
else:
    logger.warning('TRANSLATOR_INIT GEMINI_API_KEY not configured')


# =========================
# UTILITY HELPERS
# =========================

def clean_text(text: Optional[str]) -> str:
    return text.strip() if isinstance(text, str) else ''


def normalize_language_name(language: Optional[str]) -> str:
    if not language or not isinstance(language, str):
        return 'English'
    # Clean and check against aliases first (supports 'hi' -> 'Hindi', etc.)
    key = clean_text(language).lower()
    return LANGUAGE_ALIASES.get(key, key.title())


def is_supported_language(language: Optional[str]) -> bool:
    return normalize_language_name(language).lower() in SUPPORTED_LANGUAGE_SET


def ensure_us_english(text: str) -> str:
    text = clean_text(text)
    if not text:
        return text
    result = text
    for british, american in BRITISH_TO_US_ENGLISH.items():
        result = re.sub(rf'\b{re.escape(british)}\b', american, result, flags=re.IGNORECASE)
    return result


def contains_script(text: str, language: str) -> bool:
    language = normalize_language_name(language)
    if language in LANGUAGE_SCRIPT_PATTERNS:
        return bool(LANGUAGE_SCRIPT_PATTERNS[language].search(text))
    if language in {'Hindi', 'Marathi'}:
        return bool(LANGUAGE_SCRIPT_PATTERNS['Devanagari'].search(text))
    if language == 'Urdu':
        return bool(LANGUAGE_SCRIPT_PATTERNS['Arabic'].search(text))
    return False


def contains_any_indic_script(text: str) -> bool:
    return any(pattern.search(text) for pattern in LANGUAGE_SCRIPT_PATTERNS.values())


def is_tanglish(text: str) -> bool:
    text = clean_text(text).lower()
    if not text or contains_any_indic_script(text):
        return False
    score = sum(len(re.findall(pattern, text)) for pattern in TANGLISH_PATTERNS)
    return score >= 2


def detect_language(text: str) -> str:
    text = clean_text(text)
    if not text:
        return 'English'
    if contains_script(text, 'Tamil'):
        return 'Tamil'
    if contains_script(text, 'Malayalam'):
        return 'Malayalam'
    if contains_script(text, 'Kannada'):
        return 'Kannada'
    if contains_script(text, 'Telugu'):
        return 'Telugu'
    if contains_script(text, 'Bengali'):
        return 'Bengali'
    if contains_script(text, 'Gujarati'):
        return 'Gujarati'
    if contains_script(text, 'Urdu'):
        return 'Urdu'
    if contains_script(text, 'Hindi'):
        lower_text = text.lower()
        for language, keywords in DEVANAGARI_KEYWORDS.items():
            if any(re.search(rf'\b{re.escape(word)}\b', lower_text) for word in keywords):
                return language
        return 'Hindi'
    if is_tanglish(text):
        return 'Tanglish'
    return 'English'


def validate_language(language: Optional[str]) -> bool:
    if not language or not isinstance(language, str):
        return False
    # Expanded validation to use internal code mapping as well
    norm = normalize_language_name(language)
    if norm in LANGUAGE_CODES:
        return True
    return norm.lower() in SUPPORTED_LANGUAGE_SET


def _source_language_for_translation(source_language: Optional[str], text: str) -> Optional[str]:
    # Updated to handle 'auto' detection explicitly
    if source_language and source_language != 'auto':
        normalized = normalize_language_name(source_language)
        return 'Tamil' if normalized == 'Tanglish' else normalized
    detected = detect_language(text)
    return 'Tamil' if detected == 'Tanglish' else (detected if detected != 'English' else None)


def _is_already_in_target(text: str, source_language: Optional[str], target_language: str) -> bool:
    target = normalize_language_name(target_language)
    source = _source_language_for_translation(source_language, text)
    if not source or source != target:
        return False
    if target == 'English':
        return not contains_any_indic_script(text)
    if target in {'Hindi', 'Marathi'}:
        return contains_script(text, 'Hindi')
    return contains_script(text, target)


# =========================
# TRANSLATION
# =========================

def translate_text(
    text: str,
    target_language: str,
    source_language: Optional[str] = None,
) -> Tuple[bool, Optional[str], str]:
    text = clean_text(text)
    target_language = normalize_language_name(target_language)
    source_language = _source_language_for_translation(source_language, text)

    logger.info('TRANSLATE_START target=%s source=%s text=%s', target_language, source_language or 'auto', text[:120])

    if not text:
        return False, None, 'Empty text provided'

    if target_language not in LANGUAGE_CODES and not validate_language(target_language):
        return False, None, f'Unsupported language: {target_language}'

    if source_language and source_language != 'auto' and source_language not in LANGUAGE_CODES and not validate_language(source_language):
        return False, None, f'Unsupported source language: {source_language}'

    if _is_already_in_target(text, source_language, target_language):
        msg = f'Already in {target_language}'
        logger.info('TRANSLATE_SKIP %s', msg)
        return True, text, msg

    # TRANSLATION CACHE: Check cache first
    cache_key = f'translation_{hash(text)}_{source_language or "auto"}_{target_language}'
    cached_result = cache.get(cache_key)
    if cached_result:
        logger.info('TRANSLATE_CACHE_HIT key=%s', cache_key)
        return cached_result

    if not API_KEY:
        logger.error('TRANSLATE_FAIL translation service not configured')
        return False, None, 'Translation service not configured'

    if source_language:
        prompt = (
            f'Translate the following text from {source_language} to {target_language}.\n'
            'Only return the translated text. Do not include explanations or extra text.\n\n'
            f'Text:\n{text}'
        )
    else:
        prompt = (
            f'Translate the following text to {target_language}.\n'
            'Only return the translated text. Do not include explanations or extra text.\n\n'
            f'Text:\n{text}'
        )

    logger.info('TRANSLATE_PROMPT source=%s target=%s', source_language or 'auto', target_language)

    try:
        model = genai.GenerativeModel(MODEL_NAME)
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(max_output_tokens=1000),
        )

        translated = None
        if hasattr(response, 'text') and response.text:
            translated = response.text.strip()
        elif hasattr(response, 'candidates') and response.candidates:
            candidate = response.candidates[0]
            translated = getattr(candidate, 'content', None)
            if translated and hasattr(translated, 'parts') and translated.parts:
                translated = translated.parts[0].text.strip()
            elif isinstance(translated, str):
                translated = translated.strip()

        if not translated:
            logger.warning('TRANSLATE_FAIL empty response from Gemini')
            # Safe fallback: return original text if translation returns empty
            return True, text, 'Empty translation from service - returning original'

        logger.info('TRANSLATE_SUCCESS target=%s length=%d', target_language, len(translated))
        
        # CACHE SUCCESSFUL TRANSLATION
        result = (True, translated, 'Translation successful')
        cache.set(cache_key, result, 3600)  # Cache for 1 hour
        return result

    except Exception as exc:
        logger.error('TRANSLATE_EXCEPTION %s', traceback.format_exc())
        message = str(exc)
        if 'api key' in message.lower():
            error_result = (False, None, 'API key configuration error')
        elif 'rate limit' in message.lower():
            error_result = (False, None, 'Rate limit exceeded. Please try again later.')
        elif 'network' in message.lower():
            error_result = (False, None, 'Network error. Please check your connection.')
        else:
            error_result = (False, None, f'Translation failed: {message[:200]}')
        
        # Safe fallback: Return original text as fallback on exception instead of crashing
        logger.warning(f'TRANSLATE_EXCEPTION using fallback - returning original text. Error: {message[:100]}')
        return True, text, f'Translation exception: {message[:100]} - returned original'


# =========================
# NORMALIZATION
# =========================

def normalize_english_text(text: str) -> Tuple[bool, str, str]:
    text = clean_text(text)
    if not text:
        return False, text, 'Invalid English text'

    replacements = {
        r'\bu\b': 'you',
        r'\br\b': 'are',
        r'\bpls\b': 'please',
        r'\bthx\b': 'thanks',
        r'\bgonna\b': 'going to',
        r'\bwanna\b': 'want to',
        r'\bcuz\b': 'because',
        r'\blol\b': '',
        r'\bhaha\b': '',
        r'\btho\b': 'though',
        r'\bya\b': 'you',
    }

    normalized = text
    for pattern, replacement in replacements.items():
        normalized = re.sub(pattern, replacement, normalized, flags=re.IGNORECASE)

    normalized = re.sub(r'\s+', ' ', normalized).strip()
    sentences = re.split(r'([.!?]\s*)', normalized)
    normalized = ''.join(part.capitalize() if i % 2 == 0 else part for i, part in enumerate(sentences))
    normalized = ensure_us_english(normalized)
    return True, normalized, 'Normalized English text'


def normalize_to_professional_english(
    text: str,
    source_language: Optional[str] = None,
) -> Tuple[bool, str, str]:
    text = clean_text(text)
    if not text:
        return False, text, 'Empty text provided'

    normalized_source = normalize_language_name(source_language) if source_language else None
    detected = detect_language(text)
    if normalized_source == 'Tanglish':
        normalized_source = 'Tamil'
    if normalized_source and normalized_source != 'English':
        detected = normalized_source

    logger.info('NORMALIZE_START source=%s detected=%s text=%s', normalized_source or 'auto', detected, text[:120])

    if detected == 'English':
        return normalize_english_text(text)

    source_for_translation = 'Tamil' if detected == 'Tanglish' else detected
    success, translated, message = translate_text(
        text,
        'English',
        source_language=source_for_translation,
    )
    if success and translated:
        normalized = ensure_us_english(translated)
        logger.info('NORMALIZE_SUCCESS source=%s', source_for_translation)
        return True, normalized, f'Normalized from {source_for_translation}'

    logger.warning('NORMALIZE_FAIL source=%s message=%s', source_for_translation, message)
    return False, text, message


def get_display_message(
    original_text: str,
    translated_text: Optional[str],
    target_language: str,
) -> str:
    if normalize_language_name(target_language) == 'English':
        return original_text
    return translated_text or original_text


def get_translation_cache_key(message_id: int, target_language: str) -> str:
    return f'msg_translation_{message_id}_{normalize_language_name(target_language).lower()}'


def synthesize_speech_with_gtts(
    text: str,
    language_code: str = 'en',
) -> Tuple[bool, Optional[bytes], str]:
    if not text or not isinstance(text, str):
        return False, None, 'Invalid text for TTS'

    try:
        from gtts import gTTS
        import io

        tts = gTTS(text=text, lang=language_code, slow=False)
        audio_buffer = io.BytesIO()
        tts.write_to_fp(audio_buffer)
        audio_buffer.seek(0)
        return True, audio_buffer.getvalue(), 'Speech synthesized successfully'
    except Exception as exc:
        logger.error('TTS error: %s', exc)
        return False, None, str(exc)


if __name__ == '__main__':
    debug_samples = [
        'நான் செய்கிறேன்',
        'मैं ठीक हूँ',
        'నేను బాగున్నాను',
        'ഞാൻ സുഖമാണ്',
        'ನಾನು ಚೆನ್ನಾಗಿದ್ದೇನೆ',
        'আমি ভালো আছি',
        'હું સારું છું',
        'मी ठीक आहे',
        'ਮੈਂ ਠੀਕ ਹਾਂ',
        'میں ٹھیک ہوں',
        'enna bro epdi iruka',
        'Hello, how are you?',
    ]
    for sample in debug_samples:
        detected = detect_language(sample)
        print(f'INPUT: {sample}')
        print(f'  detected: {detected}')
        success, normalized, msg = normalize_to_professional_english(sample)
        print(f'  normalized success={success} msg={msg} text={normalized}')
        print('')
