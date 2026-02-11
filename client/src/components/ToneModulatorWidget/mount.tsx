/**
 * Tone Modulator Widget Mount Script
 *
 * Mounts the React-based Tone Modulator to the dashboard card 5
 * and exposes updateToneModulator for the main app (emotion_detected, tone_switched).
 */

import React from 'react';
import { createRoot, Root } from 'react-dom/client';
import { ToneModulator } from './ToneModulator';

const MAX_SERIES_LENGTH = 32;

// Default series matching reference: Clarity fluctuates ~0.2–0.6 ending ~0.5; Intensity rises to ~0.9
const DEFAULT_CLARITY = [0.2, 0.5, 0.6, 0.4, 0.55, 0.6, 0.5];
const DEFAULT_INTENSITY = [0.2, 0.5, 0.7, 0.3, 0.85, 0.9];

let root: Root | null = null;
let state = {
  detectedEmotion: 'neutral',
  nesterResponse: 'calm',
  clarityData: [...DEFAULT_CLARITY],
  intensityData: [...DEFAULT_INTENSITY],
  xAxisIntervalSec: 5,
};

function renderWidget(): void {
  if (!root) return;
  root.render(
    <ToneModulator
      detectedEmotion={state.detectedEmotion}
      nesterResponse={state.nesterResponse}
      clarityData={state.clarityData}
      intensityData={state.intensityData}
      xAxisIntervalSec={state.xAxisIntervalSec}
    />
  );
}

export function mountToneModulator(containerId: string = 'tone-modulator-root'): void {
  const container = document.getElementById(containerId);
  if (!container) {
    console.warn(`[ToneModulator] Container #${containerId} not found`);
    return;
  }

  if (root) {
    console.log('[ToneModulator] Widget already mounted');
    return;
  }

  root = createRoot(container);
  renderWidget();
  console.log('[ToneModulator] Widget mounted');
}

export interface ToneModulatorUpdate {
  detectedEmotion?: string;
  nesterResponse?: string;
  clarity?: number;
  intensity?: number;
  /** X-axis grid interval in seconds (e.g. 5, 10) */
  xAxisIntervalSec?: number;
}

/**
 * Update Tone Modulator state. Call from app on emotion_detected / hybrid_emotion_detected / tone_switched.
 * clarity/intensity can be derived from valence/arousal; if omitted, we keep existing series.
 */
export function updateToneModulator(update: ToneModulatorUpdate): void {
  let changed = false;
  if (update.detectedEmotion !== undefined) {
    state.detectedEmotion = update.detectedEmotion;
    changed = true;
  }
  if (update.nesterResponse !== undefined) {
    state.nesterResponse = update.nesterResponse;
    changed = true;
  }
  if (update.clarity !== undefined) {
    state.clarityData = [...state.clarityData, update.clarity].slice(-MAX_SERIES_LENGTH);
    changed = true;
  }
  if (update.intensity !== undefined) {
    state.intensityData = [...state.intensityData, update.intensity].slice(-MAX_SERIES_LENGTH);
    changed = true;
  }
  if (update.xAxisIntervalSec !== undefined) {
    state.xAxisIntervalSec = update.xAxisIntervalSec;
    changed = true;
  }
  if (changed) renderWidget();
}

export function unmountToneModulator(): void {
  if (root) {
    root.unmount();
    root = null;
    state = { detectedEmotion: 'neutral', nesterResponse: 'calm', clarityData: [...DEFAULT_CLARITY], intensityData: [...DEFAULT_INTENSITY], xAxisIntervalSec: 5 };
    console.log('[ToneModulator] Widget unmounted');
  }
}

declare global {
  interface Window {
    ToneModulator: {
      mount: typeof mountToneModulator;
      unmount: typeof unmountToneModulator;
      update: typeof updateToneModulator;
    };
  }
}

window.ToneModulator = {
  mount: mountToneModulator,
  unmount: unmountToneModulator,
  update: updateToneModulator,
};

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => mountToneModulator());
} else {
  setTimeout(() => mountToneModulator(), 100);
}

export default {
  mount: mountToneModulator,
  unmount: unmountToneModulator,
  update: updateToneModulator,
};
