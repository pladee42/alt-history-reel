"""
archivist.py - Google Sheets Manager

Handles all Google Sheets operations:
- Check for duplicate scenarios
- Store new scenarios
- Read pending scenarios for production
- Update scenario status
"""

import os
from typing import Optional, List, Dict, Any
from datetime import datetime

import gspread
import google.auth
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

from screenwriter import Scenario, StageData

# Load environment variables
load_dotenv(override=True)

# Google Sheets API scopes
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

# Sheet column headers (must match Scenario.to_dict() keys)
HEADERS = [
    "id", "title", "premise", "location_name", "location_prompt",
    "stage_1_year", "stage_1_label", "stage_1_description", "stage_1_mood", "stage_1_image_prompt", "stage_1_audio_prompt",
    "stage_2_year", "stage_2_label", "stage_2_description", "stage_2_mood", "stage_2_image_prompt", "stage_2_audio_prompt",
    "stage_3_year", "stage_3_label", "stage_3_description", "stage_3_mood", "stage_3_image_prompt", "stage_3_audio_prompt",
    "status", "created_at", "video_url"
]


class Archivist:
    """Manages Google Sheets storage for scenarios."""
    
    def __init__(self, sheet_id: str, credentials_path: Optional[str] = None):
        """
        Initialize connection to Google Sheets.
        
        Args:
            sheet_id: The Google Sheet ID
            credentials_path: Path to service account JSON (or use GOOGLE_APPLICATION_CREDENTIALS)
        """
        self.sheet_id = sheet_id
        
        # Load credentials
        if credentials_path:
            creds = Credentials.from_service_account_file(credentials_path, scopes=SCOPES)
        else:
            # Check for Cloud Run mounted secret path
            sa_key_path = os.getenv("GCP_SA_KEY_PATH") or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
            if sa_key_path and os.path.exists(sa_key_path):
                creds = Credentials.from_service_account_file(sa_key_path, scopes=SCOPES)
            else:
                # Default to default credentials
                creds, _ = google.auth.default(scopes=SCOPES)
            
        self.client = gspread.authorize(creds)
        
        try:
            self.sheet = self.client.open_by_key(sheet_id)
            self.worksheet = self.sheet.sheet1
        except Exception as e:
            print(f"❌ Error connecting to Sheet {sheet_id}: {e}")
            raise
        
        print(f"📊 Connected to Google Sheet: {self.sheet.title}")
    
    def _get_or_create_worksheet(self, title: str) -> gspread.Worksheet:
        """Get existing worksheet or create new one with headers."""
        try:
            worksheet = self.spreadsheet.worksheet(title)
        except gspread.WorksheetNotFound:
            worksheet = self.spreadsheet.add_worksheet(title=title, rows=1000, cols=len(HEADERS))
            # Add headers
            worksheet.update(values=[HEADERS], range_name='A1')
            worksheet.format('A1:S1', {'textFormat': {'bold': True}})
            print(f"   Created new worksheet: {title}")
        return worksheet
    
    def check_duplicate(self, premise: str) -> bool:
        """Check if a premise already exists."""
        try:
            # Get all premises (assuming column B is Premise... wait, ID is A, Title is B now?)
            # Let's use get_all_records which is safer but slower, OR just get column values.
            # Using HEADERS index: premise is index 2 (0-based)
            premises = self.worksheet.col_values(3) # 1-based index
            return premise in premises
        except Exception:
            return False
    
    def store_scenario(self, scenario: Scenario) -> bool:
        """
        Store a new scenario in the sheet.
        
        Args:
            scenario: The scenario to store
            
        Returns:
            True if stored successfully, False if duplicate
        """
        # Check for duplicates
        if self.check_duplicate(scenario.premise):
            print(f"⚠️ Duplicate premise found: {scenario.premise}")
            return False
        
        # Convert to row
        data = scenario.to_dict()
        row = [data.get(header, "") for header in HEADERS]
        
        # Append to sheet
        self.worksheet.append_row(row, value_input_option='USER_ENTERED')
        print(f"✅ Stored scenario: {scenario.id}")
        
        return True
    
    def update_full_scenario(self, scenario: Scenario) -> bool:
        """
        Update an existing scenario with full data (including improved prompts).
        
        Args:
            scenario: The scenario to update
        
        Returns:
            True if updated, False if not found
        """
        try:
            # Find row by ID (Column 1)
            cell = self.worksheet.find(scenario.id, in_column=1)
            if not cell:
                print(f"⚠️ Scenario {scenario.id} not found in sheet for update.")
                return False
            
            # Convert to row
            data = scenario.to_dict()
            row_values = [data.get(header, "") for header in HEADERS]
            
            # Update the range
            # Construct range from row number (e.g. A2:Z2)
            row_num = cell.row
            num_cols = len(HEADERS)
            # A is 1. Convert num_cols to letter?
            # Easier: update_cell is slow. update_cells or update(range, [[]])
            
            # gspread update takes range and values
            start_cell = f"A{row_num}"
            self.worksheet.update(values=[row_values], range_name=start_cell, value_input_option='USER_ENTERED')
            print(f"✅ Updated full scenario data: {scenario.id}")
            return True
            
        except Exception as e:
            print(f"❌ Error updating scenario {scenario.id}: {e}")
            return False

    def get_scenario(self, scenario_id: str) -> Optional[Scenario]:
        """
        Get a scenario by ID.
        
        Args:
            scenario_id: The ID to find
            
        Returns:
            Scenario object or None if not found
        """
        try:
            cell = self.worksheet.find(scenario_id, in_column=1)
            if not cell:
                return None
            
            # Get the whole row
            row_values = self.worksheet.row_values(cell.row)
            
            # Map headers to values
            row_dict = {}
            for i, header in enumerate(HEADERS):
                if i < len(row_values):
                    row_dict[header] = row_values[i]
                else:
                    row_dict[header] = ""
            
            return self._row_to_scenario(row_dict)
            
        except Exception as e:
            print(f"❌ Error getting scenario: {e}")
            return None

    def get_pending_scenarios(self, limit: int = 10) -> List[Scenario]:
        """
        Get scenarios with status = PENDING.
        
        Args:
            limit: Maximum number of scenarios to return
            
        Returns:
            List of Scenario objects
        """
        all_rows = self.worksheet.get_all_records()
        
        pending = []
        for row in all_rows:
            if row.get("status", "").upper() == "PENDING":
                scenario = self._row_to_scenario(row)
                pending.append(scenario)
                if len(pending) >= limit:
                    break
        
        return pending
    
    def update_status(self, scenario_id: str, status: str, video_url: str = "") -> bool:
        """
        Update the status of a scenario.
        
        Args:
            scenario_id: The ID to update
            status: New status
            video_url: Optional video URL
            
        Returns:
            True if updated, False if not found
        """
        try:
            cell = self.worksheet.find(scenario_id, in_column=1)
            if not cell:
                print(f"⚠️ Scenario {scenario_id} not found.")
                return False
            
            row = cell.row
            
            # Update Status (Column 'status')
            status_col = HEADERS.index("status") + 1
            self.worksheet.update_cell(row, status_col, status)
            
            if video_url:
                url_col = HEADERS.index("video_url") + 1
                self.worksheet.update_cell(row, url_col, video_url)
                
            return True
        except Exception as e:
            print(f"❌ Error updating status: {e}")
            return False
    
    def _row_to_scenario(self, row: Dict[str, Any]) -> Scenario:
        """Convert sheet row dict to Scenario object."""
        return Scenario(
            id=str(row.get("id", "")),
            title=str(row.get("title", "")),
            premise=row.get("premise", ""),
            location_name=row.get("location_name", ""),
            location_prompt=row.get("location_prompt", ""),
            stage_1=StageData(
                year=str(row.get("stage_1_year", "")),
                label=row.get("stage_1_label", ""),
                description=row.get("stage_1_description", ""),
                mood=row.get("stage_1_mood", ""),
                image_prompt=row.get("stage_1_image_prompt", ""),
                audio_prompt=row.get("stage_1_audio_prompt", "")
            ),
            stage_2=StageData(
                year=str(row.get("stage_2_year", "")),
                label=row.get("stage_2_label", ""),
                description=row.get("stage_2_description", ""),
                mood=row.get("stage_2_mood", ""),
                image_prompt=row.get("stage_2_image_prompt", ""),
                audio_prompt=row.get("stage_2_audio_prompt", "")
            ),
            stage_3=StageData(
                year=str(row.get("stage_3_year", "")),
                label=row.get("stage_3_label", ""),
                description=row.get("stage_3_description", ""),
                mood=row.get("stage_3_mood", ""),
                image_prompt=row.get("stage_3_image_prompt", ""),
                audio_prompt=row.get("stage_3_audio_prompt", "")
            ),
            status=row.get("status", "PENDING"),
            created_at=str(row.get("created_at", "")),
            video_url=row.get("video_url", ""),
        )
    
    def get_all_scenarios(self) -> List[Scenario]:
        """Get all scenarios from the sheet."""
        all_rows = self.worksheet.get_all_records()
        return [self._row_to_scenario(row) for row in all_rows]


if __name__ == "__main__":
    import yaml
    
    # Load config to get sheet ID
    with open("configs/realistic.yaml", 'r') as f:
        config = yaml.safe_load(f)
    
    sheet_id = config.get("google_sheet_id")
    if not sheet_id or sheet_id == "YOUR_SHEET_ID_HERE":
        print("❌ Please configure google_sheet_id in configs/realistic.yaml")
        exit(1)
    
    print("\n" + "=" * 50)
    print("📊 Testing Archivist")
    print("=" * 50)
    
    archivist = Archivist(sheet_id)
    
    # Test: Get pending scenarios
    pending = archivist.get_pending_scenarios()
    print(f"\n📋 Found {len(pending)} pending scenarios")
    for s in pending:
        print(f"   - {s.id}: {s.premise[:50]}...")
