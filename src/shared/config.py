from pathlib import Path


class Config:
    DIR = Path.home()/".raga"
    DB_PATH = ":memory:"
    HEARTBEAT_TIMEOUT = 5
    HEARBEAT_RATE = 1
    # DB_PATH = DIR/"session"/"session.sqlite"

config = Config()