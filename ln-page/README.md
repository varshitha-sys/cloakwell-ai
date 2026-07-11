# Landing page (`ln-page`)

Static marketing site for the local-first AI redaction project (AMD Hackathon Track 3).

## Approach: “static multipage + Alpine”

| Concern | Choice |
| --- | --- |
| Too basic? | Modular CSS, multi-page layout, Alpine.js for nav/interactions |
| Too heavy? | No React/Vue/Svelte, no SPA router, no `node_modules` in deploy |
| Deploy | Pure static files — GitHub Pages, Netlify, or any static host |
| Colors | Prussian blue + white (CSS custom properties) |

**Stack**

- HTML multipage (`index.html`, `download.html`)
- Plain CSS modules under `css/` (variables → base → layout → components → pages)
- Alpine.js via CDN (~15 KB gzipped) for mobile nav / light UI only
- Optional later: Vite multipage build if you want a dev server + minify (still ships static HTML/CSS/JS)

## Nav

- **Home** → `index.html`
- **Download** → `download.html` (install / run instructions)
- **GitHub** → external link to `https://github.com/varshitha-sys/amd-hackathon-track3`

## Local preview

No install required:

```bash
# from repo root, any static server works
npx --yes serve ln-page
# or Python
python -m http.server 8080 --directory ln-page
```

## Deploy

Upload the contents of `ln-page/` (or a future `dist/` if Vite is added). Nothing runs Node in production.
