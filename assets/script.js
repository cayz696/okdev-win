/* =========================================================================
   Oleksandr Kalinovskyi — Portfolio site logic
   Scroll animations · Mobile nav · Contact form · Blog · Post pages
   Config lives in assets/config.js (load it before this file).
   ========================================================================= */

const CONTACT_FORM_CONFIG = {
  get workerUrl() {
    return (typeof SITE_CONFIG !== "undefined" && SITE_CONFIG.workerUrl) || "PASTE_YOUR_WORKER_URL_HERE";
  },
};

document.addEventListener("DOMContentLoaded", () => {
  initScrollProgress();
  initHeaderScroll();
  initStaggerReveal();
  initCounterAnimation();
  renderImpactCharts();
  initRevealAnimations();
  initMobileNav();
  initContactForm();
  initBlog();
  initPostPage();
  initCardTilt();
});

function workerReady() {
  return CONTACT_FORM_CONFIG.workerUrl && !CONTACT_FORM_CONFIG.workerUrl.startsWith("PASTE_");
}

function blogBasePath() {
  const lang = document.documentElement.lang === "en" ? "en/blog" : "blog";
  return `/${lang}`;
}

function postUrl(slug) {
  return `${blogBasePath()}/${slug}`;
}

function imageUrl(post) {
  if (!post.imageId || !workerReady()) return "";
  return `${CONTACT_FORM_CONFIG.workerUrl}/images/${post.imageId}`;
}

/* ---------------- Blog list ---------------- */
const BLOG_PAGE_SIZE = 20;

async function initBlog() {
  const grid = document.getElementById("blog-grid");
  if (!grid) return;

  const lang = grid.dataset.lang || "uk";
  const emptyMsg = grid.dataset.empty || "";
  const errorMsg = grid.dataset.error || "";
  const readMore = grid.dataset.readMore || (lang === "uk" ? "Читати →" : "Read →");
  const loadMoreLabel = lang === "uk" ? "Показати ще" : "Load more";
  const countLabel = (shown, total) =>
    lang === "uk" ? `Показано ${shown} з ${total}` : `Showing ${shown} of ${total}`;

  if (!workerReady()) {
    grid.innerHTML = `<p class="blog-status">${errorMsg}</p>`;
    return;
  }

  grid.innerHTML = `<p class="blog-status">${lang === "uk" ? "Завантажую…" : "Loading…"}</p>`;
  grid._blogState = { lang, offset: 0, total: 0, items: [] };

  async function fetchPage(offset) {
    const res = await fetch(
      `${CONTACT_FORM_CONFIG.workerUrl}/posts?lang=${encodeURIComponent(lang)}&limit=${BLOG_PAGE_SIZE}&offset=${offset}`,
    );
    const data = await res.json().catch(() => ({}));
    if (!res.ok || !data.ok) throw new Error("Worker error");
    return data;
  }

  function renderPosts(posts, append) {
    const dateFmt = new Intl.DateTimeFormat(lang === "uk" ? "uk-UA" : "en-US", {
      year: "numeric", month: "long", day: "numeric",
    });
    const startIdx = append ? grid._blogState.items.length : 0;
    const html = posts.map((p, i) => {
      const idx = startIdx + i;
      const date = p.publishedAt ? dateFmt.format(new Date(p.publishedAt)) : "";
      const tags = Array.isArray(p.tags) ? p.tags : [];
      const img = imageUrl(p);
      const slug = p.slug || p.id;
      const panelId = `blog-panel-${idx}`;
      return `
        <article class="blog-item reveal stagger-item is-visible" style="--stagger:${(idx % BLOG_PAGE_SIZE) * 0.04}s">
          <button class="blog-item-toggle" type="button" aria-expanded="false" aria-controls="${panelId}">
            <span class="blog-item-head">
              <span class="blog-item-date">${date}</span>
              <span class="blog-item-title">${escapeHtml(p.title || "")}</span>
            </span>
            <span class="blog-item-chevron" aria-hidden="true"></span>
          </button>
          <div class="blog-item-panel" id="${panelId}" hidden>
            ${img ? `<div class="blog-item-image"><img src="${img}" alt="" loading="lazy"></div>` : ""}
            <p>${escapeHtml(p.summary || "")}</p>
            ${tags.length ? `<div class="blog-tags">${tags.map((t) => `<span>${escapeHtml(t)}</span>`).join("")}</div>` : ""}
            <a href="${postUrl(slug)}" class="blog-item-link">${readMore}</a>
          </div>
        </article>`;
    }).join("");
    return html;
  }

  function bindToggles(root) {
    root.querySelectorAll(".blog-item-toggle").forEach((btn) => {
      if (btn.dataset.bound) return;
      btn.dataset.bound = "1";
      btn.addEventListener("click", () => {
        const panel = btn.nextElementSibling;
        const isOpen = btn.getAttribute("aria-expanded") === "true";
        btn.setAttribute("aria-expanded", String(!isOpen));
        panel.hidden = isOpen;
        btn.closest(".blog-item").classList.toggle("is-open", !isOpen);
      });
    });
  }

  function renderFooter(state) {
    let footer = grid.parentElement.querySelector(".blog-list-footer");
    if (!footer) {
      footer = document.createElement("div");
      footer.className = "blog-list-footer";
      grid.after(footer);
    }
    const shown = state.items.length;
    if (!shown) {
      footer.innerHTML = "";
      return;
    }
    footer.innerHTML = `
      <p class="blog-count">${countLabel(shown, state.total)}</p>
      ${state.hasMore ? `<button type="button" class="btn btn-secondary blog-load-more">${loadMoreLabel}</button>` : ""}`;
    const btn = footer.querySelector(".blog-load-more");
    if (btn) btn.addEventListener("click", () => loadMore());
  }

  async function loadMore() {
    const state = grid._blogState;
    const btn = grid.parentElement.querySelector(".blog-load-more");
    if (btn) { btn.disabled = true; btn.textContent = lang === "uk" ? "Завантажую…" : "Loading…"; }
    try {
      const data = await fetchPage(state.offset);
      state.items = state.items.concat(data.posts || []);
      state.offset = state.items.length;
      state.total = data.total || state.items.length;
      state.hasMore = !!data.hasMore;
      const wrap = document.createElement("div");
      wrap.innerHTML = renderPosts(data.posts || [], true);
      while (wrap.firstChild) grid.appendChild(wrap.firstChild);
      bindToggles(grid);
      renderFooter(state);
    } catch {
      if (btn) { btn.disabled = false; btn.textContent = loadMoreLabel; }
    }
  }

  try {
    const data = await fetchPage(0);
    const posts = Array.isArray(data.posts) ? data.posts : [];
    grid._blogState = {
      lang, offset: posts.length, total: data.total || posts.length,
      hasMore: !!data.hasMore, items: posts,
    };
    if (!posts.length) {
      grid.innerHTML = `<p class="blog-status">${emptyMsg}</p>`;
      renderFooter({ items: [], total: 0, hasMore: false });
      return;
    }
    grid.innerHTML = renderPosts(posts, false);
    bindToggles(grid);
    renderFooter(grid._blogState);
  } catch {
    grid.innerHTML = `<p class="blog-status">${errorMsg}</p>`;
  }
}

/* ---------------- Blog post page ---------------- */
async function initPostPage() {
  const root = document.getElementById("post-root");
  if (!root) return;

  const lang = root.dataset.lang || "uk";
  const slug = getPostSlugFromPath();
  if (!slug) {
    root.innerHTML = `<p class="blog-status">${root.dataset.notFound || "Post not found"}</p>`;
    return;
  }

  if (!workerReady()) {
    root.innerHTML = `<p class="blog-status">${root.dataset.error || "Error"}</p>`;
    return;
  }

  try {
    const res = await fetch(`${CONTACT_FORM_CONFIG.workerUrl}/posts/${encodeURIComponent(slug)}?lang=${lang}`);
    const data = await res.json().catch(() => ({}));
    if (!res.ok || !data.ok || !data.post) throw new Error("Not found");

    const p = data.post;
    const dateFmt = new Intl.DateTimeFormat(lang === "uk" ? "uk-UA" : "en-US", {
      year: "numeric", month: "long", day: "numeric",
    });
    const date = p.publishedAt ? dateFmt.format(new Date(p.publishedAt)) : "";
    const tags = Array.isArray(p.tags) ? p.tags : [];
    const keywords = Array.isArray(p.keywords) ? p.keywords : [];
    const img = imageUrl(p);
    const domain = (typeof SITE_CONFIG !== "undefined" && SITE_CONFIG.domain) || "";

    document.title = `${p.title} — ok.dev`;
    applyPostSeo(p, slug, lang, img, domain);

    root.innerHTML = `
      <article class="post-article reveal is-visible">
        <a href="${blogBasePath()}/" class="post-back">← ${root.dataset.back || "Blog"}</a>
        <div class="blog-card-meta">${date}</div>
        <h1>${escapeHtml(p.title || "")}</h1>
        ${img ? `<div class="post-hero-image"><img src="${img}" alt="${escapeHtml(p.title || "")}" loading="lazy"></div>` : ""}
        <div class="post-body">${formatPostBody(p.body || "")}</div>
        ${tags.length ? `<div class="blog-tags">${tags.map((t) => `<span>${escapeHtml(t)}</span>`).join("")}</div>` : ""}
        ${keywords.length ? `<p class="post-keywords-label">${root.dataset.keywordsLabel || "Keywords"}: <span>${keywords.map((k) => escapeHtml(k)).join(", ")}</span></p>` : ""}
        ${keywords.length ? `<div class="blog-keywords" aria-hidden="true">${keywords.map((k) => escapeHtml(k)).join(" · ")}</div>` : ""}
        <div class="post-cta">
          <a href="${lang === "uk" ? "/" : "/en/"}#contact" class="btn btn-primary">${root.dataset.cta || "Discuss a project →"}</a>
        </div>
      </article>`;

    injectPostJsonLd(p, domain, lang);
  } catch {
    root.innerHTML = `<p class="blog-status">${root.dataset.notFound || "Post not found"}</p>`;
  }
}

function getPostSlugFromPath() {
  const params = new URLSearchParams(window.location.search);
  if (params.get("slug")) return params.get("slug");
  const parts = window.location.pathname.replace(/\/+$/, "").split("/");
  const last = parts[parts.length - 1];
  if (last && last !== "post.html" && last !== "blog") return last;
  return null;
}

function formatPostBody(text) {
  return escapeHtml(text)
    .split(/\n{2,}/)
    .map((para) => `<p>${para.replace(/\n/g, "<br>")}</p>`)
    .join("");
}

function setMeta(name, content, attr = "name") {
  if (!content) return;
  let el = document.querySelector(`meta[${attr}="${name}"]`);
  if (!el) {
    el = document.createElement("meta");
    el.setAttribute(attr, name);
    document.head.appendChild(el);
  }
  el.setAttribute("content", content);
}

function setCanonical(href) {
  if (!href) return;
  let el = document.querySelector('link[rel="canonical"]');
  if (!el) {
    el = document.createElement("link");
    el.rel = "canonical";
    document.head.appendChild(el);
  }
  el.href = href;
}

function applyPostSeo(post, slug, lang, imageUrl, domain) {
  const keywords = Array.isArray(post.keywords) ? post.keywords : [];
  const summary = post.summary || post.title || "";
  const url = domain ? `${domain}${postUrl(post.slug || slug)}` : "";

  setMeta("description", summary);
  if (keywords.length) setMeta("keywords", keywords.join(", "));
  if (url) setCanonical(url);

  setMeta("og:title", post.title || "", "property");
  setMeta("og:description", summary, "property");
  setMeta("og:type", "article", "property");
  if (url) setMeta("og:url", url, "property");
  if (imageUrl) setMeta("og:image", imageUrl, "property");
  setMeta("twitter:card", "summary_large_image");
  if (imageUrl) setMeta("twitter:image", imageUrl);
}

function injectPostJsonLd(post, domain, lang) {
  const script = document.createElement("script");
  script.type = "application/ld+json";
  script.textContent = JSON.stringify({
    "@context": "https://schema.org",
    "@type": "BlogPosting",
    headline: post.title,
    description: post.summary,
    datePublished: post.publishedAt,
    inLanguage: lang === "uk" ? "uk-UA" : "en-US",
    url: domain ? `${domain}${postUrl(post.slug)}` : undefined,
    keywords: Array.isArray(post.keywords) ? post.keywords.join(", ") : undefined,
    author: { "@type": "Person", name: "Oleksandr Kalinovskyi" },
  });
  document.head.appendChild(script);
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/* ---------------- Impact charts ---------------- */
function renderImpactCharts() {
  const grid = document.getElementById("impact-grid");
  if (!grid || !Array.isArray(window.IMPACT_DATA)) return;

  grid.innerHTML = window.IMPACT_DATA.map((item, i) => {
    const beforeY = 100 - item.beforeH;
    const afterY = 100 - item.afterH;
    const pctLabel = item.afterPct != null
      ? `<text class="bar-value" x="145" y="${afterY - 8}" text-anchor="middle">~${item.afterPct}%</text>`
      : "";
    return `
      <div class="impact-card reveal stagger-item" style="--stagger:${i * 0.1}s">
        <span class="tag">${item.tag}</span>
        <h4>${item.title}</h4>
        <svg class="impact-chart" viewBox="0 0 200 110" role="img" aria-label="${item.ariaLabel}">
          <rect class="bar-before" x="30" y="${beforeY}" width="50" height="${item.beforeH}" rx="4"></rect>
          <rect class="bar-after" x="120" y="${afterY}" width="50" height="${item.afterH}" rx="4"></rect>
          ${pctLabel}
          <text class="bar-label" x="55" y="108" text-anchor="middle">${item.beforeLabel}</text>
          <text class="bar-label" x="145" y="108" text-anchor="middle">${item.afterLabel}</text>
        </svg>
        <p>${item.caption}</p>
      </div>`;
  }).join("");
}

/* ---------------- Scroll progress bar ---------------- */
function initScrollProgress() {
  const bar = document.createElement("div");
  bar.className = "scroll-progress";
  bar.setAttribute("aria-hidden", "true");
  document.body.appendChild(bar);
  window.addEventListener("scroll", () => {
    const max = document.documentElement.scrollHeight - window.innerHeight;
    const pct = max > 0 ? (window.scrollY / max) * 100 : 0;
    bar.style.width = `${pct}%`;
  }, { passive: true });
}

/* ---------------- Header shrink on scroll ---------------- */
function initHeaderScroll() {
  const header = document.querySelector(".site-header");
  if (!header) return;
  const onScroll = () => header.classList.toggle("is-scrolled", window.scrollY > 40);
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();
}

/* ---------------- Stagger reveal delays ---------------- */
function initStaggerReveal() {
  document.querySelectorAll(".stagger-item").forEach((el) => {
    el.style.transitionDelay = el.style.getPropertyValue("--stagger") || "0s";
  });
}

/* ---------------- Counter animation for stat numbers ---------------- */
function initCounterAnimation() {
  const counters = document.querySelectorAll("[data-count-to]");
  if (!counters.length || !("IntersectionObserver" in window)) return;

  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      const el = entry.target;
      const target = parseInt(el.dataset.countTo, 10);
      const suffix = el.dataset.countSuffix || "";
      const duration = 1200;
      const start = performance.now();
      const tick = (now) => {
        const t = Math.min((now - start) / duration, 1);
        const eased = 1 - Math.pow(1 - t, 3);
        el.textContent = Math.round(target * eased) + suffix;
        if (t < 1) requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
      observer.unobserve(el);
    });
  }, { threshold: 0.5 });

  counters.forEach((el) => observer.observe(el));
}

/* ---------------- Subtle card tilt ---------------- */
function initCardTilt() {
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  if (!window.matchMedia("(hover: hover)").matches) return;

  document.querySelectorAll(".project-card, .service-card, .skill-card").forEach((card) => {
    card.addEventListener("mousemove", (e) => {
      const rect = card.getBoundingClientRect();
      const x = (e.clientX - rect.left) / rect.width - 0.5;
      const y = (e.clientY - rect.top) / rect.height - 0.5;
      card.style.transform = `perspective(600px) rotateY(${x * 6}deg) rotateX(${-y * 6}deg) translateY(-4px)`;
    });
    card.addEventListener("mouseleave", () => {
      card.style.transform = "";
    });
  });
}

/* ---------------- Scroll reveal ---------------- */
function initRevealAnimations() {
  const items = document.querySelectorAll(".reveal");
  if (!items.length) return;

  if (!("IntersectionObserver" in window)) {
    items.forEach((el) => el.classList.add("is-visible"));
    return;
  }

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.1, rootMargin: "0px 0px -30px 0px" }
  );

  items.forEach((el) => observer.observe(el));
}

/* ---------------- Mobile nav ---------------- */
function initMobileNav() {
  const toggle = document.querySelector(".nav-toggle");
  const nav = document.querySelector(".primary-nav");
  if (!toggle || !nav) return;

  toggle.addEventListener("click", () => {
    const isOpen = nav.classList.contains("is-open");
    nav.classList.toggle("is-open", !isOpen);
    toggle.setAttribute("aria-expanded", String(!isOpen));
  });

  nav.querySelectorAll("a").forEach((link) => {
    link.addEventListener("click", () => {
      nav.classList.remove("is-open");
      toggle.setAttribute("aria-expanded", "false");
    });
  });
}

/* ---------------- Contact form ---------------- */
let lastSubmitTime = 0;

function initContactForm() {
  const form = document.getElementById("contact-form");
  if (!form) return;

  const statusEl = form.querySelector(".form-status");
  const submitBtn = form.querySelector('button[type="submit"]');

  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    const honeypot = form.querySelector(".hp-field");
    if (honeypot && honeypot.value.trim() !== "") return;

    const now = Date.now();
    if (now - lastSubmitTime < 20000) {
      setStatus(statusEl, statusEl.dataset.throttle, "err");
      return;
    }

    const name = form.querySelector("#cf-name").value.trim();
    const contact = form.querySelector("#cf-contact").value.trim();
    const projectType = form.querySelector("#cf-type").value;
    const message = form.querySelector("#cf-message").value.trim();

    if (!name || !contact || !message) {
      setStatus(statusEl, statusEl.dataset.required, "err");
      return;
    }

    if (!workerReady()) {
      setStatus(statusEl, statusEl.dataset.notConfigured, "err");
      return;
    }

    submitBtn.disabled = true;
    setStatus(statusEl, statusEl.dataset.sending, "");

    try {
      const res = await fetch(CONTACT_FORM_CONFIG.workerUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, contact, type: projectType, message, website: honeypot ? honeypot.value : "" }),
      });

      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data.ok) throw new Error("Worker error");

      lastSubmitTime = now;
      form.reset();
      setStatus(statusEl, statusEl.dataset.success, "ok");
    } catch {
      setStatus(statusEl, statusEl.dataset.error, "err");
    } finally {
      submitBtn.disabled = false;
    }
  });
}

function setStatus(el, text, cls) {
  if (!el) return;
  el.textContent = text || "";
  el.className = "form-status" + (cls ? " " + cls : "");
}
