"""Unit tests for order book normalization (deterministic)."""

import unittest
from xrpl_router.orderbooks import Level, offers_to_levels


class TestOrderbooks(unittest.TestCase):
    def test_offers_to_levels_issued(self):
        offers = [
            {
                "TakerGets": {"currency": "EUR", "issuer": "x", "value": "10"},
                "TakerPays": {"currency": "USD", "issuer": "y", "value": "5"},
            },
        ]
        levels = offers_to_levels(
            offers, taker_pays_is_xrp=False, taker_gets_is_xrp=False
        )
        self.assertEqual(len(levels), 1)
        self.assertEqual(levels[0].rate, 2.0)
        self.assertEqual(levels[0].capacity, 5.0)

    def test_offers_to_levels_xrp_drops(self):
        offers = [
            {
                "TakerGets": {"currency": "USD", "issuer": "i", "value": "1"},
                "TakerPays": "1000000",
            },
        ]
        levels = offers_to_levels(
            offers, taker_pays_is_xrp=True, taker_gets_is_xrp=False
        )
        self.assertEqual(len(levels), 1)
        self.assertEqual(levels[0].capacity, 1.0)
        self.assertEqual(levels[0].rate, 1.0)
