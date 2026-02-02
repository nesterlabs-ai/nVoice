/**
 * LightRAG API Client
 * Communicates with the LightRAG server to fetch knowledge graph data
 */

import { KnowledgeGraph } from './types';

// LightRAG server URL - can be configured via environment variable or window global
const LIGHTRAG_URL = (window as any).__LIGHTRAG_URL__ ||
                     (window as any).LIGHTRAG_URL ||
                     'http://localhost:9621';

/**
 * Fetch the knowledge graph from LightRAG
 * @param label - Node label to filter by (use '*' for all nodes)
 * @param maxDepth - Maximum depth of graph traversal
 */
export async function fetchGraph(
  label: string = '*',
  maxDepth: number = 3
): Promise<KnowledgeGraph> {
  try {
    const url = `${LIGHTRAG_URL}/graphs?label=${encodeURIComponent(label)}&max_depth=${maxDepth}`;
    console.log('[KnowledgeGraph] Fetching from:', url);
    const response = await fetch(url, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        'ngrok-skip-browser-warning': 'true',  // Skip ngrok interstitial page
      },
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch graph: ${response.status} ${response.statusText}`);
    }

    const data = await response.json();
    console.log('[KnowledgeGraph] Fetched graph:', data.nodes?.length, 'nodes,', data.edges?.length, 'edges');
    return data;
  } catch (error) {
    console.error('[KnowledgeGraph] Error fetching graph:', error);
    throw error;
  }
}

/**
 * Fetch available graph labels from LightRAG
 */
export async function fetchGraphLabels(): Promise<string[]> {
  try {
    const response = await fetch(`${LIGHTRAG_URL}/graph/label/list`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        'ngrok-skip-browser-warning': 'true',
      },
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch labels: ${response.status}`);
    }

    return response.json();
  } catch (error) {
    console.error('[KnowledgeGraph] Error fetching labels:', error);
    throw error;
  }
}

/**
 * Check if LightRAG server is healthy
 */
export async function checkHealth(): Promise<boolean> {
  try {
    const response = await fetch(`${LIGHTRAG_URL}/health`, {
      method: 'GET',
      headers: {
        'ngrok-skip-browser-warning': 'true',
      },
    });
    return response.ok;
  } catch {
    return false;
  }
}
