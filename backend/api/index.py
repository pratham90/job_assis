from main import app
import os
import sys
from pathlib import Path

# Add the parent directory to Python path to import main.py
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

# Import the FastAPI app

# Vercel serverless function handler


def handler(request, context):
    # Set environment variables for Vercel
    os.environ.setdefault('MONGO_URI', os.getenv(
        'MONGO_URI', 'mongodb+srv://Jobs:Jobs-provider@jobs.2m8l8hb.mongodb.net'))

    # Import and return the FastAPI app
    from mangum import Mangum
    handler = Mangum(app)
    return handler(request, context)
