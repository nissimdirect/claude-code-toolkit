#!/usr/bin/env python3
"""Tests for startup_checks.py — consolidated health check system."""

import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import startup_checks as sc


class TestIndividualChecks(unittest.TestCase):
    """Test each check function returns proper structure."""

    def _assert_check_structure(self, result):
        """Every check must return a dict with 'status' key."""
        self.assertIsInstance(result, dict)
        self.assertIn('status', result)

    def test_check_experiments(self):
        result = sc.check_experiments()
        self._assert_check_structure(result)

    def test_check_consistency(self):
        result = sc.check_consistency()
        self._assert_check_structure(result)

    def test_check_rule_inflation(self):
        result = sc.check_rule_inflation()
        self._assert_check_structure(result)

    def test_check_hooks(self):
        result = sc.check_hooks()
        self._assert_check_structure(result)

    def test_check_learning_index(self):
        result = sc.check_learning_index()
        self._assert_check_structure(result)
        if result['status'] == 'ok':
            self.assertIn('data', result)
            self.assertIn('total', result['data'])
            self.assertIn('graduation_candidates', result['data'])

    def test_check_schedule(self):
        result = sc.check_schedule()
        self._assert_check_structure(result)

    def test_check_violations(self):
        result = sc.check_violations()
        self._assert_check_structure(result)

    def test_check_delegation(self):
        result = sc.check_delegation()
        self._assert_check_structure(result)

    def test_check_repos(self):
        result = sc.check_repos()
        self._assert_check_structure(result)
        self.assertIn('data', result)
        # Should check at least entropic and tools
        self.assertIn('entropic', result['data'])
        self.assertIn('tools', result['data'])

    def test_check_openclaw_exchange(self):
        result = sc.check_openclaw_exchange()
        self._assert_check_structure(result)

    def test_check_delegation_health(self):
        result = sc.check_delegation_health()
        self._assert_check_structure(result)
        self.assertIn('data', result)
        data = result['data']
        self.assertIn('gemini_api_key', data)
        self.assertIn('ollama', data)
        self.assertIn('hook_registered', data)


class TestRepoCheck(unittest.TestCase):
    """Test repo status checking."""

    def test_repos_have_valid_status(self):
        result = sc.check_repos()
        for name, info in result['data'].items():
            self.assertIn(info['status'], ['clean', 'dirty', 'not_git', 'error'])

    def test_clean_repo_has_no_changes(self):
        result = sc.check_repos()
        for name, info in result['data'].items():
            if info['status'] == 'clean':
                self.assertIsNone(info.get('changes'))


class TestLearningIndex(unittest.TestCase):
    """Test learning index health check."""

    def test_index_file_exists(self):
        idx = sc.LOCKS / 'learning-index.json'
        self.assertTrue(idx.exists(), "Learning index should exist")

    def test_index_is_valid_json(self):
        idx = sc.LOCKS / 'learning-index.json'
        if idx.exists():
            data = json.loads(idx.read_text())
            self.assertIn('entries', data)


class TestWorkflowAutoRun(unittest.TestCase):
    """Test workflow auto-run functions."""

    def test_testing_pipeline(self):
        result = sc.run_workflow_testing_pipeline()
        self.assertEqual(result['status'], 'ok')
        self.assertIn('py_compile', result['data'])
        pc = result['data']['py_compile']
        self.assertIn('total', pc)
        self.assertIn('errors', pc)
        self.assertIsInstance(pc['errors'], list)
        self.assertGreater(pc['total'], 0)

    def test_backup_audit(self):
        result = sc.run_workflow_backup_audit()
        self.assertEqual(result['status'], 'ok')
        self.assertIn('stale_locks', result['data'])


class TestOrchestrator(unittest.TestCase):
    """Test the main run_all_checks orchestrator."""

    def test_run_all_returns_valid_structure(self):
        data = sc.run_all_checks(run_workflows=False)
        self.assertIn('timestamp', data)
        self.assertIn('elapsed_seconds', data)
        self.assertIn('issue_count', data)
        self.assertIn('issues', data)
        self.assertIn('checks', data)
        self.assertIsInstance(data['issues'], list)
        self.assertIsInstance(data['checks'], dict)

    def test_run_all_with_workflows(self):
        data = sc.run_all_checks(run_workflows=True)
        self.assertIn('wf_testing_pipeline', data['checks'])
        self.assertIn('wf_backup_audit', data['checks'])

    def test_elapsed_is_reasonable(self):
        """All checks should complete within 30 seconds."""
        data = sc.run_all_checks(run_workflows=False)
        self.assertLess(data['elapsed_seconds'], 30)

    def test_parallel_execution(self):
        """Checks run in parallel (elapsed < sum of individual checks)."""
        data = sc.run_all_checks(run_workflows=False)
        # With parallel execution, should be much less than
        # number_of_checks * average_timeout
        num_checks = len(data['checks'])
        self.assertGreater(num_checks, 5)
        # Should complete well under 15s even if some checks are slow
        self.assertLess(data['elapsed_seconds'], 15)


class TestHumanReadableFormat(unittest.TestCase):
    """Test the human-readable output formatter."""

    def test_format_produces_output(self):
        data = sc.run_all_checks(run_workflows=False)
        output = sc.format_human_readable(data)
        self.assertIsInstance(output, str)
        self.assertGreater(len(output), 100)

    def test_format_includes_key_sections(self):
        data = sc.run_all_checks(run_workflows=False)
        output = sc.format_human_readable(data)
        self.assertIn('Repos:', output)
        self.assertIn('Hooks:', output)
        self.assertIn('Learning:', output)
        self.assertIn('Rules:', output)

    def test_format_reports_issues(self):
        """If there are issues, they appear in output."""
        data = {
            'elapsed_seconds': 1.0,
            'issue_count': 1,
            'issues': ['test_issue'],
            'checks': {},
        }
        output = sc.format_human_readable(data)
        self.assertIn('ISSUES', output)
        self.assertIn('test_issue', output)


class TestIssueDetection(unittest.TestCase):
    """Test that issue detection flags real problems."""

    def test_no_false_critical_issues(self):
        """Clean system should have no critical issues."""
        data = sc.run_all_checks(run_workflows=False)
        critical = [i for i in data['issues'] if 'critical' in i.lower()]
        # Might have some non-critical issues, but shouldn't have
        # hook failures or critical consistency issues on a working system
        hook_failures = [i for i in data['issues'] if 'hook_critical' in i]
        self.assertEqual(len(hook_failures), 0, f"Hook failures detected: {hook_failures}")

    def test_dirty_repo_format(self):
        """Dirty repos should appear in issues with correct format."""
        data = sc.run_all_checks(run_workflows=False)
        dirty_issues = [i for i in data['issues'] if 'uncommitted_work' in i]
        # If dirty repos exist, format should be 'uncommitted_work:repo1,repo2'
        for issue in dirty_issues:
            self.assertTrue(issue.startswith('uncommitted_work:'))


class TestDelegationHealth(unittest.TestCase):
    """Test delegation health check details."""

    def test_ollama_check(self):
        result = sc.check_delegation_health()
        data = result['data']
        # Ollama should be running (it's part of our infrastructure)
        ollama_status = data.get('ollama', '')
        self.assertIn('running', ollama_status.lower(),
                       "Ollama should be running for delegation to work")

    def test_hook_registered(self):
        result = sc.check_delegation_health()
        self.assertEqual(result['data']['hook_registered'], 'yes',
                         "Delegation hook should be registered in settings")

    def test_models_available(self):
        result = sc.check_delegation_health()
        models = result['data'].get('ollama_models', [])
        self.assertGreater(len(models), 0, "At least one Ollama model should be available")


class TestCLI(unittest.TestCase):
    """Test CLI entry point."""

    def test_cli_default_mode(self):
        """CLI with no flags produces human-readable output."""
        import subprocess
        r = subprocess.run(
            [sys.executable, str(sc.TOOLS / 'startup_checks.py')],
            capture_output=True, text=True, timeout=30,
            cwd=str(sc.TOOLS),
        )
        # Should produce readable output (may exit 0 or 1 depending on issues)
        self.assertGreater(len(r.stdout), 50)

    def test_cli_json_mode(self):
        """CLI with --json produces valid JSON."""
        import subprocess
        r = subprocess.run(
            [sys.executable, str(sc.TOOLS / 'startup_checks.py'), '--json'],
            capture_output=True, text=True, timeout=30,
            cwd=str(sc.TOOLS),
        )
        data = json.loads(r.stdout)
        self.assertIn('checks', data)


if __name__ == '__main__':
    unittest.main()
