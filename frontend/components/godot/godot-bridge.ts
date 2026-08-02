import {
  createGodotEnvelope,
  decodeGodotClientMessage,
  type GodotClientMessageType,
  type GodotEnvelope,
  type GodotHostMessageType,
} from "./protocol";

type MessageHandler = (message: GodotEnvelope<GodotClientMessageType>) => void;
type ProtocolErrorHandler = (error: string) => void;

export class GodotBridge {
  private sequence = 0;
  private lastClientSequence = -1;
  private isStarted = false;

  constructor(
    private readonly iframe: HTMLIFrameElement,
    private readonly runId: string,
    private readonly expectedOrigin: string,
    private readonly onMessage: MessageHandler,
    private readonly onProtocolError: ProtocolErrorHandler,
  ) {}

  start(): void {
    if (this.isStarted) return;
    window.addEventListener("message", this.handleWindowMessage);
    this.isStarted = true;
  }

  stop(): void {
    if (!this.isStarted) return;
    window.removeEventListener("message", this.handleWindowMessage);
    this.isStarted = false;
  }

  post(type: GodotHostMessageType, payload: Record<string, unknown>): boolean {
    const targetWindow = this.iframe.contentWindow;
    if (!targetWindow) return false;
    this.sequence += 1;
    const envelope = createGodotEnvelope(type, this.runId, this.sequence, payload);
    targetWindow.postMessage(JSON.stringify(envelope), this.expectedOrigin);
    return true;
  }

  private readonly handleWindowMessage = (event: MessageEvent<unknown>): void => {
    if (event.origin !== this.expectedOrigin || event.source !== this.iframe.contentWindow) {
      return;
    }
    const decoded = decodeGodotClientMessage(event.data);
    if (!decoded.ok) {
      this.onProtocolError(decoded.error);
      return;
    }
    if (decoded.envelope.run_id !== this.runId && decoded.envelope.type !== "ready") {
      this.onProtocolError("run_mismatch");
      return;
    }
    if (decoded.envelope.sequence <= this.lastClientSequence) return;
    this.lastClientSequence = decoded.envelope.sequence;
    this.onMessage(decoded.envelope);
  };
}
