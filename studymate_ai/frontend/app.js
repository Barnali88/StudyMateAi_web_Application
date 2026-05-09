const API = "";

let files = [];
let activeFileId = null;
let activeChatSessionId = null;
let flashcards = [];
let fcIndex = 0;
let fcFlipped = false;
let quizState = {};
let currentQuiz = null;
let authMode = "login";
let currentUser = null;
let modelInfoCache = null;

function getToken() { return sessionStorage.getItem("studymate_token") || ""; }
function setToken(token) { sessionStorage.setItem("studymate_token", token); localStorage.removeItem("studymate_token"); }
function clearToken() { sessionStorage.removeItem("studymate_token"); localStorage.removeItem("studymate_token"); sessionStorage.removeItem("studymate_active_file"); sessionStorage.removeItem("studymate_active_file");
  localStorage.removeItem("studymate_active_file"); }

document.addEventListener("DOMContentLoaded", async () => {
  localStorage.removeItem("studymate_token");
  sessionStorage.removeItem("studymate_active_file");
  localStorage.removeItem("studymate_active_file");
  await loadModelInfo();
  if (getToken()) {
    try {
      currentUser = await apiFetch("/api/auth/me");
      showApp();
      await loadFiles();
    } catch {
      clearToken();
      showAuth();
    }
  } else {
    showAuth();
  }
});

function showAuth() {
  document.getElementById("authOverlay").classList.remove("hidden");
}
function showApp() {
  document.getElementById("authOverlay").classList.add("hidden");
  document.getElementById("userName").textContent = currentUser ? currentUser.full_name : "Student";
}
function setAuthMode(mode) {
  authMode = mode;
  document.getElementById("loginTab").classList.toggle("active", mode === "login");
  document.getElementById("registerTab").classList.toggle("active", mode === "register");
  document.getElementById("authName").classList.toggle("hidden", mode === "login");
  document.getElementById("authSubmit").textContent = mode === "login" ? "Login" : "Create account";
}
async function submitAuth(e) {
  e.preventDefault();
  const full_name = document.getElementById("authName").value.trim();
  const email = document.getElementById("authEmail").value.trim();
  const password = document.getElementById("authPassword").value;
  const path = authMode === "login" ? "/api/auth/login" : "/api/auth/register";
  const payload = authMode === "login" ? { email, password } : { full_name, email, password };
  try {
    const data = await apiFetch(path, { method: "POST", json: payload, skipAuth: true });
    setToken(data.token);
    currentUser = data.user;
    showApp();
    await loadFiles();
    showToast("Welcome to StudyMate AI.", "success");
  } catch (err) {
    showToast(err.message, "error");
  }
}
async function logout() {
  try { await apiFetch("/api/auth/logout", { method: "POST" }); } catch {}
  clearToken();
  files = [];
  activeFileId = null;
  sessionStorage.removeItem("studymate_active_file");
  localStorage.removeItem("studymate_active_file");
  renderFileList();
  populateSelects();
  showAuth();
}

function switchView(view) {
  document.querySelectorAll(".view").forEach(v => v.classList.remove("active"));
  document.querySelectorAll(".nav-btn").forEach(b => b.classList.remove("active"));
  document.getElementById("view-" + view).classList.add("active");
  const btn = document.querySelector(`.nav-btn[data-view="${view}"]`);
  if (btn) btn.classList.add("active");
}

async function loadModelInfo() {
  try {
    const data = await apiFetch("/api/model-info", { skipAuth: true });
    modelInfoCache = data;
    const label = `${data.mode === "cloud" ? "☁ " : "⚡ "}${data.model}`;
    document.getElementById("modelLabel").textContent = label;
    document.getElementById("modelMode").value = data.mode;
    renderModelOptions();
  } catch {
    document.getElementById("modelLabel").textContent = "Offline";
    document.querySelector(".model-dot").style.background = "var(--red)";
  }
}
function renderModelOptions() {
  if (!modelInfoCache) return;
  const mode = document.getElementById("modelMode").value;
  const models = mode === "cloud" ? modelInfoCache.cloud_models : modelInfoCache.local_models;
  const select = document.getElementById("modelSelect");
  select.innerHTML = models.map(m => `<option value="${esc(m)}">${esc(m)}</option>`).join("");
  if (mode === modelInfoCache.mode) select.value = modelInfoCache.model;
}
async function saveModelSelection() {
  const mode = document.getElementById("modelMode").value;
  const model = document.getElementById("modelSelect").value;
  try {
    const data = await apiFetch("/api/model-select", { method: "POST", json: { mode, model }, skipAuth: true });
    modelInfoCache = data;
    document.getElementById("modelLabel").textContent = `${data.mode === "cloud" ? "☁ " : "⚡ "}${data.model}`;
    showToast("Model updated.", "success");
  } catch (err) {
    showToast(err.message, "error");
  }
}

async function loadFiles() {
  try {
    files = await apiFetch("/api/files/");
    activeFileId = null;
    activeChatSessionId = null;
    sessionStorage.removeItem("studymate_active_file");
  localStorage.removeItem("studymate_active_file");
    renderFileList();
    populateSelects();
    resetWorkspace();
  } catch (e) {
    if (String(e.message).toLowerCase().includes("log in")) showAuth();
  }
}
function renderFileList() {
  const el = document.getElementById("fileList");
  if (!files.length) {
    el.innerHTML = '<div class="file-empty">No files yet</div>';
    renderUploadedCards();
    return;
  }
  el.innerHTML = files.map(f => `
    <div class="file-item ${f.id === activeFileId ? "active" : ""}" onclick="openNote('${f.id}')">
      <div class="file-item-icon">${esc(f.file_type)}</div>
      <div class="file-item-name" title="${esc(f.original_name)}">${esc(f.original_name)}</div>
      <button class="file-item-del" title="Delete" onclick="deleteFile(event,'${f.id}')">✕</button>
    </div>`).join("");
  renderUploadedCards();
}
function renderUploadedCards() {
  const el = document.getElementById("uploadedFiles");
  if (!files.length) { el.innerHTML = ""; return; }
  el.innerHTML = files.map(f => `
    <div class="file-card">
      <div class="file-card-icon">${esc(f.file_type)}</div>
      <div class="file-card-info">
        <div class="file-card-name" title="${esc(f.original_name)}">${esc(f.original_name)}</div>
        <div class="file-card-meta"><span>${fmtSize(f.file_size)}</span><span>${Number(f.char_count).toLocaleString()} chars</span><span>${f.chunk_count} chunks</span>${f.is_indexed ? '<span class="indexed-chip">✓ indexed</span>' : ''}</div>
      </div>
    </div>`).join("");
}
function populateSelects() {
  const ids = ["chatFileSelect", "summaryFileSelect", "quizFileSelect", "fcFileSelect"];
  const opts = `<option value="">— select a file —</option>` + files.map(f => `<option value="${f.id}">${esc(f.original_name)}</option>`).join("");
  ids.forEach(id => {
    const sel = document.getElementById(id);
    if (!sel) return;
    sel.innerHTML = opts;
    if (activeFileId) sel.value = activeFileId;
  });
}
async function openNote(id) {
  await selectFile(id);
  switchView("chat");
  showToast("Note opened with saved study history.", "success");
}
async function selectFile(id) {
  activeFileId = id || null;
  activeChatSessionId = null;
  if (activeFileId) sessionStorage.setItem("studymate_active_file", activeFileId);
  renderFileList();
  populateSelects();
  await loadWorkspaceForFile();
}
async function handleFileDropdownChange(selectEl, view) {
  if (!selectEl.value) return;
  activeFileId = selectEl.value;
  activeChatSessionId = null;
  sessionStorage.setItem("studymate_active_file", activeFileId);
  renderFileList();
  populateSelects();
  if (view === "chat") { await loadChatSessions(true); await loadChatHistory(); }
  if (view === "summary") await loadSavedSummary();
  if (view === "quiz") await loadSavedQuiz();
  if (view === "flashcards") await loadSavedFlashcards();
}
function resetWorkspace() {
  const chatWin = document.getElementById("chatWindow");
  if (chatWin) { chatWin.innerHTML = ""; chatWin.appendChild(makeChatEmpty()); }
  const sessionSelect = document.getElementById("chatSessionSelect");
  if (sessionSelect) sessionSelect.innerHTML = '<option value="">No chat selected</option>';
  const summary = document.getElementById("summaryOutput");
  if (summary) summary.innerHTML = `<div class="placeholder-card"><span>✦</span> Click a note from My Notes to load its study history.</div>`;
  const quiz = document.getElementById("quizOutput");
  if (quiz) quiz.innerHTML = `<div class="placeholder-card"><span>✦</span> Click a note from My Notes, then generate or load a quiz.</div>`;
  const quizHistory = document.getElementById("quizHistorySelect");
  if (quizHistory) quizHistory.innerHTML = '<option value="">No saved quiz</option>';
  const ph = document.getElementById("fcPlaceholder");
  const deck = document.getElementById("fcDeck");
  if (deck) deck.classList.add("hidden");
  if (ph) { ph.classList.remove("hidden"); ph.innerHTML = `<span>✦</span> Click a note from My Notes, then generate flashcards.`; }
}
async function loadWorkspaceForFile() {
  if (!activeFileId) { resetWorkspace(); return; }
  await Promise.allSettled([
    loadChatSessions(true),
    loadSavedSummary(),
    loadSavedQuiz(),
    loadSavedFlashcards(),
  ]);
  await loadChatHistory();
}
async function deleteFile(e, id) {
  e.stopPropagation();
  if (!confirm("Delete this file and all its data?")) return;
  try {
    await apiFetch(`/api/files/${id}`, { method: "DELETE" });
    files = files.filter(f => f.id !== id);
    if (activeFileId === id) {
      activeFileId = files[0]?.id || null;
      if (activeFileId) sessionStorage.setItem("studymate_active_file", activeFileId); else sessionStorage.removeItem("studymate_active_file");
  localStorage.removeItem("studymate_active_file");
    }
    renderFileList();
    populateSelects();
    await loadWorkspaceForFile();
    showToast("File deleted.", "success");
  } catch (err) {
    showToast("Delete failed: " + err.message, "error");
  }
}

function handleDragOver(e) { e.preventDefault(); document.getElementById("uploadZone").classList.add("drag-over"); }
function handleDragLeave() { document.getElementById("uploadZone").classList.remove("drag-over"); }
function handleDrop(e) { e.preventDefault(); document.getElementById("uploadZone").classList.remove("drag-over"); const file = e.dataTransfer.files[0]; if (file) uploadFile(file); }
function handleFileSelect(e) { const file = e.target.files[0]; if (file) uploadFile(file); e.target.value = ""; }

async function uploadFile(file) {
  const progress = document.getElementById("uploadProgress");
  const fill = document.getElementById("progressFill");
  const label = document.getElementById("progressLabel");
  progress.classList.remove("hidden");
  label.textContent = "Uploading…";
  fill.style.width = "25%";
  const fd = new FormData();
  fd.append("file", file);

  try {
    fill.style.width = "55%";
    label.textContent = "Extracting text and building index…";
    const headers = {};
    if (getToken()) headers["Authorization"] = `Bearer ${getToken()}`;
    const result = await fetch(`${API}/api/files/upload`, { method: "POST", body: fd, headers });
    fill.style.width = "90%";
    let data;
    try { data = await result.json(); } catch { data = {}; }
    if (!result.ok) throw new Error(data.detail || result.statusText);
    fill.style.width = "100%";
    label.textContent = "Done!";
    files.unshift(data);
    activeFileId = data.id;
    sessionStorage.setItem("studymate_active_file", activeFileId);
    renderFileList();
    populateSelects();
    await loadWorkspaceForFile();
    showToast(`"${data.original_name}" uploaded and indexed.`, "success");
    setTimeout(() => progress.classList.add("hidden"), 1200);
  } catch (err) {
    progress.classList.add("hidden");
    showToast("Upload failed: " + err.message, "error");
  }
}

function makeChatEmpty() {
  const div = document.createElement("div");
  div.className = "chat-empty";
  div.id = "chatEmpty";
  div.innerHTML = `<div class="chat-empty-icon">💬</div><p>Select a file and ask anything about your notes</p>`;
  return div;
}
async function loadChatSessions(selectLatest = false) {
  const fileId = document.getElementById("chatFileSelect").value || activeFileId;
  const sel = document.getElementById("chatSessionSelect");
  if (!sel) return;
  if (!fileId) { sel.innerHTML = '<option value="">No chat selected</option>'; return; }
  try {
    const sessions = await apiFetch(`/api/chat/sessions/${fileId}`);
    sel.innerHTML = sessions.length
      ? sessions.map(s => `<option value="${esc(s.id)}">${esc(s.title)} · ${new Date(s.created_at).toLocaleString()}</option>`).join("")
      : '<option value="">No saved chats</option>';
    if (selectLatest && sessions.length) activeChatSessionId = sessions[0].id;
    if (activeChatSessionId && sessions.some(s => s.id === activeChatSessionId)) sel.value = activeChatSessionId;
    else if (sessions.length) { activeChatSessionId = sessions[0].id; sel.value = activeChatSessionId; }
    else activeChatSessionId = null;
  } catch {
    sel.innerHTML = '<option value="">Could not load chats</option>';
  }
}
async function handleChatSessionChange(selectEl) {
  activeChatSessionId = selectEl.value || null;
  await loadChatHistory();
}
async function startNewChat() {
  const fileId = document.getElementById("chatFileSelect").value || activeFileId;
  if (!fileId) { showToast("Select a file first.", "error"); return; }
  try {
    const session = await apiFetch("/api/chat/sessions", { method: "POST", json: { file_id: fileId } });
    activeChatSessionId = session.id;
    await loadChatSessions(false);
    const win = document.getElementById("chatWindow");
    win.innerHTML = "";
    win.appendChild(makeChatEmpty());
    showToast("New chat started for this note.", "success");
  } catch (err) {
    showToast("Error: " + err.message, "error");
  }
}
async function loadChatHistory() {
  const fileId = document.getElementById("chatFileSelect").value;
  const win = document.getElementById("chatWindow");
  win.innerHTML = "";
  const empty = makeChatEmpty();
  if (!fileId) { win.appendChild(empty); return; }
  if (!activeChatSessionId) { win.appendChild(empty); return; }
  try {
    const history = await apiFetch(`/api/chat/history/${fileId}?session_id=${encodeURIComponent(activeChatSessionId)}`);
    if (!history.length) { win.appendChild(empty); return; }
    history.forEach(msg => appendMessage(msg.role, msg.content));
  } catch {
    win.innerHTML = `<div style="color:var(--red);font-size:13px;">Could not load history.</div>`;
  }
}
async function sendChat() {
  const fileId = document.getElementById("chatFileSelect").value;
  const input = document.getElementById("chatInput");
  const msg = input.value.trim();
  if (!fileId) { showToast("Please select a file first.", "error"); return; }
  if (!msg) return;
  input.value = "";
  autoResize(input);
  const empty = document.getElementById("chatEmpty");
  if (empty && empty.parentNode) empty.remove();
  appendMessage("user", msg);
  const typingEl = appendTyping();
  document.getElementById("sendBtn").disabled = true;
  try {
    const payload = { file_id: fileId, message: msg };
    if (activeChatSessionId) payload.session_id = activeChatSessionId;
    const data = await apiFetch("/api/chat/", { method: "POST", json: payload });
    activeChatSessionId = data.session_id;
    await loadChatSessions(false);
    typingEl.remove();
    appendMessage("assistant", data.assistant_message.content);
  } catch (err) {
    typingEl.remove();
    appendMessage("assistant", `⚠ Error: ${err.message}`);
  } finally {
    document.getElementById("sendBtn").disabled = false;
  }
}
function appendMessage(role, content) {
  const win = document.getElementById("chatWindow");
  const div = document.createElement("div");
  div.className = `chat-msg ${role}`;
  const avatar = role === "user" ? "U" : "✦";
  div.innerHTML = `<div class="chat-avatar">${avatar}</div><div class="chat-bubble">${mdToHtml(content)}</div>`;
  win.appendChild(div);
  win.scrollTop = win.scrollHeight;
  return div;
}
function appendTyping() {
  const win = document.getElementById("chatWindow");
  const div = document.createElement("div");
  div.className = "chat-msg assistant";
  div.innerHTML = `<div class="chat-avatar">✦</div><div class="chat-typing"><div class="typing-dots"><span></span><span></span><span></span></div>Thinking…</div>`;
  win.appendChild(div);
  win.scrollTop = win.scrollHeight;
  return div;
}
function handleChatKey(e) { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendChat(); } }
function autoResize(el) { el.style.height = "auto"; el.style.height = Math.min(el.scrollHeight, 160) + "px"; }
async function clearChatHistory() {
  const fileId = document.getElementById("chatFileSelect").value;
  if (!fileId || !activeChatSessionId) return;
  if (!confirm("Clear this chat only?")) return;
  try {
    await apiFetch(`/api/chat/history/${fileId}?session_id=${encodeURIComponent(activeChatSessionId)}`, { method: "DELETE" });
    const win = document.getElementById("chatWindow");
    win.innerHTML = "";
    win.appendChild(makeChatEmpty());
    showToast("Current chat cleared.", "success");
  } catch (err) {
    showToast("Error: " + err.message, "error");
  }
}

async function loadSavedSummary() {
  const fileId = activeFileId || document.getElementById("summaryFileSelect").value;
  const el = document.getElementById("summaryOutput");
  if (!fileId || !el) return;
  try {
    const items = await apiFetch(`/api/summary/${fileId}`);
    if (items.length) {
      el.innerHTML = `<div class="history-label">Saved summary</div>` + mdToHtml(items[0].summary);
    } else {
      el.innerHTML = `<div class="placeholder-card"><span>✦</span> No saved summary yet. Click Summarise to create one.</div>`;
    }
  } catch {
    el.innerHTML = `<div class="placeholder-card"><span>✦</span> Could not load saved summary.</div>`;
  }
}

async function generateSummary() {
  const fileId = document.getElementById("summaryFileSelect").value;
  if (!fileId) { showToast("Select a file first.", "error"); return; }
  showLoader("Generating summary…");
  try {
    const data = await apiFetch("/api/summary/", { method: "POST", json: { file_id: fileId } });
    document.getElementById("summaryOutput").innerHTML = `<div class="history-label">Saved summary</div>` + mdToHtml(data.summary);
    showToast("Summary ready.", "success");
  } catch (err) {
    showToast("Error: " + err.message, "error");
  } finally { hideLoader(); }
}
async function loadSavedQuiz() {
  const fileId = activeFileId || document.getElementById("quizFileSelect").value;
  const el = document.getElementById("quizOutput");
  const hist = document.getElementById("quizHistorySelect");
  if (!fileId || !el) return;
  try {
    const quizzes = await apiFetch(`/api/quiz/${fileId}`);
    if (hist) {
      hist.innerHTML = quizzes.length ? quizzes.map(q => `<option value="${esc(q.id)}">${esc(q.title)} · ${new Date(q.created_at).toLocaleString()}</option>`).join("") : '<option value="">No saved quiz</option>';
    }
    if (quizzes.length) {
      currentQuiz = quizzes[0];
      if (hist) hist.value = currentQuiz.id;
      quizState = {};
      renderQuiz(currentQuiz, true);
    } else {
      currentQuiz = null;
      quizState = {};
      el.innerHTML = `<div class="placeholder-card"><span>✦</span> No saved quiz yet. Generate a quiz to start testing yourself.</div>`;
    }
  } catch {
    el.innerHTML = `<div class="placeholder-card"><span>✦</span> Could not load saved quiz.</div>`;
  }
}
function handleQuizHistoryChange(selectEl) {
  const fileId = activeFileId || document.getElementById("quizFileSelect").value;
  if (!fileId || !selectEl.value) return;
  apiFetch(`/api/quiz/${fileId}`).then(quizzes => {
    const found = quizzes.find(q => q.id === selectEl.value);
    if (found) { currentQuiz = found; quizState = {}; renderQuiz(found, true); }
  }).catch(() => showToast("Could not load selected quiz.", "error"));
}
function newQuiz() {
  currentQuiz = null;
  quizState = {};
  document.getElementById("quizOutput").innerHTML = `<div class="placeholder-card"><span>✦</span> New quiz ready. Choose question count and click Generate Quiz.</div>`;
}
async function generateQuiz() {
  const fileId = document.getElementById("quizFileSelect").value;
  const num = parseInt(document.getElementById("quizCount").value) || 5;
  if (!fileId) { showToast("Select a file first.", "error"); return; }
  showLoader("Generating quiz questions…");
  try {
    const quiz = await apiFetch("/api/quiz/generate", { method: "POST", json: { file_id: fileId, num_questions: num } });
    currentQuiz = quiz;
    quizState = {};
    renderQuiz(quiz);
    await loadSavedQuiz();
    const hist = document.getElementById("quizHistorySelect");
    if (hist) hist.value = quiz.id;
    renderQuiz(quiz);
    showToast(`Quiz with ${quiz.questions.length} questions ready.`, "success");
  } catch (err) {
    showToast("Error: " + err.message, "error");
  } finally { hideLoader(); }
}
function renderQuiz(quiz, saved = false) {
  const el = document.getElementById("quizOutput");
  const label = saved ? `<div class="history-label">Saved quiz from your study history</div>` : `<div class="history-label">New quiz saved to your study history</div>`;
  el.innerHTML = label + `<div class="quiz-score-bar"><span>Score:</span><span class="quiz-score-val" id="quizScore">0 / ${quiz.questions.length}</span><span style="color:var(--text3)">Answer all questions</span></div>` + quiz.questions.map((q, i) => `
    <div class="quiz-q" id="quizQ-${i}"><div class="quiz-q-num">Question ${i + 1}</div><div class="quiz-q-text">${esc(q.question)}</div><div class="quiz-options">${q.options.map(opt => `<button class="quiz-option" onclick="answerQuiz(${i}, '${jsEsc(opt[0])}', '${jsEsc(q.answer)}', '${jsEsc(q.explanation || "")}')">${esc(opt)}</button>`).join("")}</div><div id="quizExp-${i}" style="display:none" class="quiz-explanation"></div></div>`).join("");
}
function answerQuiz(qIdx, selected, correct, explanation) {
  if (quizState[qIdx]?.answered) return;
  quizState[qIdx] = { answered: true, correct: selected === correct };
  const qEl = document.getElementById(`quizQ-${qIdx}`);
  qEl.querySelectorAll(".quiz-option").forEach(btn => {
    btn.disabled = true;
    const letter = btn.textContent.trim()[0];
    if (letter === correct) btn.classList.add("correct"); else if (letter === selected) btn.classList.add("wrong");
  });
  if (explanation) { const expEl = document.getElementById(`quizExp-${qIdx}`); expEl.style.display = "block"; expEl.textContent = "💡 " + explanation; }
  document.getElementById("quizScore").textContent = `${Object.values(quizState).filter(s => s.correct).length} / ${currentQuiz.questions.length}`;
}

async function loadSavedFlashcards() {
  const fileId = activeFileId || document.getElementById("fcFileSelect").value;
  if (!fileId) return;
  try {
    const data = await apiFetch(`/api/flashcards/${fileId}`);
    flashcards = data.flashcards || [];
    fcIndex = 0;
    fcFlipped = false;
    if (flashcards.length) {
      document.getElementById("fcPlaceholder").classList.add("hidden");
      document.getElementById("fcDeck").classList.remove("hidden");
      renderCard();
      const label = document.getElementById("fcHistoryLabel");
      if (label) label.textContent = "Saved flashcards from your study history";
    } else {
      document.getElementById("fcDeck").classList.add("hidden");
      const ph = document.getElementById("fcPlaceholder");
      ph.classList.remove("hidden");
      ph.innerHTML = `<span>✦</span> No saved flashcards yet. Generate flashcards to start reviewing.`;
    }
  } catch {
    document.getElementById("fcDeck").classList.add("hidden");
    const ph = document.getElementById("fcPlaceholder");
    ph.classList.remove("hidden");
    ph.innerHTML = `<span>✦</span> Could not load saved flashcards.`;
  }
}

async function generateFlashcards() {
  const fileId = document.getElementById("fcFileSelect").value;
  const num = parseInt(document.getElementById("fcCount").value) || 10;
  if (!fileId) { showToast("Select a file first.", "error"); return; }
  showLoader("Generating flashcards…");
  try {
    const data = await apiFetch("/api/flashcards/generate", { method: "POST", json: { file_id: fileId, num_cards: num } });
    flashcards = data.flashcards;
    fcIndex = 0;
    fcFlipped = false;
    document.getElementById("fcPlaceholder").classList.add("hidden");
    document.getElementById("fcDeck").classList.remove("hidden");
    renderCard();
    const label = document.getElementById("fcHistoryLabel");
    if (label) label.textContent = "New flashcards saved to your study history";
    showToast(`${flashcards.length} flashcards ready.`, "success");
  } catch (err) {
    showToast("Error: " + err.message, "error");
  } finally { hideLoader(); }
}
function renderCard() {
  if (!flashcards.length) return;
  const card = flashcards[fcIndex];
  const cardEl = document.getElementById("fcCard");
  const front = document.getElementById("fcFront");
  const back = document.getElementById("fcBack");
  const hint = document.getElementById("fcHint");
  fcFlipped = false;
  cardEl.classList.remove("flipped");
  front.style.display = "block";
  back.style.display = "none";
  hint.textContent = "tap to reveal";
  front.textContent = card.front;
  back.textContent = card.back;
  document.getElementById("fcCounter").textContent = `${fcIndex + 1} / ${flashcards.length}`;
  document.getElementById("fcProgressFill").style.width = ((fcIndex + 1) / flashcards.length) * 100 + "%";
}
function flipCard() {
  const front = document.getElementById("fcFront");
  const back = document.getElementById("fcBack");
  const hint = document.getElementById("fcHint");
  const cardEl = document.getElementById("fcCard");
  fcFlipped = !fcFlipped;
  front.style.display = fcFlipped ? "none" : "block";
  back.style.display = fcFlipped ? "block" : "none";
  hint.textContent = fcFlipped ? "tap to flip back" : "tap to reveal";
  cardEl.classList.toggle("flipped", fcFlipped);
}
function nextCard() { if (fcIndex < flashcards.length - 1) { fcIndex++; renderCard(); } else showToast("You've reached the last card.", "success"); }
function prevCard() { if (fcIndex > 0) { fcIndex--; renderCard(); } }

async function apiFetch(path, opts = {}) {
  const headers = { "Accept": "application/json" };
  if (!opts.skipAuth && getToken()) headers["Authorization"] = `Bearer ${getToken()}`;
  let body;
  if (opts.json) { headers["Content-Type"] = "application/json"; body = JSON.stringify(opts.json); }
  const res = await fetch(API + path, { method: opts.method || "GET", headers, body });
  if (res.status === 204) return null;
  let data;
  try { data = await res.json(); } catch { data = {}; }
  if (res.status === 401) { clearToken(); showAuth(); }
  if (!res.ok) throw new Error(data.detail || res.statusText);
  return data;
}
function showLoader(text = "Working…") { document.getElementById("loaderText").textContent = text; document.getElementById("loader").classList.remove("hidden"); }
function hideLoader() { document.getElementById("loader").classList.add("hidden"); }
let _toastTimer;
function showToast(msg, type = "") { const el = document.getElementById("toast"); el.textContent = msg; el.className = `toast ${type}`; el.classList.remove("hidden"); clearTimeout(_toastTimer); _toastTimer = setTimeout(() => el.classList.add("hidden"), 3500); }
function esc(str) { return String(str || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;"); }
function jsEsc(str) { return String(str || "").replace(/\\/g, "\\\\").replace(/'/g, "\\'").replace(/\n/g, " ").replace(/\r/g, " "); }
function fmtSize(bytes) { if (bytes < 1024) return bytes + " B"; if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB"; return (bytes / (1024 * 1024)).toFixed(1) + " MB"; }
function mdToHtml(text) {
  if (!text) return "";
  return "<p>" + esc(text)
    .replace(/^### (.+)$/gm, "<h3>$1</h3>")
    .replace(/^## (.+)$/gm, "<h2>$1</h2>")
    .replace(/^# (.+)$/gm, "<h1>$1</h1>")
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.+?)\*/g, "<em>$1</em>")
    .replace(/`(.+?)`/g, "<code>$1</code>")
    .replace(/^[-*] (.+)$/gm, "<li>$1</li>")
    .replace(/(<li>.*<\/li>)/gs, "<ul>$1</ul>")
    .replace(/\n{2,}/g, "</p><p>")
    .replace(/\n/g, "<br>") + "</p>";
}
