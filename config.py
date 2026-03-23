import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    def __init__(self):
        self.notion_token = self._require("NOTION_TOKEN")
        self.gemini_api_key = self._require("GEMINI_API_KEY")
        self.google_credentials_path = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")
        self.google_token_path = "token.json"

        self.work_day_start = int(os.getenv("WORK_DAY_START", "8"))
        self.work_day_end = int(os.getenv("WORK_DAY_END", "22"))
        self.max_hours_per_day = float(os.getenv("MAX_HOURS_PER_DAY", "4"))
        self.look_ahead_days = int(os.getenv("LOOK_AHEAD_DAYS", "14"))
        self.timezone = os.getenv("TIMEZONE", "America/New_York")

    def _require(self, key: str) -> str:
        value = os.getenv(key)
        if not value:
            raise ValueError(
                f"Missing required environment variable: {key}\n"
                f"Copy .env.example to .env and fill in your API keys."
            )
        return value
