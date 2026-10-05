/**
 * Centralized API client — wraps fetch() with auth headers and error handling.
 * 
 * All API calls go through this module so that:
 * 1. JWT tokens are automatically attached to every request
 * 2. JSON parsing and error handling are consistent
 * 3. The base URL is configurable in one place
 */

const API_BASE = '/api';

/**
 * Get the stored JWT token from localStorage.
 */
function getToken() {
  return localStorage.getItem('token');
}

/**
 * Build headers with auth token and content type.
 */
function authHeaders() {
  const headers = { 'Content-Type': 'application/json' };
  const token = getToken();
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

/**
 * Generic fetch wrapper with error handling.
 * Returns { ok, data, status, error } for uniform error handling.
 */
async function apiRequest(method, path, body = null) {
  const options = {
    method,
    headers: authHeaders(),
  };
  if (body && method !== 'GET') {
    options.body = JSON.stringify(body);
  }

  try {
    const response = await fetch(`${API_BASE}${path}`, options);
    let data = null;
    
    // Try to parse JSON response
    const text = await response.text();
    if (text) {
      try {
        data = JSON.parse(text);
      } catch {
        data = text;
      }
    }

    if (!response.ok) {
      const errorMsg = data?.detail || `Request failed (${response.status})`;
      return { ok: false, data: null, status: response.status, error: errorMsg };
    }

    return { ok: true, data, status: response.status, error: null };
  } catch (err) {
    return { ok: false, data: null, status: 0, error: 'Network error — is the server running?' };
  }
}

// --- Convenience methods ---

const api = {
  get: (path) => apiRequest('GET', path),
  post: (path, body) => apiRequest('POST', path, body),
  put: (path, body) => apiRequest('PUT', path, body),
  delete: (path) => apiRequest('DELETE', path),
};

// --- Auth API ---

const authAPI = {
  register: (data) => api.post('/auth/register', data),
  login: (data) => api.post('/auth/login', data),
  me: () => api.get('/auth/me'),
};

// --- Projects API ---

const projectsAPI = {
  list: (status = null) => api.get(`/projects${status ? `?status=${status}` : ''}`),
  listAll: () => api.get('/projects?status=open'),
  my: () => api.get('/projects/my'),
  get: (id) => api.get(`/projects/${id}`),
  create: (data) => api.post('/projects', data),
  acceptBid: (projectId, bidId) => api.post(`/projects/${projectId}/accept-bid`, { bid_id: bidId }),
  complete: (projectId) => api.post(`/projects/${projectId}/complete`),
  rate: (projectId, data) => api.post(`/projects/${projectId}/rate`, data),
};

// --- Bids API ---

const bidsAPI = {
  submit: (projectId, data) => api.post(`/projects/${projectId}/bids`, data),
  listRanked: (projectId) => api.get(`/projects/${projectId}/bids`),
  myBids: () => api.get('/freelancers/me/bids'),
};

// --- Freelancers API ---

const freelancersAPI = {
  myProfile: () => api.get('/freelancers/me'),
  updateProfile: (data) => api.put('/freelancers/me', data),
};
