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
    "id", "premise", "location_name", "location_prompt",
    "stage_1_year", "stage_1_label", "stage_1_description", "stage_1_mood",
    "stage_2_year", "stage_2_label", "stage_2_description", "stage_2_mood",
    "stage_3_year", "stage_3_label", "stage_3_description", "stage_3_mood",
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
        
        # Get credentials path
        creds_path = credentials_path or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if not creds_path:
            raise ValueError("GOOGLE_APPLICATION_CREDENTIALS not found")
        
        # Authenticate
        credentials = Credentials.from_service_account_file(creds_path, scopes=SCOPES)
        self.client = gspread.authorize(credentials)
        
        # Open the spreadsheet
        self.spreadsheet = self.client.open_by_key(sheet_id)
        self.worksheet = self._get_or_create_worksheet("Scenarios")
        
        print(f"📊 Connected to Google Sheet: {self.spreadsheet.title}")
    
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
        """
        Check if a similar premise already exists.
        
        Args:
            premise: The premise to check
            
        Returns:
            True if duplicate found, False otherwise
        """
        all_premises = self.worksheet.col_values(2)  # Column B = premise
        
        # Simple check: exact match (could be made smarter with embeddings)
        premise_lower = premise.lower().strip()
        for existing in all_premises[1:]:  # Skip header
            if existing.lower().strip() == premise_lower:
                return True
        
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
            scenario_id: The scenario ID
            status: New status (PENDING, IMAGES_DONE, VIDEO_DONE, COMPLETED)
            video_url: Optional video URL (for COMPLETED status)
            
        Returns:
            True if updated successfully
        """
        # Find the row
        try:
            cell = self.worksheet.find(scenario_id, in_column=1)
        except gspread.CellNotFound:
            print(f"❌ Scenario not found: {scenario_id}")
            return False
        
        row_num = cell.row
        
        # Update status (column Q = 17)
        self.worksheet.update_cell(row_num, 17, status)
        
        # Update video_url if provided (column S = 19)
        if video_url:
            self.worksheet.update_cell(row_num, 19, video_url)
        
        print(f"📝 Updated {scenario_id}: status = {status}")
        return True
    
    def _row_to_scenario(self, row: Dict[str, Any]) -> Scenario:
        """Convert a sheet row to Scenario object."""
        return Scenario(
            id=row.get("id", ""),
            premise=row.get("premise", ""),
            location_name=row.get("location_name", ""),
            location_prompt=row.get("location_prompt", ""),
            stage_1=StageData(
                year=row.get("stage_1_year", ""),
                label=row.get("stage_1_label", ""),
                description=row.get("stage_1_description", ""),
                mood=row.get("stage_1_mood", ""),
            ),
            stage_2=StageData(
                year=row.get("stage_2_year", ""),
                label=row.get("stage_2_label", ""),
                description=row.get("stage_2_description", ""),
                mood=row.get("stage_2_mood", ""),
            ),
            stage_3=StageData(
                year=row.get("stage_3_year", ""),
                label=row.get("stage_3_label", ""),
                description=row.get("stage_3_description", ""),
                mood=row.get("stage_3_mood", ""),
            ),
            status=row.get("status", "PENDING"),
            created_at=row.get("created_at", ""),
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
