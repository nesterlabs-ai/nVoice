/**
 * EmotionAnalysis Widget Mount Script
 *
 * Standalone widget - mounts to a DOM container and exposes updateTopics.
 * Use window.EmotionAnalysis.updateTopics(topicNodes) from anywhere.
 */

import React from 'react';
import { createRoot, Root } from 'react-dom/client';
import { EmotionAnalysis } from './EmotionAnalysis';
import type { EmotionTopicNode } from './types';

/** Default emotion topics for testing the EMOTION ANALYSIS UI */
function getDefaultEmotionTopics(): EmotionTopicNode[] {
  const base = Date.now() - 35000;
  const ts = (sec: number) => new Date(base + sec * 1000);
  return [
    { id: 'e-0', timestamp: ts(0), sentiment: 'positive', sentimentLabel: 'Positive', intensity: 0.6 },
    { id: 'e-1', timestamp: ts(6), sentiment: 'neutral', sentimentLabel: 'Calm', intensity: 0.35 },
    { id: 'e-2', timestamp: ts(12), sentiment: 'positive', sentimentLabel: 'Excited', intensity: 0.85 },
    { id: 'e-3', timestamp: ts(18), sentiment: 'neutral', sentimentLabel: 'Neutral', intensity: 0.5 },
    { id: 'e-4', timestamp: ts(24), sentiment: 'negative', sentimentLabel: 'Concerned', intensity: 0.55 },
    { id: 'e-5', timestamp: ts(30), sentiment: 'positive', sentimentLabel: 'Positive', intensity: 0.7 },
  ];
}

let root: Root | null = null;
let currentTopics: EmotionTopicNode[] = [];

function renderWidget(): void {
  if (!root) return;
  root.render(
    <EmotionAnalysis
      topics={currentTopics}
      hideTitle={true}
    />
  );
}

/**
 * Mount the EmotionAnalysis widget to a DOM element
 */
export function mountEmotionAnalysis(containerId: string = 'emotion-analysis-root'): void {
  const container = document.getElementById(containerId);
  if (!container) {
    console.warn(`[EmotionAnalysis] Container #${containerId} not found`);
    return;
  }

  if (root) {
    renderWidget();
    return;
  }

  root = createRoot(container);
  renderWidget();
}

/**
 * Update topics and re-render. Call from app when conversation messages change.
 * Accepts TopicNode[] from layoutTopics (compatible with EmotionTopicNode)
 */
export function updateEmotionAnalysisTopics(topics: EmotionTopicNode[]): void {
  currentTopics = topics;
  renderWidget();
}

/**
 * Unmount the widget
 */
export function unmountEmotionAnalysis(): void {
  if (root) {
    root.unmount();
    root = null;
    currentTopics = [];
  }
}

declare global {
  interface Window {
    EmotionAnalysis: {
      mount: typeof mountEmotionAnalysis;
      unmount: typeof unmountEmotionAnalysis;
      updateTopics: typeof updateEmotionAnalysisTopics;
    };
  }
}

window.EmotionAnalysis = {
  mount: mountEmotionAnalysis,
  unmount: unmountEmotionAnalysis,
  updateTopics: updateEmotionAnalysisTopics,
};

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => mountEmotionAnalysis());
} else {
  setTimeout(() => mountEmotionAnalysis(), 100);
}

export default {
  mount: mountEmotionAnalysis,
  unmount: unmountEmotionAnalysis,
  updateTopics: updateEmotionAnalysisTopics,
};
