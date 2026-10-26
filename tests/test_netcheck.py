"""'Phone can't connect?': reading Windows' network type and firewall rules, and the fix script."""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from herotv import netcheck  # noqa: E402


def snap(category="Private", rules=(), alias="Ethernet", ip="192.168.1.20"):
    out = json.dumps({"profiles": {"alias": alias, "category": category, "name": "Home"},          # one item: PowerShell gives no list
                      "ips": [{"alias": alias, "ip": ip}, {"alias": "vEthernet (WSL)", "ip": "172.20.0.1"}],
                      "rules": list(rules)})
    return netcheck.snapshot(run=lambda script: out)


def ids(d):
    return [p["id"] for p in d["problems"]]


class NetCheckTests(unittest.TestCase):
    def test_all_good(self):
        d = netcheck.diagnose(True, ["192.168.1.20"], snap(rules=[{"name": "HERO-TV", "action": "Allow", "profile": "Private"}]))
        self.assertEqual(ids(d), [])
        self.assertEqual((d["alias"], d["category"]), ("Ethernet", "Private"))

    def test_cancelled_firewall_question_is_a_block(self):
        rules = [{"name": "HERO-TV", "action": "Block", "profile": "Private"}, {"name": "HERO-TV", "action": "Block", "profile": "Public"}]
        self.assertEqual(ids(netcheck.diagnose(True, ["192.168.1.20"], snap(rules=rules))), ["blocked"])

    def test_no_rule_at_all(self):
        self.assertEqual(ids(netcheck.diagnose(True, ["192.168.1.20"], snap())), ["noallow"])

    def test_public_network(self):
        rules = [{"name": "HERO-TV", "action": "Allow", "profile": "Private"}]
        self.assertEqual(ids(netcheck.diagnose(True, ["192.168.1.20"], snap("Public", rules))), ["public", "noallow"])
        ok = [{"name": "HERO-TV", "action": "Allow", "profile": "Any"}]
        self.assertEqual(ids(netcheck.diagnose(True, ["192.168.1.20"], snap("Public", ok))), [])     # allowed there too: fine

    def test_vpn_address_and_listener_off(self):
        d = netcheck.diagnose(False, ["172.20.0.1"], snap(rules=[{"name": "x", "action": "Allow", "profile": "Any"}]))
        self.assertEqual(ids(d)[:2], ["off", "virtual"])

    def test_outside_windows_only_the_basics(self):
        self.assertIsNone(netcheck.snapshot() if os.name != "nt" else None)
        self.assertEqual(ids(netcheck.diagnose(True, [], None)), ["noaddr"])
        self.assertEqual(netcheck.snapshot(run=lambda s: "not json"), None)

    def test_fix_script(self):
        s = netcheck.fix_script("Ethernet 2")
        self.assertIn("Remove-NetFirewallRule", s)
        self.assertIn("-Action Allow -Profile Private,Domain", s)
        self.assertIn("Set-NetConnectionProfile -InterfaceAlias 'Ethernet 2' -NetworkCategory Private", s)
        self.assertNotIn("Set-NetConnectionProfile", netcheck.fix_script(""))
        self.assertIn("'it''s'", netcheck._ps_quote("it's"))
        got = []
        netcheck.fix("", shell=lambda path, args: got.append((open(path, encoding="utf-8-sig").read(), args)) or True)
        self.assertIn("New-NetFirewallRule", got[0][0])
        self.assertIn("-ExecutionPolicy Bypass", got[0][1])


if __name__ == "__main__":
    unittest.main()
