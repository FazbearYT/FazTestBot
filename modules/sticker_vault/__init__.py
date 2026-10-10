"""Sticker Vault module entry point for automatic discovery."""

from .module import StickerVaultModule

sticker_vault_module = StickerVaultModule()


__all__ = ["StickerVaultModule", "sticker_vault_module"]
