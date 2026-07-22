// Client-side audio capture + WAV encoding.
//
// The backend expects 16 kHz mono WAV (what librosa/soundfile read reliably
// without ffmpeg). Browsers record webm/ogg-opus, so we decode whatever the
// MediaRecorder produced with the Web Audio API, resample to 16 kHz mono via
// an OfflineAudioContext, and hand-encode a little PCM16 WAV.

export const TARGET_SAMPLE_RATE = 16000;

export class Recorder {
  constructor() {
    this.mediaRecorder = null;
    this.chunks = [];
    this.stream = null;
  }

  async start() {
    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
    });
    this.chunks = [];
    this.mediaRecorder = new MediaRecorder(this.stream);
    this.mediaRecorder.ondataavailable = (e) => {
      if (e.data && e.data.size > 0) this.chunks.push(e.data);
    };
    this.mediaRecorder.start();
  }

  /** Stops recording and resolves to a Blob of the raw recorded audio. */
  stop() {
    return new Promise((resolve) => {
      if (!this.mediaRecorder) return resolve(null);
      this.mediaRecorder.onstop = () => {
        const blob = new Blob(this.chunks, {
          type: this.mediaRecorder.mimeType || "audio/webm",
        });
        this._cleanup();
        resolve(blob);
      };
      this.mediaRecorder.stop();
    });
  }

  _cleanup() {
    if (this.stream) this.stream.getTracks().forEach((t) => t.stop());
    this.stream = null;
    this.mediaRecorder = null;
  }
}

/** Decode any audio Blob/File to a mono 16 kHz Float32Array. */
export async function toMono16k(blob) {
  const arrayBuf = await blob.arrayBuffer();
  const AudioCtx = window.AudioContext || window.webkitAudioContext;
  const decodeCtx = new AudioCtx();
  const decoded = await decodeCtx.decodeAudioData(arrayBuf);
  decodeCtx.close?.();

  const durationSec = decoded.length / decoded.sampleRate;
  const frames = Math.max(1, Math.ceil(durationSec * TARGET_SAMPLE_RATE));
  const offline = new OfflineAudioContext(1, frames, TARGET_SAMPLE_RATE);
  const src = offline.createBufferSource();
  src.buffer = decoded;
  src.connect(offline.destination);
  src.start();
  const rendered = await offline.startRendering();
  return rendered.getChannelData(0);
}

/** Encode a Float32Array of mono samples as a 16-bit PCM WAV Blob. */
export function encodeWav(samples, sampleRate = TARGET_SAMPLE_RATE) {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);
  const writeStr = (offset, str) => {
    for (let i = 0; i < str.length; i++) view.setUint8(offset + i, str.charCodeAt(i));
  };

  writeStr(0, "RIFF");
  view.setUint32(4, 36 + samples.length * 2, true);
  writeStr(8, "WAVE");
  writeStr(12, "fmt ");
  view.setUint32(16, 16, true); // PCM chunk size
  view.setUint16(20, 1, true); // audio format = PCM
  view.setUint16(22, 1, true); // channels
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true); // byte rate
  view.setUint16(32, 2, true); // block align
  view.setUint16(34, 16, true); // bits per sample
  writeStr(36, "data");
  view.setUint32(40, samples.length * 2, true);

  let offset = 44;
  for (let i = 0; i < samples.length; i++) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true);
    offset += 2;
  }
  return new Blob([view], { type: "audio/wav" });
}

/** Full path: any recorded/uploaded audio Blob -> 16 kHz mono WAV Blob. */
export async function toWav16k(blob) {
  const mono = await toMono16k(blob);
  return encodeWav(mono, TARGET_SAMPLE_RATE);
}
