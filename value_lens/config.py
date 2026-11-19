"""Settings shared across the app."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = PROJECT_ROOT / ".cache"
DATA_DIR = PROJECT_ROOT / "data"  # your own files (ISIN-to-ticker list); in .gitignore
SAMPLES_DIR = PROJECT_ROOT / "samples"
PORTFOLIO_CSV_ENV = "PORTFOLIO_CSV"  # path to Consolidated_Portfolio_Positions.csv, set in .env

# Graham (1973 ed., Ch. 14) asked for at least $100 million of annual sales.
# US consumer prices have risen roughly 8x since then, so ~$800 million is a
# like-for-like threshold. Change it in the sidebar if you prefer another figure.
DEFAULT_MIN_REVENUE_USD = 800_000_000

# How long downloaded data is reused before fetching again (seconds).
TICKER_LIST_MAX_AGE = 7 * 24 * 3600
FACTS_MAX_AGE = 24 * 3600
MARKET_MAX_AGE = 6 * 3600

# Years of history each Graham test wants.
YEARS_EARNINGS_STABILITY = 10
YEARS_EARNINGS_GROWTH = 10
YEARS_DIVIDEND_RECORD = 20

# Listed for fewer years than this -> show the "recent IPO" flag.
RECENT_IPO_YEARS = 5
