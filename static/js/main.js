(() => {
  "use strict";

  // 1. Score ring

  const RING_R = 68;
  const RING_CX = 84;
  const RING_CY = 84;
  const CIRCUMFERENCE = 2 * Math.PI * RING_R;

  function tierLabel(score) {
    if (score >= 75) return "Strong match";
    if (score >= 50) return "Partial match";
    return "Needs work";
  }

  function buildGaugeSVG() {
    const svg = document.getElementById("gauge-svg");
    svg.innerHTML = "";
    const ns = "http://www.w3.org/2000/svg";

    const track = document.createElementNS(ns, "circle");
    track.setAttribute("cx", RING_CX);
    track.setAttribute("cy", RING_CY);
    track.setAttribute("r", RING_R);
    track.setAttribute("fill", "none");
    track.setAttribute("stroke", "#20232D");
    track.setAttribute("stroke-width", "11");
    svg.appendChild(track);

    const progress = document.createElementNS(ns, "circle");
    progress.setAttribute("id", "gauge-progress");
    progress.setAttribute("cx", RING_CX);
    progress.setAttribute("cy", RING_CY);
    progress.setAttribute("r", RING_R);
    progress.setAttribute("fill", "none");
    progress.setAttribute("stroke", "#F5A623");
    progress.setAttribute("stroke-width", "11");
    progress.setAttribute("stroke-linecap", "round");
    progress.setAttribute("transform", `rotate(-90 ${RING_CX} ${RING_CY})`);
    progress.style.strokeDasharray = `${CIRCUMFERENCE}`;
    progress.style.strokeDashoffset = `${CIRCUMFERENCE}`;
    progress.style.transition = "stroke-dashoffset 1.05s cubic-bezier(0.16,1,0.3,1)";
    svg.appendChild(progress);

    return progress;
  }

  function animateValue(el, to, duration) {
    const start = performance.now();
    const from = 0;
    function tick(now) {
      const t = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - t, 3);
      el.textContent = Math.round(from + (to - from) * eased);
      if (t < 1) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
  }

  function drawGauge(score) {
    const clamped = Math.max(0, Math.min(100, Number(score) || 0));
    const progress = buildGaugeSVG();

    // Force layout so the browser registers the starting offset before we
    // animate to the target — otherwise the transition is skipped.
    // eslint-disable-next-line no-unused-expressions
    progress.getBoundingClientRect();

    requestAnimationFrame(() => {
      const offset = CIRCUMFERENCE * (1 - clamped / 100);
      progress.style.strokeDashoffset = `${offset}`;
    });

    animateValue(document.getElementById("gauge-value"), Math.round(clamped), 1050);

    const tierEl = document.getElementById("gauge-tier");
    if (tierEl) tierEl.textContent = tierLabel(clamped);
  }

  // 2. Inputs —> dropzone + textarea wiring

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
      el.classList.add("msg-fade");
      setTimeout(() => {
        i = (i + 1) % LOADING_MESSAGES.length;
        el.textContent = LOADING_MESSAGES[i];
        el.classList.remove("msg-fade");
      }, 200);
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
        list.innerHTML = '<li class="flightlog-empty">No sessions logged yet. Run your first analysis to start a history log.</li>';
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
    document.getElementById("loading-message").textContent = "Pulling up that session…";
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