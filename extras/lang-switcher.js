// Language switcher: renders a row of tabs (one per configured language) that
// rewrites the current URL to point at the same page in another edition.
//
// URL mapping rules (from mkdocs.yml → extra.languages):
//   zh: book/chapter1.md       (default, no suffix)
//   en: book-en/chapter1.md
//   ta: book-ta/chapter1.ta.md   (.ta suffix before .md)
//   vi: book-vi/chapter1.vi.md   (.vi suffix before .md)
document.addEventListener("DOMContentLoaded", () => {
  const cfg = window.config.extra?.languages;
  if (!cfg) return;

  const container = document.querySelector(".lang-tabs");
  if (!container) return;

  // Determine current language from the URL path.
  const path = location.pathname.replace(/\/$/, ""); // trailing slash
  let active = "";
  for (const [code, lang] of Object.entries(cfg)) {
    if (path.includes(lang.prefix)) {
      active = code;
      break;
    }
  }
  if (!active) active = Object.entries(cfg).find(([, l]) => l.default)?.[0] || "zh";

  function mapUrl(targetCode) {
    if (targetCode === active) return null;

    const src = cfg[active];
    const dst = cfg[targetCode];

    // Build target URL by swapping prefix and handling suffixes.
    let url = location.pathname;
    url = url.replace(src.prefix, dst.prefix);

    // Remove old suffix (e.g. ".ta") before .md, add new one if needed.
    if (src.suffix) {
      url = url.replace(src.suffix + ".md", ".md");
    }
    if (dst.suffix) {
      url = url.replace(/\.md$/, dst.suffix + ".md");
    }

    return url || dst.prefix + "introduction" + (dst.suffix || "") + ".md";
  }

  // Render tabs.
  for (const [code, lang] of Object.entries(cfg)) {
    const btn = document.createElement("button");
    btn.className = "lang-tab" + (code === active ? " lang-tab--active" : "");
    btn.textContent = lang.label;
    btn.setAttribute("role", "tab");
    btn.setAttribute("aria-selected", code === active ? "true" : "false");

    if (code !== active) {
      btn.onclick = () => {
        const target = mapUrl(code);
        if (target) location.href = target;
      };
    }

    container.appendChild(btn);
  }
});
