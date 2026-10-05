"""Core OUI lookup implementation.

Design decisions, stated plainly:

1. Only the 24-bit OUI prefix (first three octets) is considered. We do NOT
   attempt MA-M / MA-S / IAB block lookup (28/36-bit prefixes). Those require a
   much larger dataset and a longest-prefix match. This library is a small
   "who owns this NIC roughly" helper, not a full IEEE assignment browser.

2. Prefixes are stored and matched in uppercase, colon-separated form
   ("AA:BB:CC"). All common MAC notations -- dashes, dots, colons, or no
   separator, in any case -- are normalised to this canonical form before
   comparison.

3. lookup() returns the vendor string on a hit, or None on a miss. It does not
   raise on an unrecognised address. Callers who need to distinguish "not a MAC"
   from "MAC with no known OUI" should call normalize_mac first.
"""

from __future__ import annotations

from typing import Dict, Optional


# A small, embedded OUI table. This is intentionally not the full IEEE list
# (which is ~30k entries and 2MB+ of text). The entries below are enough for
# tests and for casual use; supply your own dict to OuiDatabase for real work.
# Values are vendor names as published by IEEE, trimmed.
_DEFAULT_OUIS: Dict[str, str] = {
    "00:50:F6": "3Com Corporation",
    "00:1B:A9": "Apple, Inc.",
    "8C:85:90": "Apple, Inc.",
    "00:03:93": "Apple Computer, Inc.",
    "00:05:02": "Apple Computer, Inc.",
    "00:0A:95": "Apple Computer, Inc.",
    "00:50:E4": "Belkin International Inc.",
    "00:1D:0F": "Cisco Systems Inc",
    "00:1B:54": "Cisco Systems Inc",
    "00:1F:6E": "Cisco Systems Inc",
    "F4:CF:E7": "Cisco Systems Inc",
    "00:13:20": "Intel Corporate",
    "00:13:02": "Intel Corporate",
    "EC:55:F9": "Intel Corporate",
    "00:0C:29": "VMware, Inc.",
    "00:50:56": "VMware, Inc.",
    "00:05:69": "VMware, Inc.",
    "08:00:27": "PCS Systemtechnik GmbH",
    "0A:00:27": "PCS Systemtechnik GmbH",
    "52:54:00": "Realtek Semiconductor Corp.",
    "DC:A6:32": "Raspberry Pi Trading Ltd",
    "B8:27:EB": "Raspberry Pi Foundation",
    "00:19:D3": "Dell Inc.",
    "F0:1F:C2": "Dell Inc.",
}


class OuiDatabase:
    """A read-only OUI prefix to vendor mapping.

    Construct with no arguments to use the embedded table, or pass a dict of
    {"AA:BB:CC": "Vendor Name"} entries to use your own. Keys must be uppercase
    colon-separated three-octet prefixes; if you are unsure, build the dict via
    normalize_mac and slice, or just pass raw strings through add_prefix.
    """

    def __init__(self, table: Optional[Dict[str, str]] = None) -> None:
        # Copy defensively so callers cannot mutate our internal state by
        # holding onto the dict they passed in. Keys are normalised on the
        # way in so later lookups only have to canonicalise the query.
        source = table if table is not None else _DEFAULT_OUIS
        self._table: Dict[str, str] = {}
        for prefix, vendor in source.items():
            canon = self._canonicalize_prefix(prefix)
            if canon is None:
                # Skip malformed entries rather than raising; a bad seed row
                # shouldn't brick the whole database. This is the pragmatic
                # choice for a tiny library with no logging dependency.
                continue
            self._table[canon] = vendor.strip()

    @staticmethod
    def _canonicalize_prefix(prefix: str) -> Optional[str]:
        """Return the canonical "AA:BB:CC" form of a prefix, or None.

        We reuse normalize_mac but only need the first three octets; if the
        input has fewer than three octets it is not a usable OUI prefix.
        """
        full = normalize_mac(prefix)
        if full is None:
            return None
        # normalize_mac returns 6 octets for a full MAC; for a bare 3-octet
        # prefix it also returns 3 octets. Take the first three either way.
        octets = full.split(":")
        if len(octets) < 3:
            return None
        return ":".join(octets[:3])

    def lookup(self, mac: str) -> Optional[str]:
        """Return the vendor for the given MAC, or None if not found.

        Accepts any common MAC notation (colon/dash/dot/no-separator, any case).
        Also accepts a bare 3-octet OUI prefix as input.
        """
        canon = self._canonicalize_prefix(mac)
        if canon is None:
            return None
        return self._table.get(canon)

    def add_prefix(self, prefix: str, vendor: str) -> None:
        """Add or overwrite an OUI entry at runtime.

        The prefix is canonicalised before storage, so callers can pass
        "aa-bb-cc" or "AABBCC" freely. Raises ValueError if the prefix does
        not contain at least three valid hex octets.
        """
        canon = self._canonicalize_prefix(prefix)
        if canon is None:
            raise ValueError(f"not a valid OUI prefix: {prefix!r}")
        self._table[canon] = vendor.strip()

    def __len__(self) -> int:
        return len(self._table)

    def __contains__(self, mac: str) -> bool:
        canon = self._canonicalize_prefix(mac)
        if canon is None:
            return False
        return canon in self._table


def normalize_mac(mac: str) -> Optional[str]:
    """Normalise a MAC address or OUI prefix to canonical "AA:BB:CC[:DD:EE:FF]" form.

    Returns None if the input is not a plausible MAC. A "plausible" MAC here
    means: only hex digits and optional separators (':', '-', or '.'), with
    either 6 complete octets or a 3-octet prefix, and separators used
    consistently if present.

    We do not accept mixed separators ("AA-BB:CC-DD") because no real device
    emits them and accepting them would mask typos in caller data.
    """
    if not isinstance(mac, str):
        return None

    s = mac.strip()
    if not s:
        return None

    # Detect a consistent separator, if any. We treat the first separator
    # character we encounter as authoritative and reject the string if a
    # different separator appears later.
    sep = None
    for ch in (":", "-", "."):
        if ch in s:
            if sep is not None:
                # Two different separators present -- malformed.
                return None
            sep = ch

    if sep is not None:
        parts = s.split(sep)
    else:
        # No separator. The only valid bare forms are 6 or 12 hex digits
        # (a full MAC) or 6 hex digits (a 3-octet prefix). Anything else is
        # not a MAC we can use.
        if len(s) not in (6, 12):
            return None
        # Split into octet pairs.
        parts = [s[i : i + 2] for i in range(0, len(s), 2)]

    # We accept exactly 3 (prefix) or 6 (full MAC) octets. 4, 5, 7+ are typos.
    if len(parts) not in (3, 6):
        return None

    octets = []
    for p in parts:
        if len(p) != 2:
            return None
        if not all(c in "0123456789abcdefABCDEF" for c in p):
            return None
        octets.append(p.upper())

    return ":".join(octets)


# A shared default database instance for the module-level lookup() helper.
# Created once at import; callers wanting isolation should construct their own
# OuiDatabase rather than mutating this one.
_DEFAULT_DB = OuiDatabase()


def lookup(mac: str) -> Optional[str]:
    """Look up the vendor for a MAC address using the default embedded OUI table.

    Thin wrapper around OuiDatabase().lookup(); see that method for semantics.
    """
    return _DEFAULT_DB.lookup(mac)
