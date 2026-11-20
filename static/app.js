const calm = matchMedia("(prefers-reduced-motion: reduce)").matches;
const fmt = n => "Rs " + n.toLocaleString("en-IN", {minimumFractionDigits: 2, maximumFractionDigits: 2});

// balance counts up from zero
document.querySelectorAll("[data-count]").forEach(el => {
  const target = Number(el.dataset.count) / 100;
  if (calm) return;
  const start = performance.now(), dur = 1300;
  (function tick(now) {
    const p = Math.min((now - start) / dur, 1);
    el.textContent = fmt(target * (1 - Math.pow(1 - p, 4)));
    if (p < 1) requestAnimationFrame(tick);
  })(start);
});

// ripple on buttons
document.addEventListener("click", e => {
  const b = e.target.closest("button");
  if (!b || calm) return;
  const r = b.getBoundingClientRect(), s = Math.max(r.width, r.height);
  const dot = document.createElement("span");
  dot.className = "ripple";
  dot.style.cssText = `width:${s}px;height:${s}px;left:${e.clientX - r.left - s / 2}px;top:${e.clientY - r.top - s / 2}px`;
  b.appendChild(dot);
  setTimeout(() => dot.remove(), 700);
});

// 3D tilt on the bank card
document.querySelectorAll(".tilt").forEach(wrap => {
  const card = wrap.firstElementChild;
  if (calm) return;
  wrap.addEventListener("mousemove", e => {
    const r = wrap.getBoundingClientRect();
    const x = (e.clientX - r.left) / r.width - .5, y = (e.clientY - r.top) / r.height - .5;
    card.style.transform = `rotateY(${x * 16}deg) rotateX(${-y * 16}deg)`;
  });
  wrap.addEventListener("mouseleave", () => card.style.transform = "");
});

// remove toasts after they fade
document.querySelectorAll(".toast").forEach(t => setTimeout(() => t.remove(), 5200));
