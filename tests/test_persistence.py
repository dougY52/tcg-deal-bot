"""Exercise the same orphan-branch/worktree flow as GitHub Actions, offline."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest


class PersistenceTests(unittest.TestCase):
    def test_bootstrap_and_restore_state_branch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def git(*args, cwd=root):
                return subprocess.check_output(['git', *args], cwd=cwd, stderr=subprocess.DEVNULL, text=True).strip()
            git('init', '--bare', 'remote.git')
            git('init', '-b', 'main', 'repo')
            repo = root / 'repo'
            git('config', 'user.name', 'test', cwd=repo)
            git('config', 'user.email', 'test@example.org', cwd=repo)
            (repo / 'README.md').write_text('project')
            git('add', '.', cwd=repo)
            git('commit', '-m', 'Initial', cwd=repo)
            git('remote', 'add', 'origin', str(root / 'remote.git'), cwd=repo)
            git('push', 'origin', 'main', cwd=repo)
            self.assertEqual(git('ls-remote', '--heads', 'origin', 'refs/heads/bot-state', cwd=repo), '')
            git('worktree', 'add', '--detach', '../tcg-state', 'HEAD', cwd=repo)
            state_dir = root / 'tcg-state'
            git('switch', '--orphan', 'bot-state', cwd=state_dir)
            self.assertFalse((state_dir / 'README.md').exists())
            state = {'version': 1, 'offers': {}}
            (state_dir / 'state.json').write_text(json.dumps(state))
            git('add', 'state.json', cwd=state_dir)
            git('commit', '-m', 'State', cwd=state_dir)
            git('push', 'origin', 'HEAD:refs/heads/bot-state', cwd=state_dir)
            git('fetch', '--no-tags', 'origin', 'refs/heads/bot-state', cwd=repo)
            self.assertEqual(json.loads(git('show', 'FETCH_HEAD:state.json', cwd=repo)), state)
            self.assertEqual(git('branch', '--show-current', cwd=repo), 'main')
            self.assertEqual(git('ls-tree', '--name-only', 'FETCH_HEAD', cwd=repo), 'state.json')
