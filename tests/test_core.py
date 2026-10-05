import unittest

from mac_oui_lookup import OuiDatabase, lookup, normalize_mac


class TestNormalizeMac(unittest.TestCase):
    def test_colon_separated_uppercase(self):
        self.assertEqual(normalize_mac("00:50:F6:00:01:02"), "00:50:F6:00:01:02")

    def test_lowercase_normalised_to_uppercase(self):
        self.assertEqual(normalize_mac("00:50:f6:00:01:02"), "00:50:F6:00:01:02")

    def test_dash_separated(self):
        self.assertEqual(normalize_mac("00-50-F6-00-01-02"), "00:50:F6:00:01:02")

    def test_dot_separated(self):
        self.assertEqual(normalize_mac("00.50.F6.00.01.02"), "00:50:F6:00:01:02")

    def test_no_separator_six_octets(self):
        self.assertEqual(normalize_mac("0050F6000102"), "00:50:F6:00:01:02")

    def test_bare_three_octet_prefix(self):
        self.assertEqual(normalize_mac("00:50:F6"), "00:50:F6")

    def test_bare_six_digit_prefix(self):
        self.assertEqual(normalize_mac("0050F6"), "00:50:F6")

    def test_empty_string_returns_none(self):
        self.assertIsNone(normalize_mac(""))

    def test_whitespace_only_returns_none(self):
        self.assertIsNone(normalize_mac("   \t "))

    def test_non_string_returns_none(self):
        self.assertIsNone(normalize_mac(None))  # type: ignore[arg-type]
        self.assertIsNone(normalize_mac(12345))  # type: ignore[arg-type]

    def test_mixed_separators_rejected(self):
        # Real devices never emit mixed separators; accepting them would hide
        # caller typos rather than help.
        self.assertIsNone(normalize_mac("00:50-F6-00-01-02"))

    def test_wrong_octet_count_rejected(self):
        self.assertIsNone(normalize_mac("00:50:F6:00:01"))  # 5 octets
        self.assertIsNone(normalize_mac("00:50:F6:00:01:02:03:04"))  # 8 octets

    def test_non_hex_octet_rejected(self):
        self.assertIsNone(normalize_mac("00:50:G6:00:01:02"))

    def test_single_digit_octet_rejected(self):
        self.assertIsNone(normalize_mac("0:50:F6:00:01:02"))

    def test_dotted_notation_is_per_octet_not_quad(self):
        # "dotted" in some firmwares means octet-by-octet, not the
        # "xxxx.xxxx.xxxx" quad form. We only support the octet form here
        # because that is what the test data above exercises; quad form would
        # require a separate parser branch and is not claimed.
        self.assertIsNone(normalize_mac("0050.F600.0102"))


class TestLookup(unittest.TestCase):
    def test_known_vendor_via_colon_mac(self):
        self.assertEqual(lookup("00:50:F6:AA:BB:CC"), "3Com Corporation")

    def test_known_vendor_via_dash_mac(self):
        self.assertEqual(lookup("00-50-F6-AA-BB-CC"), "3Com Corporation")

    def test_known_vendor_via_bare_mac(self):
        self.assertEqual(lookup("0050F6AABBCC"), "3Com Corporation")

    def test_known_vendor_lowercase(self):
        self.assertEqual(lookup("00:50:f6:aa:bb:cc"), "3Com Corporation")

    def test_lookup_by_bare_three_octet_prefix(self):
        self.assertEqual(lookup("00:50:F6"), "3Com Corporation")
        self.assertEqual(lookup("0050F6"), "3Com Corporation")

    def test_unknown_oui_returns_none(self):
        self.assertIsNone(lookup("11:22:33:44:55:66"))

    def test_garbage_returns_none(self):
        self.assertIsNone(lookup("not a mac"))
        self.assertIsNone(lookup(""))

    def test_apple_prefixes_normalised_consistently(self):
        # Two different real Apple OUIs, both should resolve.
        self.assertEqual(lookup("00:1B:A9:01:02:03"), "Apple, Inc.")
        self.assertEqual(lookup("8C:85:90:01:02:03"), "Apple, Inc.")
        self.assertEqual(lookup("8c-85-90-01-02-03"), "Apple, Inc.")


class TestOuiDatabase(unittest.TestCase):
    def test_default_database_has_entries(self):
        db = OuiDatabase()
        self.assertGreater(len(db), 0)

    def test_custom_table_supplied(self):
        db = OuiDatabase({"AA:BB:CC": "Example Vendor"})
        self.assertEqual(db.lookup("AA:BB:CC:DD:EE:FF"), "Example Vendor")
        self.assertEqual(db.lookup("aa:bb:cc:dd:ee:ff"), "Example Vendor")
        self.assertIsNone(db.lookup("00:50:F6:00:00:00"))

    def test_custom_table_normalises_keys_on_construction(self):
        # Caller passes lowercase dash-form keys; we should still match.
        db = OuiDatabase({"aa-bb-cc": "Dash Vendor"})
        self.assertEqual(db.lookup("AA:BB:CC:00:00:00"), "Dash Vendor")

    def test_custom_table_skips_malformed_keys(self):
        # A bad entry in a user-supplied table is skipped, not raised. This
        # matches the docstring's stated behaviour.
        db = OuiDatabase({"AA:BB:CC": "Good", "ZZ:ZZ:ZZ": "Bad", "no": "Ugly"})
        self.assertEqual(db.lookup("AA:BB:CC:00:00:00"), "Good")
        self.assertIsNone(db.lookup("ZZ:ZZ:ZZ:00:00:00"))
        self.assertEqual(len(db), 1)

    def test_add_prefix_adds_entry(self):
        db = OuiDatabase()
        initial = len(db)
        db.add_prefix("11:22:33", "Test Vendor")
        self.assertEqual(len(db), initial + 1)
        self.assertEqual(db.lookup("11:22:33:00:00:00"), "Test Vendor")

    def test_add_prefix_overwrites_existing(self):
        db = OuiDatabase({"AA:BB:CC": "Old Name"})
        db.add_prefix("aa:bb:cc", "New Name")
        self.assertEqual(db.lookup("AA:BB:CC:00:00:00"), "New Name")
        self.assertEqual(len(db), 1)

    def test_add_prefix_rejects_garbage(self):
        db = OuiDatabase()
        with self.assertRaises(ValueError):
            db.add_prefix("nope", "Bad")
        with self.assertRaises(ValueError):
            db.add_prefix("00:50:F6:00:01", "Too short")

    def test_vendor_strings_are_stripped(self):
        db = OuiDatabase({"AA:BB:CC": "  Spaced Vendor  \t"})
        self.assertEqual(db.lookup("AA:BB:CC:00:00:00"), "Spaced Vendor")

    def test_contains_operator(self):
        db = OuiDatabase({"AA:BB:CC": "Vendor"})
        self.assertIn("AA:BB:CC:00:00:00", db)
        self.assertIn("aa-bb-cc", db)
        self.assertNotIn("11:22:33:44:55:66", db)
        self.assertNotIn("garbage", db)

    def test_default_db_not_mutated_by_instance_add(self):
        # Adding to a fresh instance must not bleed into the module-level DB.
        before = lookup("11:22:33:44:55:66")
        db = OuiDatabase()
        db.add_prefix("11:22:33", "Instance Only")
        self.assertEqual(lookup("11:22:33:44:55:66"), before)
        self.assertEqual(db.lookup("11:22:33:44:55:66"), "Instance Only")

    def test_caller_cannot_mutate_internal_table_via_source_dict(self):
        source = {"AA:BB:CC": "Original"}
        db = OuiDatabase(source)
        source["AA:BB:CC"] = "Tampered"
        source["DD:EE:FF"] = "Injected"
        self.assertEqual(db.lookup("AA:BB:CC:00:00:00"), "Original")
        self.assertIsNone(db.lookup("DD:EE:FF:00:00:00"))


if __name__ == "__main__":
    unittest.main()
