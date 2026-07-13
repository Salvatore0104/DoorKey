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
      this.toast(`State refresh failed: ${this.errorText(err)}`, true);
    }
  }

  async answer() {
    await this.safeAction(async () => {
      this.toast("Answering...");
      await this.api("POST", "haier_hr6107/call/answer", {});
      this.toast("Answered. Connecting media...");
      await this.connectMedia();
      await this.refresh();
    }, "Answer failed");
  }

  async hangup() {
    await this.safeAction(async () => {
      await this.api("POST", "haier_hr6107/call/hangup", {});
      this.closePeer();
      await this.refresh();
      this.toast("Call ended");
    }, "Hang up failed");
  }

  async unlock() {
    await this.safeAction(async () => {
      await this.api("POST", "haier_hr6107/unlock", {});
      await this.refresh();
      this.toast("Door opened");
    }, "Open door failed");
  }

  async connectMedia() {
    const video = this.shadowRoot.querySelector("#video");
    const stream = new MediaStream();
    video.srcObject = stream;
    video.muted = false;

    this.closePeer();
    this.pc = new RTCPeerConnection();
    this.pc.ontrack = (event) => {
      for (const track of event.streams?.[0]?.getTracks?.() || [event.track]) {
        if (!stream.getTracks().some((item) => item.id === track.id)) {
          stream.addTrack(track);
        }
      }
      this.setMediaStatus("Media receiving");
    };
    this.pc.onconnectionstatechange = () => {
      const state = this.pc?.connectionState || "closed";
      this.setMediaStatus(`WebRTC: ${state}`);
      if (state === "failed" || state === "disconnected") {
        this.toast(`Media ${state}`, true);
      }
    };
    this.pc.oniceconnectionstatechange = () => {
      const state = this.pc?.iceConnectionState || "closed";
      this.setMediaStatus(`ICE: ${state}`);
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
    await video.play().catch((err) => {
      this.toast(`Tap the video if playback is blocked: ${this.errorText(err)}`, true);
    });
    this.toast("Media connected");
  }

  closePeer() {
    if (this.pc) {
      this.pc.close();
      this.pc = null;
    }
    const video = this.shadowRoot?.querySelector("#video");
    if (video) video.srcObject = null;
    this.setMediaStatus("Media idle");
  }

  async safeAction(fn, label) {
    try {
      await fn();
    } catch (err) {
      this.toast(`${label}: ${this.errorText(err)}`, true);
      await this.refresh();
    }
  }

  errorText(err) {
    if (!err) return "unknown error";
    if (typeof err === "string") return err;
    return err.message || err.error || err.detail || JSON.stringify(err);
  }

  updateState() {
    if (!this.shadowRoot || !this.state) return;
    const s = this.state;
    const callState = s.call_state || "UNKNOWN";
    const actions = s.actions || {};
    this.shadowRoot.querySelector("#state").textContent = callState;
    this.shadowRoot.querySelector("#listener").textContent =
      s.listener === "online" ? "online" : "offline";
    this.shadowRoot.querySelector("#packets").textContent =
      `${s.video_packets || 0} / ${s.audio_packets || 0}`;
    this.shadowRoot.querySelector("#ring").hidden = callState !== "RINGING";
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
    el.className = error ? "error show" : "show";
    window.clearTimeout(this.toastTimer);
    this.toastTimer = window.setTimeout(() => (el.className = ""), 4500);
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
        #mediaStatus { color: var(--secondary-text-color); font-size: 13px; }
        #toast { display: none; padding: 10px 14px; margin: 0 14px 14px; border-radius: 10px; background: var(--secondary-background-color); }
        #toast.show { display: block; }
        #toast.error { color: var(--error-color); }
        @media (max-width: 600px) { .actions { grid-template-columns: 1fr 1fr; } .stats { grid-template-columns: 1fr; } }
      </style>
      <ha-card header="${this.config?.title || "Door Intercom 501"}">
        <div class="media">
          <video id="video" autoplay playsinline controls></video>
          <div id="ring" class="ring" hidden>Door call</div>
        </div>
        <div class="body">
          <div class="stats">
            <div class="stat"><span>Call state</span><strong id="state">-</strong></div>
            <div class="stat"><span>Backend</span><strong id="listener">-</strong></div>
            <div class="stat"><span>Video / audio packets</span><strong id="packets">0 / 0</strong></div>
          </div>
          <div id="mediaStatus">Media idle</div>
          <div class="actions">
            <mwc-button id="media" outlined>Connect media</mwc-button>
            <mwc-button id="answer" raised disabled>Answer</mwc-button>
            <mwc-button id="unlock" raised disabled>Open door</mwc-button>
            <mwc-button id="hangup" outlined disabled>Hang up</mwc-button>
          </div>
        </div>
        <div id="toast"></div>
      </ha-card>
    `;
    this.shadowRoot.querySelector("#media").onclick = () => this.safeAction(
      () => this.connectMedia(),
      "Media connect failed",
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
  name: "Haier HR-6107 Door Intercom",
  description: "Answer, watch video, and open the 501 door from Home Assistant.",
});
