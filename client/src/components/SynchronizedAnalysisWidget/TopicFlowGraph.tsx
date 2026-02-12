import { useEffect, useRef, useState } from 'react';
import { motion } from 'motion/react';
import { TopicNode } from './topicExtraction';

interface TopicFlowGraphProps {
  topics: TopicNode[];
  scrollRef: React.RefObject<HTMLDivElement | null>;
  onScroll: () => void;
}

export function TopicFlowGraph({ topics, scrollRef, onScroll }: TopicFlowGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [scrollTop, setScrollTop] = useState(0);
  const [scrollLeft, setScrollLeft] = useState(0);
  const [isManuallyControlled, setIsManuallyControlled] = useState(false);
  const autoScrollTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleScrollInternal = () => {
    if (scrollRef.current) {
      setScrollTop(scrollRef.current.scrollTop);
      setScrollLeft(scrollRef.current.scrollLeft);
      setIsManuallyControlled(true);
      if (autoScrollTimeoutRef.current) clearTimeout(autoScrollTimeoutRef.current);
    }
    onScroll();
  };

  const handleMouseLeave = () => {
    if (autoScrollTimeoutRef.current) clearTimeout(autoScrollTimeoutRef.current);
    autoScrollTimeoutRef.current = setTimeout(() => setIsManuallyControlled(false), 500);
  };

  useEffect(() => {
    if (!isManuallyControlled && scrollRef.current && topics.length > 0) {
      const lastTopic = topics[topics.length - 1];
      const rowHeight = 80;
      const baseY = 60;
      const lastTopicY = baseY + lastTopic.row * rowHeight;
      const viewportHeight = scrollRef.current.clientHeight;
      const currentScrollTop = scrollRef.current.scrollTop;
      const visibleTop = currentScrollTop;
      const visibleBottom = currentScrollTop + viewportHeight;
      const isAboveViewport = lastTopicY < visibleTop + 60;
      const isBelowViewport = lastTopicY > visibleBottom - 60;
      let targetScrollTop = currentScrollTop;
      if (isAboveViewport || isBelowViewport) targetScrollTop = lastTopicY - (viewportHeight / 2);
      const scrollLeftTarget = Math.max(0, scrollRef.current.scrollWidth - scrollRef.current.clientWidth);
      scrollRef.current.scrollTo({
        left: scrollLeftTarget,
        top: Math.max(0, targetScrollTop),
        behavior: 'smooth'
      });
    }
  }, [topics, scrollRef, isManuallyControlled]);

  useEffect(() => () => {
    if (autoScrollTimeoutRef.current) clearTimeout(autoScrollTimeoutRef.current);
  }, []);

  const getRowInfo = () => {
    const rowCategories: { [row: number]: string } = {};
    topics.forEach(topic => {
      if (rowCategories[topic.row] === undefined) rowCategories[topic.row] = topic.category;
    });
    return { rowCategories };
  };

  const { rowCategories } = getRowInfo();
  const rows = Object.keys(rowCategories).map(Number).sort((a, b) => a - b);
  const rowHeight = 36;
  const baseY = 60;
  const timelineMargin = 60;
  const totalHeight = rows.length * rowHeight + baseY + timelineMargin;
  const leftPadding = 90;
  const rightPadding = 80;
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
  const getTopicX = (topic: TopicNode) => {
    const elapsedSeconds = (topic.timestamp.getTime() - startTime) / 1000;
    return leftPadding + elapsedSeconds * pixelsPerSecond;
  };
  const totalWidth = leftPadding + chartWidth + rightPadding;

  return (
    <div className="sync-card">
      <div className="sync-card-body">
        {topics.length === 0 ? (
          <div className="sync-empty-state">
            <p>Topics will appear here as you speak</p>
          </div>
        ) : (
          <>
            <div
              ref={scrollRef}
              className="sync-scroll-area-both"
              onScroll={handleScrollInternal}
              onMouseLeave={handleMouseLeave}
            >
              <div ref={containerRef} className="sync-chart-inner" style={{ height: `${totalHeight}px`, width: `${totalWidth}px` }}>
                <svg width={totalWidth} height={totalHeight}>
                  {rows.map((rowNum) => {
                    const y = baseY + rowNum * rowHeight;
                    return (
                      <rect
                        key={`row-${rowNum}`}
                        x={leftPadding}
                        y={y - 40}
                        width={chartWidth}
                        height={rowHeight}
                        fill="transparent"
                        stroke="var(--sync-grid-line-color)"
                        strokeOpacity={1}
                        strokeWidth={1}
                        // rx={4}
                      />
                    );
                  })}
                  {timeMarks.map((mark, index) => (
                    <line
                      key={`grid-v-${index}`}
                      x1={mark.x}
                      y1={baseY - 40}
                      x2={mark.x}
                      y2={rows.length * rowHeight + baseY + 20}
                      stroke="var(--sync-grid-line-color-vertical, var(--sync-grid-line-color))"
                      strokeWidth={1}
                      strokeDasharray="2,3"
                      opacity={1}
                    />
                  ))}
                  {topics.map((topic, index) => {
                    if (index === 0) return null;
                    const prevTopic = topics[index - 1];
                    const x1 = getTopicX(prevTopic);
                    const x2 = getTopicX(topic);
                    const y1 = baseY + prevTopic.row * rowHeight;
                    const y2 = baseY + topic.row * rowHeight;
                    return (
                      <g key={`connection-${topic.id}`}>
                        <motion.line
                          x1={x1}
                          y1={y1}
                          x2={x2}
                          y2={y2}
                          stroke="#7D7D7D"
                          strokeWidth={1.5}
                          strokeDasharray="4,4"
                          initial={{ pathLength: 0, opacity: 0 }}
                          animate={{ pathLength: 1, opacity: 0.5 }}
                          transition={{ delay: index * 0.1, duration: 0.4 }}
                        />
                        {topic.aiRole && (
                          <motion.g
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            transition={{ delay: index * 0.1 + 0.2, duration: 0.3 }}
                          >
                            <rect x={(x1 + x2) / 2 - 30} y={(y1 + y2) / 2 - 10} width={60} height={20}
                              fill="rgba(17, 24, 39, 0.95)" stroke="#f97316" strokeWidth={1} rx={3} />
                            <text x={(x1 + x2) / 2} y={(y1 + y2) / 2 + 1} fontSize="10" fontWeight="500"
                              fill="#f97316" textAnchor="middle" dominantBaseline="middle">{topic.aiRole}</text>
                          </motion.g>
                        )}
                      </g>
                    );
                  })}
                  {topics.map((topic, index) => {
                    const x = getTopicX(topic);
                    const y = baseY + topic.row * rowHeight;
                    return (
                      <g key={topic.id}>
                        <motion.circle
                          cx={x}
                          cy={y}
                          r={6}
                          fill="#f43f5e"
                          stroke="#1f2937"
                          strokeWidth={2}
                          initial={{ scale: 0 }}
                          animate={{ scale: 1 }}
                          transition={{ delay: index * 0.1 + 0.1, duration: 0.3 }}
                        />
                        <motion.text
                          x={x}
                          y={y - 15}
                          fontSize="12"
                          fontWeight="500"
                          fill="white"
                          textAnchor="middle"
                          initial={{ opacity: 0, y: -5 }}
                          animate={{ opacity: 1, y: 0 }}
                          transition={{ delay: index * 0.1 + 0.2, duration: 0.4 }}
                        >
                          {topic.name}
                        </motion.text>
                      </g>
                    );
                  })}
                </svg>
              </div>
            </div>
            <div className="sync-sticky-y" style={{ width: `${leftPadding}px` }}>
              <svg width={leftPadding} height="100%" viewBox={`0 ${scrollTop} ${leftPadding} ${scrollRef.current?.clientHeight || 300}`} preserveAspectRatio="xMinYMin slice">
                {rows.map((rowNum) => {
                  const y = baseY + rowNum * rowHeight;
                  return (
                    <text key={`y-label-${rowNum}`} x={leftPadding - 10} y={y} fontSize="9" fill="#7D7D7D"
                      textAnchor="end" dominantBaseline="middle" style={{ fontFamily: 'monospace' }}>
                      {rowCategories[rowNum]}
                    </text>
                  );
                })}
              </svg>
            </div>
            <div className="sync-sticky-x">
              <svg width="100%" height="56" viewBox={`${scrollLeft} 0 ${scrollRef.current?.clientWidth || 800} 56`} preserveAspectRatio="xMinYMin slice">
                <line x1={leftPadding} y1={0} x2={leftPadding + chartWidth} y2={0} stroke="var(--sync-grid-line-color-vertical, var(--sync-grid-line-color))" strokeWidth={1} />
                {timeMarks.map((mark, index) => (
                  <text key={`time-${index}`} x={mark.x} y={20} textAnchor="middle" style={{ fontFamily: 'monospace', fontSize: 'var(--sync-x-axis-label-font-size)' }} fill="var(--sync-x-axis-label-color)">
                    {mark.label}
                  </text>
                ))}
              </svg>
            </div>
          </>
        )}
      </div>
      <div className="sync-legend">
        <div className="sync-legend-item">
          <div className="sync-legend-dot rose" />
          <span className="sync-legend-text">User topics</span>
        </div>
        <div className="sync-legend-item">
          <div className="sync-legend-dot orange" />
          <span className="sync-legend-text">AI interactions</span>
        </div>
      </div>
    </div>
  );
}
