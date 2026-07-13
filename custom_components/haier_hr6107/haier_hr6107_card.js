const HR6107_TEXT = {
  title: "\u95e8\u7981\u6765\u7535",
  subtitle: "501 \u95e8\u53e3\u673a",
  idle: "\u7b49\u5f85\u6765\u7535",
  ringing: "\u95e8\u53e3\u673a\u6b63\u5728\u547c\u53eb",
  active: "\u901a\u8bdd\u4e2d",
  backendOnline: "\u540e\u7aef\u5728\u7ebf",
  backendOffline: "\u540e\u7aef\u79bb\u7ebf",
  answer: "\u63a5\u542c",
  unlock: "\u5f00\u95e8",
  hangup: "\u6302\u65ad",
  media: "\u753b\u9762",
  connecting: "\u6b63\u5728\u8fde\u63a5\u753b\u9762\u2026",
  mediaIdle: "\u753b\u9762\u672a\u8fde\u63a5",
  mediaReady: "\u753b\u9762\u5df2\u8fde\u63a5",
  answered: "\u5df2\u63a5\u542c\uff0c\u6b63\u5728\u6253\u5f00\u753b\u9762",
  opened: "\u5df2\u5f00\u95e8",
  ended: "\u5df2\u6302\u65ad",
  tapVideo: "\u5982\u679c\u753b\u9762\u88ab\u6d4f\u89c8\u5668\u62e6\u622a\uff0c\u8bf7\u70b9\u51fb\u89c6\u9891\u533a\u57df",
};

class HaierHR6107Card extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this.pc = null;
    this.state = null;
    this.timer = null;
    this.toastTimer = null;
  }

  setConfig(config) {
    this.config = config || {};
    this.render();
  }

  set hass(hass) {
    this._hass = hass;
    if (!this.timer) {
      this.refresh();
      this.timer = window.setInterval(() => this.refresh(), 1000);
    }
  }

  disconnectedCallback() {
    if (this.timer) window.clearInterval(this.timer);
    if (this.toastTimer) window.clearTimeout(this.toastTimer);
    this.closePeer();
    this.timer = null;
  }

  getCardSize() {
    return 5;
  }

  async api(method, path, body) {
    return this._hass.callApi(method, path, body);
  }

  async refresh() {
    if (!this._hass) return;
    try {
      this.state = await this.api("GET", "haier_hr6107/state");
      this.updateState();
    } catch (err) {
      this.toast(`\u72b6\u6001\u8bfb\u53d6\u5931\u8d25\uff1a${this.errorText(err)}`, true);
    }
  }

  async answer() {
    await this.safeAction(async () => {
      this.toast("\u6b63\u5728\u63a5\u542c\u2026");
      await this.api("POST", "haier_hr6107/call/answer", {});
      this.toast(HR6107_TEXT.answered);
      await this.connectMedia();
      await this.refresh();
    }, "\u63a5\u542c\u5931\u8d25");
  }

  async hangup() {
    await this.safeAction(async () => {
      await this.api("POST", "haier_hr6107/call/hangup", {});
      this.closePeer();
      await this.refresh();
      this.toast(HR6107_TEXT.ended);
    }, "\u6302\u65ad\u5931\u8d25");
  }

  async unlock() {
    await this.safeAction(async () => {
      await this.api("POST", "haier_hr6107/unlock", {});
      await this.refresh();
      this.toast(HR6107_TEXT.opened);
    }, "\u5f00\u95e8\u5931\u8d25");
  }

  async connectMedia() {
    this.closePeer();
    this.setMediaStatus(HR6107_TEXT.connecting);

    const video = this.shadowRoot.querySelector("#video");
    const stream = new MediaStream();
    video.srcObject = stream;
    video.muted = false;

    this.pc = new RTCPeerConnection();
    this.pc.ontrack = (event) => {
      const tracks = event.streams?.[0]?.getTracks?.() || [event.track];
      for (const track of tracks) {
        if (!stream.getTracks().some((item) => item.id === track.id)) {
          stream.addTrack(track);
        }
      }
      this.shadowRoot.querySelector(".media")?.classList.add("has-stream");
      this.setMediaStatus(HR6107_TEXT.mediaReady);
    };
    this.pc.onconnectionstatechange = () => {
      const state = this.pc?.connectionState || "closed";
      this.setMediaStatus(`WebRTC：${this.zhConnectionState(state)}`);
      if (state === "failed" || state === "disconnected") {
        this.toast(`\u753b\u9762\u8fde\u63a5${this.zhConnectionState(state)}`, true);
      }
    };
    this.pc.oniceconnectionstatechange = () => {
      const state = this.pc?.iceConnectionState || "closed";
      this.setMediaStatus(`ICE：${this.zhConnectionState(state)}`);
    };

    this.pc.addTransceiver("video", { direction: "recvonly" });
    this.pc.addTransceiver("audio", { direction: "recvonly" });

    const offer = await this.pc.createOffer();
    await this.pc.setLocalDescription(offer);
    const answer = await this.api("POST", "haier_hr6107/webrtc/offer", {
      sdp: this.pc.localDescription.sdp,
      type: this.pc.localDescription.type,
    });
    await this.pc.setRemoteDescription(answer);
    await video.play().catch(() => this.toast(HR6107_TEXT.tapVideo, true));
    this.toast(HR6107_TEXT.mediaReady);
  }

  closePeer() {
    if (this.pc) {
      this.pc.close();
      this.pc = null;
    }
    const video = this.shadowRoot?.querySelector("#video");
    if (video) video.srcObject = null;
    this.shadowRoot?.querySelector(".media")?.classList.remove("has-stream");
    this.setMediaStatus(HR6107_TEXT.mediaIdle);
  }

  async safeAction(fn, label) {
    try {
      await fn();
    } catch (err) {
      this.toast(`${label}\uff1a${this.errorText(err)}`, true);
      await this.refresh();
    }
  }

  errorText(err) {
    if (!err) return "\u672a\u77e5\u9519\u8bef";
    if (typeof err === "string") return err;
    return err.message || err.error || err.detail || JSON.stringify(err);
  }

  zhConnectionState(state) {
    return {
      new: "\u65b0\u5efa",
      checking: "\u68c0\u67e5\u4e2d",
      connecting: "\u8fde\u63a5\u4e2d",
      connected: "\u5df2\u8fde\u63a5",
      completed: "\u5df2\u5b8c\u6210",
      disconnected: "\u5df2\u65ad\u5f00",
      failed: "\u5931\u8d25",
      closed: "\u5df2\u5173\u95ed",
    }[state] || state;
  }

  callLabel(callState) {
    if (callState === "RINGING") return HR6107_TEXT.ringing;
    if (callState === "ACTIVE" || callState === "CONNECTING") return HR6107_TEXT.active;
    return HR6107_TEXT.idle;
  }

  updateState() {
    if (!this.shadowRoot || !this.state) return;
    const s = this.state;
    const callState = s.call_state || "UNKNOWN";
    const actions = s.actions || {};
    this.shadowRoot.querySelector("#statusText").textContent = this.callLabel(callState);
    this.shadowRoot.querySelector("#state").textContent = callState;
    this.shadowRoot.querySelector("#listener").textContent =
      s.listener === "online" ? HR6107_TEXT.backendOnline : HR6107_TEXT.backendOffline;
    this.shadowRoot.querySelector("#packets").textContent =
      `${s.video_packets || 0} / ${s.audio_packets || 0}`;
    this.shadowRoot.querySelector("#shell").classList.toggle("ringing", callState === "RINGING");
    this.shadowRoot.querySelector("#shell").classList.toggle(
      "active",
      ["CONNECTING", "ACTIVE"].includes(callState),
    );
    this.shadowRoot.querySelector("#answer").disabled = callState !== "RINGING";
    this.shadowRoot.querySelector("#hangup").disabled =
      !["RINGING", "CONNECTING", "ACTIVE"].includes(callState);
    this.shadowRoot.querySelector("#unlock").disabled =
      !(actions.unlock && (actions.unlock_idle_enabled || callState === "ACTIVE"));
  }

  setMediaStatus(message) {
    const el = this.shadowRoot?.querySelector("#mediaStatus");
    if (el) el.textContent = message;
  }

  toast(message, error = false) {
    const el = this.shadowRoot?.querySelector("#toast");
    if (!el) return;
    el.textContent = message;
    el.className = error ? "toast error show" : "toast show";
    window.clearTimeout(this.toastTimer);
    this.toastTimer = window.setTimeout(() => (el.className = "toast"), 4500);
  }

  render() {
    this.shadowRoot.innerHTML = `
      <style>
        :host { --dk-green: #30d158; --dk-red: #ff453a; --dk-blue: #0a84ff; }
        ha-card { overflow: hidden; border-radius: 28px; background: transparent; box-shadow: none; }
        .shell {
          position: relative;
          overflow: hidden;
          border-radius: 28px;
          color: white;
          background:
            radial-gradient(circle at 18% 10%, rgba(10,132,255,.45), transparent 32%),
            radial-gradient(circle at 82% 18%, rgba(48,209,88,.32), transparent 30%),
            linear-gradient(145deg, #10131c, #050608 68%);
          border: 1px solid rgba(255,255,255,.13);
          box-shadow: 0 24px 60px rgba(0,0,0,.35);
        }
        .shell::before {
          content: "";
          position: absolute;
          inset: -40%;
          background: conic-gradient(from 180deg, transparent, rgba(255,255,255,.12), transparent 28%);
          animation: sheen 8s linear infinite;
          opacity: .65;
          pointer-events: none;
        }
        .shell.ringing { animation: pulse 1.45s ease-in-out infinite; }
        .island {
          position: relative;
          z-index: 1;
          width: min(84%, 420px);
          margin: 16px auto 12px;
          padding: 12px 16px;
          border-radius: 999px;
          display: grid;
          grid-template-columns: 46px 1fr auto;
          align-items: center;
          gap: 12px;
          background: rgba(0,0,0,.72);
          box-shadow: inset 0 0 0 1px rgba(255,255,255,.08), 0 18px 36px rgba(0,0,0,.35);
          backdrop-filter: blur(22px);
        }
        .avatar {
          width: 46px;
          height: 46px;
          border-radius: 50%;
          display: grid;
          place-items: center;
          background: linear-gradient(145deg, #ffd60a, #ff9f0a);
          color: #1a1200;
          font-size: 23px;
          box-shadow: 0 0 0 3px rgba(255,255,255,.08);
        }
        .title { font-weight: 750; font-size: 16px; line-height: 1.2; }
        .subtitle { color: rgba(255,255,255,.62); font-size: 12px; margin-top: 2px; }
        .signal { width: 10px; height: 10px; border-radius: 50%; background: var(--dk-green); box-shadow: 0 0 18px var(--dk-green); }
        .media {
          position: relative;
          z-index: 1;
          margin: 0 14px;
          min-height: 300px;
          border-radius: 24px;
          overflow: hidden;
          background: #020304;
          border: 1px solid rgba(255,255,255,.1);
        }
        video { width: 100%; min-height: 300px; max-height: 58vh; object-fit: contain; background: #020304; display: block; }
        .empty {
          position: absolute;
          inset: 0;
          display: grid;
          place-items: center;
          pointer-events: none;
          color: rgba(255,255,255,.52);
          font-size: 14px;
        }
        .media.has-stream .empty { display: none; }
        .body { position: relative; z-index: 1; padding: 14px; display: grid; gap: 12px; }
        .status-line { display: flex; justify-content: space-between; gap: 12px; color: rgba(255,255,255,.78); font-size: 14px; }
        .stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
        .stat {
          border-radius: 18px;
          padding: 12px;
          background: rgba(255,255,255,.08);
          border: 1px solid rgba(255,255,255,.1);
          backdrop-filter: blur(18px);
        }
        .stat span { display: block; color: rgba(255,255,255,.55); font-size: 12px; margin-bottom: 5px; }
        .stat strong { font-size: 14px; font-weight: 700; }
        .actions { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; padding: 2px 4px 4px; }
        button {
          border: 0;
          color: white;
          cursor: pointer;
          -webkit-tap-highlight-color: transparent;
          background: transparent;
          display: grid;
          justify-items: center;
          gap: 7px;
          font: inherit;
        }
        button:disabled { opacity: .34; cursor: not-allowed; }
        .bubble {
          width: 58px;
          height: 58px;
          border-radius: 50%;
          display: grid;
          place-items: center;
          font-size: 25px;
          box-shadow: 0 12px 24px rgba(0,0,0,.26), inset 0 1px 0 rgba(255,255,255,.22);
        }
        .label { color: rgba(255,255,255,.78); font-size: 12px; }
        .answer .bubble { background: var(--dk-green); }
        .unlock .bubble { background: linear-gradient(145deg, #64d2ff, var(--dk-blue)); }
        .hangup .bubble { background: var(--dk-red); transform: rotate(135deg); }
        .mediaBtn .bubble { background: rgba(255,255,255,.16); }
        .toast {
          display: none;
          position: relative;
          z-index: 2;
          margin: 0 14px 14px;
          padding: 12px 14px;
          border-radius: 18px;
          background: rgba(255,255,255,.12);
          border: 1px solid rgba(255,255,255,.12);
          color: white;
          backdrop-filter: blur(18px);
        }
        .toast.show { display: block; }
        .toast.error { color: #ffd6d3; }
        @keyframes pulse {
          0%, 100% { box-shadow: 0 24px 60px rgba(0,0,0,.35), 0 0 0 rgba(48,209,88,0); }
          50% { box-shadow: 0 24px 60px rgba(0,0,0,.35), 0 0 38px rgba(48,209,88,.32); }
        }
        @keyframes sheen { to { transform: rotate(360deg); } }
        @media (max-width: 600px) {
          .island { width: calc(100% - 28px); grid-template-columns: 42px 1fr auto; padding: 10px 12px; }
          .avatar { width: 42px; height: 42px; }
          .stats { grid-template-columns: 1fr; }
          .actions { grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 6px; }
          .bubble { width: 52px; height: 52px; font-size: 22px; }
        }
      </style>
      <ha-card>
        <div id="shell" class="shell">
          <div class="island">
            <div class="avatar">\u95e8</div>
            <div>
              <div class="title">${this.config?.title || HR6107_TEXT.title}</div>
              <div class="subtitle">${HR6107_TEXT.subtitle} · <span id="statusText">${HR6107_TEXT.idle}</span></div>
            </div>
            <div class="signal"></div>
          </div>
          <div class="media">
            <video id="video" autoplay playsinline controls></video>
            <div class="empty">\u63a5\u542c\u540e\u81ea\u52a8\u663e\u793a\u95e8\u53e3\u753b\u9762</div>
          </div>
          <div class="body">
            <div class="status-line">
              <span id="mediaStatus">${HR6107_TEXT.mediaIdle}</span>
              <span id="listener">${HR6107_TEXT.backendOffline}</span>
            </div>
            <div class="stats">
              <div class="stat"><span>\u901a\u8bdd\u72b6\u6001</span><strong id="state">-</strong></div>
              <div class="stat"><span>\u5a92\u4f53\u6570\u636e\u5305</span><strong id="packets">0 / 0</strong></div>
              <div class="stat"><span>\u64cd\u4f5c\u63d0\u793a</span><strong>\u5148\u63a5\u542c\uff0c\u518d\u5f00\u95e8</strong></div>
            </div>
            <div class="actions">
              <button id="mediaBtn" class="mediaBtn" type="button"><span class="bubble">\ud83d\udcf9</span><span class="label">${HR6107_TEXT.media}</span></button>
              <button id="answer" class="answer" type="button" disabled><span class="bubble">\ud83d\udcde</span><span class="label">${HR6107_TEXT.answer}</span></button>
              <button id="unlock" class="unlock" type="button" disabled><span class="bubble">\ud83d\udd13</span><span class="label">${HR6107_TEXT.unlock}</span></button>
              <button id="hangup" class="hangup" type="button" disabled><span class="bubble">\ud83d\udcde</span><span class="label">${HR6107_TEXT.hangup}</span></button>
            </div>
          </div>
          <div id="toast" class="toast"></div>
        </div>
      </ha-card>
    `;
    this.shadowRoot.querySelector("#mediaBtn").onclick = () => this.safeAction(
      () => this.connectMedia(),
      "\u753b\u9762\u8fde\u63a5\u5931\u8d25",
    );
    this.shadowRoot.querySelector("#answer").onclick = () => this.answer();
    this.shadowRoot.querySelector("#unlock").onclick = () => this.unlock();
    this.shadowRoot.querySelector("#hangup").onclick = () => this.hangup();
    this.updateState();
  }
}

customElements.define("haier-hr6107-card", HaierHR6107Card);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "haier-hr6107-card",
  name: "\u6d77\u5c14 HR-6107 \u95e8\u7981",
  description: "\u5728 Home Assistant \u5185\u63a5\u542c\u3001\u770b\u753b\u9762\u548c\u5f00\u95e8\u3002",
});
