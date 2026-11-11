"""Bound tool retries without hiding attempts or retrying before Retry-After."""
import datetime
from email.utils import parsedate_to_datetime
import math
import time


def retry_after_seconds(result, attempt):
    """Support seconds and HTTP dates; missing/invalid headers use backoff."""
    value = result.get('retry_after_seconds', result.get('retry_after'))
    if value is not None:
        try:
            seconds = float(value)
            if math.isfinite(seconds) and seconds >= 0:
                return seconds
        except (ValueError, TypeError):
            try:
                timestamp = parsedate_to_datetime(str(value))
                if timestamp.tzinfo is None:
                    timestamp = timestamp.replace(tzinfo=datetime.timezone.utc)
                return max(0.0, (timestamp - datetime.datetime.now(datetime.timezone.utc)).total_seconds())
            except (ValueError, TypeError, OverflowError):
                pass
    return float(2 ** (attempt - 1))


class RetryPolicy:
    """Per-run policy: at most three consecutive 429s per tool/provider."""
    def __init__(self, max_attempts=3, wait_budget=10.0):
        self.max_attempts = max_attempts
        self.wait_budget = wait_budget
        self.limits = {}

    def execute(self, tools, name, arguments):
        # Pagination and spelling changes must not bypass an endpoint cooldown.
        key = (name, str(arguments.get('provider', ''))
               if name in ('get_status', 'get_incident_details') else '')
        state = self.limits.get(key)
        waited = 0.0
        if state:
            if state['attempts'] >= self.max_attempts:
                return self._blocked('RETRY_LIMIT_REACHED'), False, waited
            remaining = max(0.0, state['not_before'] - time.monotonic())
            if remaining > self.wait_budget:
                return self._blocked('RETRY_WAIT_BUDGET_EXCEEDED'), False, waited
            if remaining:
                time.sleep(remaining)
                self.wait_budget -= remaining
                waited = remaining

        result = tools.execute(name, arguments)
        if result.get('error') == 'RATE_LIMITED' or result.get('http_status') == 429:
            attempts = (state['attempts'] if state else 0) + 1
            delay = retry_after_seconds(result, attempts)
            self.limits[key] = {
                'attempts': attempts, 'not_before': time.monotonic() + delay,
                'name': name, 'arguments': dict(arguments),
            }
            result = dict(result)
            result['agent_retry'] = {
                'attempt': attempts, 'max_attempts': self.max_attempts,
                'wait_seconds': delay,
                'allowed': attempts < self.max_attempts and delay <= self.wait_budget,
            }
        else:
            self.limits.pop(key, None)
        return result, True, waited

    def pending(self):
        return [
            {'name': state['name'], 'arguments': state['arguments'],
             'reason': 'RATE_LIMITED còn được phép retry; chưa thực hiện lần thử lại này.'}
            for state in self.limits.values()
            if state['attempts'] < self.max_attempts
            and max(0.0, state['not_before'] - time.monotonic()) <= self.wait_budget
        ]

    @staticmethod
    def _blocked(error):
        return {
            'ok': False, 'error': error, 'retriable': False,
            'message': 'Dừng retry tool này trong run; chưa xác nhận được trạng thái. '
                       'Tiếp tục báo cáo các provider khác nếu có dữ liệu.',
        }
