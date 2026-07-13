class HaierHR6107Card extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this.pc = null;
    this.state = null;
    this.timer = null;
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
    if (this.pc) this.pc.close();
    this.timer = null;
    this.pc = null;
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
      this.toast(`状态读取失败：${err.message || err}`, true);
    }
  }

  async answer() {
    await this.safeAction(async () => {
      await this.api("POST", "haier_hr6107/call/answer", {});
      await this.connectMedia();
      await this.refresh();
    }, "接听失败");
  }

  async hangup() {
    await this.safeAction(async () => {
      await this.api("POST", "haier_hr6107/call/hangup", {});
      if (this.pc) this.pc.close();
      this.pc = null;
      await this.refresh();
    }, "挂断失败");
  }

  async unlock() {
    await this.safeAction(async () => {
      await this.api("POST", "haier_hr6107/unlock", {});
      await this.refresh();
    }, "开门失败");
  }

  async connectMedia() {
    if (this.pc) this.pc.close();
    const video = this.shadowRoot.querySelector("#video");
    const stream = new MediaStream();
    video.srcObject = stream;

    this.pc = new RTCPeerConnection();
    this.pc.ontrack = (event) => stream.addTrack(event.track);
    this.pc.addTransceiver("video", { direction: "recvonly" });
    this.pc.addTransceiver("audio", { direction: "recvonly" });

    const offer = await this.pc.createOffer();
    await this.pc.setLocalDescription(offer);
    const answer = await this.api("POST", "haier_hr6107/webrtc/offer", {
      sdp: this.pc.localDescription.sdp,
      type: this.pc.localDescription.type,
    });
    await this.pc.setRemoteDescription(answer);
    this.toast("媒体已连接");
  }

  async safeAction(fn, label) {
    try {
      await fn();
    } catch (err) {
      this.toast(`${label}：${err.message || err}`, true);
    }
  }

  updateState() {
    if (!this.shadowRoot || !this.state) return;
    const s = this.state;
    const callState = s.call_state || "UNKNOWN";
    const actions = s.actions || {};
    this.shadowRoot.querySelector("#state").textContent = callState;
    this.shadowRoot.querySelector("#listener").textContent =
      s.listener === "online" ? "在线" : "离线";
    this.shadowRoot.querySelector("#packets").textContent =
      `${s.video_packets || 0} / ${s.audio_packets || 0}`;
    this.shadowRoot.querySelector("#ring").hidden = callState !== "RINGING";
    this.shadowRoot.querySelector("#answer").disabled = callState !== "RINGING";
    this.shadowRoot.querySelector("#hangup").disabled =
      !["RINGING", "CONNECTING", "ACTIVE"].includes(callState);
    this.shadowRoot.querySelector("#unlock").disabled =
      !(actions.unlock && (actions.unlock_idle_enabled || callState === "ACTIVE"));
  }

  toast(message, error = false) {
    const el = this.shadowRoot?.querySelector("#toast");
    if (!el) return;
    el.textContent = message;
    el.className = error ? "error show" : "show";
    window.clearTimeout(this.toastTimer);
    this.toastTimer = window.setTimeout(() => (el.className = ""), 3000);
  }

  render() {
    this.shadowRoot.innerHTML = `
      <style>
        ha-card { overflow: hidden; }
        .media { position: relative; background: #05070a; min-height: 260px; display: grid; place-items: center; }
        video { width: 100%; min-height: 260px; max-height: 55vh; object-fit: contain; background: #05070a; }
        .ring { position: absolute; inset: 0; display: grid; place-items: center; background: rgba(0,0,0,.42); color: white; font-size: 24px; font-weight: 700; }
        .body { padding: 14px; display: grid; gap: 12px; }
        .stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
        .stat { border: 1px solid var(--divider-color); border-radius: 10px; padding: 10px; }
        .stat span { display: block; color: var(--secondary-text-color); font-size: 12px; margin-bottom: 4px; }
        .stat strong { font-size: 16px; }
        .actions { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; }
        mwc-button { border-radius: 10px; }
        #toast { display: none; padding: 10px 14px; margin: 0 14px 14px; border-radius: 10px; background: var(--secondary-background-color); }
        #toast.show { display: block; }
        #toast.error { color: var(--error-color); }
        @media (max-width: 600px) { .actions { grid-template-columns: 1fr 1fr; } .stats { grid-template-columns: 1fr; } }
      </style>
      <ha-card header="${this.config?.title || "501 门禁"}">
        <div class="media">
          <video id="video" autoplay playsinline controls></video>
          <div id="ring" class="ring" hidden>门禁来电</div>
        </div>
        <div class="body">
          <div class="stats">
            <div class="stat"><span>通话状态</span><strong id="state">—</strong></div>
            <div class="stat"><span>终端服务</span><strong id="listener">—</strong></div>
            <div class="stat"><span>视频/音频包</span><strong id="packets">0 / 0</strong></div>
          </div>
          <div class="actions">
            <mwc-button id="media" outlined>连接媒体</mwc-button>
            <mwc-button id="answer" raised disabled>接听</mwc-button>
            <mwc-button id="unlock" raised disabled>开门</mwc-button>
            <mwc-button id="hangup" outlined disabled>挂断</mwc-button>
          </div>
        </div>
        <div id="toast"></div>
      </ha-card>
    `;
    this.shadowRoot.querySelector("#media").onclick = () => this.connectMedia();
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
  name: "Haier HR-6107 门禁",
  description: "海尔 HR-6107 501 门禁接听、视频和开门卡片",
});
