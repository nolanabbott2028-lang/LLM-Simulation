/**
 * Civilization Layers — canvas map + overlays.
 * When the Python dashboard is running, the UI uses /api (same-origin snapshot).
 * Add ?local=1 to force the in-browser LocalSim only (e.g. static file demos).
 */
window.__CIV_USE_SERVER = false;

function useLocalSim() {
  return !window.__CIV_USE_SERVER && typeof window.LocalSim !== "undefined";
}

const SCALE_PAD = 0.92;

/** Camera zoom is multiplied onto fit-scale; LOD switches by thresholds (vector map, not raster). */
const ZOOM_MIN = 0.35;
const ZOOM_MAX = 80;
const ZOOM_LERP = 0.18;

/** Shared snapshot + selection (single dashboard instance) */
let lastState = { agents: [], world_bounds: { width: 3200, height: 3200 } };
/** Set in setup — re-fetch snapshot after transport APIs / bookmark */
let refreshSnapshotFromServer = async () => {};
let selectedAgentId = null;
let lastAgentRefreshMs = 0;
/** Updated every frame — used by minimap viewport */
let lastMapTransform = null;
/** Procedural pixel terrain base layer (pixel_terrain_map.js) */
let pixelTerrainApi = null;

/** Hash string → deterministic HSL color */
function factionColor(fid) {
  if (!fid) return "#7a8a9e";
  let h = 0;
  const s = String(fid);
  for (let i = 0; i < s.length; i++) {
    h = s.charCodeAt(i) + ((h << 5) - h);
  }
  const hue = Math.abs(h) % 360;
  return `hsl(${hue}, 62%, 52%)`;
}

function projectIdeology(beliefs) {
  if (!beliefs) return { x: 0, y: 0 };
  const x =
    (beliefs.cooperation_good ?? 0) - (beliefs.violence_justified ?? 0);
  const y = (beliefs.authority_good ?? 0) - (beliefs.outgroup_danger ?? 0);
  return { x, y };
}

function terrainBrush(cell) {
  switch (cell) {
    case "forest":
      return [34, 90, 42];
    case "water":
      return [48, 110, 170];
    case "grass":
    default:
      return [88, 132, 68];
  }
}

class OverlayManager {
  constructor() {
    /** @type {Set<string>} */
    this.active = new Set();
  }

  enable(name) {
    this.active.add(name);
  }

  disable(name) {
    this.active.delete(name);
  }

  toggle(name, on) {
    if (on) this.enable(name);
    else this.disable(name);
  }

  has(name) {
    return this.active.has(name);
  }
}

function clamp(v, lo, hi) {
  return Math.max(lo, Math.min(hi, v));
}

/** LOD tier from camera zoom (matches backend-friendly thresholds). */
function getZoomLevel(zoom) {
  const z = Number(zoom) || 1;
  if (z < 2) return "regions";
  if (z < 5) return "provinces";
  if (z < 10) return "cities";
  return "towns";
}

function shouldShowLabel(zoom, type) {
  const z = Number(zoom) || 1;
  if (type === "region") return z < 3;
  if (type === "province") return z >= 3 && z < 6;
  if (type === "city") return z >= 6 && z < 10;
  if (type === "town") return z >= 10;
  return false;
}

/**
 * World → screen: pan (cx,cy) is world point at canvas center; zoom scales fit-to-view scale.
 */
function computeTransform(canvas, bounds, view) {
  const bw = bounds.width || 3200;
  const bh = bounds.height || 3200;
  const cw = canvas.clientWidth || canvas.width;
  const ch = canvas.clientHeight || canvas.height;
  const cx = view?.cx != null ? view.cx : bw / 2;
  const cy = view?.cy != null ? view.cy : bh / 2;
  const zoom = clamp(view?.zoom ?? 1, ZOOM_MIN, ZOOM_MAX);
  const sFit = Math.min((cw / bw) * SCALE_PAD, (ch / bh) * SCALE_PAD);
  const s = sFit * zoom;
  const ox = cw / 2;
  const oy = ch / 2;
  const lodLevel = getZoomLevel(zoom);
  /** Vector overlays stay LOD-gated; sim dots/sprites should be visible at any zoom. */
  const showAgents = true;
  return { s, ox, oy, cx, cy, bw, bh, cw, ch, zoom, sFit, lodLevel, showAgents };
}

function worldToScreen(wx, wy, T) {
  const x = (wx - T.cx) * T.s + T.ox;
  const y = (wy - T.cy) * T.s + T.oy;
  return [x, y];
}

function screenToWorld(mx, my, canvas, T) {
  const rect = canvas.getBoundingClientRect();
  const sx = mx - rect.left;
  const sy = my - rect.top;
  const wx = (sx - T.ox) / T.s + T.cx;
  const wy = (sy - T.oy) / T.s + T.cy;
  return { wx, wy };
}

/** Map view transform for hit-testing; works before first full paint if lastState/view are set. */
function getActiveMapTransform(canvas, view, lastStateRef, currentTransform) {
  if (currentTransform && currentTransform.s > 1e-8) return currentTransform;
  const bounds = lastStateRef.world_bounds || { width: 3200, height: 3200 };
  const t = computeTransform(canvas, bounds, view);
  if (t.s < 1e-8) t.s = 1e-6;
  return t;
}

function hslFade(hsl, alpha) {
  if (!hsl || hsl.indexOf("hsl(") !== 0) return `rgba(90, 120, 150, ${alpha})`;
  return hsl.replace(/^hsl\(/, "hsla(").replace(/\)$/, `, ${alpha})`);
}

function polygonCentroid(poly) {
  if (!poly?.length) return [0, 0];
  let sx = 0;
  let sy = 0;
  for (const p of poly) {
    sx += p[0];
    sy += p[1];
  }
  const n = poly.length;
  return [sx / n, sy / n];
}

function drawPolygonWorld(ctx, poly, T, fillStyle, strokeStyle, fillAlpha = 1) {
  if (!poly?.length) return;
  ctx.beginPath();
  const [fx, fy] = worldToScreen(poly[0][0], poly[0][1], T);
  ctx.moveTo(fx, fy);
  for (let i = 1; i < poly.length; i++) {
    const [sx, sy] = worldToScreen(poly[i][0], poly[i][1], T);
    ctx.lineTo(sx, sy);
  }
  ctx.closePath();
  ctx.globalAlpha = fillAlpha;
  if (fillStyle) {
    ctx.fillStyle = fillStyle;
    ctx.fill();
  }
  ctx.globalAlpha = 1;
  if (strokeStyle) {
    ctx.strokeStyle = strokeStyle;
    ctx.lineWidth = Math.max(1, 1.2);
    ctx.stroke();
  }
}

function drawLabelScreen(ctx, text, sx, sy, maxW = 140) {
  ctx.save();
  ctx.font = '500 11px "IBM Plex Sans",system-ui,sans-serif';
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillStyle = "rgba(232, 238, 246, 0.92)";
  ctx.strokeStyle = "rgba(0,0,0,0.55)";
  ctx.lineWidth = 3;
  const t = String(text).slice(0, 28);
  ctx.strokeText(t, sx, sy, maxW);
  ctx.fillText(t, sx, sy, maxW);
  ctx.restore();
}

/** Screen-space grid to reduce overlapping labels (one winner per bucket). */
const __labelBuckets = new Set();
function resetLabelDeclutter() {
  __labelBuckets.clear();
}
function labelBucketTake(sx, sy, cellPx = 52) {
  const bx = Math.floor(sx / cellPx);
  const by = Math.floor(sy / cellPx);
  const k = `${bx},${by}`;
  if (__labelBuckets.has(k)) return false;
  __labelBuckets.add(k);
  return true;
}

function drawLabelMaybe(ctx, text, sx, sy, maxW, z, type, declutter) {
  if (!shouldShowLabel(z, type)) return;
  if (declutter && !labelBucketTake(sx, sy)) return;
  drawLabelScreen(ctx, text, sx, sy, maxW);
}

function coarserLodLevel(lod) {
  const order = ["regions", "provinces", "cities", "towns"];
  const i = order.indexOf(lod);
  return i <= 0 ? null : order[i - 1];
}

/** Stronger near LOD thresholds 2 / 5 / 10 — soft cross-fade between tiers. */
function secondaryLodBlendAlpha(zoom) {
  const edges = [2, 5, 10];
  let m = 0;
  for (const e of edges) {
    const d = Math.abs(zoom - e);
    if (d < 0.5) {
      m = Math.max(m, 1 - d / 0.5);
    }
  }
  return clamp(m, 0, 1);
}

/** HTTP terrain tiles: higher camera zoom → higher terrain LOD (finer sampling). */
const terrainTileCache = new Map();
let terrainFetchGen = 0;

function terrainLodFromCamera(zoom) {
  return clamp(Math.round(Math.log2(Math.max(0.45, zoom)) + 2), 0, 6);
}

function visibleTerrainTileIndices(T, lod) {
  const W = T.bw;
  const H = T.bh;
  const nt = 2 ** lod;
  const tw = W / nt;
  const th = H / nt;
  const vl = T.cx - T.cw / (2 * T.s);
  const vr = T.cx + T.cw / (2 * T.s);
  const vt = T.cy - T.ch / (2 * T.s);
  const vb = T.cy + T.ch / (2 * T.s);
  const padX = tw * 0.3;
  const padY = th * 0.3;
  let i0 = Math.floor((vl - padX) / tw);
  let i1 = Math.floor((vr + padX) / tw);
  let j0 = Math.floor((vt - padY) / th);
  let j1 = Math.floor((vb + padY) / th);
  i0 = clamp(i0, 0, nt - 1);
  i1 = clamp(i1, 0, nt - 1);
  j0 = clamp(j0, 0, nt - 1);
  j1 = clamp(j1, 0, nt - 1);
  const out = [];
  for (let ty = j0; ty <= j1; ty++) {
    for (let tx = i0; tx <= i1; tx++) {
      out.push({ tx, ty });
    }
  }
  return out;
}

function biomeRgb(biome, h) {
  let rgb;
  switch (biome) {
    case "deep_water":
      rgb = [10, 22, 48];
      break;
    case "shallows":
      rgb = [26, 68, 108];
      break;
    case "grassland":
      rgb = [62, 98, 52];
      break;
    case "forest":
      rgb = [24, 82, 44];
      break;
    case "foothills":
      rgb = [92, 86, 68];
      break;
    case "mountain":
      rgb = [76, 72, 70];
      break;
    case "peak":
      rgb = [210, 212, 220];
      break;
    default:
      rgb = [58, 68, 56];
  }
  const lift = (h || 0.5) * 0.12;
  return [
    clamp(rgb[0] + lift * 55, 0, 255),
    clamp(rgb[1] + lift * 55, 0, 255),
    clamp(rgb[2] + lift * 55, 0, 255),
  ];
}

function drawOneTerrainTile(ctx, T, payload) {
  const rect = payload.world_rect;
  if (!rect || !payload.cells?.length) return;
  const [x0, y0, x1, y1] = rect;
  const gw = payload.grid?.w || payload.cells[0].length;
  const gh = payload.grid?.h || payload.cells.length;
  const cw = (x1 - x0) / gw;
  const ch = (y1 - y0) / gh;
  for (let j = 0; j < gh; j++) {
    const row = payload.cells[j];
    if (!row) continue;
    for (let i = 0; i < gw; i++) {
      const cell = row[i];
      if (!cell) continue;
      const wx0 = x0 + i * cw;
      const wy0 = y0 + j * ch;
      const [sx, sy] = worldToScreen(wx0, wy0, T);
      const [sx2, sy2] = worldToScreen(wx0 + cw, wy0 + ch, T);
      const rgb = biomeRgb(cell.biome, cell.h);
      ctx.fillStyle = `rgb(${rgb[0]|0},${rgb[1]|0},${rgb[2]|0})`;
      ctx.fillRect(sx, sy, Math.max(1, sx2 - sx), Math.max(1, sy2 - sy));
    }
  }
}

function drawTerrainRasterFromCache(ctx, T) {
  const lod = terrainLodFromCamera(T.zoom);
  for (const { tx, ty } of visibleTerrainTileIndices(T, lod)) {
    const payload = terrainTileCache.get(`${lod}/${tx}/${ty}`);
    if (payload) drawOneTerrainTile(ctx, T, payload);
  }
}

function terrainTilesMissing(T) {
  const lod = terrainLodFromCamera(T.zoom);
  for (const { tx, ty } of visibleTerrainTileIndices(T, lod)) {
    if (!terrainTileCache.has(`${lod}/${tx}/${ty}`)) return true;
  }
  return false;
}

async function fetchVisibleTerrainTiles(T) {
  if (useLocalSim()) {
    return;
  }
  const myGen = terrainFetchGen;
  const lod = terrainLodFromCamera(T.zoom);
  const jobs = [];
  for (const { tx, ty } of visibleTerrainTileIndices(T, lod)) {
    const key = `${lod}/${tx}/${ty}`;
    if (terrainTileCache.has(key)) continue;
    jobs.push(
      fetch(`/api/map/terrain?lod=${lod}&tx=${tx}&ty=${ty}`)
        .then((r) => r.json())
        .then((j) => {
          if (myGen !== terrainFetchGen) return;
          if (!j.error && j.cells) {
            terrainTileCache.set(key, j);
          } else {
            terrainTileCache.set(key, {
              cells: [],
              world_rect: [0, 0, 0, 0],
              grid: { w: 0, h: 0 },
              _empty: true,
            });
          }
        })
        .catch(() => {
          if (myGen !== terrainFetchGen) return;
          terrainTileCache.set(key, {
            cells: [],
            world_rect: [0, 0, 0, 0],
            grid: { w: 0, h: 0 },
            _empty: true,
          });
        })
    );
  }
  await Promise.all(jobs);
}

function drawFogOverlay(ctx, state, T) {
  const fog = state.fog_of_war;
  if (!fog?.cells?.length || !fog.grid_w) return;
  const gw = fog.grid_w;
  const gh = fog.grid_h;
  const W = fog.world_bounds?.width || T.bw;
  const H = fog.world_bounds?.height || T.bh;
  const cw = W / gw;
  const ch = H / gh;
  const cells = fog.cells;
  ctx.save();
  for (let j = 0; j < gh; j++) {
    for (let i = 0; i < gw; i++) {
      const vis = cells[j * gw + i];
      if (vis == null || vis >= 0.995) continue;
      const dark = (1 - vis) * 0.72;
      const wx0 = i * cw;
      const wy0 = j * ch;
      const [sx, sy] = worldToScreen(wx0, wy0, T);
      const [sx2, sy2] = worldToScreen(wx0 + cw, wy0 + ch, T);
      ctx.fillStyle = `rgba(2,6,14,${dark})`;
      ctx.fillRect(sx, sy, Math.max(1, sx2 - sx), Math.max(1, sy2 - sy));
    }
  }
  ctx.restore();
}

/**
 * Vector LOD layers — pass lodLevelKey to draw a specific tier (for cross-fade underlay).
 * @param skipLabels — ghost layer omits text
 * @param declutter — primary layer uses screen-space label buckets
 */
function drawVectorLodMapAt(ctx, state, T, lodLevelKey, skipLabels, declutter) {
  const ml = state.map_lod;
  if (!ml) return;
  const lod = lodLevelKey;
  const z = T.zoom;

  if (lod === "regions") {
    for (const r of ml.regions || []) {
      const col = hslFade(factionColor(r.faction_id), 0.32);
      drawPolygonWorld(ctx, r.polygon, T, col, "rgba(200, 230, 255, 0.35)");
      if (!skipLabels) {
        const [cx, cy] = polygonCentroid(r.polygon);
        const [sx, sy] = worldToScreen(cx, cy, T);
        drawLabelMaybe(ctx, r.name, sx, sy, 140, z, "region", declutter);
      }
    }
    return;
  }

  if (lod === "provinces") {
    for (const p of ml.provinces || []) {
      const col = factionColor(p.faction_id);
      const m = col.match(/hsl\((\d+),\s*(\d+)%,\s*(\d+)%\)/);
      const fill = m
        ? `hsla(${m[1]}, ${m[2]}%, ${m[3]}%, 0.22)`
        : "rgba(100, 140, 200, 0.2)";
      drawPolygonWorld(ctx, p.polygon, T, fill, "rgba(160, 190, 220, 0.32)");
      if (!skipLabels) {
        const [cx, cy] = polygonCentroid(p.polygon);
        const [sx, sy] = worldToScreen(cx, cy, T);
        drawLabelMaybe(ctx, p.name, sx, sy, 120, z, "province", declutter);
      }
    }
    return;
  }

  if (lod === "cities") {
    ctx.save();
    for (const c of ml.cities || []) {
      const [sx, sy] = worldToScreen(c.x, c.y, T);
      const col = factionColor(c.faction_id);
      ctx.fillStyle = col;
      ctx.strokeStyle = "rgba(0,0,0,0.4)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.arc(sx, sy, 6, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();
      if (!skipLabels) {
        drawLabelMaybe(ctx, c.name, sx, sy - 14, 100, z, "city", declutter);
      }
    }
    ctx.restore();
    return;
  }

  ctx.save();
  for (const twn of ml.towns || []) {
    const [sx, sy] = worldToScreen(twn.x, twn.y, T);
    ctx.fillStyle = "rgba(180, 200, 220, 0.95)";
    ctx.strokeStyle = "rgba(0,0,0,0.35)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.arc(sx, sy, 4, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
    if (!skipLabels) {
      drawLabelMaybe(ctx, twn.name, sx, sy - 12, 90, z, "town", declutter);
    }
  }
  ctx.restore();
}

function drawVectorLodMap(ctx, state, T) {
  resetLabelDeclutter();
  drawVectorLodMapAt(ctx, state, T, T.lodLevel, false, true);
}

function drawTerrainSample(ctx, state, T, enabled) {
  if (!enabled || !state.terrain_sample?.length) return;
  const rows = state.terrain_sample;
  const cols = rows[0]?.length || 1;
  const cellW = T.bw / cols;
  const cellH = T.bh / rows.length;
  ctx.save();
  for (let r = 0; r < rows.length; r++) {
    for (let c = 0; c < rows[r].length; c++) {
      const rgb = terrainBrush(rows[r][c]);
      ctx.fillStyle = `rgb(${rgb[0]},${rgb[1]},${rgb[2]})`;
      const x0 = c * cellW;
      const y0 = r * cellH;
      const [sx, sy] = worldToScreen(x0, y0, T);
      const [sx2, sy2] = worldToScreen(x0 + cellW, y0 + cellH, T);
      ctx.fillRect(sx, sy, sx2 - sx, sy2 - sy);
    }
  }
  ctx.restore();
}

function agentScreenRadius(T) {
  return clamp(5.5 * T.s, 2.8, 18);
}

/**
 * Sprite height in world pixels ≈ config SIM_SPRITE_BASE_HEIGHT (40).
 * `idle` — front/standing, `walk` — side profile (mirrored for facing), `swim` — rear/in-water.
 */
const AGENT_SPRITE_BASE_H = 40;
const simSheet = { idle: null, walk: null, swim: null };

/** Resolve from document URL so sprites load when /api is the app (not tied to <script> src quirks). */
function simAssetUrl(filename) {
  try {
    return new URL(`assets/sims/${filename}`, document.baseURI).href;
  } catch (_) {
    const org = window.location && window.location.origin;
    if (org) return `${org}/assets/sims/${filename}`;
    return `assets/sims/${filename}`;
  }
}

function loadSimSprites() {
  function fire() {
    window.dispatchEvent(new Event("sims-sprites-ready"));
  }
  for (const key of Object.keys(simSheet)) {
    const im = new Image();
    const name = `${key}.png`;
    const o = window.location && window.location.origin;
    const primary = o && o.length ? `${o}/assets/sims/${name}` : simAssetUrl(name);
    im.onload = () => {
      if (typeof im.decode === "function") {
        im.decode().then(fire).catch(fire);
      } else {
        fire();
      }
    };
    im.onerror = () => {
      const o = window.location && window.location.origin;
      const abs = o ? `${o}/assets/sims/${name}` : null;
      if (abs && !im.dataset.civRetried) {
        im.dataset.civRetried = "1";
        if (String(im.currentSrc || im.src) !== abs) {
          im.src = abs;
          return;
        }
      }
      if (key === "idle") {
        console.warn(
          "Sim sprite not loaded; check /assets/sims/ is served. Last src:",
          im.currentSrc || im.src || primary
        );
      }
    };
    im.src = primary;
    simSheet[key] = im;
  }
}

function drawAgentsBase(ctx, state, T) {
  if (!T.showAgents) return;
  const agents = state.agents || [];
  for (const a of agents) {
    const [sx, sy] = worldToScreen(a.x, a.y, T);
    const inWater = !!a.in_water;
    const moving = !!a.moving;
    const faceLeft = (a.facing || 1) < 0;
    let src = simSheet.idle;
    /** Sim state → art: back/rear in water, side when moving on land, front when still. */
    let mirrorX = false;
    if (inWater && simSheet.swim && simSheet.swim.naturalWidth) {
      src = simSheet.swim;
      mirrorX = false;
    } else if (moving && simSheet.walk && simSheet.walk.naturalWidth) {
      src = simSheet.walk;
      mirrorX = faceLeft;
    } else if (simSheet.idle && simSheet.idle.naturalWidth) {
      src = simSheet.idle;
      mirrorX = false;
    }

    if (src && src.complete && src.naturalWidth > 0) {
      const h = Math.max(10, AGENT_SPRITE_BASE_H * T.s);
      const w = (src.naturalWidth / src.naturalHeight) * h;
      ctx.save();
      ctx.translate(sx, sy);
      if (mirrorX) {
        ctx.scale(-1, 1);
      }
      ctx.imageSmoothingEnabled = true;
      ctx.drawImage(src, -w / 2, -h, w, h);
      ctx.restore();
    } else {
      const r = agentScreenRadius(T);
      const col = factionColor(a.faction != null && a.faction !== "" ? a.faction : a.id);
      ctx.fillStyle = col;
      ctx.strokeStyle = "rgba(0,0,0,0.45)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.arc(sx, sy, r, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();
    }
  }
}

function drawTradeFlowOverlay(ctx, state, T) {
  const flows = state.trade_flow || [];
  ctx.save();
  ctx.strokeStyle = "rgba(255, 210, 90, 0.8)";
  ctx.fillStyle = "rgba(255, 230, 140, 0.95)";
  ctx.lineWidth = 2;
  for (const tr of flows) {
    const [ax, ay] = worldToScreen(tr.x1, tr.y1, T);
    const [bx, by] = worldToScreen(tr.x2, tr.y2, T);
    ctx.beginPath();
    ctx.moveTo(ax, ay);
    ctx.lineTo(bx, by);
    ctx.stroke();
    const ang = Math.atan2(by - ay, bx - ax);
    const head = 9;
    ctx.beginPath();
    ctx.moveTo(bx, by);
    ctx.lineTo(
      bx - head * Math.cos(ang - 0.45),
      by - head * Math.sin(ang - 0.45)
    );
    ctx.lineTo(
      bx - head * Math.cos(ang + 0.45),
      by - head * Math.sin(ang + 0.45)
    );
    ctx.closePath();
    ctx.fill();
  }
  ctx.restore();
}

function drawIdeologyOverlay(ctx, state, T) {
  if (!T.showAgents) return;
  const agents = state.agents || [];
  for (const a of agents) {
    const b = a.beliefs || {};
    const { x: ix, y: iy } = projectIdeology(b);
    const t = Math.min(0.85, 0.35 + Math.hypot(ix, iy) / 220);
    const hx = Math.floor(((ix + 100) / 200) * 255);
    const hy = Math.floor(((iy + 100) / 200) * 255);
    ctx.fillStyle = `rgba(${hx}, ${120}, ${255 - hx}, ${t})`;
    const [sx, sy] = worldToScreen(a.x, a.y, T);
    ctx.fillRect(sx - 4, sy - 4, 9, 9);
  }

  const byFac = new Map();
  for (const a of agents) {
    const fid = a.faction || "_none";
    if (!byFac.has(fid)) byFac.set(fid, []);
    byFac.get(fid).push(a);
  }
  for (const [, group] of byFac) {
    if (group.length < 2) continue;
    let sx = 0,
      sy = 0;
    for (const a of group) {
      sx += a.x;
      sy += a.y;
    }
    sx /= group.length;
    sy /= group.length;
    const [cx, cy] = worldToScreen(sx, sy, T);
    const rad = 22 + Math.min(40, group.length * 6);
    const g = ctx.createRadialGradient(cx, cy, 4, cx, cy, rad);
    g.addColorStop(0, "rgba(120, 200, 255, 0.35)");
    g.addColorStop(1, "rgba(120, 200, 255, 0)");
    ctx.fillStyle = g;
    ctx.beginPath();
    ctx.arc(cx, cy, rad, 0, Math.PI * 2);
    ctx.fill();
  }
}

function drawWarOverlay(ctx, state, T) {
  const wars = state.war_overlay || [];
  ctx.save();
  ctx.strokeStyle = "rgba(255, 80, 80, 0.55)";
  ctx.lineWidth = 2;
  for (const w of wars) {
    const fa = w.front_a;
    const fb = w.front_b;
    if (!fa || !fb) continue;
    const [ax, ay] = worldToScreen(fa.x, fa.y, T);
    const [bx, by] = worldToScreen(fb.x, fb.y, T);
    ctx.beginPath();
    ctx.moveTo(ax, ay);
    ctx.lineTo(bx, by);
    ctx.stroke();
    const imb = Math.abs(w.imbalance || 0);
    const mx = (ax + bx) / 2;
    const my = (ay + by) / 2;
    ctx.fillStyle = `rgba(255, 60, 60, ${Math.min(0.45, 0.15 + imb / 80)})`;
    ctx.beginPath();
    ctx.arc(mx, my, 8 + imb * 0.4, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.restore();
}

function resourceColor(type) {
  const t = (type || "").toLowerCase();
  if (t.includes("wood") || t === "tree") return "rgba(60, 160, 80, ";
  if (
    t.includes("berry") ||
    t.includes("farm") ||
    t.includes("animal") ||
    t.includes("meat") ||
    t.includes("grain") ||
    t.includes("berries")
  )
    return "rgba(230, 200, 60, ";
  if (t.includes("stone")) return "rgba(140, 140, 150, ";
  if (t.includes("water") || t.includes("river")) return "rgba(80, 140, 220, ";
  return "rgba(180, 180, 200, ";
}

function drawEconomyOverlay(ctx, state, T) {
  const res = state.resources || [];
  ctx.save();
  for (const r of res) {
    const base = resourceColor(r.type);
    const al = Math.min(0.9, 0.15 + (r.amount || 0) / 120);
    ctx.fillStyle = base + al + ")";
    const [sx, sy] = worldToScreen(r.x, r.y, T);
    const sz = 6 + Math.min(14, (r.amount || 0) / 10);
    ctx.fillRect(sx - sz / 2, sy - sz / 2, sz, sz);
  }
  ctx.restore();
}

function drawStructuresOverlay(ctx, state, T) {
  const sts = state.structures || [];
  if (!sts.length) return;
  ctx.save();
  for (const st of sts) {
    const [sx, sy] = worldToScreen(st.x, st.y, T);
    const w = 12;
    ctx.fillStyle = "rgba(130, 95, 60, 0.88)";
    ctx.fillRect(sx - w / 2, sy - w / 3, w, w * 0.75);
    ctx.strokeStyle = "rgba(35, 28, 20, 0.95)";
    ctx.lineWidth = 1;
    ctx.strokeRect(sx - w / 2, sy - w / 3, w, w * 0.75);
    ctx.beginPath();
    ctx.moveTo(sx - w * 0.65, sy - w * 0.25);
    ctx.lineTo(sx, sy - w * 0.95);
    ctx.lineTo(sx + w * 0.65, sy - w * 0.25);
    ctx.closePath();
    ctx.fillStyle = "rgba(85, 55, 40, 0.92)";
    ctx.fill();
    ctx.stroke();
  }
  ctx.restore();
}

function drawPropagandaOverlay(ctx, state, T) {
  const factions = state.factions || [];
  ctx.save();
  for (const f of factions) {
    const lx = f.leader_x ?? f.centroid_x;
    const ly = f.leader_y ?? f.centroid_y;
    const strength = f.propaganda_power ?? 20;
    const [cx, cy] = worldToScreen(lx, ly, T);
    const rad = 30 + Math.min(120, strength * 1.5);
    const g = ctx.createRadialGradient(cx, cy, 6, cx, cy, rad);
    g.addColorStop(0, "rgba(200, 120, 255, 0.38)");
    g.addColorStop(1, "rgba(200, 120, 255, 0)");
    ctx.fillStyle = g;
    ctx.beginPath();
    ctx.arc(cx, cy, rad, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.restore();
}

function drawStabilityOverlay(ctx, state, T) {
  if (!T.showAgents) return;
  const agents = state.agents || [];
  ctx.save();
  for (const a of agents) {
    const st = a.status ?? 50;
    const t = st / 100;
    ctx.strokeStyle = `rgba(${Math.floor(255 * (1 - t))}, ${Math.floor(200 * t)}, 80, 0.65)`;
    ctx.lineWidth = 2;
    const [sx, sy] = worldToScreen(a.x, a.y, T);
    ctx.beginPath();
    ctx.arc(sx, sy, 9, 0, Math.PI * 2);
    ctx.stroke();
  }
  ctx.restore();
}

function renderFrame(canvas, ctx, om, state, terrainOn, view) {
  const bounds = state.world_bounds || { width: 3200, height: 3200 };
  const cw = canvas.clientWidth || canvas.width;
  const ch = canvas.clientHeight || canvas.height;
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = pixelTerrainApi ? "#0d1f35" : "#030508";
  ctx.fillRect(0, 0, cw, ch);

  const T = computeTransform(canvas, bounds, view);
  lastMapTransform = T;

  if (pixelTerrainApi) {
    pixelTerrainApi.draw(ctx, T);
  } else {
    drawTerrainRasterFromCache(ctx, T);
  }

  /* Political LOD + fog sit on top of the procedural base — skip when pixel terrain is the visible map. */
  if (!pixelTerrainApi) {
    const hasLod = state.map_lod?.regions?.length > 0;
    if (hasLod) {
      const blend = secondaryLodBlendAlpha(T.zoom);
      const under = coarserLodLevel(T.lodLevel);
      if (under && blend > 0.04) {
        ctx.save();
        ctx.globalAlpha = blend * 0.42;
        drawVectorLodMapAt(ctx, state, T, under, true, false);
        ctx.restore();
      }
      drawVectorLodMap(ctx, state, T);
    } else if (terrainOn) {
      drawTerrainSample(ctx, state, T, true);
    }

    drawFogOverlay(ctx, state, T);
  }

  if (om.has("economy")) drawEconomyOverlay(ctx, state, T);
  drawStructuresOverlay(ctx, state, T);
  drawAgentsBase(ctx, state, T);
  if (om.has("trade_flow")) drawTradeFlowOverlay(ctx, state, T);

  if (om.has("ideology")) drawIdeologyOverlay(ctx, state, T);
  if (om.has("war")) drawWarOverlay(ctx, state, T);
  if (om.has("propaganda")) drawPropagandaOverlay(ctx, state, T);
  if (om.has("stability")) drawStabilityOverlay(ctx, state, T);

  return T;
}

function titleCaseFaction(s) {
  return String(s || "")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function updateTransportControls(state) {
  const paused = !!state.paused;
  const running = state.sim_running !== false;
  const bp = document.getElementById("btn-pause");
  const br = document.getElementById("btn-run");
  if (bp) {
    bp.title = paused ? "Resume time (toggle)" : "Pause time (toggle)";
    bp.classList.toggle("transport-paused", paused);
    bp.setAttribute("aria-pressed", paused ? "true" : "false");
  }
  if (br) {
    br.title = running ? "Run / unpause (if stopped)" : "Start simulation clock";
    br.classList.toggle("needs-start", !running);
  }
  const chip = document.getElementById("sim-status-chip");
  if (chip) {
    if (!running) {
      chip.textContent = "⏹ Stopped";
      chip.className = "meta-chip sim-status-chip stopped";
    } else if (paused) {
      chip.textContent = "⏸ Paused";
      chip.className = "meta-chip sim-status-chip paused";
    } else {
      chip.textContent = "▶ Running";
      chip.className = "meta-chip sim-status-chip running";
    }
  }
}

function updateTopBar(state) {
  const time = state.time || {};
  const yr = time.year ?? 1;
  const era = time.era || "Stone Age";
  const chip = document.getElementById("hdr-era-year");
  if (chip) chip.textContent = `Year ${yr} · Day ${time.day ?? 0} — ${era}`;

  const st = state.stats || {};
  const hdr = document.getElementById("hdr-stats");
  if (hdr) {
    hdr.innerHTML = `
      <span class="stat-pill"><span class="ic">👥</span> Pop <strong>${st.population ?? 0}</strong></span>
      <span class="stat-pill"><span class="ic">⚑</span> Factions <strong>${st.faction_count ?? 0}</strong></span>
      <span class="stat-pill"><span class="ic">⚔</span> Wars <strong>${st.active_war_signals ?? 0}</strong></span>
      <span class="stat-pill"><span class="ic">🛡</span> Stability <strong>${st.stability ?? "—"}%</strong></span>
    `;
  }

  const scrub = document.getElementById("scrub-label");
  if (scrub) scrub.textContent = `Year ${yr} · Day ${time.day ?? 0}`;

  const spd = state.speed ?? 1;
  const speedRange = document.getElementById("speed-range");
  const speedVal = document.getElementById("speed-val");
  if (speedRange && document.activeElement !== speedRange) {
    speedRange.value = String(Math.min(100, Math.max(1, spd)));
  }
  if (speedVal) speedVal.textContent = `${spd}×`;

  updateTransportControls(state);
}

function populateLegend(state) {
  const box = document.getElementById("legend-factions");
  if (!box) return;
  const factions = state.factions || [];
  if (!factions.length) {
    box.innerHTML = `<span class="muted small">No factions yet</span>`;
    return;
  }
  box.innerHTML = factions
    .map((f) => {
      const col = factionColor(f.id);
      const label = titleCaseFaction(f.id);
      return `<div class="legend-row"><span class="legend-swatch" style="background:${col}"></span><span>${escapeHtml(
        label
      )}</span></div>`;
    })
    .join("");
}

function bucketResourceType(key) {
  const k = String(key).toLowerCase();
  if (/berry|animal|farm|food|meat|crop|grain|fish|berries|hide|fresh_water/.test(k))
    return "Food";
  if (k.includes("wood") || k.includes("log")) return "Wood";
  if (/stone|rock|granite/.test(k)) return "Stone";
  if (/axe|hammer|tool|iron|ore|metal|ingot/.test(k)) return "Iron";
  if (/gold|coin|treasure|currency/.test(k)) return "Gold";
  if (/book|scroll|knowledge|tech|paper|clay_tablet|bedroll|pottery|leather/.test(k))
    return "Knowledge";
  return "Food";
}

const RESOURCE_ICONS = {
  Food: "🌿",
  Wood: "🪵",
  Stone: "🪨",
  Iron: "⚒",
  Gold: "🪙",
  Knowledge: "📖",
};

function updateResourceGrid(state) {
  const grid = document.getElementById("resource-grid");
  if (!grid) return;
  const totals = state.economy?.resource_totals || {};
  const buckets = { Food: 0, Wood: 0, Stone: 0, Iron: 0, Gold: 0, Knowledge: 0 };
  for (const [k, v] of Object.entries(totals)) {
    const b = bucketResourceType(k);
    buckets[b] = (buckets[b] || 0) + Number(v);
  }
  const order = ["Food", "Wood", "Stone", "Iron", "Gold", "Knowledge"];
  grid.innerHTML = order
    .map((name) => {
      const val = Math.round(buckets[name] || 0);
      const ic = RESOURCE_ICONS[name] || "·";
      return `<div class="res-cell"><div class="lbl">${ic} ${name}</div><div class="val">${val}</div></div>`;
    })
    .join("");
}

function updateEventLog(state) {
  const log = document.getElementById("event-log");
  if (!log) return;
  const evs = state.timeline || [];
  const tail = evs.slice(-14).reverse();
  if (!tail.length) {
    log.innerHTML = `<div class="event-row muted">No events yet — let the sim run.</div>`;
    return;
  }
  log.innerHTML = tail
    .map((e) => {
      const kind = escapeHtml(e.kind || "event");
      const sum = escapeHtml((e.summary || "").slice(0, 120));
      return `<div class="event-row"><span class="ek">${kind}</span>${sum}</div>`;
    })
    .join("");
}

function updateEraStrip(state) {
  const el = document.getElementById("era-strip");
  if (!el) return;
  const era = state.time?.era || "—";
  const hint = state.era_hint ? ` · ${state.era_hint}` : "";
  el.innerHTML = `<span style="color:var(--accent);font-weight:600;">${escapeHtml(era)}</span>${escapeHtml(
    hint
  )}`;
}

function drawMinimap(state, T) {
  const c = document.getElementById("minimap-canvas");
  if (!c) return;
  const ctx = c.getContext("2d");
  const w = c.width;
  const h = c.height;
  ctx.fillStyle = "#0a0e14";
  ctx.fillRect(0, 0, w, h);
  const terrain = state.terrain_sample;
  if (terrain?.length && terrain[0]?.length) {
    const rows = terrain.length;
    const cols = terrain[0].length;
    const cw = w / cols;
    const ch = h / rows;
    for (let r = 0; r < rows; r++) {
      for (let col = 0; col < cols; col++) {
        const rgb = terrainBrush(terrain[r][col]);
        ctx.fillStyle = `rgb(${rgb[0]},${rgb[1]},${rgb[2]})`;
        ctx.fillRect(col * cw, r * ch, cw + 0.6, ch + 0.6);
      }
    }
  }
  const bounds = state.world_bounds || { width: 1, height: 1 };
  const bw = bounds.width;
  const bh = bounds.height;
  ctx.save();
  const showDots = T?.showAgents === true;
  if (showDots) {
    for (const a of state.agents || []) {
      const px = (a.x / bw) * w;
      const py = (a.y / bh) * h;
      ctx.fillStyle = factionColor(a.faction);
      ctx.beginPath();
      ctx.arc(px, py, 2.5, 0, Math.PI * 2);
      ctx.fill();
    }
  }
  if (T && T.s > 0 && bw > 0 && bh > 0) {
    const vl = T.cx - T.cw / (2 * T.s);
    const vr = T.cx + T.cw / (2 * T.s);
    const vt = T.cy - T.ch / (2 * T.s);
    const vb = T.cy + T.ch / (2 * T.s);
    const mx = (x) => clamp(x, 0, bw);
    const my = (y) => clamp(y, 0, bh);
    const left = (mx(vl) / bw) * w;
    const top = (my(vt) / bh) * h;
    const rw = ((mx(vr) - mx(vl)) / bw) * w;
    const rh = ((my(vb) - my(vt)) / bh) * h;
    ctx.strokeStyle = "rgba(61, 219, 255, 0.9)";
    ctx.lineWidth = 1.25;
    ctx.strokeRect(left, top, Math.max(1, rw), Math.max(1, rh));
  }
  ctx.restore();
}

function updateZoomHint(T) {
  const el = document.getElementById("map-zoom-hint");
  const pzl = document.getElementById("pixel-zoom-lbl");
  if (pzl && T) {
    pzl.textContent = `${T.zoom.toFixed(2)}×`;
  }
  if (!el) return;
  if (!T) {
    el.textContent = "";
    return;
  }
  const sims = T.showAgents
    ? "Sims & pins visible at this zoom"
    : "Sims hidden (zoom in)";
  el.textContent = `Scroll · Shift+drag pan · ${T.zoom.toFixed(2)}× · layer ${T.lodLevel} · ${sims}`;
}

function maybeRefreshSelectedAgentCard() {
  if (!selectedAgentId) return;
  const now = Date.now();
  if (now - lastAgentRefreshMs < 1100) return;
  lastAgentRefreshMs = now;
  if (useLocalSim()) {
    const data = window.LocalSim.getAgentFocus(selectedAgentId);
    if (!data) {
      clearAgentCard();
      return;
    }
    const snapAgent = lastState.agents?.find((a) => a.id === selectedAgentId);
    renderAgentCard(data, snapAgent);
    return;
  }
  fetch(`/api/agent/${encodeURIComponent(selectedAgentId)}`)
    .then((r) => {
      if (r.status === 404) {
        clearAgentCard();
        return null;
      }
      return r.ok ? r.json() : null;
    })
    .then((data) => {
      if (!data || data.id !== selectedAgentId) return;
      const snapAgent = lastState.agents?.find((a) => a.id === selectedAgentId);
      renderAgentCard(data, snapAgent);
    })
    .catch(() => {});
}

function renderAgentCard(data, snapAgent) {
  const card = document.getElementById("agent-card");
  const hint = document.getElementById("focus-hint");
  if (!card) return;
  card.classList.remove("empty");
  const v = data.vitals || {};
  const stress = Math.round(v.stress ?? 0);
  const fear = Math.round(v.fear ?? 0);
  const loyalty = Math.round(v.loyalty ?? 0);
  const health = Math.round(v.health ?? 0);
  const facName = data.faction?.id ? titleCaseFaction(data.faction.id) : "—";
  const loc = snapAgent
    ? `(${Math.round(snapAgent.x)}, ${Math.round(snapAgent.y)})`
    : "—";
  const occ = escapeHtml(data.occupation || "Traveler");

  card.innerHTML = `
    <div class="name-row">
      <strong>${escapeHtml(data.name)}</strong>
      <span class="faction-tag">${escapeHtml(facName)}</span>
    </div>
    <div class="bar-row">
      <label><span>Stress</span><span>${stress}%</span></label>
      <div class="bar-track"><div class="bar-fill stress" style="width:${stress}%"></div></div>
    </div>
    <div class="bar-row">
      <label><span>Fear</span><span>${fear}%</span></label>
      <div class="bar-track"><div class="bar-fill fear" style="width:${fear}%"></div></div>
    </div>
    <div class="bar-row">
      <label><span>Loyalty</span><span>${loyalty}%</span></label>
      <div class="bar-track"><div class="bar-fill loyalty" style="width:${loyalty}%"></div></div>
    </div>
    <div class="bar-row">
      <label><span>Health</span><span>${health}%</span></label>
      <div class="bar-track"><div class="bar-fill health" style="width:${health}%"></div></div>
    </div>
    <dl class="stats-dl" style="margin-top:12px">
      <dt>Location</dt><dd>${escapeHtml(loc)}</dd>
      <dt>Occupation</dt><dd>${occ}</dd>
    </dl>
    <button type="button" class="btn-detail" id="btn-agent-details">View details</button>
  `;

  if (hint) hint.textContent = `${data.name} — ${facName}`;

  document.getElementById("btn-agent-details")?.addEventListener("click", () => {
    document.getElementById("focus-panel")?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  });
}

function clearAgentCard() {
  const card = document.getElementById("agent-card");
  const hint = document.getElementById("focus-hint");
  selectedAgentId = null;
  if (card) {
    card.classList.add("empty");
    card.innerHTML = `<p class="muted small">Click the map to inspect someone.</p>`;
  }
  if (hint) hint.textContent = "Select an agent for details —";
}

function updateBookmark(state) {
  const el = document.getElementById("bookmark-panel");
  const bm = state.bookmark;
  if (!bm) {
    el.textContent = "—";
    return;
  }
  el.innerHTML = `Year <strong>${bm.year}</strong>, day <strong>${bm.day}</strong>${
    bm.summary ? `<br/><span class="muted">${escapeHtml(bm.summary)}</span>` : ""
  }`;
}

function updateReplayControls(state) {
  const rep = state.replay || {};
  const n = rep.count || 0;
  const max = Math.max(0, n - 1);
  const slider = document.getElementById("replay-slider");
  const live = document.getElementById("live-mode")?.checked;
  slider.max = String(max);
  slider.disabled = live || n === 0;
  document.getElementById("replay-max").textContent = String(Math.max(0, n - 1));
  if (live) {
    slider.value = String(max);
  }
  document.getElementById("replay-idx").textContent = slider.value;
}

function updateStats(state) {
  const st = state.stats || {};
  const dl = document.getElementById("stats-dl");
  const dom = document.getElementById("dom-ideology");
  const time = state.time || {};
  dl.innerHTML = `
    <dt>Year / day</dt><dd>${time.year ?? "?"} / ${time.day ?? "?"}</dd>
    <dt>Population</dt><dd>${st.population ?? 0}</dd>
    <dt>Factions</dt><dd>${st.faction_count ?? 0}</dd>
    <dt>War signals</dt><dd>${st.active_war_signals ?? 0}</dd>
    <dt>Stability</dt><dd>${st.stability ?? "—"}%</dd>
    <dt>Era hint</dt><dd>${state.era_hint || "—"}</dd>
    <dt>Simulation</dt><dd>${state.sim_running === false ? "stopped" : "on"} · ${
      state.paused ? "paused" : "running"
    } · ${state.speed ?? 1}×</dd>
    <dt>Replay frames</dt><dd>${state.replay?.count ?? 0} stored</dd>
  `;
  const di = st.dominant_ideology || {};
  dom.innerHTML = Object.entries(di)
    .map(([k, v]) => `<li><strong>${k}</strong>: ${v}</li>`)
    .join("");
}

function updateTimeline(state) {
  const strip = document.getElementById("timeline-strip");
  if (!strip) return;
  const evs = state.timeline || [];
  if (!evs.length) {
    strip.innerHTML = `<div class="timeline-empty muted small">No timeline entries yet. Start the sim (<strong>▶</strong> if stopped), un-pause, and use <strong>Macros</strong> to log events. Turn on <strong>Live feed</strong> to refresh.</div>`;
    return;
  }
  strip.innerHTML = evs
    .slice(-16)
    .reverse()
    .map((e) => {
      const yd = `y${e.year ?? "?"} d${e.day ?? "?"}`;
      const sumEnc = encodeURIComponent((e.summary || "").slice(0, 160));
      return `<div class="timeline-chip" role="button" tabindex="0" data-year="${
        e.year ?? ""
      }" data-day="${e.day ?? ""}" data-sum="${sumEnc}" data-idx="${
        e.event_index ?? ""
      }">
        <span class="muted">${escapeHtml(yd)}</span>
        <span class="k">${escapeHtml(e.kind || "?")}</span> · ${escapeHtml(
        (e.summary || "").slice(0, 100)
      )}
      </div>`;
    })
    .join("");

  strip.querySelectorAll(".timeline-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      const yr = chip.getAttribute("data-year");
      const day = chip.getAttribute("data-day");
      let summary = "";
      try {
        summary = decodeURIComponent(chip.getAttribute("data-sum") || "");
      } catch (_) {}
      const event_index = chip.getAttribute("data-idx");
      if (!yr || !day) return;
      if (useLocalSim()) {
        window.LocalSim.setBookmark(
          parseInt(yr, 10),
          parseInt(day, 10),
          summary,
          event_index ? parseInt(event_index, 10) : undefined
        );
        void refreshSnapshotFromServer();
      } else {
        fetch("/api/bookmark", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            year: parseInt(yr, 10),
            day: parseInt(day, 10),
            summary,
            event_index: event_index ? parseInt(event_index, 10) : undefined,
          }),
        })
          .catch(() => {})
          .finally(() => refreshSnapshotFromServer());
      }
      strip.querySelectorAll(".timeline-chip").forEach((c) => c.classList.remove("selected"));
      chip.classList.add("selected");
    });
  });
}

function escapeHtml(s) {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

async function loadFocus(agentId) {
  selectedAgentId = agentId;
  lastAgentRefreshMs = Date.now();
  const panel = document.getElementById("focus-panel");
  panel.innerHTML = "<p>Loading…</p>";
  try {
    let data = null;
    if (useLocalSim()) {
      data = window.LocalSim.getAgentFocus(agentId);
    } else {
      const r = await fetch(`/api/agent/${encodeURIComponent(agentId)}`);
      if (!r.ok) {
        clearAgentCard();
        panel.innerHTML = "<p class='muted'>Agent not found.</p>";
        return;
      }
      data = await r.json();
    }
    if (!data) {
      clearAgentCard();
      panel.innerHTML = "<p class='muted'>Agent not found.</p>";
      return;
    }
    const beliefs = data.beliefs || {};
    const belLines = Object.entries(beliefs)
      .map(([k, v]) => `${k}: ${Math.round(v)}`)
      .join("\n");
    panel.innerHTML = `
      <p><strong>${escapeHtml(data.name)}</strong> <span class="muted">${escapeHtml(
        data.id
      )}</span></p>
      <p class="muted">Status ${data.status} · Hunger ${Math.round(data.hunger)}</p>
      <p><strong>Beliefs</strong></p><pre>${escapeHtml(belLines)}</pre>
      <p><strong>Recent memory</strong></p><pre>${escapeHtml(
        (data.memory_recent || []).join("\n") || "—"
      )}</pre>
      <p><strong>Faction</strong></p><pre>${escapeHtml(
        JSON.stringify(data.faction || {}, null, 2)
      )}</pre>
    `;
    const snapAgent = lastState.agents?.find((a) => a.id === agentId);
    renderAgentCard(data, snapAgent);
  } catch {
    clearAgentCard();
    panel.innerHTML = "<p class='muted'>Could not load agent.</p>";
  }
}

function refreshDashboard(state) {
  updateTopBar(state);
  populateLegend(state);
  updateResourceGrid(state);
  updateEventLog(state);
  updateEraStrip(state);
  updateStats(state);
  updateBookmark(state);
  updateReplayControls(state);
  updateTimeline(state);
  maybeRefreshSelectedAgentCard();
  drawMinimap(state, lastMapTransform);
}

function setup() {
  const canvas = document.getElementById("world-canvas");
  const ctx = canvas.getContext("2d");
  const om = new OverlayManager();
  let transform = null;

  if (typeof PixelTerrainMap !== "undefined") {
    try {
      pixelTerrainApi = PixelTerrainMap.create();
    } catch (_) {
      pixelTerrainApi = null;
    }
  }

  const view = { cx: 1600, cy: 1600, zoom: 1, targetZoom: 1 };
  let viewBoundsInitialized = false;

  function syncViewToSnapshotBounds() {
    const b = lastState.world_bounds || { width: 3200, height: 3200 };
    if (!viewBoundsInitialized && b.width > 0 && b.height > 0) {
      view.cx = b.width / 2;
      view.cy = b.height / 2;
      view.zoom = 1;
      view.targetZoom = 1;
      viewBoundsInitialized = true;
    }
  }

  let terrainPrefetchBusy = false;
  function scheduleTerrainPrefetch() {
    if (pixelTerrainApi) return;
    if (terrainPrefetchBusy || !transform) return;
    if (!terrainTilesMissing(transform)) return;
    terrainPrefetchBusy = true;
    terrainFetchGen++;
    fetchVisibleTerrainTiles(transform).finally(() => {
      terrainPrefetchBusy = false;
      paint();
    });
  }

  function paint() {
    syncViewToSnapshotBounds();
    transform = renderFrame(
      canvas,
      ctx,
      om,
      lastState,
      document.getElementById("terrain-toggle").checked,
      view
    );
    updateZoomHint(transform);
    drawMinimap(lastState, lastMapTransform);
    scheduleTerrainPrefetch();
  }

  function resize() {
    syncViewToSnapshotBounds();
    const wrap = document.getElementById("map-wrap");
    const dpr = window.devicePixelRatio || 1;
    const w = wrap.clientWidth;
    const h = wrap.clientHeight;
    canvas.width = Math.floor(w * dpr);
    canvas.height = Math.floor(h * dpr);
    canvas.style.width = w + "px";
    canvas.style.height = h + "px";
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    paint();
  }

  function applySnapshot(state) {
    lastState = state;
    syncViewToSnapshotBounds();
    refreshDashboard(state);
    resize();
  }

  refreshSnapshotFromServer = async () => {
    if (useLocalSim()) {
      applySnapshot(window.LocalSim.getSnapshot());
      return;
    }
    try {
      const r = await fetch("/api/snapshot");
      if (r.ok) applySnapshot(await r.json());
    } catch (_) {}
  };

  window.addEventListener("resize", resize);

  function zoomLoop() {
    const prev = view.zoom;
    view.zoom += (view.targetZoom - view.zoom) * ZOOM_LERP;
    if (Math.abs(view.targetZoom - view.zoom) < 0.004) {
      view.zoom = view.targetZoom;
    }
    if (Math.abs(prev - view.zoom) > 1e-5) {
      paint();
    }
    requestAnimationFrame(zoomLoop);
  }
  requestAnimationFrame(zoomLoop);

  canvas.addEventListener(
    "wheel",
    (ev) => {
      ev.preventDefault();
      if (!transform) return;
      const bounds = lastState.world_bounds || { width: 3200, height: 3200 };
      const rect = canvas.getBoundingClientRect();
      const mx = ev.clientX - rect.left;
      const my = ev.clientY - rect.top;
      const before = screenToWorld(ev.clientX, ev.clientY, canvas, transform);
      const factor = ev.deltaY > 0 ? 0.9 : 1.11;
      view.targetZoom = clamp(view.targetZoom * factor, ZOOM_MIN, ZOOM_MAX);
      const Tnew = computeTransform(canvas, bounds, { ...view, zoom: view.targetZoom });
      view.cx = before.wx - (mx - Tnew.ox) / Tnew.s;
      view.cy = before.wy - (my - Tnew.oy) / Tnew.s;
      view.cx = clamp(view.cx, 0, bounds.width);
      view.cy = clamp(view.cy, 0, bounds.height);
    },
    { passive: false }
  );

  let panning = false;
  let panLastX = 0;
  let panLastY = 0;
  let panDist = 0;
  let suppressNextClick = false;

  canvas.addEventListener("pointerdown", (ev) => {
    const pan = ev.button === 1 || (ev.button === 0 && ev.shiftKey);
    if (!pan || !transform) return;
    ev.preventDefault();
    panning = true;
    panDist = 0;
    suppressNextClick = false;
    panLastX = ev.clientX;
    panLastY = ev.clientY;
    canvas.setPointerCapture(ev.pointerId);
  });

  canvas.addEventListener("pointermove", (ev) => {
    if (!panning || !transform) return;
    const bounds = lastState.world_bounds || { width: 3200, height: 3200 };
    const dx = ev.clientX - panLastX;
    const dy = ev.clientY - panLastY;
    panDist += Math.abs(dx) + Math.abs(dy);
    panLastX = ev.clientX;
    panLastY = ev.clientY;
    view.cx -= dx / transform.s;
    view.cy -= dy / transform.s;
    view.cx = clamp(view.cx, 0, bounds.width);
    view.cy = clamp(view.cy, 0, bounds.height);
    paint();
  });

  function endPan(ev) {
    if (panning) {
      if (panDist > 8) suppressNextClick = true;
      panning = false;
      panDist = 0;
      try {
        canvas.releasePointerCapture(ev.pointerId);
      } catch (_) {}
    }
  }
  canvas.addEventListener("pointerup", endPan);
  canvas.addEventListener("pointercancel", endPan);

  document.getElementById("pixel-zi")?.addEventListener("click", () => {
    view.targetZoom = clamp(view.targetZoom * 1.35, ZOOM_MIN, ZOOM_MAX);
  });
  document.getElementById("pixel-zo")?.addEventListener("click", () => {
    view.targetZoom = clamp(view.targetZoom / 1.35, ZOOM_MIN, ZOOM_MAX);
  });

  canvas.addEventListener("mousemove", (ev) => {
    const tt = document.getElementById("pixel-terrain-tt");
    if (!pixelTerrainApi || !transform || !tt) return;
    if (panning) {
      tt.style.display = "none";
      return;
    }
    const { wx, wy } = screenToWorld(ev.clientX, ev.clientY, canvas, transform);
    const bw = lastState.world_bounds?.width || 3200;
    const bh = lastState.world_bounds?.height || 3200;
    const s = pixelTerrainApi.sampleAtWorld(wx, wy, bw, bh);
    if (!s) {
      tt.style.display = "none";
      return;
    }
    let html = `${s.biome}<br/>elev ${s.elev.toFixed(2)} · mois ${s.mois.toFixed(2)}`;
    if (s.objectLabel) html += `<br/>${s.objectLabel}`;
    tt.innerHTML = html;
    tt.style.display = "block";
  });

  document.querySelectorAll("[data-overlay]").forEach((el) => {
    el.addEventListener("change", () => {
      const name = el.getAttribute("data-overlay");
      om.toggle(name, el.checked);
      resize();
    });
  });

  document.getElementById("terrain-toggle").addEventListener("change", resize);

  const foundersCb = document.getElementById("founders-mode");
  if (foundersCb) {
    foundersCb.addEventListener("change", () => {
      document.body.classList.toggle("founders-mode-cursor", foundersCb.checked);
    });
  }

  async function postFoundersAt(wx, wy) {
    const hint = document.getElementById("founders-hint");
    if (useLocalSim()) {
      const hasXY = Number.isFinite(wx) && Number.isFinite(wy);
      const cx = hasXY ? wx : 1600;
      const cy = hasXY ? wy : 1600;
      const j = window.LocalSim.spawnFoundersAt(cx, cy);
      if (foundersCb) foundersCb.checked = false;
      document.body.classList.remove("founders-mode-cursor");
      if (hint) {
        hint.textContent = j.ok
          ? "Founders placed — using local sim sprites (idle / walk / swim). Un-pause to advance years."
          : j.message || "Could not place.";
      }
      await refreshSnapshotFromServer();
      return;
    }
    const hasXY = Number.isFinite(wx) && Number.isFinite(wy);
    const payload = hasXY ? { x: wx, y: wy } : {};
    const tryUrls = ["/api/founders", "/api/world/founders"];
    try {
      let r = null;
      for (const url of tryUrls) {
        r = await fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        if (r.status !== 404) break;
      }
      if (!r) return;
      let j = {};
      try {
        j = await r.json();
      } catch (_) {
        if (hint) {
          hint.textContent =
            r.status === 404
              ? "API not found (404). Use local mode (this build) or run the Python dashboard."
              : `Server returned ${r.status} (non-JSON body).`;
        }
        return;
      }
      if (foundersCb) foundersCb.checked = false;
      document.body.classList.remove("founders-mode-cursor");
      if (hint) {
        if (!j.ok) {
          hint.textContent = j.message || j.error || `Could not place (${r.status})`;
        } else {
          hint.textContent = "Founders placed — simulation clock started. Timeline will show new events as time runs.";
        }
      }
    } catch (e) {
      if (hint) {
        hint.textContent = "Network error while contacting server API.";
      }
    }
    await refreshSnapshotFromServer();
  }

  document.getElementById("btn-pause").addEventListener("click", async () => {
    if (useLocalSim()) {
      window.LocalSim.togglePause();
    } else {
      await fetch("/api/sim/pause", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ toggle: true }),
      });
    }
    await refreshSnapshotFromServer();
  });

  document.getElementById("btn-run").addEventListener("click", async () => {
    if (useLocalSim()) {
      window.LocalSim.setRun();
    } else {
      await fetch("/api/sim/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ running: true }),
      });
    }
    await refreshSnapshotFromServer();
  });

  const speedRange = document.getElementById("speed-range");
  const speedVal = document.getElementById("speed-val");
  speedRange.addEventListener("input", () => {
    speedVal.textContent = `${parseInt(speedRange.value, 10)}×`;
  });
  speedRange.addEventListener("change", async () => {
    const v = parseInt(speedRange.value, 10);
    speedVal.textContent = `${v}×`;
    if (useLocalSim()) {
      window.LocalSim.setSpeed(v);
    } else {
      await fetch("/api/sim/speed", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ speed: v }),
      });
    }
    await refreshSnapshotFromServer();
  });

  document.querySelectorAll("[data-event]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const type = btn.getAttribute("data-event");
      if (useLocalSim()) {
        window.LocalSim.runMacro(type);
      } else {
        await fetch("/api/event", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ type }),
        });
      }
      await refreshSnapshotFromServer();
    });
  });

  document.getElementById("btn-founders-center")?.addEventListener("click", (ev) => {
    ev.preventDefault();
    void postFoundersAt();
  });

  canvas.addEventListener("click", async (ev) => {
    const T = getActiveMapTransform(canvas, view, lastState, transform);
    const placeFounders = !!foundersCb?.checked;
    if (suppressNextClick && !placeFounders) {
      suppressNextClick = false;
      return;
    }
    if (suppressNextClick) suppressNextClick = false;

    const { wx, wy } = screenToWorld(ev.clientX, ev.clientY, canvas, T);
    if (placeFounders) {
      await postFoundersAt(wx, wy);
      return;
    }
    if (!T.showAgents || !lastState.agents?.length) return;
    const pickR = Math.max(40 / T.s, 18 / T.s);
    let best = null;
    let bestD = pickR;
    for (const a of lastState.agents) {
      const d = Math.hypot(a.x - wx, a.y - wy);
      if (d < bestD) {
        bestD = d;
        best = a;
      }
    }
    if (best) loadFocus(best.id);
  });

  document.getElementById("btn-settings")?.addEventListener("click", () => {
    document.getElementById("panel-left")?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  });

  let pollTimer = null;
  let wsConn = null;

  function stopPoll() {
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  }

  function startPoll() {
    stopPoll();
    pollTimer = setInterval(async () => {
      const live = document.getElementById("live-mode")?.checked;
      if (!live) return;
      if (useLocalSim()) {
        window.LocalSim.onPoll(480);
        applySnapshot(window.LocalSim.getSnapshot());
        return;
      }
      try {
        const r = await fetch("/api/snapshot");
        const s = await r.json();
        applySnapshot(s);
      } catch (_) {}
    }, 480);
  }

  async function loadReplayFrame(i) {
    if (useLocalSim()) {
      lastState = window.LocalSim.getSnapshot();
      refreshDashboard(lastState);
      resize();
      document.getElementById("replay-idx").textContent = "0";
      return;
    }
    try {
      const r = await fetch(`/api/replay/frame?i=${i}`);
      if (!r.ok) return;
      const fr = await r.json();
      lastState = fr;
      refreshDashboard(fr);
      resize();
      document.getElementById("replay-idx").textContent = String(i);
    } catch (_) {}
  }

  document.getElementById("live-mode")?.addEventListener("change", (ev) => {
    const on = ev.target.checked;
    if (on) {
      if (wsConn && wsConn.readyState === WebSocket.OPEN) {
        stopPoll();
      } else {
        stopPoll();
        startPoll();
      }
    } else {
      const slider = document.getElementById("replay-slider");
      loadReplayFrame(parseInt(slider.value, 10) || 0);
    }
  });

  document.getElementById("replay-slider")?.addEventListener("input", (ev) => {
    if (document.getElementById("live-mode")?.checked) return;
    const i = parseInt(ev.target.value, 10) || 0;
    loadReplayFrame(i);
  });

  document.getElementById("btn-replay-clear")?.addEventListener("click", async () => {
    if (useLocalSim()) {
      applySnapshot(window.LocalSim.getSnapshot());
    } else {
      await fetch("/api/replay/clear", { method: "POST" });
      const r = await fetch("/api/snapshot");
      if (r.ok) applySnapshot(await r.json());
    }
  });

  loadSimSprites();
  window.addEventListener("sims-sprites-ready", () => {
    try {
      resize();
    } catch (_) {}
  });

  if (!useLocalSim()) {
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${proto}//${window.location.host}/ws`;
    function connectWs() {
      try {
        wsConn = new WebSocket(wsUrl);
      } catch (_) {
        startPoll();
        return;
      }
      wsConn.onopen = () => {
        stopPoll();
      };
      wsConn.onmessage = (ev) => {
        try {
          if (!document.getElementById("live-mode")?.checked) return;
          applySnapshot(JSON.parse(ev.data));
        } catch (_) {}
      };
      wsConn.onerror = () => {
        startPoll();
      };
      wsConn.onclose = () => {
        startPoll();
        setTimeout(connectWs, 3000);
      };
    }
    connectWs();
    setTimeout(() => {
      if (!wsConn || wsConn.readyState !== WebSocket.OPEN) startPoll();
    }, 900);
    fetch("/api/snapshot")
      .then((r) => r.json())
      .then(applySnapshot)
      .catch(() => {
        applySnapshot(lastState);
      });
  } else {
    applySnapshot(window.LocalSim.getSnapshot());
    startPoll();
  }

  resize();
}

async function boot() {
  window.__CIV_USE_SERVER = false;
  const params = new URLSearchParams(window.location.search);
  const forceLocal = params.get("local") === "1";
  if (!forceLocal) {
    try {
      const r = await fetch("/api/snapshot", { cache: "no-store" });
      if (r.ok) {
        window.__CIV_USE_SERVER = true;
      }
    } catch (_) {}
  }
  if (!window.__CIV_USE_SERVER) {
    await new Promise((resolve) => {
      const s = document.createElement("script");
      s.src = "assets/local_sim.js";
      s.onload = resolve;
      s.onerror = () => resolve();
      document.head.appendChild(s);
    });
  }
  setup();
}

document.addEventListener("DOMContentLoaded", () => {
  void boot();
});
