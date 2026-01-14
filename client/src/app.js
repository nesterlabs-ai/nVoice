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
                                }
                                else if (message && message.message_type) {
                                    messageType = message.message_type;
                                    emotionData = message;
                                }
                                else if (message && message.type === 'server-message' && message.data) {
                                    messageType = message.data.message_type;
                                    emotionData = message.data;
                                }
                                console.log('[Emotion] Parsed message type:', messageType, 'data:', emotionData);
                                if (messageType === 'hybrid_emotion_detected' && emotionData) {
                                    console.log('[🔄 HYBRID EMOTION] Updating emotion display:', emotionData);
                                    this.updateHybridEmotionDisplay(emotionData);
                                }
                                else if (messageType === 'emotion_detected' && emotionData) {
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
}
window.addEventListener('DOMContentLoaded', () => {
    window.VoiceScannerApp = VoiceScannerApp;
    new VoiceScannerApp();
});
