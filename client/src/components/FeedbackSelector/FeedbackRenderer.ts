/**
 * FeedbackRenderer - Vanilla TypeScript feedback form renderer
 *
 * Renders a feedback collection form in the DOM when the user ends conversation.
 * Similar to A2UIRenderer but specifically for feedback collection.
 */

interface FeedbackOption {
  label: string;
  value: string;
  emoji?: string;
}

interface FeedbackQuestion {
  id: string;
  question: string;
  options: FeedbackOption[];
}

interface FeedbackConfig {
  title: string;
  subtitle: string;
  questions: FeedbackQuestion[];
  config: {
    submitButtonText: string;
    skipButtonText: string;
    timeoutSeconds: number;
    showProgressBar?: boolean;
    theme?: string;
  };
  session_id: string;
  timestamp?: number;
}

export class FeedbackRenderer {
  private container: HTMLElement;
  private selections: Map<string, string> = new Map();
  private onSubmit: (responses: Record<string, string>, skipped: boolean) => void;
  private timeoutId: number | null = null;
  private remainingTime: number = 45;
  private config: FeedbackConfig | null = null;
  private isSubmitting: boolean = false;
  private isSubmitted: boolean = false;

  constructor(
    containerId: string,
    onSubmit: (responses: Record<string, string>, skipped: boolean) => void
  ) {
    let element = document.getElementById(containerId);
    if (!element) {
      // Create the container if it doesn't exist
      element = document.createElement('div');
      element.id = containerId;
      document.body.appendChild(element);
    }
    this.container = element;
    this.onSubmit = onSubmit;
    console.log('[Feedback] Renderer initialized');
  }

  /**
   * Render the feedback form
   */
  render(config: FeedbackConfig): void {
    this.config = config;
    this.selections.clear();
    this.isSubmitting = false;
    this.isSubmitted = false;
    this.remainingTime = config.config.timeoutSeconds || 30;

    this.container.innerHTML = this.buildOverlay();
    this.attachEventListeners();
    this.startTimeout();

    console.log('[Feedback] Form rendered for session:', config.session_id);
  }

  private buildOverlay(): string {
    if (!this.config) return '';

    return `
      <div class="feedback-overlay" id="feedback-overlay">
        <div class="feedback-modal">
          <div class="feedback-container">
            ${this.buildHeader()}
            ${this.buildProgress()}
            ${this.buildQuestions()}
            ${this.buildTimeout()}
            ${this.buildActions()}
          </div>
        </div>
      </div>
    `;
  }

  private buildHeader(): string {
    if (!this.config) return '';
    return `
      <div class="feedback-header">
        <div class="feedback-icon-container">
          <svg class="feedback-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
          </svg>
        </div>
        <h2 class="feedback-title">${this.escapeHtml(this.config.title)}</h2>
        <p class="feedback-subtitle">${this.escapeHtml(this.config.subtitle)}</p>
      </div>
    `;
  }

  private buildProgress(): string {
    if (!this.config) return '';
    const answered = this.selections.size;
    const total = this.config.questions.length;
    const allAnswered = answered === total;
    const percentage = (answered / total) * 100;

    return `
      <div class="feedback-progress">
        <span class="feedback-progress-text">${answered} of ${total} answered</span>
        <span class="feedback-progress-status ${allAnswered ? 'complete' : ''}">
          ${allAnswered ? 'Ready to submit!' : 'Please answer all questions'}
        </span>
      </div>
      <div class="feedback-progress-bar">
        <div class="feedback-progress-fill" style="width: ${percentage}%"></div>
      </div>
    `;
  }

  private buildQuestions(): string {
    if (!this.config) return '';
    return `
      <div class="feedback-questions">
        ${this.config.questions.map((q, idx) => this.buildQuestion(q, idx)).join('')}
      </div>
    `;
  }

  private buildQuestion(question: FeedbackQuestion, index: number): string {
    const isAnswered = this.selections.has(question.id);
    return `
      <div class="feedback-question ${isAnswered ? 'answered' : ''}" data-question-id="${question.id}">
        <div class="feedback-question-header">
          <span class="feedback-question-number ${isAnswered ? 'completed' : ''}">${index + 1}</span>
          <h3 class="feedback-question-text">${this.escapeHtml(question.question)}</h3>
        </div>
        <div class="feedback-options">
          ${question.options.map(opt => this.buildOption(question.id, opt)).join('')}
        </div>
      </div>
    `;
  }

  private buildOption(questionId: string, option: FeedbackOption): string {
    const isSelected = this.selections.get(questionId) === option.value;
    return `
      <button
        class="feedback-option ${isSelected ? 'selected' : ''}"
        data-question="${questionId}"
        data-value="${option.value}"
      >
        ${option.emoji ? `<span class="feedback-option-emoji">${option.emoji}</span>` : ''}
        <span class="feedback-option-label">${this.escapeHtml(option.label)}</span>
      </button>
    `;
  }

  private buildTimeout(): string {
    return `
      <div class="feedback-timeout">
        Auto-closing in <span class="feedback-timeout-value" id="feedback-timer">${this.remainingTime}</span> seconds
      </div>
    `;
  }

  private buildActions(): string {
    if (!this.config) return '';
    const allAnswered = this.selections.size === this.config.questions.length;
    return `
      <div class="feedback-actions">
        <button class="feedback-btn-skip" id="feedback-skip">
          ${this.escapeHtml(this.config.config.skipButtonText)}
        </button>
        <button class="feedback-btn-submit ${allAnswered ? '' : 'disabled'}" id="feedback-submit">
          ${allAnswered ? this.escapeHtml(this.config.config.submitButtonText) : `Answer all ${this.config.questions.length} questions`}
        </button>
      </div>
    `;
  }

  private attachEventListeners(): void {
    // Option buttons
    this.container.querySelectorAll('.feedback-option').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const target = e.currentTarget as HTMLElement;
        const questionId = target.dataset.question!;
        const value = target.dataset.value!;
        this.selectOption(questionId, value);
      });
    });

    // Skip button
    const skipBtn = this.container.querySelector('#feedback-skip');
    skipBtn?.addEventListener('click', () => this.handleSkip());

    // Submit button
    const submitBtn = this.container.querySelector('#feedback-submit');
    submitBtn?.addEventListener('click', () => this.handleSubmit());
  }

  private selectOption(questionId: string, value: string): void {
    this.selections.set(questionId, value);
    this.updateUI();
  }

  private updateUI(): void {
    if (!this.config) return;

    // Update progress
    const progressText = this.container.querySelector('.feedback-progress-text');
    const progressStatus = this.container.querySelector('.feedback-progress-status');
    const progressFill = this.container.querySelector('.feedback-progress-fill') as HTMLElement;
    const answered = this.selections.size;
    const total = this.config.questions.length;
    const allAnswered = answered === total;

    if (progressText) progressText.textContent = `${answered} of ${total} answered`;
    if (progressStatus) {
      progressStatus.textContent = allAnswered ? 'Ready to submit!' : 'Please answer all questions';
      progressStatus.classList.toggle('complete', allAnswered);
    }
    if (progressFill) progressFill.style.width = `${(answered / total) * 100}%`;

    // Update question states
    this.config.questions.forEach((q) => {
      const questionEl = this.container.querySelector(`[data-question-id="${q.id}"]`);
      const numberEl = questionEl?.querySelector('.feedback-question-number');
      const isAnswered = this.selections.has(q.id);

      questionEl?.classList.toggle('answered', isAnswered);
      numberEl?.classList.toggle('completed', isAnswered);

      // Update option selection states
      q.options.forEach(opt => {
        const optBtn = this.container.querySelector(
          `.feedback-option[data-question="${q.id}"][data-value="${opt.value}"]`
        );
        optBtn?.classList.toggle('selected', this.selections.get(q.id) === opt.value);
      });
    });

    // Update submit button
    const submitBtn = this.container.querySelector('#feedback-submit') as HTMLElement;
    if (submitBtn) {
      submitBtn.classList.toggle('disabled', !allAnswered);
      submitBtn.textContent = allAnswered
        ? this.config.config.submitButtonText
        : `Answer all ${total} questions`;
    }
  }

  private startTimeout(): void {
    this.timeoutId = window.setInterval(() => {
      this.remainingTime--;
      const timerEl = this.container.querySelector('#feedback-timer');
      if (timerEl) timerEl.textContent = String(this.remainingTime);

      if (this.remainingTime <= 0) {
        this.handleTimeout();
      }
    }, 1000);
  }

  private stopTimeout(): void {
    if (this.timeoutId) {
      clearInterval(this.timeoutId);
      this.timeoutId = null;
    }
  }

  private async handleSubmit(): Promise<void> {
    if (!this.config || this.isSubmitting) return;
    if (this.selections.size !== this.config.questions.length) return;

    this.isSubmitting = true;
    this.stopTimeout();
    this.showLoading();

    const responses: Record<string, string> = {};
    this.selections.forEach((value, key) => {
      responses[key] = value;
    });

    try {
      this.onSubmit(responses, false);
      this.showThankYou();
    } catch (error) {
      console.error('[Feedback] Submit error:', error);
      this.isSubmitting = false;
    }
  }

  private handleSkip(): void {
    this.stopTimeout();
    this.onSubmit({}, true);
    this.close();
  }

  private handleTimeout(): void {
    this.stopTimeout();
    const responses: Record<string, string> = {};
    this.selections.forEach((value, key) => {
      responses[key] = value;
    });
    this.onSubmit(responses, this.selections.size === 0);
    this.close();
  }

  private showLoading(): void {
    const modal = this.container.querySelector('.feedback-modal');
    if (modal) {
      modal.innerHTML = `
        <div class="feedback-container">
          <div class="feedback-loading">
            <div class="feedback-spinner"></div>
            <h2>Submitting Feedback...</h2>
            <p>Thank you for taking the time</p>
          </div>
        </div>
      `;
    }
  }

  private buildFeedbackSummary(): string {
    if (!this.config || this.selections.size === 0) {
      return '';
    }

    const summaryItems: string[] = [];

    for (const question of this.config.questions) {
      const selectedValue = this.selections.get(question.id);
      if (selectedValue) {
        const selectedOption = question.options.find(opt => opt.value === selectedValue);
        if (selectedOption) {
          const emoji = selectedOption.emoji ? `<span class="feedback-summary-emoji">${selectedOption.emoji}</span>` : '';
          // Extract short question label (e.g., "Overall Experience" from "How was your overall experience?")
          const questionLabel = this.getShortQuestionLabel(question.question);
          summaryItems.push(`
            <div class="feedback-summary-item">
              <span class="feedback-summary-question">${this.escapeHtml(questionLabel)}:</span>
              <span class="feedback-summary-answer">${emoji} ${this.escapeHtml(selectedOption.label)}</span>
            </div>
          `);
        }
      }
    }

    return summaryItems.join('');
  }

  private getShortQuestionLabel(question: string): string {
    // Convert "How was your overall experience?" to "Overall Experience"
    // Convert "Did you find the information helpful?" to "Information Helpful"
    // Convert "How was the voice quality?" to "Voice Quality"
    // Convert "Would you use this service again?" to "Would Use Again"
    const labelMap: Record<string, string> = {
      'How was your overall experience?': 'Overall Experience',
      'Did you find the information helpful?': 'Information Helpful',
      'How was the voice quality?': 'Voice Quality',
      'Would you use this service again?': 'Would Use Again'
    };
    return labelMap[question] || question.replace(/\?$/, '');
  }

  private showThankYou(): void {
    this.isSubmitted = true;
    const modal = this.container.querySelector('.feedback-modal');
    const hasFeedback = this.selections.size > 0;
    const summaryHtml = this.buildFeedbackSummary();

    if (modal) {
      modal.innerHTML = `
        <div class="feedback-container">
          <div class="feedback-success">
            <svg class="feedback-check" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
              <polyline points="22 4 12 14.01 9 11.01"></polyline>
            </svg>
            <h2>Thank You!</h2>
            ${hasFeedback ? `
              <div class="feedback-summary">
                <p class="feedback-summary-title">Your feedback:</p>
                ${summaryHtml}
              </div>
            ` : '<p>Your feedback helps us improve.</p>'}
          </div>
        </div>
      `;
    }

    // Auto-close after showing thank you (longer to allow TTS to speak the full summary)
    // TTS needs ~15s to speak all 4 feedback selections
    setTimeout(() => this.close(), hasFeedback ? 15000 : 2000);
  }

  /**
   * Close and remove the feedback form
   */
  close(): void {
    this.stopTimeout();
    const overlay = this.container.querySelector('#feedback-overlay');
    if (overlay) {
      overlay.classList.add('fade-out');
      setTimeout(() => {
        this.container.innerHTML = '';
      }, 300);
    } else {
      this.container.innerHTML = '';
    }
    console.log('[Feedback] Form closed');
  }

  /**
   * Check if feedback form is currently visible
   */
  isVisible(): boolean {
    return this.container.querySelector('#feedback-overlay') !== null;
  }

  private escapeHtml(text: string): string {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }
}

// Singleton instance
let _feedbackRendererInstance: FeedbackRenderer | null = null;

export function getFeedbackRenderer(
  containerId: string = 'feedback-root',
  onSubmit: (responses: Record<string, string>, skipped: boolean) => void
): FeedbackRenderer {
  if (!_feedbackRendererInstance) {
    _feedbackRendererInstance = new FeedbackRenderer(containerId, onSubmit);
  }
  return _feedbackRendererInstance;
}
