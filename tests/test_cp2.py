"""Kiểm tra lịch sử hội thoại và usage của agent loop CP2."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent import SYSTEM_PROMPT, run_agent
from status_tools import StatusTools
from test_lab import FakeProvider, final, tool_call


class ConversationTests(unittest.TestCase):
    def test_complete_assistant_precedes_all_matching_tool_results(self):
        response = tool_call('github-call', 'get_status', '{"provider":"github"}')
        other = tool_call('cloudflare-call', 'get_status', '{"provider":"cloudflare"}')
        response['calls'] += other['calls']
        response['message']['tool_calls'] += other['message']['tool_calls']
        response['message']['content'] = 'Tôi sẽ kiểm tra cả hai nhà cung cấp.'
        response['message']['refusal'] = None
        provider = FakeProvider([response, final('Đã kiểm tra.')])

        result = run_agent('Kiểm tra GitHub và Cloudflare', provider, StatusTools())

        self.assertEqual(result['status'], 'completed')
        history = provider.histories[1]
        self.assertEqual(history[0], {'role': 'system', 'content': SYSTEM_PROMPT})
        self.assertEqual(history[1]['content'], 'Kiểm tra GitHub và Cloudflare')
        self.assertEqual(history[2], response['message'])
        self.assertEqual(
            [(m['role'], m['tool_call_id'], json.loads(m['content'])['provider'])
             for m in history[3:]],
            [('tool', 'github-call', 'github'), ('tool', 'cloudflare-call', 'cloudflare')],
        )
        tool_events = [event for event in result['trace'] if event['event'] == 'tool']
        self.assertEqual([event['step'] for event in tool_events], [1, 1])

    def test_usage_includes_tool_turn_and_final_turn(self):
        first = tool_call('status-call', 'get_status', '{"provider":"github"}')
        first['usage'] = {'prompt_tokens': 100, 'completion_tokens': 20}
        last = final('Đã kiểm tra.')
        last['usage'] = {'prompt_tokens': 200, 'completion_tokens': 30}
        provider = FakeProvider([first, last])

        result = run_agent('Kiểm tra GitHub', provider, StatusTools(), max_steps=2)

        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['usage'], [first['usage'], last['usage']])
        self.assertEqual(len(provider.histories), 2)


if __name__ == '__main__':
    unittest.main()
