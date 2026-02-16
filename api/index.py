"""
Vercel ASGI entry point for FastAPI application
"""
import importlib.util
import os
import sys
from pathlib import Path

# Add the backend directory to Python path
backend_dir = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

# Temporarily add backend to sys.path and import
original_sys_path = sys.path[:]
sys.path.insert(0, str(backend_dir))

# Import the FastAPI app from backend
spec = importlib.util.spec_from_file_location(
    "main", str(backend_dir / "main.py"))
main_module = importlib.util.module_from_spec(spec)
sys.modules["main"] = main_module  # Add to modules cache
spec.loader.exec_module(main_module)
app = main_module.app

# Restore original sys.path
sys.path[:] = original_sys_path

# Export the ASGI application for Vercel
handler = app
