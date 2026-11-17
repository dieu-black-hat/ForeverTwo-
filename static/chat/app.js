/*
 * ForeverTwo chat – browser side (messages, media, voice notes).
 * Calls live in call.js.
 *
 * How live chat works here (in plain words):
 *  1. When a room opens, the page already contains the last messages (as JSON).
 *  2. Every 2 seconds we ask the server: "anything new since message X?"
 *     (GET /api/rooms/<slug>/messages/?after=X). This is called POLLING.
 *     The answer also says who is typing, which messages were deleted and
 *     what the other person has seen.
 *  3. Text goes to /api/rooms/<slug>/send/; photos, videos, files and voice
 *     notes go to /api/rooms/<slug>/upload/.
 *  4. Every 5 seconds we refresh the sidebar (unread badges, who is online).
 */
(function () {
  "use strict";

  // ================================================================ utils ==
  function getCookie(name) {
    const match = document.cookie.match(new RegExp("(^|;\\s*)" + name + "=([^;]*)"));
    return match ? decodeURIComponent(match[2]) : null;
  }
  window.getCookie = getCookie;

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text; // textContent = safe, no HTML injection
    return node;
  }

  const SVG = {
    play: '<path fill="currentColor" stroke="none" d="M7 4v16l13-8z"/>',
    pause: '<path fill="currentColor" stroke="none" d="M6 4h4v16H6zM14 4h4v16h-4z"/>',
    download: '<path d="M12 3v12M7 10l5 5 5-5M5 21h14"/>',
    trash: '<path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6M10 11v6M14 11v6"/>',
    x: '<path d="M18 6 6 18M6 6l12 12"/>',
    phone: '<path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1.9.4 1.8.7 2.7a2 2 0 0 1-.5 2.1L8 9.8a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.4c.9.3 1.8.6 2.7.7a2 2 0 0 1 1.7 2z"/>',
    video: '<rect x="2" y="6" width="14" height="12" rx="2"/><path d="m22 8-6 4 6 4z"/>',
    ban: '<circle cx="12" cy="12" r="9"/><path d="m5.7 5.7 12.6 12.6"/>',
    reply: '<path d="M9 14 4 9l5-5"/><path d="M4 9h11a5 5 0 0 1 5 5v6"/>',
    volume: '<path d="M11 5 6 9H2v6h4l5 4z"/><path d="M15.5 8.5a5 5 0 0 1 0 7M19 5a10 10 0 0 1 0 14"/>',
    volumeOff: '<path d="M11 5 6 9H2v6h4l5 4z"/><path d="m22 9-6 6M16 9l6 6"/>',
  };
  function icon(name, size) {
    const span = document.createElement("span");
    span.className = "i-wrap";
    span.innerHTML =
      '<svg class="i" viewBox="0 0 24 24" width="' + (size || 18) + '" height="' + (size || 18) +
      '" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
      SVG[name] + "</svg>";
    return span.firstChild;
  }

  function initials(name) { return (name || "?").slice(0, 2).toUpperCase(); }

  function formatBytes(bytes) {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(0) + " KB";
    return (bytes / 1024 / 1024).toFixed(1) + " MB";
  }
  function formatDuration(sec) {
    sec = Math.max(0, Math.round(sec || 0));
    return Math.floor(sec / 60) + ":" + String(sec % 60).padStart(2, "0");
  }

  const URL_RE = /(https?:\/\/[^\s<>"']+)/g;
  function renderText(container, text) {
    text.split(URL_RE).forEach(function (part, i) {
      if (i % 2 === 1) {
        const a = el("a", null, part);
        a.href = part;
        a.target = "_blank";
        a.rel = "noopener noreferrer";
        container.appendChild(a);
      } else if (part) {
        container.appendChild(document.createTextNode(part));
      }
    });
  }

  function dayLabel(date) {
    const today = new Date();
    const yesterday = new Date();
    yesterday.setDate(today.getDate() - 1);
    if (date.toDateString() === today.toDateString()) return "Today";
    if (date.toDateString() === yesterday.toDateString()) return "Yesterday";
    return date.toLocaleDateString([], { weekday: "long", day: "numeric", month: "long", year: "numeric" });
  }
  function timeLabel(date) { return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }); }

  function toast(text, kind) {
    let box = document.getElementById("toasts");
    if (!box) {
      box = el("div", "toasts");
      box.id = "toasts";
      document.body.appendChild(box);
    }
    const t = el("div", "toast toast-" + (kind || "info"), text);
    box.appendChild(t);
    setTimeout(function () { t.remove(); }, 4500);
  }
  window.chatToast = toast;

  document.querySelectorAll(".toast").forEach(function (t) { setTimeout(function () { t.remove(); }, 4500); });

  // "Copy" buttons (e.g. login details on the Manage users page)
  document.querySelectorAll("[data-copy]").forEach(function (btn) {
    btn.addEventListener("click", async function () {
      const text = document.getElementById(btn.dataset.copy).innerText;
      try {
        await navigator.clipboard.writeText(text);
      } catch (e) {
        const area = el("textarea");
        area.value = text;
        document.body.appendChild(area);
        area.select();
        document.execCommand("copy");
        area.remove();
      }
      toast("Copied! Paste it in WhatsApp, SMS or email.", "success");
    });
  });

  // ================================================ desktop notifications ==
  // Pop-ups on your Windows/Mac/phone screen when a message arrives (like WhatsApp Web).
  // The browser asks you once for permission. The ForeverTwo tab must stay open
  // (it can be minimised or in the background).
  const notifySupported = "Notification" in window && window.isSecureContext;
  const iconUrl = document.body.dataset.icon;
  const notifyBtn = document.getElementById("notify-btn");
  const notifyBanner = document.getElementById("notify-banner");

  function notifyState() { return notifySupported ? Notification.permission : "unsupported"; }
  function bannerDismissed() {
    try { return localStorage.getItem("ft-notify-dismissed") === "1"; } catch (e) { return false; }
  }
  function updateNotifyUI() {
    const st = notifyState();
    if (notifyBanner) notifyBanner.hidden = !(st === "default" && !bannerDismissed());
    if (notifyBtn) {
      notifyBtn.hidden = st === "unsupported";
      notifyBtn.classList.toggle("on", st === "granted");
      notifyBtn.title = st === "granted" ? "Desktop notifications are ON (click to test)"
        : st === "denied" ? "Notifications are blocked – allow them via the 🔒 icon next to the address"
        : "Turn on desktop notifications";
    }
  }
  function notify(title, body, url, tag) {
    if (notifyState() !== "granted") return null;
    try {
      const n = new Notification(title, { body: body, icon: iconUrl, tag: tag || undefined, renotify: !!tag });
      n.onclick = function () {
        window.focus();
        if (url && url !== window.location.pathname) window.location.href = url;
        n.close();
      };
      setTimeout(function () { n.close(); }, 10000);
      return n;
    } catch (e) { return null; } // some phones only allow notifications from installed apps
  }
  window.chatNotify = notify;

  async function askPermission() {
    if (!notifySupported) { toast("Notifications need https (or localhost) and a modern browser.", "error"); return; }
    if (Notification.permission === "denied") {
      toast("Notifications are blocked. Click the 🔒 icon next to the address → Notifications → Allow, then reload.", "error");
      return;
    }
    if (Notification.permission !== "granted") await Notification.requestPermission();
    updateNotifyUI();
    if (Notification.permission === "granted") notify("Notifications are on ✅", "You'll get a pop-up like this when a message arrives.", null, "test");
  }
  if (notifyBtn) notifyBtn.addEventListener("click", askPermission);
  const enableBtn = document.getElementById("notify-enable");
  if (enableBtn) enableBtn.addEventListener("click", askPermission);
  const dismissBtn = document.getElementById("notify-dismiss");
  if (dismissBtn) dismissBtn.addEventListener("click", function () {
    try { localStorage.setItem("ft-notify-dismissed", "1"); } catch (e) { /* ignore */ }
    updateNotifyUI();
  });
  updateNotifyUI();

  // ======================================================= message sound ==
  // A short "pop" made in code (no sound file needed). Each person can mute it
  // with the 🔊 button at the top of the sidebar; the choice is remembered.
  const soundBtn = document.getElementById("sound-btn");
  let soundCtx = null;
  let lastDing = 0;

  function soundOn() {
    try { return localStorage.getItem("ft-sound") !== "off"; } catch (e) { return true; }
  }
  function updateSoundBtn() {
    if (!soundBtn) return;
    const on = soundOn();
    soundBtn.replaceChildren(icon(on ? "volume" : "volumeOff", 19));
    soundBtn.title = on ? "Message sound is ON (click to mute)" : "Message sound is OFF (click to turn on)";
    soundBtn.classList.toggle("muted", !on);
  }
  function getSoundCtx() {
    soundCtx = soundCtx || new (window.AudioContext || window.webkitAudioContext)();
    if (soundCtx.state === "suspended") soundCtx.resume();
    return soundCtx;
  }
  function ding(force) {
    if (!force && !soundOn()) return;
    const nowMs = Date.now();
    if (!force && nowMs - lastDing < 1200) return; // don't stack sounds when several messages arrive
    lastDing = nowMs;
    try {
      const ctx = getSoundCtx();
      const now = ctx.currentTime;
      [[660, 0], [990, 0.12]].forEach(function (note) {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = "sine";
        osc.frequency.setValueAtTime(note[0], now + note[1]);
        gain.gain.setValueAtTime(0.0001, now + note[1]);
        gain.gain.exponentialRampToValueAtTime(0.3, now + note[1] + 0.015); // volume (0.0 – 1.0)
        gain.gain.exponentialRampToValueAtTime(0.0001, now + note[1] + 0.22);
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start(now + note[1]);
        osc.stop(now + note[1] + 0.25);
      });
    } catch (e) { /* sound not available */ }
  }
  window.chatDing = ding;

  // Browsers only allow sound after you've touched the page once, so we
  // switch the sound system on at your first click, tap or key press.
  function unlockSound() {
    try { getSoundCtx(); } catch (e) { /* ignore */ }
    ["pointerdown", "keydown", "touchstart"].forEach(function (ev) { document.removeEventListener(ev, unlockSound); });
  }
  ["pointerdown", "keydown", "touchstart"].forEach(function (ev) { document.addEventListener(ev, unlockSound); });

  if (soundBtn) {
    soundBtn.addEventListener("click", function () {
      try { localStorage.setItem("ft-sound", soundOn() ? "off" : "on"); } catch (e) { /* ignore */ }
      updateSoundBtn();
      if (soundOn()) ding(true); // play a sample so you know it works
    });
  }
  updateSoundBtn();

  // ======================================================= mobile sidebar ==
  document.querySelectorAll("[data-open-sidebar]").forEach(function (b) {
    b.addEventListener("click", function () { document.body.classList.add("sidebar-open"); });
  });
  document.querySelectorAll("[data-close-sidebar]").forEach(function (b) {
    b.addEventListener("click", function () { document.body.classList.remove("sidebar-open"); });
  });

  const filterInput = document.getElementById("sidebar-filter");
  if (filterInput) {
    filterInput.addEventListener("input", function () {
      const q = filterInput.value.trim().toLowerCase();
      document.querySelectorAll(".sidebar [data-filter]").forEach(function (item) {
        item.parentElement.hidden = q && item.dataset.filter.indexOf(q) === -1;
      });
    });
  }

  // ====================================================== sidebar polling ==
  const sidebarUrl = document.body.dataset.sidebarUrl;
  const configNode = document.getElementById("chat-config");
  const chat = configNode ? JSON.parse(configNode.textContent) : null;
  let unreadTotal = 0;
  let notifyCursor = null; // newest message id we already know about
  const baseTitle = document.title;

  function updateTitle() {
    document.title = unreadTotal > 0 ? "(" + unreadTotal + ") " + baseTitle : baseTitle;
  }

  function addDmToSidebar(room) {
    const list = document.getElementById("dm-list");
    if (!list) return;
    const empty = document.getElementById("dm-empty");
    if (empty) empty.remove();
    const li = el("li");
    const a = el("a", "nav-item");
    a.href = room.url;
    a.dataset.slug = room.slug;
    a.dataset.filter = room.name.toLowerCase();
    const av = el("span", "avatar xs", initials(room.name));
    av.style.background = room.color || "#64748b";
    a.appendChild(av);
    a.appendChild(el("span", "nav-name", room.name));
    const badge = el("span", "badge");
    badge.hidden = true;
    a.appendChild(badge);
    li.appendChild(a);
    list.prepend(li);
  }

  async function refreshSidebar() {
    if (!sidebarUrl) return;
    try {
      const url = notifyCursor === null ? sidebarUrl : sidebarUrl + "?since=" + notifyCursor;
      const res = await fetch(url, { headers: { "X-Requested-With": "XMLHttpRequest" } });
      if (res.redirected) { window.location.reload(); return; }
      if (!res.ok) return;
      const data = await res.json();
      unreadTotal = 0;
      data.rooms.forEach(function (room) {
        let link = document.querySelector('.sidebar .nav-item[data-slug="' + room.slug + '"]');
        if (!link && room.kind === "direct") {
          addDmToSidebar(room);
          link = document.querySelector('.sidebar .nav-item[data-slug="' + room.slug + '"]');
        }
        if (!link) return;
        const count = chat && chat.slug === room.slug ? 0 : room.unread;
        const badge = link.querySelector(".badge");
        if (badge) {
          badge.hidden = count === 0;
          badge.textContent = count > 99 ? "99+" : String(count);
        }
        link.classList.toggle("has-unread", count > 0);
        unreadTotal += count;
      });
      const online = new Set(data.online);
      document.querySelectorAll("#people-list [data-user]").forEach(function (a) {
        const dot = a.querySelector(".dot");
        if (dot) dot.classList.toggle("online", online.has(a.dataset.user));
      });
      document.querySelectorAll("[data-presence]").forEach(function (dot) {
        dot.classList.toggle("online", online.has(dot.dataset.presence));
      });
      document.querySelectorAll("[data-presence-text]").forEach(function (t) {
        if (!t.dataset.typing) t.textContent = online.has(t.dataset.presenceText) ? "Online" : "Offline";
      });
      updateTitle();

      // Pop-up + sound for new messages (except in the chat you're looking at right now).
      let alerted = false;
      if (notifyCursor !== null) {
        data.latest.forEach(function (m) {
          const viewing = chat && chat.slug === m.room && !document.hidden && document.hasFocus();
          if (viewing) return;
          const title = m.is_direct ? m.sender : m.sender + " in #" + m.room_name;
          notify(title, m.preview, m.url, "room-" + m.room);
          alerted = true;
        });
      }
      if (alerted) ding();
      notifyCursor = data.cursor;
    } catch (e) { /* network hiccup – try again next time */ }
  }

  if (sidebarUrl) {
    refreshSidebar();
    setInterval(refreshSidebar, 4000); // keeps running in the background so pop-ups arrive
  }

  if (!chat) return; // the rest is only for chat-room pages

  // =========================================================== chat room ==
  const list = document.getElementById("messages");
  const emptyState = document.getElementById("empty-state");
  const form = document.getElementById("composer");
  const input = document.getElementById("composer-input");
  const sendBtn = document.getElementById("send-btn");
  const pill = document.getElementById("new-pill");
  const typingBox = document.getElementById("typing");
  const typingText = document.getElementById("typing-text");
  const csrf = function () { return getCookie("csrftoken"); };

  const rows = new Map(); // message id → row element
  const messagesById = new Map(); // message id → message data (used for replies)
  let lastId = 0;
  let lastMsg = null;
  let lastDay = null;
  let hiddenNew = 0;
  let pinned = true; // is the view stuck to the newest message?
  let seenId = chat.seenId || 0;
  let lastMineId = 0;
  const seenLabel = el("div", "seen-label");

  function nearBottom() { return list.scrollHeight - list.scrollTop - list.clientHeight < 150; }
  function scrollToBottom(smooth) {
    list.scrollTo({ top: list.scrollHeight, behavior: smooth ? "smooth" : "auto" });
    pill.hidden = true;
    pinned = true;
  }
  list.addEventListener("scroll", function () {
    pinned = nearBottom();
    if (pinned) pill.hidden = true;
  });
  pill.addEventListener("click", function () { scrollToBottom(true); });

  function keepPinned() { if (pinned) scrollToBottom(false); }

  // ---------------------------------------------------- message rendering --
  let currentAudio = null;

  function buildVoicePlayer(m) {
    const player = el("div", "voice-player");
    const btn = el("button", "voice-play");
    btn.type = "button";
    btn.setAttribute("aria-label", "Play voice note");
    btn.appendChild(icon("play", 16));
    const track = el("div", "voice-track");
    const fill = el("div", "voice-fill");
    track.appendChild(fill);
    const time = el("span", "voice-time", formatDuration(m.duration));
    player.append(btn, track, time);

    let audio = null;
    let loading = false;
    const total = function () { return audio && isFinite(audio.duration) && audio.duration > 0 ? audio.duration : (m.duration || 1); };
    function setIcon(name) { btn.replaceChildren(icon(name, 16)); }

    async function ensureAudio() {
      if (audio || loading) return audio;
      loading = true;
      player.classList.add("loading");
      try {
        // Download the whole note first so it can be played and scrubbed smoothly.
        const res = await fetch(m.file_url);
        const blob = await res.blob();
        audio = new Audio(URL.createObjectURL(blob));
        audio.addEventListener("timeupdate", function () {
          fill.style.width = Math.min(100, (audio.currentTime / total()) * 100) + "%";
          time.textContent = formatDuration(audio.currentTime);
        });
        audio.addEventListener("ended", function () {
          setIcon("play");
          fill.style.width = "0%";
          time.textContent = formatDuration(m.duration);
        });
        audio.addEventListener("pause", function () { setIcon("play"); });
        audio.addEventListener("play", function () { setIcon("pause"); });
      } catch (e) {
        toast("Could not load the voice note.", "error");
      }
      loading = false;
      player.classList.remove("loading");
      return audio;
    }

    btn.addEventListener("click", async function () {
      const a = await ensureAudio();
      if (!a) return;
      if (a.paused) {
        if (currentAudio && currentAudio !== a) currentAudio.pause();
        currentAudio = a;
        a.play().catch(function () {});
      } else {
        a.pause();
      }
    });
    track.addEventListener("click", async function (e) {
      const a = await ensureAudio();
      if (!a) return;
      const rect = track.getBoundingClientRect();
      a.currentTime = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width)) * total();
    });
    return player;
  }

  function fileExt(name) {
    const m = /\.([a-z0-9]{1,5})$/i.exec(name || "");
    return m ? m[1].toUpperCase() : "FILE";
  }

  function buildBubble(m) {
    const bubble = el("div", "bubble");
    bubble.title = new Date(m.created_at).toLocaleString();

    if (m.kind === "deleted") {
      bubble.classList.add("deleted");
      bubble.append(icon("ban", 15), document.createTextNode(m.is_mine ? " You deleted this message" : " This message was deleted"));
      return bubble;
    }
    if (m.kind === "image") {
      bubble.classList.add("media-bubble");
      const img = document.createElement("img");
      img.className = "media-img";
      img.src = m.file_url;
      img.alt = m.file_name || "Photo";
      img.addEventListener("load", function () { img.classList.add("loaded"); keepPinned(); });
      img.addEventListener("click", function () { openLightbox(m); });
      bubble.appendChild(img);
    } else if (m.kind === "video") {
      bubble.classList.add("media-bubble");
      const video = document.createElement("video");
      video.className = "media-video";
      video.src = m.file_url;
      video.controls = true;
      video.preload = "metadata";
      video.playsInline = true;
      video.addEventListener("loadedmetadata", keepPinned);
      bubble.appendChild(video);
    } else if (m.kind === "file") {
      bubble.classList.add("file-bubble");
      const card = el("a", "file-card");
      card.href = m.file_url + "?download=1";
      card.setAttribute("download", m.file_name || "");
      card.appendChild(el("span", "file-icon", fileExt(m.file_name)));
      const info = el("span", "file-info");
      info.append(el("strong", null, m.file_name || "File"), el("small", null, formatBytes(m.file_size || 0)));
      card.append(info, icon("download", 18));
      bubble.appendChild(card);
    } else if (m.kind === "voice") {
      bubble.classList.add("voice-bubble");
      bubble.appendChild(buildVoicePlayer(m));
    }
    if (m.content && m.kind !== "voice") {
      const text = el("div", m.kind === "text" ? "text" : "caption");
      renderText(text, m.content);
      bubble.appendChild(text);
    }
    return bubble;
  }

  // Small buttons next to a message: Reply (everyone) and Delete (your own).
  function addActions(row, m) {
    if (m.kind === "deleted" || m.kind === "call") return;
    const box = el("div", "msg-actions");
    const reply = el("button", "msg-action");
    reply.type = "button";
    reply.title = "Reply";
    reply.setAttribute("aria-label", "Reply to this message");
    reply.appendChild(icon("reply", 15));
    reply.addEventListener("click", function () { startReply(m); });
    box.appendChild(reply);
    if (m.is_mine) {
      const del = el("button", "msg-action danger");
      del.type = "button";
      del.title = "Delete for everyone";
      del.setAttribute("aria-label", "Delete message");
      del.appendChild(icon("trash", 15));
      del.addEventListener("click", function () { deleteMessage(m.id); });
      box.appendChild(del);
    }
    row.querySelector(".msg-body").appendChild(box);
  }

  // The little quoted box at the top of a reply. Click it to jump to the original.
  function buildQuote(reply) {
    const q = el("button", "reply-quote");
    q.type = "button";
    q.style.borderLeftColor = reply.color || "var(--accent)";
    const who = el("strong", null, reply.user === chat.me ? "You" : reply.user);
    who.style.color = reply.color || "inherit";
    q.append(who, el("span", null, reply.text));
    q.addEventListener("click", function () { jumpTo(reply.id); });
    return q;
  }

  function jumpTo(id) {
    const row = rows.get(id);
    if (!row) { toast("That message is too old to show here.", "info"); return; }
    row.scrollIntoView({ behavior: "smooth", block: "center" });
    row.classList.remove("flash");
    void row.offsetWidth; // restart the animation
    row.classList.add("flash");
  }

  function addMessage(m) {
    if (rows.has(m.id)) return false;
    emptyState.hidden = true;

    const date = new Date(m.created_at);
    const day = date.toDateString();
    if (day !== lastDay) {
      const sep = el("div", "day-sep");
      sep.appendChild(el("span", null, dayLabel(date)));
      list.appendChild(sep);
      lastDay = day;
      lastMsg = null;
    }

    if (m.kind === "call") {
      const row = el("div", "call-log" + (/^Missed|declined|No answer/i.test(m.content) ? " missed" : ""));
      row.dataset.id = m.id;
      row.append(icon(/video/i.test(m.content) ? "video" : "phone", 15), el("span", null, m.content), el("time", null, timeLabel(date)));
      list.appendChild(row);
      rows.set(m.id, row);
      lastMsg = null;
      lastId = Math.max(lastId, m.id);
      return true;
    }

    const grouped = lastMsg && lastMsg.user === m.user && date - lastMsg.date < 5 * 60 * 1000;
    const row = el("div", "msg" + (m.is_mine ? " mine" : "") + (grouped ? " grouped" : ""));
    row.dataset.id = m.id;

    const avatar = el("div", "avatar sm", grouped ? "" : initials(m.user));
    if (!grouped) avatar.style.background = m.color;
    else avatar.classList.add("spacer");
    row.appendChild(avatar);

    const body = el("div", "msg-body");
    if (!grouped) {
      const meta = el("div", "msg-meta");
      meta.appendChild(el("strong", null, m.is_mine ? "You" : m.user));
      meta.appendChild(el("time", null, timeLabel(date)));
      body.appendChild(meta);
    }
    const bubble = buildBubble(m);
    if (m.reply && m.kind !== "deleted") bubble.prepend(buildQuote(m.reply));
    body.appendChild(bubble);
    row.appendChild(body);
    addActions(row, m);
    messagesById.set(m.id, m);

    list.appendChild(row);
    rows.set(m.id, row);
    lastMsg = { user: m.user, date: date };
    lastId = Math.max(lastId, m.id);
    if (m.is_mine) lastMineId = Math.max(lastMineId, m.id);
    return true;
  }

  function markDeleted(id) {
    const row = rows.get(id);
    if (!row || row.classList.contains("is-deleted")) return;
    row.classList.add("is-deleted");
    const old = row.querySelector(".bubble");
    if (old) old.replaceWith(buildBubble({ kind: "deleted", is_mine: row.classList.contains("mine"), created_at: new Date().toISOString() }));
    const actions = row.querySelector(".msg-actions");
    if (actions) actions.remove();
    if (replyTo && replyTo.id === id) cancelReply();
  }

  function updateSeen() {
    if (!chat.isDirect || !lastMineId) { seenLabel.remove(); return; }
    const row = rows.get(lastMineId);
    if (!row) return;
    seenLabel.textContent = seenId >= lastMineId ? "Seen ✓✓" : "Sent ✓";
    seenLabel.classList.toggle("is-seen", seenId >= lastMineId);
    row.after(seenLabel);
  }

  // Show the messages that came with the page.
  const initial = JSON.parse(document.getElementById("initial-messages").textContent);
  initial.forEach(addMessage);
  if (initial.length === 0) emptyState.hidden = false;
  updateSeen();
  scrollToBottom(false);

  // ------------------------------------------------------------- typing --
  function showTyping(names) {
    const presence = document.querySelector("[data-presence-text]");
    if (!names.length) {
      typingBox.hidden = true;
      if (presence && presence.dataset.typing) { delete presence.dataset.typing; presence.textContent = "Online"; }
      return;
    }
    let text;
    if (names.length === 1) text = names[0] + " is typing…";
    else if (names.length === 2) text = names[0] + " and " + names[1] + " are typing…";
    else text = "Several people are typing…";
    typingText.textContent = text;
    typingBox.hidden = false;
    if (presence) { presence.dataset.typing = "1"; presence.textContent = "typing…"; }
  }

  let lastTypingSent = 0;
  input.addEventListener("input", function () {
    const now = Date.now();
    if (input.value.trim() && now - lastTypingSent > 2500) {
      lastTypingSent = now;
      fetch(chat.typingUrl, { method: "POST", headers: { "X-CSRFToken": csrf() } }).catch(function () {});
    }
  });

  // ------------------------------------------------------------ polling --
  let polling = false;
  async function poll() {
    if (polling) return;
    polling = true;
    try {
      const res = await fetch(chat.messagesUrl + "?after=" + lastId, { headers: { "X-Requested-With": "XMLHttpRequest" } });
      if (res.redirected || res.status === 404) { window.location.href = "/"; return; }
      if (res.ok) {
        const data = await res.json();
        const stick = nearBottom();
        let added = 0;
        data.messages.forEach(function (m) { if (addMessage(m) && !m.is_mine) added++; });
        data.deleted.forEach(markDeleted);
        showTyping(data.typing);
        seenId = data.seen_id || seenId;
        updateSeen();
        if (added) {
          ding(); // sound for messages from the other person in this chat
          if (stick) scrollToBottom(true);
          else pill.hidden = false;
          if (document.hidden) { hiddenNew += added; unreadTotal += added; updateTitle(); }
        }
      }
    } catch (e) { /* offline for a moment – keep trying */ }
    polling = false;
    setTimeout(poll, document.hidden ? 6000 : 2000);
  }
  setTimeout(poll, 2000);

  document.addEventListener("visibilitychange", function () {
    if (!document.hidden && hiddenNew) {
      unreadTotal = Math.max(0, unreadTotal - hiddenNew);
      hiddenNew = 0;
      updateTitle();
    }
  });

  function messageArrived(message) {
    addMessage(message);
    updateSeen();
    scrollToBottom(true);
  }
  window.chatMessageArrived = messageArrived; // used by call.js for call records

  // -------------------------------------------------------------- replies --
  const replyBar = document.getElementById("reply-bar");
  const replyName = document.getElementById("reply-name");
  const replyText = document.getElementById("reply-text");
  let replyTo = null; // the message you are answering

  function previewOf(m) {
    const labels = { image: "📷 Photo", video: "🎬 Video", voice: "🎤 Voice note", file: "📄 " + (m.file_name || "File") };
    if (labels[m.kind]) return m.content ? labels[m.kind] + ": " + m.content : labels[m.kind];
    return m.content;
  }

  function startReply(m) {
    replyTo = { id: m.id, user: m.user };
    replyName.textContent = m.is_mine ? "yourself" : m.user;
    replyText.textContent = previewOf(m);
    replyBar.hidden = false;
    list.querySelectorAll(".msg.show-actions").forEach(function (r) { r.classList.remove("show-actions"); });
    input.focus();
  }
  function cancelReply() {
    replyTo = null;
    replyBar.hidden = true;
  }
  document.getElementById("reply-cancel").addEventListener("click", cancelReply);

  // Double-click a message to reply quickly.
  list.addEventListener("dblclick", function (e) {
    const row = e.target.closest(".msg");
    if (!row || row.classList.contains("pending") || e.target.closest("a, video, .voice-player, .msg-actions")) return;
    const m = messagesById.get(Number(row.dataset.id));
    if (m && !row.classList.contains("is-deleted")) startReply(m);
  });

  // ---------------------------------------------------------- send text --
  function autoresize() {
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 180) + "px";
  }
  input.addEventListener("input", autoresize);
  input.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
      e.preventDefault();
      form.requestSubmit();
    }
  });

  form.addEventListener("submit", async function (e) {
    e.preventDefault();
    const content = input.value.trim();
    if (!content || sendBtn.disabled) return;
    sendBtn.disabled = true;
    try {
      const body = new FormData();
      body.append("content", content);
      if (replyTo) body.append("reply_to", String(replyTo.id));
      const res = await fetch(chat.sendUrl, { method: "POST", body: body, headers: { "X-CSRFToken": csrf() } });
      const data = await res.json().catch(function () { return {}; });
      if (res.ok) {
        messageArrived(data.message);
        input.value = "";
        autoresize();
        cancelReply();
      } else {
        toast(data.error || "Could not send the message. Please try again.", "error");
      }
    } catch (err) {
      toast("You seem to be offline. Message not sent.", "error");
    } finally {
      sendBtn.disabled = false;
      input.focus();
    }
  });

  // ------------------------------------------------------------- delete --
  async function deleteMessage(id) {
    if (!confirm("Delete this message for everyone?")) return;
    try {
      const res = await fetch(chat.deleteUrl.replace("/0/", "/" + id + "/"), { method: "POST", headers: { "X-CSRFToken": csrf() } });
      if (res.ok) markDeleted(id);
      else toast("Could not delete the message.", "error");
    } catch (e) {
      toast("You seem to be offline.", "error");
    }
  }

  // Touch screens: tap a message to show its delete button.
  list.addEventListener("click", function (e) {
    const row = e.target.closest(".msg");
    list.querySelectorAll(".msg.show-actions").forEach(function (r) { if (r !== row) r.classList.remove("show-actions"); });
    if (row && !row.classList.contains("pending") && !e.target.closest("a, button, video, img")) {
      row.classList.toggle("show-actions");
    }
  });

  // ============================================== photo / video / files ==
  const fileInput = document.getElementById("file-input");
  const attachBtn = document.getElementById("attach-btn");
  const modal = document.getElementById("upload-modal");
  const previews = document.getElementById("upload-previews");
  const caption = document.getElementById("upload-caption");
  const uploadCount = document.getElementById("upload-count");
  const uploadSend = document.getElementById("upload-send");
  const dropZone = document.getElementById("drop-zone");
  const BLOCKED = /\.(exe|bat|cmd|com|msi|scr|vbs|ps1|pif|cpl)$/i;
  let queue = [];

  function guessKind(file) {
    if (/^image\/(jpeg|png|gif|webp)$/.test(file.type)) return "image";
    if (/^video\//.test(file.type)) return "video";
    return "file";
  }

  function renderPreviews() {
    previews.replaceChildren();
    queue.forEach(function (item, index) {
      const card = el("div", "preview");
      if (item.kind === "image") {
        const img = document.createElement("img");
        img.src = item.url;
        card.appendChild(img);
      } else if (item.kind === "video") {
        const v = document.createElement("video");
        v.src = item.url;
        v.muted = true;
        v.preload = "metadata";
        v.playsInline = true;
        v.addEventListener("loadedmetadata", function () { v.currentTime = Math.min(0.5, v.duration / 2 || 0); });
        card.appendChild(v);
        card.appendChild(el("span", "preview-badge", "VIDEO"));
      } else {
        card.classList.add("preview-file");
        card.appendChild(el("span", "file-icon", fileExt(item.file.name)));
      }
      card.appendChild(el("span", "preview-name", item.file.name + " · " + formatBytes(item.file.size)));
      const remove = el("button", "preview-remove");
      remove.type = "button";
      remove.setAttribute("aria-label", "Remove");
      remove.appendChild(icon("x", 14));
      remove.addEventListener("click", function () {
        URL.revokeObjectURL(item.url);
        queue.splice(index, 1);
        if (!queue.length) closeUpload(); else renderPreviews();
      });
      card.appendChild(remove);
      previews.appendChild(card);
    });
    uploadCount.textContent = queue.length === 1 ? "1 item" : queue.length + " items";
  }

  function openUpload(files) {
    Array.from(files).forEach(function (file) {
      const kind = guessKind(file);
      const limit = (chat.limitsMb[kind] || chat.limitsMb.file) * 1024 * 1024;
      if (BLOCKED.test(file.name)) { toast(file.name + ": this type of file is not allowed.", "error"); return; }
      if (file.size > limit) { toast(file.name + " is too big (max " + chat.limitsMb[kind] + " MB).", "error"); return; }
      if (file.size === 0) { toast(file.name + " is empty.", "error"); return; }
      queue.push({ file: file, kind: kind, url: URL.createObjectURL(file) });
    });
    if (!queue.length) return;
    renderPreviews();
    modal.hidden = false;
    caption.focus();
  }

  function closeUpload() {
    modal.hidden = true;
    queue.forEach(function (item) { URL.revokeObjectURL(item.url); });
    queue = [];
    caption.value = "";
    fileInput.value = "";
  }

  attachBtn.addEventListener("click", function () { fileInput.click(); });
  fileInput.addEventListener("change", function () { if (fileInput.files.length) openUpload(fileInput.files); });
  modal.querySelectorAll("[data-close-upload]").forEach(function (b) { b.addEventListener("click", closeUpload); });
  caption.addEventListener("keydown", function (e) { if (e.key === "Enter") { e.preventDefault(); uploadSend.click(); } });

  uploadSend.addEventListener("click", async function () {
    const items = queue.slice();
    const text = caption.value.trim();
    queue = [];
    modal.hidden = true;
    caption.value = "";
    fileInput.value = "";
    const replyId = replyTo ? replyTo.id : null;
    cancelReply();
    for (let i = 0; i < items.length; i++) {
      await uploadFile(items[i].file, { caption: i === 0 ? text : "", replyTo: i === 0 ? replyId : null });
      URL.revokeObjectURL(items[i].url);
    }
  });

  // Show a "sending…" bubble with a progress bar while the file uploads.
  function uploadFile(file, opts) {
    return new Promise(function (resolve) {
      const pending = el("div", "msg mine pending");
      pending.appendChild(el("div", "avatar sm spacer"));
      const body = el("div", "msg-body");
      const bubble = el("div", "bubble upload-bubble");
      const name = el("div", "upload-name", opts.voice ? "Voice note" : file.name);
      const bar = el("div", "progress");
      const barFill = el("div", "progress-fill");
      bar.appendChild(barFill);
      const status = el("small", "upload-status", "Sending… 0%");
      bubble.append(name, bar, status);
      body.appendChild(bubble);
      pending.appendChild(body);
      list.appendChild(pending);
      emptyState.hidden = true;
      scrollToBottom(true);

      const fd = new FormData();
      fd.append("file", file, file.name || "file");
      if (opts.caption) fd.append("caption", opts.caption);
      if (opts.replyTo) fd.append("reply_to", String(opts.replyTo));
      if (opts.voice) { fd.append("voice", "1"); fd.append("duration", String(opts.duration || 0)); }

      const xhr = new XMLHttpRequest();
      xhr.open("POST", chat.uploadUrl);
      xhr.setRequestHeader("X-CSRFToken", csrf());
      xhr.upload.addEventListener("progress", function (e) {
        if (!e.lengthComputable) return;
        const pct = Math.round((e.loaded / e.total) * 100);
        barFill.style.width = pct + "%";
        status.textContent = pct < 100 ? "Sending… " + pct + "%" : "Processing…";
      });
      xhr.addEventListener("load", function () {
        let data = {};
        try { data = JSON.parse(xhr.responseText); } catch (e) { /* not JSON */ }
        if (xhr.status === 201 && data.message) {
          pending.remove();
          messageArrived(data.message);
        } else {
          bubble.classList.add("failed");
          status.textContent = data.error || (xhr.status === 413 ? "File too large for the server." : "Upload failed.");
          setTimeout(function () { pending.remove(); }, 6000);
        }
        resolve();
      });
      xhr.addEventListener("error", function () {
        bubble.classList.add("failed");
        status.textContent = "Upload failed — check your connection.";
        setTimeout(function () { pending.remove(); }, 6000);
        resolve();
      });
      xhr.send(fd);
    });
  }

  // Drag & drop anywhere on the chat.
  const main = document.querySelector(".main");
  let dragDepth = 0;
  main.addEventListener("dragenter", function (e) {
    if (!e.dataTransfer || Array.from(e.dataTransfer.types).indexOf("Files") === -1) return;
    e.preventDefault();
    dragDepth++;
    dropZone.hidden = false;
  });
  main.addEventListener("dragover", function (e) { if (!dropZone.hidden) e.preventDefault(); });
  main.addEventListener("dragleave", function () { dragDepth = Math.max(0, dragDepth - 1); if (!dragDepth) dropZone.hidden = true; });
  main.addEventListener("drop", function (e) {
    if (dropZone.hidden) return;
    e.preventDefault();
    dragDepth = 0;
    dropZone.hidden = true;
    if (e.dataTransfer.files.length) openUpload(e.dataTransfer.files);
  });

  // Paste a screenshot / image straight into the message box.
  input.addEventListener("paste", function (e) {
    const files = Array.from((e.clipboardData && e.clipboardData.files) || []);
    if (files.length) {
      e.preventDefault();
      openUpload(files);
    }
  });

  // ============================================================ lightbox ==
  const lightbox = document.getElementById("lightbox");
  const lightboxImg = document.getElementById("lightbox-img");
  function openLightbox(m) {
    lightboxImg.src = m.file_url;
    document.getElementById("lightbox-name").textContent = m.file_name || "";
    document.getElementById("lightbox-download").href = m.file_url + "?download=1";
    lightbox.hidden = false;
  }
  function closeLightbox() { lightbox.hidden = true; lightboxImg.removeAttribute("src"); }
  document.getElementById("lightbox-close").addEventListener("click", closeLightbox);
  lightbox.addEventListener("click", function (e) { if (e.target === lightbox) closeLightbox(); });
  document.addEventListener("keydown", function (e) {
    if (e.key !== "Escape") return;
    if (!lightbox.hidden) closeLightbox();
    else if (!modal.hidden) closeUpload();
    else if (replyTo) cancelReply();
  });

  // ========================================================= voice notes ==
  const voiceBtn = document.getElementById("voice-btn");
  const recorderBar = document.getElementById("recorder");
  const recTime = document.getElementById("rec-time");
  let recorder = null;
  let recStream = null;
  let recChunks = [];
  let recStart = 0;
  let recTimer = null;
  let recCancelled = false;

  function pickMime() {
    const types = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg;codecs=opus"];
    for (let i = 0; i < types.length; i++) {
      if (window.MediaRecorder && MediaRecorder.isTypeSupported(types[i])) return types[i];
    }
    return "";
  }

  async function startRecording() {
    if (!navigator.mediaDevices || !window.MediaRecorder) {
      toast("Voice notes need a secure (https) connection and a modern browser.", "error");
      return;
    }
    try {
      recStream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
    } catch (e) {
      toast("Microphone access was blocked. Allow it in your browser settings.", "error");
      return;
    }
    const mime = pickMime();
    recorder = new MediaRecorder(recStream, mime ? { mimeType: mime, audioBitsPerSecond: 48000 } : undefined);
    recChunks = [];
    recCancelled = false;
    recorder.addEventListener("dataavailable", function (e) { if (e.data && e.data.size) recChunks.push(e.data); });
    recorder.addEventListener("stop", finishRecording);
    recorder.start(250);
    recStart = Date.now();
    form.classList.add("recording");
    recorderBar.hidden = false;
    recTime.textContent = "0:00";
    recTimer = setInterval(function () {
      const sec = (Date.now() - recStart) / 1000;
      recTime.textContent = formatDuration(sec);
      if (sec >= chat.maxVoiceSeconds) stopRecording(false);
    }, 250);
  }

  function stopRecording(cancel) {
    recCancelled = cancel;
    if (recorder && recorder.state !== "inactive") recorder.stop();
  }

  async function finishRecording() {
    clearInterval(recTimer);
    if (recStream) recStream.getTracks().forEach(function (t) { t.stop(); });
    form.classList.remove("recording");
    recorderBar.hidden = true;
    const duration = Math.round((Date.now() - recStart) / 1000);
    const type = (recorder && recorder.mimeType) || "audio/webm";
    recorder = null;
    if (recCancelled || !recChunks.length) return;
    if (duration < 1) { toast("Voice note too short — hold on a little longer.", "info"); return; }
    const ext = type.indexOf("mp4") !== -1 ? "m4a" : type.indexOf("ogg") !== -1 ? "ogg" : "webm";
    const file = new File(recChunks, "voice-note." + ext, { type: type.split(";")[0] });
    const replyId = replyTo ? replyTo.id : null;
    cancelReply();
    await uploadFile(file, { voice: true, duration: duration, replyTo: replyId });
  }

  voiceBtn.addEventListener("click", startRecording);
  document.getElementById("rec-cancel").addEventListener("click", function () { stopRecording(true); });
  document.getElementById("rec-send").addEventListener("click", function () { stopRecording(false); });

  if (window.matchMedia("(min-width: 821px)").matches) input.focus();
})();
