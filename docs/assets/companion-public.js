/* English-only public pages. Preserve old #fr / #fr-section bookmarks.
 * No storage, cookies, network requests or app behaviour changes.
 */
(function () {
  'use strict';
  document.documentElement.setAttribute('lang', 'en');
  document.documentElement.setAttribute('data-active-lang', 'en');
  function redirectLegacyFragment() {
    var hash = window.location.hash;
    if (!/^#fr(?:-|$)/.test(hash)) return;
    var next = '#en' + hash.slice(3);
    var target = document.getElementById(next.slice(1));
    if (!target) { next = '#en'; target = document.getElementById('en'); }
    window.history.replaceState(null, '', next);
    if (target) target.scrollIntoView();
  }
  window.addEventListener('hashchange', redirectLegacyFragment);
  redirectLegacyFragment();
})();
