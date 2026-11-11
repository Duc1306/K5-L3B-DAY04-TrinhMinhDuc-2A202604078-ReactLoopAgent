"""Regression tests for missing investigation steps and unsupported status claims."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent import run_agent
from bonus.tools import BonusTools
from evals.scenarios import ScenarioTools
from status_tools import StatusTools
from test_lab import FakeProvider, final, tool_call


def together(*responses):
    response = responses[0]
    for other in responses[1:]:
        response['calls'] += other['calls']
        response['message']['tool_calls'] += other['message']['tool_calls']
    return response


class InvestigationTests(unittest.TestCase):
    def test_incident_resolved_does_not_replace_current_component_status(self):
        tools = StatusTools()
        url = tools.get_incident_details('github', 't89g2q1800fr')['url']
        provider = FakeProvider([
            tool_call('incident', 'get_incident_details', '{"provider":"github","incident_id":"t89g2q1800fr"}'),
            final('Incident đã resolved. ' + url),
            tool_call('status', 'get_status', '{"provider":"github","component":"Actions"}'),
            final('Actions operational theo snapshot, incident đã resolved. ' + url),
        ])

        result = run_agent('GitHub Actions hiện đang outage vì incident này phải không?', provider, tools, 4)

        self.assertEqual(result['status'], 'completed')
        validation = next(item for item in result['trace'] if item['event'] == 'validation_incomplete_investigation')
        action = validation['actions'][0]
        self.assertEqual(action['name'], 'get_status')
        self.assertEqual(action['arguments'], {'provider': 'github', 'component': 'Actions'})

    def test_related_incident_is_read_before_cause_conclusion(self):
        tools = StatusTools()
        url = tools.get_incident_details('github', 'h02n9572mx9y')['url']
        related = tools.get_incident_details('github', 'xr3myzj7ms51')['url']
        provider = FakeProvider([
            tool_call('first', 'get_incident_details', '{"provider":"github","incident_id":"h02n9572mx9y"}'),
            final('Chưa rõ nguyên nhân. ' + url),
            tool_call('linked', 'get_incident_details', '{"provider":"github","incident_id":"xr3myzj7ms51"}'),
            final('Đã đọc incident liên quan; đoạn cập nhật bị cắt. ' + related),
        ])

        result = run_agent('Đọc incident GitHub, theo liên kết để tìm nguyên nhân.', provider, tools, 4)

        self.assertEqual(result['status'], 'completed')
        validation = next(item for item in result['trace'] if item['event'] == 'validation_incomplete_investigation')
        self.assertEqual(validation['actions'][0]['arguments']['incident_id'], 'xr3myzj7ms51')
        self.assertEqual([item['step'] for item in result['trace'] if item['event'] == 'tool'], [1, 3])

    def test_comparison_requires_details_for_each_provider(self):
        tools = BonusTools()
        vercel = tools.status('vercel', 'Builds')['incidents'][0]['id']
        npm = tools.status('npm', 'publishing')['incidents'][0]['id']
        urls = [tools.get_incident_details(p, incident)['url'] for p, incident in [('vercel', vercel), ('npm', npm)]]
        provider = FakeProvider([
            together(tool_call('vercel-status', 'get_vercel_status', '{"component":"Builds"}'),
                     tool_call('npm-status', 'get_npm_status', '{"component":"publishing"}')),
            final('Hai incident đã resolved; nguồn tổng quan.'),
            together(tool_call('vercel-details', 'get_incident_details', json.dumps({'provider': 'vercel', 'incident_id': vercel, 'limit': 3})),
                     tool_call('npm-details', 'get_incident_details', json.dumps({'provider': 'npm', 'incident_id': npm, 'limit': 3}))),
            final('Phạm vi build và package publishing khác nhau. ' + ' '.join(urls)),
        ])

        result = run_agent('Đối chiếu incident mới nhất Vercel Builds và npm, nêu phạm vi.', provider, tools, 4)

        self.assertEqual(result['status'], 'completed')
        validation = next(item for item in result['trace'] if item['event'] == 'validation_incomplete_investigation')
        self.assertEqual({action['arguments']['provider'] for action in validation['actions']}, {'vercel', 'npm'})

    def test_pending_rate_limit_cannot_be_reported_as_already_retried(self):
        tools = BonusTools(scenario='rate_limit_once')
        provider = FakeProvider([
            tool_call('first', 'get_vercel_status', '{}'),
            final('Vercel chưa có dữ liệu, đã retry rồi.'),
            tool_call('retry', 'get_vercel_status', '{}'),
            final('Đã lấy được snapshot Vercel.'),
        ])

        result = run_agent('Kiểm tra Vercel và retry nếu có thể.', provider, tools, 4)

        self.assertEqual(result['status'], 'completed')
        self.assertEqual(tools.calls[('get_vercel_status', 'vercel')], 2)
        self.assertTrue(any(item['event'] == 'validation_incomplete_investigation' for item in result['trace']))

    def test_timeout_does_not_allow_operational_claim(self):
        provider = FakeProvider([
            tool_call('cloudflare', 'get_status', '{"provider":"cloudflare","component":"Spectrum"}'),
            final('Cloudflare Spectrum đang operational dù không lấy được dữ liệu.'),
            final('Cloudflare Spectrum chưa thể xác nhận operational do timeout.'),
        ])

        result = run_agent('Kiểm tra Cloudflare Spectrum.', provider, ScenarioTools('cloudflare_timeout'), 3)

        self.assertEqual(result['status'], 'completed')
        validation = next(item for item in result['trace'] if item['event'] == 'validation_unsupported_status')
        self.assertEqual(validation['providers'], ['cloudflare'])
        self.assertEqual(provider.histories[2][-2]['role'], 'system')

    def test_failure_disclaimer_does_not_block_other_provider_status(self):
        provider = FakeProvider([
            together(tool_call('github', 'get_status', '{"provider":"github"}'),
                     tool_call('cloudflare', 'get_status', '{"provider":"cloudflare"}')),
            final('Cloudflare chưa xác nhận được, GitHub operational theo snapshot.'),
        ])

        result = run_agent('Kiểm tra GitHub và Cloudflare.', provider, ScenarioTools('cloudflare_timeout'), 2)

        self.assertEqual(result['status'], 'completed')
        self.assertFalse(any(item['event'] == 'validation_unsupported_status' for item in result['trace']))

    def test_explicit_no_tools_request_does_not_create_pending_actions(self):
        provider = FakeProvider([final('Một bài thơ về biển.')])

        result = run_agent('Viết thơ về biển, đừng kiểm tra trạng thái GitHub.', provider, StatusTools(), 1)

        self.assertEqual(result['status'], 'completed')
        self.assertEqual(len(provider.histories), 1)

    def test_all_systems_operational_is_scoped_to_its_provider(self):
        provider = FakeProvider([
            together(tool_call('github', 'get_status', '{"provider":"github"}'),
                     tool_call('cloudflare', 'get_status', '{"provider":"cloudflare"}')),
            final('1. GitHub:\n- All Systems Operational (tất cả hệ thống hoạt động bình thường).\n'
                  '2. Cloudflare:\n- Chưa xác nhận được trạng thái do timeout.'),
        ])

        result = run_agent('Kiểm tra GitHub và Cloudflare.', provider, ScenarioTools('cloudflare_timeout'), 2)

        self.assertEqual(result['status'], 'completed')
        self.assertFalse(any(item['event'] == 'validation_unsupported_status' for item in result['trace']))

    def test_missing_data_disclaimer_is_not_a_positive_status_claim(self):
        provider = FakeProvider([
            tool_call('cloudflare', 'get_status', '{"provider":"cloudflare"}'),
            final('Cloudflare: Thiếu dữ liệu để kết luận operational.'),
        ])

        result = run_agent('Kiểm tra Cloudflare.', provider, ScenarioTools('cloudflare_timeout'), 2)

        self.assertEqual(result['status'], 'completed')
        self.assertFalse(any(item['event'] == 'validation_unsupported_status' for item in result['trace']))


if __name__ == '__main__':
    unittest.main()
