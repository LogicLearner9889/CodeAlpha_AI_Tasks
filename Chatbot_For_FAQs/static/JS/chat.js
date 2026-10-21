(() => {
  'use strict';

  const MAX_LEN = 2000;          // must match MAX_QUERY_LENGTH in chatbot.py
  const TIMEOUT_MS = 15000;      // give up on a request after 15 s
  const MAX_RETRIES = 2;         // extra attempts for network / 5xx failures
  const STORE_KEY = 'faq_chat_history_v1';
  const MAX_STORED = 100;        // keep the last 100 messages in the browser

  const $ = (id) => document.getElementById(id);
  const log = $('log');
  const form = $('form');
  const input = $('input');
  const sendBtn = $('send');
  const counter = $('counter');
  const banner = $('banner');
  const clearBtn = $('clear');
  const chips = $('chips');
  const statusDot = $('status-dot');
  const statusText = $('status-text');

  const reduceMotion = window.matchMedia &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  let sending = false;
  let history = [];

  /* ---------- storage that never throws (private mode, blocked storage) ---------- */
  const store = {
    get() {
      try { return JSON.parse(localStorage.getItem(STORE_KEY) || '[]'); }
      catch (e) { return []; }
    },
    set(value) {
      try { localStorage.setItem(STORE_KEY, JSON.stringify(value)); }
      catch (e) { /* storage full or blocked: chat still works */ }
    },
    clear() {
      try { localStorage.removeItem(STORE_KEY); } catch (e) { /* ignore */ }
    }
  };

  /* ---------- rendering ---------- */
  function scrollToBottom() {
    log.scrollTo({ top: log.scrollHeight, behavior: reduceMotion ? 'auto' : 'smooth' });
  }

  function makeMessage(role, text) {
    const div = document.createElement('div');
    div.className = 'msg ' + role;
    div.textContent = text;
    return div;
  }

  function addMeta(div, text) {
    const small = document.createElement('small');
    small.className = 'meta';
    small.textContent = text;
    div.appendChild(small);
  }

  function addPills(div, items, onClick) {
    const wrap = document.createElement('div');
    wrap.className = 'actions';
    items.forEach(({ label, value }) => {
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'pill';
      b.textContent = label;
      b.addEventListener('click', () => onClick(value));
      wrap.appendChild(b);
    });
    div.appendChild(wrap);
  }

  function renderItem(item) {
    const div = makeMessage(item.role, item.text);
    if (item.info) addMeta(div, item.info);
    if (item.suggestions && item.suggestions.length) {
      addMeta(div, 'Did you mean:');
      addPills(div, item.suggestions.map((s) => ({ label: s, value: s })), ask);
    }
    if (item.retry) {
      addPills(div, [{ label: 'Try again', value: item.retry }], (q) => {
        div.remove();
        history = history.filter((h) => h !== item);
        save();
        ask(q, { echo: false });
      });
    }
    log.appendChild(div);
    scrollToBottom();
    return div;
  }

  function save() {
    // error bubbles with a "Try again" button are temporary and never stored
    store.set(history.filter((m) => !m.retry).slice(-MAX_STORED));
  }

  function push(item) {
    history.push(item);
    save();
    return renderItem(item);
  }

  function showTyping() {
    const div = document.createElement('div');
    div.className = 'msg bot';
    div.setAttribute('aria-label', 'Assistant is typing');
    div.innerHTML = '<span class="typing"><span></span><span></span><span></span></span>';
    log.appendChild(div);
    scrollToBottom();
    return div;
  }

  /* ---------- state helpers ---------- */
  function updateCounter() {
    const n = input.value.length;
    counter.textContent = n + ' / ' + MAX_LEN;
    counter.classList.toggle('is-near', n >= MAX_LEN * 0.9 && n < MAX_LEN);
    counter.classList.toggle('is-full', n >= MAX_LEN);
  }

  function updateSendState() {
    const empty = !input.value.trim();
    sendBtn.disabled = sending || empty;
  }

  function autosize() {
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 150) + 'px';
  }

  function setOnline(isOnline) {
    banner.hidden = isOnline;
    statusDot.classList.toggle('is-offline', !isOnline);
    statusText.textContent = isOnline ? 'Online' : 'Offline';
  }

  /* ---------- networking ---------- */
  function describeFailure(err) {
    if (err.kind === 'offline') return 'You are offline. Reconnect to the internet, then try again.';
    if (err.kind === 'timeout') return 'The server took too long to reply. Please try again.';
    if (err.kind === 'network') return 'Could not reach the server. Check your connection and try again.';
    if (err.status === 429) return 'Too many requests. Wait a few seconds and try again.';
    if (err.status === 503) return err.message || 'The chatbot is unavailable right now.';
    if (err.status >= 500) return 'The server had a problem. Please try again in a moment.';
    return err.message || 'Something went wrong. Please try again.';
  }

  async function requestOnce(text) {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), TIMEOUT_MS);
    try {
      const res = await fetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text }),
        signal: ctrl.signal
      });
      let data = {};
      try { data = await res.json(); } catch (e) { /* non-JSON error page */ }
      if (!res.ok) {
        const e = new Error(data.error || '');
        e.status = res.status;
        throw e;
      }
      return data;
    } catch (e) {
      if (e.status) throw e;
      const err = new Error('');
      err.kind = e.name === 'AbortError' ? 'timeout' : 'network';
      throw err;
    } finally {
      clearTimeout(timer);
    }
  }

  async function requestWithRetry(text) {
    let lastErr;
    for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
      if (!navigator.onLine) {
        const e = new Error('');
        e.kind = 'offline';
        throw e;
      }
      try {
        return await requestOnce(text);
      } catch (err) {
        lastErr = err;
        const retriable = err.kind === 'network' || err.kind === 'timeout' ||
          (err.status >= 500 && err.status !== 503);
        if (!retriable || attempt === MAX_RETRIES) break;
        await new Promise((r) => setTimeout(r, 600 * (attempt + 1)));
      }
    }
    throw lastErr;
  }

  /* ---------- main flow ---------- */
  async function ask(text, { echo = true } = {}) {
    text = String(text || '').trim();
    if (!text || sending) return;
    if (text.length > MAX_LEN) text = text.slice(0, MAX_LEN);

    if (echo) push({ role: 'user', text });
    sending = true;
    updateSendState();
    chips.hidden = true;
    const typing = showTyping();

    try {
      const data = await requestWithRetry(text);
      typing.remove();
      const info = data.matched
        ? 'Matched: "' + data.matched_question + '" (' + Math.round(data.score * 100) + '%)'
        : '';
      push({
        role: 'bot',
        text: data.answer || 'No answer was returned.',
        info,
        suggestions: data.suggestions || []
      });
    } catch (err) {
      typing.remove();
      const retriable = err.kind || (err.status >= 500);
      push({ role: 'bot error', text: describeFailure(err), retry: retriable ? text : null });
    } finally {
      sending = false;
      updateSendState();
      input.focus({ preventScroll: true });
    }
  }

  /* ---------- welcome + restore ---------- */
  function showWelcome() {
    log.innerHTML = '';
    renderItem({
      role: 'bot',
      text: 'Hi! Ask me about accounts, orders, shipping, payments, returns, products or technical problems.'
    });
    const note = document.querySelector('[data-startup-error]');
    if (note) renderItem({ role: 'bot error', text: note.textContent.trim() });
  }

  function restore() {
    showWelcome();
    const saved = store.get();
    if (Array.isArray(saved) && saved.length) {
      history = saved.filter((m) => m && typeof m.text === 'string');
      history.forEach((m) => renderItem(Object.assign({}, m, { retry: null })));
      chips.hidden = true;
    }
  }

  /* ---------- events ---------- */
  form.addEventListener('submit', (e) => {
    e.preventDefault();
    const text = input.value;
    if (!text.trim() || sending) return;
    input.value = '';
    autosize();
    updateCounter();
    updateSendState();
    ask(text);
  });

  input.addEventListener('input', () => {
    updateCounter();
    updateSendState();
    autosize();
  });

  input.addEventListener('keydown', (e) => {
    // Enter sends, Shift+Enter adds a new line (skip while an IME is composing)
    if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
      e.preventDefault();
      form.requestSubmit ? form.requestSubmit() : form.dispatchEvent(new Event('submit', { cancelable: true }));
    }
  });

  chips.addEventListener('click', (e) => {
    const b = e.target.closest('[data-q]');
    if (b) ask(b.dataset.q);
  });

  clearBtn.addEventListener('click', () => {
    history = [];
    store.clear();
    showWelcome();
    chips.hidden = false;
    input.focus();
  });

  window.addEventListener('online', () => setOnline(true));
  window.addEventListener('offline', () => setOnline(false));

  // Keep the newest message visible when the mobile keyboard opens or the screen rotates
  if (window.visualViewport) {
    window.visualViewport.addEventListener('resize', scrollToBottom);
  }
  window.addEventListener('orientationchange', () => setTimeout(scrollToBottom, 250));

  // Report unexpected script errors in the chat instead of failing silently
  window.addEventListener('error', () => {
    if (!sending) renderItem({ role: 'bot error', text: 'Something unexpected happened in the page. Reload and try again.' });
  });

  /* ---------- start ---------- */
  if (!window.fetch || !window.AbortController || !window.Promise) {
    showWelcome();
    renderItem({
      role: 'bot error',
      text: 'This browser is too old to run the chat. Please update it or try Chrome, Firefox, Safari or Edge.'
    });
    input.disabled = true;
    sendBtn.disabled = true;
    return;
  }

  setOnline(navigator.onLine !== false);
  restore();
  updateCounter();
  updateSendState();
  autosize();
})();
