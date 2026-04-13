"""
Translation utility module for Google Gemini API integration.
Provides functions to translate messages between supported languages.
Handles Tamil/Tanglish normalization and message content formatting.
"""

import os
import logging
import warnings
import traceback
import re
from typing import Optional, Tuple

# Suppress deprecation warning for google.generativeai
# Migration to google.genai is planned for the future
warnings.filterwarnings('ignore', category=FutureWarning, module='google.generativeai')

import google.generativeai as genai

logger = logging.getLogger(__name__)

# Initialize Gemini API
API_KEY = os.getenv('GEMINI_API_KEY')
SUPPORTED_LANGUAGES = os.getenv('SUPPORTED_LANGUAGES', 'English,Tamil').split(',')
DEFAULT_LANGUAGE = os.getenv('DEFAULT_LANGUAGE', 'English').strip()

print("[TRANSLATOR_INIT] API_KEY loaded:", "YES (length: {})".format(len(API_KEY)) if API_KEY else "NO")
print("[TRANSLATOR_INIT] SUPPORTED_LANGUAGES:", SUPPORTED_LANGUAGES)
print("[TRANSLATOR_INIT] DEFAULT_LANGUAGE:", DEFAULT_LANGUAGE)

# Configure Gemini API
if API_KEY:
    try:
        genai.configure(api_key=API_KEY)
        print("[TRANSLATOR_INIT] OK Gemini API configured successfully")
    except Exception as e:
        print(f"[TRANSLATOR_INIT] FAILED Error configuring Gemini API: {e}")
        logger.error(f"Failed to configure Gemini API: {e}")
else:
    print("[TRANSLATOR_INIT] FAILED GEMINI_API_KEY not found in environment")
    logger.warning("GEMINI_API_KEY not configured. Translation features will be disabled.")

# Model configuration
MODEL_NAME = "gemini-2.5-flash"  # Updated: gemini-2.0-flash no longer available, using latest 2.5-flash
print(f"[TRANSLATOR_INIT] Using model: {MODEL_NAME}")



def validate_language(language: str) -> bool:
    """
    Validate if the language is supported.
    
    Args:
        language: Language name or code
        
    Returns:
        True if language is supported, False otherwise
    """
    if not language:
        print("[TRANSLATOR] validate_language: Empty language provided")
        return False
        
    language_normalized = language.strip().lower()
    is_valid = any(lang.strip().lower() == language_normalized for lang in SUPPORTED_LANGUAGES)
    print(f"[TRANSLATOR] validate_language ('{language}') = {is_valid}")
    return is_valid


def translate_text(text: str, target_language: str) -> Tuple[bool, Optional[str], str]:
    """
    Translate text using Google Gemini API.
    
    Args:
        text: Text to translate
        target_language: Target language for translation
        
    Returns:
        Tuple of (success: bool, translated_text: Optional[str], message: str)
        - success: Whether translation was successful
        - translated_text: The translated text if successful, None otherwise
        - message: Status message or error description
    """
    print(f"\n[TRANSLATE_START] Text: '{text[:50]}...' Target: '{target_language}'")
    
    # Validate inputs
    if not text or not isinstance(text, str):
        msg = "Invalid text provided"
        print(f"[TRANSLATE_FAIL] {msg}")
        return False, None, msg
    
    if not target_language or not isinstance(target_language, str):
        msg = "Invalid target language"
        print(f"[TRANSLATE_FAIL] {msg}")
        return False, None, msg
    
    text = text.strip()
    if len(text) == 0:
        msg = "Text cannot be empty"
        print(f"[TRANSLATE_FAIL] {msg}")
        return False, None, msg
    
    if len(text) > 5000:
        msg = "Text too long (max 5000 characters)"
        print(f"[TRANSLATE_FAIL] {msg}")
        return False, None, msg
    
    print(f"[TRANSLATE] OK Input validation passed. Text length: {len(text)} chars")
    
    # Validate language
    if not validate_language(target_language):
        supported = ", ".join(SUPPORTED_LANGUAGES)
        msg = f"Unsupported language. Supported: {supported}"
        print(f"[TRANSLATE_FAIL] {msg}")
        return False, None, msg
    
    print(f"[TRANSLATE] OK Language validation passed")
    
    # Check if text is already in target language (skip expensive API call if so)
    target_lang_normalized = target_language.strip().lower()
    
    # Import language detection function
    from .tamil_detector import contains_tamil_script
    
    # If English is target, check if input is already English
    if target_lang_normalized == 'english':
        if not contains_tamil_script(text):
            # Input doesn't contain Tamil script, likely already English
            msg = "No translation needed (already in English)"
            print(f"[TRANSLATE_SUCCESS] {msg}")
            return True, text, msg
        # Input contains Tamil, needs translation to English
    
    # If Tamil is target, check if input is already Tamil
    elif target_lang_normalized == 'tamil':
        if contains_tamil_script(text):
            # Input already contains Tamil script
            msg = "No translation needed (already in Tamil)"
            print(f"[TRANSLATE_SUCCESS] {msg}")
            return True, text, msg
        # Input is not Tamil, needs translation to Tamil
    
    if not API_KEY:
        msg = "Translation service not configured"
        print(f"[TRANSLATE_FAIL] {msg} - API_KEY is None")
        logger.error(msg)
        return False, None, msg
    
    print(f"[TRANSLATE] OK API_KEY present, proceeding with API call")
    
    try:
        # Build translation prompt
        prompt = f"""Translate the following text to {target_language}. 
Only provide the translated text, nothing else. Do not add explanations or quotes.

Text to translate: {text}"""
        
        print(f"[TRANSLATE_API] Building prompt for model '{MODEL_NAME}'")
        print(f"[TRANSLATE_API] Target language: {target_language}")
        print(f"[TRANSLATE_API] Calling genai.GenerativeModel()")
        
        # Call Gemini API (using deprecated google.generativeai for compatibility)
        model = genai.GenerativeModel(MODEL_NAME)
        print(f"[TRANSLATE_API] OK Model instance created")
        
        print(f"[TRANSLATE_API] Calling model.generate_content() with prompt")
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=1000,
            ),
        )
        print(f"[TRANSLATE_API] OK API call completed")
        
        # Debug response object
        print(f"[TRANSLATE_API] Response object type: {type(response)}")
        
        if response:
            print(f"[TRANSLATE_API] OK Response is not None")
            
            # Try multiple ways to get text from response
            translated = None
            if hasattr(response, 'text'):
                translated = response.text
                try:
                    print(f"[TRANSLATE_API] Got text via response.text: '{translated[:100] if translated else None}'")
                except UnicodeEncodeError:
                    print(f"[TRANSLATE_API] Got text via response.text (length: {len(translated)} chars)")
            elif hasattr(response, 'candidates') and response.candidates:
                content = response.candidates[0].content
                translated = content.parts[0].text if content.parts else None
                try:
                    print(f"[TRANSLATE_API] Got text via candidates: '{translated[:100] if translated else None}'")
                except UnicodeEncodeError:
                    print(f"[TRANSLATE_API] Got text via candidates (length: {len(translated)} chars)")
            else:
                print(f"[TRANSLATE_API] Could not extract text from response")
            
            if translated:
                translated = translated.strip()
                
                # Validate translation
                if not translated or len(translated) == 0:
                    msg = "Empty translation received"
                    print(f"[TRANSLATE_FAIL] {msg}")
                    return False, None, msg
                
                print(f"[TRANSLATE_SUCCESS] OK Translation successful")
                try:
                    print(f"[TRANSLATE_SUCCESS] Original ({len(text)} chars): '{text[:50]}'")
                    print(f"[TRANSLATE_SUCCESS] Translated ({len(translated)} chars): '{translated[:50]}'")
                except UnicodeEncodeError:
                    print(f"[TRANSLATE_SUCCESS] Original ({len(text)} chars), Translated ({len(translated)} chars)")
                logger.info(f"OK Translation successful: {target_language}")
                return True, translated, "Translation successful"
            else:
                msg = "Could not extract text from response"
                print(f"[TRANSLATE_FAIL] {msg}")
                return False, None, msg
        else:
            msg = "No response from translation service"
            print(f"[TRANSLATE_FAIL] {msg}")
            return False, None, msg
            
    except Exception as e:
        print(f"[TRANSLATE_EXCEPTION] Exception occurred during translation")
        print(f"[TRANSLATE_EXCEPTION] Exception type: {type(e).__name__}")
        print(f"[TRANSLATE_EXCEPTION] Exception message: {str(e)}")
        print(f"[TRANSLATE_EXCEPTION] Full traceback:")
        print(traceback.format_exc())
        
        error_msg = str(e)
        logger.error(f"Translation error: {error_msg}")
        
        # Provide helpful error messages
        if "API key" in error_msg:
            return False, None, "API key configuration error"
        elif "rate limit" in error_msg.lower():
            return False, None, "Rate limit exceeded. Please try again later."
        elif "network" in error_msg.lower():
            return False, None, "Network error. Please check your connection."
        else:
            return False, None, f"Translation failed: {error_msg[:100]}"


def get_display_message(original_text: str, translated_text: Optional[str], target_language: str) -> str:
    """
    Get the message to display based on original and translated content.
    
    Args:
        original_text: Original message content
        translated_text: Translated message content (if available)
        target_language: Target language
        
    Returns:
        The appropriate text to display
    """
    target_lang_normalized = target_language.strip().lower()
    
    # If already in English or no translation available
    if target_lang_normalized == 'english' or not translated_text:
        return original_text
    
    # Return translated text if available and different
    if translated_text and translated_text != original_text:
        return translated_text
    
    # Fallback to original
    return original_text


def get_translation_cache_key(message_id: int, target_language: str) -> str:
    """
    Generate a cache key for translated message.
    Can be used for Redis caching if needed in the future.
    
    Args:
        message_id: Message ID
        target_language: Target language
        
    Returns:
        Cache key string
    """
    return f"msg_translation_{message_id}_{target_language.lower()}"


def detect_language(text: str) -> str:
    """
    Detect if text is in Tamil, Tanglish, or English.
    
    Args:
        text: Text to analyze
        
    Returns:
        Language type: 'tamil', 'tanglish', or 'english'
    """
    if not text or not isinstance(text, str):
        return 'english'
    
    text = text.strip()
    
    # Tamil Unicode range: U+0B80 to U+0BFF
    tamil_pattern = re.compile(r'[\u0B80-\u0BFF]')
    tamil_char_count = len(tamil_pattern.findall(text))
    
    # Check if text contains significant Tamil characters
    if tamil_char_count > len(text) * 0.3:  # More than 30% Tamil characters
        return 'tamil'
    
    # Tanglish patterns: common Tamil words written in English
    # Extended comprehensive list of Tamil words in English
    tanglish_patterns = [
        # Common Tamil greetings and expressions
        r'\b(vanakkam|namaskar|namaste|ayyo|aiyyo|dei|bro|ra|la|da|ma|machi|machan|kitchdi)\b',
        r'\b(nee|neenga|neeyum|neeya|naan|nanu|adhu|idhu|atha|idha|athaan|dhaan)\b',
        r'\b(enna|enada|enadi|enadhu|epdi|epda|yeppadi|yaaru|yaari)\b',
        r'\b(sari|sarie|saru|sare|sariyama|ok|okayy|okay|hmm|hm|uh|da|daa|pa|paa)\b',
        r'\b(konjam|kondu|kupdu|koorum|koodei)\b',
        r'\b(vera|verai|vendam|venda|vendaa|neeya|nei|neii|enaku|enakku|enalum)\b',
        r'\b(vandha|vandhu|vandhuta|irundha|irukanu|irukkanu|irruku|irukka)\b',
        r'\b(panna|pannadhu|pannicci|pannitu|pannitaan|pannaan|sonnaan|sonnaan)\b',
        r'\b(solra|solren|solren|sollran|sollran|vituta|viduta|vidutam)\b',
        r'\b(oru|rendo|moonru|naalu|aidu|aaru|yelu|ettu|tombai|patthu)\b',
        r'\b(aandavan|devi|shiva|krishna|rama|ganesha)\b',
        # Common Tanglish slang
        r'\b(da|daa|di|di|yaar|super|vera|item|level|scene|mass|cool)\b',
    ]
    
    text_lower = text.lower()
    tanglish_score = 0
    word_tokens = text_lower.split()
    
    # Check each word against Tanglish patterns
    for pattern in tanglish_patterns:
        matches = re.findall(pattern, text_lower)
        tanglish_score += len(matches)
    
    # If we have substantial Tanglish word matches and no/minimal Tamil script, it's Tanglish
    if tanglish_score >= 2 and tamil_char_count == 0:
        return 'tanglish'
    
    # If only one Tanglish word but it's in context (not just random English)
    if tanglish_score >= 1 and len(word_tokens) <= 10 and tamil_char_count == 0:
        # Check if it's really Tanglish or just English with a Tamil word
        english_word_count = 0
        for word in word_tokens:
            if word.lower() in ['how', 'are', 'you', 'i', 'me', 'is', 'am', 'the', 'a', 'an', 
                                'what', 'when', 'where', 'why', 'which', 'who', 'can', 'do', 'will',
                                'would', 'should', 'could', 'is', 'be', 'been', 'have', 'has']:
                english_word_count += 1
        
        # If mostly Tamil words with some English, it's Tanglish
        if english_word_count < len(word_tokens) * 0.7 and tanglish_score > 0:
            return 'tanglish'
    
    # Otherwise, treat as English
    return 'english'


def normalize_to_professional_english(text: str, user_language: str = 'English') -> Tuple[bool, str, str]:
    """
    Normalize user input to professional English.
    Handles Tamil, Tanglish, and casual English inputs.
    
    Args:
        text: User input text
        user_language: User's preferred language (for context)
        
    Returns:
        Tuple of (success, normalized_text, message)
    """
    print(f"\n[NORMALIZE_START] Input: '{text[:50]}...' User language: '{user_language}'")
    
    if not text or not isinstance(text, str):
        msg = "Invalid text provided"
        print(f"[NORMALIZE_FAIL] {msg}")
        return False, text, msg
    
    text = text.strip()
    if len(text) == 0:
        msg = "Text cannot be empty"
        print(f"[NORMALIZE_FAIL] {msg}")
        return False, text, msg
    
    if len(text) > 5000:
        msg = "Text too long (max 5000 characters)"
        print(f"[NORMALIZE_FAIL] {msg}")
        return False, text, msg
    
    detected_lang = detect_language(text)
    print(f"[NORMALIZE] Detected language: {detected_lang}")
    
    try:
        if detected_lang == 'tamil':
            msg = "Tamil text detected - translating to professional English"
            print(f"[NORMALIZE] {msg}")
            success, normalized, trans_msg = translate_text(text, 'English')
            if success and normalized:
                print(f"[NORMALIZE_SUCCESS] Tamil → Professional English")
                return True, normalized, "Normalized from Tamil"
            else:
                print(f"[NORMALIZE_FALLBACK] Translation failed, using original text")
                return False, text, "Translation failed, using original"
        
        elif detected_lang == 'tanglish':
            msg = "Tanglish text detected - translating to professional English"
            print(f"[NORMALIZE] {msg}")
            success, normalized, trans_msg = translate_text(text, 'English')
            if success and normalized:
                print(f"[NORMALIZE_SUCCESS] Tanglish → Professional English")
                return True, normalized, "Normalized from Tanglish"
            else:
                print(f"[NORMALIZE_FALLBACK] Translation failed, using original text")
                return False, text, "Translation failed, using original"
        
        else:  # English
            print(f"[NORMALIZE] English text - normalizing to professional format")
            # Normalize casual English to professional English
            success, normalized, norm_msg = normalize_english_text(text)
            if success:
                print(f"[NORMALIZE_SUCCESS] English normalized to professional format")
                return True, normalized, norm_msg
            else:
                print(f"[NORMALIZE_FALLBACK] Normalization processing complete")
                return True, normalized, norm_msg
    
    except Exception as e:
        print(f"[NORMALIZE_EXCEPTION] Error during normalization: {str(e)}")
        logger.error(f"Normalization error: {str(e)}")
        return False, text, f"Normalization error: {str(e)}"


def normalize_english_text(text: str) -> Tuple[bool, str, str]:
    """
    Normalize casual/slang English to professional English.
    
    Args:
        text: English text to normalize
        
    Returns:
        Tuple of (success, normalized_text, message)
    """
    if not text or not isinstance(text, str):
        return False, text, "Invalid input"
    
    normalized = text.strip()
    
    # Common slang/casual expressions to professional mapping
    casual_to_professional = {
        r'\bu\b': 'you',
        r'\br\b': 'are',
        r'\bpls\b': 'please',
        r'\bty\b': 'thank you',
        r'\bthnx\b': 'thanks',
        r'\bk\b': 'okay',
        r'\btb\b': 'to be',
        r'\bgr8\b': 'great',
        r'\bhey\s+guys': 'hello everyone',
        r'\bthnx\s+m8': 'thank you friend',
        r'\bc\u0027mon': 'come on',
        r'\bwanna\b': 'want to',
        r'\bgonna\b': 'going to',
        r'\bgotta\b': 'got to',
        r'\bkinda\b': 'kind of',
        r'\bsorta\b': 'sort of',
        r'\bcuz\b': 'because',
        r'\bfyi\b': 'for your information',
        r'\blol\b': '',  # Remove LOL
        r'\bhaha\b': '',  # Remove casual laughs
        r'\bhehe\b': '',  # Remove casual laughs
    }
    
    # Apply substitutions (case-insensitive)
    for casual_pattern, professional in casual_to_professional.items():
        normalized = re.sub(casual_pattern, professional, normalized, flags=re.IGNORECASE)
    
    # Fix multiple spaces
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    
    # Capitalize first letter of sentences
    sentences = normalized.split('. ')
    capitalized = '. '.join([s.capitalize() if s else s for s in sentences])
    
    return True, capitalized, "Normalized to professional English"


def get_message_for_sender(content: str, normalized_content: str, user_language: str) -> Tuple[str, str]:
    """
    Get the message to display for the sender.
    If user's language is Tamil and content is in English, translate it.
    
    Args:
        content: Original message content (in professional English)
        normalized_content: Normalized content (from storage)
        user_language: User's preferred language
        
    Returns:
        Tuple of (display_content, translation_source)
    """
    print(f"\n[GET_MESSAGE_SENDER] Language: {user_language}")
    
    display_content = content or normalized_content
    
    user_lang_normalized = user_language.strip().lower()
    
    # If sender's language is Tamil, show Tamil translation
    if user_lang_normalized == 'tamil':
        success, translated, msg = translate_text(content, 'Tamil')
        if success and translated:
            print(f"[GET_MESSAGE_SENDER] SUCCESS - Translated to Tamil for sender")
            return translated, 'translated_for_sender'
        else:
            print(f"[GET_MESSAGE_SENDER] FALLBACK - Using original English")
            return display_content, 'original'
    
    # English users see professional English
    print(f"[GET_MESSAGE_SENDER] SUCCESS - Showing professional English")
    return display_content, 'professional_english'


def get_message_for_receiver(content: str, normalized_content: str) -> Tuple[str, str]:
    """
    Get the message to display for the receiver.
    Always show professional English to ensure clarity.
    
    Args:
        content: Original message content
        normalized_content: Normalized professional English content
        
    Returns:
        Tuple of (display_content, translation_source)
    """
    print(f"\n[GET_MESSAGE_RECEIVER] Preparing professional English for receiver")
    
    # Use normalized content if available, otherwise original
    display_content = normalized_content if normalized_content else content
    
    print(f"[GET_MESSAGE_RECEIVER] SUCCESS - Using professional English")
    return display_content, 'professional_english'
