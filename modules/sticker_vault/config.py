"""Configuration for the Sticker Vault module."""

MODULE_VERSION = "1.0.0"
CALLBACK_PREFIX = "sv_"

PACK_CAPACITY = 120
MAX_PACK_PARTS = 999

PENDING_ACTION_TTL_SECONDS = 15 * 60
PENDING_ACTION_CACHE_SIZE = 512

DEFAULT_STICKER_EMOJI = "🙂"
SUPPORTED_STICKER_TYPES = {"regular"}
SUPPORTED_STICKER_FORMATS = {"static", "animated", "video"}

PACK_TABLE = "sticker_vault_packs"
