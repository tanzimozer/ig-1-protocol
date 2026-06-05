# Protocol Veronica

Instagram scraper targeting female fitness accounts across 14 cities globally.

## Configuration

**Filter criteria:**
- Followers: 500–3,500
- Account status: Public only
- Gender signal: Detects female indicators in bio, full name, username

**Cities (Phase 1):**
- Melbourne (target: 100 accounts)
- Tallinn (target: 50 accounts)

## Usage

```bash
python3 protocol_veronica.py
```

**Requirements:**
- Instagram session cookies in `~/.hermes/vault.json` (key: `instagram`)
- `requests` library

## Output

- `targets.json` — Full profile data (username, followers, bio, verified status, timestamp)
- `targets.csv` — CSV export for spreadsheet import

## Known Issues

- API endpoint `/api/v1/users/{uid}/info/` can return 401 (require_login) if rate limited or session stale
- Hashtag pagination maxes at 8 pages per tag (adjust `max_pages` in code)
- Some accounts filtered out during enrichment phase if endpoint fails

## Next Steps

- [ ] Add 12 more cities (Seattle, London, Singapore, etc.)
- [ ] Implement retry logic with exponential backoff for rate limits
- [ ] Add webhook for auto-follow on new targets
- [ ] Sync to Google Sheet
