import { CROW_ASCII } from "./crow-art.js";

const BG_ID = "ascii-bg";

/**
 * Load art from assets/crow.txt when available (easy to paste full multi-line
 * ASCII without chat truncation). Falls back to CROW_ASCII.
 */
async function loadCrowArt() {
  try {
    const url = new URL("../assets/crow-ascii-art.txt", import.meta.url);
    const res = await fetch(url);
    if (!res.ok) return CROW_ASCII;
    const text = (await res.text()).replace(/\r\n/g, "\n").replace(/\s+$/, "");
    return text.trim().length ? text : CROW_ASCII;
  } catch {
    return CROW_ASCII;
  }
}

/**
 * Inject a fixed, decorative monospaced ASCII layer and scale it so the
 * full art fits any viewport (width + height) without blur.
 */
export async function mountAsciiBackground() {
  if (document.getElementById(BG_ID)) return;

  const art = await loadCrowArt();

  const layer = document.createElement("div");
  layer.id = BG_ID;
  layer.className = "ascii-bg";
  layer.setAttribute("aria-hidden", "true");

  const pre = document.createElement("pre");
  pre.className = "ascii-bg__art";
  pre.textContent = art;
  layer.appendChild(pre);

  document.body.prepend(layer);

  const fit = () => fitAsciiToViewport(pre, art);
  fit();

  let raf = 0;
  const onResize = () => {
    cancelAnimationFrame(raf);
    raf = requestAnimationFrame(fit);
  };
  window.addEventListener("resize", onResize, { passive: true });
}

/**
 * Measure monospaced glyph metrics, then set font-size so the block
 * fits inside the viewport with a small margin.
 */
function fitAsciiToViewport(pre, art) {
  const lines = art.split("\n");
  const cols = lines.reduce((m, line) => Math.max(m, line.length), 0);
  const rows = lines.length;
  if (!cols || !rows) return;

  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const padX = Math.min(48, vw * 0.04);
  const padY = Math.min(48, vh * 0.04);
  const availW = Math.max(1, vw - padX * 2);
  const availH = Math.max(1, vh - padY * 2);

  const probeSize = 100;
  pre.style.fontSize = `${probeSize}px`;
  pre.style.lineHeight = "1.05";
  pre.style.letterSpacing = "0";

  const rect = pre.getBoundingClientRect();
  const measuredW = rect.width || probeSize * cols * 0.6;
  const measuredH = rect.height || probeSize * rows * 1.05;

  const unitW = measuredW / cols;
  const unitH = measuredH / rows;

  const fsByW = (availW / cols) * (probeSize / unitW);
  const fsByH = (availH / rows) * (probeSize / unitH);
  const fontSize = Math.max(4, Math.min(fsByW, fsByH));

  pre.style.fontSize = `${fontSize}px`;
}
