# MAC OUI Lookup

A small, dependency-free Python library for matching MAC address prefixes against an OUI vendor mapping. Ships with a tiny embedded table; supply your own for real work.

## Usage

```python
from mac_oui_lookup import OuiDatabase, lookup, normalize_mac

# Module-level helper using the embedded default table.
print(lookup("00:50:F6:AA:BB:CC"))   # -> "3Com Corporation"
print(lookup("00-50-f6-aa-bb-cc"))   # -> "3Com Corporation"
print(lookup("0050F6AABBCC"))        # -> "3Com Corporation"
print(lookup("11:22:33:44:55:66"))   # -> None

# Normalise a MAC yourself if you want to tell "not a MAC" from "unknown OUI".
print(normalize_mac("00-50-F6-00-01-02"))  # -> "00:50:F6:00:01:02"
print(normalize_mac("nope"))               # -> None

# Custom table for real deployments.
db = OuiDatabase({
    "00:1B:A9": "Apple, Inc.",
    "8C:85:90": "Apple, Inc.",
})
print(db.lookup("8c:85:90:11:22:33"))  # -> "Apple, Inc."
db.add_prefix("11:22:33", "My Custom Vendor")
print(db.lookup("11:22:33:00:00:00"))  # -> "My Custom Vendor"
```

Exported names: `OuiDatabase`, `lookup`, `normalize_mac`.

## Why this exists

The IEEE publishes a ~30,000-entry OUI list as a 2 MB+ text file. Most code that needs to say "who made this NIC" wants a few dozen well-known vendors, not a heavyweight dependency or a downloaded dataset. This library is that: a stdlib-only module with an embedded table and a normaliser that accepts the common MAC notations (colon, dash, dot, or no separator, any case).

The trade-off: only the 24-bit OUI prefix is matched. MA-M / MA-S / IAB blocks (28- and 36-bit assignments) are not supported. A device whose OUI was reassigned or subdivided will report the original registrant, which may be a parent company or a defunct name. This is good enough for "roughly who built this" and wrong for forensics-grade attribution.

## Edge cases you will hit

- `lookup` returns `None` both for an unrecognised OUI and for a string that is not a MAC at all. If you need to distinguish, call `normalize_mac` first; it returns `None` for malformed input and a canonical string otherwise.
- Mixed separators ("00:50-F6-00-01-02") are rejected, not silently repaired. Real hardware does not emit these; accepting them would mask typos in your data.
- Bare 3-octet prefixes ("00:50:F6") are accepted as both input to `lookup` and as a normalised form from `normalize_mac`. A bare 6-hex-digit string ("0050F6") is treated as a 3-octet prefix, not a truncated MAC.
- User-supplied tables with malformed keys are silently skipped on construction. `add_prefix` raises `ValueError` for bad input instead, so you can catch it.

## Running the tests

```
PYTHONPATH=src python -m unittest discover -s tests
```

## Performance

The window keeps a bounded buffer, so `push` is constant time and memory does not
grow with the length of the stream. `peak` and `trough` are linear in the window
size, which is the trade that keeps `push` cheap.

## Limitations

Values are coerced to floats, so very large integers lose precision. If you need
exact integer aggregates over a window, this is the wrong tool.

