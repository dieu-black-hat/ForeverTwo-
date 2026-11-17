/*
 * ForeverTwo – audio & video calls (1-to-1, in direct messages).
 *
 * In plain words:
 *  - The sound and video travel DIRECTLY between the two browsers using WebRTC.
 *  - To find each other, the browsers first swap two small "letters":
 *      caller  → "offer"  (what I can send/receive + my network addresses)
 *      callee  → "answer" (the same, from the other side)
 *    Our Django server only delivers these letters (POST /api/calls/signal/),
 *    and each browser checks its mailbox every second or so (GET /api/calls/poll/).
 *  - STUN/TURN servers (see settings.py) help when people are behind routers.
 */
(function () {
  "use strict";

  const cfgNode = document.getElementById("call-config");
  if (!cfgNode) return;
  const cfg = JSON.parse(cfgNode.textContent);
  if (!cfg) return;

  const $ = function (id) { return document.getElementById(id); };
  const ui = {
    overlay: $("call-overlay"), remote: $("call-remote"), local: $("call-local"),
    avatar: $("call-avatar"), peer: $("call-peer"), status: $("call-status"),
    incoming: $("call-incoming"), controls: $("call-controls"),
    accept: $("call-accept"), decline: $("call-decline"), hangup: $("call-hangup"),
    mute: $("call-mute"), muteLabel: $("call-mute-label"),
    camera: $("call-camera"), cameraLabel: $("call-camera-label"), cameraWrap: $("call-camera-wrap"),
  };
  const toast = function (msg, kind) { if (window.chatToast) window.chatToast(msg, kind); };
  const csrf = function () { return window.getCookie ? window.getCookie("csrftoken") : ""; };

  let state = "idle"; // idle | outgoing | incoming | connecting | active | ending
  let call = null;
  let cursor = null;
  const supported = !!(window.RTCPeerConnection && navigator.mediaDevices && navigator.mediaDevices.getUserMedia);

  function newId() {
    return window.crypto && crypto.randomUUID ? crypto.randomUUID() : Date.now() + "-" + Math.random().toString(36).slice(2);
  }

  async function sendSignal(room, kind, callId, payload) {
    const fd = new FormData();
    fd.append("room", room);
    fd.append("kind", kind);
    fd.append("call_id", callId);
    if (payload) fd.append("payload", payload);
    try {
      await fetch(cfg.signalUrl, { method: "POST", body: fd, headers: { "X-CSRFToken": csrf() } });
    } catch (e) { /* ignore */ }
  }

  // ------------------------------------------------------------ ringing --
  let audioCtx = null;
  let ringTimer = null;
  function beep(freqs, ms) {
    try {
      audioCtx = audioCtx || new (window.AudioContext || window.webkitAudioContext)();
      if (audioCtx.state === "suspended") audioCtx.resume();
      const gain = audioCtx.createGain();
      gain.gain.value = 0.08;
      gain.connect(audioCtx.destination);
      freqs.forEach(function (f) {
        const osc = audioCtx.createOscillator();
        osc.frequency.value = f;
        osc.connect(gain);
        osc.start();
        osc.stop(audioCtx.currentTime + ms / 1000);
      });
    } catch (e) { /* sound not allowed – visual only */ }
  }
  function startRing(kind) {
    stopRing();
    const play = kind === "incoming"
      ? function () { beep([440, 480], 400); setTimeout(function () { beep([440, 480], 400); }, 600); if (navigator.vibrate) navigator.vibrate([300, 200, 300]); }
      : function () { beep([425], 1000); };
    play();
    ringTimer = setInterval(play, kind === "incoming" ? 2500 : 3500);
  }
  function stopRing() { clearInterval(ringTimer); ringTimer = null; }

  let titleTimer = null;
  const originalTitle = document.title;
  function flashTitle(text) {
    stopTitle();
    let on = false;
    titleTimer = setInterval(function () { on = !on; document.title = on ? text : originalTitle; }, 1000);
  }
  function stopTitle() { clearInterval(titleTimer); titleTimer = null; document.title = originalTitle; }

  // ----------------------------------------------------------------- UI --
  function setStatus(text) { ui.status.textContent = text; }

  function showOverlay() {
    ui.overlay.hidden = false;
    ui.overlay.classList.toggle("is-video", !!call.video);
    ui.overlay.classList.remove("has-remote-video");
    ui.avatar.textContent = call.peer.slice(0, 2).toUpperCase();
    ui.avatar.style.background = call.color || "#4f46e5";
    ui.peer.textContent = call.peer;
    ui.cameraWrap.hidden = !call.video;
    ui.incoming.hidden = state !== "incoming";
    ui.controls.hidden = state === "incoming";
    setMuted(false);
    setCameraOff(false);
  }

  function hideOverlay() {
    ui.overlay.hidden = true;
    ui.remote.srcObject = null;
    ui.local.srcObject = null;
    ui.local.hidden = true;
  }

  function startTimer() {
    call.startedAt = Date.now();
    call.tick = setInterval(function () {
      const s = Math.floor((Date.now() - call.startedAt) / 1000);
      setStatus(Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0"));
    }, 1000);
    setStatus("0:00");
  }

  function setMuted(muted) {
    if (call) call.muted = muted;
    if (call && call.stream) call.stream.getAudioTracks().forEach(function (t) { t.enabled = !muted; });
    ui.mute.classList.toggle("off", muted);
    ui.muteLabel.textContent = muted ? "Unmute" : "Mute";
  }
  function setCameraOff(off) {
    if (call) call.cameraOff = off;
    if (call && call.stream) call.stream.getVideoTracks().forEach(function (t) { t.enabled = !off; });
    ui.camera.classList.toggle("off", off);
    ui.cameraLabel.textContent = off ? "Camera on" : "Camera off";
    ui.local.classList.toggle("camera-off", off);
  }

  // ------------------------------------------------------------- WebRTC --
  async function getMedia(video) {
    return navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      video: video ? { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: "user" } : false,
    });
  }

  function waitForIce(pc) {
    // Collect our network addresses (max ~3s) so they travel inside the offer/answer.
    return new Promise(function (resolve) {
      if (pc.iceGatheringState === "complete") return resolve();
      const timer = setTimeout(resolve, 3000);
      pc.addEventListener("icegatheringstatechange", function () {
        if (pc.iceGatheringState === "complete") { clearTimeout(timer); resolve(); }
      });
    });
  }

  function createPeer() {
    const pc = new RTCPeerConnection({ iceServers: cfg.iceServers });
    pc.addEventListener("track", function (e) {
      ui.remote.srcObject = e.streams[0];
      ui.remote.play().catch(function () {});
      if (e.track.kind === "video") ui.overlay.classList.add("has-remote-video");
    });
    pc.addEventListener("connectionstatechange", function () {
      if (!call || call.pc !== pc) return;
      if (pc.connectionState === "connected") {
        clearTimeout(call.lostTimer);
        if (state !== "active") { state = "active"; startTimer(); }
      } else if (pc.connectionState === "disconnected") {
        setStatus("Reconnecting…");
        call.lostTimer = setTimeout(function () { hangUp("Connection lost"); }, 10000);
      } else if (pc.connectionState === "failed") {
        hangUp("Call failed — the network blocked the connection.");
      }
    });
    call.stream.getTracks().forEach(function (t) { pc.addTrack(t, call.stream); });
    return pc;
  }

  function showLocalVideo() {
    if (!call.video) return;
    ui.local.srcObject = call.stream;
    ui.local.hidden = false;
  }

  // ------------------------------------------------------- outgoing call --
  async function startCall(room, peer, color, video) {
    if (state !== "idle") return;
    if (!supported) {
      toast("Calls need a secure (https) connection and a modern browser.", "error");
      return;
    }
    call = { id: newId(), room: room, peer: peer, color: color, video: video, initiator: true };
    state = "outgoing";
    showOverlay();
    setStatus(video ? "Starting camera…" : "Starting microphone…");
    try {
      call.stream = await getMedia(video);
    } catch (e) {
      end(video ? "Camera or microphone access was blocked." : "Microphone access was blocked.", { noLog: true });
      return;
    }
    if (!call || state !== "outgoing") return;
    showLocalVideo();
    setStatus("Calling…");
    call.pc = createPeer();
    await call.pc.setLocalDescription(await call.pc.createOffer());
    await waitForIce(call.pc);
    if (!call || state !== "outgoing") return;
    await sendSignal(room, "offer", call.id, JSON.stringify({ sdp: call.pc.localDescription, video: video }));
    setStatus("Ringing…");
    startRing("outgoing");
    call.noAnswer = setTimeout(function () { hangUp("No answer"); }, 45000);
  }

  // ------------------------------------------------------- incoming call --
  function onOffer(s) {
    if (state !== "idle") {
      if (!call || call.id !== s.call_id) sendSignal(s.room, "busy", s.call_id, "");
      return;
    }
    let data;
    try { data = JSON.parse(s.payload); } catch (e) { return; }
    call = { id: s.call_id, room: s.room, peer: s.sender, color: s.color, video: !!data.video, initiator: false, offer: data.sdp };
    state = "incoming";
    showOverlay();
    setStatus(call.video ? "Incoming video call…" : "Incoming audio call…");
    startRing("incoming");
    flashTitle("📞 " + s.sender + " is calling");
    if (window.chatNotify && (document.hidden || !document.hasFocus())) {
      call.popup = window.chatNotify(
        call.video ? "🎥 Incoming video call" : "📞 Incoming audio call", s.sender + " is calling you", null, "call"
      );
    }
    call.noAnswer = setTimeout(function () { end("Missed call"); }, 45000);
  }

  async function accept() {
    if (state !== "incoming") return;
    if (call.popup) call.popup.close();
    stopRing();
    stopTitle();
    clearTimeout(call.noAnswer);
    state = "connecting";
    ui.incoming.hidden = true;
    ui.controls.hidden = false;
    setStatus("Connecting…");
    try {
      call.stream = await getMedia(call.video);
    } catch (e) {
      sendSignal(call.room, "decline", call.id, "");
      end("Microphone/camera access was blocked, so the call could not start.");
      return;
    }
    showLocalVideo();
    call.pc = createPeer();
    await call.pc.setRemoteDescription(call.offer);
    await call.pc.setLocalDescription(await call.pc.createAnswer());
    await waitForIce(call.pc);
    if (!call) return;
    await sendSignal(call.room, "answer", call.id, JSON.stringify({ sdp: call.pc.localDescription }));
  }

  function decline() {
    if (state !== "incoming") return;
    sendSignal(call.room, "decline", call.id, "");
    end("Call declined");
  }

  // ----------------------------------------------------------- ending --
  function hangUp(reason) {
    if (!call) return;
    sendSignal(call.room, "hangup", call.id, "");
    end(reason || "Call ended");
  }

  function logCall(c, reason) {
    // The caller writes a small record into the chat ("Video call · 2:31", "Missed audio call").
    const type = c.video ? "Video call" : "Audio call";
    let text;
    if (c.startedAt) {
      const s = Math.floor((Date.now() - c.startedAt) / 1000);
      text = type + " · " + Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0");
    } else if (/declined/i.test(reason)) {
      text = type + " · declined";
    } else {
      text = "Missed " + type.toLowerCase();
    }
    const fd = new FormData();
    fd.append("kind", "call");
    fd.append("content", text);
    fetch(cfg.sendUrl.replace("__room__", c.room), { method: "POST", body: fd, headers: { "X-CSRFToken": csrf() } })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        const cfgNode = document.getElementById("chat-config");
        if (d.message && cfgNode && JSON.parse(cfgNode.textContent).slug === c.room && window.chatMessageArrived) {
          window.chatMessageArrived(d.message);
        }
      })
      .catch(function () {});
  }

  function end(reason, opts) {
    if (!call || state === "ending") return;
    const c = call;
    state = "ending";
    stopRing();
    stopTitle();
    if (c.popup) c.popup.close();
    clearTimeout(c.noAnswer);
    clearTimeout(c.lostTimer);
    clearInterval(c.tick);
    if (c.stream) c.stream.getTracks().forEach(function (t) { t.stop(); });
    if (c.pc) c.pc.close();
    if (c.initiator && !(opts && opts.noLog)) logCall(c, reason || "");
    ui.incoming.hidden = true;
    ui.controls.hidden = true;
    ui.overlay.classList.remove("has-remote-video");
    setStatus(reason || "Call ended");
    setTimeout(function () {
      hideOverlay();
      call = null;
      state = "idle";
    }, 1600);
  }

  // --------------------------------------------------------- mailbox --
  async function onSignal(s) {
    if (s.kind === "offer") return onOffer(s);
    if (!call || call.id !== s.call_id) return;
    if (s.kind === "answer" && call.initiator && state === "outgoing") {
      stopRing();
      clearTimeout(call.noAnswer);
      state = "connecting";
      setStatus("Connecting…");
      try {
        await call.pc.setRemoteDescription(JSON.parse(s.payload).sdp);
      } catch (e) {
        hangUp("Call failed to connect.");
      }
    } else if (s.kind === "decline") {
      end(call.peer + " declined the call");
    } else if (s.kind === "busy") {
      end(call.peer + " is on another call");
    } else if (s.kind === "hangup") {
      end(state === "incoming" ? "Missed call" : "Call ended");
    } else if (s.kind === "taken" && state === "incoming") {
      end("Answered on another device", { noLog: true });
    }
  }

  async function poll() {
    try {
      const url = cursor === null ? cfg.pollUrl : cfg.pollUrl + "?after=" + cursor;
      const res = await fetch(url, { headers: { "X-Requested-With": "XMLHttpRequest" } });
      if (res.ok && !res.redirected) {
        const data = await res.json();
        cursor = data.cursor;
        for (let i = 0; i < data.signals.length; i++) await onSignal(data.signals[i]);
      }
    } catch (e) { /* offline – retry */ }
    const delay = state !== "idle" ? 1000 : document.hidden ? 3000 : 1500;
    setTimeout(poll, delay);
  }
  poll();

  // ---------------------------------------------------------- buttons --
  document.querySelectorAll("[data-call]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      startCall(btn.dataset.room, btn.dataset.peer, btn.dataset.color, btn.dataset.call === "video");
    });
  });
  ui.accept.addEventListener("click", accept);
  ui.decline.addEventListener("click", decline);
  ui.hangup.addEventListener("click", function () { hangUp("Call ended"); });
  ui.mute.addEventListener("click", function () { setMuted(!call.muted); });
  ui.camera.addEventListener("click", function () { setCameraOff(!call.cameraOff); });

  // Leaving or reloading the page ends the call, so warn first and tell the other side.
  window.addEventListener("beforeunload", function (e) {
    if (state === "active" || state === "connecting" || state === "outgoing") {
      e.preventDefault();
      e.returnValue = "";
    }
  });
  window.addEventListener("pagehide", function () {
    if (!call || state === "ending") return;
    const fd = new FormData();
    fd.append("room", call.room);
    fd.append("kind", state === "incoming" ? "decline" : "hangup");
    fd.append("call_id", call.id);
    fd.append("csrfmiddlewaretoken", csrf());
    navigator.sendBeacon(cfg.signalUrl, fd);
  });
})();
