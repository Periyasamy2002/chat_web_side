#!/bin/bash
# Language Translation Feature - Quick Setup & Test Guide

echo "========================================="
echo "Django Chat - Language Translation Setup"
echo "========================================="
echo ""

# Step 1: Apply Database Migration
echo "Step 1: Applying database migration..."
python manage.py migrate
if [ $? -eq 0 ]; then
    echo "✓ Migration applied successfully"
else
    echo "✗ Migration failed"
    exit 1
fi

echo ""
echo "Step 2: Verifying environment variables..."
if grep -q "GEMINI_API_KEY" .env; then
    echo "✓ GEMINI_API_KEY found in .env"
else
    echo "⚠ Warning: GEMINI_API_KEY not found in .env"
    echo "  Add it: GEMINI_API_KEY=your_key_here"
fi

if grep -q "SUPPORTED_LANGUAGES" .env; then
    echo "✓ SUPPORTED_LANGUAGES found in .env"
else
    echo "⚠ Warning: SUPPORTED_LANGUAGES not found in .env"
    echo "  Add it: SUPPORTED_LANGUAGES=English,Tamil"
fi

echo ""
echo "Step 3: Checking imports..."
python -c "import google.generativeai; print('✓ google-generativeai installed')" || {
    echo "✗ google-generativeai not installed"
    echo "  Install: pip install google-generativeai==0.4.1"
    exit 1
}

python -c "from dotenv import load_dotenv; print('✓ python-dotenv installed')" || {
    echo "✗ python-dotenv not installed"
    echo "  Install: pip install python-dotenv==1.0.0"
    exit 1
}

echo ""
echo "Step 4: Testing translation module..."
python << 'EOF'
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chatproject.settings')

try:
    from chatapp.utils.translator import translate_text, validate_language
    
    # Test language validation
    if validate_language('English'):
        print("✓ Language validation working")
    
    # Test import
    print("✓ Translator module imported successfully")
except ImportError as e:
    print(f"✗ Import error: {e}")
    exit(1)
except Exception as e:
    print(f"✗ Error: {e}")
    exit(1)
EOF

echo ""
echo "========================================="
echo "Setup Complete! Ready for Testing."
echo "========================================="
echo ""
echo "Next steps:"
echo "1. Start development server: python manage.py runserver"
echo "2. Go to http://localhost:8000/chat/"
echo "3. Select a language and join a group"
echo "4. Click 🌐 Translate button on messages"
echo ""
