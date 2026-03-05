# path.py
#
# Central definition of all filesystem paths used by the extraction scripts.
# Import this module wherever a path to data/ or logs/ is needed.

from pathlib import Path

# Root of the project — the directory this file lives in
BASE_DIR = Path(__file__).parent

# Where chunked JSON data files are written
DATA_DIR = BASE_DIR / "data" / "json"

# Root folder for log files (a dated sub-folder is created automatically)
LOG_DIR = BASE_DIR / "logs"