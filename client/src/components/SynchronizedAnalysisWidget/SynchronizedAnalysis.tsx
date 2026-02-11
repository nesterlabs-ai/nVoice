import { useRef, useEffect } from 'react';
import { TopicFlowGraph } from './TopicFlowGraph';
import { EmotionAnalysis } from './EmotionAnalysis';
import { TopicNode } from './topicExtraction';

interface SynchronizedAnalysisProps {
  topics: TopicNode[];
}

export function SynchronizedAnalysis({ topics }: SynchronizedAnalysisProps) {
  const conversationScrollRef = useRef<HTMLDivElement>(null);
  const emotionScrollRef = useRef<HTMLDivElement>(null);
  const isSyncingRef = useRef(false);

  const handleConversationScroll = () => {
    if (isSyncingRef.current || !conversationScrollRef.current || !emotionScrollRef.current) return;
    isSyncingRef.current = true;
    emotionScrollRef.current.scrollLeft = conversationScrollRef.current.scrollLeft;
    requestAnimationFrame(() => { isSyncingRef.current = false; });
  };

  const handleEmotionScroll = () => {
    if (isSyncingRef.current || !conversationScrollRef.current || !emotionScrollRef.current) return;
    isSyncingRef.current = true;
    conversationScrollRef.current.scrollLeft = emotionScrollRef.current.scrollLeft;
    requestAnimationFrame(() => { isSyncingRef.current = false; });
  };

  useEffect(() => {
    if (topics.length > 0 && conversationScrollRef.current && emotionScrollRef.current) {
      const scrollLeft = Math.max(0, conversationScrollRef.current.scrollWidth - conversationScrollRef.current.clientWidth);
      conversationScrollRef.current.scrollTo({ left: scrollLeft, behavior: 'smooth' });
      emotionScrollRef.current.scrollTo({ left: scrollLeft, behavior: 'smooth' });
    }
  }, [topics.length]);

  return (
    <div className="sync-analysis">
      <TopicFlowGraph topics={topics} scrollRef={conversationScrollRef} onScroll={handleConversationScroll} />
      <EmotionAnalysis topics={topics} scrollRef={emotionScrollRef} onScroll={handleEmotionScroll} />
    </div>
  );
}
