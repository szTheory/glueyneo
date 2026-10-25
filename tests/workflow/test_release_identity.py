#!/usr/bin/env python3
"""Exercise draft recovery across a protected workflow repair without retagging."""
import json
import os
import re
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/workflow'))
from release_identity import resolve_identity
from release_state import ReleaseStateError


class ReleaseIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.git('init', '-q')
        self.git('config', 'user.name', 'Release Test')
        self.git('config', 'user.email', 'test@example.invalid')
        self.source = self.commit('0.2.0', 'version')
        self.workflow = self.commit('0.2.0', 'repair')
        self.env = {'GITHUB_SHA': self.workflow}
        self.snapshot = {'status': 'found', 'release': {
            'tag_name': 'v0.2.0', 'draft': True, 'tag_commit': self.source,
            'target_commitish': self.source}}

    def git(self, *args):
        return subprocess.run(['git', *args], cwd=self.repo, check=True,
                              capture_output=True, text=True).stdout.strip()

    def commit(self, version, message):
        (self.repo / '.release-please-manifest.json').write_text(json.dumps({'.': version}))
        self.git('add', '.')
        self.git('commit', '-qm', message, '--allow-empty')
        return self.git('rev-parse', 'HEAD')

    def test_recovery_keeps_original_source_with_newer_workflow(self):
        result = resolve_identity(self.repo, self.snapshot, self.env)
        self.assertEqual(result, {'should_build': 'true', 'commit': self.source,
                                 'version': '0.2.0', 'tag': 'v0.2.0'})
        self.snapshot['release']['target_commitish'] = 'main'
        self.assertEqual(resolve_identity(self.repo, self.snapshot, self.env)['commit'], self.source)

    def test_new_release_requires_workflow_and_tag_to_be_identical(self):
        self.env.update(RELEASE_CREATED='true', RELEASE_TAG='v0.2.0',
                        RELEASE_VERSION='0.2.0', RELEASE_SHA=self.workflow)
        with self.assertRaises(ReleaseStateError):
            resolve_identity(self.repo, self.snapshot, self.env)
        self.snapshot['release'].update(tag_commit=self.workflow, target_commitish=self.workflow)
        self.assertEqual(resolve_identity(self.repo, self.snapshot, self.env)['commit'], self.workflow)
        for key in ('RELEASE_SHA', 'RELEASE_VERSION', 'RELEASE_TAG'):
            with self.subTest(key=key), self.assertRaises(ReleaseStateError):
                resolve_identity(self.repo, self.snapshot, {**self.env, key: 'wrong'})

    def test_absent_and_published_retries_are_noops(self):
        self.assertEqual(resolve_identity(self.repo, {'status': 'absent', 'release': None},
                                          self.env)['should_build'], 'false')
        self.snapshot['release']['draft'] = False
        self.assertEqual(resolve_identity(self.repo, self.snapshot, self.env)['should_build'], 'false')
        with self.assertRaises(ReleaseStateError):
            resolve_identity(self.repo, {'status': 'absent', 'release': None},
                             {**self.env, 'RELEASE_CREATED': 'true'})

    def test_wrong_dispatch_target_version_and_unrelated_commit_reject(self):
        with self.assertRaises(ReleaseStateError):
            resolve_identity(self.repo, self.snapshot, {**self.env, 'DISPATCH_TAG': 'v9.9.9'})
        for field, value in [('tag_name', 'v9.9.9'), ('target_commitish', 'b'*40),
                             ('tag_commit', 'a'*40), ('draft', 'true')]:
            bad = {'status': 'found', 'release': {**self.snapshot['release'], field: value}}
            with self.subTest(field=field), self.assertRaises((ReleaseStateError, ValueError)):
                resolve_identity(self.repo, bad, self.env)
        self.git('checkout', '--orphan', 'unrelated')
        unrelated = self.commit('0.2.0', 'unrelated')
        self.snapshot['release'].update(tag_commit=unrelated, target_commitish=unrelated)
        with self.assertRaises(ReleaseStateError):
            resolve_identity(self.repo, self.snapshot, self.env)
        self.git('checkout', self.workflow)
        future = self.commit('0.3.0', 'new version')
        with self.assertRaises(ReleaseStateError):
            resolve_identity(self.repo, {'status': 'found', 'release': {
                'tag_name':'v0.3.0', 'draft':True, 'tag_commit':self.source,
                'target_commitish':self.source}}, {'GITHUB_SHA':future})

    def test_actual_upload_loop_skips_complete_draft_and_uploads_only_missing_assets(self):
        workflow = (ROOT / '.github/workflows/release.yml').read_text()
        start = workflow.index('          while IFS= read -r asset; do')
        end = workflow.index('      - name: Re-query and require complete staged draft', start)
        loop = '\n'.join(line[10:] for line in workflow[start:end].splitlines())
        calls = self.repo / 'calls'
        binary = self.repo / 'fakebin'
        binary.mkdir()
        gh = binary / 'gh'
        gh.write_text('#!/bin/sh\nprintf "call\n" >> "$CALL_LOG"\nprintf "%s\n" "$@" >> "$CALL_LOG"\n')
        gh.chmod(0o755)
        plan = self.repo / 'build/release-validation.json'
        plan.parent.mkdir()
        environment = {**os.environ, 'PATH': str(binary) + os.pathsep + os.environ['PATH'],
                       'RELEASE_TAG': 'v0.2.0', 'CALL_LOG': str(calls)}
        for missing in ([], ['glueyneo-source-0.2.0.tar.gz', 'release-manifest.json']):
            with self.subTest(missing=missing):
                calls.unlink(missing_ok=True)
                plan.write_text(json.dumps({'missing_assets': missing}))
                result = subprocess.run(['bash', '-euo', 'pipefail', '-c', loop],
                                        cwd=self.repo, env=environment, capture_output=True,
                                        text=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
                actual = calls.read_text().splitlines() if calls.exists() else []
                expected = []
                for name in missing:
                    expected += ['call', 'release', 'upload', 'v0.2.0', 'build/release-assets/' + name]
                self.assertEqual(actual, expected)

    def test_workflow_uses_trusted_helpers_but_builds_and_consumes_tagged_source(self):
        workflow = (ROOT / '.github/workflows/release.yml').read_text()
        for job in ('release-control', 'stage-release', 'publish-release'):
            # Split at the next job, not indented YAML properties.
            section = re.split(r'\n  [a-z][\w-]*:\n', workflow.split('\n  '+job+':\n',1)[1])[0]
            self.assertIn('ref: ${{ github.sha }}', section)
        for job in ('build-release','verify-downloaded-release'):
            section = re.split(r'\n  [a-z][\w-]*:\n', workflow.split('\n  '+job+':\n',1)[1])[0]
            self.assertIn('ref: ${{ needs.release-control.outputs.commit }}', section)
        self.assertIn('tools/workflow/release_identity.py build/release-control/release.json', workflow)
        self.assertIn('manifest_artifact_name: ${{ steps.assemble.outputs.manifest_artifact_name }}', workflow)
        self.assertEqual(workflow.count('name: ${{ needs.stage-release.outputs.manifest_artifact_name }}'), 2)
        self.assertIn('release-identity-manifest-attempt-${GITHUB_RUN_ATTEMPT}', workflow)
        self.assertEqual(workflow.count('release-app-authority-${{ github.job }}-attempt-${{ github.run_attempt }}'), 3)
        helper_checkout = workflow.split('      - name: Check out trusted release packaging helper\n', 1)[1].split('      - name:', 1)[0]
        self.assertIn('ref: ${{ github.sha }}', helper_checkout)
        self.assertIn('path: build/release-tools', helper_checkout)
        self.assertIn('sparse-checkout: tools/release_manifest.py', workflow)
        self.assertIn('python3 build/release-tools/tools/release_manifest.py build --repo . --commit', workflow)
        self.assertIn('python build/release-tools/tools/release_manifest.py build --repo . --commit', workflow)
        ci = (ROOT / '.github/workflows/ci.yml').read_text()
        self.assertIn('Verify Windows release archives and relocated consumers', ci)
        self.assertIn('&& python tools/verify_sdk.py --suite release-consumer', ci)
        self.assertIn('python3 tools/verify_sdk.py --suite release-recovery', ci)


if __name__ == '__main__':
    unittest.main(verbosity=2)
