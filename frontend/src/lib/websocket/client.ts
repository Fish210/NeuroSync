import type { WebSocketMessage } from "@/lib/types";

type MessageHandler = (message: WebSocketMessage) => void;
type StatusHandler = (status: "connecting" | "open" | "closed" | "error") => void;

export class WSClient {
  private socket: WebSocket | null = null;
  private url: string;
  private onMessage: MessageHandler;
  private onStatus?: StatusHandler;

  constructor(url: string, onMessage: MessageHandler, onStatus?: StatusHandler) {
    this.url = url;
    this.onMessage = onMessage;
    this.onStatus = onStatus;
  }

  connect() {
    this.onStatus?.("connecting");
    this.socket = new WebSocket(this.url);

    this.socket.onopen = () => this.onStatus?.("open");
    this.socket.onerror = () => this.onStatus?.("error");
    this.socket.onclose = () => this.onStatus?.("closed");

    this.socket.onmessage = (event) => {
      try {
        const parsed = JSON.parse(event.data) as WebSocketMessage;
        this.onMessage(parsed);
      } catch (err) {
        console.error("Bad WS message:", err);
      }
    };
  }

  disconnect() {
    this.socket?.close();
    this.socket = null;
  }

  send(data: unknown) {
    if (this.socket?.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify(data));
    }
  }
}