"""MAC OUI lookup: match MAC address prefixes to vendor names."""

from .core import OuiDatabase, lookup, normalize_mac

__all__ = ["OuiDatabase", "lookup", "normalize_mac"]
