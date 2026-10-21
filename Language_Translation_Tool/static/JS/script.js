(() => {
  const $ = (id) => document.getElementById(id);
  const el = {
    source: $("source"), target: $("target"), input: $("input"), output: $("output"),
    translate: $("translate"), copy: $("copy"), speak: $("speak"), swap: $("swap"),
    clear: $("clear"), count: $("count"), error: $("error"), detected: $("detected"),
  };
  let maxChars = 500, languages = {}, lastTranslation = "", lastTargetLang = "en";

  const showError = (msg) => { el.error.textContent = msg; el.error.hidden = false; };
  const hideError = () => { el.error.hidden = true; };

  function setOutput(text, isPlaceholder = false) {
    el.output.textContent = text;
    el.output.classList.toggle("placeholder", isPlaceholder);
  }

  function fillSelect(select, includeAuto, selected) {
    select.innerHTML = "";
    if (includeAuto) select.add(new Option("Detect language", "auto"));
    for (const [code, name] of Object.entries(languages)) select.add(new Option(name, code));
    select.value = selected;
  }

  async function loadLanguages() {
    try {
      const res = await fetch("/api/languages");
      if (!res.ok) throw new Error();
      const data = await res.json();
      languages = data.languages;
      maxChars = data.maxChars;
      fillSelect(el.source, data.autoDetect, data.autoDetect ? "auto" : "en");
      fillSelect(el.target, false, "hi");
      el.input.maxLength = maxChars;
      updateCount();
    } catch {
      showError("Could not load the language list. Make sure the server is running, then reload.");
      el.translate.disabled = true;
    }
  }

  function updateCount() { el.count.textContent = `${el.input.value.length} / ${maxChars}`; }

  async function translate() {
    hideError();
    const text = el.input.value.trim();
    if (!text) return showError("Enter some text to translate.");
    if (el.source.value === el.target.value) return showError("Choose two different languages.");
    if (!navigator.onLine) return showError("You are offline. Check your connection and try again.");

    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 20000);
    el.translate.disabled = true;
    el.translate.firstChild.textContent = "Translating… ";
    setOutput("Translating…", true);

    try {
      const res = await fetch("/api/translate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, source: el.source.value, target: el.target.value }),
        signal: ctrl.signal,
      });
      let data = {};
      try { data = await res.json(); } catch { /* non-JSON response */ }
      if (!res.ok) throw new Error(data.error || `Server error (${res.status}).`);

      lastTranslation = data.translation;
      lastTargetLang = el.target.value;
      el.output.lang = lastTargetLang;
      setOutput(lastTranslation);
      el.detected.textContent = data.detectedSource
        ? `Detected: ${languages[data.detectedSource] || data.detectedSource}` : "";
      el.copy.disabled = el.speak.disabled = false;
    } catch (err) {
      setOutput("Your translation will appear here.", true);
      el.copy.disabled = el.speak.disabled = true;
      showError(err.name === "AbortError" ? "The request took too long. Try again." :
                err instanceof TypeError ? "Could not reach the server. Check your connection." : err.message);
    } finally {
      clearTimeout(timer);
      el.translate.disabled = false;
      el.translate.firstChild.textContent = "Translate ";
    }
  }

  async function copyText() {
    try {
      await navigator.clipboard.writeText(lastTranslation);
    } catch {
      const ta = document.createElement("textarea");   // fallback for older browsers / http
      ta.value = lastTranslation; document.body.appendChild(ta); ta.select();
      const ok = document.execCommand("copy"); ta.remove();
      if (!ok) return showError("Could not copy. Select the text and copy it manually.");
    }
    el.copy.textContent = "Copied";
    setTimeout(() => (el.copy.textContent = "Copy"), 1500);
  }

  function speak() {
    if (!("speechSynthesis" in window)) return showError("Your browser does not support text-to-speech.");
    hideError();
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(lastTranslation);
    u.lang = lastTargetLang;
    u.onerror = (e) => { if (e.error !== "canceled" && e.error !== "interrupted")
      showError("Could not play audio. Your device may not have a voice for this language."); };
    window.speechSynthesis.speak(u);
  }

  function swap() {
    if (el.source.value === "auto") return showError("Pick a specific source language to swap.");
    [el.source.value, el.target.value] = [el.target.value, el.source.value];
    if (lastTranslation) { el.input.value = lastTranslation; updateCount(); translate(); }
  }

  el.translate.addEventListener("click", translate);
  el.copy.addEventListener("click", copyText);
  el.speak.addEventListener("click", speak);
  el.swap.addEventListener("click", swap);
  el.input.addEventListener("input", updateCount);
  el.input.addEventListener("keydown", (e) => { if ((e.ctrlKey || e.metaKey) && e.key === "Enter") translate(); });
  el.clear.addEventListener("click", () => {
    el.input.value = ""; updateCount(); hideError(); lastTranslation = "";
    setOutput("Your translation will appear here.", true);
    el.detected.textContent = ""; el.copy.disabled = el.speak.disabled = true; el.input.focus();
  });

  setOutput("Your translation will appear here.", true);
  loadLanguages();
})();
