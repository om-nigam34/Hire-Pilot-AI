(() => {
  "use strict";

  const GAUGE_CX = 100;
  const GAUGE_CY = 105;
  const GAUGE_R = 78;

  function valueToAngle(value) {
    const clamped = Math.max(0, Math.min(100, value));
    return -90 + (clamped / 100) * 180;
  }

  function polarPoint(angleDeg, radius) {
    const rad = (angleDeg * Math.PI) / 180;
    return {
      x: GAUGE_CX + radius * Math.sin(rad),
      y: GAUGE_CY - radius * Math.cos(rad),
    };
  }

  function describeArc(startValue, endValue, radius) {
    const startAngle = valueToAngle(startValue);
    const endAngle = valueToAngle(endValue);
    const start = polarPoint(startAngle, radius);
    const end = polarPoint(endAngle, radius);
    return `M ${start.x.toFixed(2)} ${start.y.toFixed(2)} A ${radius} ${radius} 0 0 1 ${end.x.toFixed(2)} ${end.y.toFixed(2)}`;
  }

  function buildGaugeSVG(score) {
    const svg = document.getElementById("gauge-svg");
    svg.innerHTML = ""; // Clear previous render

    const ns = "http://www.w3.org/2000/svg";
    const track = radius => {
      const path = document.createElementNS(ns, "path");
      path.setAttribute("d", describeArc(0, 100, radius));
      path.setAttribute("fill", "none");
      path.setAttribute("stroke", "#1E2A42");
      path.setAttribute("stroke-width", "14");
      path.setAttribute("stroke-linecap", "round");
      return path;
    };
    svg.appendChild(track(GAUGE_R));

    // Colored zones, matching an altimeter-style readout

    const zones = [
      { from: 0, to: 40, color: "#7A3232" },
      { from: 40, to: 70, color: "#7A5A22" },
      { from: 70, to: 100, color: "#1F6B4C" },
    ];

    zones.forEach(zone => {
      const path = document.createElementNS(ns, "path");
      path.setAttribute("d", describeArc(zone.from, zone.to, GAUGE_R));
      path.setAttribute("fill", "none");
      path.setAttribute("stroke", zone.color);
      path.setAttribute("stroke-width", "6");
      path.setAttribute("stroke-linecap", "butt");
      path.setAttribute("transform", `translate(0, 0)`);
      path.setAttribute("d", describeArc(zone.from, zone.to, GAUGE_R - 12));
      svg.appendChild(path);
    });

    // Tick marks at 0/25/50/75/100
    [0, 25, 50, 75, 100].forEach(tick => {
      const angle = valueToAngle(tick);
      const outer = polarPoint(angle, GAUGE_R + 10);
      const inner = polarPoint(angle, GAUGE_R - 2);
      const line = document.createElementNS(ns, "line");
      line.setAttribute("x1", inner.x);
      line.setAttribute("y1", inner.y);
      line.setAttribute("x2", outer.x);
      line.setAttribute("y2", outer.y);
      line.setAttribute("stroke", "#5C6B87");
      line.setAttribute("stroke-width", "1.5");
      svg.appendChild(line);
    });

    const needleAngle = valueToAngle(score);
    const needleGroup = document.createElementNS(ns, "g");
    needleGroup.setAttribute("transform", `rotate(${needleAngle} ${GAUGE_CX} ${GAUGE_CY})`);
    needleGroup.setAttribute("class", "gauge-needle");

    const needleLine = document.createElementNS(ns, "line");
    needleLine.setAttribute("x1", GAUGE_CX);
    needleLine.setAttribute("y1", GAUGE_CY);
    needleLine.setAttribute("x2", GAUGE_CX);
    needleLine.setAttribute("y2", GAUGE_CY - (GAUGE_R - 16));
    needleLine.setAttribute("stroke", "#F5A623");
    needleLine.setAttribute("stroke-width", "3");
    needleLine.setAttribute("stroke-linecap", "round");
    needleGroup.appendChild(needleLine);
    svg.appendChild(needleGroup);

    const hub = document.createElementNS(ns, "circle");
    hub.setAttribute("cx", GAUGE_CX);
    hub.setAttribute("cy", GAUGE_CY);
    hub.setAttribute("r", "5");
    hub.setAttribute("fill", "#F5A623");
    svg.appendChild(hub);
  }

  function drawGauge(score) {
    buildGaugeSVG(0);
    document.getElementById("gauge-value").textContent = "0";
    const steps = 24;
    let i = 0;
    const interval = setInterval(() => {
      i += 1;
      const eased = score * (i / steps);
      buildGaugeSVG(eased);
      document.getElementById("gauge-value").textContent = Math.round(eased);
      if (i >= steps) clearInterval(interval);
    }, 16);
  }

  // 2. Inputs — dropzone + textarea wiring

  function initInputs() {
    const dropzone = document.getElementById("dropzone");
    const fileInput = document.getElementById("resume-input");
    const filenameEl = document.getElementById("dropzone-filename");
    const textarea = document.getElementById("jd-textarea");
    const charCount = document.getElementById("jd-char-count");

    const setFilename = file => {
      if (file) {
        filenameEl.textContent = file.name;
        filenameEl.classList.remove("is-empty");
      } else {
        filenameEl.textContent = "No file loaded";
        filenameEl.classList.add("is-empty");
      }
    };

    dropzone.addEventListener("click", () => fileInput.click());
    dropzone.addEventListener("keydown", e => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        fileInput.click();
      }
    });
    
    fileInput.addEventListener("change", () => setFilename(fileInput.files[0]));

    ["dragenter", "dragover"].forEach(evt =>
      dropzone.addEventListener(evt, e => {
        e.preventDefault();
        dropzone.classList.add("dragover");
      })
    );
    ["dragleave", "drop"].forEach(evt =>
      dropzone.addEventListener(evt, e => {
        e.preventDefault();
        dropzone.classList.remove("dragover");
      })
    );
    dropzone.addEventListener("drop", e => {
      const file = e.dataTransfer.files[0];
      if (file) {
        fileInput.files = e.dataTransfer.files;
        setFilename(file);
      }
    });

    textarea.addEventListener("input", () => {
      charCount.textContent = `${textarea.value.length} characters`;
    });
  }

  // 3. Form submit -> POST /api/analyze

  const LOADING_MESSAGES = [
    "Extracting text from resume…",
    "Computing semantic match…",
    "Running gap analysis…",
    "Rewriting weak bullets…",
    "Drafting interview questions…",
  ];

  function showState(stateName) {
    const states = ["readout-empty", "readout-loading", "readout-results", "readout-error"];
    states.forEach(id => {
      document.getElementById(id).hidden = id !== stateName;
    });
  }

  function cycleLoadingMessages() {
    const el = document.getElementById("loading-message");
    let i = 0;
    el.textContent = LOADING_MESSAGES[0];
    return setInterval(() => {
      i = (i + 1) % LOADING_MESSAGES.length;
      el.textContent = LOADING_MESSAGES[i];
    }, 1400);
  }

  async function handleAnalyzeSubmit(e) {
    e.preventDefault();

    const fileInput = document.getElementById("resume-input");
    const textarea = document.getElementById("jd-textarea");
    const errorEl = document.getElementById("form-error");
    const btn = document.getElementById("analyze-btn");

    errorEl.hidden = true;

    if (!fileInput.files[0]) {
      errorEl.textContent = "Upload a resume PDF before running the analysis.";
      errorEl.hidden = false;
      return;
    }
    if (textarea.value.trim().length < 40) {
      errorEl.textContent = "Paste the full job description (it looks too short).";
      errorEl.hidden = false;
      return;
    }

    const formData = new FormData();
    formData.append("resume", fileInput.files[0]);
    formData.append("jd_text", textarea.value.trim());

    btn.disabled = true;
    showState("readout-loading");
    const msgInterval = cycleLoadingMessages();

    try {
      const res = await fetch("/api/analyze", { method: "POST", body: formData });
      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.error || "The analysis failed for an unknown reason.");
      }

      renderResults(data);
      showState("readout-results");
      refreshFlightLog();
    } catch (err) {
      document.getElementById("readout-error-message").textContent = err.message;
      showState("readout-error");
    } finally {
      clearInterval(msgInterval);
      btn.disabled = false;
    }
  }

  // 4. Rendering results

  function renderTagList(containerId, items, emptyText) {
    const ul = document.getElementById(containerId);
    ul.innerHTML = "";
    if (!items || items.length === 0) {
      const li = document.createElement("li");
      li.className = "tag-list-empty";
      li.textContent = emptyText;
      ul.appendChild(li);
      return;
    }
    items.forEach(text => {
      const li = document.createElement("li");
      li.textContent = text;
      ul.appendChild(li);
    });
  }

  function renderBulletCompare(weakBullets, rewrittenBullets) {
    const ul = document.getElementById("bullet-compare-list");
    ul.innerHTML = "";

    if (!weakBullets || weakBullets.length === 0) {
      ul.innerHTML = '<li class="tag-list-empty">No notably weak bullets found — nice.</li>';
      return;
    }

    weakBullets.forEach((weak, idx) => {
      const match =
        (rewrittenBullets || []).find(r => r.original && r.original.trim() === weak.original.trim()) ||
        (rewrittenBullets || [])[idx];

      const li = document.createElement("li");
      li.className = "bullet-compare-item";

      const beforeRow = document.createElement("div");
      beforeRow.className = "bullet-row";
      beforeRow.innerHTML = `
        <span class="bullet-tag bullet-tag-before">BEFORE</span>
        <span class="bullet-before-text"></span>
      `;
      beforeRow.querySelector(".bullet-before-text").textContent = weak.original || "";
      li.appendChild(beforeRow);

      if (match && match.rewritten) {
        const afterRow = document.createElement("div");
        afterRow.className = "bullet-row";
        afterRow.innerHTML = `
          <span class="bullet-tag bullet-tag-after">AFTER</span>
          <span class="bullet-after-text"></span>
        `;
        afterRow.querySelector(".bullet-after-text").textContent = match.rewritten;
        li.appendChild(afterRow);

        if (match.why_better) {
          const why = document.createElement("p");
          why.className = "bullet-why";
          why.textContent = match.why_better;
          li.appendChild(why);
        }
      }

      ul.appendChild(li);
    });
  }

  function renderQuestions(questions) {
    const ul = document.getElementById("question-list");
    ul.innerHTML = "";
    if (!questions || questions.length === 0) {
      ul.innerHTML = '<li class="tag-list-empty">No questions generated for this session.</li>';
      return;
    }
    questions.forEach(q => {
      const li = document.createElement("li");
      li.className = "question-item";
      const qText = document.createElement("p");
      qText.className = "question-text";
      qText.textContent = q.question || "";
      li.appendChild(qText);
      if (q.why_they_might_ask) {
        const why = document.createElement("p");
        why.className = "question-why";
        why.textContent = q.why_they_might_ask;
        li.appendChild(why);
      }
      ul.appendChild(li);
    });
  }

  function renderResults(data) {
    drawGauge(data.similarity_score);

    const evaluation = data.evaluation || {};
    const generation = data.generation || {};

    document.getElementById("overall-summary").textContent =
      evaluation.overall_summary || "No summary returned for this session.";

    renderTagList("missing-skills-list", evaluation.missing_skills, "No major skill gaps flagged.");
    renderTagList("keyword-gaps-list", evaluation.keyword_gaps, "No obvious ATS keyword gaps flagged.");
    renderBulletCompare(evaluation.weak_bullets, generation.rewritten_bullets);
    renderQuestions(generation.interview_questions);
  }

  // 5. Flight log -> history

  async function refreshFlightLog() {
    try {
      const res = await fetch("/api/history");
      const data = await res.json();
      const list = document.getElementById("flightlog-list");
      list.innerHTML = "";

      if (!data.sessions || data.sessions.length === 0) {
        list.innerHTML = '<li class="flightlog-empty">No sessions logged yet. Run your first analysis to start a flight log.</li>';
        return;
      }

      data.sessions.forEach(item => {
        const li = document.createElement("li");
        li.className = "flightlog-item";
        li.dataset.sessionId = item.id;
        li.innerHTML = `
          <span class="flightlog-score">${Math.round(item.similarity_score)}</span>
          <span class="flightlog-title"></span>
          <span class="flightlog-time"></span>
        `;
        li.querySelector(".flightlog-title").textContent = item.jd_title;
        li.querySelector(".flightlog-time").textContent = (item.created_at || "").split("T")[0];
        li.addEventListener("click", () => loadSessionIntoView(item.id));
        list.appendChild(li);
      });
    } catch {
      // Non-critical - history.
    }
  }

  async function loadSessionIntoView(sessionId) {
    showState("readout-loading");
    document.getElementById("loading-message").textContent = "Pulling session from the flight log…";
    try {
      const res = await fetch(`/api/session/${sessionId}`);
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Couldn't load that session.");

      renderResults({
        similarity_score: data.similarity_score,
        evaluation: data.evaluation,
        generation: data.generation,
      });
      showState("readout-results");
    } catch (err) {
      document.getElementById("readout-error-message").textContent = err.message;
      showState("readout-error");
    }
  }

  function initFlightLogClicks() {
    document.querySelectorAll(".flightlog-item[data-session-id]").forEach(li => {
      li.addEventListener("click", () => loadSessionIntoView(li.dataset.sessionId));
    });
  }

  // Init

  document.addEventListener("DOMContentLoaded", () => {
    initInputs();
    initFlightLogClicks();
    document.getElementById("analyze-form").addEventListener("submit", handleAnalyzeSubmit);
  });
})();