export class AudioPlayer {
  private audioCtx: AudioContext | null = null;
  private chunks: Uint8Array[] = [];
  private source: AudioBufferSourceNode | null = null;

  private getCtx(): AudioContext {
    if (!this.audioCtx || this.audioCtx.state === "closed") {
      this.audioCtx = new AudioContext();
    }
    return this.audioCtx;
  }

  /** Call this on AUDIO_CHUNK events */
  onChunk(data: string, isFinal: boolean): void {
    const bytes = Uint8Array.from(atob(data), (c) => c.charCodeAt(0));
    this.chunks.push(bytes);

    if (isFinal) {
      this._playAssembled();
    }
  }

  private async _playAssembled(): Promise<void> {
    const total = this.chunks.reduce((sum, c) => sum + c.length, 0);
    const merged = new Uint8Array(total);
    let offset = 0;
    for (const chunk of this.chunks) {
      merged.set(chunk, offset);
      offset += chunk.length;
    }
    this.chunks = [];

    try {
      const ctx = this.getCtx();
      if (ctx.state === "suspended") await ctx.resume();
      const buffer = await ctx.decodeAudioData(merged.buffer);
      this.source = ctx.createBufferSource();
      this.source.buffer = buffer;
      this.source.connect(ctx.destination);
      this.source.start();
    } catch (err) {
      console.error("AudioPlayer: playback failed", err);
      this.chunks = [];
    }
  }

  /** Call this on INTERRUPT events */
  interrupt(): void {
    try {
      this.source?.stop();
    } catch (_) {}
    this.source = null;
    this.chunks = [];
  }

  dispose(): void {
    this.interrupt();
    this.audioCtx?.close();
    this.audioCtx = null;
  }
}
