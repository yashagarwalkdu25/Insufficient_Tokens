"""Application settings loaded from environment variables."""

from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Central configuration for the MCP server."""

    # LLM
    openai_api_key: str = ""
    openai_model_reasoning: str = "gpt-4o"
    openai_model_fast: str = "gpt-4o-mini"

    # Angel One SmartAPI — https://smartapi.angelone.in/docs
    angel_one_api_key: str = ""
    angel_one_api_secret: str = ""
    angel_one_client_code: str = ""
    angel_one_password: str = ""
    angel_one_totp_secret: str = ""

    # Alpha Vantage
    alpha_vantage_key: str = ""

    # Finnhub
    finnhub_key: str = ""

    # GNews
    gnews_key: str = ""

    # LangSmith
    langsmith_api_key: str = ""
    langsmith_project: str = "finint-mcp"
    langchain_tracing_v2: bool = True

    # Keycloak
    keycloak_url: str = "http://keycloak:8080"
    keycloak_public_url: str = "http://localhost:10003"
    keycloak_realm: str = "finint"
    keycloak_client_id: str = "finint-dashboard"

    # PostgreSQL
    postgres_host: str = "postgres"
    postgres_port: int = 5432
    postgres_db: str = "finint"
    postgres_user: str = "finint"
    postgres_password: str = "finint_secure_pwd_2026"

    # Redis
    redis_host: str = "redis"
    redis_port: int = 6379

    # MCP Server (bind address / port inside container or local process)
    mcp_server_host: str = "0.0.0.0"
    mcp_server_port: int = 10004
    # Public URL for OAuth protected-resource metadata (browser / MCP clients on host)
    oauth_resource_url: str = "http://localhost:10004"

    @property
    def postgres_dsn(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def postgres_async_dsn(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}"

    @property
    def keycloak_issuer(self) -> str:
        """Public issuer URL — must match the 'iss' claim in JWT tokens."""
        return f"{self.keycloak_public_url}/realms/{self.keycloak_realm}"

    @property
    def keycloak_internal_issuer(self) -> str:
        """Internal issuer URL — used for JWKS fetching inside Docker."""
        return f"{self.keycloak_url}/realms/{self.keycloak_realm}"

    @property
    def keycloak_jwks_uri(self) -> str:
        """JWKS URI — uses internal URL for Docker networking."""
        return f"{self.keycloak_internal_issuer}/protocol/openid-connect/certs"

    @property
    def keycloak_token_endpoint(self) -> str:
        return f"{self.keycloak_issuer}/protocol/openid-connect/token"

    @property
    def keycloak_auth_endpoint(self) -> str:
        return f"{self.keycloak_issuer}/protocol/openid-connect/auth"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
