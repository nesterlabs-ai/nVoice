/**
 * Knowledge Graph Widget
 *
 * Displays the LightRAG knowledge graph in a fixed position widget.
 * Highlights nodes based on keywords extracted from user queries.
 * Based on LightRAG's graph visualization implementation.
 */

import React, { useEffect, useState, useCallback, useRef } from 'react';
import {
  SigmaContainer,
  useRegisterEvents,
  useSigma,
  useLoadGraph,
  useSetSettings,
  useCamera,
} from '@react-sigma/core';
import { useLayoutForceAtlas2 } from '@react-sigma/layout-forceatlas2';
import Graph from 'graphology';
import { EdgeArrowProgram } from 'sigma/rendering';
import EdgeCurveProgram, { EdgeCurvedArrowProgram } from '@sigma/edge-curve';
import MiniSearch from 'minisearch';
import seedrandom from 'seedrandom';

import { fetchGraph } from './api';
import { KnowledgeGraph, GraphWidgetProps } from './types';

import '@react-sigma/core/lib/style.css';
import './styles.css';

// Constants for styling - matching LightRAG's pattern
const COLORS = {
  nodeDefault: '#9ca3af',
  nodeHighlighted: '#ef4444',
  nodeDisabled: '#4b5563',
  edgeDefault: '#7D7D7D',
  edgeHighlighted: '#ef4444',
  labelDefault: '#e5e7eb',
  labelHighlighted: '#000000',  // Dark text for highlighted nodes
};

const MIN_NODE_SIZE = 5;
const MAX_NODE_SIZE = 15;

function randomColor(seed: string): string {
  seedrandom(seed, { global: true });
  const colors = ['#9ca3af', '#a1a1aa', '#78716c'];
  return colors[Math.floor(Math.random() * colors.length)];
}

/**
 * Graph Events Handler - handles click events
 */
function GraphEvents({ onNodeClick }: { onNodeClick?: (nodeId: string) => void }) {
  const registerEvents = useRegisterEvents();

  useEffect(() => {
    registerEvents({
      clickNode: (event: { node: string }) => {
        onNodeClick?.(event.node);
      },
    });
  }, [registerEvents, onNodeClick]);

  return null;
}

/**
 * FocusOnNode - highlights node, centers camera on it, and zooms in slightly
 */
function FocusOnNode({ node }: { node: string | null }) {
  const sigma = useSigma();
  const { gotoNode } = useCamera();

  useEffect(() => {
    if (!node) return;

    const graph = sigma.getGraph();
    if (!graph.hasNode(node)) return;

    // Set highlighted attribute
    graph.setNodeAttribute(node, 'highlighted', true);

    // First center on node using gotoNode (this works reliably)
    gotoNode(node);

    // Then zoom in slightly after a small delay
    const camera = sigma.getCamera();
    setTimeout(() => {
      const currentState = camera.getState();
      camera.animate(
        { ...currentState, ratio: 0.35 },
        { duration: 300, easing: 'cubicInOut' }
      );
    }, 100);

    return () => {
      if (graph.hasNode(node)) {
        graph.setNodeAttribute(node, 'highlighted', false);
      }
    };
  }, [node, sigma, gotoNode]);

  return null;
}

/**
 * InitialZoom - animates camera zoom after page loads
 * Creates a visible zoom-in effect so users see the graph "coming to life"
 */
function InitialZoom({ graphLoaded }: { graphLoaded: boolean }) {
  const sigma = useSigma();
  const zoomApplied = useRef(false);
  const [pageReady, setPageReady] = useState(false);

  // Listen for page ready event (dispatched when loading overlay hides)
  useEffect(() => {
    const handlePageReady = () => setPageReady(true);
    window.addEventListener('nesterPageReady', handlePageReady);
    return () => window.removeEventListener('nesterPageReady', handlePageReady);
  }, []);

  useEffect(() => {
    if (!graphLoaded || zoomApplied.current) return;

    const camera = sigma.getCamera();

    // Start zoomed out
    camera.setState({ ratio: 1.5, x: 0.5, y: 0.5 });

    // Wait for page ready, then animate zoom in
    if (pageReady) {
      const timer = setTimeout(() => {
        zoomApplied.current = true;
        // Zoom in to ratio 0.5 for a closer view
        camera.animate(
          { ratio: 0.5, x: 0.5, y: 0.5 },
          { duration: 1200, easing: 'cubicInOut' }
        );
      }, 200);

      return () => clearTimeout(timer);
    }
  }, [graphLoaded, pageReady, sigma]);

  return null;
}

/**
 * GraphControl - handles graph loading and node/edge styling via reducers
 * Following LightRAG's pattern with setSettings
 */
function GraphControl({
  graphData,
  highlightedNodes,
  focusedNode,
}: {
  graphData: KnowledgeGraph | null;
  highlightedNodes: Set<string>;
  focusedNode: string | null;
}) {
  const sigma = useSigma();
  const loadGraph = useLoadGraph();
  const setSettings = useSetSettings();
  const { assign: assignLayout } = useLayoutForceAtlas2({ iterations: 50 });
  const graphLoadedRef = useRef(false);

  // Load graph data once
  useEffect(() => {
    if (!graphData || graphLoadedRef.current) return;
    graphLoadedRef.current = true;

    const graph = new Graph();

    // Calculate node degrees for sizing
    const degrees: Record<string, number> = {};
    graphData.nodes.forEach((n) => { degrees[n.id] = 0; });
    graphData.edges.forEach((e) => {
      degrees[e.source] = (degrees[e.source] || 0) + 1;
      degrees[e.target] = (degrees[e.target] || 0) + 1;
    });

    const maxDegree = Math.max(...Object.values(degrees), 1);
    const minDegree = Math.min(...Object.values(degrees), 0);
    const range = maxDegree - minDegree || 1;

    // Add nodes
    graphData.nodes.forEach((node) => {
      const degree = degrees[node.id] || 0;
      const size = MIN_NODE_SIZE + (MAX_NODE_SIZE - MIN_NODE_SIZE) * Math.pow((degree - minDegree) / range, 0.5);

      const displayName = node.labels?.length > 0
        ? node.labels.join(', ')
        : (node.properties?.name || node.properties?.entity_name || node.id);

      graph.addNode(node.id, {
        label: displayName,
        color: randomColor(node.id),
        x: node.x ?? Math.random(),
        y: node.y ?? Math.random(),
        size,
      });
    });

    // Add edges
    graphData.edges.forEach((edge) => {
      if (graph.hasNode(edge.source) && graph.hasNode(edge.target)) {
        try {
          graph.addDirectedEdge(edge.source, edge.target, {
            label: edge.type,
            color: COLORS.edgeDefault,
          });
        } catch {
          // Edge might already exist
        }
      }
    });

    loadGraph(graph);
    setTimeout(() => assignLayout(), 100);
  }, [graphData, loadGraph, assignLayout]);

  // Set up reducers - re-run when highlightedNodes or focusedNode changes
  // Following LightRAG's pattern exactly
  useEffect(() => {
    setSettings({
      nodeReducer: (node, data) => {
        const newData: Record<string, any> = {
          ...data,
          highlighted: data.highlighted || false,
          labelColor: COLORS.labelDefault,
        };

        // If we have highlighted nodes, apply styling
        if (highlightedNodes.size > 0) {
          if (highlightedNodes.has(node)) {
            newData.highlighted = true;
            newData.color = COLORS.nodeHighlighted;
            newData.labelColor = COLORS.labelHighlighted;  // Dark text for contrast
          } else {
            newData.color = COLORS.nodeDisabled;
          }
        }

        return newData;
      },
      edgeReducer: (edge, data) => {
        const graph = sigma.getGraph();
        const newData = { ...data };

        if (highlightedNodes.size > 0) {
          const [source, target] = graph.extremities(edge);
          if (highlightedNodes.has(source) || highlightedNodes.has(target)) {
            newData.color = COLORS.edgeHighlighted;
          } else {
            newData.color = COLORS.edgeDefault;
          }
        }

        return newData;
      },
    });
  }, [highlightedNodes, focusedNode, setSettings, sigma]);

  return null;
}

/**
 * Main Knowledge Graph Widget Component
 */
export function KnowledgeGraphWidget({
  highlightKeywords = [],
  focusNodeId,
  visible = true,
  onNodeClick,
  className = '',
}: GraphWidgetProps) {
  const [graphData, setGraphData] = useState<KnowledgeGraph | null>(null);
  const [searchIndex, setSearchIndex] = useState<MiniSearch<{ id: number; nodeId: string; label: string }> | null>(null);
  const [highlightedNodes, setHighlightedNodes] = useState<Set<string>>(new Set());
  const [focusedNode, setFocusedNode] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [allNodeIds, setAllNodeIds] = useState<Set<string>>(new Set());
  const cycleIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Load graph on mount
  useEffect(() => {
    async function loadGraphData() {
      try {
        setLoading(true);
        setError(null);

        const data = await fetchGraph('*', 10);
        setGraphData(data);

        const nodeIds = new Set(data.nodes.map((n) => n.id.toLowerCase()));
        setAllNodeIds(nodeIds);

        const index = new MiniSearch<{ id: number; nodeId: string; label: string }>({
          fields: ['label'],
          storeFields: ['label', 'nodeId'],
          searchOptions: { fuzzy: 0.2, prefix: true },
        });

        index.addAll(data.nodes.map((n, i) => ({
          id: i,
          nodeId: n.id,
          label: n.id.toLowerCase(),
        })));

        setSearchIndex(index);
        console.log('[KnowledgeGraph] Graph loaded:', data.nodes.length, 'nodes');
      } catch (e) {
        console.error('[KnowledgeGraph] Failed to load graph:', e);
        setError('Failed to load knowledge graph');
      } finally {
        setLoading(false);
      }
    }

    loadGraphData();
  }, []);

  // Handle keyword highlighting and cycling - show one node at a time
  useEffect(() => {
    // Clear any existing cycle
    if (cycleIntervalRef.current) {
      clearInterval(cycleIntervalRef.current);
      cycleIntervalRef.current = null;
    }

    if (!searchIndex || !graphData || highlightKeywords.length === 0) {
      setHighlightedNodes(new Set());
      setFocusedNode(null);
      return;
    }

    const matchedNodes: string[] = [];

    highlightKeywords.forEach((keyword) => {
      const kw = keyword.toLowerCase().trim();
      if (!kw) return;

      if (allNodeIds.has(kw)) {
        const node = graphData.nodes.find((n) => n.id.toLowerCase() === kw);
        if (node && !matchedNodes.includes(node.id)) {
          matchedNodes.push(node.id);
        }
      } else {
        const results = searchIndex.search(kw).slice(0, 3);
        results.forEach((result) => {
          const node = graphData.nodes[result.id];
          if (node && !matchedNodes.includes(node.id)) {
            matchedNodes.push(node.id);
          }
        });
      }
    });

    console.log('[KnowledgeGraph] Matched nodes for cycling:', matchedNodes);

    if (matchedNodes.length === 0) {
      setHighlightedNodes(new Set());
      setFocusedNode(null);
      return;
    }

    // Show first node only
    setHighlightedNodes(new Set([matchedNodes[0]]));
    setFocusedNode(matchedNodes[0]);

    // Cycle through nodes one by one
    if (matchedNodes.length > 1) {
      let currentIndex = 0;

      cycleIntervalRef.current = setInterval(() => {
        currentIndex = (currentIndex + 1) % matchedNodes.length;
        const currentNode = matchedNodes[currentIndex];

        // Highlight only the current node
        setHighlightedNodes(new Set([currentNode]));
        setFocusedNode(currentNode);

        // Stop after one complete cycle back to first
        if (currentIndex === 0) {
          if (cycleIntervalRef.current) {
            clearInterval(cycleIntervalRef.current);
            cycleIntervalRef.current = null;
          }
        }
      }, 2000);
    }

    return () => {
      if (cycleIntervalRef.current) {
        clearInterval(cycleIntervalRef.current);
        cycleIntervalRef.current = null;
      }
    };
  }, [highlightKeywords, searchIndex, graphData, allNodeIds]);

  const getAvailableKeywords = useCallback(() => {
    return graphData?.nodes.map((n) => n.id) || [];
  }, [graphData]);

  useEffect(() => {
    (window as any).getGraphKeywords = getAvailableKeywords;
    return () => { delete (window as any).getGraphKeywords; };
  }, [getAvailableKeywords]);

  const handleNodeClick = useCallback((nodeId: string) => {
    if (onNodeClick && graphData) {
      const nodeData = graphData.nodes.find((n) => n.id === nodeId);
      if (nodeData) onNodeClick(nodeId, nodeData);
    }
  }, [onNodeClick, graphData]);

  if (!visible) return null;

  const sigmaSettings = {
    allowInvalidContainer: true,
    defaultNodeType: 'circle',
    defaultEdgeType: 'curvedArrow',
    renderEdgeLabels: false,
    renderLabels: true,
    labelSize: 12,
    labelColor: { color: COLORS.labelDefault, attribute: 'labelColor' },
    labelRenderedSizeThreshold: 4,
    edgeProgramClasses: {
      curvedArrow: EdgeCurvedArrowProgram,
      curved: EdgeCurveProgram,
      arrow: EdgeArrowProgram,
    },
  };

  return (
    <div className={`knowledge-graph-widget ${className}`}>
      <div className="kg-container">
        {loading && (
          <div className="kg-loading">
            <div className="kg-spinner"></div>
            <span>Loading graph...</span>
          </div>
        )}

        {error && (
          <div className="kg-error">
            <span>{error}</span>
          </div>
        )}

        {!loading && !error && graphData && (
          <SigmaContainer settings={sigmaSettings} className="kg-sigma">
            <GraphControl
              graphData={graphData}
              highlightedNodes={highlightedNodes}
              focusedNode={focusedNode}
            />
            <GraphEvents onNodeClick={handleNodeClick} />
            <FocusOnNode node={focusedNode} />
            <InitialZoom graphLoaded={!!graphData} />
          </SigmaContainer>
        )}
      </div>

      {highlightedNodes.size > 0 && (
        <div className="kg-highlights">
          <span className="kg-highlights-label">NODES:</span>
          <div className="kg-highlights-list">
            {[...highlightedNodes].slice(0, 5).map((nodeId) => {
              const node = graphData?.nodes.find((n) => n.id === nodeId);
              const displayName = node?.labels?.length
                ? node.labels[0]
                : (node?.properties?.name || nodeId);
              const isFocused = nodeId === (focusNodeId || focusedNode);
              return (
                <span
                  key={nodeId}
                  className={`kg-highlight-tag ${isFocused ? 'kg-highlight-focused' : ''}`}
                >
                  {displayName}
                </span>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

export default KnowledgeGraphWidget;
