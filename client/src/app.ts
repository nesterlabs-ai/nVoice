/**
 * Nester AI - Voice Intelligence Scanner
 *
 * A sci-fi themed voice assistant with scanner interface and emotion visualization.
 * States: idle | listening | thinking | speaking
 *
 * Features:
 * - Scanner frame with animated scan line
 * - Circular audio visualizer
 * - Waveform visualization
 * - Emotion metrics panel
 * - Terminal system messages
 * - Floating particles
 */

import {
  RTVIClient,
  RTVIClientOptions,
  RTVIEvent,
} from '@pipecat-ai/client-js';
import {
  WebSocketTransport
} from "@pipecat-ai/websocket-transport";

type VoiceState = 'idle' | 'listening' | 'thinking' | 'speaking';

class VoiceScannerApp {
  private rtviClient: RTVIClient | null = null;

  // UI Elements
  private scannerFrame: HTMLElement | null = null;
  private orbContainer: HTMLElement | null = null;
  private orbStatus: HTMLElement | null = null;
  private welcomeMessage: HTMLElement | null = null;
  private transcriptList: HTMLElement | null = null;
  private transcriptStatus: HTMLElement | null = null;
  private debugPanel: HTMLElement | null = null;
  private debugLog: HTMLElement | null = null;
  private debugToggle: HTMLElement | null = null;
  private debugClose: HTMLElement | null = null;
  private emotionPanel: HTMLElement | null = null;
  private emotionToggle: HTMLElement | null = null;
  private emotionLabel: HTMLElement | null = null;
  private emotionEmoji: HTMLElement | null = null;
  private emotionConfidence: HTMLElement | null = null;
  private toneLabel: HTMLElement | null = null;
  private arousalBar: HTMLElement | null = null;
  private arousalValue: HTMLElement | null = null;
  private dominanceValue: HTMLElement | null = null;
  private valenceValue: HTMLElement | null = null;
  private emotionTimeline: HTMLElement | null = null;
  private statusIndicator: HTMLElement | null = null;
  private loadingOverlay: HTMLElement | null = null;
  private terminalContent: HTMLElement | null = null;
  private terminalStatus: HTMLElement | null = null;
  private typingLine: HTMLElement | null = null;
  private timestampElement: HTMLElement | null = null;
  private notification: HTMLElement | null = null;

  // Canvas elements
  private waveformCanvas: HTMLCanvasElement | null = null;
  private circularCanvas: HTMLCanvasElement | null = null;
  private preloaderCanvas: HTMLCanvasElement | null = null;
  private waveformCtx: CanvasRenderingContext2D | null = null;
  private circularCtx: CanvasRenderingContext2D | null = null;
  private preloaderCtx: CanvasRenderingContext2D | null = null;

  // Audio analysis
  private audioContext: AudioContext | null = null;
  private analyser: AnalyserNode | null = null;
  private dataArray: Uint8Array | null = null;
  private animationFrame: number | null = null;

  // Audio
  private botAudio: HTMLAudioElement;

  // State
  private voiceState: VoiceState = 'idle';
  private isConnected: boolean = false;
  private isConnecting: boolean = false;
  private preloaderAngle: number = 0;

  constructor() {
    console.log("Nester AI Voice Scanner initializing...");

    this.botAudio = document.createElement('audio');
    this.botAudio.autoplay = true;
    document.body.appendChild(this.botAudio);

    this.setupDOMElements();
    this.setupEventListeners();
    this.initializeCanvases();
    this.startTimestampUpdate();
    this.createFloatingParticles();
    this.showLoadingOverlay();
    this.setVoiceState('idle');

    // Hide loading after initialization
    setTimeout(() => this.hideLoadingOverlay(), 2500);
  }

  private setupDOMElements(): void {
    this.scannerFrame = document.getElementById('scanner-frame');
    this.orbContainer = document.getElementById('voice-orb-container');
    this.orbStatus = document.getElementById('orb-status');
    this.welcomeMessage = document.getElementById('welcome-message');
    this.transcriptList = document.getElementById('transcript-list');
    this.transcriptStatus = document.getElementById('transcript-status');
    this.debugPanel = document.getElementById('debug-panel');
    this.debugLog = document.getElementById('debug-log');
    this.debugToggle = document.getElementById('debug-toggle');
    this.debugClose = document.getElementById('debug-close');
    this.emotionPanel = document.getElementById('emotion-panel');
    this.emotionToggle = document.getElementById('emotion-toggle');
    this.emotionLabel = document.getElementById('emotion-label');
    this.emotionEmoji = document.getElementById('emotion-emoji');
    this.emotionConfidence = document.getElementById('emotion-confidence');
    this.toneLabel = document.getElementById('tone-label');
    this.arousalBar = document.getElementById('arousal-bar');
    this.arousalValue = document.getElementById('arousal-value');
    this.dominanceValue = document.getElementById('dominance-value');
    this.valenceValue = document.getElementById('valence-value');
    this.emotionTimeline = document.getElementById('emotion-timeline');
    this.statusIndicator = document.getElementById('status-indicator');
    this.loadingOverlay = document.getElementById('loading-overlay');
    this.terminalContent = document.getElementById('terminal-content');
    this.terminalStatus = document.getElementById('terminal-status');
    this.typingLine = document.getElementById('typing-line');
    this.timestampElement = document.getElementById('timestamp');
    this.notification = document.getElementById('notification');

    // Canvas elements
    this.waveformCanvas = document.getElementById('waveform-canvas') as HTMLCanvasElement;
    this.circularCanvas = document.getElementById('circular-canvas') as HTMLCanvasElement;
    this.preloaderCanvas = document.getElementById('preloader-canvas') as HTMLCanvasElement;
  }

  private setupEventListeners(): void {
    // Scanner frame click handler (whole frame is clickable)
    this.scannerFrame?.addEventListener('click', () => this.handleOrbClick());

    // Debug panel
    this.debugToggle?.addEventListener('click', () => this.toggleDebugPanel());
    this.debugClose?.addEventListener('click', () => this.hideDebugPanel());

    // Emotion panel toggle
    this.emotionToggle?.addEventListener('click', () => this.toggleEmotionPanel());
  }

  /**
   * Initialize canvas elements for visualizations
   */
  private initializeCanvases(): void {
    // Waveform canvas
    if (this.waveformCanvas) {
      this.waveformCanvas.width = this.waveformCanvas.offsetWidth * 2;
      this.waveformCanvas.height = this.waveformCanvas.offsetHeight * 2;
      this.waveformCtx = this.waveformCanvas.getContext('2d');
      this.drawIdleWaveform();
    }

    // Circular visualizer canvas
    if (this.circularCanvas) {
      const container = this.circularCanvas.parentElement;
      if (container) {
        this.circularCanvas.width = container.offsetWidth;
        this.circularCanvas.height = container.offsetHeight;
      }
      this.circularCtx = this.circularCanvas.getContext('2d');
    }

    // Preloader canvas
    if (this.preloaderCanvas) {
      this.preloaderCtx = this.preloaderCanvas.getContext('2d');
      this.animatePreloader();
    }
  }

  /**
   * Draw idle waveform (flat line with subtle noise)
   */
  private drawIdleWaveform(): void {
    if (!this.waveformCtx || !this.waveformCanvas) return;

    const ctx = this.waveformCtx;
    const width = this.waveformCanvas.width;
    const height = this.waveformCanvas.height;
    const centerY = height / 2;

    ctx.clearRect(0, 0, width, height);

    // Draw center line with gradient
    const gradient = ctx.createLinearGradient(0, 0, width, 0);
    gradient.addColorStop(0, 'rgba(55, 182, 255, 0.3)');
    gradient.addColorStop(0.5, 'rgba(55, 182, 255, 0.8)');
    gradient.addColorStop(1, 'rgba(55, 182, 255, 0.3)');

    ctx.strokeStyle = gradient;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(0, centerY);

    // Subtle idle movement
    for (let x = 0; x < width; x += 4) {
      const noise = Math.sin(x * 0.02 + Date.now() * 0.002) * 3;
      ctx.lineTo(x, centerY + noise);
    }

    ctx.stroke();
  }

  /**
   * Animate preloader spinner
   */
  private animatePreloader(): void {
    if (!this.preloaderCtx || !this.preloaderCanvas) return;

    const ctx = this.preloaderCtx;
    const width = this.preloaderCanvas.width;
    const height = this.preloaderCanvas.height;
    const centerX = width / 2;
    const centerY = height / 2;
    const radius = Math.min(width, height) / 2 - 15;

    const animate = () => {
      ctx.clearRect(0, 0, width, height);

      // Draw arc segments
      const segments = 12;
      for (let i = 0; i < segments; i++) {
        const angle = (i / segments) * Math.PI * 2 + this.preloaderAngle;
        const alpha = 0.2 + (i / segments) * 0.8;

        ctx.strokeStyle = `rgba(55, 182, 255, ${alpha})`;
        ctx.lineWidth = 3;
        ctx.lineCap = 'round';
        ctx.beginPath();
        ctx.arc(centerX, centerY, radius, angle, angle + 0.3);
        ctx.stroke();
      }

      this.preloaderAngle += 0.05;

      if (this.loadingOverlay && !this.loadingOverlay.classList.contains('hidden')) {
        requestAnimationFrame(animate);
      }
    };

    animate();
  }

  /**
   * Show loading overlay
   */
  private showLoadingOverlay(): void {
    if (this.loadingOverlay) {
      this.loadingOverlay.classList.remove('hidden');
      this.animatePreloader();
    }
  }

  /**
   * Hide loading overlay
   */
  private hideLoadingOverlay(): void {
    if (this.loadingOverlay) {
      this.loadingOverlay.classList.add('hidden');
      this.addTerminalMessage('Voice scanner ready. Awaiting user input.', 'regular');
    }
  }

  /**
   * Start timestamp update
   */
  private startTimestampUpdate(): void {
    const updateTime = () => {
      if (this.timestampElement) {
        const now = new Date();
        const timeStr = now.toLocaleTimeString('en-US', { hour12: false });
        this.timestampElement.textContent = `TIME: ${timeStr}`;
      }
    };

    updateTime();
    setInterval(updateTime, 1000);
  }

  /**
   * Create floating particles
   */
  private createFloatingParticles(): void {
    const container = document.getElementById('floating-particles');
    if (!container) return;

    const particleCount = 30;

    for (let i = 0; i < particleCount; i++) {
      const particle = document.createElement('div');
      particle.className = 'particle';
      particle.style.cssText = `
        position: absolute;
        width: ${2 + Math.random() * 4}px;
        height: ${2 + Math.random() * 4}px;
        background: rgba(55, 182, 255, ${0.2 + Math.random() * 0.4});
        border-radius: 50%;
        left: ${Math.random() * 100}%;
        top: ${Math.random() * 100}%;
        animation: floatParticle ${10 + Math.random() * 20}s linear infinite;
        animation-delay: ${-Math.random() * 20}s;
      `;
      container.appendChild(particle);
    }
  }

  /**
   * Add message to terminal
   */
  private addTerminalMessage(message: string, type: 'command' | 'regular' | 'error' | 'success' = 'regular'): void {
    if (!this.terminalContent || !this.typingLine) return;

    const line = document.createElement('div');
    line.className = `terminal-line ${type}-line`;

    if (type === 'command') {
      line.textContent = `> ${message}`;
    } else if (type === 'error') {
      line.innerHTML = `<span style="color: #ef4444;">[ERROR]</span> ${message}`;
    } else if (type === 'success') {
      line.innerHTML = `<span style="color: #4ade80;">[OK]</span> ${message}`;
    } else {
      line.textContent = message;
    }

    // Insert before the typing line
    this.terminalContent.insertBefore(line, this.typingLine);

    // Keep only last 20 lines
    const lines = this.terminalContent.querySelectorAll('.terminal-line:not(.typing)');
    if (lines.length > 20) {
      lines[0].remove();
    }

    // Scroll to bottom
    this.terminalContent.scrollTop = this.terminalContent.scrollHeight;
  }

  /**
   * Show notification banner
   */
  private showNotification(message: string): void {
    if (!this.notification) return;

    this.notification.textContent = message;
    this.notification.classList.add('visible');

    setTimeout(() => {
      this.notification?.classList.remove('visible');
    }, 3000);
  }

  /**
   * Handle orb click - connect or disconnect
   */
  private async handleOrbClick(): Promise<void> {
    if (this.isConnecting) return;

    if (this.isConnected) {
      await this.disconnect();
    } else {
      await this.connect();
    }
  }

  /**
   * Set voice state and update UI
   */
  private setVoiceState(state: VoiceState): void {
    this.voiceState = state;

    if (!this.scannerFrame || !this.orbContainer || !this.orbStatus) return;

    // Remove all state classes from scanner frame
    this.scannerFrame.classList.remove('idle', 'listening', 'thinking', 'speaking', 'connected');
    this.orbContainer.classList.remove('idle', 'listening', 'thinking', 'speaking', 'connected');

    // Add current state
    this.scannerFrame.classList.add(state);
    this.orbContainer.classList.add(state);

    // Add connected class if connected
    if (this.isConnected) {
      this.scannerFrame.classList.add('connected');
      this.orbContainer.classList.add('connected');
    }

    // Update status text (sci-fi style)
    const statusTexts: Record<VoiceState, string> = {
      'idle': this.isConnected ? 'TAP TO TERMINATE' : 'TAP TO INITIALIZE',
      'listening': 'SCANNING VOICE INPUT...',
      'thinking': 'PROCESSING SIGNAL...',
      'speaking': 'TRANSMITTING RESPONSE...'
    };

    this.orbStatus.textContent = statusTexts[state];

    // Update status indicator
    if (this.statusIndicator) {
      this.statusIndicator.className = this.isConnected ? 'live-dot active' : 'live-dot';
    }

    // Update transcript status
    if (this.transcriptStatus) {
      this.transcriptStatus.textContent = this.isConnected ? 'ACTIVE' : 'READY';
    }

    // Update terminal status
    if (this.terminalStatus) {
      this.terminalStatus.textContent = this.isConnected ? 'CONNECTED' : 'ONLINE';
    }

    // Update signal status
    const signalStatus = document.getElementById('signal-status');
    if (signalStatus) {
      const signalTexts: Record<VoiceState, string> = {
        'idle': 'STANDBY',
        'listening': 'RECEIVING',
        'thinking': 'PROCESSING',
        'speaking': 'TRANSMITTING'
      };
      signalStatus.textContent = signalTexts[state];
    }
  }

  /**
   * Log message to debug panel
   */
  private log(message: string): void {
    if (!this.debugLog) return;

    const entry = document.createElement('div');
    const time = new Date().toLocaleTimeString('en-US', { hour12: false });
    entry.textContent = `[${time}] ${message}`;

    // Color coding
    if (message.startsWith('You:')) {
      entry.style.color = '#37b6ff';
    } else if (message.startsWith('Bot:')) {
      entry.style.color = '#9747ff';
    } else if (message.includes('Error')) {
      entry.style.color = '#ef4444';
    } else if (message.includes('Connected')) {
      entry.style.color = '#4ade80';
    }

    this.debugLog.appendChild(entry);
    this.debugLog.scrollTop = this.debugLog.scrollHeight;
    console.log(message);
  }

  /**
   * Add transcript bubble to conversation
   */
  private addTranscript(text: string, isUser: boolean): void {
    if (!this.transcriptList) return;

    // Hide welcome message
    this.welcomeMessage?.classList.add('hidden');

    const bubble = document.createElement('div');
    bubble.className = `transcript-bubble ${isUser ? 'user' : 'bot'}`;

    // Add label
    const label = document.createElement('span');
    label.className = 'transcript-label';
    label.textContent = isUser ? 'USER' : 'NESTER';

    // Add text
    const textSpan = document.createElement('span');
    textSpan.className = 'transcript-text';
    textSpan.textContent = text;

    bubble.appendChild(label);
    bubble.appendChild(textSpan);

    this.transcriptList.appendChild(bubble);

    // Scroll to bottom
    this.transcriptList.scrollTop = this.transcriptList.scrollHeight;
  }

  /**
   * Toggle debug panel
   */
  private toggleDebugPanel(): void {
    this.debugPanel?.classList.toggle('visible');
  }

  /**
   * Hide debug panel
   */
  private hideDebugPanel(): void {
    this.debugPanel?.classList.remove('visible');
  }

  /**
   * Toggle emotion panel visibility
   */
  private toggleEmotionPanel(): void {
    this.emotionPanel?.classList.toggle('visible');
  }

  /**
   * Update emotion display with detected emotion data
   */
  private updateEmotionDisplay(data: {
    arousal: number;
    dominance: number;
    valence: number;
    emotion: string;
    tone: string;
    confidence: number;
    timestamp: number;
  }): void {
    // Update emotion label and emoji
    const emotionEmojis: Record<string, string> = {
      'neutral': '😊',
      'happy': '😄',
      'excited': '🤩',
      'sad': '😢',
      'angry': '😠',
      'frustrated': '😤',
      'fear': '😨',
      'worried': '😟',
      'calm': '😌',
      'content': '😊',
    };

    const emoji = emotionEmojis[data.emotion] || '😊';
    const emotionName = data.emotion.toUpperCase();

    if (this.emotionEmoji) this.emotionEmoji.textContent = emoji;
    if (this.emotionLabel) this.emotionLabel.textContent = emotionName;
    if (this.emotionConfidence) {
      this.emotionConfidence.textContent = `${Math.round(data.confidence * 100)}%`;
    }

    // Update dimensional values
    if (this.arousalBar && this.arousalValue) {
      this.arousalBar.style.width = `${data.arousal * 100}%`;
      this.arousalValue.textContent = data.arousal.toFixed(2);
    }
    if (this.dominanceValue) {
      this.dominanceValue.textContent = data.dominance.toFixed(2);
    }
    if (this.valenceValue) {
      this.valenceValue.textContent = data.valence.toFixed(2);
    }

    // Add to emotion timeline
    this.addEmotionToTimeline(data.emotion, emoji);

    // Add terminal message
    this.addTerminalMessage(`emotion.detect({type: '${data.emotion}', conf: ${(data.confidence * 100).toFixed(0)}%});`, 'command');

    this.log(`Emotion detected: ${emotionName} (${Math.round(data.confidence * 100)}%)`);
  }

  /**
   * Update tone display when voice tone is switched
   */
  private updateToneDisplay(tone: string): void {
    const toneDisplayNames: Record<string, string> = {
      'neutral': 'NEUTRAL',
      'excited': 'ENERGETIC',
      'sad': 'EMPATHETIC',
      'frustrated': 'CALM',
      'happy': 'WARM',
      'angry': 'CONTROLLED',
      'fear': 'GENTLE',
      'content': 'RELAXED',
    };

    const displayName = toneDisplayNames[tone] || 'NEUTRAL';

    if (this.toneLabel) {
      this.toneLabel.textContent = displayName;
    }

    this.addTerminalMessage(`voice.tone.switch('${tone}');`, 'command');
    this.log(`Voice tone switched to: ${displayName}`);
  }

  /**
   * Add emotion dot to timeline
   */
  private addEmotionToTimeline(emotion: string, _emoji?: string): void {
    if (!this.emotionTimeline) return;

    const emotionColors: Record<string, string> = {
      'neutral': '#6b7280',
      'happy': '#10b981',
      'excited': '#8b5cf6',
      'sad': '#3b82f6',
      'angry': '#ef4444',
      'frustrated': '#f59e0b',
      'fear': '#ec4899',
      'worried': '#f59e0b',
      'calm': '#10b981',
      'content': '#10b981',
    };

    const dot = document.createElement('div');
    dot.className = 'timeline-dot';
    dot.style.backgroundColor = emotionColors[emotion] || '#6b7280';
    dot.title = `${emotion.charAt(0).toUpperCase() + emotion.slice(1)}`;

    // Keep only last 15 emotions
    if (this.emotionTimeline.children.length >= 15) {
      this.emotionTimeline.removeChild(this.emotionTimeline.firstChild!);
    }

    this.emotionTimeline.appendChild(dot);

    // Animate dot entrance
    setTimeout(() => dot.classList.add('visible'), 10);
  }

  /**
   * Start audio visualization
   */
  private startAudioVisualization(): void {
    if (!this.analyser || !this.dataArray) return;

    const visualize = () => {
      if (!this.isConnected) return;

      this.analyser!.getByteFrequencyData(this.dataArray! as Uint8Array<ArrayBuffer>);

      // Draw waveform
      this.drawWaveform();

      // Draw circular visualizer
      this.drawCircularVisualizer();

      // Update peak frequency
      this.updatePeakFrequency();

      this.animationFrame = requestAnimationFrame(visualize);
    };

    visualize();
  }

  /**
   * Draw audio waveform
   */
  private drawWaveform(): void {
    if (!this.waveformCtx || !this.waveformCanvas || !this.dataArray) return;

    const ctx = this.waveformCtx;
    const width = this.waveformCanvas.width;
    const height = this.waveformCanvas.height;
    const centerY = height / 2;

    ctx.clearRect(0, 0, width, height);

    // Create gradient
    const gradient = ctx.createLinearGradient(0, 0, width, 0);
    gradient.addColorStop(0, 'rgba(55, 182, 255, 0.3)');
    gradient.addColorStop(0.3, 'rgba(55, 182, 255, 0.8)');
    gradient.addColorStop(0.5, 'rgba(151, 71, 255, 0.9)');
    gradient.addColorStop(0.7, 'rgba(55, 182, 255, 0.8)');
    gradient.addColorStop(1, 'rgba(55, 182, 255, 0.3)');

    ctx.strokeStyle = gradient;
    ctx.lineWidth = 2;
    ctx.beginPath();

    const sliceWidth = width / this.dataArray.length;
    let x = 0;

    for (let i = 0; i < this.dataArray.length; i++) {
      const v = this.dataArray[i] / 128.0;
      const y = centerY + (v - 1) * (height / 3);

      if (i === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }

      x += sliceWidth;
    }

    ctx.stroke();

    // Draw glow effect
    ctx.strokeStyle = 'rgba(55, 182, 255, 0.3)';
    ctx.lineWidth = 6;
    ctx.stroke();
  }

  /**
   * Draw circular audio visualizer
   */
  private drawCircularVisualizer(): void {
    if (!this.circularCtx || !this.circularCanvas || !this.dataArray) return;

    const ctx = this.circularCtx;
    const width = this.circularCanvas.width;
    const height = this.circularCanvas.height;
    const centerX = width / 2;
    const centerY = height / 2;
    const radius = Math.min(width, height) / 2 - 50;

    ctx.clearRect(0, 0, width, height);

    const bars = 64;
    const barWidth = (Math.PI * 2) / bars;

    for (let i = 0; i < bars; i++) {
      const dataIndex = Math.floor(i * (this.dataArray.length / bars));
      const value = this.dataArray[dataIndex] / 255;
      const barHeight = value * 40 + 5;

      const angle = i * barWidth - Math.PI / 2;
      const x1 = centerX + Math.cos(angle) * radius;
      const y1 = centerY + Math.sin(angle) * radius;
      const x2 = centerX + Math.cos(angle) * (radius + barHeight);
      const y2 = centerY + Math.sin(angle) * (radius + barHeight);

      ctx.strokeStyle = `rgba(55, 182, 255, ${0.3 + value * 0.7})`;
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(x1, y1);
      ctx.lineTo(x2, y2);
      ctx.stroke();
    }
  }

  /**
   * Update peak frequency display
   */
  private updatePeakFrequency(): void {
    if (!this.dataArray) return;

    let maxVal = 0;
    let maxIndex = 0;

    for (let i = 0; i < this.dataArray.length; i++) {
      if (this.dataArray[i] > maxVal) {
        maxVal = this.dataArray[i];
        maxIndex = i;
      }
    }

    // Approximate frequency (assuming 44100 sample rate)
    const frequency = Math.round((maxIndex * 44100) / (this.dataArray.length * 2));

    const peakValue = document.getElementById('peak-value');
    if (peakValue && maxVal > 10) {
      peakValue.textContent = `${frequency} HZ`;
    }

    // Update amplitude
    const amplitudeValue = document.getElementById('amplitude-value');
    if (amplitudeValue) {
      const amplitude = (maxVal / 255).toFixed(2);
      amplitudeValue.textContent = amplitude;
    }
  }

  /**
   * Stop audio visualization
   */
  private stopAudioVisualization(): void {
    if (this.animationFrame) {
      cancelAnimationFrame(this.animationFrame);
      this.animationFrame = null;
    }

    // Reset displays
    this.drawIdleWaveform();

    if (this.circularCtx && this.circularCanvas) {
      this.circularCtx.clearRect(0, 0, this.circularCanvas.width, this.circularCanvas.height);
    }

    const peakValue = document.getElementById('peak-value');
    if (peakValue) peakValue.textContent = '-- HZ';

    const amplitudeValue = document.getElementById('amplitude-value');
    if (amplitudeValue) amplitudeValue.textContent = '0.00';
  }

  /**
   * Set up audio track with visualization
   */
  private setupAudioTrack(track: MediaStreamTrack): void {
    this.log('Audio track connected');

    if (this.botAudio.srcObject && "getAudioTracks" in this.botAudio.srcObject) {
      const oldTrack = this.botAudio.srcObject.getAudioTracks()[0];
      if (oldTrack?.id === track.id) return;
    }

    const stream = new MediaStream([track]);
    this.botAudio.srcObject = stream;

    // Set up audio analysis for visualization
    try {
      this.audioContext = new AudioContext();
      const source = this.audioContext.createMediaStreamSource(stream);
      this.analyser = this.audioContext.createAnalyser();
      this.analyser.fftSize = 256;
      source.connect(this.analyser);
      this.dataArray = new Uint8Array(this.analyser.frequencyBinCount);

      this.startAudioVisualization();
    } catch (e) {
      console.warn('Could not set up audio visualization:', e);
    }
  }

  /**
   * Set up media tracks
   */
  private setupMediaTracks(): void {
    if (!this.rtviClient) return;
    const tracks = this.rtviClient.tracks();
    if (tracks.bot?.audio) {
      this.setupAudioTrack(tracks.bot.audio);
    }
  }

  /**
   * Set up event listeners for RTVI
   */
  private setupTrackListeners(): void {
    if (!this.rtviClient) return;

    // Track events
    this.rtviClient.on(RTVIEvent.TrackStarted, (track, participant) => {
      if (!participant?.local && track.kind === 'audio') {
        this.setupAudioTrack(track);
      }
    });

    // Bot speech events
    this.rtviClient.on(RTVIEvent.BotStartedSpeaking, () => {
      this.log('Bot started speaking');
      this.setVoiceState('speaking');
    });

    this.rtviClient.on(RTVIEvent.BotStoppedSpeaking, () => {
      this.log('Bot stopped speaking');
      if (this.isConnected) {
        this.setVoiceState('listening');
      }
    });

    // User speech events
    this.rtviClient.on(RTVIEvent.UserStartedSpeaking, () => {
      this.log('User started speaking');
      this.setVoiceState('listening');
      this.showNotification('VOICE DETECTED');
    });

    this.rtviClient.on(RTVIEvent.UserStoppedSpeaking, () => {
      this.log('User stopped speaking');
      this.setVoiceState('thinking');
    });
  }

  /**
   * Get backend URL
   */
  private getBackendUrl(): string {
    // @ts-ignore
    if (typeof import.meta !== 'undefined' && import.meta.env?.VITE_BACKEND_URL) {
      // @ts-ignore
      return import.meta.env.VITE_BACKEND_URL;
    }
    if ((window as any).__BACKEND_URL__) {
      return (window as any).__BACKEND_URL__;
    }
    return 'http://localhost:7860';
  }

  /**
   * Connect to voice server
   */
  public async connect(): Promise<void> {
    if (this.isConnecting || this.isConnected) return;

    this.isConnecting = true;
    this.setVoiceState('thinking');

    this.addTerminalMessage('voice.scanner.connect();', 'command');
    this.addTerminalMessage('Establishing secure connection...', 'regular');

    try {
      const backendUrl = this.getBackendUrl();
      this.log(`Connecting to ${backendUrl}...`);

      const transport = new WebSocketTransport();
      const config: RTVIClientOptions = {
        transport,
        params: {
          baseUrl: backendUrl,
          endpoints: { connect: '/connect' },
        },
        enableMic: true,
        enableCam: false,
        callbacks: {
          onConnected: () => {
            this.isConnecting = false;
            this.isConnected = true;
            this.log('Connected successfully!');
            this.setVoiceState('listening');
            this.addTerminalMessage('Connection established. Voice scanner active.', 'success');
            this.showNotification('CONNECTION ESTABLISHED');
          },
          onDisconnected: () => {
            this.isConnecting = false;
            this.isConnected = false;
            this.rtviClient = null;
            this.log('Disconnected');
            this.setVoiceState('idle');
            this.stopAudioVisualization();
            this.addTerminalMessage('Connection terminated.', 'regular');
          },
          onBotReady: () => {
            this.log(`Bot ready`);
            this.setupMediaTracks();
            this.addTerminalMessage('Voice AI initialized and ready.', 'success');
          },
          onUserTranscript: (data) => {
            if (data.final) {
              this.log(`You: ${data.text}`);
              this.addTranscript(data.text, true);
            }
          },
          onBotTranscript: (data) => {
            this.log(`Bot: ${data.text}`);
            this.addTranscript(data.text, false);
          },
          onError: (error) => {
            this.log(`Error: ${error}`);
            this.addTerminalMessage(`${error}`, 'error');
            console.error('RTVI Error:', error);
          },
          onServerMessage: (message) => {
            console.log('[Emotion] Server message received:', JSON.stringify(message, null, 2));

            try {
              let emotionData = null;
              let messageType = null;

              if (message && message.data) {
                messageType = message.data.message_type;
                emotionData = message.data;
              } else if (message && message.message_type) {
                messageType = message.message_type;
                emotionData = message;
              } else if (message && message.type === 'server-message' && message.data) {
                messageType = message.data.message_type;
                emotionData = message.data;
              }

              console.log('[Emotion] Parsed message type:', messageType, 'data:', emotionData);

              if (messageType === 'emotion_detected' && emotionData) {
                console.log('[Emotion] Updating emotion display:', emotionData);
                this.updateEmotionDisplay(emotionData);
              } else if (messageType === 'tone_switched' && emotionData) {
                console.log('[Emotion] Updating tone display:', emotionData.new_tone);
                this.updateToneDisplay(emotionData.new_tone);
              }
            } catch (e) {
              console.error('[Emotion] Error handling server message:', e);
            }
          },
        },
      };

      this.rtviClient = new RTVIClient(config);
      this.setupTrackListeners();

      await this.rtviClient.initDevices();
      await this.rtviClient.connect();

    } catch (error) {
      this.isConnecting = false;
      this.log(`Connection failed: ${(error as Error).message}`);
      this.addTerminalMessage(`Connection failed: ${(error as Error).message}`, 'error');
      this.setVoiceState('idle');

      if (this.rtviClient) {
        try {
          await this.rtviClient.disconnect();
        } catch (e) {}
        this.rtviClient = null;
      }
    }
  }

  /**
   * Disconnect from voice server
   */
  public async disconnect(): Promise<void> {
    if (!this.rtviClient && !this.isConnecting) return;

    this.log('Disconnecting...');
    this.addTerminalMessage('voice.scanner.disconnect();', 'command');

    try {
      if (this.rtviClient) {
        await this.rtviClient.disconnect();
        this.rtviClient = null;
      }

      // Clean up audio
      if (this.botAudio.srcObject && "getAudioTracks" in this.botAudio.srcObject) {
        this.botAudio.srcObject.getAudioTracks().forEach((track) => track.stop());
        this.botAudio.srcObject = null;
      }

      // Clean up audio context
      if (this.audioContext) {
        await this.audioContext.close();
        this.audioContext = null;
        this.analyser = null;
        this.dataArray = null;
      }

      this.stopAudioVisualization();

      this.isConnecting = false;
      this.isConnected = false;
      this.setVoiceState('idle');
      this.log('Disconnected successfully');

    } catch (error) {
      this.log(`Disconnect error: ${(error as Error).message}`);
      this.isConnecting = false;
      this.isConnected = false;
      this.setVoiceState('idle');
    }
  }
}

// Initialize when DOM is ready
declare global {
  interface Window {
    VoiceScannerApp: typeof VoiceScannerApp;
  }
}

window.addEventListener('DOMContentLoaded', () => {
  window.VoiceScannerApp = VoiceScannerApp;
  new VoiceScannerApp();
});
