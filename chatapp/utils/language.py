import logging
from .translator import translate_text, normalize_to_professional_english, ensure_us_english
from .tamil_detector import contains_tamil_script, contains_tanglish

logger = logging.getLogger(__name__)

# Mapping of language codes to display names
# Supports BOTH short codes (ta, hi) AND full names (tamil, hindi)
SUPPORTED_LANGUAGES = {
    "ta": "Tamil",
    "tamil": "Tamil",
    "hi": "Hindi",
    "hindi": "Hindi",
    "te": "Telugu",
    "telugu": "Telugu",
    "ml": "Malayalam",
    "malayalam": "Malayalam",
    "kn": "Kannada",
    "kannada": "Kannada",
    "bn": "Bengali",
    "bengali": "Bengali",
    "gu": "Gujarati",
    "gujarati": "Gujarati",
    "mr": "Marathi",
    "marathi": "Marathi",
    "pa": "Punjabi",
    "punjabi": "Punjabi",
    "ur": "Urdu",
    "urdu": "Urdu",
    "en": "English",
    "english": "English"
}

def process_message_content(content, sender_language_mode):
    """
    MULTILINGUAL WORKFLOW - CRITICAL FUNCTION:
    
    1. Input: User sends message in ANY language (Tamil, Hindi, English, Tanglish, etc.)
    2. Process: Convert to normalized Professional English (canonical form)
    3. Store: Save ONLY the English version in database
    4. Retrieval: Translate English → each user's language mode on-the-fly
    
    🔴 CRITICAL: Must ALWAYS produce canonical English, regardless of input language
    
    Args:
        content: Raw message from user
        sender_language_mode: User's selected input language (e.g., 'tamil', 'hindi', etc.)
    
    Returns:
        (english_version, display_version, validation_msg, should_warn, tamil_version)
        - english_version: Canonical Professional English (stored in DB)
        - display_version: Already in sender's language (for immediate feedback)
        - tamil_version: Backward compatibility field
    """
    sender_lang_name = SUPPORTED_LANGUAGES.get(sender_language_mode, "English")
    
    # STEP 1: Normalize any input to Professional English (internal storage)
    # 🔴 CRITICAL: This MUST produce English, NOT original language text
    try:
        # Normalize based on sender's selected language mode
        if sender_language_mode.lower() in ['tamil', 'ta']:
            # Tamil mode - use Tamil detection and normalization
            if contains_tamil_script(content) or contains_tanglish(content):
                norm_success, english_version, _ = normalize_to_professional_english(content, 'Tamil')
                english_version = english_version if norm_success else content
            else:
                # English input in Tamil mode - just ensure it's professional
                english_version = content
        
        elif sender_language_mode.lower() in ['english', 'en']:
            # English mode - normalize English text
            english_version = content
        
        else:
            # ALL OTHER LANGUAGES (Hindi, Telugu, Malayalam, etc.)
            # Must translate FROM the sender's selected language TO English
            # The key insight: sender_language_mode tells us the SOURCE language!
            lang_map_reverse = {
                'hindi': 'Hindi',
                'telugu': 'Telugu', 
                'malayalam': 'Malayalam',
                'kannada': 'Kannada',
                'bengali': 'Bengali',
                'gujarati': 'Gujarati',
                'marathi': 'Marathi',
                'punjabi': 'Punjabi',
                'urdu': 'Urdu',
            }
            
            if sender_language_mode.lower() in lang_map_reverse:
                # Translate from source language to English
                # We MUST translate, even if it "looks like English" to contains_tamil_script()
                logger.info(f"Translating from {sender_language_mode} to English")
                success, english_version, _ = translate_text(content, 'English', source_language=lang_map_reverse[sender_language_mode.lower()])
                english_version = english_version if success and english_version else content
            else:
                # Fallback for unknown languages
                english_version = content
    
    except Exception as e:
        logger.error(f"Normalization failed for '{content[:50]}': {e}")
        english_version = content

    # Verify we have canonical English (not original language text)
    english_version = ensure_us_english(english_version)
    
    if english_version == content and sender_language_mode.lower() not in ['english', 'en']:
        logger.warning(f"[WARNING] English version still equals original input for {sender_language_mode} mode. May not have translated correctly.")

    # STEP 2: Generate Display Version (for immediate sender feedback - shows their language)
    # This is what the sender sees immediately
    display_version = content  # Show original content to sender
    validation_msg = None
    should_warn = False

    # STEP 3: Generate Tamil Version (backward compatibility)
    try:
        t_success, tamil_version, _ = translate_text(english_version, 'Tamil')
        tamil_version = tamil_version if t_success else english_version
    except:
        tamil_version = english_version

    logger.info(f"Message processed: {sender_language_mode} -> Canonical English | Len:{len(english_version)}")
    logger.info(f"  Input: {content[:50]}...")
    logger.info(f"  Canonical: {english_version[:50]}...")
    
    return english_version, display_version, validation_msg, should_warn, tamil_version


def translate_message_for_user(english_message, target_language_mode):
    """
    CRITICAL FUNCTION: Translate a canonical English message to user's language.
    Called during message retrieval (group view, get-messages endpoint).
    
    CRITICAL: This MUST return the translated version for each user, NOT the original message
    
    Args:
        english_message: Canonical Professional English message from DB
        target_language_mode: User's selected language (e.g., 'tamil', 'hindi', etc.)
    
    Returns:
        str: Message translated to user's language (or English if translation fails)
    """
    if not english_message:
        return english_message
    
    # Normalize to lowercase for comparison
    target_mode_lower = target_language_mode.lower().strip() if target_language_mode else 'english'
    
    if target_mode_lower in ['english', 'en']:
        return english_message
    
    # Language mapping - supports both full names and short codes
    lang_map = {
        'tamil': 'Tamil',
        'ta': 'Tamil',
        'hindi': 'Hindi',
        'hi': 'Hindi',
        'telugu': 'Telugu',
        'te': 'Telugu',
        'malayalam': 'Malayalam',
        'ml': 'Malayalam',
        'kannada': 'Kannada',
        'kn': 'Kannada',
        'bengali': 'Bengali',
        'bn': 'Bengali',
        'gujarati': 'Gujarati',
        'gu': 'Gujarati',
        'marathi': 'Marathi',
        'mr': 'Marathi',
        'punjabi': 'Punjabi',
        'pa': 'Punjabi',
        'urdu': 'Urdu',
        'ur': 'Urdu',
    }
    
    # Get target language name
    target_lang_name = lang_map.get(target_mode_lower, 'English')

    # Debug logging to trace message display translation
    logger.info(f"Selected Language: {target_language_mode}")
    logger.info(f"English Stored: {english_message}")
    logger.info(f"Target Language Name: {target_lang_name}")

    # CRITICAL: Always translate from canonical English to target language.
    # Replaced hardcoded 'English' with 'auto' to allow AI to handle mixed language detection.
    try:
        success, translated_text, msg = translate_text(english_message, target_lang_name, source_language='auto')
        if success and translated_text:
            logger.info(f"Final Display: {translated_text[:100]}")  # Limit length for logging
            logger.info(f"[OK] Translated to {target_lang_name}: {english_message[:40]}... -> {translated_text[:40]}...")
            return translated_text
        else:
            logger.warning(f"[FAIL] Translation to {target_lang_name} failed: {msg}")
            return english_message
    except Exception as e:
        logger.error(f"[ERROR] Translation exception to {target_lang_name}: {e}", exc_info=True)
        return english_message