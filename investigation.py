"""Track observable work still needed for an investigation, without case IDs."""
import re
from urllib.parse import urlparse

from bonus.tools import HOSTS


class Investigation:
    def __init__(self, question, schemas):
        question = question.casefold()
        self.status_tools = {}
        self.detail_parameters = None
        for schema in schemas:
            function = schema['function']
            name = function['name']
            properties = function['parameters']['properties']
            if name == 'get_status':
                for provider in properties['provider'].get('enum', []):
                    self.status_tools[provider] = name
            elif name.startswith('get_') and name.endswith('_status'):
                self.status_tools[name[4:-7]] = name
            elif name == 'get_incident_details':
                self.detail_parameters = properties
        self.question = question
        self.requested = {provider for provider in self.status_tools if provider in question}
        forbidden = any(term in question for term in (
            'đừng kiểm tra', 'không kiểm tra', 'không gọi tool', 'do not check', "don't check", 'no tools',
        ))
        current = any(term in question for term in (
            'hiện tại', 'hiện có', 'hiện trạng', 'outage', 'hoạt động', 'current', 'xem status',
            'kiểm tra status', 'tổng hợp status',
        ))
        status = any(term in question for term in ('status', 'trạng thái', 'tình trạng'))
        self.needs_status = not forbidden and (current or (status and 'incident' not in question))
        self.needs_details = not forbidden and 'incident' in question and any(term in question for term in (
            'đối chiếu', 'so sánh', 'phạm vi', 'timeline', 'chi tiết', 'mới nhất', 'nguyên nhân',
            'ảnh hưởng', 'compare', 'scope', 'details', 'latest', 'cause', 'impact',
        ))
        self.follow_links = not forbidden and any(term in question for term in (
            'theo liên kết', 'liên kết của', 'nguyên nhân', 'follow', 'cause',
        ))
        self.status_attempted = set()
        self.status_results = {}
        self.details_attempted = set()
        self.detail_results = {}
        self.links = {}
        self.failed_status = set()

    def observe(self, name, arguments, result):
        provider = arguments.get('provider')
        for candidate, tool_name in self.status_tools.items():
            if name == tool_name and (name != 'get_status' or provider == candidate):
                if result.get('error') != 'INVALID_ARGUMENTS':
                    self.status_attempted.add(candidate)
                if result.get('ok') is False:
                    self.failed_status.add(candidate)
                else:
                    self.failed_status.discard(candidate)
                    self.status_results[candidate] = result
        if name != 'get_incident_details' or not isinstance(provider, str):
            return
        incident_id = arguments.get('incident_id')
        if not isinstance(incident_id, str) or result.get('error') == 'INVALID_ARGUMENTS':
            return
        key = (provider, incident_id)
        self.details_attempted.add(key)
        if not result.get('ok'):
            return
        self.detail_results[key] = result
        if self.follow_links:
            for update in result.get('updates', []):
                for url in re.findall(r'https?://[^\s<>"\']+', update.get('body', '')):
                    parsed = urlparse(url.rstrip('.,);'))
                    target = next((p for p, host in HOSTS.items()
                                   if urlparse(host).hostname == parsed.hostname), None)
                    match = re.fullmatch(r'/incidents/([A-Za-z0-9_-]+)/?', parsed.path)
                    if target in self.status_tools and match:
                        self.links[(target, match[1])] = parsed.geturl()

    def pending(self):
        actions = []
        if self.needs_status:
            for provider in sorted(self.requested - self.status_attempted):
                arguments = {} if self.status_tools[provider] != 'get_status' else {'provider': provider}
                components = [component for (p, _), result in self.detail_results.items() if p == provider
                              for component in result.get('components', []) if isinstance(component, str)]
                component = next((c for c in components if c.casefold() in self.question), None)
                if component:
                    arguments['component'] = component
                actions.append({'name': self.status_tools[provider], 'arguments': arguments,
                                'reason': 'Cần status để xác nhận trạng thái dịch vụ, không suy từ incident resolved.'})
        if self.detail_parameters is not None:
            if self.needs_details:
                visited_providers = {provider for provider, _ in self.details_attempted}
                for provider, result in self.status_results.items():
                    incidents = result.get('incidents', [])
                    if provider not in visited_providers and incidents:
                        incident = next((item for item in incidents if item['id'].casefold() in self.question), incidents[0])
                        actions.append(self._details(provider, incident['id'], 'Cần đọc chi tiết incident, không chỉ danh sách status.'))
            for (provider, incident_id), url in self.links.items():
                if (provider, incident_id) not in self.details_attempted:
                    actions.append(self._details(provider, incident_id, 'Incident đã đọc dẫn tới nguồn liên quan: ' + url))
        return actions

    def _details(self, provider, incident_id, reason):
        arguments = {'provider': provider, 'incident_id': incident_id}
        if 'limit' in self.detail_parameters:
            arguments.update(offset=0, limit=3)
        return {'name': 'get_incident_details', 'arguments': arguments, 'reason': reason}

    def unsupported_status_claims(self, answer):
        """Conservative check for explicit positive/negative status without evidence.

        This is a language heuristic, not a general factuality judge. The model
        still has to explain failures and scope in the final answer.
        """
        problems = set()
        active = set()
        positive = r'\boperational\b|hoạt động bình thường|\boutage\b|sập toàn|mất dịch vụ'
        negation = re.compile(
            r'(?:không|chưa)\s+(?:thể\s+)?(?:xác nhận|khẳng định|kết luận|xác định|nói)'
            r'|chưa biết|chưa rõ|unknown|unconfirmed|cannot confirm|cannot determine'
            r'|thiếu (?:dữ liệu|bằng chứng)|(?:không|chưa) (?:có|đủ) (?:dữ liệu|bằng chứng)', re.I
        )
        for line in answer.casefold().splitlines():
            mentioned = {provider for provider in self.status_tools if provider in line}
            if mentioned:
                active = mentioned
            for match in re.finditer(positive, line):
                # A later assertion after a comma must not inherit an earlier disclaimer.
                prefix = re.split(r'[,;]', line[:match.start()])[-1]
                if negation.search(prefix):
                    continue
                local = {provider for provider in self.status_tools if provider in prefix}
                subjects = local or mentioned or active
                if any(term in line for term in ('cả hai dịch vụ', 'tất cả dịch vụ', 'all services', 'both services')):
                    subjects = subjects | self.failed_status
                problems.update(subjects & self.failed_status)
        return sorted(problems)
