// Musobaqa taymerlari: [data-deadline] — UTC millisekund. Nolga yetganda sahifa yangilanadi.
(() => {
  const items = [...document.querySelectorAll('[data-deadline]')];
  if (!items.length) return;
  const pad = (n) => String(n).padStart(2, '0');
  let reloaded = false;
  function tick() {
    const now = Date.now();
    items.forEach((el) => {
      const left = Math.max(0, Math.floor((Number(el.dataset.deadline) - now) / 1000));
      const days = Math.floor(left / 86400);
      const hours = Math.floor((left % 86400) / 3600);
      const minutes = Math.floor((left % 3600) / 60);
      const seconds = left % 60;
      if (el.dataset.style === 'blocks') {
        el.querySelector('[data-part="d"]').textContent = pad(days);
        el.querySelector('[data-part="h"]').textContent = pad(hours);
        el.querySelector('[data-part="m"]').textContent = pad(minutes);
        el.querySelector('[data-part="s"]').textContent = pad(seconds);
      } else {
        el.textContent = (days ? `${days}d ` : '') + `${pad(hours)}:${pad(minutes)}:${pad(seconds)}`;
      }
      if (left === 0 && el.dataset.reload !== 'no' && !reloaded) {
        reloaded = true;
        setTimeout(() => location.reload(), 1500);
      }
    });
  }
  tick();
  setInterval(tick, 1000);
})();
