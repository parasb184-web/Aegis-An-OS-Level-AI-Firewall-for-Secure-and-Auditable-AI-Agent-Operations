import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import db


class TestPolicyMatching(unittest.TestCase):
    def setUp(self):
        self.sample_policies = [
            ("/home/*/.ssh/*", "high", "block", "SSH private keys"),
            ("/home/*/.aws/*", "high", "block", "cloud credentials"),
            ("*/.env", "high", "block", "environment secrets"),
            ("/home/*/.gnupg/*", "high", "block", "GPG keys"),
            ("/home/*/project/*", "low", "allow", "the agent workspace"),
        ]

    def test_block_ssh_keys(self):
        action, note = db.check(self.sample_policies, "/home/user/.ssh/id_rsa")
        self.assertEqual(action, "block")
        self.assertEqual(note, "SSH private keys")

    def test_block_aws_credentials(self):
        action, note = db.check(self.sample_policies, "/home/user/.aws/credentials")
        self.assertEqual(action, "block")
        self.assertEqual(note, "cloud credentials")

    def test_block_dot_env(self):
        action, note = db.check(self.sample_policies, "/home/user/project/.env")
        self.assertEqual(action, "block")
        self.assertEqual(note, "environment secrets")

    def test_allow_project_workspace(self):
        action, note = db.check(self.sample_policies, "/home/user/project/src/app.py")
        self.assertEqual(action, "allow")
        self.assertEqual(note, "the agent workspace")

    def test_no_rule_match(self):
        action, note = db.check(self.sample_policies, "/var/log/syslog")
        self.assertIsNone(action)
        self.assertIsNone(note)

    def test_block_precedence_over_allow(self):
        policies_with_overlap = [
            ("/home/*/project/.env", "high", "block", "nested secret"),
            ("/home/*/project/*", "low", "allow", "workspace"),
        ]
        action, note = db.check(policies_with_overlap, "/home/dev/project/.env")
        self.assertEqual(action, "block")
        self.assertEqual(note, "nested secret")


if __name__ == "__main__":
    unittest.main()

