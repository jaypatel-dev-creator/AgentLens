import logging
import sys


def setup_logging(app_env: str = "development") -> None:
    log_level = logging.DEBUG if app_env == "development" else logging.INFO # for local set log level to debug, for prod, set to info. 

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    # Silencing  noisy third-party loggers — only show WARNING and above
    for noisy in [
        "httpx",
        "httpcore",
        "aiosqlite",
        "passlib",
        "urllib3",
        "langsmith",
        "langsmith.client",
        "opentelemetry",
        "opentelemetry.sdk",
        "chromadb",
        "chromadb.telemetry",
        "google.auth",
        "google.auth.transport",
    ]:
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)