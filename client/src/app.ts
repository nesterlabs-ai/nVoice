/**
 * Copyright (c) 2024–2025, Daily
 *
 * SPDX-License-Identifier: BSD 2-Clause License
 */

/**
 * Nester AI Voice Assistant - Modern Floating UI
 *
 * This client connects to an RTVI-compatible bot server using WebSocket.
 * Features a modern floating design with animated voice orb and visual feedback.
 */

import {
  RTVIClient,
  RTVIClientOptions,
  RTVIEvent,
} from '@pipecat-ai/client-js';
import {
  WebSocketTransport
} from "@pipecat-ai/websocket-transport";

type OrbState = 'idle' | 'connecting' | 'listening' | 'speaking' | 'processing';

class VoiceAssistantApp {
  private rtviClient: RTVIClient | null = null;

  // UI Elements
  private connectBtn: HTMLButtonElement | null = null;
  private btnText: HTMLElement | null = null;
  private statusBadge: HTMLElement | null = null;
  private statusText: HTMLElement | null = null;
  private voiceOrbContainer: HTMLElement | null = null;
  private orbLabel: HTMLElement | null = null;
  private debugPanel: HTMLElement | null = null;
  private debugLog: HTMLElement | null = null;
  private debugToggle: HTMLElement | null = null;
  private debugClose: HTMLElement | null = null;
  private userTranscript: HTMLElement | null = null;
  private botTranscript: HTMLElement | null = null;
  private userText: HTMLElement | null = null;
  private botText: HTMLElement | null = null;

  // Audio elements
  private botAudio: HTMLAudioElement;
  private audioContext: AudioContext | null = null;
  private audioAnalyzer: AnalyserNode | null = null;
  private vizBars: HTMLElement[] = [];
  private animationFrameId: number | null = null;

  // State
  private isConnected: boolean = false;
  private isConnecting: boolean = false;
  private currentState: OrbState = 'idle';
  private isBotSpeaking: boolean = false;

  constructor() {
    console.log("Nester AI Voice Assistant Initializing...");
    this.botAudio = document.createElement('audio');
    this.botAudio.autoplay = true;
    document.body.appendChild(this.botAudio);

    this.setupDOMElements();
    this.setupEventListeners();
    this.initializeState();
  }

  /**
   * Set up references to DOM elements
   */
  private setupDOMElements(): void {
    // Header elements
    this.statusBadge = document.getElementById('status-badge');
    this.statusText = this.statusBadge?.querySelector('.status-text') || null;

    // Voice orb elements
    this.voiceOrbContainer = document.getElementById('voice-orb-container');
    this.orbLabel = document.getElementById('orb-label');

    // Control elements
    this.connectBtn = document.getElementById('connect-btn') as HTMLButtonElement;
    this.btnText = this.connectBtn?.querySelector('.btn-text') || null;

    // Debug elements
    this.debugPanel = document.getElementById('debug-panel');
    this.debugLog = document.getElementById('debug-log');
    this.debugToggle = document.getElementById('debug-toggle');
    this.debugClose = document.getElementById('debug-close');

    // Transcript elements
    this.userTranscript = document.getElementById('user-transcript');
    this.botTranscript = document.getElementById('bot-transcript');
    this.userText = document.getElementById('user-text');
    this.botText = document.getElementById('bot-text');

    // Visualizer bars
    const vizContainer = document.getElementById('orb-visualizer');
    if (vizContainer) {
      this.vizBars = Array.from(vizContainer.querySelectorAll('.viz-bar'));
    }
  }

  /**
   * Set up event listeners for interactive elements
   */
  private setupEventListeners(): void {
    // Connect button
    this.connectBtn?.addEventListener('click', () => this.toggleConnection());

    // Voice orb click (same as connect button)
    this.voiceOrbContainer?.addEventListener('click', () => {
      if (!this.isConnecting) {
        this.toggleConnection();
      }
    });

    // Debug panel toggle
    this.debugToggle?.addEventListener('click', () => this.toggleDebugPanel());
    this.debugClose?.addEventListener('click', () => this.hideDebugPanel());
  }

  /**
   * Initialize the UI state
   */
  private initializeState(): void {
    this.setOrbState('idle');
    this.updateConnectionUI(false);
  }

  /**
   * Set the orb visual state
   */
  private setOrbState(state: OrbState): void {
    this.currentState = state;

    if (!this.voiceOrbContainer) return;

    // Remove all state classes
    this.voiceOrbContainer.classList.remove('idle', 'connecting', 'listening', 'speaking', 'processing');

    // Add current state class
    this.voiceOrbContainer.classList.add(state);

    // Update label
    if (this.orbLabel) {
      switch (state) {
        case 'idle':
          this.orbLabel.textContent = 'Tap to start';
          break;
        case 'connecting':
          this.orbLabel.textContent = 'Connecting...';
          break;
        case 'listening':
          this.orbLabel.textContent = 'Listening...';
          break;
        case 'speaking':
          this.orbLabel.textContent = 'Speaking...';
          break;
        case 'processing':
          this.orbLabel.textContent = 'Processing...';
          break;
      }
    }
  }

  /**
   * Update UI based on connection state
   */
  private updateConnectionUI(connected: boolean): void {
    this.isConnected = connected;

    // Update status badge
    if (this.statusBadge) {
      if (connected) {
        this.statusBadge.classList.add('connected');
      } else {
        this.statusBadge.classList.remove('connected');
      }
    }

    if (this.statusText) {
      this.statusText.textContent = connected ? 'Online' : 'Offline';
    }

    // Update connect button
    if (this.connectBtn) {
      if (connected) {
        this.connectBtn.classList.add('connected');
      } else {
        this.connectBtn.classList.remove('connected');
      }
    }

    if (this.btnText) {
      this.btnText.textContent = connected ? 'End Conversation' : 'Start Conversation';
    }

    // Update orb state
    if (!connected && !this.isConnecting) {
      this.setOrbState('idle');
      this.hideTranscripts();
    }
  }

  /**
   * Toggle connection state
   */
  private async toggleConnection(): Promise<void> {
    if (this.isConnected) {
      await this.disconnect();
    } else {
      await this.connect();
    }
  }

  /**
   * Toggle debug panel visibility
   */
  private toggleDebugPanel(): void {
    if (this.debugPanel) {
      this.debugPanel.classList.toggle('visible');
    }
  }

  /**
   * Hide debug panel
   */
  private hideDebugPanel(): void {
    if (this.debugPanel) {
      this.debugPanel.classList.remove('visible');
    }
  }

  /**
   * Show user transcript
   */
  private showUserTranscript(text: string): void {
    if (this.userText) {
      this.userText.textContent = text;
    }
    if (this.userTranscript) {
      this.userTranscript.classList.add('visible');
    }
  }

  /**
   * Show bot transcript
   */
  private showBotTranscript(text: string): void {
    if (this.botText) {
      this.botText.textContent = text;
    }
    if (this.botTranscript) {
      this.botTranscript.classList.add('visible');
    }
  }

  /**
   * Hide all transcripts
   */
  private hideTranscripts(): void {
    this.userTranscript?.classList.remove('visible');
    this.botTranscript?.classList.remove('visible');
    if (this.userText) this.userText.textContent = '';
    if (this.botText) this.botText.textContent = '';
  }

  /**
   * Add a timestamped message to the debug log
   */
  private log(message: string): void {
    if (!this.debugLog) return;
    const entry = document.createElement('div');
    const time = new Date().toLocaleTimeString();
    entry.textContent = `[${time}] ${message}`;

    // Color coding for different message types
    if (message.startsWith('You:') || message.startsWith('User:')) {
      entry.style.color = '#818cf8'; // Accent color
    } else if (message.startsWith('Bot:')) {
      entry.style.color = '#ff8e8e'; // Primary color
    } else if (message.includes('Error') || message.includes('error')) {
      entry.style.color = '#ef4444'; // Red
    } else if (message.includes('Connected') || message.includes('success')) {
      entry.style.color = '#22c55e'; // Green
    }

    this.debugLog.appendChild(entry);
    this.debugLog.scrollTop = this.debugLog.scrollHeight;
    console.log(message);
  }

  /**
   * Set up audio track for playback and visualization
   */
  private setupAudioTrack(track: MediaStreamTrack): void {
    this.log('Setting up audio track');

    if (this.botAudio.srcObject && "getAudioTracks" in this.botAudio.srcObject) {
      const oldTrack = this.botAudio.srcObject.getAudioTracks()[0];
      if (oldTrack?.id === track.id) return;
    }

    const stream = new MediaStream([track]);
    this.botAudio.srcObject = stream;

    // Set up audio analyzer for visualization
    this.setupAudioAnalyzer(stream);
  }

  /**
   * Set up audio analyzer for visualizer
   */
  private setupAudioAnalyzer(stream: MediaStream): void {
    try {
      if (!this.audioContext) {
        this.audioContext = new (window.AudioContext || (window as any).webkitAudioContext)();
      }

      const source = this.audioContext.createMediaStreamSource(stream);
      this.audioAnalyzer = this.audioContext.createAnalyser();
      this.audioAnalyzer.fftSize = 32;

      source.connect(this.audioAnalyzer);

      // Start visualization loop
      this.startVisualization();
    } catch (e) {
      this.log(`Audio analyzer setup failed: ${e}`);
    }
  }

  /**
   * Start audio visualization
   */
  private startVisualization(): void {
    if (!this.audioAnalyzer || this.vizBars.length === 0) return;

    const bufferLength = this.audioAnalyzer.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);

    const animate = () => {
      this.animationFrameId = requestAnimationFrame(animate);

      if (!this.audioAnalyzer || !this.isBotSpeaking) return;

      this.audioAnalyzer.getByteFrequencyData(dataArray);

      // Map frequency data to visualizer bars
      const step = Math.floor(bufferLength / this.vizBars.length);
      this.vizBars.forEach((bar, i) => {
        const value = dataArray[i * step] || 0;
        const height = Math.max(20, (value / 255) * 60);
        bar.style.height = `${height}px`;
      });
    };

    animate();
  }

  /**
   * Stop audio visualization
   */
  private stopVisualization(): void {
    if (this.animationFrameId) {
      cancelAnimationFrame(this.animationFrameId);
      this.animationFrameId = null;
    }

    // Reset bars to idle state
    this.vizBars.forEach(bar => {
      bar.style.height = '20px';
    });
  }

  /**
   * Handle bot speaking state
   */
  private setBotSpeaking(speaking: boolean): void {
    this.isBotSpeaking = speaking;

    if (speaking) {
      this.setOrbState('speaking');
    } else if (this.isConnected) {
      this.setOrbState('listening');
    }
  }

  /**
   * Check for available media tracks
   */
  private setupMediaTracks(): void {
    if (!this.rtviClient) return;
    const tracks = this.rtviClient.tracks();
    if (tracks.bot?.audio) {
      this.setupAudioTrack(tracks.bot.audio);
    }
  }

  /**
   * Set up track event listeners
   */
  private setupTrackListeners(): void {
    if (!this.rtviClient) return;

    this.rtviClient.on(RTVIEvent.TrackStarted, (track, participant) => {
      if (!participant?.local && track.kind === 'audio') {
        this.setupAudioTrack(track);
      }
    });

    this.rtviClient.on(RTVIEvent.TrackStopped, (track, participant) => {
      this.log(`Track stopped: ${track.kind} from ${participant?.name || 'bot'}`);
    });

    // Bot speech events
    this.rtviClient.on(RTVIEvent.BotStartedSpeaking, () => {
      this.log('Bot started speaking');
      this.setBotSpeaking(true);
    });

    this.rtviClient.on(RTVIEvent.BotStoppedSpeaking, () => {
      this.log('Bot stopped speaking');
      this.setBotSpeaking(false);
    });

    // User speech events
    this.rtviClient.on(RTVIEvent.UserStartedSpeaking, () => {
      this.log('User started speaking');
      if (this.isBotSpeaking) {
        this.setBotSpeaking(false);
      }
      this.setOrbState('listening');
    });

    this.rtviClient.on(RTVIEvent.UserStoppedSpeaking, () => {
      this.log('User stopped speaking');
      this.setOrbState('processing');
    });
  }

  /**
   * Get the backend URL from environment or config
   */
  private getBackendUrl(): string {
    // @ts-ignore - Vite injects this at build time
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
   * Connect to the bot server
   */
  public async connect(): Promise<void> {
    if (this.isConnecting) {
      this.log('Connection already in progress...');
      return;
    }

    if (this.isConnected || this.rtviClient) {
      this.log('Already connected. Disconnect first.');
      return;
    }

    this.isConnecting = true;
    this.setOrbState('connecting');

    if (this.connectBtn) {
      this.connectBtn.disabled = true;
    }
    if (this.btnText) {
      this.btnText.textContent = 'Connecting...';
    }

    try {
      const startTime = Date.now();
      const backendUrl = this.getBackendUrl();
      this.log(`Connecting to: ${backendUrl}`);

      const transport = new WebSocketTransport();
      const RTVIConfig: RTVIClientOptions = {
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
            this.updateConnectionUI(true);
            this.setOrbState('listening');
            this.log('Connected successfully!');
          },
          onDisconnected: () => {
            this.isConnecting = false;
            this.updateConnectionUI(false);
            this.log('Disconnected');
            this.rtviClient = null;
            this.stopVisualization();
          },
          onBotReady: (data) => {
            this.log(`Bot ready: ${JSON.stringify(data)}`);
            this.setupMediaTracks();
          },
          onUserTranscript: (data) => {
            if (data.final) {
              this.log(`You: ${data.text}`);
              this.showUserTranscript(data.text);
            }
          },
          onBotTranscript: (data) => {
            this.log(`Bot: ${data.text}`);
            this.showBotTranscript(data.text);
          },
          onMessageError: (error) => {
            console.error('Message error:', error);
            this.log(`Message error: ${error}`);
          },
          onError: (error) => {
            console.error('Error:', error);
            this.log(`Error: ${error}`);
          },
        },
      };

      this.rtviClient = new RTVIClient(RTVIConfig);
      this.setupTrackListeners();

      this.log('Initializing devices...');
      await this.rtviClient.initDevices();

      this.log('Connecting to server...');
      await this.rtviClient.connect();

      const timeTaken = Date.now() - startTime;
      this.log(`Connected in ${timeTaken}ms`);
    } catch (error) {
      this.isConnecting = false;
      this.log(`Connection failed: ${(error as Error).message}`);
      this.setOrbState('idle');

      if (this.rtviClient) {
        try {
          await this.rtviClient.disconnect();
        } catch (e) {
          this.log(`Cleanup error: ${e}`);
        }
        this.rtviClient = null;
      }

      if (this.connectBtn) {
        this.connectBtn.disabled = false;
      }
      if (this.btnText) {
        this.btnText.textContent = 'Start Conversation';
      }
    }
  }

  /**
   * Disconnect from the bot server
   */
  public async disconnect(): Promise<void> {
    if (!this.rtviClient && !this.isConnecting) {
      this.log('Not connected');
      return;
    }

    if (this.connectBtn) {
      this.connectBtn.disabled = true;
    }
    if (this.btnText) {
      this.btnText.textContent = 'Disconnecting...';
    }

    try {
      this.log('Disconnecting...');

      if (this.rtviClient) {
        await this.rtviClient.disconnect();
        this.rtviClient = null;
      }

      // Clean up audio
      if (this.botAudio.srcObject && "getAudioTracks" in this.botAudio.srcObject) {
        this.botAudio.srcObject.getAudioTracks().forEach((track) => track.stop());
        this.botAudio.srcObject = null;
      }

      this.stopVisualization();

      // Reset states
      this.isConnecting = false;
      this.isBotSpeaking = false;
      this.updateConnectionUI(false);
      this.log('Disconnected successfully');

      if (this.connectBtn) {
        this.connectBtn.disabled = false;
      }
    } catch (error) {
      this.log(`Disconnect error: ${(error as Error).message}`);
      this.isConnecting = false;

      if (this.connectBtn) {
        this.connectBtn.disabled = false;
      }
      if (this.btnText) {
        this.btnText.textContent = 'Start Conversation';
      }
    }
  }
}

// Initialize app when DOM is ready
declare global {
  interface Window {
    VoiceAssistantApp: typeof VoiceAssistantApp;
  }
}

window.addEventListener('DOMContentLoaded', () => {
  window.VoiceAssistantApp = VoiceAssistantApp;
  new VoiceAssistantApp();
});
