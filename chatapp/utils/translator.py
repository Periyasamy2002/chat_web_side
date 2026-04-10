"""
Translation utility module for Google Gemini API integration.
Provides functions to translate messages between supported languages.
"""

import os
import logging
import warnings
import traceback
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
    
    # Check if text is already in target language (simple check)
    target_lang_normalized = target_language.strip().lower()
    # If already in English, just return as is
    if target_lang_normalized == 'english':
        msg = "No translation needed (English selected)"
        print(f"[TRANSLATE_SUCCESS] {msg}")
        return True, text, msg
    
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
