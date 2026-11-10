/**
 * Auth module — handles login, registration, token storage, and redirects.
 * 
 * Token lifecycle:
 *   register/login → store token + user info in localStorage
 *   logout → clear localStorage → redirect to index.html
 *   page load → check token → redirect if unauthorized
 */

// --- Centralized Security: HTML Sanitizer ---

/**
 * Escape HTML special characters to prevent Cross-Site Scripting (XSS).
 * Handles strings, numbers, null, and undefined cleanly.
 */
function escapeHTML(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

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
    container.setAttribute('role', 'status');
    container.setAttribute('aria-live', 'polite');
    container.setAttribute('aria-atomic', 'true');
    document.body.appendChild(container);
  }

  const icons = {
    success: '✓',
    error: '✕',
    info: 'ℹ',
  };

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.setAttribute('role', type === 'error' ? 'alert' : 'status');

  const iconSpan = document.createElement('span');
  iconSpan.textContent = icons[type] || 'ℹ';
  toast.appendChild(iconSpan);

  const textNode = document.createTextNode(` ${message}`);
  toast.appendChild(textNode);

  container.appendChild(toast);

  // Clean removal: remove from DOM on animation end, with a fallback timer
  const removeToast = () => {
    if (toast.isConnected) {
      toast.remove();
    }
  };

  toast.addEventListener('animationend', (e) => {
    if (e.animationName === 'fadeOut') {
      removeToast();
    }
  });

  setTimeout(removeToast, 4200);
}

// --- UI Helpers ---

/** Generate initials avatar from username */
function avatarInitials(name) {
  if (!name) return '?';
  const parts = name.trim().split(/[_\s-]+/);
  if (parts.length > 1 && parts[0] && parts[1]) {
    return (parts[0][0] + parts[1][0]).toUpperCase();
  }
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
  let html = `<span class="star-display" aria-label="Rating: ${rating} out of ${maxStars}">`;
  for (let i = 1; i <= maxStars; i++) {
    html += i <= Math.round(rating)
      ? '<span class="star-filled" aria-hidden="true">★</span>'
      : '<span class="star-empty" aria-hidden="true">★</span>';
  }
  html += '</span>';
  return html;
}

/** Generate interactive star rating HTML */
function starRatingHTML(name = 'rating') {
  let html = `<div class="star-rating" data-rating="0" data-name="${name}" role="radiogroup" aria-label="Rating selection" tabindex="0">`;
  for (let i = 1; i <= 5; i++) {
    html += `<span class="star" data-value="${i}" role="radio" aria-checked="false" aria-label="${i} star${i > 1 ? 's' : ''}" tabindex="-1">★</span>`;
  }
  html += '</div>';
  return html;
}

/** Initialize interactive star ratings with click and keyboard support */
function initStarRatings() {
  document.querySelectorAll('.star-rating').forEach(container => {
    const stars = Array.from(container.querySelectorAll('.star'));

    function setRating(value) {
      container.dataset.rating = value;
      stars.forEach((s, idx) => {
        const starVal = idx + 1;
        const filled = starVal <= value;
        s.classList.toggle('filled', filled);
        s.setAttribute('aria-checked', starVal === value ? 'true' : 'false');
      });
    }

    stars.forEach(star => {
      star.addEventListener('click', () => {
        setRating(parseInt(star.dataset.value));
      });

      star.addEventListener('mouseenter', () => {
        const value = parseInt(star.dataset.value);
        stars.forEach(s => {
          s.classList.toggle('filled', parseInt(s.dataset.value) <= value);
        });
      });
    });

    container.addEventListener('mouseleave', () => {
      const current = parseInt(container.dataset.rating || '0');
      stars.forEach(s => {
        s.classList.toggle('filled', parseInt(s.dataset.value) <= current);
      });
    });

    // Keyboard navigation (ArrowLeft/ArrowRight, Space/Enter)
    container.addEventListener('keydown', (e) => {
      let current = parseInt(container.dataset.rating || '0');
      if (e.key === 'ArrowRight' || e.key === 'ArrowUp') {
        e.preventDefault();
        setRating(Math.min(5, current + 1));
      } else if (e.key === 'ArrowLeft' || e.key === 'ArrowDown') {
        e.preventDefault();
        setRating(Math.max(1, current - 1));
      } else if (e.key >= '1' && e.key <= '5') {
        setRating(parseInt(e.key));
      }
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
  const safeStatus = escapeHTML(status);
  const clean = safeStatus.replace(/_/g, '-');
  return `<span class="badge badge-${clean}">${safeStatus.replace(/_/g, ' ')}</span>`;
}

/** Build skill chips with optional matching highlights */
function skillChipsHTML(skills, matchedSkills = []) {
  const matchedSet = new Set(matchedSkills.map(s => s.toLowerCase()));
  return skills.map(s => {
    const isMatched = matchedSet.has(s.toLowerCase());
    return `<span class="skill-chip ${isMatched ? 'matched' : ''}">${escapeHTML(s)}</span>`;
  }).join('');
}

/** Build score breakdown bars */
function scoreBreakdownHTML(matchScore, skillOverlap = null, priceScore = null, ratingScore = null) {
  const skill = skillOverlap !== null ? skillOverlap : Math.min(matchScore * 1.2, 1);
  const price = priceScore !== null ? priceScore : Math.min(matchScore * 1.1, 1);
  const rating = ratingScore !== null ? ratingScore : Math.min(matchScore * 0.9, 1);

  return `
    <div class="score-bar-group" role="region" aria-label="Score breakdown">
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

/** Setup tab switching with keyboard navigation */
function initTabs() {
  document.querySelectorAll('.tabs').forEach(tabGroup => {
    tabGroup.setAttribute('role', 'tablist');
    const tabs = Array.from(tabGroup.querySelectorAll('.tab'));

    tabs.forEach((tab, index) => {
      tab.setAttribute('role', 'tab');
      tab.setAttribute('id', `tab-${tab.dataset.tab}`);
      tab.setAttribute('aria-controls', tab.dataset.tab);
      tab.setAttribute('aria-selected', tab.classList.contains('active') ? 'true' : 'false');
      tab.setAttribute('tabindex', tab.classList.contains('active') ? '0' : '-1');

      const panel = document.getElementById(tab.dataset.tab);
      if (panel) {
        panel.setAttribute('role', 'tabpanel');
        panel.setAttribute('aria-labelledby', `tab-${tab.dataset.tab}`);
      }

      tab.addEventListener('click', () => switchTab(tabs, index));

      tab.addEventListener('keydown', (e) => {
        let newIndex = index;
        if (e.key === 'ArrowRight') {
          newIndex = (index + 1) % tabs.length;
        } else if (e.key === 'ArrowLeft') {
          newIndex = (index - 1 + tabs.length) % tabs.length;
        }
        if (newIndex !== index) {
          e.preventDefault();
          switchTab(tabs, newIndex);
          tabs[newIndex].focus();
        }
      });
    });
  });

  function switchTab(tabs, activeIndex) {
    const parent = tabs[0].closest('.tabs').parentElement;
    tabs.forEach((t, i) => {
      const isActive = i === activeIndex;
      t.classList.toggle('active', isActive);
      t.setAttribute('aria-selected', isActive ? 'true' : 'false');
      t.setAttribute('tabindex', isActive ? '0' : '-1');

      const panel = document.getElementById(t.dataset.tab);
      if (panel) {
        panel.classList.toggle('active', isActive);
      }
    });
  }
}

// --- Accessible Modal Management ---

let previouslyFocusedElement = null;

/** Open modal with focus trap and aria management */
function openModal(id) {
  const overlay = document.getElementById(id);
  if (!overlay) return;

  previouslyFocusedElement = document.activeElement;
  overlay.classList.add('active');
  overlay.setAttribute('aria-hidden', 'false');

  // Focus the first focusable element inside the modal
  const focusable = overlay.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
  if (focusable.length > 0) {
    setTimeout(() => focusable[0].focus(), 50);
  }
}

/** Close modal and return focus */
function closeModal(id) {
  const overlay = document.getElementById(id);
  if (!overlay) return;

  overlay.classList.remove('active');
  overlay.setAttribute('aria-hidden', 'true');

  if (previouslyFocusedElement && typeof previouslyFocusedElement.focus === 'function') {
    previouslyFocusedElement.focus();
  }
}

/** Setup modal close buttons, backdrop click, Escape key, and focus trap */
function initModals() {
  document.querySelectorAll('.modal-overlay').forEach(overlay => {
    overlay.setAttribute('aria-hidden', 'true');
    const modalBox = overlay.querySelector('.modal');
    if (modalBox) {
      modalBox.setAttribute('role', 'dialog');
      modalBox.setAttribute('aria-modal', 'true');
    }

    // Close on backdrop click
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) {
        closeModal(overlay.id);
      }
    });

    // Trap focus inside open modal
    overlay.addEventListener('keydown', (e) => {
      if (!overlay.classList.contains('active')) return;

      if (e.key === 'Escape') {
        e.preventDefault();
        closeModal(overlay.id);
        return;
      }

      if (e.key === 'Tab') {
        const focusables = Array.from(
          overlay.querySelectorAll('button:not(:disabled), [href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex]:not([tabindex="-1"])')
        );
        if (focusables.length === 0) return;

        const first = focusables[0];
        const last = focusables[focusables.length - 1];

        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    });
  });

  // Close buttons
  document.querySelectorAll('.modal-close').forEach(btn => {
    btn.setAttribute('aria-label', 'Close dialog');
    btn.addEventListener('click', () => {
      const overlay = btn.closest('.modal-overlay');
      if (overlay) closeModal(overlay.id);
    });
  });
}
