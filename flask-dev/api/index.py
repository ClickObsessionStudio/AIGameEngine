import sys
from pathlib import Path

# Add the parent directory (flask-dev) to the system path
# This allows Python to find the 'app.py' file
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import app as app