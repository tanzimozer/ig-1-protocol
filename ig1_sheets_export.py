"""
IG-1 Google Sheets Integration
Append crawl results to a single Google Sheet, one tab per city per run.
Uses existing OAuth token from Google Drive connection.
"""

import gspread
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from datetime import datetime
import json
from pathlib import Path

class IG1SheetsExporter:
    def __init__(self, spreadsheet_id, token_path='~/.hermes/google_token.json'):
        """
        Initialize Google Sheets connection using OAuth token.
        
        Args:
            spreadsheet_id: The Google Sheet ID (from URL)
            token_path: Path to stored OAuth token
        """
        self.spreadsheet_id = spreadsheet_id
        self.token_path = Path(token_path).expanduser()
        self.client = None
        self.spreadsheet = None
        self._authenticate()
    
    def _authenticate(self):
        """Authenticate with Google Sheets API using stored OAuth token."""
        try:
            creds = Credentials.from_authorized_user_file(self.token_path)
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
            
            self.client = gspread.authorize(creds)
            print(f'✓ Google Sheets authenticated (OAuth)')
        except Exception as e:
            print(f'✗ Google Sheets auth failed: {e}')
            raise
    
    def get_spreadsheet(self):
        """Open the spreadsheet by ID."""
        try:
            self.spreadsheet = self.client.open_by_key(self.spreadsheet_id)
            print(f'✓ Opened sheet: {self.spreadsheet.title}')
            return self.spreadsheet
        except Exception as e:
            print(f'✗ Failed to open sheet: {e}')
            raise
    
    def export_crawl(self, city, results, timestamp=None):
        """
        Export crawl results to a new tab in the sheet.
        
        Args:
            city: City name (becomes tab name)
            results: List of account dicts with keys: username, full_name, follower_count, female_score, is_business, bio_preview
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
            
            worksheet.append_rows(rows)
            
            # Format header row (bold)
            worksheet.format('A1:G1', {'textFormat': {'bold': True}})
            
            # Auto-resize columns
            worksheet.columns_auto_resize(start_column_index=0, end_column_index=7)
            
            print(f'✓ Exported {len(results)} accounts to tab: {tab_name}')
            return tab_name
        
        except Exception as e:
            print(f'✗ Export failed: {e}')
            raise

def append_to_sheets(spreadsheet_id, city, results):
    """
    Convenience function for crawler integration.
    Call this after each city crawl completes.
    
    Args:
        spreadsheet_id: Google Sheet ID
        city: City name
        results: List of account dicts
    """
    exporter = IG1SheetsExporter(spreadsheet_id)
    exporter.get_spreadsheet()
    tab_name = exporter.export_crawl(city, results)
    return tab_name
