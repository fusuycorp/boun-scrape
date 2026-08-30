/**
 * Centralized Single-Origin API Client for BOUN Scraper Dashboard
 */

const etagCache = new Map();

const getAuthHeader = () => {
  const token = localStorage.getItem('token');
  return token ? { Authorization: `Bearer ${token}` } : {};
};

export async function apiRequest(endpoint, options = {}) {
  const { method = 'GET', body = null, headers = {}, params = null, signal = null } = options;

  let url = endpoint.startsWith('/api') ? endpoint : `/api/v1${endpoint}`;

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

  const isGet = method.toUpperCase() === 'GET';
  const reqHeaders = {
    ...getAuthHeader(),
    ...headers,
  };

  if (isGet && etagCache.has(url)) {
    const cached = etagCache.get(url);
    if (cached && cached.etag) {
      reqHeaders['If-None-Match'] = cached.etag;
    }
  }

  let reqBody = body;
  if (body && typeof body === 'object' && !(body instanceof FormData) && !(body instanceof URLSearchParams)) {
    reqHeaders['Content-Type'] = 'application/json';
    reqBody = JSON.stringify(body);
  }

  const response = await fetch(url, {
    method,
    headers: reqHeaders,
    body: reqBody,
    signal,
  });

  if (response.status === 401) {
    localStorage.removeItem('token');
    window.dispatchEvent(new CustomEvent('auth:unauthorized'));
    throw new Error('Session expired. Please log in again.');
  }

  if (response.status === 304 && isGet && etagCache.has(url)) {
    return etagCache.get(url).data;
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

  const responseEtag = response.headers.get('ETag');
  const contentType = response.headers.get('content-type');
  let resultData;
  if (contentType && contentType.includes('application/json')) {
    resultData = await response.json();
  } else {
    resultData = await response.text();
  }

  if (isGet && responseEtag) {
    if (etagCache.size > 100) {
      const firstKey = etagCache.keys().next().value;
      etagCache.delete(firstKey);
    }
    etagCache.set(url, { etag: responseEtag, data: resultData });
  }

  return resultData;
}

export const api = {
  // Auth
  login: (username, password) => {
    const body = new URLSearchParams();
    body.append('username', username);
    body.append('password', password);
    return fetch('/api/v1/auth/login', {
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
  getStats: (options = {}) => apiRequest('/stats', options),
  getTerms: (options = {}) => apiRequest('/terms', options),
  getDepartments: (paramsOrOptions = {}, options = {}) => {
    let params = {};
    let signal = options.signal;
    if (paramsOrOptions) {
      if (paramsOrOptions.signal instanceof AbortSignal) {
        signal = signal || paramsOrOptions.signal;
      }
      const { signal: s, ...rest } = paramsOrOptions;
      if (s instanceof AbortSignal) {
        signal = signal || s;
      }
      params = rest;
    }
    return apiRequest('/departments', {
      params: Object.keys(params).length > 0 ? params : undefined,
      signal,
      ...options,
    });
  },

  // Courses Search
  getCourses: (params = {}, options = {}) => {
    const { signal, ...restParams } = typeof params === 'object' && params !== null ? params : {};
    const effectiveSignal = options.signal || signal;
    return apiRequest('/courses', { params: restParams, signal: effectiveSignal, ...options });
  },

  // Feeds
  getDeltas: (params = {}, options = {}) => {
    const { signal, ...restParams } = typeof params === 'object' && params !== null ? params : {};
    const effectiveSignal = options.signal || signal;
    return apiRequest('/feeds/deltas', { params: restParams, signal: effectiveSignal, ...options });
  },

  // Scraper Control
  getScraperConfig: (options = {}) => apiRequest('/scraper/config', options),
  updateScraperConfig: (data, options = {}) => apiRequest('/scraper/config', { method: 'POST', body: data, ...options }),
  startScrape: (payload = {}, options = {}) => apiRequest('/scraper/trigger', { method: 'POST', body: payload, ...options }),
  stopScrape: (options = {}) => apiRequest('/scraper/stop', { method: 'POST', ...options }),
  getScrapeStatus: (options = {}) => apiRequest('/scraper/status', options),
  getScrapeLogs: (clear = false, options = {}) => apiRequest('/scraper/logs', { params: { clear }, ...options }),
  getCoverageSummary: (termOrOptions = {}, options = {}) => {
    let term = null;
    let signal = options.signal;
    if (typeof termOrOptions === 'string') {
      term = termOrOptions;
    } else if (termOrOptions && typeof termOrOptions === 'object') {
      if ('term' in termOrOptions) term = termOrOptions.term;
      if ('signal' in termOrOptions) signal = signal || termOrOptions.signal;
    }
    return apiRequest('/scraper/coverage', {
      params: term ? { term } : undefined,
      signal,
      ...options,
    });
  },
  getScraperCoverage: (termOrOptions = {}, options = {}) => api.getCoverageSummary(termOrOptions, options),
  getMasterCoverage: (options = {}) => apiRequest('/scraper/coverage/master', options),
  getScheduleConfig: (options = {}) => apiRequest('/scraper/schedule', options),
  updateScheduleConfig: (data, options = {}) => apiRequest('/scraper/schedule', { method: 'POST', body: data, ...options }),
  startSchedulerDaemon: (options = {}) => apiRequest('/scraper/start-daemon', { method: 'POST', ...options }),
  stopSchedulerDaemon: (options = {}) => apiRequest('/scraper/stop-daemon', { method: 'POST', ...options }),

  // Quota
  checkQuota: (abbr, code, section, term, options = {}) =>
    apiRequest('/quota', { params: { abbr, code, section, term }, ...options }),
};
