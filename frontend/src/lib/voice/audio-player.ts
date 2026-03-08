export class AudioPlayer {
  private audioCtx: AudioContext | null = null;
  private chunks: Uint8Array[] = [];
  private source: AudioBufferSourceNode | null = null;
  private _playingPromise: Promise<void> | null = null;
  private _interrupted = false;

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

    if (isFinal && !this._interrupted) {
      // Serialize: wait for any existing play to finish before starting another
      this._playingPromise = (this._playingPromise ?? Promise.resolve()).then(() =>
        this._playAssembled()
      );
    }
  }

  private async _playAssembled(): Promise<void> {
    if (this._interrupted) {
      this.chunks = [];
      return;
    }

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

      if (this._interrupted) return;

      const buffer = await ctx.decodeAudioData(merged.buffer);

      if (this._interrupted) return;

      this.source = ctx.createBufferSource();
      this.source.buffer = buffer;
      this.source.connect(ctx.destination);
      this.source.start();
    } catch (err) {
      console.error("AudioPlayer: playback failed", err);
    }
  }

  /** Call this on INTERRUPT events */
  interrupt(): void {
    this._interrupted = true;
    this.chunks = [];
    try {
      this.source?.stop();
    } catch (_) {}
    this.source = null;
    // Reset flag after a tick so the next session can play audio
    setTimeout(() => { this._interrupted = false; }, 50);
  }

  dispose(): void {
    this._interrupted = true;
    this.chunks = [];
    try {
      this.source?.stop();
    } catch (_) {}
    this.source = null;
    this._playingPromise = null;
    this.audioCtx?.close();
    this.audioCtx = null;
  }
}
