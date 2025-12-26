/**
 * Nester AI - Floating Voice Orb Widget
 *
 * A compact floating voice assistant with state-based animations.
 * States: idle | listening | thinking | speaking
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

class VoiceOrbApp {
  private rtviClient: RTVIClient | null = null;

  // UI Elements
  private orbContainer: HTMLElement | null = null;
  private orbStatus: HTMLElement | null = null;
  private welcomeMessage: HTMLElement | null = null;
  private transcriptList: HTMLElement | null = null;
  private debugPanel: HTMLElement | null = null;
  private debugLog: HTMLElement | null = null;
  private debugToggle: HTMLElement | null = null;
  private debugClose: HTMLElement | null = null;

  // Audio
  private botAudio: HTMLAudioElement;

  // State
  private voiceState: VoiceState = 'idle';
  private isConnected: boolean = false;
  private isConnecting: boolean = false;

  constructor() {
    console.log("Nester AI Voice Orb initializing...");

    this.botAudio = document.createElement('audio');
    this.botAudio.autoplay = true;
    document.body.appendChild(this.botAudio);

    this.setupDOMElements();
    this.setupEventListeners();
    this.setVoiceState('idle');
  }

  private setupDOMElements(): void {
    this.orbContainer = document.getElementById('voice-orb-container');
    this.orbStatus = document.getElementById('orb-status');
    this.welcomeMessage = document.getElementById('welcome-message');
    this.transcriptList = document.getElementById('transcript-list');
    this.debugPanel = document.getElementById('debug-panel');
    this.debugLog = document.getElementById('debug-log');
    this.debugToggle = document.getElementById('debug-toggle');
    this.debugClose = document.getElementById('debug-close');
  }

  private setupEventListeners(): void {
    // Orb click handler
    this.orbContainer?.addEventListener('click', () => this.handleOrbClick());

    // Debug panel
    this.debugToggle?.addEventListener('click', () => this.toggleDebugPanel());
    this.debugClose?.addEventListener('click', () => this.hideDebugPanel());
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

    if (!this.orbContainer || !this.orbStatus) return;

    // Remove all state classes
    this.orbContainer.classList.remove('idle', 'listening', 'thinking', 'speaking', 'connected');

    // Add current state
    this.orbContainer.classList.add(state);

    // Add connected class if connected
    if (this.isConnected) {
      this.orbContainer.classList.add('connected');
    }

    // Update status text
    const statusTexts: Record<VoiceState, string> = {
      'idle': this.isConnected ? 'Tap to end' : 'Tap to talk',
      'listening': 'Listening...',
      'thinking': 'Thinking...',
      'speaking': 'Speaking...'
    };

    this.orbStatus.textContent = statusTexts[state];
  }

  /**
   * Log message to debug panel
   */
  private log(message: string): void {
    if (!this.debugLog) return;

    const entry = document.createElement('div');
    const time = new Date().toLocaleTimeString();
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
    bubble.textContent = text;

    this.transcriptList.appendChild(bubble);

    // Scroll to bottom
    const conversationArea = document.getElementById('conversation-area');
    if (conversationArea) {
      conversationArea.scrollTop = conversationArea.scrollHeight;
    }
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
   * Set up audio track
   */
  private setupAudioTrack(track: MediaStreamTrack): void {
    this.log('Audio track connected');

    if (this.botAudio.srcObject && "getAudioTracks" in this.botAudio.srcObject) {
      const oldTrack = this.botAudio.srcObject.getAudioTracks()[0];
      if (oldTrack?.id === track.id) return;
    }

    this.botAudio.srcObject = new MediaStream([track]);
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
    this.setVoiceState('thinking'); // Show thinking animation while connecting

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
          },
          onDisconnected: () => {
            this.isConnecting = false;
            this.isConnected = false;
            this.rtviClient = null;
            this.log('Disconnected');
            this.setVoiceState('idle');
          },
          onBotReady: (data) => {
            this.log(`Bot ready`);
            this.setupMediaTracks();
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
            console.error('RTVI Error:', error);
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
    VoiceOrbApp: typeof VoiceOrbApp;
  }
}

window.addEventListener('DOMContentLoaded', () => {
  window.VoiceOrbApp = VoiceOrbApp;
  new VoiceOrbApp();
});
