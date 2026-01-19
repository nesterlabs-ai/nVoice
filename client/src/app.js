"use strict";
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
class VoiceScannerApp {
    constructor() {
        this.rtviClient = null;
        // UI Elements
        this.scannerFrame = null;
        this.orbContainer = null;
        this.orbStatus = null;
        this.welcomeMessage = null;
        this.transcriptList = null;
        this.transcriptStatus = null;
        this.debugPanel = null;
        this.debugLog = null;
        this.debugToggle = null;
        this.debugClose = null;
        this.emotionPanel = null;
        this.emotionToggle = null;
        this.emotionLabel = null;
        this.emotionEmoji = null;
        this.emotionConfidence = null;
        this.toneLabel = null;
        this.arousalBar = null;
        this.arousalValue = null;
        this.dominanceValue = null;
        this.valenceValue = null;
        this.emotionTimeline = null;
        this.statusIndicator = null;
        this.loadingOverlay = null;
        this.terminalContent = null;
        this.terminalStatus = null;
        this.typingLine = null;
        this.timestampElement = null;
        this.notification = null;
        // Canvas elements
        this.waveformCanvas = null;
        this.circularCanvas = null;
        this.preloaderCanvas = null;
        this.waveformCtx = null;
        this.circularCtx = null;
        this.preloaderCtx = null;
        // Audio analysis
        this.audioContext = null;
        this.analyser = null;
        this.dataArray = null;
        this.animationFrame = null;
        // State
        this.voiceState = 'idle';
        this.isConnected = false;
        this.isConnecting = false;
        this.preloaderAngle = 0;
        // Streaming transcript state
        this.streamingBubble = null;
        this.currentUtteranceId = null;
        this.streamingWords = [];
        // Visual cards state
        this.activeVisualCard = null;
        this.visualCardsContainer = null;
        // Emotion-reactive UI state
        this.lastEmotionUpdate = 0;
        this.emotionUpdateDebounceMs = 100;
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
        window.testVisualCard = () => {
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
        console.log('[DEBUG] testVisualCard() function available in console');
    }
    setupDOMElements() {
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
        this.waveformCanvas = document.getElementById('waveform-canvas');
        this.circularCanvas = document.getElementById('circular-canvas');
        this.preloaderCanvas = document.getElementById('preloader-canvas');
    }
    setupEventListeners() {
        var _a, _b, _c, _d;
        // Scanner frame click handler (whole frame is clickable)
        (_a = this.scannerFrame) === null || _a === void 0 ? void 0 : _a.addEventListener('click', () => this.handleOrbClick());
        // Debug panel
        (_b = this.debugToggle) === null || _b === void 0 ? void 0 : _b.addEventListener('click', () => this.toggleDebugPanel());
        (_c = this.debugClose) === null || _c === void 0 ? void 0 : _c.addEventListener('click', () => this.hideDebugPanel());
        // Emotion panel toggle
        (_d = this.emotionToggle) === null || _d === void 0 ? void 0 : _d.addEventListener('click', () => this.toggleEmotionPanel());
    }
    /**
     * Initialize canvas elements for visualizations
     */
    initializeCanvases() {
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
    drawIdleWaveform() {
        if (!this.waveformCtx || !this.waveformCanvas)
            return;
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
    animatePreloader() {
        if (!this.preloaderCtx || !this.preloaderCanvas)
            return;
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
    showLoadingOverlay() {
        if (this.loadingOverlay) {
            this.loadingOverlay.classList.remove('hidden');
            this.animatePreloader();
        }
    }
    /**
     * Hide loading overlay
     */
    hideLoadingOverlay() {
        if (this.loadingOverlay) {
            this.loadingOverlay.classList.add('hidden');
            this.addTerminalMessage('Voice scanner ready. Awaiting user input.', 'regular');
        }
    }
    /**
     * Start timestamp update
     */
    startTimestampUpdate() {
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
    createFloatingParticles() {
        const container = document.getElementById('floating-particles');
        if (!container)
            return;
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
    addTerminalMessage(message, type = 'regular') {
        if (!this.terminalContent || !this.typingLine)
            return;
        const line = document.createElement('div');
        line.className = `terminal-line ${type}-line`;
        if (type === 'command') {
            line.textContent = `> ${message}`;
        }
        else if (type === 'error') {
            line.innerHTML = `<span style="color: #ef4444;">[ERROR]</span> ${message}`;
        }
        else if (type === 'success') {
            line.innerHTML = `<span style="color: #4ade80;">[OK]</span> ${message}`;
        }
        else {
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
    showNotification(message) {
        if (!this.notification)
            return;
        this.notification.textContent = message;
        this.notification.classList.add('visible');
        setTimeout(() => {
            var _a;
            (_a = this.notification) === null || _a === void 0 ? void 0 : _a.classList.remove('visible');
        }, 3000);
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
        if (!this.scannerFrame || !this.orbContainer || !this.orbStatus)
            return;
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
        const statusTexts = {
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
            const signalTexts = {
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
    log(message) {
        if (!this.debugLog)
            return;
        const entry = document.createElement('div');
        const time = new Date().toLocaleTimeString('en-US', { hour12: false });
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
     * Toggle emotion panel visibility
     */
    toggleEmotionPanel() {
        var _a;
        (_a = this.emotionPanel) === null || _a === void 0 ? void 0 : _a.classList.toggle('visible');
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
        const emotionName = data.emotion.toUpperCase();
        if (this.emotionEmoji)
            this.emotionEmoji.textContent = emoji;
        if (this.emotionLabel)
            this.emotionLabel.textContent = emotionName;
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
     * Update emotion display with HYBRID emotion data (audio + text)
     */
    updateHybridEmotionDisplay(data) {
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
        const emoji = emotionEmojis[data.primary_emotion] || '😊';
        const emotionName = data.primary_emotion.toUpperCase();
        if (this.emotionEmoji)
            this.emotionEmoji.textContent = emoji;
        if (this.emotionLabel)
            this.emotionLabel.textContent = emotionName;
        if (this.emotionConfidence) {
            this.emotionConfidence.textContent = `${Math.round(data.confidence * 100)}%`;
        }
        // Update dimensional values (fused from audio + text)
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
        this.addEmotionToTimeline(data.primary_emotion, emoji);
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
    updateToneDisplay(tone) {
        const toneDisplayNames = {
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
    addEmotionToTimeline(emotion, _emoji) {
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
        // Keep only last 15 emotions
        if (this.emotionTimeline.children.length >= 15) {
            this.emotionTimeline.removeChild(this.emotionTimeline.firstChild);
        }
        this.emotionTimeline.appendChild(dot);
        // Animate dot entrance
        setTimeout(() => dot.classList.add('visible'), 10);
    }
    /**
     * Start audio visualization
     */
    startAudioVisualization() {
        if (!this.analyser || !this.dataArray)
            return;
        const visualize = () => {
            if (!this.isConnected)
                return;
            this.analyser.getByteFrequencyData(this.dataArray);
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
    drawWaveform() {
        if (!this.waveformCtx || !this.waveformCanvas || !this.dataArray)
            return;
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
            }
            else {
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
    drawCircularVisualizer() {
        if (!this.circularCtx || !this.circularCanvas || !this.dataArray)
            return;
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
    updatePeakFrequency() {
        if (!this.dataArray)
            return;
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
    stopAudioVisualization() {
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
        if (peakValue)
            peakValue.textContent = '-- HZ';
        const amplitudeValue = document.getElementById('amplitude-value');
        if (amplitudeValue)
            amplitudeValue.textContent = '0.00';
    }
    /**
     * Set up audio track with visualization
     */
    setupAudioTrack(track) {
        this.log('Audio track connected');
        if (this.botAudio.srcObject && "getAudioTracks" in this.botAudio.srcObject) {
            const oldTrack = this.botAudio.srcObject.getAudioTracks()[0];
            if ((oldTrack === null || oldTrack === void 0 ? void 0 : oldTrack.id) === track.id)
                return;
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
        }
        catch (e) {
            console.warn('Could not set up audio visualization:', e);
        }
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
            this.showNotification('VOICE DETECTED');
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
     */
    connect() {
        return __awaiter(this, void 0, void 0, function* () {
            if (this.isConnecting || this.isConnected)
                return;
            this.isConnecting = true;
            this.setVoiceState('thinking');
            this.addTerminalMessage('voice.scanner.connect();', 'command');
            this.addTerminalMessage('Establishing secure connection...', 'regular');
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
                                }
                                else if (message && message.message_type) {
                                    messageType = message.message_type;
                                    messageData = message;
                                }
                                else if (message && message.type === 'server-message' && message.data) {
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
                                }
                            }
                            catch (e) {
                                console.error('[Visual] Error handling server message:', e);
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
                this.addTerminalMessage(`Connection failed: ${error.message}`, 'error');
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
            this.addTerminalMessage('voice.scanner.disconnect();', 'command');
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
                // Clean up audio context
                if (this.audioContext) {
                    yield this.audioContext.close();
                    this.audioContext = null;
                    this.analyser = null;
                    this.dataArray = null;
                }
                this.stopAudioVisualization();
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
    // ===== STREAMING TRANSCRIPT METHODS =====
    /**
     * Handle streaming text events for word-by-word display
     */
    handleStreamingText(data) {
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
    createStreamingBubble() {
        var _a;
        if (!this.transcriptList)
            return;
        // Hide welcome message
        (_a = this.welcomeMessage) === null || _a === void 0 ? void 0 : _a.classList.add('hidden');
        this.streamingBubble = document.createElement('div');
        this.streamingBubble.className = 'transcript-bubble bot streaming';
        const label = document.createElement('span');
        label.className = 'transcript-label';
        label.textContent = 'NESTER';
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
    addStreamingWord(word, sequenceId) {
        if (!this.streamingBubble)
            return;
        const textContainer = this.streamingBubble.querySelector('.streaming-text');
        if (!textContainer)
            return;
        // Create word span with animation
        const wordSpan = document.createElement('span');
        wordSpan.className = 'streaming-word';
        wordSpan.textContent = word + ' ';
        wordSpan.style.animationDelay = `${(sequenceId % 10) * 30}ms`; // Stagger animation
        textContainer.appendChild(wordSpan);
        this.streamingWords.push(word);
        // Auto-scroll
        if (this.transcriptList) {
            this.transcriptList.scrollTop = this.transcriptList.scrollHeight;
        }
    }
    /**
     * Finalize the current streaming bubble
     */
    finalizeCurrentStreamingBubble() {
        if (this.streamingBubble) {
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
    handleVisualHint(data) {
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
    showGreetingAnimation() {
        var _a;
        // Trigger greeting animation on the orb
        (_a = this.orbContainer) === null || _a === void 0 ? void 0 : _a.classList.add('greeting-pulse');
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
            var _a;
            (_a = this.orbContainer) === null || _a === void 0 ? void 0 : _a.classList.remove('greeting-pulse');
        }, 3000);
    }
    /**
     * Show contact information card with full details
     */
    showContactCard(_content) {
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
    showServiceCard(_content) {
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
    showPricingCard(_content) {
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
    showProjectCard(_content) {
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
    showProjectDetailCard(projectId) {
        var _a;
        const projects = {
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
        const project = (_a = projects[projectId]) !== null && _a !== void 0 ? _a : projects.visualizing_intelligence;
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
    showExpertiseCard(_content) {
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
    showCompanyCard(_content) {
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
    showNextStepsCard(_content) {
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
    showLocationCard(_content) {
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
    createVisualCard(className) {
        const card = document.createElement('div');
        card.className = `visual-card ${className}`;
        return card;
    }
    /**
     * Display a visual card with optional auto-dismiss
     */
    displayVisualCard(card, autoDismissMs) {
        var _a;
        console.log('[Visual Card] Displaying card:', card.className);
        // Get or create visual cards container
        if (!this.visualCardsContainer) {
            this.visualCardsContainer = document.getElementById('visual-cards-container');
            console.log('[Visual Card] Container from DOM:', this.visualCardsContainer);
            if (!this.visualCardsContainer) {
                this.visualCardsContainer = document.createElement('div');
                this.visualCardsContainer.id = 'visual-cards-container';
                (_a = document.querySelector('.interface-container')) === null || _a === void 0 ? void 0 : _a.appendChild(this.visualCardsContainer);
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
    dismissVisualCard() {
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
    // ===== EMOTION-REACTIVE UI METHODS =====
    /**
     * Update UI colors and animations based on emotion state
     */
    updateEmotionReactiveUI(data) {
        var _a, _b, _c;
        // Debounce updates
        const now = Date.now();
        if (now - this.lastEmotionUpdate < this.emotionUpdateDebounceMs) {
            return;
        }
        this.lastEmotionUpdate = now;
        const emotion = data.primary_emotion || data.emotion || 'neutral';
        const arousal = (_a = data.arousal) !== null && _a !== void 0 ? _a : 0.5;
        const valence = (_b = data.valence) !== null && _b !== void 0 ? _b : 0.5;
        // Update CSS custom properties for emotion colors
        const root = document.documentElement;
        const emotionColors = {
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
        (_c = this.orbContainer) === null || _c === void 0 ? void 0 : _c.setAttribute('data-emotion', emotion);
        // Update scanner frame border based on valence
        if (this.scannerFrame) {
            if (valence > 0.6) {
                this.scannerFrame.style.borderColor = colors.primary;
            }
            else if (valence < 0.4) {
                this.scannerFrame.style.borderColor = colors.secondary;
            }
            else {
                this.scannerFrame.style.borderColor = '';
            }
        }
    }
}
window.addEventListener('DOMContentLoaded', () => {
    window.VoiceScannerApp = VoiceScannerApp;
    new VoiceScannerApp();
});
