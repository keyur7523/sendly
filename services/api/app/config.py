from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Environment configuration. Contract addresses and chain IDs come only from here,
    never from the client or a model (PRD Section 14)."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    privy_app_id: str
    # PEM public key from the Privy dashboard. "\n" escapes are accepted so it fits on one line.
    privy_verification_key: str

    chain_id: int = 10143
    rpc_url: str = "https://testnet-rpc.monad.xyz"
    rpc_timeout_seconds: float = 10.0

    demo_token_address: str | None = None
    demo_token_decimals: int = 6
    demo_token_symbol: str = "DemoUSD"

    # Monad charges the full gas limit (PRD Section 10.3); keep the margin modest and measured.
    gas_margin_bps: int = Field(default=1000, ge=0, le=10_000)
    base_fee_multiplier: int = Field(default=2, ge=1, le=10)
    native_transfer_gas: int = 21_000

    cors_origins: list[str] = ["http://localhost:3000"]
    gate_results_path: Path = REPO_ROOT / "docs" / "signer-gate" / "results.jsonl"

    @field_validator("privy_verification_key")
    @classmethod
    def _unescape_pem(cls, value: str) -> str:
        return value.replace("\\n", "\n").strip()


@lru_cache
def get_settings() -> Settings:
    return Settings()
