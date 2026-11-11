"""CP5: nguồn phải đến từ incident đã đọc, việc sửa câu trả lời vẫn có budget."""
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent import run_agent
from status_tools import StatusTools
from test_lab import FakeProvider, final, tool_call


class SourceValidationTests(unittest.TestCase):
    def test_source_revision_preserves_history_and_usage(self):
        url = StatusTools().get_incident_details('github', 'h02n9572mx9y')['url']
        request = tool_call('details', 'get_incident_details',
                            '{"provider":"github","incident_id":"h02n9572mx9y"}')
        rejected = final('Nguồn: https://www.githubstatus.com/incidents/xr3myzjms51')
        corrected = final('Nguồn đã quan sát: ' + url)
        for index, response in enumerate((request, rejected, corrected), start=1):
            response['usage'] = {'total_tokens': index * 100}
        provider = FakeProvider([request, rejected, corrected])

        result = run_agent('Kiểm tra nguồn incident', provider, StatusTools(), max_steps=3)

        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['answer'], corrected['message']['content'])
        self.assertEqual(result['usage'], [{'total_tokens': 100}, {'total_tokens': 200}, {'total_tokens': 300}])
        history = provider.histories[2]
        self.assertEqual(history[-2], rejected['message'])
        self.assertEqual(history[-1]['role'], 'user')
        self.assertIn(url, history[-1]['content'])
        self.assertEqual(history[3]['tool_call_id'], 'details')
        self.assertEqual(json.loads(history[3]['content'])['url'], url)
        validation = next(item for item in result['trace'] if item['event'] == 'validation_missing_source')
        self.assertEqual(validation['step'], 2)
        self.assertEqual(validation['observed_urls'], [url])
        self.assertEqual(validation['answer'], rejected['message']['content'])

    def test_answer_with_observed_source_needs_no_revision(self):
        url = StatusTools().get_incident_details('cloudflare', 'wp49bp8bqo6c')['url']
        provider = FakeProvider([
            tool_call('details', 'get_incident_details',
                      '{"provider":"cloudflare","incident_id":"wp49bp8bqo6c"}'),
            final('Theo incident: ' + url),
        ])

        result = run_agent('Kiểm tra', provider, StatusTools(), max_steps=2)

        self.assertEqual(result['status'], 'completed')
        self.assertEqual(len(provider.histories), 2)
        self.assertFalse(any(item['event'] == 'validation_missing_source' for item in result['trace']))

    def test_status_source_does_not_replace_observed_incident_source(self):
        provider = FakeProvider([
            tool_call('details', 'get_incident_details',
                      '{"provider":"github","incident_id":"h02n9572mx9y"}'),
            final('Nguồn: https://www.githubstatus.com'),
        ])

        result = run_agent('Kiểm tra', provider, StatusTools(), max_steps=2)

        self.assertEqual(result['status'], 'max_steps')
        self.assertEqual(result['answer'], '')
        self.assertTrue(any(item['event'] == 'validation_missing_source' for item in result['trace']))

    def test_repeated_missing_sources_exhaust_budget_without_completion(self):
        provider = FakeProvider([
            tool_call('details', 'get_incident_details',
                      '{"provider":"github","incident_id":"h02n9572mx9y"}'),
            final('Thiếu nguồn lần 1.'),
            final('Thiếu nguồn lần 2.'),
        ])

        result = run_agent('Kiểm tra', provider, StatusTools(), max_steps=3)

        self.assertEqual(result['status'], 'max_steps')
        self.assertEqual(result['answer'], '')
        self.assertEqual(len(provider.histories), 3)
        validations = [item for item in result['trace'] if item['event'] == 'validation_missing_source']
        self.assertEqual([item['step'] for item in validations], [2, 3])
        self.assertEqual(result['trace'][-1]['event'], 'max_steps')

    def test_status_only_run_does_not_require_incident_url(self):
        provider = FakeProvider([
            tool_call('status', 'get_status', '{"provider":"github"}'),
            final('Chỉ kiểm tra status, không đọc incident.'),
        ])

        result = run_agent('Kiểm tra status', provider, StatusTools(), max_steps=2)

        self.assertEqual(result['status'], 'completed')
        self.assertFalse(any(item['event'] == 'validation_missing_source' for item in result['trace']))

    def test_failed_incident_url_is_not_accepted_as_evidence(self):
        tools = Mock()
        tools.execute.side_effect = [
            {'ok': True, 'url': 'https://status.example/observed'},
            {'ok': False, 'url': 'https://status.example/unverified', 'error': 'TimeoutError'},
        ]
        provider = FakeProvider([
            tool_call('success', 'get_incident_details', '{"provider":"github","incident_id":"one"}'),
            tool_call('failed', 'get_incident_details', '{"provider":"github","incident_id":"two"}'),
            final('Nguồn: https://status.example/unverified'),
        ])

        result = run_agent('Kiểm tra nguồn', provider, tools, max_steps=3)

        self.assertEqual(result['status'], 'max_steps')
        validation = next(item for item in result['trace'] if item['event'] == 'validation_missing_source')
        self.assertEqual(validation['observed_urls'], ['https://status.example/observed'])

    def test_source_state_does_not_leak_between_runs(self):
        first = FakeProvider([
            tool_call('details', 'get_incident_details',
                      '{"provider":"github","incident_id":"h02n9572mx9y"}'),
            final('Chưa có nguồn.'),
        ])
        self.assertEqual(run_agent('Kiểm tra', first, StatusTools(), max_steps=2)['status'], 'max_steps')

        second = FakeProvider([final('Không cần tra cứu incident cho yêu cầu này.')])
        result = run_agent('Yêu cầu khác', second, StatusTools(), max_steps=1)

        self.assertEqual(result['status'], 'completed')
        self.assertFalse(any(item['event'] == 'validation_missing_source' for item in result['trace']))


if __name__ == '__main__':
    unittest.main()
