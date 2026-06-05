# IG-1 Protocol Code Organization

## Modules

### /crawlers
- `ig1_live_crawler.py` — Live discovery via Instagram API hashtags
- `ig1_live_crawler_html.py` — HTML scraping fallback
- `ig1_batch_crawler.py` — Process consolidated handle batches
- `ig1_authenticated_crawler.py` — Authenticated session-based discovery

### /filters
- `ig1_female_filter.py` — Female demographic scoring
- `ig1_business_filter.py` — Business account detection

### /analysis
- `ig1_pattern_analyzer.py` — Pattern recognition engine
- `run_pattern_analysis.py` — Full analysis runner (1,975 handles)
- `run_pattern_analysis_sample.py` — Sample analysis (50 handles)
- `run_pattern_analysis_demo.py` — Demo with synthetic data

### /export
- `ig1_sheets_export.py` — Google Sheets OAuth integration

### /legacy
- `ig1_crawl.py` — Original crawler (deprecated)
- `ig1_feedback.py` — Feedback collection (deprecated)

## Quality Status
- All syntax validated
- All imports verified
- Dual test suite passed
- Code organized and committed
