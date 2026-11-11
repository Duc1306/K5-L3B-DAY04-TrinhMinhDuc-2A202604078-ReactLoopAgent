"""CP3: lỗi phải được quan sát hoặc kết thúc run, không làm mất trace."""
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent import run_agent
from status_tools import StatusTools
from test_lab import FakeProvider, final, tool_call


class ErrorHandlingTests(unittest.TestCase):
    def test_invalid_arguments_are_observations_and_can_be_corrected(self):
        for raw in ('{', '[]', 'null', '"github"', '1'):
            with self.subTest(arguments=raw):
                tools = Mock(wraps=StatusTools())
                provider = FakeProvider([
                    tool_call('bad-call', 'get_status', raw),
                    tool_call('retry-call', 'get_status', '{"provider":"github"}'),
                    final('Đã kiểm tra sau khi sửa arguments.'),
                ])

                result = run_agent('Kiểm tra GitHub', provider, tools)

                self.assertEqual(result['status'], 'completed')
                tools.execute.assert_called_once_with('get_status', {'provider': 'github'})
                returned = provider.histories[1][-1]
                self.assertEqual(returned['tool_call_id'], 'bad-call')
                self.assertEqual(json.loads(returned['content'])['error'], 'INVALID_ARGUMENTS')
                events = [item for item in result['trace'] if item['event'] == 'tool']
                self.assertEqual(events[0]['raw_arguments'], raw)
                self.assertEqual(events[0]['tool_call_id'], 'bad-call')
                self.assertEqual(events[1]['result']['provider'], 'github')

    def test_registry_errors_are_returned_to_model_and_recorded(self):
        cases = [
            ('missing', '{}', StatusTools(), 'UNKNOWN_TOOL'),
            ('get_status', '{"provider":"invalid"}', StatusTools(), 'ValueError'),
            ('get_status', '{"provider":"github"}', StatusTools(fail=True), 'TimeoutError'),
        ]
        for name, raw, tools, expected_error in cases:
            with self.subTest(error=expected_error):
                provider = FakeProvider([
                    tool_call('failed-call', name, raw),
                    final('Không đủ dữ liệu để xác nhận trạng thái.'),
                ])

                result = run_agent('Kiểm tra', provider, tools)

                self.assertEqual(result['status'], 'completed')
                returned = provider.histories[1][-1]
                observation = json.loads(returned['content'])
                self.assertEqual(returned['tool_call_id'], 'failed-call')
                self.assertFalse(observation['ok'])
                self.assertEqual(observation['error'], expected_error)
                event = next(item for item in result['trace'] if item['event'] == 'tool')
                self.assertEqual(event['result'], observation)
                self.assertTrue({'event', 'step', 'name', 'arguments', 'result'} <= event.keys())

    def test_tool_exception_does_not_skip_remaining_calls(self):
        first = tool_call('failed-call', 'get_status', '{"provider":"github"}')
        second = tool_call('good-call', 'get_status', '{"provider":"cloudflare"}')
        first['calls'] += second['calls']
        first['message']['tool_calls'] += second['message']['tool_calls']
        successful = StatusTools().get_status('cloudflare')
        tools = Mock()
        tools.execute.side_effect = [RuntimeError('Tool execution failed.'), successful]
        provider = FakeProvider([first, final('Chỉ kiểm tra được Cloudflare.')])

        result = run_agent('Kiểm tra cả hai provider', provider, tools)

        self.assertEqual(result['status'], 'completed')
        self.assertEqual(tools.execute.call_count, 2)
        returned = provider.histories[1][-2:]
        self.assertEqual([item['tool_call_id'] for item in returned], ['failed-call', 'good-call'])
        self.assertEqual(json.loads(returned[0]['content'])['error'], 'RuntimeError')
        self.assertEqual(json.loads(returned[1]['content']), successful)
        events = [item for item in result['trace'] if item['event'] == 'tool']
        self.assertEqual([item['step'] for item in events], [1, 1])
        self.assertEqual([item['tool_call_id'] for item in events], ['failed-call', 'good-call'])

    def test_provider_exceptions_end_run_without_executing_tools(self):
        for exception in (RuntimeError('HTTP 401'), TimeoutError('timeout'), KeyError('choices')):
            with self.subTest(error=type(exception).__name__):
                provider = Mock()
                provider.complete.side_effect = exception
                tools = Mock()

                result = run_agent('Kiểm tra', provider, tools)

                self.assertEqual(result['status'], 'error')
                self.assertEqual(result['answer'], '')
                self.assertEqual(result['usage'], [])
                self.assertIn(type(exception).__name__, result['error'])
                self.assertEqual(result['trace'][-1]['event'], 'provider_error')
                self.assertEqual(result['trace'][-1]['step'], 1)
                self.assertEqual(provider.complete.call_count, 1)
                tools.execute.assert_not_called()

    def test_provider_failure_keeps_previous_trace_and_usage(self):
        first = tool_call('status-call', 'get_status', '{"provider":"github"}')
        first['usage'] = {'total_tokens': 100}
        provider = Mock()
        provider.complete.side_effect = [first, RuntimeError('HTTP 429')]

        result = run_agent('Kiểm tra', provider, StatusTools())

        self.assertEqual(result['status'], 'error')
        self.assertEqual(result['usage'], [{'total_tokens': 100}])
        self.assertEqual([item['event'] for item in result['trace']], ['model', 'tool', 'provider_error'])
        self.assertEqual(result['trace'][-1]['step'], 2)
        self.assertEqual(provider.complete.call_count, 2)

    def test_truncated_tool_call_is_not_executed_or_completed(self):
        response = tool_call('partial-call', 'get_status', '{"provider":"github"}')
        response['finish'] = 'length'
        response['usage'] = {'total_tokens': 50}
        provider = FakeProvider([response])
        tools = Mock()

        result = run_agent('Kiểm tra', provider, tools)

        self.assertEqual(result['status'], 'error')
        self.assertEqual(result['answer'], '')
        self.assertEqual(result['usage'], [{'total_tokens': 50}])
        self.assertEqual(result['trace'][-1]['event'], 'model_error')
        self.assertEqual(result['trace'][-1]['finish'], 'length')
        tools.execute.assert_not_called()
        self.assertEqual(len(provider.histories), 1)

    def test_unexpected_finish_or_missing_calls_is_an_error(self):
        for finish in ('content_filter', None, 'tool_calls'):
            with self.subTest(finish=finish):
                response = final('Chưa phải câu trả lời hoàn chỉnh.')
                response['finish'] = finish

                result = run_agent('Kiểm tra', FakeProvider([response]), StatusTools())

                self.assertEqual(result['status'], 'error')
                self.assertEqual(result['trace'][-1]['event'], 'model_error')
                self.assertEqual(result['trace'][-1]['finish'], finish)

    def test_max_steps_bounds_calls_and_records_exhaustion(self):
        provider = FakeProvider([
            tool_call(f'call-{step}', 'get_status', '{"provider":"github"}')
            for step in range(1, 4)
        ])

        result = run_agent('Kiểm tra', provider, StatusTools(), max_steps=3)

        self.assertEqual(result['status'], 'max_steps')
        self.assertEqual(result['answer'], '')
        self.assertEqual(len(provider.histories), 3)
        self.assertEqual(len(result['usage']), 3)
        events = [item for item in result['trace'] if item['event'] == 'tool']
        self.assertEqual([item['step'] for item in events], [1, 2, 3])
        self.assertEqual(result['trace'][-1], {'event': 'max_steps', 'step': 3, 'max_steps': 3})


if __name__ == '__main__':
    unittest.main()
