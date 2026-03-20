import http from 'k6/http';
import { check, sleep } from 'k6';

const baseUrl = __ENV.BASE_URL || 'http://localhost:9010';
const username = __ENV.AUTH_USERNAME || 'admin';
const password = __ENV.AUTH_PASSWORD || 'change-me-immediately';

export const options = {
  vus: 10,
  duration: '30s',
  thresholds: {
    http_req_failed: ['rate<0.01'],
    http_req_duration: ['p(95)<1000'],
  },
};

export default function () {
  const payload = JSON.stringify({
    username,
    password,
  });

  const res = http.post(`${baseUrl}/auth/token`, payload, {
    headers: {
      'Content-Type': 'application/json',
    },
  });

  check(res, {
    'auth status is 200': (r) => r.status === 200,
    'auth returns access token': (r) => !!r.json('access_token'),
  });

  sleep(1);
}
