import sys
import os
from pathlib import Path

# Add the project root to sys.path so 'backend' can be imported
root_path = Path(__file__).parent.parent
sys.path.append(str(root_path))

try:
    from backend.main import app
except ImportError as e:
    print(f"Deployment Error: Could not import backend.main. Path: {sys.path}")
    raise e
