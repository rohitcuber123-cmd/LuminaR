"""Create an isolated local configuration without replacing existing settings."""
from pathlib import Path
import secrets
ROOT = Path(__file__).resolve().parents[1]
target = ROOT/'.env'
if not target.exists():
    target.write_text('MONGO_URI=mongodb://127.0.0.1:27017\nMONGO_DB_NAME=luminar_local\n'
        + 'JWT_SECRET_KEY='+secrets.token_urlsafe(48)+'\n'
        + 'KNOW_MORE_DEVICE_CACHE_ENABLED=false\n'
        + 'LUMINAR_SEARCH_INDEX_DIR=local-data/search-index\n'
        + 'LUMINAR_LEXICAL_PATH=local-data/lexical\n', encoding='utf-8')
    print('Created isolated .env with a new JWT key.')
else:
    print('Existing .env retained. Local seeding requires loopback MongoDB and luminar_local.')
