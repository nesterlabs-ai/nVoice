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

// A2UI imports
import { A2UIRenderer } from './components/a2ui/A2UIRenderer';
import { A2UIDocument, isA2UIUpdate } from './types/a2ui';

// Emotion Chart import
import { EmotionChart } from './components/EmotionChart';
// Topic Timeline import
import { TopicTimeline } from './components/TopicTimeline';
// Wave Visualization Config
import { waveConfig } from './config/waveVisualization';
import { Loader } from './components/Loader';

type VoiceState = 'idle' | 'listening' | 'thinking' | 'speaking';

class VoiceScannerApp {
  private rtviClient: RTVIClient | null = null;
  private transport: WebSocketTransport | null = null;
  private botPlayerAnalyser: AnalyserNode | null = null;
  private botPlayerDataArray: Uint8Array | null = null;
  private botPlayerContext: AudioContext | null = null;

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
  private mainLayout: HTMLElement | null = null;
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
  private emotionChart: EmotionChart | null = null;
  private topicTimeline: TopicTimeline | null = null;
  private statusIndicator: HTMLElement | null = null;
  private loadingOverlay: HTMLElement | null = null;
  private loader: Loader | null = null;
  private terminalContent: HTMLElement | null = null;
  private terminalStatus: HTMLElement | null = null;
  private typingLine: HTMLElement | null = null;
  private timestampElement: HTMLElement | null = null;
  private notification: HTMLElement | null = null;

  // Canvas elements
  private waveformCanvas: HTMLCanvasElement | null = null;
  private circularCanvas: HTMLCanvasElement | null = null;
  private preloaderCanvas: HTMLCanvasElement | null = null;
  private geminiWaveCanvas: HTMLCanvasElement | null = null;
  private waveformCtx: CanvasRenderingContext2D | null = null;
  private circularCtx: CanvasRenderingContext2D | null = null;
  private preloaderCtx: CanvasRenderingContext2D | null = null;
  private geminiWaveCtx: CanvasRenderingContext2D | null = null;

  // Audio analysis - Dual source for Gemini-style visualization
  private audioContext: AudioContext | null = null;
  private analyser: AnalyserNode | null = null;  // Output (bot) audio
  private inputAnalyser: AnalyserNode | null = null;  // Input (mic) audio
  private dataArray: Uint8Array | null = null;
  private inputDataArray: Uint8Array | null = null;
  private animationFrame: number | null = null;

  // Gemini blob animation state
  private blobTime: number = 0;
  private blobPhase: number = 0;
  private smoothedAmplitude: number = 0;
  private targetAmplitude: number = 0;

  // Audio-driven wave state - stores smoothed frequency data for organic transitions
  private smoothedFrequencyData: number[] = new Array(64).fill(0);
  private waveHistory: number[][] = []; // Store recent wave frames for trail effect

  // Bot audio level from RTVI RemoteAudioLevel event
  private botAudioLevel: number = 0;
  private smoothedBotAudioLevel: number = 0;

  // Safari/iOS: ctx.filter blur is broken; use separate canvases + CSS blur
  private _waveBlurFallback: boolean | null = null;
  private _safariWaveLayers: { wrapper: HTMLDivElement; canvas: HTMLCanvasElement; ctx: CanvasRenderingContext2D }[] | null = null;

  // Audio
  private botAudio!: HTMLAudioElement;

  // State
  private voiceState: VoiceState = 'idle';
  private isConnected: boolean = false;
  private isConnecting: boolean = false;
  private preloaderAngle: number = 0;

  // Streaming transcript state
  private streamingBubble: HTMLElement | null = null;
  private currentUtteranceId: string | null = null;
  private streamingWords: string[] = [];

  // Typewriter effect state for bot transcripts
  private currentBotBubble: HTMLElement | null = null;
  private typewriterQueue: string[] = [];
  private isTypewriting: boolean = false;
  private typewriterSpeed: number = 30; // ms per word

  // Live subtitle above wave (single line, current speaker only)
  private liveSubtitle: HTMLElement | null = null;
  private liveSubtitleText: HTMLElement | null = null;
  private subtitleClearTimeout: ReturnType<typeof setTimeout> | null = null;

  // Media control bar: speaker/mic icon toggle (slash = muted)
  private speakerMuted: boolean = false;
  private micMuted: boolean = false;
  private localAudioTrack: MediaStreamTrack | null = null;

  // Visual cards state
  private activeVisualCard: HTMLElement | null = null;
  private visualCardsContainer: HTMLElement | null = null;

  // A2UI state
  private a2uiRenderer: A2UIRenderer | null = null;
  private a2uiPanel: HTMLElement | null = null;
  private a2uiStatus: HTMLElement | null = null;

  // Emotion-reactive UI state
  private lastEmotionUpdate: number = 0;
  private emotionUpdateDebounceMs: number = 100;

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

    // Expose test method for debugging visual cards
    (window as any).testVisualCard = () => {
      console.log('[TEST] Manually triggering visual card test...');
      this.handleVisualHint({
        hint_type: 'project_card',
        content_type: 'projects',
        content: { mentioned: true },
        confidence: 0.9,
        trigger_text: 'Test trigger',
        timestamp: Date.now() / 1000
      });
    };
    // Expose test method for debugging emotion timeline
    (window as any).testEmotionTimeline = () => {
      console.log('[TEST] Manually triggering emotion timeline test...');
      const testEmotions = ['happy', 'neutral', 'excited', 'sad', 'calm'];
      testEmotions.forEach((emotion, i) => {
        setTimeout(() => {
          this.addEmotionToTimeline(emotion);
        }, i * 500);
      });
    };

    console.log('[DEBUG] testVisualCard() and testEmotionTimeline() functions available in console');
  }

  private setupDOMElements(): void {
    // Legacy elements (hidden but kept for compatibility)
    this.scannerFrame = document.getElementById('scanner-frame');
    this.orbContainer = document.getElementById('voice-orb-container');
    this.orbStatus = document.getElementById('orb-status');

    // Main UI elements
    this.welcomeMessage = document.getElementById('welcome-message');
    this.transcriptList = document.getElementById('transcript-list');
    this.transcriptStatus = document.getElementById('transcript-status');
    this.liveSubtitle = document.getElementById('live-subtitle');
    this.liveSubtitleText = document.getElementById('live-subtitle-text');
    this.debugPanel = document.getElementById('debug-panel');
    this.debugLog = document.getElementById('debug-log');
    this.debugToggle = document.getElementById('debug-toggle');
    this.debugClose = document.getElementById('debug-close');
    this.mainLayout = document.querySelector('.main-layout');
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

    // Initialize Loader (text configurable via loader.setText())
    const loadingTextEl = document.getElementById('loading-text');
    if (loadingTextEl) {
      this.loader = new Loader({
        container: loadingTextEl,
        text: 'INITIALIZING',
      });
    }

    // Initialize Emotion Chart
    try {
      this.emotionChart = new EmotionChart('emotion-chart-canvas');
      console.log('[EmotionChart] Initialized successfully');
      // Expose for testing
      (window as any).testEmotionChart = () => {
        if (this.emotionChart) {
          console.log('[EmotionChart] Adding test data points...');
          this.emotionChart.addDataPoint(0.7, 0.6, 0.8);
          setTimeout(() => this.emotionChart?.addDataPoint(0.5, 0.4, 0.3), 500);
          setTimeout(() => this.emotionChart?.addDataPoint(0.8, 0.7, 0.6), 1000);
          setTimeout(() => this.emotionChart?.addDataPoint(0.4, 0.5, 0.7), 1500);
        }
      };
    } catch (e) {
      console.warn('[EmotionChart] Failed to initialize:', e);
    }

    // Initialize Topic Timeline
    try {
      this.topicTimeline = new TopicTimeline('topic-timeline-canvas');
      console.log('[TopicTimeline] Initialized successfully');
    } catch (e) {
      console.warn('[TopicTimeline] Failed to initialize:', e);
    }

    this.terminalContent = document.getElementById('terminal-content');
    this.terminalStatus = document.getElementById('terminal-status');
    this.typingLine = document.getElementById('typing-line');
    this.timestampElement = document.getElementById('timestamp');
    this.notification = document.getElementById('notification');

    // Canvas elements
    this.waveformCanvas = document.getElementById('waveform-canvas') as HTMLCanvasElement;
    this.circularCanvas = document.getElementById('circular-canvas') as HTMLCanvasElement;
    this.preloaderCanvas = document.getElementById('preloader-canvas') as HTMLCanvasElement;
    this.geminiWaveCanvas = document.getElementById('gemini-wave-canvas') as HTMLCanvasElement;

    // A2UI elements
    this.a2uiPanel = document.getElementById('a2ui-panel');
    this.a2uiStatus = document.getElementById('a2ui-status');

    // Initialize A2UI renderer
    this.initializeA2UIRenderer();
  }

  private setupEventListeners(): void {
    // New connect/disconnect buttons
    const connectBtn = document.getElementById('connect-btn');
    const disconnectBtn = document.getElementById('disconnect-btn');

    connectBtn?.addEventListener('click', () => this.handleConnect());
    disconnectBtn?.addEventListener('click', () => this.handleDisconnect());

    // Back button: open NesterLabs in the same tab
    document.getElementById('back-btn')?.addEventListener('click', () => {
      window.location.href = 'https://www.nesterlabs.com/';
    });

    // Legacy scanner frame click (if still exists)
    this.scannerFrame?.addEventListener('click', () => this.handleOrbClick());

    // Debug panel
    this.debugToggle?.addEventListener('click', () => this.toggleDebugPanel());
    this.debugClose?.addEventListener('click', () => this.hideDebugPanel());

    document.getElementById('control-peak')?.addEventListener('click', () => this.toggleSidePanels());
    document.getElementById('control-close')?.addEventListener('click', () => {
      this.hideA2UIPanel();
      this.handleDisconnect();
      this.showCloseOptions();
    });
    document.getElementById('control-speaker')?.addEventListener('click', () => this.toggleSpeakerIcon());
    document.getElementById('control-mic')?.addEventListener('click', () => this.toggleMicIcon());

    document.getElementById('close-option-restart')?.addEventListener('click', () => this.onRestartOption());
    document.getElementById('close-option-peak')?.addEventListener('click', () => this.onPeakOption());

    // Emotion panel toggle
    this.emotionToggle?.addEventListener('click', () => this.toggleEmotionPanel());

  }

  /**
   * Handle connect button click
   */
  private handleConnect(): void {
    // Show connecting state immediately
    const connectBtn = document.getElementById('connect-btn');
    connectBtn?.classList.add('connecting');
    this.connect();
  }

  /**
   * Show Restart/Peak options: bar animates from bottom to center, buttons swap (when Close is clicked)
   */
  private showCloseOptions(): void {
    const mediaBar = document.getElementById('media-control-bar');
    const connectArea = document.getElementById('connect-area');
    mediaBar?.classList.add('close-mode');
    connectArea?.classList.add('hidden');
  }

  /**
   * Restart: hide options bar, disconnect, then connect (same flow as connect-btn)
   */
  private async onRestartOption(): Promise<void> {
    this.hideCloseOptions();
    await this.disconnect();
    this.handleConnect();
  }

  /**
   * Peak: toggle side panels and show media bar again
   */
  private onPeakOption(): void {
    this.toggleSidePanels();
  }

  /**
   * Hide Restart/Peak options: bar animates back to bottom, buttons swap back
   */
  private hideCloseOptions(): void {
    const mediaBar = document.getElementById('media-control-bar');
    const connectArea = document.getElementById('connect-area');
    mediaBar?.classList.remove('close-mode');
    connectArea?.classList.remove('hidden');
  }

  /**
   * Handle disconnect button click
   */
  private handleDisconnect(): void {
    this.disconnect();
  }

  /** Icon paths for control-close button (normal vs disabled) */
  private static readonly CLOSE_ICON_ENABLED = '/X (1).svg';
  private static readonly CLOSE_ICON_DISABLED = '/X-disable.svg';

  /**
   * Enable or disable the control-close button. Disabled while WebSocket is connecting so user cannot close during pending API.
   * Swaps the button icon to X-disable.svg when disabled.
   */
  private setCloseButtonEnabled(enabled: boolean): void {
    const closeBtn = document.getElementById('control-close');
    if (!closeBtn) return;
    (closeBtn as HTMLButtonElement).disabled = !enabled;
    closeBtn.setAttribute('aria-disabled', String(!enabled));
    const icon = closeBtn.querySelector('img');
    if (icon) {
      icon.src = enabled ? VoiceScannerApp.CLOSE_ICON_ENABLED : VoiceScannerApp.CLOSE_ICON_DISABLED;
    }
    if (enabled) {
      closeBtn.classList.remove('control-btn-close-disabled');
    } else {
      closeBtn.classList.add('control-btn-close-disabled');
    }
  }

  /**
   * Update UI for connection state
   */
  private updateConnectionUI(connected: boolean): void {
    const connectArea = document.getElementById('connect-area');
    const connectBtn = document.getElementById('connect-btn');
    const statusDisplay = document.getElementById('status-display');
    const connectionStatus = document.getElementById('connection-status');

    if (connected) {
      // Remove connecting state, add shrinking animation
      connectBtn?.classList.remove('connecting');
      connectBtn?.classList.add('shrinking');

      // After animation, hide connect area (disconnect is via control-close in media bar)
      setTimeout(() => {
        connectArea?.classList.add('hidden');
        connectBtn?.classList.remove('shrinking');
      }, 400);

      statusDisplay?.classList.remove('hidden');
      connectionStatus?.classList.add('online');
      if (connectionStatus) connectionStatus.textContent = 'ONLINE';
    } else {
      connectBtn?.classList.remove('connecting');
      connectBtn?.classList.remove('shrinking');
      this.setCloseButtonEnabled(true); // Ensure close is enabled when not connected
      // Don't show connect-area when bar is in close-mode (Restart serves that purpose)
      const mediaBar = document.getElementById('media-control-bar');
      if (!mediaBar?.classList.contains('close-mode')) {
        connectArea?.classList.remove('hidden');
      }
      statusDisplay?.classList.add('hidden');
      connectionStatus?.classList.remove('online');
      if (connectionStatus) connectionStatus.textContent = 'OFFLINE';
    }
  }

  /**
   * Update status display based on voice state
   */
  private updateStatusDisplay(): void {
    const statusDisplay = document.getElementById('status-display');
    const statusText = document.getElementById('status-text');

    if (!statusDisplay) return;

    // Remove all state classes
    statusDisplay.classList.remove('idle', 'listening', 'speaking', 'thinking');

    // Add current state class
    statusDisplay.classList.add(this.voiceState);

    // Update status text
    const stateTexts: Record<string, string> = {
      idle: 'READY',
      listening: 'LISTENING',
      speaking: 'SPEAKING',
      thinking: 'PROCESSING'
    };

    if (statusText) {
      statusText.textContent = stateTexts[this.voiceState] || 'READY';
    }
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

    // Old circular canvas (kept for compatibility but hidden)
    if (this.circularCanvas) {
      const container = this.circularCanvas.parentElement;
      if (container) {
        const size = Math.max(container.offsetWidth, container.offsetHeight) + 100;
        this.circularCanvas.width = size;
        this.circularCanvas.height = size;
      }
      this.circularCtx = this.circularCanvas.getContext('2d');
    }

    // Gemini-style bottom wave visualizer canvas
    if (this.geminiWaveCanvas) {
      const container = this.geminiWaveCanvas.parentElement;
      if (container) {
        // Safari/iOS: ctx.filter blur is broken; use separate canvases + CSS blur
        if (this._waveBlurFallback === null && typeof navigator !== 'undefined') {
          const ua = navigator.userAgent;
          this._waveBlurFallback = (
            (/Safari\//.test(ua) && !/Chrome|Chromium/.test(ua)) ||
            /iPhone|iPad|iPod/.test(ua)
          );
        }
        if (this._waveBlurFallback === true) {
          this.ensureSafariWaveLayerDOM(container);
        } else {
          this.geminiWaveCanvas.width = container.offsetWidth * 2;  // 2x for retina
          this.geminiWaveCanvas.height = container.offsetHeight * 2;
        }
        this.geminiWaveCtx = this.geminiWaveCanvas.getContext('2d');

        // Start the Gemini wave animation
        this.startIdleBlobAnimation();
      }
    }

    // Preloader canvas
    if (this.preloaderCanvas) {
      this.preloaderCtx = this.preloaderCanvas.getContext('2d');
      this.animatePreloader();
    }
  }

  /**
   * Safari/iOS: Create separate canvases per layer with CSS blur wrapper.
   * ctx.filter blur is broken in Safari; this fallback uses CSS filter: blur() instead.
   */
  private ensureSafariWaveLayerDOM(container: HTMLElement): void {
    if (this._safariWaveLayers) return; // Already created

    const { layers } = waveConfig;
    const w = container.offsetWidth * 2;  // Retina
    const h = container.offsetHeight * 2;

    // Hide the main canvas; we'll use layer canvases instead
    if (this.geminiWaveCanvas) {
      this.geminiWaveCanvas.style.display = 'none';
    }

    const safariWrapper = document.createElement('div');
    safariWrapper.className = 'safari-wave-layers';
    safariWrapper.style.cssText = 'position:absolute;inset:0;pointer-events:none;';

    this._safariWaveLayers = [];
    for (let i = layers.length - 1; i >= 0; i--) {
      const layerConfig = layers[i];
      const layerBlur = layerConfig.blur;

      const layerDiv = document.createElement('div');
      layerDiv.style.cssText = `position:absolute;inset:0;overflow:hidden;filter:blur(${layerBlur}px);`;
      layerDiv.className = 'safari-wave-layer';

      const canvas = document.createElement('canvas');
      canvas.className = 'wave-canvas';
      canvas.width = w;
      canvas.height = h;
      canvas.style.cssText = 'width:100%;height:100%;';

      const ctx = canvas.getContext('2d');
      if (!ctx) continue;

      layerDiv.appendChild(canvas);
      safariWrapper.appendChild(layerDiv);
      this._safariWaveLayers.push({ wrapper: layerDiv, canvas, ctx });
    }

    container.appendChild(safariWrapper);
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
   * Update loader text (e.g. "Planning next moves", "INITIALIZING")
   */
   setLoaderText(text: string): void {
    this.loader?.setText(text);
  }

  /**
   * Hide loading overlay
   */
  private hideLoadingOverlay(): void {
    if (this.loadingOverlay) {
      this.loadingOverlay.classList.add('hidden');
      this.addTerminalMessage('Voice scanner ready. Awaiting user input.', 'regular');
      // Dispatch event for components waiting for page ready
      window.dispatchEvent(new CustomEvent('nesterPageReady'));
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

    // Update new status display UI
    this.updateStatusDisplay();

    // Legacy scanner frame updates (hidden but kept for compatibility)
    if (this.scannerFrame && this.orbContainer) {
      this.scannerFrame.classList.remove('idle', 'listening', 'thinking', 'speaking', 'connected');
      this.orbContainer.classList.remove('idle', 'listening', 'thinking', 'speaking', 'connected');
      this.scannerFrame.classList.add(state);
      this.orbContainer.classList.add(state);

      if (this.isConnected) {
        this.scannerFrame.classList.add('connected');
        this.orbContainer.classList.add('connected');
      }
    }

    // Update legacy status text
    if (this.orbStatus) {
      const statusTexts: Record<VoiceState, string> = {
        'idle': this.isConnected ? 'TAP TO TERMINATE' : 'TAP TO INITIALIZE',
        'listening': 'SCANNING VOICE INPUT...',
        'thinking': 'PROCESSING SIGNAL...',
        'speaking': 'TRANSMITTING RESPONSE...'
      };
      this.orbStatus.textContent = statusTexts[state];
    }

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

    this.updateLiveSubtitle(isUser ? 'user' : 'bot', text);

    const bubble = document.createElement('div');
    bubble.className = `transcript-bubble ${isUser ? 'user' : 'bot'}`;

    // Add label
    const label = document.createElement('span');
    label.className = 'transcript-label';
    label.textContent = isUser ? 'You: ' : 'NesterAI: ';

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
   * Update the live subtitle above the wave visualizer (2 lines: user + bot, synced with voice)
   */
  private updateLiveSubtitle(role: 'user' | 'bot', text: string): void {
    if (!this.liveSubtitle || !this.liveSubtitleText) return;
    if (!text) return;

    // Reset auto-clear timer
    if (this.subtitleClearTimeout) {
      clearTimeout(this.subtitleClearTimeout);
    }

    // Role class on container for .user / .bot text styling
    this.liveSubtitle.classList.remove('user', 'bot');
    this.liveSubtitle.classList.add(role);

    // User speech: prefix with "- " so we can identify user vs bot at a glance
    const displayText = role === 'user' ? `- ${text}` : text;

    // Render each word as an animated span
    const words = displayText.split(/\s+/).filter(w => w.length > 0);
    this.liveSubtitleText.innerHTML = words.map(w =>
      `<span class="sub-word">${w}</span>`
    ).join(' ');

    // Show the subtitle
    this.liveSubtitle.classList.add('visible');

    // Auto-hide after 4s of no new updates
    this.subtitleClearTimeout = setTimeout(() => {
      this.liveSubtitle?.classList.remove('visible');
    }, 4000);
  }

  /**
   * Append a single word to the live subtitle (same word-by-word behavior as transcript bubble).
   * Used during bot typewriter so the subtitle streams one word at a time instead of re-rendering all.
   */
  private appendBotWordToLiveSubtitle(word: string, isFirstWord: boolean): void {
    if (!this.liveSubtitle || !this.liveSubtitleText) return;

    if (this.subtitleClearTimeout) {
      clearTimeout(this.subtitleClearTimeout);
    }

    this.liveSubtitle.classList.remove('user', 'bot');
    this.liveSubtitle.classList.add('bot');

    if (isFirstWord) {
      this.liveSubtitleText.innerHTML = '';
    }

    const wordSpan = document.createElement('span');
    wordSpan.className = 'typewriter-word';
    wordSpan.textContent = word + ' ';
    this.liveSubtitleText.appendChild(wordSpan);

    this.liveSubtitle.classList.add('visible');
    this.subtitleClearTimeout = setTimeout(() => {
      this.liveSubtitle?.classList.remove('visible');
    }, 4000);
  }

  /**
   * Add bot transcript with typewriter effect (word by word)
   */
  private addBotTranscriptWithTypewriter(text: string): void {
    if (!this.transcriptList) return;

    // Hide welcome message
    this.welcomeMessage?.classList.add('hidden');

    // Create new bubble if none exists
    if (!this.currentBotBubble) {
      this.currentBotBubble = document.createElement('div');
      this.currentBotBubble.className = 'transcript-bubble bot typewriter';

      const label = document.createElement('span');
      label.className = 'transcript-label';
      label.textContent = 'NesterAI: ';

      const textSpan = document.createElement('span');
      textSpan.className = 'transcript-text typewriter-text';

      this.currentBotBubble.appendChild(label);
      this.currentBotBubble.appendChild(textSpan);
      this.transcriptList.appendChild(this.currentBotBubble);
    }

    // Split text into words and add to queue
    const words = text.split(/\s+/).filter(w => w.length > 0);
    this.typewriterQueue.push(...words);

    // Start typewriter if not already running
    if (!this.isTypewriting) {
      this.processTypewriterQueue();
    }
  }

  /**
   * Process the typewriter queue word by word
   */
  private processTypewriterQueue(): void {
    if (this.typewriterQueue.length === 0) {
      this.isTypewriting = false;
      return;
    }

    this.isTypewriting = true;
    const word = this.typewriterQueue.shift()!;

    if (this.currentBotBubble) {
      const textSpan = this.currentBotBubble.querySelector('.typewriter-text');
      if (textSpan) {
        // Same as live subtitle: first word = start of line
        const isFirstWord = textSpan.childNodes.length === 0;

        // Add word with animation (same as transcript bubble)
        const wordSpan = document.createElement('span');
        wordSpan.className = 'typewriter-word';
        wordSpan.textContent = word + ' ';
        textSpan.appendChild(wordSpan);

        // Live subtitle: append one word at a time (same word-by-word behavior as bubble)
        this.appendBotWordToLiveSubtitle(word, isFirstWord);

        // Scroll to bottom
        if (this.transcriptList) {
          this.transcriptList.scrollTop = this.transcriptList.scrollHeight;
        }
      }
    }

    // Schedule next word
    setTimeout(() => this.processTypewriterQueue(), this.typewriterSpeed);
  }

  /**
   * Finalize the current bot bubble (called when user starts speaking)
   */
  private finalizeBotBubble(): void {
    if (this.currentBotBubble) {
      const textSpan = this.currentBotBubble.querySelector('.typewriter-text');
      if (textSpan) {
        this.updateLiveSubtitle('bot', (textSpan.textContent || '').trim());
      }
      this.currentBotBubble.classList.remove('typewriter');
      this.currentBotBubble.classList.add('finalized');

      // Convert animated words to static text for performance
      if (textSpan) {
        const fullText = textSpan.textContent || '';
        textSpan.innerHTML = '';
        textSpan.textContent = fullText;
      }
    }
    this.currentBotBubble = null;
    this.typewriterQueue = [];
    this.isTypewriting = false;
  }

  // Store last user query and accumulated bot answer for graph highlighting
  private lastUserQuery: string = '';
  private accumulatedBotAnswer: string = '';
  private graphHighlightTimeout: ReturnType<typeof setTimeout> | null = null;

  // Track previous topics for context (last 10 topics)
  private previousTopics: string[] = [];

  /**
   * Highlight relevant graph nodes based on query and answer
   * LLM selects nodes from the actual graph that match the conversation
   * Also returns the conversation topic for the timeline
   */
  private async highlightGraphKeywords(query: string, answer: string = ''): Promise<void> {
    if ((!query || query.trim().length < 3) && (!answer || answer.trim().length < 3)) return;

    const backendUrl = this.getBackendUrl();

    try {
      const response = await fetch(`${backendUrl}/graph/keywords`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query,
          answer,
          // Send previous topics for LLM context to determine topic relationships
          previousTopics: this.previousTopics,
        }),
      });

      if (!response.ok) {
        console.warn('[KnowledgeGraph] Node selection failed:', response.status);
        return;
      }

      const data = await response.json();

      // Highlight matched nodes in the graph with cycling animation
      if (data.matched && data.matched.length > 0 && (window as any).KnowledgeGraph) {
        console.log('[KnowledgeGraph] Selected nodes (by relevance):', data.matched.join(', '));
        (window as any).KnowledgeGraph.highlightWithCycle(data.matched);
      } else {
        console.log('[KnowledgeGraph] No matching nodes for conversation');
      }

      // Add topic to timeline - topic and type come from backend LLM call
      if (this.topicTimeline && data.topic) {
        const keywords = data.matched || [];
        this.topicTimeline.addTopic(data.topic, keywords, data.topicType, data.parentTopic);
        console.log('[TopicTimeline] Added topic:', data.topic, 'type:', data.topicType);

        // Track this topic for future context (keep last 10)
        this.previousTopics.push(data.topic);
        if (this.previousTopics.length > 10) {
          this.previousTopics.shift();
        }
      }
    } catch (error) {
      console.warn('[KnowledgeGraph] Failed to select nodes:', error);
    }
  }

  /**
   * Toggle debug panel
   */
  private toggleDebugPanel(): void {
    this.debugPanel?.classList.toggle('visible');
  }

  /**
   * Toggle left and right side panels visibility
   */
  private toggleSidePanels(): void {
    this.mainLayout?.classList.toggle('panels-hidden');
  }

  /**
   * Toggle speaker icon between SpeakerHigh.svg and SpeakerSlash.svg
   */
  private toggleSpeakerIcon(): void {
    this.speakerMuted = !this.speakerMuted;
    if (this.botPlayerContext) {
      if (this.speakerMuted) {
        this.botPlayerContext.suspend();
      } else {
        this.botPlayerContext.resume();
      }
    }
    const btn = document.getElementById('control-speaker');
    const img = btn?.querySelector<HTMLImageElement>('.control-btn-icon');
    if (img) {
      img.src = this.speakerMuted ? '/SpeakerSlash.svg' : '/SpeakerHigh.svg';
    }
    btn?.setAttribute('aria-label', this.speakerMuted ? 'Sound muted' : 'Sound');
  }

  /**
   * Toggle mic icon between Microphone (1).svg and MicrophoneSlash.svg
   */
  private toggleMicIcon(): void {
    this.micMuted = !this.micMuted;
    if (this.localAudioTrack) {
      this.localAudioTrack.enabled = !this.micMuted;
    }
    const btn = document.getElementById('control-mic');
    const img = btn?.querySelector<HTMLImageElement>('.control-btn-icon');
    if (img) {
      img.src = this.micMuted ? '/MicrophoneSlash.svg' : '/Microphone (1).svg';
    }
    btn?.setAttribute('aria-label', this.micMuted ? 'Microphone muted' : 'Microphone');
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

    // Update emotion chart with new data point
    if (this.emotionChart) {
      this.emotionChart.addDataPoint(data.arousal, data.dominance, data.valence);
    }

    // Add terminal message
    this.addTerminalMessage(`emotion.detect({type: '${data.emotion}', conf: ${(data.confidence * 100).toFixed(0)}%});`, 'command');

    this.log(`Emotion detected: ${emotionName} (${Math.round(data.confidence * 100)}%)`);
  }

  /**
   * Update emotion display with HYBRID emotion data (audio + text)
   */
  private updateHybridEmotionDisplay(data: {
    primary_emotion: string;
    secondary_emotion?: string;
    arousal: number;
    dominance: number;
    valence: number;
    confidence: number;
    audio_emotion: string;
    text_emotion: string;
    audio_weight: number;
    text_weight: number;
    mismatch_detected: boolean;
    interpretation?: string;
    tokens_used: number;
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

    const emoji = emotionEmojis[data.primary_emotion] || '😊';
    const emotionName = data.primary_emotion.toUpperCase();

    if (this.emotionEmoji) this.emotionEmoji.textContent = emoji;
    if (this.emotionLabel) this.emotionLabel.textContent = emotionName;
    if (this.emotionConfidence) {
      this.emotionConfidence.textContent = `${Math.round(data.confidence * 100)}%`;
    }

    // Update emotion chart with new data point
    if (this.emotionChart) {
      this.emotionChart.addDataPoint(data.arousal, data.dominance, data.valence);
    }

    // Add hybrid-specific terminal message with audio/text breakdown
    const audioPercent = Math.round(data.audio_weight * 100);
    const textPercent = Math.round(data.text_weight * 100);

    let terminalMsg = `🔄 hybrid.emotion({primary: '${data.primary_emotion}', conf: ${(data.confidence * 100).toFixed(0)}%, audio: ${audioPercent}%, text: ${textPercent}%})`;

    if (data.mismatch_detected && data.interpretation) {
      terminalMsg += `\n⚠️  ${data.interpretation}`;
    }

    this.addTerminalMessage(terminalMsg, 'command');

    this.log(`🔄 Hybrid Emotion: ${emotionName} (${Math.round(data.confidence * 100)}%) | Audio: ${data.audio_emotion} ${audioPercent}% | Text: ${data.text_emotion} ${textPercent}%`);
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
    console.log('[Timeline] Adding emotion to timeline:', emotion, 'Element exists:', !!this.emotionTimeline);
    if (!this.emotionTimeline) {
      console.warn('[Timeline] emotionTimeline element not found!');
      return;
    }

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
    console.log('[Timeline] Dot appended, current count:', this.emotionTimeline.children.length);

    // Animate dot entrance
    setTimeout(() => dot.classList.add('visible'), 10);
  }

  /**
   * Start audio visualization
   * The actual animation loop is in startIdleBlobAnimation which handles all states
   */
  private startAudioVisualization(): void {
    // Animation loop is already running from startIdleBlobAnimation
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
   * Draw audio-driven wave visualizer at bottom of screen
   */
  private drawGeminiBlob(): void {
    const useSafariFallback = this._waveBlurFallback === true && this._safariWaveLayers && this._safariWaveLayers.length > 0;
    const ctx = useSafariFallback ? null : this.geminiWaveCtx;
    const canvas = useSafariFallback ? this._safariWaveLayers![0].canvas : this.geminiWaveCanvas;

    if (!canvas || (!useSafariFallback && !ctx)) return;

    const width = canvas.width;
    const height = canvas.height;

    // Safety check for valid dimensions
    if (width <= 0 || height <= 0) return;

    if (useSafariFallback) {
      for (const layer of this._safariWaveLayers!) {
        layer.ctx.clearRect(0, 0, width, height);
      }
    } else {
      ctx!.clearRect(0, 0, width, height);
    }

    // Update animation time
    this.blobTime += 0.02;
    this.blobPhase += 0.015;

    // Get active audio data based on state
    const activeDataArray = this.voiceState === 'speaking'
      ? this.dataArray
      : (this.voiceState === 'listening' ? this.inputDataArray : null);

    const numBars = this.smoothedFrequencyData.length;

    // Update smoothed frequency data from actual audio OR simulated audio
    if (this.voiceState === 'listening' && activeDataArray && activeDataArray.length > 0) {
      // User's turn (listening state) - mic input with base resting height
      for (let i = 0; i < numBars; i++) {
        const dataIndex = Math.floor((i / numBars) * activeDataArray.length * 0.8);
        const rawValue = (activeDataArray[dataIndex] || 0) / 255;

        // Apply noise gate threshold to filter out background noise
        const noiseThreshold = 0.08;
        const gatedValue = rawValue > noiseThreshold ? (rawValue - noiseThreshold) / (1 - noiseThreshold) : 0;

        // Base resting height + audio reactive component
        const baseHeight = 0.22 + Math.sin(this.blobPhase + i * 0.1) * 0.06;
        const audioComponent = Math.pow(gatedValue, 0.8) * 0.8;
        const targetValue = baseHeight + audioComponent;

        // Smooth transition (moderate attack, slower decay)
        if (targetValue > this.smoothedFrequencyData[i]) {
          this.smoothedFrequencyData[i] += (targetValue - this.smoothedFrequencyData[i]) * 0.5;
        } else {
          this.smoothedFrequencyData[i] += (targetValue - this.smoothedFrequencyData[i]) * 0.15;
        }
      }
    } else if (this.voiceState === 'speaking') {
      // Bot's turn (speaking state) - try to use real frequency data from bot audio analyser
      // Priority: botPlayerDataArray (WavStreamPlayer) > dataArray (TrackStarted) > simulated

      // Determine which data array to use
      let activeFreqArray: Uint8Array | null = null;

      // First, try the new bot player analyser (WavStreamPlayer from transport)
      if (this.botPlayerDataArray && this.botPlayerDataArray.length > 0) {
        for (let i = 0; i < this.botPlayerDataArray.length; i++) {
          if (this.botPlayerDataArray[i] > 5) {
            activeFreqArray = this.botPlayerDataArray;
            break;
          }
        }
      }

      // Fall back to old analyser (from TrackStarted event) if no bot player data
      if (!activeFreqArray && this.dataArray && this.dataArray.length > 0) {
        for (let i = 0; i < this.dataArray.length; i++) {
          if (this.dataArray[i] > 5) {
            activeFreqArray = this.dataArray;
            break;
          }
        }
      }

      if (activeFreqArray) {
        // Use REAL frequency data from bot audio analyser (IDENTICAL to user input processing)
        for (let i = 0; i < numBars; i++) {
          const dataIndex = Math.floor((i / numBars) * activeFreqArray.length * 0.8);
          const rawValue = (activeFreqArray[dataIndex] || 0) / 255;

          // Apply noise gate threshold (same as user input)
          const noiseThreshold = 0.08;
          const gatedValue = rawValue > noiseThreshold ? (rawValue - noiseThreshold) / (1 - noiseThreshold) : 0;

          // Base resting height + audio reactive component (same as user input)
          const baseHeight = 0.22 + Math.sin(this.blobPhase + i * 0.1) * 0.06;
          const audioComponent = Math.pow(gatedValue, 0.8) * 0.8;
          const targetValue = baseHeight + audioComponent;

          // Smooth transition (same as user input)
          if (targetValue > this.smoothedFrequencyData[i]) {
            this.smoothedFrequencyData[i] += (targetValue - this.smoothedFrequencyData[i]) * 0.5;
          } else {
            this.smoothedFrequencyData[i] += (targetValue - this.smoothedFrequencyData[i]) * 0.15;
          }
        }
      } else {
        // Fallback: Simulate frequency bands using single audio level
        this.smoothedBotAudioLevel += (this.botAudioLevel - this.smoothedBotAudioLevel) * 0.3;

        for (let i = 0; i < numBars; i++) {
          const baseHeight = 0.22 + Math.sin(this.blobPhase + i * 0.1) * 0.06;
          const pos = i / numBars;

          // Multiple frequency band simulation
          const band1 = Math.sin(this.blobTime * 4.5 + i * 0.3) * 0.5 + 0.5;
          const band2 = Math.sin(this.blobTime * 6.2 + i * 0.5) * 0.5 + 0.5;
          const band3 = Math.sin(this.blobTime * 8.1 + i * 0.7) * 0.5 + 0.5;
          const band4 = Math.sin(this.blobTime * 5.3 + i * 0.4) * 0.5 + 0.5;

          const lowWeight = Math.exp(-Math.pow((pos - 0.2) * 3, 2));
          const midWeight = Math.exp(-Math.pow((pos - 0.45) * 3, 2));
          const highWeight = Math.exp(-Math.pow((pos - 0.7) * 3, 2));
          const extraWeight = Math.exp(-Math.pow((pos - 0.35) * 4, 2));

          const combinedBands = (band1 * lowWeight + band2 * midWeight + band3 * highWeight + band4 * extraWeight) / 2;
          const audioComponent = this.smoothedBotAudioLevel * combinedBands * 1.2;

          const targetValue = baseHeight + audioComponent;

          if (targetValue > this.smoothedFrequencyData[i]) {
            this.smoothedFrequencyData[i] += (targetValue - this.smoothedFrequencyData[i]) * 0.5;
          } else {
            this.smoothedFrequencyData[i] += (targetValue - this.smoothedFrequencyData[i]) * 0.15;
          }
        }
      }
    } else {
      // Idle/thinking animation
      for (let i = 0; i < numBars; i++) {
        let targetValue: number;
        if (this.voiceState === 'thinking') {
          targetValue = 0.25 + Math.sin(this.blobTime * 2 + i * 0.2) * 0.1;
        } else {
          // Idle resting position - taller base wave
          targetValue = 0.35 + Math.sin(this.blobPhase + i * 0.25) * 0.07;
        }
        this.smoothedFrequencyData[i] += (targetValue - this.smoothedFrequencyData[i]) * 0.1;
      }
    }

    // Calculate overall amplitude
    let totalAmplitude = 0;
    for (let i = 0; i < numBars; i++) {
      totalAmplitude += this.smoothedFrequencyData[i];
    }
    this.smoothedAmplitude = totalAmplitude / numBars;

    // State-based colors
    let primaryColor: string;
    let glowAlpha: number;

    switch (this.voiceState) {
      case 'idle':
        primaryColor = '#ef3339';
        glowAlpha = 0.15;
        break;
      case 'listening':
        primaryColor = '#22c55e';
        glowAlpha = 0.6;
        break;
      case 'thinking':
        primaryColor = '#f97316';
        glowAlpha = 0.4;
        break;
      case 'speaking':
        primaryColor = '#ef3339';
        glowAlpha = 0.7;
        break;
      default:
        primaryColor = '#ef3339';
        glowAlpha = 0.15;
    }

    // Wave parameters from configuration
    const { numPoints, maxWaveHeightRatio, layers, layerTimeOffset, layerSpeedIncrement, edgeFadePower, organicWaveAmplitude } = waveConfig;
    const baseY = height; // Start from bottom
    const maxWaveHeight = height * maxWaveHeightRatio;
    const numLayers = layers.length;

    // Get interpolated value from frequency data with smoothing
    const getAudioValue = (position: number): number => {
      const idx = Math.max(0, Math.min(position, 1)) * (numBars - 1);
      const i0 = Math.floor(idx);
      const i1 = Math.min(i0 + 1, numBars - 1);
      const t = idx - i0;
      const v0 = this.smoothedFrequencyData[i0] || 0;
      const v1 = this.smoothedFrequencyData[i1] || 0;
      return v0 * (1 - t) + v1 * t;
    };

    // Draw multiple layered waves from back to front
    for (let layer = numLayers - 1; layer >= 0; layer--) {
      const layerConfig = layers[layer];
      const layerScale = layerConfig.heightScale;
      const layerBlur = layerConfig.blur;
      const layerOffset = layer * layerTimeOffset;
      const layerSpeed = 1 + layer * layerSpeedIncrement;

      const layerCtx = useSafariFallback
        ? this._safariWaveLayers![numLayers - 1 - layer].ctx
        : ctx!;

      // Apply blur filter for this layer (Safari: skip - CSS blur on wrapper handles it)
      if (!useSafariFallback) {
        layerCtx.filter = layerBlur > 0 ? `blur(${layerBlur}px)` : 'none';
      }

      layerCtx.beginPath();
      layerCtx.moveTo(0, baseY);

      // Draw the wave curve
      for (let i = 0; i <= numPoints; i++) {
        const x = (i / numPoints) * width;
        const normalizedX = i / numPoints;

        // Mirror frequency data from center for symmetric wave
        const dataPosition = normalizedX <= 0.5 ? normalizedX * 2 : (1 - normalizedX) * 2;

        // Get audio value and add organic movement
        const audioValue = getAudioValue(dataPosition);
        const organicWave = Math.sin(normalizedX * Math.PI * 3 + this.blobTime * layerSpeed + layerOffset) * organicWaveAmplitude;

        // Calculate wave height - rises from bottom
        const waveIntensity = (audioValue + organicWave) * layerScale;
        const waveHeight = Math.max(0, waveIntensity) * maxWaveHeight;

        // Edge fade for smooth tapering at sides
        const edgeFade = Math.pow(Math.sin(normalizedX * Math.PI), edgeFadePower);

        const y = baseY - waveHeight * edgeFade;
        layerCtx.lineTo(x, y);
      }

      // Complete the shape by going to bottom corners
      layerCtx.lineTo(width, baseY);
      layerCtx.lineTo(0, baseY);
      layerCtx.closePath();

      // Fill with solid color from config
      layerCtx.fillStyle = layerConfig.color;
      layerCtx.fill();

      if (!useSafariFallback) {
        layerCtx.filter = 'none';
      }
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

    // Draw one final idle blob frame
    this.smoothedAmplitude = 0;
    this.drawGeminiBlob();

    const peakValue = document.getElementById('peak-value');
    if (peakValue) peakValue.textContent = '-- HZ';

    const amplitudeValue = document.getElementById('amplitude-value');
    if (amplitudeValue) amplitudeValue.textContent = '0.00';
  }

  /**
   * Start idle blob animation (runs even when not connected)
   */
  private startIdleBlobAnimation(): void {
    if (this.animationFrame) return;

    const animate = () => {
      // Read mic audio frequency data when user is speaking
      if (this.voiceState === 'listening' && this.inputAnalyser && this.inputDataArray) {
        this.inputAnalyser.getByteFrequencyData(this.inputDataArray as Uint8Array<ArrayBuffer>);
      }

      // Read bot audio frequency data when AI is speaking
      // Prefer botPlayerAnalyser (from transport's WavStreamPlayer) over the old analyser
      if (this.voiceState === 'speaking') {
        if (this.botPlayerAnalyser && this.botPlayerDataArray) {
          this.botPlayerAnalyser.getByteFrequencyData(this.botPlayerDataArray as Uint8Array<ArrayBuffer>);
        } else if (this.analyser && this.dataArray) {
          this.analyser.getByteFrequencyData(this.dataArray as Uint8Array<ArrayBuffer>);
        }
      }

      // Draw the main wave visualizer
      this.drawGeminiBlob();

      // When connected, also update other visualizations
      if (this.isConnected) {
        this.drawWaveform();
        this.updatePeakFrequency();
      }

      this.animationFrame = requestAnimationFrame(animate);
    };
    animate();
  }

  /**
   * Set up output audio track (bot voice) with visualization
   */
  private botAnalyserSetup = false;

  private setupAudioTrack(track: MediaStreamTrack): void {
    this.log('Bot audio track connected');

    const stream = new MediaStream([track]);
    this.botAudio.srcObject = stream;

    // Set up audio analysis for visualization
    try {
      if (!this.audioContext) {
        this.audioContext = new AudioContext();
      }

      if (this.audioContext.state === 'suspended') {
        this.audioContext.resume();
      }

      // Only set up analyser once
      if (!this.botAnalyserSetup) {
        // Method 1: Try to capture stream from the audio element (works best for playback)
        if ('captureStream' in this.botAudio) {
          this.botAudio.onplay = () => {
            if (this.botAnalyserSetup) return;
            try {
              const capturedStream = (this.botAudio as any).captureStream();
              const source = this.audioContext!.createMediaStreamSource(capturedStream);
              this.analyser = this.audioContext!.createAnalyser();
              this.analyser.fftSize = 256;
              this.analyser.smoothingTimeConstant = 0.5;
              source.connect(this.analyser);
              this.dataArray = new Uint8Array(this.analyser.frequencyBinCount);
              this.botAnalyserSetup = true;
              console.log('[BOT AUDIO] Analyser set up via captureStream');
            } catch (e) {
              console.warn('[BOT AUDIO] captureStream failed:', e);
            }
          };
        }

        // Method 2: Also try direct MediaStreamSource as backup
        const source = this.audioContext.createMediaStreamSource(stream);
        this.analyser = this.audioContext.createAnalyser();
        this.analyser.fftSize = 256;
        this.analyser.smoothingTimeConstant = 0.5;
        source.connect(this.analyser);
        this.dataArray = new Uint8Array(this.analyser.frequencyBinCount);
        console.log('[BOT AUDIO] Analyser set up via MediaStreamSource');
      }

      this.startAudioVisualization();
    } catch (e) {
      console.warn('Could not set up output audio visualization:', e);
    }
  }

  /**
   * Set up input audio track (user microphone) with visualization
   */
  private setupInputAudioTrack(track: MediaStreamTrack): void {
    this.log('Microphone audio track connected for visualization');

    try {
      if (!this.audioContext) {
        this.audioContext = new AudioContext();
      }

      const stream = new MediaStream([track]);
      const source = this.audioContext.createMediaStreamSource(stream);
      this.inputAnalyser = this.audioContext.createAnalyser();
      this.inputAnalyser.fftSize = 256;
      this.inputAnalyser.smoothingTimeConstant = 0.7;
      source.connect(this.inputAnalyser);
      this.inputDataArray = new Uint8Array(this.inputAnalyser.frequencyBinCount);

      this.log('Microphone analyser ready for Gemini-style visualization');
    } catch (e) {
      console.warn('Could not set up input audio visualization:', e);
    }
  }

  /**
   * Set up bot player analyser from transport's internal WavStreamPlayer
   * This gives us real frequency data for bot audio visualization
   */
  private setupBotPlayerAnalyser(): void {
    console.log('[BOT AUDIO] Setting up bot player analyser...');
    try {
      if (!this.transport) {
        console.warn('[BOT AUDIO] Transport not available');
        return;
      }
      console.log('[BOT AUDIO] Transport found:', this.transport);

      // Access the internal media manager and player
      // Note: This accesses internal properties which may change in future versions
      const mediaManager = (this.transport as any)._mediaManager;
      console.log('[BOT AUDIO] MediaManager:', mediaManager);
      if (!mediaManager) {
        console.warn('[BOT AUDIO] MediaManager not found on transport');
        // Log available properties on transport for debugging
        console.log('[BOT AUDIO] Transport properties:', Object.keys(this.transport));
        return;
      }

      const wavPlayer = mediaManager._wavStreamPlayer;
      console.log('[BOT AUDIO] WavStreamPlayer:', wavPlayer);
      if (!wavPlayer) {
        console.warn('[BOT AUDIO] WavStreamPlayer not found on media manager');
        // Log available properties for debugging
        console.log('[BOT AUDIO] MediaManager properties:', Object.keys(mediaManager));
        return;
      }

      // Store the player's AudioContext for speaker mute (suspend/resume)
      if (wavPlayer.context) {
        this.botPlayerContext = wavPlayer.context as AudioContext;
      }

      // Get the analyser from the player
      if (wavPlayer.analyser) {
        this.botPlayerAnalyser = wavPlayer.analyser as AnalyserNode;
        const freqBinCount = this.botPlayerAnalyser.frequencyBinCount;
        this.botPlayerDataArray = new Uint8Array(freqBinCount);
        console.log('[BOT AUDIO] ✅ Connected to WavStreamPlayer analyser - real frequency data available!');
        console.log('[BOT AUDIO] Frequency bins:', freqBinCount);
      } else {
        console.warn('[BOT AUDIO] Analyser not found on WavStreamPlayer (may not be connected yet)');

        // Try again after a short delay (player might connect later)
        setTimeout(() => {
          if (wavPlayer.analyser && !this.botPlayerAnalyser) {
            this.botPlayerAnalyser = wavPlayer.analyser as AnalyserNode;
            const freqBinCount = this.botPlayerAnalyser.frequencyBinCount;
            this.botPlayerDataArray = new Uint8Array(freqBinCount);
            console.log('[BOT AUDIO] ✅ Connected to WavStreamPlayer analyser (delayed)');
          }
        }, 1000);
      }
    } catch (e) {
      console.warn('[BOT AUDIO] Could not set up bot player analyser:', e);
    }
  }

  /**
   * Set up media tracks
   */
  private setupMediaTracks(): void {
    if (!this.rtviClient) return;
    const tracks = this.rtviClient.tracks();

    // Set up bot output audio
    if (tracks.bot?.audio) {
      this.setupAudioTrack(tracks.bot.audio);
    }

    // Set up local microphone input for visualization
    if (tracks.local?.audio) {
      this.localAudioTrack = tracks.local.audio;
      this.setupInputAudioTrack(tracks.local.audio);
    }
  }

  /**
   * Set up event listeners for RTVI
   */
  private setupTrackListeners(): void {
    if (!this.rtviClient) return;

    // Track events
    this.rtviClient.on(RTVIEvent.TrackStarted, (track, participant) => {
      if (track.kind === 'audio') {
        if (participant?.local) {
          // Local microphone track - for user voice visualization
          this.localAudioTrack = track;
          this.setupInputAudioTrack(track);
        } else {
          // Remote bot track - for AI voice visualization
          this.setupAudioTrack(track);
        }
      }
    });

    // Bot speech events
    this.rtviClient.on(RTVIEvent.BotStartedSpeaking, () => {
      this.log('Bot started speaking');
      // Note: Bot audio visualization uses simulated data since RTVI doesn't expose bot audio track
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

    // Listen for bot audio levels - this gives us real-time audio level data for visualization
    this.rtviClient.on(RTVIEvent.RemoteAudioLevel, (level: number) => {
      this.botAudioLevel = level;
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
   * Get LightRAG URL for knowledge graph queries
   */
  private getLightRAGUrl(): string {
    // @ts-ignore
    if (typeof import.meta !== 'undefined' && import.meta.env?.VITE_LIGHTRAG_URL) {
      // @ts-ignore
      return import.meta.env.VITE_LIGHTRAG_URL;
    }
    if ((window as any).__LIGHTRAG_URL__) {
      return (window as any).__LIGHTRAG_URL__;
    }
    return 'http://localhost:9621';
  }

  /**
   * Connect to voice server
   */
  public async connect(): Promise<void> {
    if (this.isConnecting || this.isConnected) return;

    this.isConnecting = true;
    this.setVoiceState('thinking');
    this.setCloseButtonEnabled(false); // Disable close until WebSocket is connected (or fails)

    this.addTerminalMessage('voice.scanner.connect();', 'command');
    this.addTerminalMessage('Establishing secure connection...', 'regular');

    try {
      const backendUrl = this.getBackendUrl();
      this.log(`Connecting to ${backendUrl}...`);

      this.transport = new WebSocketTransport();
      const config: RTVIClientOptions = {
        transport: this.transport,
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
            this.setCloseButtonEnabled(true); // WebSocket connected; allow close
            this.log('Connected successfully!');
            this.setVoiceState('listening');
            this.updateConnectionUI(true);
            this.addTerminalMessage('Connection established. Voice active.', 'success');
            this.showNotification('CONNECTION ESTABLISHED');

            // Set up bot player analyser after connection (with delay to ensure player is ready)
            setTimeout(() => {
              this.setupBotPlayerAnalyser();
            }, 500);
          },
          onDisconnected: () => {
            this.isConnecting = false;
            this.isConnected = false;
            this.rtviClient = null;
            this.setCloseButtonEnabled(true);
            this.log('Disconnected');
            this.setVoiceState('idle');
            this.updateConnectionUI(false);
            this.stopAudioVisualization();
            this.startIdleBlobAnimation(); // Keep wave animating in idle state
            this.addTerminalMessage('Connection terminated.', 'regular');
          },
          onBotReady: () => {
            this.log(`Bot ready`);
            this.setupMediaTracks();
            this.setupBotPlayerAnalyser(); // Set up real frequency analysis for bot audio
            this.addTerminalMessage('Voice AI initialized and ready.', 'success');
          },
          onUserTranscript: (data) => {
            console.log('User transcript:', data);
            if (data.final) {
              this.log(`You: ${data.text}`);
              // Finalize previous bot bubble before adding user message
              this.finalizeBotBubble();
              this.addTranscript(data.text, true);
              // Store query and reset accumulated answer for new turn
              this.lastUserQuery = data.text;
              this.accumulatedBotAnswer = '';
              // Clear A2UI from previous turn when new user query starts
              this.clearA2UI();
              // Stop any ongoing graph node cycling
              if ((window as any).KnowledgeGraph?.stopCycle) {
                (window as any).KnowledgeGraph.stopCycle();
              }
            }
          },
          onBotTranscript: (data) => {
            console.log('Bot transcript:', data);
            this.log(`Bot: ${data.text}`);
            // Use typewriter effect for bot transcript
            this.addBotTranscriptWithTypewriter(data.text);
            // Accumulate bot answer chunks
            this.accumulatedBotAnswer += ' ' + data.text;
            // Debounce highlight call - wait 500ms after last chunk
            if (this.graphHighlightTimeout) {
              clearTimeout(this.graphHighlightTimeout);
            }
            this.graphHighlightTimeout = setTimeout(() => {
              this.highlightGraphKeywords(this.lastUserQuery, this.accumulatedBotAnswer.trim());
            }, 500);
          },
          onError: (error) => {
            this.setCloseButtonEnabled(true); // Re-enable close on error
            const errorMsg = typeof error === 'object' ? JSON.stringify(error) : String(error);
            this.log(`Error: ${errorMsg}`);
            this.addTerminalMessage(errorMsg, 'error');
            console.error('RTVI Error:', error);
          },
          onServerMessage: (message) => {
            console.log('[Visual] Server message received:', JSON.stringify(message, null, 2));

            try {
              let messageData = null;
              let messageType = null;

              // Parse message structure (flexible - handles multiple formats)
              if (message && message.data) {
                messageType = message.data.message_type;
                messageData = message.data;
              } else if (message && message.message_type) {
                messageType = message.message_type;
                messageData = message;
              } else if (message && message.type === 'server-message' && message.data) {
                messageType = message.data.message_type;
                messageData = message.data;
              }

              console.log('[Visual] Parsed message type:', messageType);

              // Handle different message types
              switch (messageType) {
                case 'hybrid_emotion_detected':
                  console.log('[HYBRID EMOTION] Updating displays:', messageData);
                  this.updateHybridEmotionDisplay(messageData);
                  this.updateEmotionReactiveUI(messageData);
                  break;
                case 'emotion_detected':
                  console.log('[Emotion] Updating displays:', messageData);
                  this.updateEmotionDisplay(messageData);
                  this.updateEmotionReactiveUI(messageData);
                  break;
                case 'tone_switched':
                  console.log('[Tone] Switching to:', messageData.new_tone);
                  this.updateToneDisplay(messageData.new_tone);
                  break;
                case 'streaming_text':
                  console.log('[Streaming] Text received:', messageData.text, 'seq:', messageData.sequence_id);
                  this.handleStreamingText(messageData);
                  break;
                case 'visual_hint':
                  console.log('[Visual Hint] Received:', messageData.hint_type);
                  this.handleVisualHint(messageData);
                  break;
                case 'a2ui_update':
                  console.log('='.repeat(60));
                  console.log('🎨 [A2UI] *** A2UI_UPDATE MESSAGE RECEIVED ***');
                  console.log('   Raw messageData:', messageData);
                  console.log('   isA2UIUpdate check:', isA2UIUpdate(messageData));
                  if (isA2UIUpdate(messageData)) {
                    console.log('✅ [A2UI] Valid A2UI update - calling handleA2UIUpdate');
                    this.handleA2UIUpdate(messageData);
                  } else {
                    console.warn('⚠️ [A2UI] Invalid A2UI update format');
                    console.warn('   Expected: message_type="a2ui_update" and a2ui object');
                  }
                  console.log('='.repeat(60));
                  break;
              }
            } catch (e) {
              console.error('[Visual] Error handling server message:', e);
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
      this.setCloseButtonEnabled(true); // Re-enable close when connection fails
      this.log(`Connection failed: ${(error as Error).message}`);
      this.addTerminalMessage(`Connection failed: ${(error as Error).message}`, 'error');
      this.setVoiceState('idle');
      this.updateConnectionUI(false);

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
        this.inputAnalyser = null;
        this.dataArray = null;
        this.inputDataArray = null;
      }

      // Reset Gemini blob state
      this.smoothedAmplitude = 0;
      this.targetAmplitude = 0;

      this.stopAudioVisualization();
      this.startIdleBlobAnimation(); // Restart wave animation (idle) so it keeps running after close/restart

      // Clear A2UI display
      this.clearA2UI();

      // Clear topic timeline and history
      if (this.topicTimeline) {
        this.topicTimeline.clear();
      }
      this.previousTopics = [];

      this.isConnecting = false;
      this.isConnected = false;
      this.setVoiceState('idle');
      this.updateConnectionUI(false);
      this.log('Disconnected successfully');

    } catch (error) {
      this.log(`Disconnect error: ${(error as Error).message}`);
      this.isConnecting = false;
      this.isConnected = false;
      this.setVoiceState('idle');
      this.updateConnectionUI(false);
    }
  }

  // ===== STREAMING TRANSCRIPT METHODS =====

  /**
   * Handle streaming text events for word-by-word display
   */
  private handleStreamingText(data: {
    text: string;
    is_final: boolean;
    sequence_id: number;
    utterance_id: string;
    timestamp: number;
  }): void {
    // Start new utterance if needed
    if (data.utterance_id !== this.currentUtteranceId) {
      this.finalizeCurrentStreamingBubble();
      this.currentUtteranceId = data.utterance_id;
      this.streamingWords = [];
      this.createStreamingBubble();
    }

    // Add word with animation (skip empty final markers)
    if (data.text && data.text.trim()) {
      this.addStreamingWord(data.text, data.sequence_id);
    }

    // Finalize on is_final
    if (data.is_final) {
      this.finalizeCurrentStreamingBubble();
    }
  }

  /**
   * Create a new streaming transcript bubble
   */
  private createStreamingBubble(): void {
    if (!this.transcriptList) return;

    // Hide welcome message
    this.welcomeMessage?.classList.add('hidden');

    this.streamingBubble = document.createElement('div');
    this.streamingBubble.className = 'transcript-bubble bot streaming';

    const label = document.createElement('span');
    label.className = 'transcript-label';
    label.textContent = 'NesterAI: ';

    const textContainer = document.createElement('span');
    textContainer.className = 'transcript-text streaming-text';

    this.streamingBubble.appendChild(label);
    this.streamingBubble.appendChild(textContainer);
    this.transcriptList.appendChild(this.streamingBubble);
    this.transcriptList.scrollTop = this.transcriptList.scrollHeight;
  }

  /**
   * Add a word to the streaming bubble with animation
   */
  private addStreamingWord(word: string, sequenceId: number): void {
    if (!this.streamingBubble) return;

    const textContainer = this.streamingBubble.querySelector('.streaming-text');
    if (!textContainer) return;

    // Create word span with animation
    const wordSpan = document.createElement('span');
    wordSpan.className = 'streaming-word';
    wordSpan.textContent = word + ' ';
    wordSpan.style.animationDelay = `${(sequenceId % 10) * 30}ms`; // Stagger animation

    textContainer.appendChild(wordSpan);
    const isFirstWord = this.streamingWords.length === 0;
    this.streamingWords.push(word);

    // Live subtitle: append one word at a time (same typewriter effect as transcript)
    this.appendBotWordToLiveSubtitle(word, isFirstWord);

    // Auto-scroll
    if (this.transcriptList) {
      this.transcriptList.scrollTop = this.transcriptList.scrollHeight;
    }
  }

  /**
   * Finalize the current streaming bubble
   */
  private finalizeCurrentStreamingBubble(): void {
    if (this.streamingBubble) {
      // Subtitle already has words appended; just reset hide timer
      if (this.liveSubtitle && this.liveSubtitle.classList.contains('visible')) {
        if (this.subtitleClearTimeout) clearTimeout(this.subtitleClearTimeout);
        this.subtitleClearTimeout = setTimeout(() => {
          this.liveSubtitle?.classList.remove('visible');
        }, 4000);
      }

      this.streamingBubble.classList.remove('streaming');
      this.streamingBubble.classList.add('finalized');

      // Convert streaming words to static text for better performance
      const textContainer = this.streamingBubble.querySelector('.streaming-text');
      if (textContainer && this.streamingWords.length > 0) {
        textContainer.innerHTML = '';
        textContainer.textContent = this.streamingWords.join(' ');
      }
    }
    this.streamingBubble = null;
    this.currentUtteranceId = null;
    this.streamingWords = [];
  }

  // ===== VISUAL CARD METHODS =====

  /**
   * Handle visual hint events to display dynamic cards
   */
  private handleVisualHint(data: {
    hint_type: string;
    content_type: string;
    content: any;
    confidence: number;
    trigger_text: string;
    timestamp: number;
  }): void {
    // Remove existing card if present
    this.dismissVisualCard();

    // Create appropriate card based on hint_type
    switch (data.hint_type) {
      case 'greeting_animation':
        this.showGreetingAnimation();
        break;
      case 'contact_card':
        this.showContactCard(data.content);
        break;
      case 'service_card':
        this.showServiceCard(data.content);
        break;
      case 'pricing_card':
        this.showPricingCard(data.content);
        break;
      case 'project_card':
        this.showProjectCard(data.content);
        break;
      case 'project_detail_visualizing_intelligence':
        this.showProjectDetailCard('visualizing_intelligence');
        break;
      case 'project_detail_natural_conversations':
        this.showProjectDetailCard('natural_conversations');
        break;
      case 'project_detail_agentic_intake':
        this.showProjectDetailCard('agentic_intake');
        break;
      case 'project_detail_ai_first_bank':
        this.showProjectDetailCard('ai_first_bank');
        break;
      case 'expertise_card':
        this.showExpertiseCard(data.content);
        break;
      case 'company_card':
        this.showCompanyCard(data.content);
        break;
      case 'next_steps_card':
        this.showNextStepsCard(data.content);
        break;
      case 'location_card':
        this.showLocationCard(data.content);
        break;
    }

    // Log to terminal
    this.addTerminalMessage(`visual.hint({ type: '${data.hint_type}' });`, 'command');
  }

  /**
   * Show greeting animation on orb and display welcome card
   */
  private showGreetingAnimation(): void {
    // Trigger greeting animation on the orb
    this.orbContainer?.classList.add('greeting-pulse');

    // Show welcome visual overlay
    const card = this.createVisualCard('greeting-card');
    card.innerHTML = `
      <div class="greeting-animation">
        <div class="greeting-wave">
          <span class="wave-emoji">👋</span>
        </div>
        <div class="greeting-text">WELCOME TO NESTERLABS</div>
      </div>
    `;
    this.displayVisualCard(card, 3000); // Auto-dismiss after 3s

    setTimeout(() => {
      this.orbContainer?.classList.remove('greeting-pulse');
    }, 3000);
  }

  /**
   * Show contact information card with full details
   */
  private showContactCard(_content: { email?: string; phone?: string }): void {
    const card = this.createVisualCard('contact-card');
    card.innerHTML = `
      <div class="visual-card-header">
        <svg class="card-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/>
          <polyline points="22,6 12,13 2,6"/>
        </svg>
        <span>GET IN TOUCH</span>
      </div>
      <div class="visual-card-content">
        <div class="contact-grid">
          <div class="contact-method">
            <div class="contact-icon">📧</div>
            <div class="contact-details">
              <div class="contact-label">EMAIL</div>
              <div class="contact-value">contact@nesterlabs.com</div>
            </div>
          </div>
          <div class="contact-method">
            <div class="contact-icon">📞</div>
            <div class="contact-details">
              <div class="contact-label">PHONE</div>
              <div class="contact-value">+1 (408) 673-1340</div>
            </div>
          </div>
          <div class="contact-method">
            <div class="contact-icon">🌐</div>
            <div class="contact-details">
              <div class="contact-label">WEBSITE</div>
              <div class="contact-value">nesterlabs.com</div>
            </div>
          </div>
          <div class="contact-method">
            <div class="contact-icon">💼</div>
            <div class="contact-details">
              <div class="contact-label">LINKEDIN</div>
              <div class="contact-value">@nesterlabs</div>
            </div>
          </div>
        </div>
        <div class="contact-response-note">
          <span class="note-icon">⚡</span>
          <span>We respond within 24 business hours</span>
        </div>
      </div>
    `;
    this.displayVisualCard(card, 12000);
  }

  /**
   * Show services card with detailed four service pillars
   */
  private showServiceCard(_content: { services?: string[]; description?: string }): void {
    const card = this.createVisualCard('service-card');
    card.innerHTML = `
      <div class="visual-card-header">
        <svg class="card-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="10"/>
          <polygon points="10,8 16,12 10,16 10,8"/>
        </svg>
        <span>OUR SERVICES</span>
      </div>
      <div class="visual-card-content">
        <div class="services-detailed">
          <div class="service-detail-item">
            <div class="service-detail-header">
              <span class="service-emoji">👤</span>
              <span class="service-title">HUMAN</span>
            </div>
            <div class="service-detail-desc">User research, product design, voice & emotion design, brand identity</div>
            <div class="service-detail-outcome">
              <span class="outcome-label">Outcome:</span> Coherent, emotionally resonant experiences
            </div>
          </div>
          <div class="service-detail-item">
            <div class="service-detail-header">
              <span class="service-emoji">🧠</span>
              <span class="service-title">INTELLIGENCE</span>
            </div>
            <div class="service-detail-desc">Agentic AI, NLP engines, AI synthesis pipelines, conversational systems</div>
            <div class="service-detail-outcome">
              <span class="outcome-label">Outcome:</span> Systems that understand intent & respond in context
            </div>
          </div>
          <div class="service-detail-item">
            <div class="service-detail-header">
              <span class="service-emoji">📚</span>
              <span class="service-title">MEMORY</span>
            </div>
            <div class="service-detail-desc">Knowledge graphs, RAG pipelines, conversation analysis, privacy guardrails</div>
            <div class="service-detail-outcome">
              <span class="outcome-label">Outcome:</span> Reliable memory layer with security & privacy
            </div>
          </div>
          <div class="service-detail-item">
            <div class="service-detail-header">
              <span class="service-emoji">☁️</span>
              <span class="service-title">CLOUD</span>
            </div>
            <div class="service-detail-desc">Infrastructure security, compliance, DevOps, CI/CD for AI workloads</div>
            <div class="service-detail-outcome">
              <span class="outcome-label">Outcome:</span> Ship fast while staying secure & compliant
            </div>
          </div>
        </div>
      </div>
    `;
    this.displayVisualCard(card, 15000);
  }

  /**
   * Show pricing card with detailed engagement models
   */
  private showPricingCard(_content: { amounts?: string[] }): void {
    const card = this.createVisualCard('pricing-card');
    card.innerHTML = `
      <div class="visual-card-header">
        <svg class="card-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="12" y1="1" x2="12" y2="23"/>
          <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>
        </svg>
        <span>ENGAGEMENT MODELS</span>
      </div>
      <div class="visual-card-content">
        <div class="engagement-models">
          <div class="engagement-item">
            <div class="engagement-icon">🔍</div>
            <div class="engagement-info">
              <div class="engagement-name">DISCOVERY & STRATEGY</div>
              <div class="engagement-duration">2-4 weeks</div>
              <div class="engagement-desc">Understand problems & define clear path forward</div>
            </div>
          </div>
          <div class="engagement-item">
            <div class="engagement-icon">⚡</div>
            <div class="engagement-info">
              <div class="engagement-name">DESIGN SPRINTS</div>
              <div class="engagement-duration">1-2 weeks</div>
              <div class="engagement-desc">Solve specific problems or validate approaches</div>
            </div>
          </div>
          <div class="engagement-item">
            <div class="engagement-icon">🚀</div>
            <div class="engagement-info">
              <div class="engagement-name">PRODUCT DEVELOPMENT</div>
              <div class="engagement-duration">2-6 months+</div>
              <div class="engagement-desc">Design & build AI features, products, or platforms</div>
            </div>
          </div>
          <div class="engagement-item">
            <div class="engagement-icon">🔄</div>
            <div class="engagement-info">
              <div class="engagement-name">TIME & MATERIALS</div>
              <div class="engagement-duration">Flexible</div>
              <div class="engagement-desc">Scale up or down based on your priorities</div>
            </div>
          </div>
        </div>
        <div class="pricing-footer">
          <span class="footer-note">We work with startups to enterprises with realistic budgets</span>
        </div>
      </div>
    `;
    this.displayVisualCard(card, 15000);
  }

  /**
   * Show project card with detailed case studies
   */
  private showProjectCard(_content: { mentioned?: boolean }): void {
    const card = this.createVisualCard('project-card');
    card.innerHTML = `
      <div class="visual-card-header">
        <svg class="card-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
        </svg>
        <span>CASE STUDIES</span>
      </div>
      <div class="visual-card-content">
        <div class="project-showcase">
          <div class="project-case">
            <div class="case-header">
              <span class="case-icon">🎨</span>
              <div class="case-title-wrap">
                <div class="case-title">Visualizing Intelligence</div>
                <div class="case-industry">AI & Technology Studio</div>
              </div>
            </div>
            <div class="case-challenge">Brand & web to communicate complex AI work</div>
            <div class="case-outcome">Cohesive identity enabling confident stakeholder conversations</div>
          </div>
          <div class="project-case">
            <div class="case-header">
              <span class="case-icon">💬</span>
              <div class="case-title-wrap">
                <div class="case-title">Natural Conversations</div>
                <div class="case-industry">Data Platforms & Analytics</div>
              </div>
            </div>
            <div class="case-challenge">Users struggling with dashboards & query languages</div>
            <div class="case-outcome">Plain language data queries → faster decision-making</div>
          </div>
          <div class="project-case">
            <div class="case-header">
              <span class="case-icon">🤖</span>
              <div class="case-title-wrap">
                <div class="case-title">Agentic Intake Coordinator</div>
                <div class="case-industry">Operations & Workflows</div>
              </div>
            </div>
            <div class="case-challenge">Manual back-and-forth intake processes</div>
            <div class="case-outcome">Voice AI streamlines intake with cleaner data</div>
          </div>
          <div class="project-case coming-soon">
            <div class="case-header">
              <span class="case-icon">🏦</span>
              <div class="case-title-wrap">
                <div class="case-title">AI First Bank</div>
                <div class="case-industry">Financial Services</div>
              </div>
            </div>
            <div class="case-challenge">Rigid, transactional banking experiences</div>
            <div class="case-badge">COMING SOON</div>
          </div>
        </div>
      </div>
    `;
    this.displayVisualCard(card, 18000);
  }

  /**
   * Show detailed project card for a specific case study
   */
  private showProjectDetailCard(projectId: string): void {
    const projects: Record<string, {
      title: string;
      industry: string;
      badge?: string;
      challenge: string;
      solution: string;
      outcome: string;
      deliverables: string[];
      signals: string[];
      icon: string;
    }> = {
      visualizing_intelligence: {
        title: 'Visualizing Intelligence',
        industry: 'AI & Technology Studio',
        challenge: 'Communicate complex AI work in a way that feels inspiring, clear, and trustworthy.',
        solution: 'Strategy, visual identity, and a web experience that makes the story easy to grasp at a glance.',
        outcome: 'Cohesive brand and site that unlocks confident conversations with partners and stakeholders.',
        deliverables: ['Strategy', 'Identity System', 'Web Experience'],
        signals: ['Narrative Clarity', 'Trust & Credibility', 'Stakeholder Confidence'],
        icon: '🎨',
      },
      natural_conversations: {
        title: 'Natural Conversations with Data',
        industry: 'Data Platforms & Analytics',
        challenge: 'Users struggled with dashboards and query languages to access insights.',
        solution: 'Natural language interface with intent understanding, guided questions, and clear answer formats.',
        outcome: 'Faster decision-making and broader adoption by non-technical users.',
        deliverables: ['Conversational UI', 'Intent Mapping', 'Answer Cards'],
        signals: ['Plain Language', 'Guided Queries', 'Faster Insights'],
        icon: '💬',
      },
      agentic_intake: {
        title: 'Agentic Intake Coordinator',
        industry: 'Operations & Workflows',
        challenge: 'Manual back-and-forth intake created slow, inconsistent handoffs.',
        solution: 'Conversational AI that listens, clarifies, and structures inputs for downstream teams.',
        outcome: 'Faster intake, smoother user experience, and cleaner structured data.',
        deliverables: ['Voice Flow', 'Clarification Logic', 'Structured Output'],
        signals: ['Automation', 'Clarity', 'Structured Data'],
        icon: '🤖',
      },
      ai_first_bank: {
        title: 'AI First Bank',
        industry: 'Financial Services',
        badge: 'COMING SOON',
        challenge: 'Traditional banking feels rigid, transactional, and disconnected from real goals.',
        solution: 'Conversational finance experience with context, personalization, and proactive guidance.',
        outcome: 'A partner-like banking experience that sets a new bar for AI in finance.',
        deliverables: ['Conversational Journeys', 'Context Memory', 'Proactive Insights'],
        signals: ['Personalized', 'Proactive', 'Trusted'],
        icon: '🏦',
      },
    };

    const project = projects[projectId] ?? projects.visualizing_intelligence;
    const card = this.createVisualCard('project-detail-card');

    card.innerHTML = `
      <div class="visual-card-header">
        <svg class="card-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
        </svg>
        <span>PROJECT DETAILS</span>
      </div>
      <div class="visual-card-content">
        <div class="project-detail-hero">
          <div class="project-detail-icon">${project.icon}</div>
          <div class="project-detail-main">
            <div class="project-detail-title">${project.title}</div>
            <div class="project-detail-industry">${project.industry}</div>
          </div>
          ${project.badge ? `<div class="project-detail-badge">${project.badge}</div>` : ''}
        </div>

        <div class="project-detail-sections">
          <div class="detail-section">
            <div class="detail-label">Challenge</div>
            <div class="detail-text">${project.challenge}</div>
          </div>
          <div class="detail-section">
            <div class="detail-label">Solution</div>
            <div class="detail-text">${project.solution}</div>
          </div>
          <div class="detail-section">
            <div class="detail-label">Outcome</div>
            <div class="detail-text detail-outcome">${project.outcome}</div>
          </div>
        </div>

        <div class="project-detail-grid">
          <div class="detail-panel">
            <div class="panel-title">Deliverables</div>
            <div class="panel-list">
              ${project.deliverables.map((item) => `<span class="panel-pill">${item}</span>`).join('')}
            </div>
          </div>
          <div class="detail-panel">
            <div class="panel-title">Key Signals</div>
            <div class="panel-list">
              ${project.signals.map((item) => `<span class="panel-pill accent">${item}</span>`).join('')}
            </div>
          </div>
        </div>

        <div class="project-detail-flow">
          <div class="flow-step">Discovery</div>
          <div class="flow-line"></div>
          <div class="flow-step">Design</div>
          <div class="flow-line"></div>
          <div class="flow-step">Delivery</div>
        </div>
      </div>
    `;

    this.displayVisualCard(card, 20000);
  }

  /**
   * Show expertise card with technical capabilities
   */
  private showExpertiseCard(_content: Record<string, unknown>): void {
    const card = this.createVisualCard('expertise-card');
    card.innerHTML = `
      <div class="visual-card-header">
        <svg class="card-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polygon points="12,2 15.09,8.26 22,9.27 17,14.14 18.18,21.02 12,17.77 5.82,21.02 7,14.14 2,9.27 8.91,8.26"/>
        </svg>
        <span>EXPERTISE AREAS</span>
      </div>
      <div class="visual-card-content">
        <div class="expertise-grid">
          <div class="expertise-item">
            <div class="expertise-icon">🎙️</div>
            <div class="expertise-name">Voice AI & Conversational</div>
            <div class="expertise-desc">Natural dialogues, voice tone, emotional awareness</div>
          </div>
          <div class="expertise-item">
            <div class="expertise-icon">🤖</div>
            <div class="expertise-name">Agentic AI & Orchestration</div>
            <div class="expertise-desc">Multi-capability systems for complex workflows</div>
          </div>
          <div class="expertise-item">
            <div class="expertise-icon">📊</div>
            <div class="expertise-name">RAG & Context Engineering</div>
            <div class="expertise-desc">Grounding AI in the right information at the right time</div>
          </div>
          <div class="expertise-item">
            <div class="expertise-icon">💭</div>
            <div class="expertise-name">Natural Language Processing</div>
            <div class="expertise-desc">Intent recognition & contextual response generation</div>
          </div>
          <div class="expertise-item">
            <div class="expertise-icon">✨</div>
            <div class="expertise-name">AI-First Product Design</div>
            <div class="expertise-desc">UX research & design for AI-native experiences</div>
          </div>
          <div class="expertise-item">
            <div class="expertise-icon">🔗</div>
            <div class="expertise-name">Knowledge Graphs & Memory</div>
            <div class="expertise-desc">Consistent info with privacy guardrails</div>
          </div>
        </div>
        <div class="expertise-footer">
          <span>85+ years combined team experience</span>
        </div>
      </div>
    `;
    this.displayVisualCard(card, 15000);
  }

  /**
   * Show company overview card
   */
  private showCompanyCard(_content: Record<string, unknown>): void {
    const card = this.createVisualCard('company-card');
    card.innerHTML = `
      <div class="visual-card-header">
        <svg class="card-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>
          <polyline points="9,22 9,12 15,12 15,22"/>
        </svg>
        <span>ABOUT NESTERLABS</span>
      </div>
      <div class="visual-card-content">
        <div class="company-overview">
          <div class="company-tagline">AI-Accelerated Product Studio</div>
          <div class="company-desc">
            Reimagining intelligence through research, design, and technology. We help companies make advanced technologies usable, legible, and effective inside real products.
          </div>
          <div class="company-stats">
            <div class="stat-item">
              <div class="stat-value">85+</div>
              <div class="stat-label">Years Combined Experience</div>
            </div>
            <div class="stat-item">
              <div class="stat-value">SF Bay</div>
              <div class="stat-label">Area Based</div>
            </div>
            <div class="stat-item">
              <div class="stat-value">E2E</div>
              <div class="stat-label">Research to Deploy</div>
            </div>
          </div>
          <div class="company-clients">
            <span class="clients-label">Clients:</span> Early-stage startups to large enterprises
          </div>
        </div>
      </div>
    `;
    this.displayVisualCard(card, 12000);
  }

  /**
   * Show next steps card for engagement flow
   */
  private showNextStepsCard(_content: Record<string, unknown>): void {
    const card = this.createVisualCard('next-steps-card');
    card.innerHTML = `
      <div class="visual-card-header">
        <svg class="card-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="9,18 15,12 9,6"/>
        </svg>
        <span>WHAT HAPPENS NEXT</span>
      </div>
      <div class="visual-card-content">
        <div class="steps-timeline">
          <div class="step-item">
            <div class="step-number">1</div>
            <div class="step-info">
              <div class="step-title">Initial Response</div>
              <div class="step-desc">We respond within 1-2 business days</div>
            </div>
          </div>
          <div class="step-item">
            <div class="step-number">2</div>
            <div class="step-info">
              <div class="step-title">Discovery Call</div>
              <div class="step-desc">30-45 min to understand goals, constraints & timeline</div>
            </div>
          </div>
          <div class="step-item">
            <div class="step-number">3</div>
            <div class="step-info">
              <div class="step-title">Tailored Proposal</div>
              <div class="step-desc">Scope, approach, timeline & pricing</div>
            </div>
          </div>
          <div class="step-item">
            <div class="step-number">4</div>
            <div class="step-info">
              <div class="step-title">Kickoff</div>
              <div class="step-desc">Align on goals & start deep work within 1-2 weeks</div>
            </div>
          </div>
        </div>
        <div class="steps-cta">
          Ready to start? Let's talk!
        </div>
      </div>
    `;
    this.displayVisualCard(card, 15000);
  }

  /**
   * Show location card with office details
   */
  private showLocationCard(_content: Record<string, unknown>): void {
    const card = this.createVisualCard('location-card');
    card.innerHTML = `
      <div class="visual-card-header">
        <svg class="card-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/>
          <circle cx="12" cy="10" r="3"/>
        </svg>
        <span>VISIT US</span>
      </div>
      <div class="visual-card-content">
        <div class="location-details">
          <div class="location-address">
            <div class="address-icon">🏢</div>
            <div class="address-text">
              <div class="address-line">701 Lakeway Dr #200</div>
              <div class="address-line">Sunnyvale, CA 94085</div>
            </div>
          </div>
          <div class="location-region">
            <span class="region-badge">SF Bay Area</span>
            <span class="region-note">Silicon Valley</span>
          </div>
          <div class="location-hours">
            <div class="hours-icon">🕐</div>
            <div class="hours-text">
              <div class="hours-label">Business Hours (PST)</div>
              <div class="hours-note">In-person meetings by appointment</div>
            </div>
          </div>
        </div>
      </div>
    `;
    this.displayVisualCard(card, 10000);
  }

  /**
   * Create a visual card element
   */
  private createVisualCard(className: string): HTMLElement {
    const card = document.createElement('div');
    card.className = `visual-card ${className}`;
    return card;
  }

  /**
   * Display a visual card with optional auto-dismiss
   */
  private displayVisualCard(card: HTMLElement, autoDismissMs?: number): void {
    console.log('[Visual Card] Displaying card:', card.className);

    // Get or create visual cards container
    if (!this.visualCardsContainer) {
      this.visualCardsContainer = document.getElementById('visual-cards-container');
      console.log('[Visual Card] Container from DOM:', this.visualCardsContainer);
      if (!this.visualCardsContainer) {
        this.visualCardsContainer = document.createElement('div');
        this.visualCardsContainer.id = 'visual-cards-container';
        document.querySelector('.interface-container')?.appendChild(this.visualCardsContainer);
        console.log('[Visual Card] Created new container');
      }
    }

    // Add close button to card (except greeting cards)
    if (!card.classList.contains('greeting-card')) {
      const closeBtn = document.createElement('button');
      closeBtn.className = 'card-close';
      closeBtn.innerHTML = '×';
      closeBtn.onclick = (e) => {
        e.stopPropagation();
        this.dismissVisualCard();
      };
      card.appendChild(closeBtn);
    }

    this.visualCardsContainer.appendChild(card);
    this.activeVisualCard = card;

    // Force a reflow before adding the visible class
    void card.offsetWidth;

    // Animate in with a small delay to ensure DOM is ready
    setTimeout(() => {
      card.classList.add('visible');
    }, 50);

    // Auto-dismiss if specified
    if (autoDismissMs) {
      setTimeout(() => this.dismissVisualCard(), autoDismissMs);
    }
  }

  /**
   * Dismiss the active visual card
   */
  private dismissVisualCard(): void {
    if (this.activeVisualCard) {
      this.activeVisualCard.classList.remove('visible');
      this.activeVisualCard.classList.add('dismissing');
      const card = this.activeVisualCard;
      setTimeout(() => {
        card.remove();
      }, 300);
      this.activeVisualCard = null;
    }
  }

  // ===== A2UI RENDERING METHODS =====

  /**
   * Initialize the A2UI renderer
   */
  private initializeA2UIRenderer(): void {
    console.log('='.repeat(60));
    console.log('🎨 [A2UI] Initializing A2UI Renderer...');
    try {
      this.a2uiRenderer = new A2UIRenderer('a2ui-container');
      this.log('A2UI renderer initialized');
      this.addTerminalMessage('a2ui.renderer.init();', 'command');
      console.log('✅ [A2UI] A2UIRenderer created successfully');
      console.log('   Panel element:', this.a2uiPanel);
      console.log('   Status element:', this.a2uiStatus);
      console.log('='.repeat(60));
    } catch (error) {
      console.error('='.repeat(60));
      console.error('❌ [A2UI] Failed to initialize A2UI renderer:', error);
      console.error('='.repeat(60));
      this.log('A2UI renderer initialization failed');
    }
  }

  /**
   * Handle A2UI update events from the backend
   */
  private handleA2UIUpdate(data: {
    a2ui: A2UIDocument;
    query?: string;
    tier?: string;
    template_type?: string;
    timestamp?: number;
  }): void {
    console.log('='.repeat(60));
    console.log('🎨 [A2UI] handleA2UIUpdate CALLED');
    console.log('   Full data received:', data);
    console.log('   Renderer exists:', !!this.a2uiRenderer);
    console.log('   A2UI doc exists:', !!data.a2ui);
    
    if (!this.a2uiRenderer || !data.a2ui) {
      console.warn('⚠️ [A2UI] Renderer not available or no A2UI data');
      console.warn('   Renderer:', this.a2uiRenderer);
      console.warn('   Data:', data);
      console.log('='.repeat(60));
      return;
    }

    const templateType = data.a2ui.root?.type || 'unknown';
    const tier = data.tier || data.a2ui._metadata?.tier || 'auto';
    const tierName = data.a2ui._metadata?.tier_name || 'unknown';
    
    console.log('📋 [A2UI] Document details:');
    console.log(`   Template type: ${templateType}`);
    console.log(`   Tier: ${tier} (${tierName})`);
    console.log(`   Query: ${data.query || 'N/A'}`);
    console.log(`   Timestamp: ${data.timestamp}`);

    // Update status indicator
    if (this.a2uiStatus) {
      this.a2uiStatus.textContent = 'RENDERING';
      this.a2uiStatus.classList.add('active');
      console.log('📊 [A2UI] Status updated to RENDERING');
    }

    // Show the A2UI panel if hidden
    if (this.a2uiPanel) {
      this.a2uiPanel.classList.add('visible');
      console.log('📺 [A2UI] Panel made visible');
    }

    try {
      console.log('🔄 [A2UI] Calling renderer.render()...');
      // Render the A2UI document
      this.a2uiRenderer.render(data.a2ui);

      // Log to terminal
      this.addTerminalMessage(`a2ui.render({ type: '${templateType}', tier: '${tier}' });`, 'command');
      this.log(`A2UI rendered: ${templateType} (${tier})`);
      
      console.log('✅ [A2UI] Render completed successfully!');

      // Update status after render
      setTimeout(() => {
        if (this.a2uiStatus) {
          this.a2uiStatus.textContent = 'READY';
          this.a2uiStatus.classList.remove('active');
          console.log('📊 [A2UI] Status updated to READY');
        }
      }, 500);

    } catch (error) {
      console.error('❌ [A2UI] Render error:', error);
      this.addTerminalMessage(`a2ui.error: ${(error as Error).message}`, 'error');

      if (this.a2uiStatus) {
        this.a2uiStatus.textContent = 'ERROR';
        this.a2uiStatus.classList.remove('active');
      }
    }
    console.log('='.repeat(60));
  }

  /**
   * Clear the A2UI display
   */
  private clearA2UI(): void {
    if (this.a2uiRenderer) {
      this.a2uiRenderer.clear();
    }
    if (this.a2uiStatus) {
      this.a2uiStatus.textContent = 'READY';
    }
  }

  /**
   * Hide the A2UI panel
   */
  private hideA2UIPanel(): void {
    if (this.a2uiPanel) {
      this.a2uiPanel.classList.remove('visible');
    }
  }

  /**
   * Show the A2UI panel
   */
  private showA2UIPanel(): void {
    if (this.a2uiPanel) {
      this.a2uiPanel.classList.add('visible');
    }
  }

  // ===== EMOTION-REACTIVE UI METHODS =====

  /**
   * Update UI colors and animations based on emotion state
   */
  private updateEmotionReactiveUI(data: {
    arousal?: number;
    valence?: number;
    primary_emotion?: string;
    emotion?: string;
  }): void {
    // Debounce updates
    const now = Date.now();
    if (now - this.lastEmotionUpdate < this.emotionUpdateDebounceMs) {
      return;
    }
    this.lastEmotionUpdate = now;

    const emotion = data.primary_emotion || data.emotion || 'neutral';
    const arousal = data.arousal ?? 0.5;
    const valence = data.valence ?? 0.5;

    // Update CSS custom properties for emotion colors
    const root = document.documentElement;

    const emotionColors: Record<string, { primary: string; secondary: string; glow: string }> = {
      'neutral': { primary: '#37b6ff', secondary: '#9747ff', glow: 'rgba(55, 182, 255, 0.4)' },
      'happy': { primary: '#10b981', secondary: '#34d399', glow: 'rgba(16, 185, 129, 0.4)' },
      'excited': { primary: '#f59e0b', secondary: '#fbbf24', glow: 'rgba(245, 158, 11, 0.4)' },
      'sad': { primary: '#3b82f6', secondary: '#60a5fa', glow: 'rgba(59, 130, 246, 0.4)' },
      'frustrated': { primary: '#ef4444', secondary: '#f87171', glow: 'rgba(239, 68, 68, 0.4)' },
      'calm': { primary: '#06b6d4', secondary: '#22d3ee', glow: 'rgba(6, 182, 212, 0.4)' },
    };

    const colors = emotionColors[emotion] || emotionColors['neutral'];

    // Apply emotion colors to orb and UI elements
    root.style.setProperty('--emotion-primary', colors.primary);
    root.style.setProperty('--emotion-secondary', colors.secondary);
    root.style.setProperty('--emotion-glow', colors.glow);

    // Adjust animation speed based on arousal (0.75x to 1.25x)
    const animationSpeed = 1 + (arousal - 0.5) * 0.5;
    root.style.setProperty('--emotion-animation-speed', `${animationSpeed}`);

    // Update orb container data attribute for CSS styling
    this.orbContainer?.setAttribute('data-emotion', emotion);

    // Update scanner frame border based on valence
    if (this.scannerFrame) {
      if (valence > 0.6) {
        this.scannerFrame.style.borderColor = colors.primary;
      } else if (valence < 0.4) {
        this.scannerFrame.style.borderColor = colors.secondary;
      } else {
        this.scannerFrame.style.borderColor = '';
      }
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
  const app = new VoiceScannerApp();
  (window as any).voiceScannerApp = app; // e.g. voiceScannerApp.setLoaderText('Planning next moves')
});

