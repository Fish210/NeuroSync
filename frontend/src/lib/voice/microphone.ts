declare global {
  interface SpeechRecognitionEvent extends Event {
    readonly resultIndex: number;
    readonly results: SpeechRecognitionResultList;
  }
  interface SpeechRecognitionErrorEvent extends Event {
    readonly error: string;
    readonly message: string;
  }
  interface SpeechRecognition extends EventTarget {
    lang: string;
    continuous: boolean;
    interimResults: boolean;
    onresult: ((event: SpeechRecognitionEvent) => void) | null;
    onerror: ((event: SpeechRecognitionErrorEvent) => void) | null;
    onend: (() => void) | null;
    start(): void;
    stop(): void;
    abort(): void;
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

  async start(
    onTranscript: TranscriptCallback,
    onVadLevel: VadCallback,
  ): Promise<void> {
    // Microphone stream for VAD
    this.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    this.audioCtx = new AudioContext();
    const source = this.audioCtx.createMediaStreamSource(this.stream);
    this.analyser = this.audioCtx.createAnalyser();
    this.analyser.fftSize = 256;
    source.connect(this.analyser);

    const dataArray = new Uint8Array(this.analyser.frequencyBinCount);
    this.vadInterval = setInterval(() => {
      this.analyser!.getByteFrequencyData(dataArray);
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
      for (let i = event.resultIndex; i < event.results.length; i++) {
        if (event.results[i].isFinal) {
          const text = event.results[i][0].transcript.trim();
          if (text) onTranscript(text);
        }
      }
    };

    this.recognition.onerror = (e: SpeechRecognitionErrorEvent) => {
      if (e.error !== "aborted") {
        setTimeout(() => this.recognition?.start(), 500);
      }
    };

    this.recognition.onend = () => {
      if (this.stream) {
        setTimeout(() => this.recognition?.start(), 200);
      }
    };

    this.recognition.start();
  }

  stop(): void {
    if (this.vadInterval) clearInterval(this.vadInterval);
    this.vadInterval = null;
    this.recognition?.stop();
    this.recognition = null;
    this.stream?.getTracks().forEach((t) => t.stop());
    this.stream = null;
    this.audioCtx?.close();
    this.audioCtx = null;
    this.analyser = null;
  }
}
