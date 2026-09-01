"""
CascadeX application configuration.

Loads all settings from environment variables (or a .env file).
Never hardcode secrets — always read from the environment.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application-wide settings loaded from environment variables.

    All fields with no default MUST be provided via environment or .env file.
    Fields with defaults are safe to override per-environment.
    """

    # Neo4j connection
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "password"

    # JWT signing key — must be a long, random string in production
    jwt_secret: str = "change_me_in_production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7

    # Application environment: "dev" | "test" | "staging" | "production"
    env: str = "dev"

    # CORS — comma-separated origins allowed to call the API
    allowed_origins: str = "http://localhost:3000,http://localhost:8080"

    # LLM / OCR — Phase 05
    # Empty string = stub mode (exact-match only, no network call).
    # Set GEMINI_API_KEY in .env to enable fuzzy LLM matching.
    gemini_api_key: str = ""
    # Maximum candidate drugs forwarded to the LLM for fuzzy selection.
    ocr_match_top_k: int = 20

    # Field-level encryption — Phase 09
    # Must be a URL-safe base64-encoded 32-byte Fernet key.
    # Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    # Empty string = no-op passthrough (dev / test only).
    field_encryption_key: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def allowed_origins_list(self) -> list[str]:
        """Return CORS origins as a Python list."""
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def is_dev(self) -> bool:
        """True when running in the development environment."""
        return self.env.lower() == "dev"

    @property
    def is_test(self) -> bool:
        """True when running the test suite (ENV=test)."""
        return self.env.lower() == "test"

    @property
    def rate_limit_register(self) -> str:
        """Rate limit string for the /register endpoint.

        High limit in test mode so integration tests can freely register users.
        """
        return "10000/minute" if self.is_test else "10/minute"

    @property
    def rate_limit_login(self) -> str:
        """Rate limit string for the /login and /otp endpoints."""
        return "10000/minute" if self.is_test else "10/minute"


# Module-level singleton — import `settings` from here everywhere
settings = Settings()
