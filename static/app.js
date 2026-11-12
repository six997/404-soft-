(() => {
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];

  // 字母图标配色
  $$(".icon.letter").forEach(el => el.style.setProperty("--h", el.dataset.hue));

  // 深色模式
  $("#theme")?.addEventListener("click", () => {
    const root = document.documentElement;
    const dark = root.dataset.theme === "dark" ||
      (!root.dataset.theme && matchMedia("(prefers-color-scheme: dark)").matches);
    root.dataset.theme = dark ? "light" : "dark";
    localStorage.theme = root.dataset.theme;
  });

  // 搜索 + 平台筛选
  const list = $("#list");
  if (list) {
    const q = $("#q"), empty = $("#empty");
    let plat = "";
    const apply = () => {
      const kw = (q.value || "").trim().toLowerCase();
      let shown = 0;
      $$(".soft-card", list).forEach(c => {
        const ok = (!kw || c.dataset.name.includes(kw)) && (!plat || c.dataset.platforms.split(" ").includes(plat));
        c.hidden = !ok;
        if (ok) shown++;
      });
      $$('.ad-slot[data-ad="feed"]', list).forEach(a => a.hidden = !!(kw || plat));
      empty.hidden = shown > 0;
    };
    q.addEventListener("input", apply);
    $$(".chip").forEach(ch => ch.addEventListener("click", () => {
      $$(".chip").forEach(x => x.classList.remove("on"));
      ch.classList.add("on");
      plat = ch.dataset.plat;
      apply();
    }));
    $$(".hot").forEach(h => h.addEventListener("click", () => { q.value = h.dataset.q; apply(); q.focus(); }));
    if (location.hash === "#search") q.focus();
  }

  // 复制 SHA-256
  $$(".sha").forEach(b => b.addEventListener("click", async () => {
    try { await navigator.clipboard.writeText(b.dataset.sha); } catch { return; }
    b.classList.add("copied");
    setTimeout(() => b.classList.remove("copied"), 1200);
  }));

  // 广告位：读取 ads.json，进入视口再加载；?ads=debug 显示所有占位
  const slots = $$(".ad-slot");
  if (!slots.length) return;
  const debug = new URLSearchParams(location.search).get("ads") === "debug";
  fetch((window.BASE || "") + "/ads.json").then(r => r.json()).catch(() => ({})).then(conf => {
    let adsense = false;
    const render = el => {
      const id = el.dataset.ad, c = conf[id];
      if (!c) {
        if (debug) { el.classList.add("debug"); el.textContent = "广告位：" + id; }
        return;
      }
      el.classList.add("on");
      if (c.type === "image") {
        const a = document.createElement("a");
        a.href = c.href; a.target = "_blank"; a.rel = "sponsored noopener";
        const img = new Image(); img.src = c.img; img.alt = c.alt || ""; img.loading = "lazy";
        a.appendChild(img); el.appendChild(a);
      } else if (c.type === "html") {
        el.innerHTML = c.html;
      } else if (c.type === "adsense") {
        if (!adsense) {
          const s = document.createElement("script");
          s.async = true; s.crossOrigin = "anonymous";
          s.src = "https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=" + c.client;
          document.head.appendChild(s); adsense = true;
        }
        el.innerHTML = `<ins class="adsbygoogle" style="display:block;width:100%" data-ad-client="${c.client}" data-ad-slot="${c.slot}" data-ad-format="auto" data-full-width-responsive="true"></ins>`;
        (window.adsbygoogle = window.adsbygoogle || []).push({});
      }
    };
    const io = new IntersectionObserver(es => es.forEach(en => {
      if (en.isIntersecting) { render(en.target); io.unobserve(en.target); }
    }), { rootMargin: "200px" });
    slots.forEach(s => io.observe(s));
  });
})();
