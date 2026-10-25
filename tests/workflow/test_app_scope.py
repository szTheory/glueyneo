#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Effective App-token scope rejects broader, malformed or mismatched grants."""
from __future__ import annotations

import io
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools/workflow"))
import app_scope

REPOSITORY = "public-example/sdk"
PAYLOAD = {"total_count": 1, "repositories": [{"full_name": REPOSITORY}]}
ENV = {"GH_TOKEN": "synthetic-token", "GITHUB_REPOSITORY": REPOSITORY,
       "GITHUB_SHA": "a" * 40, "GITHUB_RUN_ID": "123", "GITHUB_JOB": "release-control",
       "APP_INSTALLATION_ID": "456"}


class ScopeTests(unittest.TestCase):
    def test_exact_single_repository_passes(self):
        app_scope.validate_scope(PAYLOAD, REPOSITORY)

    def test_broad_mismatched_empty_and_malformed_responses_fail(self):
        for payload in (None, [], {}, {**PAYLOAD, "total_count": True},
                        {**PAYLOAD, "total_count": 2}, {**PAYLOAD, "repositories": []},
                        {"total_count": 1, "repositories": [{"full_name": "private-example/other"}]},
                        {"total_count": 1, "repositories": [PAYLOAD["repositories"][0]] * 2}):
            with self.subTest(payload=payload), self.assertRaises(app_scope.ScopeError) as caught:
                app_scope.validate_scope(payload, REPOSITORY)
            self.assertNotIn("private-example", str(caught.exception))

    def response(self, data):
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = data
        response.geturl.return_value = "https://api.github.com/installation/repositories?per_page=2"
        return response

    def test_observation_is_bound_and_never_records_token(self):
        with mock.patch.object(app_scope, "open_request", return_value=self.response(json.dumps(PAYLOAD).encode())):
            result = app_scope.observe(ENV)
        self.assertEqual(result["source_revision"], ENV["GITHUB_SHA"])
        self.assertEqual(result["repository_count"], 1)
        self.assertNotIn(ENV["GH_TOKEN"], json.dumps(result))
        self.assertIn("not measured", result["lifetime_basis"])

    def test_missing_identity_and_wrong_api_fail_before_authentication(self):
        for env in ({**ENV, "GH_TOKEN": ""}, {**ENV, "GITHUB_SHA": "bad"},
                    {**ENV, "GITHUB_API_URL": "https://private.example"}):
            with self.subTest(env=env), mock.patch.object(app_scope, "open_request") as request:
                with self.assertRaises(app_scope.ScopeError):
                    app_scope.observe(env)
                request.assert_not_called()

    def test_oversize_and_invalid_json_fail(self):
        for data in (b"x" * (app_scope.MAX_RESPONSE_BYTES + 1), b"invalid-json"):
            with mock.patch.object(app_scope, "open_request", return_value=self.response(data)):
                with self.assertRaises(ValueError):
                    app_scope.observe(ENV)

    def test_redirect_handler_refuses_to_forward_authorization(self):
        request = app_scope.urllib.request.Request("https://api.github.com/installation/repositories",
                                                  headers={"Authorization": "Bearer synthetic-token"})
        self.assertIsNone(app_scope.NoRedirect().redirect_request(
            request, None, 302, "redirect", {}, "https://other.example"))


if __name__ == "__main__":
    unittest.main()
