// Runs in <head> before the page paints: picks day or night from the saved choice, else the
// system setting. Storage can throw in a private window, so the read is guarded.
(function () {
  var t;
  try { t = localStorage.getItem('md2h-theme'); } catch (e) {}
  if (t !== 'dark' && t !== 'light') t = matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  document.documentElement.setAttribute('data-theme', t);
})();
