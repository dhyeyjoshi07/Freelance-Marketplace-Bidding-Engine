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

  /** Apply a theme immediately (no reflow needed). */
  function applyTheme(id) {
    if (!THEMES.find(t => t.id === id)) id = DEFAULT;
    document.documentElement.setAttribute('data-theme', id);
    try { localStorage.setItem(STORAGE_KEY, id); } catch (_) {}
  }

  // Apply saved (or default) theme as early as possible.
  const saved = (function () {
    try { return localStorage.getItem(STORAGE_KEY); } catch (_) { return null; }
  })();
  applyTheme(saved || DEFAULT);

  /** Build the switcher UI and inject it into the page. */
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
      // Swatch always shows its own colours regardless of active theme
      btn.style.background = t.bg;
      btn.style.color = t.accent;
      // Inner dot in accent colour
      const dot = document.createElement('span');
      dot.className = 'swatch-dot';
      dot.style.background = t.accent;
      btn.appendChild(dot);

      btn.addEventListener('click', () => {
        applyTheme(t.id);
        wrapper.querySelectorAll('.theme-swatch').forEach(s => {
          const isActive = s.dataset.theme === t.id;
          s.classList.toggle('active', isActive);
          s.setAttribute('aria-pressed', isActive ? 'true' : 'false');
        });
      });

      wrapper.appendChild(btn);
    });

    return wrapper;
  }

  document.addEventListener('DOMContentLoaded', () => {
    // Dashboard pages: place before the navbar-user element
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
  });
})();

