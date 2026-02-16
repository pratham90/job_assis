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
    # Ensure MONGO_URI is set from environment with fallback
    if not os.getenv('MONGO_URI'):
        os.environ['MONGO_URI'] = 'mongodb+srv://Jobs:Jobs-provider@jobs.2m8l8hb.mongodb.net/?retryWrites=true&writeConcern=majority'

    # Import and return the FastAPI app
    from mangum import Mangum
    mangum_handler = Mangum(app)
    return mangum_handler(request, context)
