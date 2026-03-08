declare global {
  interface Window {
    SpeechRecognition: new () => SpeechRecognition;
    webkitSpeechRecognition: new () => SpeechRecognition;
  }
}

type TranscriptCallback = (text: string) => void;
type VadCallback = (level: number) => void;

export class Microphone {
  private recognition: SpeechRecognition | null = null;
  private stream: MediaStream | null = null;
  private audioCtx: AudioContext | null = null;
  private analyser: AnalyserNode | null = null;
  private vadInterval: ReturnType<typeof setInterval> | null = null;
  private _stopped = false;

  async start(
    onTranscript: TranscriptCallback,
    onVadLevel: VadCallback,
  ): Promise<void> {
    this._stopped = false;

    // Microphone stream for VAD
    this.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    this.audioCtx = new AudioContext();
    const source = this.audioCtx.createMediaStreamSource(this.stream);
    this.analyser = this.audioCtx.createAnalyser();
    this.analyser.fftSize = 256;
    source.connect(this.analyser);

    const dataArray = new Uint8Array(this.analyser.frequencyBinCount);
    this.vadInterval = setInterval(() => {
      if (this._stopped || !this.analyser) return;
      this.analyser.getByteFrequencyData(dataArray);
      const avg = dataArray.reduce((a, b) => a + b, 0) / dataArray.length;
      onVadLevel(avg / 255);
    }, 100);

    // Web Speech API
    const SR =
      (window as any).SpeechRecognition ||
      (window as any).webkitSpeechRecognition;
    if (!SR) {
      console.warn("Web Speech API not supported in this browser");
      return;
    }

    this.recognition = new SR() as SpeechRecognition;
    this.recognition.lang = "en-US";
    this.recognition.continuous = true;
    this.recognition.interimResults = false;

    this.recognition.onresult = (event: SpeechRecognitionEvent) => {
      if (this._stopped) return;
      for (let i = event.resultIndex; i < event.results.length; i++) {
        if (event.results[i].isFinal) {
          const text = event.results[i][0].transcript.trim();
          if (text) onTranscript(text);
        }
      }
    };

    this.recognition.onerror = (e: SpeechRecognitionErrorEvent) => {
      if (this._stopped) return;
      if (e.error !== "aborted") {
        setTimeout(() => {
          if (!this._stopped) this.recognition?.start();
        }, 500);
      }
    };

    this.recognition.onend = () => {
      if (this._stopped) return;
      setTimeout(() => {
        if (!this._stopped) this.recognition?.start();
      }, 200);
    };

    this.recognition.start();
  }

  stop(): void {
    this._stopped = true;

    if (this.vadInterval) clearInterval(this.vadInterval);
    this.vadInterval = null;

    try { this.recognition?.stop(); } catch (_) {}
    this.recognition = null;

    this.stream?.getTracks().forEach((t) => t.stop());
    this.stream = null;

    this.audioCtx?.close();
    this.audioCtx = null;
    this.analyser = null;
  }
}
