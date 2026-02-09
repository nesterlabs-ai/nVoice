/**
 * Knowledge Graph API Client
 * Communicates with the NesterAI backend proxy to fetch knowledge graph data
 * The backend handles LightRAG authentication with the API key
 */

import { KnowledgeGraph } from './types';

// Use the backend proxy endpoint (same origin as the app)
// This keeps the LightRAG API key secure on the server side
const getApiBaseUrl = (): string => {
  // In production, use the same origin
  // In development, the Vite proxy handles it
  return '';
};

/**
 * Fetch the knowledge graph from LightRAG via backend proxy
 * @param label - Node label to filter by (use '*' for all nodes)
 * @param maxDepth - Maximum depth of graph traversal
 */
export async function fetchGraph(
  label: string = '*',
  maxDepth: number = 3
): Promise<KnowledgeGraph> {
  try {
    const baseUrl = getApiBaseUrl();
    const url = `${baseUrl}/graph/data?label=${encodeURIComponent(label)}&max_depth=${maxDepth}`;
    console.log('[KnowledgeGraph] Fetching from proxy:', url);

    const response = await fetch(url, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
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
 * Note: This endpoint may not be proxied yet - falls back gracefully
 */
export async function fetchGraphLabels(): Promise<string[]> {
  try {
    const baseUrl = getApiBaseUrl();
    const response = await fetch(`${baseUrl}/graph/labels`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      console.warn('[KnowledgeGraph] Labels endpoint not available, returning empty');
      return [];
    }

    return response.json();
  } catch (error) {
    console.warn('[KnowledgeGraph] Error fetching labels:', error);
    return [];
  }
}

/**
 * Check if LightRAG server is healthy via backend proxy
 */
export async function checkHealth(): Promise<boolean> {
  try {
    const baseUrl = getApiBaseUrl();
    const response = await fetch(`${baseUrl}/graph/health`, {
      method: 'GET',
    });
    return response.ok;
  } catch {
    return false;
  }
}
