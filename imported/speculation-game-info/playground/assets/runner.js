/* Speculation Game Info — shared playground runtime.
 *
 * Responsibilities:
 *  - boot Pyodide once (cached), load requested packages
 *  - fetch the REAL model source files from ../experiments/... and write them
 *    into the Pyodide virtual FS (single source of truth — no model code is
 *    duplicated in the HTML pages)
 *  - tiny helpers for parameter forms, status line, Plotly dark plots
 *
 * Requires (loaded by each page): pyodide.js + plotly.min.js from CDN.
 */
const SGP = (() => {
  let _pyodide = null;
  let _booting = null;
  const _loadedPkgs = new Set();
  const _writtenFiles = new Set();

  const PYODIDE_INDEX = "https://cdn.jsdelivr.net/pyodide/v0.26.4/full/";

  // ---- file:// guard -------------------------------------------------------
  function fileProtocolBanner(id = "proto-banner") {
    if (location.protocol !== "file:") return false;
    const el = document.getElementById(id);
    if (el) {
      el.classList.remove("hidden");
      el.innerHTML =
        "⚠️ <b>file:// で開かれています。</b> このページはローカルサーバ経由でないと " +
        "本物の model.py を fetch できません（ブラウザの CORS 制約）。リポジトリ直下で<br>" +
        "<code>python -m http.server 8000</code><br>を実行し、" +
        "<code>http://localhost:8000/playground/" +
        location.pathname.split("/").pop() +
        "</code> を開いてください。";
    }
    return true;
  }

  // ---- status line ---------------------------------------------------------
  let _statusEl = null;
  function status(msg, kind = "busy") {
    if (!_statusEl) _statusEl = document.getElementById("status");
    if (!_statusEl) return;
    _statusEl.className = "status " + kind;
    _statusEl.innerHTML = `<span class="dot"></span>${msg}`;
  }

  // ---- pyodide boot --------------------------------------------------------
  async function boot({ packages = ["numpy"] } = {}) {
    if (!_pyodide) {
      if (!_booting) {
        status("Pyodide を初期化中… (初回は数十秒、CDN から取得)", "busy");
        _booting = loadPyodide({ indexURL: PYODIDE_INDEX });
      }
      _pyodide = await _booting;
    }
    const need = packages.filter((p) => !_loadedPkgs.has(p));
    if (need.length) {
      status(`Python パッケージを取得中: ${need.join(", ")} …`, "busy");
      await _pyodide.loadPackage(need);
      need.forEach((p) => _loadedPkgs.add(p));
    }
    // shared numpy-only analysis helpers (always available to drivers as `sf`)
    if (!_writtenFiles.has("sf.py")) {
      const res = await fetch("assets/sf.py", { cache: "no-cache" });
      if (!res.ok) throw new Error(`fetch failed: assets/sf.py (${res.status})`);
      _pyodide.FS.writeFile("sf.py", await res.text());
      _writtenFiles.add("sf.py");
      _pyodide.runPython("import sys\nif '' not in sys.path: sys.path.insert(0, '')");
    }
    return _pyodide;
  }

  // ---- fetch real sources into the pyodide FS ------------------------------
  // files: [{ url, name }]  -> writes <name> at FS root, ensures cwd on sys.path
  async function loadSources(files) {
    const py = _pyodide;
    for (const f of files) {
      if (_writtenFiles.has(f.name)) continue;
      const res = await fetch(f.url, { cache: "no-cache" });
      if (!res.ok) throw new Error(`fetch failed: ${f.url} (${res.status})`);
      const src = await res.text();
      py.FS.writeFile(f.name, src);
      _writtenFiles.add(f.name);
    }
    py.runPython(
      "import sys\n" +
      "if '' not in sys.path: sys.path.insert(0, '')"
    );
  }

  // run a python driver string with `params` injected as a dict; expect it to
  // leave a JSON string in a variable named `RESULT`. Returns parsed object.
  async function runDriver(driver, params) {
    const py = _pyodide;
    py.globals.set("PARAMS_JSON", JSON.stringify(params || {}));
    await py.runPythonAsync(driver);
    const out = py.globals.get("RESULT");
    const parsed = JSON.parse(out);
    return parsed;
  }

  // ---- parameter form ------------------------------------------------------
  // specs: [{id,label,type:'range'|'number'|'select',min,max,step,value,options,hint}]
  function buildControls(containerId, specs) {
    const c = document.getElementById(containerId);
    c.innerHTML = "";
    for (const s of specs) {
      const wrap = document.createElement("div");
      wrap.className = "ctl";
      if (s.type === "select") {
        const lab = document.createElement("label");
        lab.textContent = s.label;
        const sel = document.createElement("select");
        sel.id = "p_" + s.id;
        for (const o of s.options) {
          const opt = document.createElement("option");
          opt.value = o.value;
          opt.textContent = o.label;
          if (o.value === s.value) opt.selected = true;
          sel.appendChild(opt);
        }
        wrap.appendChild(lab);
        wrap.appendChild(sel);
      } else if (s.type === "number") {
        const lab = document.createElement("label");
        lab.textContent = s.label;
        const inp = document.createElement("input");
        inp.type = "number";
        inp.id = "p_" + s.id;
        if (s.min != null) inp.min = s.min;
        if (s.max != null) inp.max = s.max;
        if (s.step != null) inp.step = s.step;
        inp.value = s.value;
        wrap.appendChild(lab);
        wrap.appendChild(inp);
      } else {
        // range
        const lab = document.createElement("label");
        lab.innerHTML = `${s.label}<span class="val" id="v_${s.id}">${s.value}</span>`;
        const inp = document.createElement("input");
        inp.type = "range";
        inp.id = "p_" + s.id;
        inp.min = s.min;
        inp.max = s.max;
        inp.step = s.step != null ? s.step : 1;
        inp.value = s.value;
        inp.addEventListener("input", () => {
          document.getElementById("v_" + s.id).textContent = inp.value;
        });
        wrap.appendChild(lab);
        wrap.appendChild(inp);
      }
      if (s.hint) {
        const h = document.createElement("div");
        h.className = "hint";
        h.textContent = s.hint;
        wrap.appendChild(h);
      }
      c.appendChild(wrap);
    }
  }

  function readControls(specs) {
    const out = {};
    for (const s of specs) {
      const el = document.getElementById("p_" + s.id);
      if (!el) continue;
      if (s.type === "select") {
        out[s.id] = el.value;
      } else {
        const num = parseFloat(el.value);
        out[s.id] = Number.isNaN(num) ? el.value : num;
      }
    }
    return out;
  }

  // ---- metrics chips -------------------------------------------------------
  function setMetrics(containerId, items) {
    const c = document.getElementById(containerId);
    if (!c) return;
    c.innerHTML = "";
    for (const it of items) {
      const d = document.createElement("div");
      d.className = "metric" + (it.good ? " good" : "");
      d.innerHTML = `<div class="k">${it.k}</div><div class="v">${it.v}</div>`;
      c.appendChild(d);
    }
  }

  // ---- Plotly helpers ------------------------------------------------------
  const FONT = { color: "#cfd6e4", family: "system-ui, sans-serif", size: 12 };
  function baseLayout(title, extra = {}) {
    return Object.assign(
      {
        title: { text: title, font: { size: 14, color: "#e6e9ef" } },
        paper_bgcolor: "rgba(0,0,0,0)",
        plot_bgcolor: "rgba(0,0,0,0)",
        font: FONT,
        margin: { l: 56, r: 18, t: 40, b: 46 },
        xaxis: { gridcolor: "#262b36", zerolinecolor: "#39404e" },
        yaxis: { gridcolor: "#262b36", zerolinecolor: "#39404e" },
        legend: { font: { size: 11 }, bgcolor: "rgba(0,0,0,0)" },
        showlegend: true,
      },
      extra
    );
  }
  const CONFIG = { responsive: true, displaylogo: false, displayModeBar: false };

  function plot(divId, traces, layout) {
    Plotly.react(divId, traces, layout, CONFIG);
  }

  const COLORS = {
    sim: "#5b9cff", ref: "#f87171", g1: "#34d399", g2: "#fbbf24",
    g3: "#c084fc", muted: "#9aa3b2", black: "#cbd3e1",
  };

  return {
    boot, loadSources, runDriver, fileProtocolBanner, status,
    buildControls, readControls, setMetrics, plot, baseLayout, COLORS,
    get pyodide() { return _pyodide; },
  };
})();
