/**
 * Client-only world state (no HTTP). Replaces /api/snapshot and sim control endpoints.
 * Adam & Eve are added here; the map uses the same sim sprites as the Pygame build (assets/sims/*).
 */
(function (global) {
  const WORLD_W = 3200;
  const WORLD_H = 3200;
  const TILE = 32;
  const MS_PER_SIM_DAY = 3200;

  let eventIndex = 0;
  let timeAccumMs = 0;
  let state = createInitialState();

  function makeTerrainSample() {
    const stride = 8;
    const rows = [];
    for (let r = 0; r < 100; r += stride) {
      const row = [];
      for (let c = 0; c < 100; c += stride) {
        row.push("grass");
      }
      rows.push(row);
    }
    return rows;
  }

  function createInitialState() {
    return {
      time: { year: 1, day: 0, era: "Stone Age" },
      paused: true,
      speed: 1,
      sim_running: false,
      world_bounds: { width: WORLD_W, height: WORLD_H },
      agents: [],
      resources: [],
      structures: [],
      factions: [],
      terrain_sample: makeTerrainSample(),
      economy: { resource_totals: {}, total_inventory_mass: 0, prices: {} },
      timeline: [],
      wars: [],
      war_overlay: [],
      trade_flow: [],
      stats: {
        population: 0,
        faction_count: 0,
        active_war_signals: 0,
        stability: 50,
        dominant_ideology: {},
      },
      era_hint: null,
      bookmark: null,
      map_lod: { regions: [] },
      fog_of_war: null,
      replay: { count: 0, max_index: 0 },
      active_wars: [],
    };
  }

  function logTimeline(kind, summary) {
    eventIndex += 1;
    state.timeline.push({
      kind,
      summary,
      year: state.time.year,
      day: state.time.day,
      event_index: eventIndex,
    });
    if (state.timeline.length > 220) {
      state.timeline = state.timeline.slice(-220);
    }
  }

  function advanceDay() {
    state.time.day += 1;
    if (state.time.day >= 365) {
      state.time.day = 0;
      state.time.year += 1;
    }
  }

  /**
   * Call from the UI poll loop (e.g. every ~480ms) with the elapsed interval in ms.
   */
  function onPoll(elapsedMs) {
    if (!state.sim_running || state.paused) return;
    timeAccumMs += elapsedMs * Math.max(1, state.speed);
    while (timeAccumMs >= MS_PER_SIM_DAY) {
      timeAccumMs -= MS_PER_SIM_DAY;
      advanceDay();
    }
  }

  function spawnFoundersAt(wx, wy) {
    if (state.agents.some((a) => a.id === "adam" || a.id === "eve")) {
      return { ok: false, message: "Adam and Eve are already in this world." };
    }
    if (state.agents.length > 0) {
      return { ok: false, message: "Remove other population first (reload page to reset)." };
    }
    const cx = Math.max(TILE, Math.min(WORLD_W - TILE, wx));
    const cy = Math.max(TILE, Math.min(WORLD_H - TILE, wy));
    state.agents = [
      {
        id: "adam",
        name: "Adam",
        x: cx - TILE * 2,
        y: cy,
        hunger: 88,
        energy: 92,
        faction: "founders",
        status: 55,
        beliefs: {},
        ideology_xy: { x: 0, y: 0 },
        moving: false,
        in_water: false,
        facing: 1,
        memory: ["The land is new underfoot."],
      },
      {
        id: "eve",
        name: "Eve",
        x: cx + TILE * 2.5,
        y: cy,
        hunger: 88,
        energy: 90,
        faction: "founders",
        status: 55,
        beliefs: {},
        ideology_xy: { x: 0, y: 0 },
        moving: false,
        in_water: false,
        facing: -1,
        memory: ["The sky and soil feel like a first morning."],
      },
    ];
    state.sim_running = true;
    state.paused = false;
    state.stats.population = 2;
    state.stats.faction_count = 1;
    logTimeline("founding", "Adam and Eve appear — the first generation begins.");
    return { ok: true, message: "ok" };
  }

  function togglePause() {
    if (state.sim_running) state.paused = !state.paused;
  }

  function setRun() {
    state.sim_running = true;
    state.paused = false;
  }

  function setSpeed(v) {
    state.speed = Math.max(1, Math.min(100, v | 0));
  }

  function runMacro(kind) {
    const k = (kind || "").toLowerCase();
    if (k === "famine") {
      logTimeline("crisis", "Hard season: a lean year tests the first families.");
    } else if (k === "war_drums") {
      logTimeline("macro", "Distant drums — rumor runs ahead of any blade.");
    } else if (k === "leader_shift") {
      logTimeline("macro", "Voices gather; someone may soon speak for the band.");
    } else {
      logTimeline("unknown", "The world notes a small change in the air.");
    }
  }

  function setBookmark(yr, day, summary, evIdx) {
    state.bookmark = {
      year: yr,
      day: day,
      summary: summary || "",
      event_index: evIdx,
    };
  }

  function clearBookmark() {
    state.bookmark = null;
  }

  function getAgentFocus(agentId) {
    const a = state.agents.find((x) => x.id === agentId);
    if (!a) return null;
    return {
      id: a.id,
      name: a.name,
      status: a.status,
      hunger: a.hunger,
      beliefs: a.beliefs || {},
      memory_recent: a.memory || [],
      faction: { id: a.faction, label: a.faction || "—" },
    };
  }

  function getSnapshot() {
    return JSON.parse(JSON.stringify(state));
  }

  global.LocalSim = {
    getSnapshot,
    onPoll,
    spawnFoundersAt,
    togglePause,
    setRun,
    setSpeed,
    runMacro,
    setBookmark,
    clearBookmark,
    getAgentFocus,
  };
})(typeof window !== "undefined" ? window : globalThis);
