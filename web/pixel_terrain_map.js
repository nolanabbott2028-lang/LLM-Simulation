/**
 * Pixel Terrain Map — procedural 256×256 elevation/moisture biomes + objects.
 * Renders scaled to simulation world_bounds; integrates with dashboard camera (T).
 */
(function () {
  const W = 256;
  const H = 256;

  function rng32(s) {
    return function () {
      s |= 0;
      s = (s + 0x6d2b79f5) | 0;
      var t = Math.imul(s ^ (s >>> 15), 1 | s);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return (((t ^ (t >>> 14)) >>> 0) / 4294967296);
    };
  }

  function noise2D(rng, Wo, Ho, scale, oct) {
    const b = new Float32Array(Wo * Ho);
    for (let i = 0; i < Wo * Ho; i++) b[i] = rng() * 2 - 1;
    function s(x, y) {
      x = ((x % Wo) + Wo) % Wo;
      y = ((y % Ho) + Ho) % Ho;
      return b[y * Wo + x];
    }
    function sm(x, y) {
      const xi = Math.floor(x),
        yi = Math.floor(y),
        xf = x - xi,
        yf = y - yi;
      const t = (v) => v * v * (3 - 2 * v);
      return (
        s(xi, yi) * (1 - t(xf)) * (1 - t(yf)) +
        s(xi + 1, yi) * t(xf) * (1 - t(yf)) +
        s(xi, yi + 1) * (1 - t(xf)) * t(yf) +
        s(xi + 1, yi + 1) * t(xf) * t(yf)
      );
    }
    const out = new Float32Array(Wo * Ho);
    let amp = 1,
      freq = 1 / scale,
      mv = 0;
    for (let o = 0; o < oct; o++) {
      for (let y = 0; y < Ho; y++)
        for (let x = 0; x < Wo; x++)
          out[y * Wo + x] += sm(x * freq, y * freq) * amp;
      mv += amp;
      amp *= 0.5;
      freq *= 2;
    }
    for (let i = 0; i < Wo * Ho; i++) out[i] /= mv;
    return out;
  }

  function lerp(a, b, t) {
    t = Math.max(0, Math.min(1, t));
    return a + (b - a) * t;
  }
  function lc(c1, c2, t) {
    return [
      Math.round(lerp(c1[0], c2[0], t)),
      Math.round(lerp(c1[1], c2[1], t)),
      Math.round(lerp(c1[2], c2[2], t)),
    ];
  }

  const C = {
    dw: [18, 45, 78],
    w: [30, 95, 152],
    sw: [45, 130, 185],
    sh: [190, 172, 102],
    sand: [210, 195, 130],
    pl: [74, 138, 44],
    gr: [58, 112, 32],
    fo: [30, 92, 18],
    df: [18, 65, 10],
    hi: [122, 140, 106],
    rk: [138, 122, 104],
    mt: [120, 108, 95],
    pk: [168, 158, 143],
    sn: [224, 220, 214],
  };

  function biome(e, m) {
    if (e < -0.38) return lc(C.dw, C.w, (e + 0.55) / 0.17);
    if (e < -0.06) return lc(C.w, C.sw, (e + 0.38) / 0.32);
    if (e < 0.01) return lc(C.sw, C.sh, (e + 0.06) / 0.07);
    if (e < 0.06) return lc(C.sh, C.sand, (e - 0.01) / 0.05);
    if (e < 0.16) {
      const t = (e - 0.06) / 0.1;
      return m > 0.1 ? lc(C.gr, C.pl, t) : lc(C.sand, C.pl, t);
    }
    if (e < 0.4) {
      const t = (e - 0.16) / 0.24;
      return m > 0.15 ? lc(C.fo, C.df, t * Math.min(1, m)) : lc(C.pl, C.gr, t);
    }
    if (e < 0.54) return lc(C.hi, C.rk, (e - 0.4) / 0.14);
    if (e < 0.72) return lc(C.rk, C.mt, (e - 0.54) / 0.18);
    if (e < 0.86) return lc(C.mt, C.pk, (e - 0.72) / 0.14);
    return lc(C.pk, C.sn, (e - 0.86) / 0.14);
  }

  function bname(e, m) {
    if (e < -0.38) return "Deep ocean";
    if (e < -0.06) return "Ocean";
    if (e < 0.01) return "Shallow water";
    if (e < 0.06) return "Shore";
    if (e < 0.16) return "Plains";
    if (e < 0.4) return m > 0.15 ? "Forest" : "Grassland";
    if (e < 0.54) return "Highland";
    if (e < 0.72) return "Mountain";
    if (e < 0.86) return "Peak";
    return "Snow cap";
  }

  const OAK = 0,
    PINE = 1,
    BIRCH = 2,
    ROCK_SM = 3,
    ROCK_LG = 4,
    BUSH = 5,
    FRUIT_BUSH = 6,
    ORE = 7,
    FLOWER = 8,
    MUSHROOM = 9,
    DEAD_TREE = 10,
    CACTUS = 11;

  const OBJ_NAMES = [
    "oak tree",
    "pine tree",
    "birch tree",
    "small rock",
    "large rock",
    "bush",
    "fruit bush",
    "ore deposit",
    "flower",
    "mushroom",
    "dead tree",
    "cactus",
  ];

  function objName(t) {
    return OBJ_NAMES[t] || "unknown";
  }

  function pr(ctx, color, x, y, w, h) {
    ctx.fillStyle = color;
    ctx.fillRect(x, y, w, h);
  }

  function drawOak(ctx, px, py, sz, v) {
    const rng = rng32(Math.floor(v * 999999));
    const tw = Math.max(2, Math.round(sz * 0.18));
    const th = Math.max(2, Math.round(sz * 0.38));
    pr(ctx, "#5c3317", px + Math.round(sz * 0.41), py + Math.round(sz * 0.55), tw, th);
    const layers = [
      { y: 0.06, w: 0.28, c: "#1a5c0a" },
      { y: 0.14, w: 0.4, c: "#227010" },
      { y: 0.24, w: 0.5, c: "#2a8014" },
      { y: 0.34, w: 0.44, c: "#1e6a0c" },
      { y: 0.44, w: 0.32, c: "#175508" },
    ];
    for (const l of layers) {
      const lx = Math.round(px + sz * (0.5 - l.w / 2));
      const ly = Math.round(py + sz * l.y);
      const lw = Math.round(sz * l.w);
      const lh = Math.max(2, Math.round(sz * 0.13));
      pr(ctx, l.c, lx, ly, lw, lh);
      if (sz >= 8 && rng() > 0.5)
        pr(
          ctx,
          "#33a018",
          lx + Math.round(lw * 0.2),
          ly - Math.round(lh * 0.5),
          Math.round(lw * 0.35),
          Math.round(lh * 0.5)
        );
    }
    if (sz >= 6)
      pr(
        ctx,
        "rgba(0,0,0,0.25)",
        px + Math.round(sz * 0.55),
        py + Math.round(sz * 0.1),
        Math.round(sz * 0.12),
        Math.round(sz * 0.35)
      );
  }

  function drawPine(ctx, px, py, sz, v) {
    const tw = Math.max(1, Math.round(sz * 0.12));
    const th = Math.max(2, Math.round(sz * 0.3));
    pr(ctx, "#4a2a0e", px + Math.round(sz * 0.44), py + Math.round(sz * 0.65), tw, th);
    const tiers = [
      { y: 0.05, w: 0.18, c: "#0d4a08" },
      { y: 0.14, w: 0.28, c: "#0e5a09" },
      { y: 0.24, w: 0.38, c: "#126e0c" },
      { y: 0.36, w: 0.46, c: "#167a0f" },
      { y: 0.5, w: 0.52, c: "#0d5a08" },
    ];
    for (const t of tiers) {
      const lx = Math.round(px + sz * (0.5 - t.w / 2));
      const ly = Math.round(py + sz * t.y);
      const lw = Math.round(sz * t.w);
      const lh = Math.max(2, Math.round(sz * 0.14));
      pr(ctx, t.c, lx, ly, lw, lh);
    }
    if (sz >= 8)
      pr(
        ctx,
        "rgba(0,0,0,0.2)",
        px + Math.round(sz * 0.54),
        py + Math.round(sz * 0.08),
        Math.round(sz * 0.08),
        Math.round(sz * 0.5)
      );
  }

  function drawBirch(ctx, px, py, sz, v) {
    const tw = Math.max(1, Math.round(sz * 0.14));
    const th = Math.max(2, Math.round(sz * 0.42));
    const tx = px + Math.round(sz * 0.43);
    const ty = py + Math.round(sz * 0.5);
    pr(ctx, "#d8d0c0", tx, ty, tw, th);
    if (sz >= 6) {
      pr(ctx, "#888078", tx, ty + Math.round(th * 0.25), tw, Math.max(1, Math.round(sz * 0.04)));
      pr(ctx, "#888078", tx, ty + Math.round(th * 0.55), tw, Math.max(1, Math.round(sz * 0.04)));
    }
    const heads = ["#3a8c1a", "#2e7814", "#44a020", "#386010"];
    for (let i = 0; i < 4; i++) {
      const rng = rng32(Math.floor(v * 77777 + i * 1111));
      const hx = px + Math.round((0.1 + rng() * 0.6) * sz);
      const hy = py + Math.round((0.05 + rng() * 0.35) * sz);
      const hw = Math.max(2, Math.round(sz * (0.12 + rng() * 0.1)));
      pr(ctx, heads[i % 4], hx, hy, hw, hw);
    }
  }

  function drawDeadTree(ctx, px, py, sz, v) {
    const tw = Math.max(1, Math.round(sz * 0.12));
    const th = Math.max(3, Math.round(sz * 0.7));
    pr(ctx, "#5a4030", px + Math.round(sz * 0.44), py + Math.round(sz * 0.2), tw, th);
    const bw = Math.max(2, Math.round(sz * 0.22));
    pr(ctx, "#4e3828", px + Math.round(sz * 0.22), py + Math.round(sz * 0.28), bw, Math.max(1, Math.round(sz * 0.08)));
    pr(ctx, "#4e3828", px + Math.round(sz * 0.5), py + Math.round(sz * 0.35), bw, Math.max(1, Math.round(sz * 0.08)));
  }

  function drawRockSm(ctx, px, py, sz, v) {
    const rx = px + Math.round(sz * 0.15),
      ry = py + Math.round(sz * 0.45);
    const rw = Math.max(3, Math.round(sz * 0.55)),
      rh = Math.max(2, Math.round(sz * 0.38));
    pr(ctx, "#7a7268", rx, ry, rw, rh);
    pr(ctx, "#6a6258", rx + Math.round(rw * 0.4), ry + Math.round(rh * 0.35), Math.round(rw * 0.55), Math.round(rh * 0.65));
    if (sz >= 6) {
      pr(ctx, "#9a9288", rx + Math.round(rw * 0.1), ry, Math.round(rw * 0.35), Math.round(rh * 0.4));
      pr(ctx, "rgba(0,0,0,0.3)", rx + Math.round(rw * 0.6), ry + Math.round(rh * 0.5), Math.round(rw * 0.25), Math.round(rh * 0.35));
    }
  }

  function drawRockLg(ctx, px, py, sz, v) {
    const rx = px + Math.round(sz * 0.05),
      ry = py + Math.round(sz * 0.3);
    const rw = Math.max(4, Math.round(sz * 0.8)),
      rh = Math.max(3, Math.round(sz * 0.55));
    pr(ctx, "#6e6660", rx, ry, rw, rh);
    pr(ctx, "#5c5650", rx + Math.round(rw * 0.35), ry + Math.round(rh * 0.4), Math.round(rw * 0.6), Math.round(rh * 0.6));
    pr(ctx, "#888078", rx + Math.round(rw * 0.05), ry, Math.round(rw * 0.45), Math.round(rh * 0.35));
    if (sz >= 8) {
      pr(ctx, "#7e7870", rx + Math.round(rw * 0.55), ry + Math.round(rh * 0.1), Math.round(rw * 0.3), Math.round(rh * 0.25));
      pr(
        ctx,
        "rgba(0,0,0,0.22)",
        rx + Math.round(rw * 0.55),
        ry + Math.round(rh * 0.38),
        Math.round(rw * 0.35),
        Math.round(rh * 0.4)
      );
      pr(
        ctx,
        "rgba(255,255,255,0.1)",
        rx + Math.round(rw * 0.08),
        ry + Math.round(rh * 0.05),
        Math.round(rw * 0.25),
        Math.round(rh * 0.12)
      );
    }
  }

  function drawBush(ctx, px, py, sz, v) {
    const bx = px + Math.round(sz * 0.08),
      by = py + Math.round(sz * 0.45);
    const bw = Math.max(3, Math.round(sz * 0.75)),
      bh = Math.max(2, Math.round(sz * 0.4));
    pr(ctx, "#2d7a18", bx, by, bw, bh);
    pr(ctx, "#227010", bx + Math.round(bw * 0.5), by + Math.round(bh * 0.35), Math.round(bw * 0.45), Math.round(bh * 0.65));
    if (sz >= 6) {
      pr(ctx, "#38901e", bx + Math.round(bw * 0.05), by - Math.round(sz * 0.06), Math.round(bw * 0.38), Math.round(sz * 0.12));
      pr(ctx, "#38901e", bx + Math.round(bw * 0.5), by - Math.round(sz * 0.08), Math.round(bw * 0.35), Math.round(sz * 0.14));
    }
  }

  function drawFruitBush(ctx, px, py, sz, v) {
    const rng = rng32(Math.floor(v * 55555));
    drawBush(ctx, px, py, sz, v);
    const fruits = sz >= 6 ? 5 : 2;
    const fcolors = ["#c0392b", "#e74c3c", "#922b21", "#d35400", "#8e44ad"];
    for (let i = 0; i < fruits; i++) {
      const fx = px + Math.round((0.15 + rng() * 0.65) * sz);
      const fy = py + Math.round((0.38 + rng() * 0.25) * sz);
      pr(ctx, fcolors[Math.floor(rng() * fcolors.length)], fx, fy, Math.max(2, Math.round(sz * 0.1)), Math.max(2, Math.round(sz * 0.1)));
    }
  }

  function drawOre(ctx, px, py, sz, v) {
    drawRockLg(ctx, px, py, sz, v);
    const oreColors = ["#8B6914", "#c0a030", "#4a90a0", "#7a3c8a"];
    const oc2 = oreColors[Math.floor(v * 4) % 4];
    const spots = sz >= 8 ? 4 : 2;
    const rng = rng32(Math.floor(v * 33333));
    for (let i = 0; i < spots; i++) {
      const sx = px + Math.round((0.2 + rng() * 0.5) * sz);
      const sy = py + Math.round((0.35 + rng() * 0.3) * sz);
      pr(ctx, oc2, sx, sy, Math.max(2, Math.round(sz * 0.1)), Math.max(2, Math.round(sz * 0.1)));
    }
  }

  function drawFlower(ctx, px, py, sz, v) {
    const rng = rng32(Math.floor(v * 22222));
    pr(ctx, "#3a8c1a", px + Math.round(sz * 0.45), py + Math.round(sz * 0.6), Math.max(1, Math.round(sz * 0.1)), Math.max(2, Math.round(sz * 0.28)));
    const pcolors = ["#e8d44d", "#e84393", "#4a9fe8", "#e84a4a", "#e87a1a"];
    const pc = pcolors[Math.floor(rng() * pcolors.length)];
    const fs = Math.max(2, Math.round(sz * 0.18));
    pr(ctx, pc, px + Math.round(sz * 0.38), py + Math.round(sz * 0.44), fs, fs);
    if (sz >= 8) pr(ctx, "#f5f0a0", px + Math.round(sz * 0.42), py + Math.round(sz * 0.47), Math.round(fs * 0.5), Math.round(fs * 0.5));
  }

  function drawMushroom(ctx, px, py, sz, v) {
    const rng = rng32(Math.floor(v * 44444));
    const sw = Math.max(1, Math.round(sz * 0.14));
    const sh = Math.max(2, Math.round(sz * 0.28));
    pr(ctx, "#c8b890", px + Math.round(sz * 0.43), py + Math.round(sz * 0.62), sw, sh);
    const caps = ["#c0392b", "#8e44ad", "#d35400", "#e8b84d"];
    const capC = caps[Math.floor(rng() * caps.length)];
    const cw = Math.max(3, Math.round(sz * 0.42)),
      ch = Math.max(2, Math.round(sz * 0.24));
    pr(ctx, capC, px + Math.round(sz * 0.29), py + Math.round(sz * 0.38), cw, ch);
    if (sz >= 8) {
      pr(ctx, "rgba(255,255,255,0.4)", px + Math.round(sz * 0.32), py + Math.round(sz * 0.4), Math.round(cw * 0.25), Math.round(ch * 0.45));
      pr(ctx, "rgba(255,255,255,0.25)", px + Math.round(sz * 0.55), py + Math.round(sz * 0.41), Math.round(cw * 0.2), Math.round(ch * 0.35));
    }
  }

  function drawCactus(ctx, px, py, sz, v) {
    const tw = Math.max(2, Math.round(sz * 0.2));
    const th = Math.max(3, Math.round(sz * 0.7));
    const tx = px + Math.round(sz * 0.4),
      ty = py + Math.round(sz * 0.2);
    pr(ctx, "#2d7a18", tx, ty, tw, th);
    const aw = Math.max(2, Math.round(sz * 0.18));
    const ah = Math.max(2, Math.round(sz * 0.22));
    pr(ctx, "#2d7a18", px + Math.round(sz * 0.18), ty + Math.round(th * 0.25), aw + tw, ah);
    pr(ctx, "#2d7a18", px + Math.round(sz * 0.55), ty + Math.round(th * 0.4), aw + tw, ah);
    if (sz >= 8) {
      pr(ctx, "#228014", tx + 1, ty + 1, Math.round(tw * 0.4), th - 2);
      pr(ctx, "rgba(0,0,0,0.15)", tx + Math.round(tw * 0.6), ty, Math.round(tw * 0.4), th);
    }
  }

  function drawObject(ctx, obj, px, py, sz) {
    switch (obj.t) {
      case OAK:
        drawOak(ctx, px, py, sz, obj.v);
        break;
      case PINE:
        drawPine(ctx, px, py, sz, obj.v);
        break;
      case BIRCH:
        drawBirch(ctx, px, py, sz, obj.v);
        break;
      case DEAD_TREE:
        drawDeadTree(ctx, px, py, sz, obj.v);
        break;
      case ROCK_SM:
        drawRockSm(ctx, px, py, sz, obj.v);
        break;
      case ROCK_LG:
        drawRockLg(ctx, px, py, sz, obj.v);
        break;
      case BUSH:
        drawBush(ctx, px, py, sz, obj.v);
        break;
      case FRUIT_BUSH:
        drawFruitBush(ctx, px, py, sz, obj.v);
        break;
      case ORE:
        drawOre(ctx, px, py, sz, obj.v);
        break;
      case FLOWER:
        drawFlower(ctx, px, py, sz, obj.v);
        break;
      case MUSHROOM:
        drawMushroom(ctx, px, py, sz, obj.v);
        break;
      case CACTUS:
        drawCactus(ctx, px, py, sz, obj.v);
        break;
      default:
        break;
    }
  }

  function wts(wx, wy, T) {
    const x = (wx - T.cx) * T.s + T.ox;
    const y = (wy - T.cy) * T.s + T.oy;
    return [x, y];
  }

  function createPixelTerrainMap() {
    const elev = noise2D(rng32(0xfaceb00c), W, H, 52, 8);
    const mois = noise2D(rng32(0xbeefdead), W, H, 30, 5);
    const OBJS = new Map();
    const OBJR = rng32(0xc0ffee00);

    for (let y = 0; y < H; y++) {
      for (let x = 0; x < W; x++) {
        const i = y * W + x;
        const e = elev[i],
          m = mois[i];
        const r = OBJR();
        let obj = null;
        if (e >= 0.16 && e < 0.4) {
          if (m > 0.15) {
            if (r < 0.07) obj = { t: OAK, v: OBJR() };
            else if (r < 0.13) obj = { t: PINE, v: OBJR() };
            else if (r < 0.17) obj = { t: BIRCH, v: OBJR() };
            else if (r < 0.2) obj = { t: BUSH, v: OBJR() };
            else if (r < 0.22) obj = { t: FRUIT_BUSH, v: OBJR() };
            else if (r < 0.23) obj = { t: MUSHROOM, v: OBJR() };
            else if (r < 0.235) obj = { t: FLOWER, v: OBJR() };
          } else {
            if (r < 0.025) obj = { t: ROCK_SM, v: OBJR() };
            else if (r < 0.035) obj = { t: FLOWER, v: OBJR() };
            else if (r < 0.04) obj = { t: BUSH, v: OBJR() };
          }
        } else if (e >= 0.4 && e < 0.54) {
          if (r < 0.06) obj = { t: ROCK_SM, v: OBJR() };
          else if (r < 0.1) obj = { t: ROCK_LG, v: OBJR() };
          else if (r < 0.12) obj = { t: ORE, v: OBJR() };
          else if (r < 0.14) obj = { t: PINE, v: OBJR() };
          else if (r < 0.16) obj = { t: DEAD_TREE, v: OBJR() };
        } else if (e >= 0.54 && e < 0.72) {
          if (r < 0.1) obj = { t: ROCK_LG, v: OBJR() };
          else if (r < 0.18) obj = { t: ROCK_SM, v: OBJR() };
          else if (r < 0.21) obj = { t: ORE, v: OBJR() };
        } else if (e >= 0.06 && e < 0.16) {
          if (r < 0.015) obj = { t: ROCK_SM, v: OBJR() };
          else if (r < 0.025) obj = { t: FLOWER, v: OBJR() };
          else if (r < 0.03) obj = { t: CACTUS, v: OBJR() };
        }
        if (obj) OBJS.set(i, obj);
      }
    }

    const offscreen = document.createElement("canvas");
    offscreen.width = W;
    offscreen.height = H;
    const oc = offscreen.getContext("2d");
    const img = oc.createImageData(W, H);
    for (let y = 0; y < H; y++) {
      for (let x = 0; x < W; x++) {
        const i = y * W + x;
        const [r, g, b] = biome(elev[i], mois[i]);
        const pi = i * 4;
        img.data[pi] = r;
        img.data[pi + 1] = g;
        img.data[pi + 2] = b;
        img.data[pi + 3] = 255;
      }
    }
    oc.putImageData(img, 0, 0);

    function sampleAtWorld(wx, wy, bw, bh) {
      const gx = Math.floor((wx / bw) * W);
      const gy = Math.floor((wy / bh) * H);
      if (gx < 0 || gy < 0 || gx >= W || gy >= H) return null;
      const i = gy * W + gx;
      const o = OBJS.get(i);
      return {
        biome: bname(elev[i], mois[i]),
        elev: elev[i],
        mois: mois[i],
        object: o,
        objectLabel: o ? objName(o.t) : null,
      };
    }

    function draw(ctx, T) {
      const bw = T.bw;
      const bh = T.bh;
      const [x0, y0] = wts(0, 0, T);
      const [x1, y1] = wts(bw, bh, T);
      ctx.imageSmoothingEnabled = false;
      ctx.drawImage(offscreen, 0, 0, W, H, x0, y0, x1 - x0, y1 - y0);

      const cellPx = T.s * (bw / W);
      if (cellPx < 4.5) return;

      const vl = T.cx - T.cw / (2 * T.s);
      const vr = T.cx + T.cw / (2 * T.s);
      const vt = T.cy - T.ch / (2 * T.s);
      const vb = T.cy + T.ch / (2 * T.s);
      const sx = Math.max(0, Math.floor((vl / bw) * W));
      const ex = Math.min(W - 1, Math.ceil((vr / bw) * W));
      const sy = Math.max(0, Math.floor((vt / bh) * H));
      const ey = Math.min(H - 1, Math.ceil((vb / bh) * H));

      if (cellPx >= 9) {
        ctx.strokeStyle = "rgba(0,0,0,0.07)";
        ctx.lineWidth = 0.5;
        for (let x = sx; x <= ex + 1; x++) {
          const wx = (x * bw) / W;
          const [vx0, vy0] = wts(wx, (sy * bh) / H, T);
          const [, vy1] = wts(wx, ((ey + 1) * bh) / H, T);
          ctx.beginPath();
          ctx.moveTo(vx0, vy0);
          ctx.lineTo(vx0, vy1);
          ctx.stroke();
        }
        for (let y = sy; y <= ey + 1; y++) {
          const wy = (y * bh) / H;
          const [vx0, vy0] = wts((sx * bw) / W, wy, T);
          const [vx1] = wts(((ex + 1) * bw) / W, wy, T);
          ctx.beginPath();
          ctx.moveTo(vx0, vy0);
          ctx.lineTo(vx1, vy0);
          ctx.stroke();
        }
      }

      for (let y = sy; y <= ey; y++) {
        for (let x = sx; x <= ex; x++) {
          const i = y * W + x;
          const obj = OBJS.get(i);
          if (obj) {
            const wx = (x * bw) / W;
            const wy = (y * bh) / H;
            const [px, py] = wts(wx, wy, T);
            drawObject(ctx, obj, px, py, cellPx);
          }
        }
      }

      if (cellPx >= 15) {
        for (let y = sy; y <= ey; y++) {
          for (let x = sx; x <= ex; x++) {
            const i = y * W + x;
            const e = elev[i];
            const wx0 = (x * bw) / W;
            const wy0 = (y * bh) / H;
            const [ox, oy] = wts(wx0, wy0, T);

            if (e >= -0.06 && e < 0.01) {
              const wx = ox + cellPx * 0.5,
                wy = oy + cellPx * 0.5;
              ctx.strokeStyle = "rgba(160,210,240,0.28)";
              ctx.lineWidth = Math.max(0.5, cellPx * 0.07);
              ctx.beginPath();
              ctx.arc(wx - cellPx * 0.15, wy, cellPx * 0.2, 0.1, Math.PI * 0.9);
              ctx.stroke();
              ctx.beginPath();
              ctx.arc(wx + cellPx * 0.15, wy, cellPx * 0.2, Math.PI * 1.1, Math.PI * 1.9);
              ctx.stroke();
            }
            if (e >= 0.72 && !OBJS.has(i)) {
              const mx = ox + cellPx * 0.5,
                mcy = oy + cellPx * 0.5;
              const mh = cellPx * 0.46,
                mw = cellPx * 0.36;
              ctx.fillStyle = "rgba(255,255,255,0.16)";
              ctx.beginPath();
              ctx.moveTo(mx, mcy - mh);
              ctx.lineTo(mx - mw, mcy + mh * 0.4);
              ctx.lineTo(mx + mw * 0.15, mcy + mh * 0.4);
              ctx.closePath();
              ctx.fill();
              ctx.fillStyle = "rgba(0,0,0,0.18)";
              ctx.beginPath();
              ctx.moveTo(mx, mcy - mh);
              ctx.lineTo(mx + mw, mcy + mh * 0.4);
              ctx.lineTo(mx - mw * 0.15, mcy + mh * 0.4);
              ctx.closePath();
              ctx.fill();
            }
          }
        }
      }
    }

    return { draw, sampleAtWorld, gridW: W, gridH: H };
  }

  window.PixelTerrainMap = { create: createPixelTerrainMap };
})();
