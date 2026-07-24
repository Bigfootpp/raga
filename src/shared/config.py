from pathlib import Path

class Config:
    DIR = Path.home()/".raga"
    DB_PATH = ":memory:"
    # DB_PATH = DIR/"session"/"session.sqlite"

config = Config()