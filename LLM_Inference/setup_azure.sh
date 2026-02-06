#!/bin/bash
# Quick setup script for Azure OpenAI with GiantRepair

echo "=== GiantRepair Azure OpenAI Setup ==="
echo ""

# Check Python version
echo "Checking Python version..."
python3 --version

# Install dependencies
echo ""
echo "Installing Python dependencies..."
pip install python-dotenv openai==0.28.0 transformers==4.33.3 torch numpy

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo ""
    echo "Creating .env file from example..."
    cp .env.example .env
    echo ""
    echo "⚠️  IMPORTANT: Edit .env file with your Azure OpenAI credentials!"
    echo "   Run: nano .env"
    echo ""
else
    echo ""
    echo "✓ .env file already exists"
fi

# Verify imports work
echo ""
echo "Testing imports..."
python3 -c "from dotenv import load_dotenv; import openai; print('✓ All imports successful')"

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "1. Edit .env with your Azure credentials: nano .env"
echo "2. Generate patches: python run_apr.py --model_name gpt-3.5 --chances 20 --dataset defects4j --folder ../data/patches"
echo "3. See AZURE_SETUP_GUIDE.md for full documentation"
