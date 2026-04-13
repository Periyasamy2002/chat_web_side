"""
Tamil and Tanglish detection module
Detects and rejects messages containing:
1. Tamil script (Unicode U+0B80 to U+0BFF)
2. Tanglish (Tamil language written in English letters)
3. Mixed Tamil/English text
"""

import re

# Tamil Unicode range
TAMIL_SCRIPT_START = 0x0B80
TAMIL_SCRIPT_END = 0x0BFF

# Common Tanglish patterns - Tamil words/phrases written in English
TANGLISH_PATTERNS = [
    # Common Tamil greetings and responses
    r'\b(vanakkam|namaskara|namaskar)\b',
    r'\b(saalama|salama|asalamu?alaikum)\b',
    r'\b(sollra|sollre|sollren|sollran)\b',
    r'\b(nee|naan|avan|ava|avanga|avangaluku)\b',
    
    # Tamil phonetic patterns with specific endings
    r'\b(thamizh|tamil|tamizhaga)\b',
    r'\b(pesi|pesadhey|pesanum|pesanum)\b',
    r'\b(veettu|vitu|vittadhu|vittom)\b',
    r'\b(ambi|ambil|ambuladhu)\b',
    
    # Common Tamil words
    r'\b(kudumbam|kudumba|kudumbathula)\b',
    r'\b(orupugai|orupukai)\b',
    r'\b(paravai|paravaigal)\b',
    r'\b(engal|endral)\b',
    
    # Tamil verb patterns
    r'\b(\w*kka\w*nu\b|\w*kk\w*aanen\b|\w*kkanum\b)',
    r'\b(\w*kkara\b|\w*kkira\b|\w*kkiradhu\b)',
    r'\b(seyyanum|seyyum|seyyum)\b',
    
    # Specific Tamil-English mixed patterns
    r'\b(thaniya|thaniye|thaniyadhu)\b',
    r'\b(padikalam|padikalamnu|padikka)\b',
    r'\b(solren|sollran|solldren|sollren)\b',
    
    # Tamil question words
    r'\b(enna|yenna|ennada|ennadi)\b',
    r'\b(yaar|yaarum|yaaruku)\b',
    r'\b(yaaru|yarre|yarukku)\b',
    r'\b(ethanai|ethana|ethanaikku)\b',
    
    # Common Tamil suffixes and particles
    r'\b(\w+ukka|\w+ukku|\w+kkum)\b',
    r'\b(\w+ane|\w+anu|\w+agum)\b',
    r'\b(\w+kku|\w+kka|\w+kkum)\b',
    
    # Tamil conjunctions and connectors
    r'\b(athu|athai|adhu|adhai)\b',
    r'\b(athukku|athukkaaga|adhukkum)\b',
    r'\b(innum|irundhalum|irundhadhu)\b',
    
    # Double character patterns common in Tamil (but not English)
    r'\b(\w*tt\w+|\w*nn\w+|\w*mm\w+|\w*pp\w+|l\w*ll\w+)\b',
    
    # Specific Tanglish indicators
    r'\b(da|thee|di|ma|pa|cha|thaa|paa)\b',
    r'\b(\w+andha?\b|\w+anda?\b|\w+uma?\b)',
    r'\bzhaa?i?\b',
    r'\bij?i\b',
    
    # More Tamil verb and noun patterns
    r'\b(sollvu|sollvachu|sollvom)\b',
    r'\b(kkodu|ddhum|ddhigal)\b',
    r'\b(kaara|kaaran|kaarum)\b',
]

# Compile patterns for faster matching (case-insensitive)
COMPILED_TANGLISH_PATTERNS = [
    re.compile(pattern, re.IGNORECASE) for pattern in TANGLISH_PATTERNS
]


def contains_tamil_script(text):
    """
    Detect if text contains Tamil script characters.
    Tamil Unicode range: U+0B80 to U+0BFF
    """
    if not text:
        return False
    
    for char in text:
        char_code = ord(char)
        if TAMIL_SCRIPT_START <= char_code <= TAMIL_SCRIPT_END:
            return True
    return False


def contains_tanglish(text):
    """
    Detect Tanglish (Tamil written in English letters).
    Checks for common Tamil words/patterns written phonetically.
    """
    if not text:
        return False
    
    # Check against compiled patterns
    for pattern in COMPILED_TANGLISH_PATTERNS:
        if pattern.search(text):
            return True
    
    return False


def is_valid_english_only(text):
    """
    Comprehensive check to ensure text is STRICTLY English only.
    Returns: (is_valid, error_message)
    """
    if not text:
        return True, None
    
    # Check 1: No Tamil script characters
    if contains_tamil_script(text):
        return False, "Messages cannot contain Tamil script. Please use English only."
    
    # Check 2: No Tanglish (Tamil written in English letters)
    if contains_tanglish(text):
        return False, "Messages cannot contain Tanglish. Please use proper English only."
    
    # Check 3: No unusual character patterns that look suspicious
    # Allow basic punctuation and English characters
    allowed_chars = set(
        'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 ' +
        '.,!?;:\'-"()[]{}/@#$%^&*+=~`<>|\\\n\t'
    )
    
    for char in text:
        if char not in allowed_chars and ord(char) > 127:
            # Non-ASCII character that's not Tamil (already checked) - could be other languages
            if not (128 <= ord(char) <= 255):  # Allow extended ASCII
                return False, "Messages must contain English characters only. No other languages or scripts allowed."
    
    return True, None


def filter_message_for_english_only(text):
    """
    Filter and clean message, removing any non-English content.
    Returns cleaned text that only contains valid English.
    """
    if not text:
        return text
    
    # Original message for checking
    cleaned = text
    
    # Remove Tamil script characters if present
    tamil_removed = ''.join(
        char for char in cleaned 
        if not (TAMIL_SCRIPT_START <= ord(char) <= TAMIL_SCRIPT_END)
    )
    
    # If Tamil was removed, it means message contained Tamil
    if tamil_removed != text:
        return None  # Reject entirely
    
    return text


def get_language_violation_details(text):
    """
    Provide detailed information about language violations.
    Useful for logging and debugging.
    """
    violations = []
    
    if contains_tamil_script(text):
        tamil_chars = [
            (i, char, ord(char)) for i, char in enumerate(text)
            if TAMIL_SCRIPT_START <= ord(char) <= TAMIL_SCRIPT_END
        ]
        violations.append({
            'type': 'Tamil Script Detected',
            'count': len(tamil_chars),
            'positions': tamil_chars[:5]  # First 5 occurrences
        })
    
    if contains_tanglish(text):
        violations.append({
            'type': 'Tanglish Detected',
            'details': 'Tamil language written in English letters'
        })
    
    return violations


# Tamil to English (Roman) character mapping for conversion
TAMIL_TO_ROMAN_MAP = {
    # Vowels (சுரம் - Vowels)
    'அ': 'a', 'ஆ': 'aa', 'இ': 'i', 'ஈ': 'ii', 'உ': 'u', 'ஊ': 'uu',
    'எ': 'e', 'ஏ': 'ee', 'ஐ': 'ai', 'ஒ': 'o', 'ஓ': 'oo', 'ஔ': 'au',
    # Consonants (மெய் எழுத்து - Consonants)
    'க': 'k', 'ங': 'ng', 'ச': 'ch', 'ஞ': 'ny', 'ட': 't', 'ண': 'n',
    'த': 'th', 'ந': 'n', 'ப': 'p', 'ம': 'm', 'ய': 'y', 'ர': 'r',
    'ல': 'l', 'வ': 'v', 'ழ': 'zh', 'ள': 'l', 'ற': 'r', 'ன': 'n',
    # Special/Complex consonants
    'ஹ': 'h',
    # Vowel modifiers (மெய்யெழுத்து - Vowel signs)
    'ா': 'aa', 'ி': 'i', 'ீ': 'ii', 'ு': 'u', 'ூ': 'uu',
    'ெ': 'e', 'ே': 'ee', 'ை': 'ai', 'ொ': 'o', 'ோ': 'oo', 'ௌ': 'au',
    # Numerals (எண் - Numbers)
    '௦': '0', '௧': '1', '௨': '2', '௩': '3', '௪': '4',
    '௫': '5', '௬': '6', '௭': '7', '௮': '8', '௯': '9',
}


def convert_tamil_to_english(text):
    """
    Convert Tamil script characters to English/Roman equivalents.
    Replaces Tamil characters with their phonetic English representations.
    
    Args:
        text: Text that may contain Tamil characters
        
    Returns:
        Text with Tamil characters converted to English phonetics
    """
    if not text:
        return text
    
    result = []
    i = 0
    while i < len(text):
        char = text[i]
        
        # Check if it's a Tamil character in the mapping
        if char in TAMIL_TO_ROMAN_MAP:
            result.append(TAMIL_TO_ROMAN_MAP[char])
            i += 1
        # Check if it's Tamil script (even if not in mapping, convert to placeholder)
        elif TAMIL_SCRIPT_START <= ord(char) <= TAMIL_SCRIPT_END:
            # For unmapped Tamil characters, convert to [T] placeholder
            result.append('[T]')
            i += 1
        else:
            # Keep non-Tamil characters as-is
            result.append(char)
            i += 1
    
    return ''.join(result)


def ensure_english_only_display(text):
    """
    Ensure text is suitable for English-only display.
    Removes any Tamil/non-English characters.
    
    Note: Does NOT transliterate! Just removes Tamil script.
    Transliteration (like "vanakkam") is NOT used.
    Translation API handles meaning translation.
    
    Args:
        text: Text to filter
        
    Returns:
        Text with only English characters (Tamil removed, no transliteration)
    """
    if not text:
        return text
    
    result = []
    for char in text:
        char_code = ord(char)
        
        # Keep English letters a-z, A-Z
        if ('a' <= char <= 'z') or ('A' <= char <= 'Z'):
            result.append(char)
        # Keep numbers
        elif char.isdigit():
            result.append(char)
        # Keep spaces and common punctuation
        elif char in ' \t\n.,!?;:\'"()[]{}@-+=*/~`|\\<>':
            result.append(char)
        # Skip Tamil script - do NOT transliterate!
        elif TAMIL_SCRIPT_START <= char_code <= TAMIL_SCRIPT_END:
            continue  # Remove Tamil script entirely
        # Keep other safe characters
        elif ord(char) >= 32 and ord(char) <= 126:
            result.append(char)
    
    return ''.join(result)


def ensure_tamil_only_display(text):
    """
    Ensure text is suitable for Tamil-only display.
    Removes any non-Tamil script characters (English letters, numbers, etc).
    Keeps: Tamil script, spaces, and universal punctuation.
    
    Args:
        text: Text to filter for Tamil-only display
        
    Returns:
        Text with ONLY Tamil characters and safe punctuation/spaces
    """
    if not text:
        return text
    
    result = []
    for char in text:
        char_code = ord(char)
        
        # Keep Tamil script characters (includes vowels, consonants, modifiers)
        if TAMIL_SCRIPT_START <= char_code <= TAMIL_SCRIPT_END:
            result.append(char)
        # Keep spaces and common universal punctuation
        elif char in ' \t\n.,!?;:\'"()[]{}':
            result.append(char)
        # Keep common symbols
        elif char in '@ - + = * / ~ ` | \\ < >':
            result.append(char)
        # Everything else (English letters, digits, etc.) is skipped from display
        # This ensures ONLY Tamil characters show in Tamil mode
    
    return ''.join(result).strip()
