
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from helpers.manager import init_settings
from utils.archivist import Archivist, HEADERS

def update_headers():
    print("🔄 Updating Google Sheet Headers to match new schema...")
    
    config_path = PROJECT_ROOT / "configs" / "realistic.yaml"
    settings = init_settings(str(config_path))
    
    archivist = Archivist(settings.google_sheet_id)
    
    # Update Row 1
    print(f"📝 Writing {len(HEADERS)} headers to Row 1...")
    archivist.worksheet.update(values=[HEADERS], range_name="A1", value_input_option='USER_ENTERED')
    print("✅ Headers updated successfully.")
    print("⚠️  NOTE: Existing data rows may now be misaligned with new columns. This is expected for a schema migration.")

if __name__ == "__main__":
    update_headers()
