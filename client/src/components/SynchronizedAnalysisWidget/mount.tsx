/**
 * SynchronizedAnalysis Widget Mount Script
 *
 * Mounts the React-based SynchronizedAnalysis (Topic Flow + Emotion Analysis)
 * to the left panel and exposes methods for the main app to update topics.
 */

import React from 'react';
import { createRoot, Root } from 'react-dom/client';
import { SynchronizedAnalysis } from './SynchronizedAnalysis';
import { TopicNode } from './topicExtraction';

import './SynchronizedAnalysis.css';

/** Default topic nodes for testing the CONVERSATION ANALYSIS UI */
function getDefaultTopicNodes(): TopicNode[] {
  const base = Date.now() - 35000;
  const ts = (sec: number) => new Date(base + sec * 1000);
  const topics: TopicNode[] = [
    { id: 'topic-0', name: 'Color & Branding', timestamp: ts(0), keywords: ['color', 'design'], category: 'Design', color: '#3b82f6', sentiment: 'positive', sentimentLabel: 'Positive', intensity: 0.7, row: 0, x: 120, y: 100 },
    { id: 'topic-1', name: 'Web Development', timestamp: ts(8), keywords: ['web', 'app'], category: 'Technology', color: '#10b981', sentiment: 'neutral', sentimentLabel: 'Neutral', intensity: 0.5, aiRole: 'suggesting', row: 1, x: 270, y: 135 },
    { id: 'topic-2', name: 'Services', timestamp: ts(16), keywords: ['service', 'solution'], category: 'Business', color: '#f59e0b', sentiment: 'positive', sentimentLabel: 'Excited', intensity: 0.8, aiRole: 'explaining', row: 2, x: 420, y: 170 },
    { id: 'topic-3', name: 'Typography', timestamp: ts(24), keywords: ['font', 'layout'], category: 'Design', color: '#3b82f6', sentiment: 'neutral', sentimentLabel: 'Calm', intensity: 0.4, row: 0, x: 570, y: 100 },
    { id: 'topic-4', name: 'AI & ML', timestamp: ts(32), keywords: ['ai', 'machine learning'], category: 'Technology', color: '#10b981', sentiment: 'positive', sentimentLabel: 'Positive', intensity: 0.6, aiRole: 'agreeing', row: 1, x: 720, y: 135 },
  ];
  return topics;
}

let root: Root | null = null;
let currentTopics: TopicNode[] = getDefaultTopicNodes();

function renderWidget(): void {
  if (!root) return;
  root.render(<SynchronizedAnalysis topics={currentTopics} />);
}

/**
 * Initialize and mount the SynchronizedAnalysis widget
 */
export function mountSynchronizedAnalysis(containerId: string = 'synchronized-analysis-root'): void {
  const container = document.getElementById(containerId);
  if (!container) {
    console.warn(`[SynchronizedAnalysis] Container #${containerId} not found`);
    return;
  }

  if (root) {
    console.log('[SynchronizedAnalysis] Widget already mounted');
    return;
  }

  root = createRoot(container);
  renderWidget();
  console.log('[SynchronizedAnalysis] Widget mounted');
}

/**
 * Update topics and re-render
 */
export function updateSynchronizedAnalysisTopics(topics: TopicNode[]): void {
  currentTopics = topics;
  renderWidget();
}

/**
 * Unmount the widget
 */
export function unmountSynchronizedAnalysis(): void {
  if (root) {
    root.unmount();
    root = null;
    currentTopics = [];
    console.log('[SynchronizedAnalysis] Widget unmounted');
  }
}

declare global {
  interface Window {
    SynchronizedAnalysis: {
      mount: typeof mountSynchronizedAnalysis;
      unmount: typeof unmountSynchronizedAnalysis;
      updateTopics: typeof updateSynchronizedAnalysisTopics;
    };
  }
}

window.SynchronizedAnalysis = {
  mount: mountSynchronizedAnalysis,
  unmount: unmountSynchronizedAnalysis,
  updateTopics: updateSynchronizedAnalysisTopics,
};

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => mountSynchronizedAnalysis());
} else {
  setTimeout(() => mountSynchronizedAnalysis(), 100);
}

export default {
  mount: mountSynchronizedAnalysis,
  unmount: unmountSynchronizedAnalysis,
  updateTopics: updateSynchronizedAnalysisTopics,
};
