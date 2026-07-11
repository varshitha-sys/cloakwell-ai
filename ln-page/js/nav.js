import { site } from "./config.js";

/**
 * Inject shared nav markup so both pages stay in sync without a framework.
 * Alpine handles mobile open/close when we flesh out the responsive menu.
 */
export function renderNav(activePage) {
  const links = Object.entries(site.pages)
    .map(([key, page]) => {
      const current = key === activePage ? ' aria-current="page"' : "";
      return `<li><a href="${page.href}"${current}>${page.label}</a></li>`;
    })
    .join("");

  return `
    <nav class="nav" x-data="{ open: false }" aria-label="Primary">
      <a class="nav-brand" href="${site.pages.home.href}">
        <img src="assets/crow-imogen-oh.png" alt="" class="nav-logo" />
        <span>${site.shortName}</span>
      </a>
      <ul class="nav-links">
        ${links}
        <li>
          <a href="${site.githubUrl}" target="_blank" rel="noopener noreferrer">
            ${site.githubLabel}
          </a>
        </li>
      </ul>
    </nav>
  `;
}

export function renderFooter() {
  const year = new Date().getFullYear();
  return `
    <div class="inner">
      <div>
        <span>© ${year} ${site.name}</span>
        <br />
        <small style="opacity: 0.35; font-size: 0.75rem; display: block; margin-top: 0.25rem;">
          <a href="https://www.flaticon.com/free-icons/crow" title="crow icons" target="_blank" rel="noopener noreferrer" style="color: inherit; text-decoration: none;">Crow icon created by Imogen.Oh - Flaticon</a>
        </small>
      </div>
      <a href="${site.githubUrl}" target="_blank" rel="noopener noreferrer">
        ${site.githubLabel} repository
      </a>
    </div>
  `;
}
