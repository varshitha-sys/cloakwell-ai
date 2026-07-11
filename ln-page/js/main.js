import { renderNav, renderFooter } from "./nav.js";
import { mountAsciiBackground } from "./ascii-bg.js";

async function boot() {
  await mountAsciiBackground();

  const root = document.getElementById("app");
  if (!root) return;

  const page = root.dataset.page || "home";

  const navHost = document.querySelector('[data-partial="nav"]');
  if (navHost) navHost.innerHTML = renderNav(page);

  const footerHost = document.querySelector('[data-partial="footer"]');
  if (footerHost) footerHost.innerHTML = renderFooter();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", () => {
    void boot();
  });
} else {
  void boot();
}
