"""
Vercel ASGI entry point for FastAPI application
"""
import os
import sys
from pathlib import Path

# Add the backend directory to Python path
backend_dir = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_dir))

# Import the FastAPI app
from app.main import app

# Export the ASGI application for Vercel
handler = app
