import http from 'k6/http';
import { check, sleep } from 'k6';

const baseUrl = __ENV.BASE_URL || 'http://localhost:9010';
const token = __ENV.JWT_TOKEN;
const provider = __ENV.CHAT_PROVIDER || 'ollama';
const model = __ENV.CHAT_MODEL || 'llama3.2';

if (!token) {
  throw new Error('JWT_TOKEN is required for loadtest/chat.js');
}

export const options = {
  vus: 5,
  duration: '30s',
  thresholds: {
    http_req_failed: ['rate<0.05'],
    http_req_duration: ['p(95)<3000'],
  },
};

export default function () {
  const payload = JSON.stringify({
    message: 'What do we offer?',
    provider,
    model,
  });

  const res = http.post(`${baseUrl}/chat`, payload, {
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
  });

  check(res, {
    'chat status is 200': (r) => r.status === 200,
  });

  sleep(1);
}
