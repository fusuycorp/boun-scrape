/**
 * Centralized Single-Origin API Client for BOUN Scraper Dashboard
 */

const getAuthHeader = () => {
  const token = localStorage.getItem('token');
  return token ? { Authorization: `Bearer ${token}` } : {};
};

export async function apiRequest(endpoint, options = {}) {
  const { method = 'GET', body = null, headers = {}, params = null } = options;

  let url = endpoint.startsWith('/api') ? endpoint : `/api${endpoint}`;

  if (params) {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, val]) => {
      if (val !== undefined && val !== null && val !== '') {
        searchParams.append(key, val);
      }
    });
    const queryString = searchParams.toString();
    if (queryString) {
      url += (url.includes('?') ? '&' : '?') + queryString;
    }
  }

  const reqHeaders = {
    ...getAuthHeader(),
    ...headers,
  };

  let reqBody = body;
  if (body && typeof body === 'object' && !(body instanceof FormData) && !(body instanceof URLSearchParams)) {
    reqHeaders['Content-Type'] = 'application/json';
    reqBody = JSON.stringify(body);
  }

  const response = await fetch(url, {
    method,
    headers: reqHeaders,
    body: reqBody,
  });

  if (response.status === 401) {
    localStorage.removeItem('token');
    if (!window.location.pathname.includes('/login')) {
      window.location.href = '/login';
    }
    throw new Error('Session expired. Please log in again.');
  }

  if (!response.ok) {
    let errMessage = `HTTP Error ${response.status}`;
    try {
      const errData = await response.json();
      if (errData && errData.detail) {
        errMessage = typeof errData.detail === 'string' ? errData.detail : JSON.stringify(errData.detail);
      }
    } catch {
      // Ignore JSON parse errors for non-JSON error responses
    }
    throw new Error(errMessage);
  }

  const contentType = response.headers.get('content-type');
  if (contentType && contentType.includes('application/json')) {
    return await response.json();
  }

  return await response.text();
}

export const api = {
  // Auth
  login: (username, password) => {
    const body = new URLSearchParams();
    body.append('username', username);
    body.append('password', password);
    return fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body,
    }).then(async (res) => {
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || 'Authentication failed');
      }
      return res.json();
    });
  },
  getMe: () => apiRequest('/auth/me'),

  // Stats & Lookups
  getStats: () => apiRequest('/stats'),
  getTerms: () => apiRequest('/terms'),
  getDepartments: () => apiRequest('/departments'),
  getAllDepartments: () => apiRequest('/departments/all'),

  // Courses Search
  getCourses: (params) => apiRequest('/courses', { params }),

  // Scraper Control
  getScraperConfig: () => apiRequest('/config'),
  updateScraperConfig: (data) => apiRequest('/config', { method: 'POST', body: data }),
  startScrape: () => apiRequest('/scrape/start', { method: 'POST' }),
  stopScrape: () => apiRequest('/scrape/stop', { method: 'POST' }),
  getScrapeStatus: () => apiRequest('/scrape/status'),
  getScrapeTerms: () => apiRequest('/scrape/terms'),
  getScrapeLogs: (clear = false) => apiRequest('/scrape/logs', { params: { clear } }),

  // Quota
  checkQuota: (abbr, code, section, donem) =>
    apiRequest('/quota/check', { params: { abbr, code, section, donem } }),
};
