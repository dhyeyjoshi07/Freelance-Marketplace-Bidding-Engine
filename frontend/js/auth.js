/**
 * Auth module — handles login, registration, token storage, and redirects.
 * 
 * Token lifecycle:
 *   register/login → store token + user info in localStorage
 *   logout → clear localStorage → redirect to index.html
 *   page load → check token → redirect if unauthorized
 */

// --- Token Management ---

function saveAuth(data) {
  localStorage.setItem('token', data.access_token);
  localStorage.setItem('role', data.role);
  localStorage.setItem('user_id', data.user_id);
  localStorage.setItem('username', data.username);
}

function clearAuth() {
  localStorage.removeItem('token');
  localStorage.removeItem('role');
  localStorage.removeItem('user_id');
  localStorage.removeItem('username');
}

function getRole() {
  return localStorage.getItem('role');
}

function getUsername() {
  return localStorage.getItem('username');
}

function getUserId() {
  return parseInt(localStorage.getItem('user_id') || '0');
}

function isLoggedIn() {
  return !!localStorage.getItem('token');
}

function logout() {
  clearAuth();
  window.location.href = '/index.html';
}

// --- Page Guards ---

/**
 * Redirect to login if not authenticated, or to the correct dashboard
 * if the user's role doesn't match the current page.
 */
function requireAuth(expectedRole) {
  if (!isLoggedIn()) {
    window.location.href = '/index.html';
    return false;
  }
  if (expectedRole && getRole() !== expectedRole) {
    window.location.href = getRole() === 'client' ? '/client.html' : '/freelancer.html';
    return false;
  }
  return true;
}

/**
 * If already logged in, redirect away from the auth page to the dashboard.
 */
function redirectIfLoggedIn() {
  if (isLoggedIn()) {
    window.location.href = getRole() === 'client' ? '/client.html' : '/freelancer.html';
  }
}

// --- Toast Notifications ---

function showToast(message, type = 'info') {
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    container.className = 'toast-container';
    document.body.appendChild(container);
  }

  const icons = {
    success: '✓',
    error: '✕',
    info: 'ℹ',
  };

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `<span>${icons[type] || 'ℹ'}</span> ${message}`;
  container.appendChild(toast);

  // Auto-remove after animation
  setTimeout(() => toast.remove(), 4000);
}

// --- UI Helpers ---

/** Generate initials avatar from username */
function avatarInitials(name) {
  if (!name) return '?';
  return name.slice(0, 2).toUpperCase();
}

/** Format a date string for display */
function formatDate(dateStr) {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

/** Format currency */
function formatCurrency(amount) {
  return `$${Number(amount).toLocaleString('en-US', { minimumFractionDigits: 0 })}`;
}

/** Generate star display HTML (read-only) */
function starDisplayHTML(rating, maxStars = 5) {
  let html = '<span class="star-display">';
  for (let i = 1; i <= maxStars; i++) {
    html += i <= Math.round(rating)
      ? '<span class="star-filled">★</span>'
      : '<span class="star-empty">★</span>';
  }
  html += '</span>';
  return html;
}

/** Generate interactive star rating HTML */
function starRatingHTML(name = 'rating') {
  let html = `<span class="star-rating" data-rating="0" data-name="${name}">`;
  for (let i = 1; i <= 5; i++) {
    html += `<span class="star" data-value="${i}">★</span>`;
  }
  html += '</span>';
  return html;
}

/** Initialize interactive star ratings (call after rendering) */
function initStarRatings() {
  document.querySelectorAll('.star-rating').forEach(container => {
    container.querySelectorAll('.star').forEach(star => {
      star.addEventListener('click', () => {
        const value = parseInt(star.dataset.value);
        container.dataset.rating = value;
        container.querySelectorAll('.star').forEach(s => {
          s.classList.toggle('filled', parseInt(s.dataset.value) <= value);
        });
      });

      star.addEventListener('mouseenter', () => {
        const value = parseInt(star.dataset.value);
        container.querySelectorAll('.star').forEach(s => {
          s.classList.toggle('filled', parseInt(s.dataset.value) <= value);
        });
      });

      star.addEventListener('mouseleave', () => {
        const current = parseInt(container.dataset.rating);
        container.querySelectorAll('.star').forEach(s => {
          s.classList.toggle('filled', parseInt(s.dataset.value) <= current);
        });
      });
    });
  });
}

/** Get the score category class */
function scoreClass(score) {
  if (score >= 0.7) return 'high';
  if (score >= 0.4) return 'medium';
  return 'low';
}

/** Get rank badge class */
function rankClass(rank) {
  if (rank <= 3) return `rank-${rank}`;
  return 'rank-other';
}

/** Build a status badge */
function statusBadge(status) {
  const clean = status.replace('_', '-');
  return `<span class="badge badge-${clean}">${status.replace('_', ' ')}</span>`;
}

/** Build skill chips with optional matching highlights */
function skillChipsHTML(skills, matchedSkills = []) {
  const matchedSet = new Set(matchedSkills.map(s => s.toLowerCase()));
  return skills.map(s =>
    `<span class="skill-chip ${matchedSet.has(s.toLowerCase()) ? 'matched' : ''}">${s}</span>`
  ).join('');
}

/** Build score breakdown bars */
function scoreBreakdownHTML(matchScore, skillOverlap = null, priceScore = null, ratingScore = null) {
  // Estimate component scores from composite if individual scores aren't available
  const skill = skillOverlap !== null ? skillOverlap : Math.min(matchScore * 1.2, 1);
  const price = priceScore !== null ? priceScore : Math.min(matchScore * 1.1, 1);
  const rating = ratingScore !== null ? ratingScore : Math.min(matchScore * 0.9, 1);

  return `
    <div class="score-bar-group">
      <div class="score-bar">
        <span class="score-bar-label">Skill</span>
        <div class="score-bar-track">
          <div class="score-bar-fill skill" style="width: 0%" data-width="${Math.round(skill * 100)}%"></div>
        </div>
        <span class="score-bar-value">${Math.round(skill * 100)}%</span>
      </div>
      <div class="score-bar">
        <span class="score-bar-label">Rating</span>
        <div class="score-bar-track">
          <div class="score-bar-fill rating" style="width: 0%" data-width="${Math.round(rating * 100)}%"></div>
        </div>
        <span class="score-bar-value">${Math.round(rating * 100)}%</span>
      </div>
      <div class="score-bar">
        <span class="score-bar-label">Price</span>
        <div class="score-bar-track">
          <div class="score-bar-fill price" style="width: 0%" data-width="${Math.round(price * 100)}%"></div>
        </div>
        <span class="score-bar-value">${Math.round(price * 100)}%</span>
      </div>
    </div>
  `;
}

/** Animate score bars (call after rendering) */
function animateScoreBars() {
  setTimeout(() => {
    document.querySelectorAll('.score-bar-fill').forEach(bar => {
      const width = bar.dataset.width;
      if (width) bar.style.width = width;
    });
  }, 100);
}

/** Setup tab switching */
function initTabs() {
  document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
      const group = tab.closest('.tabs').parentElement;
      group.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      group.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
      tab.classList.add('active');
      const target = document.getElementById(tab.dataset.tab);
      if (target) target.classList.add('active');
    });
  });
}

/** Open/close modal */
function openModal(id) {
  document.getElementById(id)?.classList.add('active');
}
function closeModal(id) {
  document.getElementById(id)?.classList.remove('active');
}

/** Setup modal close buttons and overlay click */
function initModals() {
  document.querySelectorAll('.modal-overlay').forEach(overlay => {
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) overlay.classList.remove('active');
    });
  });
  document.querySelectorAll('.modal-close').forEach(btn => {
    btn.addEventListener('click', () => {
      btn.closest('.modal-overlay').classList.remove('active');
    });
  });
}
