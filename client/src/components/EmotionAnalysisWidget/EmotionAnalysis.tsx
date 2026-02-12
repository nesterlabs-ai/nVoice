import { useEffect, useRef, useState } from 'react';
import { motion } from 'motion/react';
import type { EmotionTopicNode } from './types';
import './EmotionAnalysis.css';

const DEFAULT_CHART_HEIGHT = 300;
const MIN_CHART_HEIGHT = 160;

/** Axis label font sizes (px). Change these to adjust readability. */
const Y_AXIS_LABEL_FONT_SIZE = 10;
const SENTIMENT_LABEL_FONT_SIZE = 10;
const SENTIMENT_EMOJI_FONT_SIZE = 14;

export interface EmotionAnalysisProps {
  topics: EmotionTopicNode[];
  /** Optional: hide the header when embedded in another card */
  hideTitle?: boolean;
}

const sentimentToEmoji: { [key: string]: string } = {
  'Excited': '😄',
  'Positive': '🙂',
  'Neutral': '😐',
  'Calm': '😌',
  'Concerned': '😟',
};

function calculateEmotionMetrics(topic: EmotionTopicNode) {
  let valence = 0.5;
  if (topic.sentiment === 'positive') valence = 0.2 + topic.intensity * 0.6;
  if (topic.sentiment === 'negative') valence = 0.2 - topic.intensity * 0.2;
  const arousal = topic.intensity;
  let dominance = 0.5;
  if (topic.sentimentLabel === 'Excited') dominance = 0.7;
  if (topic.sentimentLabel === 'Positive') dominance = 0.6;
  if (topic.sentimentLabel === 'Concerned') dominance = 0.3;
  return { valence, arousal, dominance };
}

export function EmotionAnalysis({ topics, hideTitle }: EmotionAnalysisProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const bodyRef = useRef<HTMLDivElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const [scrollLeft, setScrollLeft] = useState(0);
  const [chartHeight, setChartHeight] = useState(DEFAULT_CHART_HEIGHT);

  useEffect(() => {
    const el = bodyRef.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => {
      const h = entry.contentRect.height;
      setChartHeight(Math.max(MIN_CHART_HEIGHT, Math.round(h)));
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const handleScrollInternal = () => {
    if (scrollRef.current) setScrollLeft(scrollRef.current.scrollLeft);
  };

  const leftPadding = 90;
  const rightPadding = 80;
  const topPadding = 60;
  const bottomPadding = 60;
  const pixelsPerSecond = 17;

  const getTimeBasedPositions = () => {
    if (topics.length === 0) return { chartWidth: 0, startTime: 0, timeMarks: [] };
    const startTime = topics[0].timestamp.getTime();
    const endTime = topics[topics.length - 1].timestamp.getTime();
    const durationMs = endTime - startTime;
    const durationSeconds = Math.ceil(durationMs / 1000);
    const totalSeconds = Math.max(durationSeconds + 10, 30);
    const chartWidth = totalSeconds * pixelsPerSecond;
    const timeMarks: { time: Date; x: number; label: string }[] = [];
    for (let sec = 0; sec <= totalSeconds; sec += 5) {
      const markTime = new Date(startTime + sec * 1000);
      const x = leftPadding + sec * pixelsPerSecond;
      timeMarks.push({
        time: markTime,
        x,
        label: markTime.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
      });
    }
    return { chartWidth, startTime, timeMarks };
  };

  const { chartWidth, startTime, timeMarks } = getTimeBasedPositions();
  const getTopicX = (topic: EmotionTopicNode) => {
    const elapsedSeconds = (topic.timestamp.getTime() - startTime) / 1000;
    return leftPadding + elapsedSeconds * pixelsPerSecond;
  };

  /** Snap x to nearest vertical grid line so emotion labels align with grid. */
  const getLabelX = (topicX: number) => {
    if (timeMarks.length === 0) return topicX;
    let nearest = timeMarks[0];
    let minDist = Math.abs(timeMarks[0].x - topicX);
    for (const mark of timeMarks) {
      const d = Math.abs(mark.x - topicX);
      if (d < minDist) {
        minDist = d;
        nearest = mark;
      }
    }
    return nearest.x;
  };

  const getDataPoints = () => {
    if (topics.length === 0) return { valence: [] as [number, number][], arousal: [] as [number, number][], dominance: [] as [number, number][], xPositions: [] as number[] };
    const valencePoints: [number, number][] = [];
    const arousalPoints: [number, number][] = [];
    const dominancePoints: [number, number][] = [];
    const xPositions: number[] = [];
    const chartArea = chartHeight - topPadding - bottomPadding;
    topics.forEach((topic) => {
      const x = getTopicX(topic);
      const snappedX = getLabelX(x);
      const metrics = calculateEmotionMetrics(topic);
      xPositions.push(snappedX);
      valencePoints.push([snappedX, topPadding + (1 - metrics.valence) * chartArea]);
      arousalPoints.push([snappedX, topPadding + (1 - metrics.arousal) * chartArea]);
      dominancePoints.push([snappedX, topPadding + (1 - metrics.dominance) * chartArea]);
    });
    return { valence: valencePoints, arousal: arousalPoints, dominance: dominancePoints, xPositions };
  };

  const createPath = (points: [number, number][]) => {
    if (points.length === 0) return '';
    let path = `M ${points[0][0]} ${points[0][1]}`;
    for (let i = 1; i < points.length; i++) path += ` L ${points[i][0]} ${points[i][1]}`;
    return path;
  };

  const dataPoints = getDataPoints();
  const totalWidth = leftPadding + chartWidth + rightPadding;

  return (
    <div className="emotion-analysis-card">
      {!hideTitle && (
        <div className="emotion-analysis-header">
          <h2 className="emotion-analysis-title">EMOTION ANALYSIS</h2>
        </div>
      )}
      <div ref={bodyRef} className="emotion-analysis-body">
        {topics.length === 0 ? (
          <div className="emotion-analysis-empty">
            <p>Emotion data will appear here as you speak</p>
          </div>
        ) : (
          <>
            <div ref={scrollRef} className="emotion-analysis-scroll" onScroll={handleScrollInternal}>
              <div ref={containerRef} className="emotion-analysis-chart-inner" style={{ height: `${chartHeight}px`, width: `${totalWidth}px` }}>
                <svg ref={svgRef} width={totalWidth} height={chartHeight}>
                  <g opacity={1}>
                    {[0, 0.2, 0.4, 0.6, 0.8, 1.0].map((value) => {
                      const y = topPadding + (1 - value) * (chartHeight - topPadding - bottomPadding);
                      return (
                        <line key={`grid-h-${value}`} x1={leftPadding} x2={leftPadding + chartWidth} y1={y} y2={y}
                          stroke="var(--emotion-grid-line-color)" strokeWidth={1} strokeDasharray="2,3"  opacity={1}/>
                      );
                    })}
                  </g>
                  {timeMarks.map((mark, index) => (
                    <line key={`grid-v-${index}`} x1={mark.x} y1={topPadding} x2={mark.x} y2={chartHeight - bottomPadding}
                      stroke="var(--emotion-grid-line-color-vertical, var(--emotion-grid-line-color))" strokeWidth={1} strokeDasharray="2,3" opacity={1} />
                  ))}
                  <motion.path d={createPath(dataPoints.arousal)} stroke="#f97316" strokeWidth={2} fill="none"
                    initial={{ pathLength: 0, opacity: 0 }} animate={{ pathLength: 1, opacity: 1 }}
                    transition={{ duration: 1.5, ease: 'easeInOut' }} />
                  <motion.path d={createPath(dataPoints.valence)} stroke="#06b6d4" strokeWidth={2} fill="none"
                    initial={{ pathLength: 0, opacity: 0 }} animate={{ pathLength: 1, opacity: 1 }}
                    transition={{ duration: 1.5, ease: 'easeInOut', delay: 0.2 }} />
                  <motion.path d={createPath(dataPoints.dominance)} stroke="#a855f7" strokeWidth={2} fill="none"
                    initial={{ pathLength: 0, opacity: 0 }} animate={{ pathLength: 1, opacity: 1 }}
                    transition={{ duration: 1.5, ease: 'easeInOut', delay: 0.4 }} />
                  {topics.map((topic, index) => {
                    const emoji = sentimentToEmoji[topic.sentimentLabel] || '😐';
                    const labelX = getLabelX(dataPoints.xPositions[index]);
                    return (
                      <g key={`emoji-group-${topic.id}`}>
                        <motion.text x={labelX} y={topPadding - 35} textAnchor="middle" fontSize={SENTIMENT_LABEL_FONT_SIZE} fill="#7D7D7D"
                          initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: index * 0.1 + 0.5, duration: 0.4 }}>
                          {topic.sentimentLabel}
                        </motion.text>
                        <motion.text x={labelX} y={topPadding - 15} textAnchor="middle" fontSize={SENTIMENT_EMOJI_FONT_SIZE} fill="#7D7D7D"
                          initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: index * 0.1 + 0.6, duration: 0.4 }}>
                          {emoji}
                        </motion.text>
                      </g>
                    );
                  })}
                </svg>
              </div>
            </div>
            <div className="emotion-analysis-sticky-y" style={{ width: `${leftPadding}px` }}>
              <svg width={leftPadding} height="100%">
                <g>
                  {[1.0, 0.8, 0.6, 0.4, 0.2, 0.0].map((value) => {
                    const y = topPadding + (1 - value) * (chartHeight - topPadding - bottomPadding);
                    return (
                      <text key={`y-label-${value}`} x={leftPadding - 15} y={y} textAnchor="end" dominantBaseline="middle"
                        fontSize={Y_AXIS_LABEL_FONT_SIZE} fill="#7D7D7D" style={{ fontFamily: 'monospace' }}>{value.toFixed(2)}</text>
                    );
                  })}
                </g>
              </svg>
            </div>
            <div className="emotion-analysis-sticky-x">
              <svg width="100%" height="56" viewBox={`${scrollLeft} 0 ${scrollRef.current?.clientWidth || 800} 56`} preserveAspectRatio="xMinYMin slice">
                <line x1={leftPadding} y1={0} x2={leftPadding + chartWidth} y2={0} stroke="var(--emotion-grid-line-color-vertical, var(--emotion-grid-line-color))" strokeWidth={1} />
                {timeMarks.map((mark, index) => (
                  <text key={`time-${index}`} x={mark.x} y={20} textAnchor="middle" style={{ fontFamily: 'monospace', fontSize: 'var(--emotion-x-axis-label-font-size)' }} fill="var(--emotion-x-axis-label-color)">
                    {mark.label}
                  </text>
                ))}
              </svg>
            </div>
          </>
        )}
      </div>
      <div className="emotion-analysis-legend">
        <div className="emotion-analysis-legend-item">
          <div className="emotion-analysis-legend-dot cyan" />
          <span className="emotion-analysis-legend-text">Valence</span>
        </div>
        <div className="emotion-analysis-legend-item">
          <div className="emotion-analysis-legend-dot orange" />
          <span className="emotion-analysis-legend-text">Arousal</span>
        </div>
        <div className="emotion-analysis-legend-item">
          <div className="emotion-analysis-legend-dot purple" />
          <span className="emotion-analysis-legend-text">Dominance</span>
        </div>
      </div>
    </div>
  );
}

export default EmotionAnalysis;
