# IG-1 Protocol

Large-scale Instagram follower mining targeting female-presenting accounts across 14 cities globally.

## What It Does

Deploys parallel crawlers across 14 cities to identify and catalog female fitness/lifestyle accounts with 500–3,500 followers on public profiles.

**Cities (Phase 1):**
- Melbourne, Sydney, London, Tallinn, Brisbane
- Anchorage, Edmonton, Dallas, Chicago, Salt Lake City
- Portland, Warsaw, Kyiv, Moscow

## Configuration

**Filter criteria:**
- Followers: 500–3,500
- Account status: Public only
- Gender signal: Detects female indicators in bio, full name, username
- Target quota: Up to 50 accounts per city (700 total)

## Usage

```bash
python3 ig1_crawler.py
```

**Requirements:**
- Instagram session cookies in `~/.hermes/vault.json` (key: `instagram`)
- `requests` library

## Output

- `targets.json` — Full profile data (username, followers, bio, verified status, timestamp)
- `targets.csv` — CSV export for spreadsheet import
- Per-city results saved to `/tmp/ig_city_{cityname}.json`

## Architecture

- **Parallel execution:** One subagent per city
- **Hashtag strategy:** 10 tags per city (lifestyle, fitness, girl, women, blogger, local)
- **Scraping method:** HTML profile scraping + API enrichment
- **Rate limiting:** 45–75 second spacing between requests to avoid Meta detection

## Known Issues

- API endpoint `/api/v1/users/{uid}/info/` can return 401 (require_login) if rate limited or session stale
- Hashtag pagination maxes at 8 pages per tag (adjust `max_pages` in code)
- Some accounts filtered out during enrichment phase if endpoint fails

## Next Steps

- [x] Rename from "Protocol Veronica" to "IG-1 Protocol"
- [ ] Implement exponential backoff retry logic for rate limits
- [ ] Add webhook for auto-follow on new targets
- [ ] Sync results to Google Sheet
- [ ] Expand to additional cities (Phase 2)
