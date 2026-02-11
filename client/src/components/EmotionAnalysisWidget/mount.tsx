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
    console.log('[EmotionAnalysis] Widget already mounted');
    renderWidget();
    return;
  }

  root = createRoot(container);
  renderWidget();
  console.log('[EmotionAnalysis] Widget mounted');
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
    console.log('[EmotionAnalysis] Widget unmounted');
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
