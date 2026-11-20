// Masala sahifasi (ochiq arxiv): tablar, yechim yuborish va natijani kutish.
(() => {
  const config = JSON.parse(document.getElementById('codingConfig').textContent);
  const ide = window.initIde(config);
  const form = document.getElementById('codeForm');
  const submitButton = document.getElementById('ideSubmit');
  const resultBox = document.getElementById('resultBox');
  const csrf = document.querySelector('meta[name="csrf-token"]').content;

  function showTab(id) {
    document.querySelectorAll('.pub-tabs button').forEach((button) => button.classList.toggle('active', button.dataset.tab === id));
    document.querySelectorAll('.pub-tab-pane').forEach((pane) => { pane.hidden = pane.id !== id; });
  }
  document.querySelectorAll('.pub-tabs button').forEach((button) => button.addEventListener('click', () => showTab(button.dataset.tab)));
  // "Ishga tushirish" bosilsa konsol ko'rinsin.
  document.getElementById('ideRun').addEventListener('click', () => showTab('tabTests'), true);

  function setResult(label, kind, detail) {
    resultBox.textContent = '';
    const badge = document.createElement('span');
    badge.className = `pub-verdict big v-${kind}`;
    badge.textContent = label;
    resultBox.appendChild(badge);
    if (detail) {
      const div = document.createElement('div');
      div.className = 'pub-result-detail';
      div.textContent = detail;
      resultBox.appendChild(div);
    }
  }

  async function refreshMine() {
    try {
      const response = await fetch(location.href, {cache: 'no-store', credentials: 'same-origin'});
      const doc = new DOMParser().parseFromString(await response.text(), 'text/html');
      const fresh = doc.getElementById('mySubs');
      if (fresh) document.getElementById('mySubs').innerHTML = fresh.innerHTML;
      const freshResult = doc.getElementById('resultBox');
      if (freshResult) resultBox.innerHTML = freshResult.innerHTML;
    } catch (error) { /* keyingi yangilashda */ }
  }

  function poll(id) {
    submitButton.disabled = true;
    setResult(t('Kutilmoqda'), 'pending');
    const url = config.statusUrl.replace('/0.json', `/${id}.json`);
    const tick = async () => {
      try {
        const response = await fetch(url, {cache: 'no-store', credentials: 'same-origin'});
        const data = await response.json();
        if (data.status === 'pending') { setTimeout(tick, 1500); return; }
        submitButton.disabled = false;
        await refreshMine();
      } catch (error) {
        setTimeout(tick, 3000);
      }
    };
    setTimeout(tick, 1200);
  }

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (window.codeEditor) window.codeEditor.save();
    if (!document.getElementById('source_code').value.trim()) {
      showTab('tabResult');
      setResult(t('Avval kod yozing.'), 'error');
      return;
    }
    submitButton.disabled = true;
    showTab('tabResult');
    try {
      const response = await fetch(form.action, {
        method: 'POST',
        body: new FormData(form),
        headers: {'X-Requested-With': 'fetch', 'X-CSRF-Token': csrf},
        credentials: 'same-origin',
      });
      const data = await response.json();
      if (response.status === 202 && data.id) {
        poll(data.id);
        return;
      }
      setResult(data.error || data.message || t('Server xatosi'), 'error');
    } catch (error) {
      setResult(t('Server bilan aloqa uzildi. Qayta urinib ko‘ring.'), 'error');
    }
    submitButton.disabled = false;
  });

  if (config.pendingId) { showTab('tabResult'); poll(config.pendingId); }
  void ide;
})();
