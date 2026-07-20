
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# local==> returns checkpoint saving db path, in prod returns empty string cause postgre does not need and file location 
def get_db_path() -> str:
    settings = get_settings()
    return settings.checkpoint_db_path if not settings.database_url else ""

#prod==> save checkpoints in postgre
def use_postgres_checkpointer() -> bool:
    settings = get_settings()
    return bool(settings.database_url)
