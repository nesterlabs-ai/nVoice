import { useRef, useEffect } from 'react';
import { TopicFlowGraph } from './TopicFlowGraph';
import { TopicNode } from './topicExtraction';

interface SynchronizedAnalysisProps {
  topics: TopicNode[];
}

export function SynchronizedAnalysis({ topics }: SynchronizedAnalysisProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (topics.length > 0 && scrollRef.current) {
      const scrollLeft = Math.max(0, scrollRef.current.scrollWidth - scrollRef.current.clientWidth);
      scrollRef.current.scrollTo({ left: scrollLeft, behavior: 'smooth' });
    }
  }, [topics.length]);

  return (
    <div className="sync-analysis">
      <TopicFlowGraph topics={topics} scrollRef={scrollRef} onScroll={() => {}} />
    </div>
  );
}
