"""
TripSaathi configuration via Pydantic Settings.
Loads from .env; all API keys optional for graceful degradation.
"""
from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with env file support."""

    model_config = SettingsConfigDict(
        env_file=(".env", ".ENV"),  # .ENV supported for case-sensitive systems
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # API Keys (all optional — graceful degradation when missing)
    OPENAI_API_KEY: Optional[str] = Field(default=None, description="OpenAI API key for GPT-4o / GPT-4o-mini")
    AMADEUS_CLIENT_ID: Optional[str] = Field(default=None, description="Amadeus Self-Service API client ID")
    AMADEUS_CLIENT_SECRET: Optional[str] = Field(default=None, description="Amadeus Self-Service API client secret")
    LITEAPI_KEY: Optional[str] = Field(default=None, description="LiteAPI/Nuitee key for hotel search")
    GOOGLE_PLACES_KEY: Optional[str] = Field(default=None, description="Google Places API key (activities, opening hours)")
    GOOGLE_DIRECTIONS_KEY: Optional[str] = Field(default=None, description="Google Directions API key (can reuse GOOGLE_PLACES_KEY)")
    OPENWEATHERMAP_KEY: Optional[str] = Field(default=None, description="OpenWeatherMap API key")
    REDDIT_CLIENT_ID: Optional[str] = Field(default=None, description="Reddit API client ID for local tips")
    REDDIT_CLIENT_SECRET: Optional[str] = Field(default=None, description="Reddit API client secret")

    # Model configs
    GPT4O_MODEL: str = Field(default="gpt-4o", description="Model for complex tasks (intent, itinerary)")
    GPT4O_MINI_MODEL: str = Field(default="gpt-4o-mini", description="Model for routing and optimization")

    # Cache TTLs (seconds)
    FLIGHT_CACHE_TTL: int = Field(default=1800, description="Flight cache TTL (30 min)")
    HOTEL_CACHE_TTL: int = Field(default=3600, description="Hotel cache TTL (1 hour)")
    WEATHER_CACHE_TTL: int = Field(default=7200, description="Weather cache TTL (2 hours)")
    PLACES_CACHE_TTL: int = Field(default=86400, description="Places cache TTL (24 hours)")

    # Database
    DB_PATH: str = Field(default="yatra.db", description="SQLite database file path")

    @property
    def has_openai(self) -> bool:
        return bool(self.OPENAI_API_KEY)

    @property
    def has_amadeus(self) -> bool:
        return bool(self.AMADEUS_CLIENT_ID and self.AMADEUS_CLIENT_SECRET)

    @property
    def has_hotels(self) -> bool:
        return bool(self.LITEAPI_KEY)

    @property
    def has_places(self) -> bool:
        return bool(self.GOOGLE_PLACES_KEY)

    @property
    def has_directions(self) -> bool:
        return bool(self.GOOGLE_DIRECTIONS_KEY or self.GOOGLE_PLACES_KEY)

    @property
    def has_weather(self) -> bool:
        return bool(self.OPENWEATHERMAP_KEY)

    @property
    def has_reddit(self) -> bool:
        return bool(self.REDDIT_CLIENT_ID and self.REDDIT_CLIENT_SECRET)


@lru_cache
def get_settings() -> Settings:
    return Settings()


# Convenience alias
settings = get_settings()
