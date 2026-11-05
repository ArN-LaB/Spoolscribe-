/* SpoolScribe Companion public pages: English/French display only.
 *
 * - Language from the address fragment: #en, #fr, or a section id that
 *   starts with "en-" / "fr-" (for example #fr-contact). Otherwise the
 *   first English or French entry of the browser preferences, else English.
 * - Choosing a language keeps the current section: #en-contact <-> #fr-contact.
 * - Support/Privacy links keep the chosen language (#en / #fr).
 * - Nothing is stored (no cookie, no localStorage) and nothing is requested
 *   from the network. Without this script both languages stay readable.
 */
(function () {
  'use strict';

  var root = document.documentElement;
  var current = null;

  function langOfHash(hash) {
    var match = /^#(en|fr)(?:-[a-z0-9-]+)?$/.exec(hash || '');
    return match ? match[1] : null;
  }

  function browserLang() {
    var list = navigator.languages && navigator.languages.length
      ? navigator.languages
      : [navigator.language || ''];
    for (var i = 0; i < list.length; i++) {
      var code = String(list[i]).toLowerCase().slice(0, 2);
      if (code === 'en' || code === 'fr') return code;
    }
    return 'en';
  }

  function each(selector, fn) {
    Array.prototype.forEach.call(document.querySelectorAll(selector), fn);
  }

  function apply(lang) {
    current = lang;
    root.setAttribute('data-active-lang', lang);
    root.setAttribute('lang', lang);
    var title = root.getAttribute('data-title-' + lang);
    if (title) document.title = title;
    each('[data-lang-switch]', function (link) {
      if (link.getAttribute('data-lang-switch') === lang) {
        link.setAttribute('aria-current', 'true');
      } else {
        link.removeAttribute('aria-current');
      }
    });
    each('a[data-keep-lang]', function (link) {
      var base = link.getAttribute('href').split('#')[0];
      link.setAttribute('href', base + '#' + lang);
    });
  }

  function reveal(hash) {
    var id = hash ? hash.slice(1) : '';
    var target = id ? document.getElementById(id) : null;
    if (target) target.scrollIntoView();
  }

  each('[data-lang-switch]', function (link) {
    link.addEventListener('click', function (event) {
      var lang = link.getAttribute('data-lang-switch');
      var hash = window.location.hash;
      var targetId = lang;
      var hashLang = langOfHash(hash);
      if (hashLang && hash.length > 3) {
        var counterpart = lang + hash.slice(3);
        if (document.getElementById(counterpart)) targetId = counterpart;
      }
      event.preventDefault();
      apply(lang);
      if (window.location.hash === '#' + targetId) {
        reveal('#' + targetId);
      } else {
        window.location.hash = targetId;
      }
    });
  });

  window.addEventListener('hashchange', function () {
    var lang = langOfHash(window.location.hash);
    if (lang && lang !== current) {
      apply(lang);
      reveal(window.location.hash);
    }
  });

  var initial = langOfHash(window.location.hash);
  apply(initial || browserLang());
  if (initial) reveal(window.location.hash);
})();
