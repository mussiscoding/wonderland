from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Required secrets
    session_secret: str
    fernet_key: str

    # Spotify OAuth
    spotify_client_id: str
    spotify_client_secret: str
    spotify_redirect_uri: str = "http://127.0.0.1:8000/callback"

    # Database
    database_url: str = "sqlite:///data/wonderland.db"

    # Optional API keys for scrapers / enrichment
    dice_api_key: str = ""
    skiddle_api_key: str = ""
    ticketmaster_api_key: str = ""
    last_fm_api_key: str = ""

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
