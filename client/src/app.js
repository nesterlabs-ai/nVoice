"use strict";
/**
 * Copyright (c) 2024–2025, Daily
 *
 * SPDX-License-Identifier: BSD 2-Clause License
 */
var __awaiter = (this && this.__awaiter) || function (thisArg, _arguments, P, generator) {
    function adopt(value) { return value instanceof P ? value : new P(function (resolve) { resolve(value); }); }
    return new (P || (P = Promise))(function (resolve, reject) {
        function fulfilled(value) { try { step(generator.next(value)); } catch (e) { reject(e); } }
        function rejected(value) { try { step(generator["throw"](value)); } catch (e) { reject(e); } }
        function step(result) { result.done ? resolve(result.value) : adopt(result.value).then(fulfilled, rejected); }
        step((generator = generator.apply(thisArg, _arguments || [])).next());
    });
};
Object.defineProperty(exports, "__esModule", { value: true });
/**
 * RTVI Client Implementation
 *
 * This client connects to an RTVI-compatible bot server using WebSocket.
 *
 * Requirements:
 * - A running RTVI bot server (defaults to http://localhost:7860)
 */
const client_js_1 = require("@pipecat-ai/client-js");
const websocket_transport_1 = require("@pipecat-ai/websocket-transport");
class WebsocketClientApp {
    constructor() {
        this.rtviClient = null;
        this.connectBtn = null;
        this.statusDot = null;
        this.debugLog = null;
        this.voiceOverlay = null;
        this.overlayWaveContainer = null;
        this.logToggle = null;
        this.isConnected = false;
        console.log("Voice Chat Initializing...");
        this.botAudio = document.createElement('audio');
        this.botAudio.autoplay = true;
        document.body.appendChild(this.botAudio);
        this.setupDOMElements();
        this.setupEventListeners();
        this.initializeVisualEffects();
    }
    /**
     * Set up references to DOM elements and create necessary media elements
     */
    setupDOMElements() {
        this.connectBtn = document.getElementById('connect-btn');
        this.statusDot = document.getElementById('status-dot');
        this.debugLog = document.getElementById('debug-log');
        this.voiceOverlay = document.getElementById('voice-overlay');
        this.overlayWaveContainer = document.querySelector('.overlay-wave-container');
        this.logToggle = document.getElementById('log-toggle');
    }
    /**
     * Set up event listeners for interactive elements
     */
    setupEventListeners() {
        var _a, _b;
        (_a = this.connectBtn) === null || _a === void 0 ? void 0 : _a.addEventListener('click', () => this.toggleConnection());
        (_b = this.logToggle) === null || _b === void 0 ? void 0 : _b.addEventListener('click', () => this.toggleLog());
    }
    /**
     * Initialize visual effects and animations
     */
    initializeVisualEffects() {
        this.updateConnectionVisuals(false);
    }
    /**
     * Toggle connection state
     */
    toggleConnection() {
        return __awaiter(this, void 0, void 0, function* () {
            if (this.isConnected) {
                yield this.disconnect();
            }
            else {
                yield this.connect();
            }
        });
    }
    /**
     * Toggle log panel visibility
     */
    toggleLog() {
        if (this.debugLog) {
            this.debugLog.classList.toggle('collapsed');
        }
    }
    /**
     * Update visual elements based on connection state
     */
    updateConnectionVisuals(connected) {
        this.isConnected = connected;
        if (this.statusDot) {
            if (connected) {
                this.statusDot.classList.add('connected');
            }
            else {
                this.statusDot.classList.remove('connected');
            }
        }
        if (this.connectBtn) {
            if (connected) {
                this.connectBtn.classList.add('connected');
                this.connectBtn.disabled = false;
            }
            else {
                this.connectBtn.classList.remove('connected');
                this.connectBtn.disabled = false;
            }
        }
        if (this.voiceOverlay) {
            if (connected) {
                this.voiceOverlay.classList.add('active');
            }
            else {
                this.voiceOverlay.classList.remove('active');
            }
        }
        if (this.overlayWaveContainer) {
            if (connected) {
                this.overlayWaveContainer.classList.add('active');
            }
            else {
                this.overlayWaveContainer.classList.remove('active');
            }
        }
    }
    /**
     * Add a timestamped message to the debug log
     */
    log(message) {
        if (!this.debugLog)
            return;
        const entry = document.createElement('div');
        entry.textContent = `${new Date().toISOString()} - ${message}`;
        if (message.startsWith('User: ')) {
            entry.style.color = '#2196F3';
        }
        else if (message.startsWith('Bot: ')) {
            entry.style.color = '#4CAF50';
        }
        this.debugLog.appendChild(entry);
        this.debugLog.scrollTop = this.debugLog.scrollHeight;
        console.log(message);
    }
    /**
     * Update the connection status display
     */
    updateStatus(status) {
        const isConnected = status === 'Connected' || status === 'Online';
        this.updateConnectionVisuals(isConnected);
        this.log(`Connection Status: ${status}`);
    }
    /**
     * Check for available media tracks and set them up if present
     * This is called when the bot is ready or when the transport state changes to ready
     */
    setupMediaTracks() {
        var _a;
        if (!this.rtviClient)
            return;
        const tracks = this.rtviClient.tracks();
        if ((_a = tracks.bot) === null || _a === void 0 ? void 0 : _a.audio) {
            this.setupAudioTrack(tracks.bot.audio);
        }
    }
    /**
     * Set up listeners for track events (start/stop)
     * This handles new tracks being added during the session
     */
    setupTrackListeners() {
        if (!this.rtviClient)
            return;
        // Listen for new tracks starting
        this.rtviClient.on(client_js_1.RTVIEvent.TrackStarted, (track, participant) => {
            // Only handle non-local (bot) tracks
            if (!(participant === null || participant === void 0 ? void 0 : participant.local) && track.kind === 'audio') {
                this.setupAudioTrack(track);
            }
        });
        // Listen for tracks stopping
        this.rtviClient.on(client_js_1.RTVIEvent.TrackStopped, (track, participant) => {
            this.log(`Track stopped: ${track.kind} from ${(participant === null || participant === void 0 ? void 0 : participant.name) || 'unknown'}`);
        });
    }
    /**
     * Set up an audio track for playback
     * Handles both initial setup and track updates
     */
    setupAudioTrack(track) {
        this.log('Setting up audio track');
        if (this.botAudio.srcObject && "getAudioTracks" in this.botAudio.srcObject) {
            const oldTrack = this.botAudio.srcObject.getAudioTracks()[0];
            if ((oldTrack === null || oldTrack === void 0 ? void 0 : oldTrack.id) === track.id)
                return;
        }
        this.botAudio.srcObject = new MediaStream([track]);
    }
    /**
     * Get the backend URL from environment or use default
     */
    getBackendUrl() {
        var _a;
        // Check for Vite environment variable (build time)
        // @ts-ignore - Vite injects this at build time
        if (typeof import.meta !== 'undefined' && ((_a = import.meta.env) === null || _a === void 0 ? void 0 : _a.VITE_BACKEND_URL)) {
            // @ts-ignore
            return import.meta.env.VITE_BACKEND_URL;
        }
        // Check for window config (runtime injection)
        if (window.__BACKEND_URL__) {
            return window.__BACKEND_URL__;
        }
        // Default for local development
        return 'http://localhost:7860';
    }
    /**
     * Initialize and connect to the bot
     * This sets up the RTVI client, initializes devices, and establishes the connection
     */
    connect() {
        return __awaiter(this, void 0, void 0, function* () {
            try {
                const startTime = Date.now();
                const backendUrl = this.getBackendUrl();
                this.log(`Connecting to backend: ${backendUrl}`);
                //const transport = new DailyTransport();
                const transport = new websocket_transport_1.WebSocketTransport();
                const RTVIConfig = {
                    transport,
                    params: {
                        // The baseURL and endpoint of your bot server that the client will connect to
                        baseUrl: backendUrl,
                        endpoints: { connect: '/connect' },
                    },
                    enableMic: true,
                    enableCam: false,
                    // Browser-based noise suppression
                    customAudioConstraints: {
                        echoCancellation: true,
                        noiseSuppression: true,
                        autoGainControl: true,
                    },
                    callbacks: {
                        onConnected: () => {
                            this.updateStatus('Connected');
                            this.log('Connection established successfully');
                        },
                        onDisconnected: () => {
                            this.updateStatus('Disconnected');
                            this.log('Connection terminated');
                        },
                        onBotReady: (data) => {
                            this.log(`Bot ready: ${JSON.stringify(data)}`);
                            this.setupMediaTracks();
                        },
                        onUserTranscript: (data) => {
                            if (data.final) {
                                this.log(`You: ${data.text}`);
                            }
                        },
                        onBotTranscript: (data) => this.log(`Bot: ${data.text}`),
                        onMessageError: (error) => console.error('Message error:', error),
                        onError: (error) => console.error('Error:', error),
                    },
                };
                this.rtviClient = new client_js_1.RTVIClient(RTVIConfig);
                this.setupTrackListeners();
                this.log('Initializing devices...');
                yield this.rtviClient.initDevices();
                this.log('Connecting to server...');
                yield this.rtviClient.connect();
                const timeTaken = Date.now() - startTime;
                this.log(`Connection established in ${timeTaken}ms`);
            }
            catch (error) {
                this.log(`Connection failed: ${error.message}`);
                this.updateStatus('Error');
                if (this.rtviClient) {
                    try {
                        yield this.rtviClient.disconnect();
                    }
                    catch (disconnectError) {
                        this.log(`Cleanup error: ${disconnectError}`);
                    }
                }
            }
        });
    }
    /**
     * Disconnect from the bot and clean up media resources
     */
    disconnect() {
        return __awaiter(this, void 0, void 0, function* () {
            if (this.rtviClient) {
                try {
                    this.log('Disconnecting...');
                    yield this.rtviClient.disconnect();
                    this.rtviClient = null;
                    if (this.botAudio.srcObject && "getAudioTracks" in this.botAudio.srcObject) {
                        this.botAudio.srcObject.getAudioTracks().forEach((track) => track.stop());
                        this.botAudio.srcObject = null;
                    }
                    this.log('Disconnected successfully');
                }
                catch (error) {
                    this.log(`Disconnect error: ${error.message}`);
                }
            }
        });
    }
}
window.addEventListener('DOMContentLoaded', () => {
    window.WebsocketClientApp = WebsocketClientApp;
    new WebsocketClientApp();
});
