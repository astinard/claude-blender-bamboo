"""Configuration management for Claude Fab Lab."""

from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="FAB_",
        extra="ignore",
    )

    # Paths
    output_dir: Path = Field(default=Path("output"), description="Output directory for generated files")
    data_dir: Path = Field(default=Path("data"), description="Data directory for databases and storage")

    # Printer configuration
    printer_ip: Optional[str] = Field(default=None, description="Bambu Lab printer IP address")
    printer_serial: Optional[str] = Field(default=None, description="Printer serial number")
    printer_access_code: Optional[str] = Field(default=None, description="Printer access code")

    # AI Generation
    meshy_api_key: Optional[str] = Field(default=None, description="Meshy AI API key")
    tripo_api_key: Optional[str] = Field(default=None, description="Tripo AI API key")
    openai_api_key: Optional[str] = Field(default=None, description="OpenAI API key")

    # Web server
    web_host: str = Field(default="127.0.0.1", description="Web server host")
    web_port: int = Field(default=9880, description="Web server port (unique: 9880)")

    # MQTT settings for Bambu Lab
    mqtt_host: Optional[str] = Field(default=None, description="MQTT broker host (usually printer IP)")
    mqtt_port: int = Field(default=8883, description="MQTT broker port")
    mqtt_use_tls: bool = Field(default=True, description="Use TLS for MQTT connection")

    # Database
    database_url: str = Field(
        default="sqlite+aiosqlite:///data/fablab.db",
        description="Database connection URL",
    )

    # Feature flags
    enable_voice: bool = Field(default=False, description="Enable voice control")
    enable_camera: bool = Field(default=False, description="Enable camera monitoring")
    mock_mode: bool = Field(default=False, description="Enable mock mode for testing")


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get the global settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def configure(settings: Settings) -> None:
    """Override global settings."""
    global _settings
    _settings = settings
