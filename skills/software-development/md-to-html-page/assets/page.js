(function () {
  "use strict";
  var root = document.documentElement;
  var KEY = "md-to-html-page:theme";

  function load() {
    try { return window.localStorage.getItem(KEY); } catch (e) { return null; }
  }
  function save(value) {
    try { window.localStorage.setItem(KEY, value); } catch (e) { return; }
  }
  function systemDark() {
    return !!(window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches);
  }
  function isDark() {
    var t = root.getAttribute("data-theme");
    return t ? t === "dark" : systemDark();
  }

  var saved = load();
  if (saved === "light" || saved === "dark") root.setAttribute("data-theme", saved);
  var toggle = document.querySelector(".theme-toggle");
  if (toggle) {
    toggle.hidden = false;
    toggle.addEventListener("click", function () {
      var next = isDark() ? "light" : "dark";
      root.setAttribute("data-theme", next);
      save(next);
    });
  }

  function fallbackCopy(text) {
    var ta = document.createElement("textarea");
    ta.value = text;
    ta.setAttribute("readonly", "");
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    var ok = false;
    try { ok = document.execCommand("copy"); } catch (e) { ok = false; }
    document.body.removeChild(ta);
    return ok;
  }
  document.querySelectorAll("figure.code .copy").forEach(function (btn) {
    var label = btn.textContent;
    btn.hidden = false;
    function done(ok) {
      btn.textContent = ok ? btn.getAttribute("data-copied") : label;
      setTimeout(function () { btn.textContent = label; }, 1400);
    }
    btn.addEventListener("click", function () {
      var code = btn.closest("figure").querySelector("pre code");
      var text = code ? code.textContent : "";
      if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(text).then(function () { done(true); }, function () { done(fallbackCopy(text)); });
      } else {
        done(fallbackCopy(text));
      }
    });
  });

  var tocDetails = document.querySelector(".toc details");
  if (tocDetails && window.matchMedia && !window.matchMedia("(min-width: 1100px)").matches) tocDetails.open = false;
  var links = Array.prototype.slice.call(document.querySelectorAll(".toc a[href^='#']"));
  var pairs = links.map(function (a) {
    return [a, document.getElementById(decodeURIComponent(a.getAttribute("href").slice(1)))];
  }).filter(function (p) { return p[1]; });
  if (pairs.length) {
    var ticking = false;
    var spy = function () {
      ticking = false;
      var current = null;
      for (var i = 0; i < pairs.length; i++) {
        if (pairs[i][1].getBoundingClientRect().top < window.innerHeight * 0.3) current = pairs[i][0];
      }
      links.forEach(function (a) { a.classList.toggle("active", a === current); });
    };
    window.addEventListener("scroll", function () {
      if (!ticking) { ticking = true; window.requestAnimationFrame(spy); }
    }, { passive: true });
    spy();
  }

  var opened = [];
  window.addEventListener("beforeprint", function () {
    document.querySelectorAll("details:not([open])").forEach(function (d) { d.open = true; opened.push(d); });
  });
  window.addEventListener("afterprint", function () {
    opened.forEach(function (d) { d.open = false; });
    opened = [];
  });
})();
