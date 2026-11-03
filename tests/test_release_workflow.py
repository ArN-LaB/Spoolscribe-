"""Exercise the actual publication step offline, including pre-release safety."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import textwrap
import unittest
from unittest.mock import patch

from tests.support import ROOT


class ReleasePublicationTests(unittest.TestCase):
    def execute_publication(self, channel, *, corrupt=False, wrong_channel=False, tag='v0.4.0'):
        workflow = (ROOT / '.github/workflows/build.yml').read_text(encoding='utf-8')
        step = workflow.split('- name: Verify uploaded assets and publish\n', 1)[1]
        code = textwrap.dedent(step.split('        run: |\n', 1)[1])
        edits = []
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            assets = root / 'artifacts'
            assets.mkdir()
            for platform in ('windows', 'macos', 'linux'):
                archive = assets / ('SpoolScribe-' + platform + '.zip')
                archive.write_bytes(('validated-' + platform).encode())
                archive.with_name(archive.name + '.sha256').write_text(
                    hashlib.sha256(archive.read_bytes()).hexdigest() + '  ' + archive.name,
                    encoding='utf-8')

            def command(args, **kwargs):
                self.assertEqual(args[:2], ['gh', 'release'])
                self.assertTrue(kwargs['check'])
                if args[2] == 'download':
                    destination = Path(args[args.index('--dir') + 1])
                    for source in assets.iterdir():
                        shutil.copyfile(source, destination / source.name)
                    if corrupt:
                        (destination / 'SpoolScribe-linux.zip').write_bytes(b'changed')
                elif args[2] == 'edit':
                    edits.append(args)
                else:
                    self.fail('Unexpected command: ' + str(args))
                return subprocess.CompletedProcess(args, 0)

            metadata = dict(isDraft=False, tagName=tag,
                            isPrerelease=(channel == 'true') != wrong_channel)
            previous = Path.cwd()
            try:
                os.chdir(root)
                with patch.dict(os.environ, RELEASE_PRERELEASE=channel,
                                GITHUB_REF_NAME=tag, GITHUB_REPOSITORY='ArN-LaB/Spoolscribe-'), \
                     patch('subprocess.run', side_effect=command), \
                     patch('subprocess.check_output', return_value=json.dumps(metadata)):
                    if corrupt or wrong_channel or channel not in ('true', 'false'):
                        with self.assertRaises(AssertionError):
                            exec(compile(code, 'release-publication-step', 'exec'), {})
                    else:
                        exec(compile(code, 'release-publication-step', 'exec'), {})
            finally:
                os.chdir(previous)
        return edits

    def test_pre_release_never_replaces_latest_stable(self):
        edits = self.execute_publication('true')
        self.assertEqual(len(edits), 1)
        self.assertIn('--prerelease=true', edits[0])
        self.assertIn('--latest=false', edits[0])

    def test_stable_channel_keeps_existing_publication_behavior(self):
        edits = self.execute_publication('false')
        self.assertEqual(len(edits), 1)
        self.assertIn('--prerelease=false', edits[0])
        self.assertIn('--latest=true', edits[0])

    def test_downloaded_asset_mismatch_blocks_publication(self):
        self.assertEqual(self.execute_publication('true', corrupt=True), [])

    def test_unknown_channel_blocks_publication(self):
        self.assertEqual(self.execute_publication('unknown'), [])

    def test_wrong_published_channel_is_reported_as_failure(self):
        self.assertEqual(len(self.execute_publication('true', wrong_channel=True)), 1)

    def test_v050_explicitly_uses_pre_release_channel(self):
        workflow=(ROOT/'.github/workflows/build.yml').read_text(encoding='utf-8')
        channel=next(line for line in workflow.splitlines() if 'RELEASE_PRERELEASE:' in line)
        self.assertIn("github.ref_name == 'v0.5.0'",channel)
        self.assertIn("github.ref_name == 'v0.4.0'",channel)
        self.assertIn("contains(github.ref_name, '-')",channel)

    def test_v060_explicitly_preserves_pre_release_and_stable(self):
        workflow = (ROOT / '.github/workflows/build.yml').read_text(encoding='utf-8')
        channel = next(line for line in workflow.splitlines() if 'RELEASE_PRERELEASE:' in line)
        self.assertIn("github.ref_name == 'v0.6.0'", channel)
        edits = self.execute_publication('true', tag='v0.6.0')
        self.assertEqual(len(edits), 1)
        self.assertIn('--prerelease=true', edits[0])
        self.assertIn('--latest=false', edits[0])
