# SAP APP MVP

Runnable MVP for SAP Business One Query Manager automation and analytics.

## Stack
- Python 3.12+
- Streamlit
- Playwright
- Pandas
- BeautifulSoup4
- Pydantic Settings

## Architecture (Clean / Hexagonal)
- `domain/`: entities, value objects, contracts, errors
- `application/`: use cases orchestration
- `infrastructure/`: SAP adapters, parsers, cache, scheduler
- `interfaces/`: Streamlit pages
- `app/`: config, observability, app bootstrap

## Quickstart
1. Create and activate env:
   ```bash
   python3.12 -m venv .venv
   source .venv/bin/activate
   ```
2. Install dependencies:
   ```bash
   pip install -e .[dev]
   playwright install chromium
   ```
3. Configure environment:
   ```bash
   cp .env.example .env
   ```
4. Run app:
   ```bash
   streamlit run app/main.py
   ```

## Mock mode (default)
Set `SAP_MOCK_MODE=true` in `.env` to run without SAP access.
The app reads CSV fixtures from `fixtures/` and stays fully runnable.

## Tests / checks
```bash
pytest
python -m compileall .
```

## Notes
- Do not store secrets in source files.
- Real SAP browser automation is implemented behind infrastructure ports and guarded with retries.
