"""Test config and network selection."""

import os
import unittest


class TestConfig(unittest.TestCase):
    def setUp(self):
        self._saved = os.environ.get("XRPL_NETWORK")

    def tearDown(self):
        if self._saved is not None:
            os.environ["XRPL_NETWORK"] = self._saved
        elif "XRPL_NETWORK" in os.environ:
            del os.environ["XRPL_NETWORK"]

    def test_get_json_rpc_url_testnet(self):
        os.environ["XRPL_NETWORK"] = "testnet"
        from xrpl_router.config import get_json_rpc_url, TESTNET_JSON_RPC

        self.assertEqual(get_json_rpc_url(), TESTNET_JSON_RPC)

    def test_get_json_rpc_url_devnet(self):
        os.environ["XRPL_NETWORK"] = "devnet"
        from xrpl_router.config import get_json_rpc_url, DEVNET_JSON_RPC

        self.assertEqual(get_json_rpc_url(), DEVNET_JSON_RPC)
