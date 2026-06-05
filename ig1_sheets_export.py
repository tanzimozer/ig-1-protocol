"""
IG-1 Google Sheets Integration
Append crawl results to a single Google Sheet, one tab per city per run.
"""

import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import json
from pathlib import Path

class IG1SheetsExporter:
    def __init__(self, credentials_path='~/.hermes/google_service_account.json', spreadsheet_name='IG-1 Protocol Results'):
        """
        Initialize Google Sheets connection.
        
        Args:
            credentials_path: Path to Google service account JSON
            spreadsheet_name: Name of the target Google Sheet
        """
        self.creds_path = Path(credentials_path).expanduser()
        self.sheet_name = spreadsheet_name
        self.client = None
        self.spreadsheet = None
        self._authenticate()
    
    def _authenticate(self):
        """Authenticate with Google Sheets API using service account."""
        try:
            scope = [
                'https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/drive'
            ]
            credentials = Credentials.from_service_account_file(self.creds_path, scopes=scope)
            self.client = gspread.authorize(credentials)
            print(f'✓ Google Sheets authenticated')
        except Exception as e:
            print(f'✗ Google Sheets auth failed: {e}')
            raise
    
    def get_or_create_sheet(self):
        """Get existing spreadsheet or create new one."""
        try:
            self.spreadsheet = self.client.open(self.sheet_name)
            print(f'✓ Opened existing sheet: {self.sheet_name}')
        except gspread.exceptions.SpreadsheetNotFound:
            self.spreadsheet = self.client.create(self.sheet_name)
            self.spreadsheet.share('', perm_type='anyone', role='reader')
            print(f'✓ Created new sheet: {self.sheet_name}')
        return self.spreadsheet
    
    def export_crawl(self, city, results, timestamp=None):
        """
        Export crawl results to a new tab in the sheet.
        
        Args:
            city: City name (becomes tab name)
            results: List of account dicts with keys: username, full_name, follower_count, female_score, business_flag, bio_preview
            timestamp: Optional timestamp for tab naming (defaults to now)
        """
        if not timestamp:
            timestamp = datetime.utcnow().isoformat()
        
        # Tab name: City-YYYYMMDD-HHMMSS
        tab_name = f"{city}-{datetime.fromisoformat(timestamp).strftime('%Y%m%d-%H%M%S')}"[:31]  # GSheets 31-char limit
        
        try:
            # Create new worksheet
            worksheet = self.spreadsheet.add_worksheet(title=tab_name, rows=len(results)+1, cols=7)
            
            # Headers
            headers = ['Username', 'Full Name', 'Followers', 'Female Score', 'Business', 'Bio Preview', 'Crawled At']
            worksheet.append_row(headers)
            
            # Data rows
            rows = []
            for acc in results:
                rows.append([
                    acc.get('username', ''),
                    acc.get('full_name', ''),
                    acc.get('follower_count', 0),
                    round(acc.get('female_score', 0), 2),
                    'Yes' if acc.get('is_business', False) else 'No',
                    acc.get('bio_preview', '')[:100],  # Truncate bio to 100 chars
                    timestamp
                ])
            
            worksheet.append_rows(rows, value_input_option='USER_ENTERED')
            
            # Format header row (bold)
            worksheet.format('A1:G1', {'textFormat': {'bold': True}})
            
            # Auto-resize columns
            worksheet.columns_auto_resize(start_column_index=0, end_column_index=7)
            
            print(f'✓ Exported {len(results)} accounts to tab: {tab_name}')
            return tab_name
        
        except Exception as e:
            print(f'✗ Export failed: {e}')
            raise

def append_to_sheets(city, results):
    """
    Convenience function for crawler integration.
    Call this after each city crawl completes.
    """
    exporter = IG1SheetsExporter()
    exporter.get_or_create_sheet()
    tab_name = exporter.export_crawl(city, results)
    return tab_name
