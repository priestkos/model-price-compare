"""Unit tests for the price fetcher's parsing and matching logic.

Run:  python -m unittest scripts/test_fetch_prices.py -v
These run offline. They pin the exact bugs found while building the site:
  * struck-through prices (<s>, and <del class=...>) must read the NEW price, not the old one
  * a 'free' suffix must never match the paid model
  * the 3:1 blend and the drop/rise annotation must follow the history
"""
import importlib.util
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("fp", HERE / "fetch_prices.py")
fp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fp)


class Money(unittest.TestCase):
    def test_plain_and_free(self):
        self.assertEqual(fp.money("$0.30"), 0.30)
        self.assertEqual(fp.money("Free"), 0.0)
        self.assertIsNone(fp.money("—"))

    def test_struck_price_reads_new_value(self):
        # Command Code / Zen discount markup: <s>old</s>new
        self.assertEqual(fp.split_was("<s>$0.60</s>$0.30<button>+1</button>")[0], 0.30)
        self.assertEqual(fp.split_was("<s>$0.60</s>$0.30")[1], 0.60)
        # Zen markup: <del>old</del> new
        self.assertEqual(fp.split_was("<del>$1.36</del> $0.68")[0], 0.68)
        self.assertEqual(fp.split_was("<del>$1.36</del> $0.68")[1], 1.36)

    def test_struck_price_with_attributes(self):
        # the regex must also accept <del class="x">
        now, was = fp.split_was('<del class="x">$4.18</del> $2.09')
        self.assertEqual((now, was), (2.09, 4.18))

    def test_blend_is_three_to_one(self):
        self.assertEqual(fp.blended(1.0, 5.0), 2.0)
        self.assertIsNone(fp.blended(None, 5.0))


class Matching(unittest.TestCase):
    def setUp(self):
        fp._aliases = {}

    def test_provider_prefixes_and_dots_collapse(self):
        a = fp.match_key("openrouter", "anthropic/claude-opus-5.5")
        b = fp.match_key("zen", "claude-opus-5-5")
        c = fp.match_key("commandcode", "claude-opus-5-5")
        self.assertEqual(a, b)
        self.assertEqual(b, c)

    def test_free_is_its_own_key(self):
        paid = fp.match_key("openrouter", "minimax/minimax-m2.7")
        free = fp.match_key("openrouter", "minimax/minimax-m2.7:free")
        self.assertNotEqual(paid, free)
        self.assertTrue(free.endswith(":free"))

    def test_free_suffix_on_other_providers(self):
        self.assertEqual(fp.match_key("commandcode", "laguna-s-2-1-free"), "laguna" + "s21" + ":free")

    def test_alias_override_wins(self):
        fp._aliases = {"zen": {"weird-id": "claudeopus55"}}
        self.assertEqual(fp.match_key("zen", "weird-id"), "claudeopus55")


class History(unittest.TestCase):
    def _row(self, id_, inp, out):
        return {"id": id_, "in": inp, "out": out, "cr": None}

    def test_drop_detected_within_window(self):
        t0 = datetime(2026, 10, 12, 9, tzinfo=timezone.utc)
        ts0 = t0.isoformat().replace("+00:00", "Z")
        ts1 = (t0 + timedelta(hours=1)).isoformat().replace("+00:00", "Z")
        hist = {}
        fp.update_history(hist, "zen", [self._row("m", 2.0, 8.0)], ts0)
        fp.update_history(hist, "zen", [self._row("m", 1.0, 4.0)], ts1)
        rows = [self._row("m", 1.0, 4.0)]
        fp.annotate(hist, "zen", rows, ts1)
        self.assertIn("drop", rows[0])
        self.assertEqual(rows[0]["drop"]["pct"], 50)

    def test_no_drop_without_change(self):
        t0 = datetime(2026, 10, 12, 9, tzinfo=timezone.utc)
        ts0 = t0.isoformat().replace("+00:00", "Z")
        ts1 = (t0 + timedelta(hours=1)).isoformat().replace("+00:00", "Z")
        hist = {}
        fp.update_history(hist, "zen", [self._row("m", 2.0, 8.0)], ts0)
        fp.update_history(hist, "zen", [self._row("m", 2.0, 8.0)], ts1)
        rows = [self._row("m", 2.0, 8.0)]
        fp.annotate(hist, "zen", rows, ts1)
        self.assertNotIn("drop", rows[0])


    def test_sub_percent_move_is_not_flagged(self):
        # a 0.3% blended change must not be labelled "0% drop"
        t0 = datetime(2026, 10, 12, 9, tzinfo=timezone.utc)
        ts0 = t0.isoformat().replace("+00:00", "Z")
        ts1 = (t0 + timedelta(hours=1)).isoformat().replace("+00:00", "Z")
        hist = {}
        fp.update_history(hist, "nous", [self._row("m", 0.006, 1.536)], ts0)
        fp.update_history(hist, "nous", [self._row("m", 0.0046, 1.536)], ts1)
        rows = [self._row("m", 0.0046, 1.536)]
        fp.annotate(hist, "nous", rows, ts1)
        self.assertNotIn("drop", rows[0])
        self.assertNotIn("rise", rows[0])

    def test_real_rise_is_flagged_as_rise(self):
        t0 = datetime(2026, 10, 12, 9, tzinfo=timezone.utc)
        ts0 = t0.isoformat().replace("+00:00", "Z")
        ts1 = (t0 + timedelta(hours=1)).isoformat().replace("+00:00", "Z")
        hist = {}
        fp.update_history(hist, "nous", [self._row("m", 0.0057, 1.28)], ts0)
        fp.update_history(hist, "nous", [self._row("m", 0.0057, 1.536)], ts1)
        rows = [self._row("m", 0.0057, 1.536)]
        fp.annotate(hist, "nous", rows, ts1)
        self.assertIn("rise", rows[0])
        self.assertNotIn("drop", rows[0])


if __name__ == "__main__":
    unittest.main()
