"use strict";
/**
 * Nester AI - Floating Voice Orb Widget
 *
 * A compact floating voice assistant with state-based animations.
 * States: idle | listening | thinking | speaking
 *
 * Features rich content panel for dynamic visual responses.
 * Emotion detection is handled server-side by Hume AI.
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
const client_js_1 = require("@pipecat-ai/client-js");
const websocket_transport_1 = require("@pipecat-ai/websocket-transport");
class VoiceOrbApp {
    constructor() {
        this.rtviClient = null;
        // UI Elements
        this.orbContainer = null;
        this.orbStatus = null;
        this.welcomeMessage = null;
        this.transcriptList = null;
        this.debugPanel = null;
        this.debugLog = null;
        this.debugToggle = null;
        this.debugClose = null;
        this.richContentPanel = null;
        this.richContentInner = null;
        this.emotionPanel = null;
        this.emotionToggle = null;
        this.emotionClose = null;
        this.emotionLabel = null;
        this.emotionEmoji = null;
        this.emotionConfidence = null;
        this.toneLabel = null;
        this.arousalBar = null;
        this.arousalValue = null;
        this.dominanceBar = null;
        this.dominanceValue = null;
        this.valenceBar = null;
        this.valenceValue = null;
        this.emotionTimeline = null;
        // State
        this.voiceState = 'idle';
        this.isConnected = false;
        this.isConnecting = false;
        console.log("Nester AI Voice Orb initializing...");
        this.botAudio = document.createElement('audio');
        this.botAudio.autoplay = true;
        document.body.appendChild(this.botAudio);
        this.setupDOMElements();
        this.setupEventListeners();
        this.setVoiceState('idle');
    }
    setupDOMElements() {
        this.orbContainer = document.getElementById('voice-orb-container');
        this.orbStatus = document.getElementById('orb-status');
        this.welcomeMessage = document.getElementById('welcome-message');
        this.transcriptList = document.getElementById('transcript-list');
        this.debugPanel = document.getElementById('debug-panel');
        this.debugLog = document.getElementById('debug-log');
        this.debugToggle = document.getElementById('debug-toggle');
        this.debugClose = document.getElementById('debug-close');
        this.richContentPanel = document.getElementById('rich-content-panel');
        this.richContentInner = document.getElementById('rich-content-inner');
        this.emotionPanel = document.getElementById('emotion-panel');
        this.emotionToggle = document.getElementById('emotion-toggle');
        this.emotionClose = document.getElementById('emotion-close');
        this.emotionLabel = document.getElementById('emotion-label');
        this.emotionEmoji = document.getElementById('emotion-emoji');
        this.emotionConfidence = document.getElementById('emotion-confidence');
        this.toneLabel = document.getElementById('tone-label');
        this.arousalBar = document.getElementById('arousal-bar');
        this.arousalValue = document.getElementById('arousal-value');
        this.dominanceBar = document.getElementById('dominance-bar');
        this.dominanceValue = document.getElementById('dominance-value');
        this.valenceBar = document.getElementById('valence-bar');
        this.valenceValue = document.getElementById('valence-value');
        this.emotionTimeline = document.getElementById('emotion-timeline');
    }
    setupEventListeners() {
        var _a, _b, _c, _d, _e;
        // Orb click handler
        (_a = this.orbContainer) === null || _a === void 0 ? void 0 : _a.addEventListener('click', () => this.handleOrbClick());
        // Debug panel
        (_b = this.debugToggle) === null || _b === void 0 ? void 0 : _b.addEventListener('click', () => this.toggleDebugPanel());
        (_c = this.debugClose) === null || _c === void 0 ? void 0 : _c.addEventListener('click', () => this.hideDebugPanel());
        // Emotion panel
        (_d = this.emotionToggle) === null || _d === void 0 ? void 0 : _d.addEventListener('click', () => this.toggleEmotionPanel());
        (_e = this.emotionClose) === null || _e === void 0 ? void 0 : _e.addEventListener('click', () => this.hideEmotionPanel());
    }
    /**
     * Handle orb click - connect or disconnect
     */
    handleOrbClick() {
        return __awaiter(this, void 0, void 0, function* () {
            if (this.isConnecting)
                return;
            if (this.isConnected) {
                yield this.disconnect();
            }
            else {
                yield this.connect();
            }
        });
    }
    /**
     * Set voice state and update UI
     */
    setVoiceState(state) {
        this.voiceState = state;
        if (!this.orbContainer || !this.orbStatus)
            return;
        // Remove all state classes
        this.orbContainer.classList.remove('idle', 'listening', 'thinking', 'speaking', 'connected');
        // Add current state
        this.orbContainer.classList.add(state);
        // Add connected class if connected
        if (this.isConnected) {
            this.orbContainer.classList.add('connected');
        }
        // Update status text
        const statusTexts = {
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
    log(message) {
        if (!this.debugLog)
            return;
        const entry = document.createElement('div');
        const time = new Date().toLocaleTimeString();
        entry.textContent = `[${time}] ${message}`;
        // Color coding
        if (message.startsWith('You:')) {
            entry.style.color = '#37b6ff';
        }
        else if (message.startsWith('Bot:')) {
            entry.style.color = '#9747ff';
        }
        else if (message.includes('Error')) {
            entry.style.color = '#ef4444';
        }
        else if (message.includes('Connected')) {
            entry.style.color = '#4ade80';
        }
        this.debugLog.appendChild(entry);
        this.debugLog.scrollTop = this.debugLog.scrollHeight;
        console.log(message);
    }
    /**
     * Add transcript bubble to conversation
     */
    addTranscript(text, isUser) {
        var _a;
        if (!this.transcriptList)
            return;
        // Hide welcome message
        (_a = this.welcomeMessage) === null || _a === void 0 ? void 0 : _a.classList.add('hidden');
        const bubble = document.createElement('div');
        bubble.className = `transcript-bubble ${isUser ? 'user' : 'bot'}`;
        // Add label
        const label = document.createElement('span');
        label.className = 'transcript-label';
        label.textContent = isUser ? 'You' : 'Nester';
        // Add text
        const textSpan = document.createElement('span');
        textSpan.textContent = text;
        bubble.appendChild(label);
        bubble.appendChild(textSpan);
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
    toggleDebugPanel() {
        var _a;
        (_a = this.debugPanel) === null || _a === void 0 ? void 0 : _a.classList.toggle('visible');
    }
    /**
     * Hide debug panel
     */
    hideDebugPanel() {
        var _a;
        (_a = this.debugPanel) === null || _a === void 0 ? void 0 : _a.classList.remove('visible');
    }
    /**
     * Toggle emotion panel
     */
    toggleEmotionPanel() {
        var _a;
        (_a = this.emotionPanel) === null || _a === void 0 ? void 0 : _a.classList.toggle('visible');
    }
    /**
     * Hide emotion panel
     */
    hideEmotionPanel() {
        var _a;
        (_a = this.emotionPanel) === null || _a === void 0 ? void 0 : _a.classList.remove('visible');
    }
    /**
     * Update emotion display with detected emotion data
     */
    updateEmotionDisplay(data) {
        // Update emotion label and emoji
        const emotionEmojis = {
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
        const emotionName = data.emotion.charAt(0).toUpperCase() + data.emotion.slice(1);
        if (this.emotionEmoji)
            this.emotionEmoji.textContent = emoji;
        if (this.emotionLabel)
            this.emotionLabel.textContent = emotionName;
        if (this.emotionConfidence) {
            this.emotionConfidence.textContent = `${Math.round(data.confidence * 100)}%`;
        }
        // Update dimensional values with smooth animation
        if (this.arousalBar && this.arousalValue) {
            this.arousalBar.style.width = `${data.arousal * 100}%`;
            this.arousalValue.textContent = data.arousal.toFixed(2);
        }
        if (this.dominanceBar && this.dominanceValue) {
            this.dominanceBar.style.width = `${data.dominance * 100}%`;
            this.dominanceValue.textContent = data.dominance.toFixed(2);
        }
        if (this.valenceBar && this.valenceValue) {
            this.valenceBar.style.width = `${data.valence * 100}%`;
            this.valenceValue.textContent = data.valence.toFixed(2);
        }
        // Add to emotion timeline
        this.addEmotionToTimeline(data.emotion, emoji);
        this.log(`Emotion detected: ${emotionName} (${Math.round(data.confidence * 100)}%)`);
    }
    /**
     * Update tone display when voice tone is switched
     */
    updateToneDisplay(tone) {
        const toneDisplayNames = {
            'neutral': 'Neutral Voice',
            'excited': 'Excited Voice',
            'sad': 'Empathetic Voice',
            'frustrated': 'Calm Voice',
            'happy': 'Happy Voice',
            'angry': 'Controlled Voice',
            'fear': 'Gentle Voice',
            'content': 'Content Voice',
        };
        const displayName = toneDisplayNames[tone] || 'Neutral Voice';
        if (this.toneLabel) {
            this.toneLabel.textContent = displayName;
            // Animate the tone indicator
            const toneIndicator = document.getElementById('current-tone');
            if (toneIndicator) {
                toneIndicator.classList.add('tone-switching');
                setTimeout(() => toneIndicator.classList.remove('tone-switching'), 600);
            }
        }
        this.log(`Voice tone switched to: ${displayName}`);
    }
    /**
     * Add emotion dot to timeline
     */
    addEmotionToTimeline(emotion, emoji) {
        if (!this.emotionTimeline)
            return;
        const emotionColors = {
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
        // Keep only last 20 emotions
        if (this.emotionTimeline.children.length >= 20) {
            this.emotionTimeline.removeChild(this.emotionTimeline.firstChild);
        }
        this.emotionTimeline.appendChild(dot);
        // Animate dot entrance
        setTimeout(() => dot.classList.add('visible'), 10);
    }
    /**
     * Show rich content panel with animation
     */
    showRichContentPanel() {
        var _a;
        (_a = this.richContentPanel) === null || _a === void 0 ? void 0 : _a.classList.add('visible');
    }
    /**
     * Hide rich content panel
     */
    hideRichContentPanel() {
        var _a;
        (_a = this.richContentPanel) === null || _a === void 0 ? void 0 : _a.classList.remove('visible');
    }
    /**
     * Clear all rich content cards
     */
    clearRichContent() {
        if (this.richContentInner) {
            this.richContentInner.innerHTML = '';
        }
        this.hideRichContentPanel();
    }
    /**
     * Add a rich content card with animation
     */
    addRichContent(content) {
        if (!this.richContentInner)
            return;
        const card = document.createElement('div');
        card.className = `knowledge-card ${content.type === 'info_card' ? 'info-card' : ''}`;
        let cardHTML = '';
        // Image or placeholder
        if (content.image) {
            cardHTML += `<img class="card-image" src="${content.image}" alt="${content.title}" onerror="this.parentElement.querySelector('.card-image-placeholder')?.classList.remove('hidden'); this.remove();">`;
        }
        else {
            cardHTML += `
        <div class="card-image-placeholder">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <path d="M12 2L2 7l10 5 10-5-10-5z"/>
            <path d="M2 17l10 5 10-5"/>
            <path d="M2 12l10 5 10-5"/>
          </svg>
        </div>
      `;
        }
        // Card content
        cardHTML += `<div class="card-content">`;
        // Type badge
        const badgeText = content.type.replace('_', ' ').replace('card', '').trim().toUpperCase() || 'INFO';
        cardHTML += `<span class="card-type-badge">${badgeText}</span>`;
        // Title
        cardHTML += `<h3 class="card-title">${content.title}</h3>`;
        // Description
        if (content.description) {
            cardHTML += `<p class="card-description">${content.description}</p>`;
        }
        // Stats grid
        if (content.stats && content.stats.length > 0) {
            cardHTML += `<div class="stats-grid">`;
            content.stats.forEach(stat => {
                cardHTML += `
          <div class="stat-item">
            <div class="stat-value">${stat.value}</div>
            <div class="stat-label">${stat.label}</div>
          </div>
        `;
            });
            cardHTML += `</div>`;
        }
        // Features list
        if (content.features && content.features.length > 0) {
            cardHTML += `<div class="card-features">`;
            content.features.forEach(feature => {
                cardHTML += `
          <div class="feature-item">
            <span class="feature-dot"></span>
            <span>${feature}</span>
          </div>
        `;
            });
            cardHTML += `</div>`;
        }
        // Link button
        if (content.link) {
            const linkText = content.linkText || 'Learn More';
            cardHTML += `
        <a href="${content.link}" target="_blank" rel="noopener noreferrer" class="card-link">
          ${linkText}
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M5 12h14"/>
            <path d="M12 5l7 7-7 7"/>
          </svg>
        </a>
      `;
        }
        cardHTML += `</div>`;
        card.innerHTML = cardHTML;
        this.richContentInner.appendChild(card);
        this.showRichContentPanel();
        this.log(`Rich content added: ${content.title}`);
    }
    /**
     * Show loading state in rich content panel
     */
    showRichContentLoading() {
        if (!this.richContentInner)
            return;
        const loadingCard = document.createElement('div');
        loadingCard.className = 'knowledge-card loading';
        loadingCard.id = 'rich-content-loader';
        loadingCard.innerHTML = `
      <div class="card-loader">
        <span></span>
        <span></span>
        <span></span>
      </div>
    `;
        this.richContentInner.appendChild(loadingCard);
        this.showRichContentPanel();
    }
    /**
     * Hide loading state
     */
    hideRichContentLoading() {
        const loader = document.getElementById('rich-content-loader');
        if (loader) {
            loader.classList.add('removing');
            setTimeout(() => loader.remove(), 400);
        }
    }
    /**
     * Handle rich content from backend response
     */
    handleRichContent(richContent) {
        this.hideRichContentLoading();
        if (Array.isArray(richContent)) {
            richContent.forEach(content => this.addRichContent(content));
        }
        else {
            this.addRichContent(richContent);
        }
    }
    /**
     * Set up audio track
     */
    setupAudioTrack(track) {
        this.log('Audio track connected');
        if (this.botAudio.srcObject && "getAudioTracks" in this.botAudio.srcObject) {
            const oldTrack = this.botAudio.srcObject.getAudioTracks()[0];
            if ((oldTrack === null || oldTrack === void 0 ? void 0 : oldTrack.id) === track.id)
                return;
        }
        this.botAudio.srcObject = new MediaStream([track]);
    }
    /**
     * Set up media tracks
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
     * Set up event listeners for RTVI
     */
    setupTrackListeners() {
        if (!this.rtviClient)
            return;
        // Track events
        this.rtviClient.on(client_js_1.RTVIEvent.TrackStarted, (track, participant) => {
            if (!(participant === null || participant === void 0 ? void 0 : participant.local) && track.kind === 'audio') {
                this.setupAudioTrack(track);
            }
        });
        // Bot speech events
        this.rtviClient.on(client_js_1.RTVIEvent.BotStartedSpeaking, () => {
            this.log('Bot started speaking');
            this.setVoiceState('speaking');
        });
        this.rtviClient.on(client_js_1.RTVIEvent.BotStoppedSpeaking, () => {
            this.log('Bot stopped speaking');
            if (this.isConnected) {
                this.setVoiceState('listening');
            }
        });
        // User speech events
        this.rtviClient.on(client_js_1.RTVIEvent.UserStartedSpeaking, () => {
            this.log('User started speaking');
            this.setVoiceState('listening');
        });
        this.rtviClient.on(client_js_1.RTVIEvent.UserStoppedSpeaking, () => {
            this.log('User stopped speaking');
            this.setVoiceState('thinking');
        });
    }
    /**
     * Get backend URL
     */
    getBackendUrl() {
        var _a;
        // @ts-ignore
        if (typeof import.meta !== 'undefined' && ((_a = import.meta.env) === null || _a === void 0 ? void 0 : _a.VITE_BACKEND_URL)) {
            // @ts-ignore
            return import.meta.env.VITE_BACKEND_URL;
        }
        if (window.__BACKEND_URL__) {
            return window.__BACKEND_URL__;
        }
        return 'http://localhost:7860';
    }
    /**
     * Connect to voice server
     * Note: Emotion detection is now handled server-side by Hume AI
     */
    connect() {
        return __awaiter(this, void 0, void 0, function* () {
            if (this.isConnecting || this.isConnected)
                return;
            this.isConnecting = true;
            this.setVoiceState('thinking'); // Show thinking animation while connecting
            try {
                const backendUrl = this.getBackendUrl();
                this.log(`Connecting to ${backendUrl}...`);
                const transport = new websocket_transport_1.WebSocketTransport();
                const config = {
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
                        onBotReady: () => {
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
                        onServerMessage: (message) => {
                            // Handle custom server messages (OutputTransportMessageFrame from backend)
                            console.log('[Emotion] Server message received:', JSON.stringify(message, null, 2));
                            try {
                                // The RTVI SDK unwraps the message - we receive { data: {...} }
                                // Check multiple possible message structures
                                let emotionData = null;
                                let messageType = null;
                                // Case 1: message.data contains our custom data directly
                                if (message && message.data) {
                                    messageType = message.data.message_type;
                                    emotionData = message.data;
                                }
                                // Case 2: message itself has message_type (direct data)
                                else if (message && message.message_type) {
                                    messageType = message.message_type;
                                    emotionData = message;
                                }
                                // Case 3: Wrapped in server-message type
                                else if (message && message.type === 'server-message' && message.data) {
                                    messageType = message.data.message_type;
                                    emotionData = message.data;
                                }
                                console.log('[Emotion] Parsed message type:', messageType, 'data:', emotionData);
                                if (messageType === 'emotion_detected' && emotionData) {
                                    console.log('[Emotion] Updating emotion display:', emotionData);
                                    this.updateEmotionDisplay(emotionData);
                                }
                                else if (messageType === 'tone_switched' && emotionData) {
                                    console.log('[Emotion] Updating tone display:', emotionData.new_tone);
                                    this.updateToneDisplay(emotionData.new_tone);
                                }
                            }
                            catch (e) {
                                console.error('[Emotion] Error handling server message:', e);
                            }
                        },
                    },
                };
                this.rtviClient = new client_js_1.RTVIClient(config);
                this.setupTrackListeners();
                yield this.rtviClient.initDevices();
                yield this.rtviClient.connect();
            }
            catch (error) {
                this.isConnecting = false;
                this.log(`Connection failed: ${error.message}`);
                this.setVoiceState('idle');
                if (this.rtviClient) {
                    try {
                        yield this.rtviClient.disconnect();
                    }
                    catch (e) { }
                    this.rtviClient = null;
                }
            }
        });
    }
    /**
     * Disconnect from voice server
     */
    disconnect() {
        return __awaiter(this, void 0, void 0, function* () {
            if (!this.rtviClient && !this.isConnecting)
                return;
            this.log('Disconnecting...');
            try {
                if (this.rtviClient) {
                    yield this.rtviClient.disconnect();
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
            }
            catch (error) {
                this.log(`Disconnect error: ${error.message}`);
                this.isConnecting = false;
                this.isConnected = false;
                this.setVoiceState('idle');
            }
        });
    }
    /**
     * Demo function to test rich content panel (for development)
     * Can be called from browser console: window.demoRichContent()
     */
    demoRichContent() {
        this.clearRichContent();
        // Demo project card
        this.addRichContent({
            type: 'project_card',
            title: 'NesterLabs ConversationalBot',
            description: 'A real-time voice conversational assistant with ultra-low latency responses.',
            image: 'https://images.unsplash.com/photo-1677442136019-21780ecad995?w=400',
            features: [
                '1.5 second response time',
                'Hinglish language support',
                'RAG knowledge integration',
                'Real-time voice streaming'
            ],
            link: 'https://github.com/nesterlabs-ai/NesterConversationalBot',
            linkText: 'View on GitHub'
        });
        // Demo stats card
        setTimeout(() => {
            this.addRichContent({
                type: 'stats_card',
                title: 'Performance Metrics',
                stats: [
                    { label: 'Latency', value: '1.5s' },
                    { label: 'Accuracy', value: '98%' },
                    { label: 'Users', value: '10K+' },
                    { label: 'Uptime', value: '99.9%' }
                ]
            });
        }, 600);
    }
}
window.addEventListener('DOMContentLoaded', () => {
    window.VoiceOrbApp = VoiceOrbApp;
    const app = new VoiceOrbApp();
    // Expose demo function for testing
    window.demoRichContent = () => app.demoRichContent();
});
