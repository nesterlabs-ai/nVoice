import { useState, useEffect } from "react";
import { Loader2, CheckCircle, MessageSquare } from "lucide-react";

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

interface FeedbackSelectorProps {
  questions: FeedbackQuestion[];
  onSubmit: (responses: Record<string, string>, skipped: boolean) => Promise<void>;
  onSkip?: () => void;
  title?: string;
  subtitle?: string;
  submitButtonText?: string;
  skipButtonText?: string;
  timeoutSeconds?: number;
  showTimeout?: boolean;
}

/**
 * FeedbackSelector - Visual feedback collection component
 *
 * Displays ALL feedback questions at once for quick selection.
 * Designed to show when user says "bye" to collect feedback before closing.
 *
 * Features:
 * - Shows all questions simultaneously
 * - Optional countdown timer
 * - Skip and Submit buttons
 * - Thank you animation after submission
 */
export const FeedbackSelector = ({
  questions,
  onSubmit,
  onSkip,
  title = "Quick Feedback",
  subtitle = "Help us improve your experience",
  submitButtonText = "Submit Feedback",
  skipButtonText = "Skip",
  timeoutSeconds = 45,
  showTimeout = true
}: FeedbackSelectorProps) => {
  const [selections, setSelections] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [remainingTime, setRemainingTime] = useState(timeoutSeconds);

  const answeredCount = Object.keys(selections).length;
  const allAnswered = answeredCount === questions.length;

  // Countdown timer
  useEffect(() => {
    if (!showTimeout || submitted || submitting) return;

    const timer = setInterval(() => {
      setRemainingTime((prev) => {
        if (prev <= 1) {
          clearInterval(timer);
          handleTimeout();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [showTimeout, submitted, submitting]);

  const handleSelect = (questionId: string, value: string) => {
    setSelections((prev) => ({
      ...prev,
      [questionId]: value
    }));
  };

  const handleSubmit = async () => {
    if (!allAnswered) return;

    setSubmitting(true);
    try {
      await onSubmit(selections, false);
      setSubmitted(true);
    } catch (error) {
      console.error("Feedback submit error:", error);
    } finally {
      setSubmitting(false);
    }
  };

  const handleSkip = () => {
    if (onSkip) {
      onSkip();
    } else {
      onSubmit({}, true);
    }
  };

  const handleTimeout = () => {
    // Submit whatever we have on timeout
    onSubmit(selections, answeredCount === 0);
  };

  // Loading state
  if (submitting) {
    return (
      <div className="feedback-container">
        <div className="feedback-loading">
          <Loader2 className="feedback-spinner" />
          <h2>Submitting Feedback...</h2>
          <p>Thank you for taking the time</p>
        </div>
      </div>
    );
  }

  // Success state
  if (submitted) {
    return (
      <div className="feedback-container">
        <div className="feedback-success">
          <CheckCircle className="feedback-check" />
          <h2>Thank You!</h2>
          <p>Your feedback helps us improve.</p>
        </div>
      </div>
    );
  }

  // Main feedback form
  return (
    <div className="feedback-container">
      {/* Header */}
      <div className="feedback-header">
        <div className="feedback-icon-container">
          <MessageSquare className="feedback-icon" />
        </div>
        <h2 className="feedback-title">{title}</h2>
        <p className="feedback-subtitle">{subtitle}</p>
      </div>

      {/* Progress */}
      <div className="feedback-progress">
        <span className="feedback-progress-text">
          {answeredCount} of {questions.length} answered
        </span>
        <span className={`feedback-progress-status ${allAnswered ? "complete" : ""}`}>
          {allAnswered ? "Ready to submit!" : "Please answer all questions"}
        </span>
      </div>
      <div className="feedback-progress-bar">
        <div
          className="feedback-progress-fill"
          style={{ width: `${(answeredCount / questions.length) * 100}%` }}
        />
      </div>

      {/* All Questions */}
      <div className="feedback-questions">
        {questions.map((q, qIndex) => {
          const isAnswered = selections[q.id] !== undefined;

          return (
            <div
              key={q.id}
              className={`feedback-question ${isAnswered ? "answered" : ""}`}
            >
              {/* Question Header */}
              <div className="feedback-question-header">
                <span className={`feedback-question-number ${isAnswered ? "completed" : ""}`}>
                  {qIndex + 1}
                </span>
                <h3 className="feedback-question-text">{q.question}</h3>
              </div>

              {/* Options */}
              <div className="feedback-options">
                {q.options.map((opt) => {
                  const isSelected = selections[q.id] === opt.value;

                  return (
                    <button
                      key={opt.value}
                      onClick={() => handleSelect(q.id, opt.value)}
                      className={`feedback-option ${isSelected ? "selected" : ""}`}
                    >
                      {opt.emoji && <span className="feedback-option-emoji">{opt.emoji}</span>}
                      <span className="feedback-option-label">{opt.label}</span>
                    </button>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>

      {/* Timeout indicator */}
      {showTimeout && (
        <div className="feedback-timeout">
          Auto-closing in <span className="feedback-timeout-value">{remainingTime}</span> seconds
        </div>
      )}

      {/* Action Buttons */}
      <div className="feedback-actions">
        <button onClick={handleSkip} className="feedback-btn-skip">
          {skipButtonText}
        </button>
        <button
          onClick={handleSubmit}
          disabled={!allAnswered}
          className={`feedback-btn-submit ${allAnswered ? "" : "disabled"}`}
        >
          {allAnswered ? submitButtonText : `Answer all ${questions.length} questions`}
        </button>
      </div>
    </div>
  );
};

// Default feedback questions
export const DEFAULT_FEEDBACK_QUESTIONS: FeedbackQuestion[] = [
  {
    id: "overall_experience",
    question: "How was your overall experience?",
    options: [
      { label: "Excellent", value: "excellent", emoji: "😊" },
      { label: "Good", value: "good", emoji: "🙂" },
      { label: "Okay", value: "okay", emoji: "😐" },
      { label: "Poor", value: "poor", emoji: "😞" }
    ]
  },
  {
    id: "information_helpful",
    question: "Did you find the information helpful?",
    options: [
      { label: "Very Helpful", value: "very_helpful" },
      { label: "Somewhat", value: "somewhat" },
      { label: "Not Really", value: "not_really" },
      { label: "Not at All", value: "not_at_all" }
    ]
  },
  {
    id: "voice_quality",
    question: "How was the voice quality?",
    options: [
      { label: "Clear & Natural", value: "clear" },
      { label: "Mostly Clear", value: "mostly_clear" },
      { label: "Hard to Understand", value: "hard_to_understand" }
    ]
  },
  {
    id: "would_use_again",
    question: "Would you use this service again?",
    options: [
      { label: "Definitely", value: "definitely" },
      { label: "Probably", value: "probably" },
      { label: "Maybe", value: "maybe" },
      { label: "No", value: "no" }
    ]
  }
];

export default FeedbackSelector;
