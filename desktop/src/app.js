/**
 * Zé das Coisas AI — Frontend Application Logic
 * ==================================================
 * Voice-first interface using Web Audio API + WebSocket
 * for real-time bidirectional audio streaming with Gemini Live.
 */

let BACKEND_URL = 'http://127.0.0.1:8765';
let WS_URL = 'ws://127.0.0.1:8765';

// ─── Voice State ────────────────────────────────────────────────────────────
let voiceWs = null;
let audioContext = null;
let playbackContext = null;
let nextPlayTime = 0;
let micStream = null;
let micProcessor = null;
let isVoiceActive = false;
let playbackQueue = [];
let isPlaying = false;

// ─── Init ───────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  if (window.electronAPI) {
    try {
      BACKEND_URL = await window.electronAPI.getBackendUrl();
      WS_URL = BACKEND_URL.replace('http', 'ws');
    } catch {}
  }

  initTheme();
  initNavigation();
  initVoice();
  initLibrary();
  initSettings();
  initDebugOverlay();
  loadConfig();
  loadDbStatus();
  setInterval(loadDbStatus, 3000);
  loadDocuments();
});

// ─── Toast ──────────────────────────────────────────────────────────────────
function toast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  const icons = { success: '✅', error: '❌', info: 'ℹ️' };
  el.innerHTML = `<span>${icons[type] || ''}</span> ${message}`;
  container.appendChild(el);
  setTimeout(() => el.remove(), 4000);
}

// ─── API Helper ─────────────────────────────────────────────────────────────
async function api(path, opts = {}) {
  const res = await fetch(`${BACKEND_URL}${path}`, {
    headers: { 'Content-Type': 'application/json', ...opts.headers }, ...opts
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Request failed');
  }
  return res.json();
}

// ─── Navigation ─────────────────────────────────────────────────────────────
function initNavigation() {
  const buttons = document.querySelectorAll('.nav-btn[data-page]');
  buttons.forEach(btn => {
    btn.addEventListener('click', () => {
      buttons.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
      document.getElementById(`page-${btn.dataset.page}`)?.classList.add('active');
    });
  });

  document.getElementById('btn-open-docs')?.addEventListener('click', () => {
    if (window.electronAPI) window.electronAPI.openDocsFolder();
    else toast('Disponível no app desktop', 'info');
  });
}

// ─── Theme Toggling ──────────────────────────────────────────────────────────
function initTheme() {
  const toggleBtn = document.getElementById('btn-theme-toggle');
  if (!toggleBtn) return;

  // Load saved theme or default to dark
  const savedTheme = localStorage.getItem('theme') || 'dark';
  document.documentElement.setAttribute('data-theme', savedTheme);
  updateThemeIcon(savedTheme);

  toggleBtn.addEventListener('click', () => {
    const currentTheme = document.documentElement.getAttribute('data-theme') || 'dark';
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    
    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
    updateThemeIcon(newTheme);
    
    toast(`Tema alternado para modo ${newTheme === 'dark' ? 'escuro' : 'claro'}`, 'info');
  });
}

function updateThemeIcon(theme) {
  const toggleBtn = document.getElementById('btn-theme-toggle');
  if (toggleBtn) {
    toggleBtn.textContent = theme === 'dark' ? '☀️' : '🌙';
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// ═══ VOICE ENGINE — Web Audio API + WebSocket ═══════════════════════════
// ═══════════════════════════════════════════════════════════════════════════

function initVoice() {
  const micBtn = document.getElementById('btn-mic');
  const stopBtn = document.getElementById('btn-stop-voice');

  micBtn.addEventListener('click', () => {
    if (isVoiceActive) {
      stopVoiceSession();
    } else {
      startVoiceSession();
    }
  });

  stopBtn.addEventListener('click', stopVoiceSession);
}

function setVoiceStatus(state, text) {
  const el = document.getElementById('voice-status');
  const textEl = el.querySelector('.voice-status-text');
  el.className = `voice-status ${state}`;
  textEl.textContent = text;
}

function setOrbState(state) {
  const orb = document.getElementById('voice-orb');
  orb.className = `voice-orb ${state}`;
}

function setWaveBars(active, speaking = false) {
  const bars = document.getElementById('wave-bars');
  bars.classList.toggle('active', active);
  bars.classList.toggle('speaking', speaking);
}

async function startVoiceSession() {
  const micBtn = document.getElementById('btn-mic');
  const stopBtn = document.getElementById('btn-stop-voice');
  const hint = document.getElementById('voice-hint');

  try {
    // 1. Request mic access
    setVoiceStatus('', 'Solicitando acesso ao microfone...');
    micStream = await navigator.mediaDevices.getUserMedia({
      audio: { sampleRate: 16000, channelCount: 1, echoCancellation: true, noiseSuppression: true }
    });

    // 2. Connect WebSocket to backend
    setVoiceStatus('', 'Conectando com Zé das Coisas...');
    voiceWs = new WebSocket(`${WS_URL}/api/voice`);
    voiceWs.onopen = () => {
      const wsStatus = document.getElementById('debug-ws-status');
      if (wsStatus) {
        wsStatus.textContent = 'Online';
        wsStatus.style.color = 'var(--accent-emerald)';
      }
    };
    voiceWs.onclose = () => {
      const wsStatus = document.getElementById('debug-ws-status');
      if (wsStatus) {
        wsStatus.textContent = 'Off';
        wsStatus.style.color = 'var(--accent-rose)';
      }
      if (isVoiceActive) stopVoiceSession();
    };
    voiceWs.onerror = () => toast('Erro na conexão WebSocket', 'error');

    voiceWs.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      handleVoiceMessage(msg);
    };

    // Wait for WebSocket to be ready
    await new Promise((resolve, reject) => {
      const origOnMsg = voiceWs.onmessage;
      voiceWs.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        if (msg.type === 'connected') {
          voiceWs.onmessage = origOnMsg;
          resolve();
        } else if (msg.type === 'error') {
          reject(new Error(msg.message));
        } else if (msg.type === 'status') {
          setVoiceStatus('', msg.message);
        }
      };
      setTimeout(() => resolve(), 10000); // fallback timeout
    });

    // 3. Start audio capture & streaming
    audioContext = new AudioContext({ sampleRate: 16000 });
    const source = audioContext.createMediaStreamSource(micStream);

    // Use ScriptProcessor for PCM extraction (widely supported)
    micProcessor = audioContext.createScriptProcessor(4096, 1, 1);
    micProcessor.onaudioprocess = (e) => {
      if (!isVoiceActive || !voiceWs || voiceWs.readyState !== WebSocket.OPEN) return;

      const float32 = e.inputBuffer.getChannelData(0);
      // Convert Float32 → Int16 PCM
      const int16 = new Int16Array(float32.length);
      for (let i = 0; i < float32.length; i++) {
        const s = Math.max(-1, Math.min(1, float32[i]));
        int16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
      }

      // Send as base64
      const b64 = arrayBufferToBase64(int16.buffer);
      voiceWs.send(JSON.stringify({ type: 'audio', data: b64 }));
    };

    source.connect(micProcessor);
    micProcessor.connect(audioContext.destination);

    // 4. Update UI
    isVoiceActive = true;
    micBtn.classList.add('active');
    document.getElementById('mic-icon').textContent = '⏹️';
    stopBtn.style.display = 'none';
    hint.textContent = 'Sessão ativa — fale com o Zé';
    setVoiceStatus('connected', 'Conectado — fale agora com o Zé!');
    setOrbState('active');
    setWaveBars(true);
    startWaveAnimation();

  } catch (err) {
    toast(`Erro: ${err.message}`, 'error');
    setVoiceStatus('error', `Erro: ${err.message}`);
    stopVoiceSession();
  }
}

function stopVoiceSession() {
  isVoiceActive = false;

  // Close WebSocket
  if (voiceWs) {
    try { voiceWs.send(JSON.stringify({ type: 'stop' })); } catch {}
    try { voiceWs.close(); } catch {}
    voiceWs = null;
  }

  const wsStatus = document.getElementById('debug-ws-status');
  if (wsStatus) {
    wsStatus.textContent = 'Off';
    wsStatus.style.color = 'var(--accent-rose)';
  }

  // Stop mic
  if (micStream) {
    micStream.getTracks().forEach(t => t.stop());
    micStream = null;
  }

  // Cleanup audio context
  if (micProcessor) { try { micProcessor.disconnect(); } catch {} micProcessor = null; }
  if (audioContext) { try { audioContext.close(); } catch {} audioContext = null; }
  if (playbackContext) { try { playbackContext.close(); } catch {} playbackContext = null; }
  nextPlayTime = 0;

  // Clear playback queue
  playbackQueue = [];
  isPlaying = false;

  // Reset UI
  const micBtn = document.getElementById('btn-mic');
  micBtn.classList.remove('active');
  document.getElementById('mic-icon').textContent = '🎙️';
  document.getElementById('btn-stop-voice').style.display = 'none';
  document.getElementById('voice-hint').textContent = 'Converse sobre qualquer assunto ou pergunte sobre seus documentos';
  document.getElementById('voice-tool-indicator').style.display = 'none';

  setVoiceStatus('', 'Sessão encerrada');
  setOrbState('');
  setWaveBars(false);
  stopWaveAnimation();
}

function handleVoiceMessage(msg) {
  switch (msg.type) {
    case 'audio':
      // Decode base64 PCM and queue for playback
      const pcmData = base64ToArrayBuffer(msg.data);
      playbackQueue.push(pcmData);
      setOrbState('speaking');
      setWaveBars(true, true);
      setVoiceStatus('speaking', 'Zé das Coisas está falando...');
      if (!isPlaying) playNextChunk();
      break;

    case 'turn_complete':
      setOrbState('active');
      setWaveBars(true, false);
      setVoiceStatus('listening', 'Sua vez — fale agora...');
      break;

    case 'interrupted':
      playbackQueue = [];
      isPlaying = false;
      setOrbState('active');
      setWaveBars(true, false);
      setVoiceStatus('listening', 'Interrupção detectada');
      break;

    case 'transcript':
      appendTranscript(msg.text);
      break;

    case 'tool_call':
      showToolCall(msg.name);
      break;

    case 'status':
      setVoiceStatus('connected', msg.message);
      break;

    case 'error':
      toast(`Erro: ${msg.message}`, 'error');
      setVoiceStatus('error', msg.message);
      break;

    case 'connected':
      setVoiceStatus('connected', 'Conectado!');
      addDebugLog('sys', 'WS Conectado com sucesso.');
      document.getElementById('debug-ws-status').textContent = 'Online';
      document.getElementById('debug-ws-status').style.color = 'var(--accent-emerald)';
      break;

    case 'debug':
      if (msg.source === 'RAG') {
        const ragCount = document.getElementById('debug-rag-calls');
        ragCount.textContent = parseInt(ragCount.textContent) + 1;
        let dataStr = typeof msg.data === 'string' ? msg.data : JSON.stringify(msg.data);
        if (dataStr.length > 300) dataStr = dataStr.substring(0, 300) + '...';
        addDebugLog('rag', `<div class="meta">RAG | ${msg.message}</div>${dataStr}`);
      } else {
        addDebugLog('sys', msg.message);
      }
      break;
  }
}

// ─── Audio Playback (24kHz PCM from Gemini) ─────────────────────────────────

function getPlaybackContext() {
  if (!playbackContext || playbackContext.state === 'closed') {
    playbackContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 24000 });
    nextPlayTime = 0;
  }
  if (playbackContext.state === 'suspended') {
    playbackContext.resume();
  }
  return playbackContext;
}

async function playNextChunk() {
  if (playbackQueue.length === 0) {
    isPlaying = false;
    return;
  }

  isPlaying = true;
  const pcmBuffer = playbackQueue.shift();

  try {
    const playCtx = getPlaybackContext();
    const int16 = new Int16Array(pcmBuffer);
    const float32 = new Float32Array(int16.length);
    for (let i = 0; i < int16.length; i++) {
      float32[i] = int16[i] / 32768;
    }

    const audioBuffer = playCtx.createBuffer(1, float32.length, 24000);
    audioBuffer.getChannelData(0).set(float32);

    const source = playCtx.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(playCtx.destination);

    const now = playCtx.currentTime;
    // Se a linha do tempo ficou para trás, reinicia com um buffer mínimo de 60ms para evitar underrun
    if (nextPlayTime < now) {
      nextPlayTime = now + 0.06;
    }

    source.start(nextPlayTime);
    nextPlayTime += audioBuffer.duration;

    // Agenda a execução do próximo chunk um pouco antes dele vencer para garantir fluidez perfeita
    const delayMs = Math.max(0, (nextPlayTime - now - 0.05) * 1000);
    setTimeout(() => {
      playNextChunk();
    }, delayMs);

  } catch (err) {
    console.error('Playback error:', err);
    isPlaying = false;
    playNextChunk();
  }
}

function appendTranscript(text) {
  const el = document.getElementById('voice-transcript');
  el.textContent = text;
  el.scrollTop = el.scrollHeight;
}

function showToolCall(name) {
  const el = document.getElementById('voice-tool-indicator');
  const textEl = document.getElementById('voice-tool-text');
  const labels = {
    'query_documents': '📚 Consultando documentos...',
    'deep_query_documents': '🔬 Busca profunda em andamento...'
  };
  textEl.textContent = labels[name] || `🔧 ${name}`;
  el.style.display = 'flex';
  setTimeout(() => { el.style.display = 'none'; }, 8000);
}

// ─── Wave Bar Animation ─────────────────────────────────────────────────────
let waveAnimationId = null;

function startWaveAnimation() {
  const bars = document.querySelectorAll('.wave-bar');
  function animate() {
    bars.forEach((bar) => {
      const h = 4 + Math.random() * 28;
      bar.style.height = `${h}px`;
    });
    waveAnimationId = requestAnimationFrame(animate);
  }
  animate();
}

function stopWaveAnimation() {
  if (waveAnimationId) cancelAnimationFrame(waveAnimationId);
  waveAnimationId = null;
  document.querySelectorAll('.wave-bar').forEach(b => b.style.height = '4px');
}

// ─── Base64 Helpers ─────────────────────────────────────────────────────────
function arrayBufferToBase64(buffer) {
  const bytes = new Uint8Array(buffer);
  let binary = '';
  for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
  return btoa(binary);
}

function base64ToArrayBuffer(b64) {
  const binary = atob(b64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes.buffer;
}

// ─── Debug Overlay Logic ────────────────────────────────────────────────────
function initDebugOverlay() {
  const overlay = document.getElementById('debug-overlay');
  
  // Shortcut: Ctrl + Shift + D
  document.addEventListener('keydown', (e) => {
    if (e.ctrlKey && e.shiftKey && e.key.toLowerCase() === 'd') {
      overlay.style.display = overlay.style.display === 'none' ? 'flex' : 'none';
      if (overlay.style.display === 'flex') {
        addDebugLog('sys', 'Painel de debug aberto pelo atalho.');
      }
    }
  });

  // Track Audio Status periodically
  setInterval(() => {
    const statusEl = document.getElementById('debug-audio-status');
    if (!isVoiceActive) {
      statusEl.textContent = 'Idle';
      statusEl.style.color = 'var(--text-muted)';
    } else if (isPlaying) {
      statusEl.textContent = 'Tocando (Gemini)';
      statusEl.style.color = 'var(--accent-cyan)';
    } else {
      statusEl.textContent = 'Capturando (Mic)';
      statusEl.style.color = 'var(--accent-emerald)';
    }
  }, 500);
}

function addDebugLog(type, htmlContent) {
  const container = document.getElementById('debug-content');
  const el = document.createElement('div');
  el.className = `debug-log debug-log-${type}`;
  
  const time = new Date().toLocaleTimeString([], { hour12: false, hour: '2-digit', minute:'2-digit', second:'2-digit' });
  el.innerHTML = `<span style="opacity:0.5; font-size:9px; margin-right:4px;">[${time}]</span> ${htmlContent}`;
  
  container.appendChild(el);
  container.scrollTop = container.scrollHeight;
  
  // Limit to 50 logs max to prevent memory bloat
  while (container.children.length > 50) {
    container.removeChild(container.firstChild);
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// ═══ LIBRARY PAGE ═══════════════════════════════════════════════════════
// ═══════════════════════════════════════════════════════════════════════════

function initLibrary() {
  const zone = document.getElementById('upload-zone');
  const fileInput = document.getElementById('file-input');

  zone.addEventListener('click', () => {
    if (window.electronAPI) selectFilesElectron();
    else fileInput.click();
  });

  fileInput.addEventListener('change', (e) => {
    if (e.target.files.length) uploadFiles(e.target.files);
  });

  zone.addEventListener('dragover', (e) => { e.preventDefault(); zone.classList.add('dragover'); });
  zone.addEventListener('dragleave', () => zone.classList.remove('dragover'));
  zone.addEventListener('drop', (e) => {
    e.preventDefault(); zone.classList.remove('dragover');
    const files = Array.from(e.dataTransfer.files).filter(f => {
      const ext = f.name.toLowerCase().split('.').pop();
      return ['pdf', 'docx', 'txt'].includes(ext);
    });
    if (files.length) uploadFiles(files);
    else toast('Apenas arquivos PDF, DOCX ou TXT são aceitos', 'error');
  });
}

async function selectFilesElectron() {
  try {
    const paths = await window.electronAPI.selectFiles();
    if (!paths?.length) return;
    const formData = new FormData();
    const LIMIT = 200 * 1024 * 1024; // 200MB
    for (const filePath of paths) {
      const res = await fetch(`file://${filePath}`);
      const blob = await res.blob();
      if (blob.size > LIMIT) {
        toast(`O arquivo "${filePath.split('/').pop().split('\\').pop()}" excede o limite máximo permitido de 200 MB.`, 'error');
        return;
      }
      formData.append('files', blob, filePath.split('/').pop().split('\\').pop());
    }
    await uploadFormData(formData);
  } catch (err) { toast(`Erro: ${err.message}`, 'error'); }
}

async function uploadFiles(fileList) {
  const formData = new FormData();
  const LIMIT = 200 * 1024 * 1024; // 200MB
  for (const file of fileList) {
    if (file.size > LIMIT) {
      toast(`O arquivo "${file.name}" excede o limite máximo permitido de 200 MB.`, 'error');
      return;
    }
    formData.append('files', file);
  }
  await uploadFormData(formData);
}

async function uploadFormData(formData) {
  try {
    const res = await fetch(`${BACKEND_URL}/api/upload`, { method: 'POST', body: formData });
    const data = await res.json();
    if (data.uploaded.length) {
      toast(`${data.message} Reindexando...`, 'info');
      await api('/api/index', { method: 'POST' });
      toast('Biblioteca pronta e indexada!', 'success');
    }
    if (data.errors.length) data.errors.forEach(e => toast(e, 'error'));
    loadDocuments();
    loadDbStatus();
  } catch (err) { toast(`Erro no upload: ${err.message}`, 'error'); }
}

async function loadDocuments() {
  const container = document.getElementById('doc-list');
  const countEl = document.getElementById('doc-count');
  try {
    const data = await api('/api/documents');
    countEl.textContent = `(${data.total})`;
    if (!data.documents.length) {
      container.innerHTML = `<div class="empty-state"><div class="empty-icon">📭</div><div class="empty-text">Nenhum documento carregado</div></div>`;
      return;
    }
    container.innerHTML = data.documents.map(doc => {
      const ext = doc.name.split('.').pop().toLowerCase();
      const icon = ext === 'pdf' ? '📕' : (ext === 'docx' ? '📘' : '📝');
      return `
        <div class="doc-item">
          <span class="doc-icon">${icon}</span>
          <div class="doc-info">
            <div class="doc-name" title="${doc.name}">${doc.name}</div>
            <div class="doc-size">${doc.size_display}</div>
          </div>
          <button class="doc-delete" onclick="deleteDoc('${doc.name}')" title="Excluir">🗑️</button>
        </div>`;
    }).join('');
  } catch {
    container.innerHTML = `<div class="empty-state"><div class="empty-icon">⚠️</div><div class="empty-text">Erro ao carregar</div></div>`;
  }
}

async function deleteDoc(filename) {
  if (!confirm(`Excluir "${filename}"?`)) return;
  try {
    await api('/api/delete', { method: 'POST', body: JSON.stringify({ filename }) });
    toast(`"${filename}" excluído. Reindexando...`, 'info');
    await api('/api/index', { method: 'POST' });
    toast('Biblioteca atualizada e pronta!', 'success');
    loadDocuments(); loadDbStatus();
  } catch (err) { toast(`Erro: ${err.message}`, 'error'); }
}

// ═══════════════════════════════════════════════════════════════════════════
// ═══ SETTINGS PAGE ══════════════════════════════════════════════════════
// ═══════════════════════════════════════════════════════════════════════════

function initSettings() {
  const input = document.getElementById('input-api-key');
  const toggleBtn = document.getElementById('btn-toggle-key');
  const saveBtn = document.getElementById('btn-save-key');
  const validateBtn = document.getElementById('btn-validate-key');
  const reindexBtn = document.getElementById('btn-reindex');
  const resetDbBtn = document.getElementById('btn-reset-db');

  toggleBtn.addEventListener('click', () => { input.type = input.type === 'password' ? 'text' : 'password'; });

  saveBtn.addEventListener('click', async () => {
    const key = input.value.trim();
    if (!key) { toast('Informe a API Key', 'error'); return; }
    saveBtn.disabled = true; saveBtn.innerHTML = '<span class="spinner"></span> Salvando...';
    try {
      await api('/api/config', { method: 'POST', body: JSON.stringify({ google_api_key: key }) });
      toast('API Key salva!', 'success'); input.value = ''; loadConfig();
    } catch (err) { toast(`Erro: ${err.message}`, 'error'); }
    finally { saveBtn.disabled = false; saveBtn.innerHTML = '💾 Salvar Chave'; }
  });

  validateBtn.addEventListener('click', async () => {
    const key = input.value.trim();
    if (!key) { toast('Informe a API Key', 'error'); return; }
    validateBtn.disabled = true; validateBtn.innerHTML = '<span class="spinner"></span>';
    try {
      const res = await api('/api/config/validate', { method: 'POST', body: JSON.stringify({ google_api_key: key }) });
      document.getElementById('key-status').innerHTML = res.status === 'valid'
        ? `<span class="status-badge success"><span class="dot"></span>${res.message}</span>`
        : `<span class="status-badge error"><span class="dot"></span>${res.message}</span>`;
      toast(res.status === 'valid' ? 'Chave válida!' : 'Chave inválida', res.status === 'valid' ? 'success' : 'error');
    } catch (err) { document.getElementById('key-status').innerHTML = `<span class="status-badge error">${err.message}</span>`; }
    finally { validateBtn.disabled = false; validateBtn.innerHTML = '🔍 Validar'; }
  });

  reindexBtn.addEventListener('click', async () => {
    reindexBtn.disabled = true; reindexBtn.innerHTML = '<span class="spinner"></span> Indexando...';
    const pb = document.getElementById('index-progress');
    pb.style.display = 'block'; pb.classList.add('indeterminate');
    try {
      const res = await api('/api/index', { method: 'POST' });
      toast(res.message, 'success'); loadDbStatus();
    } catch (err) { toast(`Erro: ${err.message}`, 'error'); }
    finally { reindexBtn.disabled = false; reindexBtn.innerHTML = '🔄 Reindexar Biblioteca'; pb.style.display = 'none'; pb.classList.remove('indeterminate'); }
  });

  resetDbBtn.addEventListener('click', async () => {
    if (!confirm('Apagar todo o banco de dados vetorial?')) return;
    try { await api('/api/reset-db', { method: 'POST' }); toast('Banco resetado', 'success'); loadDbStatus(); }
    catch (err) { toast(`Erro: ${err.message}`, 'error'); }
  });
}

async function loadConfig() {
  try {
    const config = await api('/api/config');
    document.getElementById('key-status').innerHTML = config.google_api_key_set
      ? `<span class="status-badge success"><span class="dot"></span>Chave configurada: ${config.google_api_key_masked}</span>`
      : `<span class="status-badge warning"><span class="dot"></span>Nenhuma chave configurada</span>`;
  } catch {}
}

async function loadDbStatus() {
  try {
    const data = await api('/api/db-status');
    document.getElementById('stat-pdfs').textContent = data.pdf_count;
    document.getElementById('stat-chunks').textContent = data.chunks_indexed;
    if (data.is_indexing) {
      document.getElementById('stat-status').textContent = '🔄 Indexando...';
    } else {
      document.getElementById('stat-status').textContent = data.db_exists ? '🟢' : '🔴';
    }

    const micBtn = document.getElementById('btn-mic');
    if (micBtn) {
      if (data.is_indexing || !data.db_exists || data.chunks_indexed === 0) {
        micBtn.disabled = true;
        micBtn.style.opacity = '0.4';
        micBtn.style.pointerEvents = 'none';
        micBtn.title = 'Aguarde a indexação da biblioteca técnica para conversar.';
      } else {
        micBtn.disabled = false;
        micBtn.style.opacity = '1';
        micBtn.style.pointerEvents = 'auto';
        micBtn.title = 'Iniciar Conversação de Voz';
      }
    }
  } catch { document.getElementById('stat-status').textContent = '⚠️'; }
}
