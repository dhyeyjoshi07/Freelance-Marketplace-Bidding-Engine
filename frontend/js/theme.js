/**
 * Theme Manager — colour-scheme switcher for BidForge.
 *
 * Loaded in <head> so the saved theme is applied before first paint.
 * Builds the swatch-button switcher once the DOM is ready.
 */

(function () {
  'use strict';

  const THEMES = [
    { id: 'midnight-blue',  name: 'Midnight blue',      accent: '#6FA8FF', bg: '#0B1220' },
    { id: 'deep-teal',      name: 'Deep teal',          accent: '#3FC1C9', bg: '#0A1416' },
    { id: 'aubergine',      name: 'Aubergine',          accent: '#B794F4', bg: '#140F18' },
    { id: 'graphite-sand',  name: 'Graphite and sand',  accent: '#D9C59A', bg: '#111315' },
  ];

  const STORAGE_KEY = 'theme';
  const DEFAULT     = 'deep-teal';

  /** Apply a theme immediately. */
  function applyTheme(id) {
    if (!THEMES.find(t => t.id === id)) id = DEFAULT;
    document.documentElement.setAttribute('data-theme', id);
    if (document.body) document.body.setAttribute('data-theme', id);
    try { localStorage.setItem(STORAGE_KEY, id); } catch (_) {}

    // Update active class on all swatch buttons across the page
    document.querySelectorAll('.theme-swatch').forEach(s => {
      const isActive = s.dataset.theme === id;
      s.classList.toggle('active', isActive);
      s.setAttribute('aria-pressed', isActive ? 'true' : 'false');
    });

    // Dispatch event for any listeners
    window.dispatchEvent(new CustomEvent('themechange', { detail: { theme: id } }));
  }

  // Expose on window for programmatic access / debugging
  window.setTheme = applyTheme;
  window.getTheme = function () {
    return document.documentElement.getAttribute('data-theme') || DEFAULT;
  };

  // Apply saved (or default) theme as early as possible.
  const saved = (function () {
    try { return localStorage.getItem(STORAGE_KEY); } catch (_) { return null; }
  })();
  applyTheme(saved || DEFAULT);

  /** Build the switcher UI element. */
  function buildSwitcher() {
    const current = document.documentElement.getAttribute('data-theme') || DEFAULT;

    const wrapper = document.createElement('div');
    wrapper.className = 'theme-switcher';
    wrapper.setAttribute('role', 'radiogroup');
    wrapper.setAttribute('aria-label', 'Colour theme');

    THEMES.forEach(t => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'theme-swatch' + (t.id === current ? ' active' : '');
      btn.setAttribute('aria-label', t.name);
      btn.setAttribute('aria-pressed', t.id === current ? 'true' : 'false');
      btn.title = t.name;
      btn.dataset.theme = t.id;

      // Swatch displays its theme's background and accent
      btn.style.backgroundColor = t.bg;
      btn.style.color = t.accent;

      const dot = document.createElement('span');
      dot.className = 'swatch-dot';
      dot.style.backgroundColor = t.accent;
      btn.appendChild(dot);

      btn.addEventListener('click', (e) => {
        e.preventDefault();
        applyTheme(t.id);
      });

      wrapper.appendChild(btn);
    });

    return wrapper;
  }

  function mountSwitcher() {
    // Avoid double mounting
    if (document.querySelector('.theme-switcher')) return;

    // Dashboard pages: place before navbar-user
    const navActions = document.querySelector('.navbar-actions');
    const navUser    = document.querySelector('.navbar-user');
    if (navActions && navUser) {
      navActions.insertBefore(buildSwitcher(), navUser);
      return;
    }

    // Auth page: place in top-right corner
    const authPage = document.querySelector('.auth-page');
    if (authPage) {
      const corner = document.createElement('div');
      corner.className = 'theme-switcher-corner';
      corner.appendChild(buildSwitcher());
      authPage.appendChild(corner);
    }
  }

  // Mount when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', mountSwitcher);
  } else {
    mountSwitcher();
  }
})();
