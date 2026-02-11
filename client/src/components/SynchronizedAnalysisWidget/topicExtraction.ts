/**
 * Topic extraction from conversation messages.
 * Adapted from Voice Chat UI with Topic Flow.
 */

export interface Message {
  id: string;
  text: string;
  timestamp: Date;
  isFinal: boolean;
  speaker?: 'user' | 'ai';
}

export interface Topic {
  id: string;
  name: string;
  timestamp: Date;
  keywords: string[];
  parentId?: string;
  color: string;
  category: string;
  sentiment: 'positive' | 'neutral' | 'negative';
  sentimentLabel: string;
  intensity: number;
  speaker?: 'user' | 'ai';
  aiRole?: string;
}

function detectAIRole(text: string): string {
  const lowerText = text.toLowerCase();
  if (lowerText.match(/\?$/)) {
    if (lowerText.match(/^(what|which|where|when|who|why|how)/)) return 'asking';
    if (lowerText.match(/have you (considered|thought|tried)/)) return 'suggesting';
    return 'clarifying';
  }
  if (lowerText.match(/^(absolutely|definitely|exactly|right|true|yes|agreed|perfect|great|good|smart|excellent)/)) {
    return 'agreeing';
  }
  if (lowerText.match(/(but |back to|speaking of|let's|now )/)) return 'redirecting';
  if (lowerText.match(/(you (could|should|might)|have you considered|maybe|perhaps|try)/)) return 'suggesting';
  if (lowerText.match(/(because|that's|the reason|it |this )/)) return 'explaining';
  return 'responding';
}

const categoryKeywords: { [key: string]: string[] } = {
  'Design': ['design', 'ui', 'ux', 'interface', 'visual', 'layout', 'color', 'typography', 'component', 'user', 'prototype', 'wireframe', 'mockup', 'figma', 'sketch', 'style', 'aesthetic', 'branding', 'identity', 'spacing', 'grid', 'navigation', 'accessibility', 'usability', 'interaction', 'animation', 'micro', 'button', 'input', 'form', 'responsive', 'mobile', 'desktop', 'tablet', 'screen', 'device', 'pixel'],
  'Technology': ['tech', 'technology', 'computer', 'software', 'app', 'application', 'code', 'coding', 'program', 'programming', 'digital', 'internet', 'web', 'website', 'online', 'ai', 'artificial', 'intelligence', 'machine', 'learning', 'algorithm', 'data', 'database', 'server', 'cloud', 'api', 'development', 'developer', 'engineering', 'platform', 'system', 'framework', 'library', 'package', 'npm', 'github', 'react', 'javascript', 'typescript', 'python', 'java'],
  'Food': ['food', 'eat', 'eating', 'restaurant', 'cook', 'cooking', 'recipe', 'dinner', 'lunch', 'breakfast', 'meal', 'taste', 'delicious', 'cuisine', 'dish', 'ingredient', 'kitchen', 'chef', 'menu', 'order', 'spice', 'flavor', 'hungry', 'appetite', 'paella', 'pasta', 'pizza', 'tapas', 'rice', 'chicken', 'seafood', 'vegetable', 'fruit'],
  'Travel': ['travel', 'traveling', 'trip', 'vacation', 'holiday', 'journey', 'flight', 'fly', 'flying', 'airline', 'airport', 'hotel', 'accommodation', 'destination', 'tour', 'tourist', 'visit', 'visiting', 'country', 'city', 'europe', 'italy', 'france', 'spain', 'japan', 'tokyo', 'paris', 'barcelona', 'rome', 'passport', 'visa', 'luggage', 'pack', 'packing', 'backpack', 'suitcase', 'ticket', 'booking', 'reservation', 'airbnb', 'hostel'],
  'Finance': ['money', 'finance', 'financial', 'bank', 'banking', 'account', 'credit', 'card', 'debit', 'payment', 'pay', 'paying', 'cost', 'price', 'expensive', 'cheap', 'budget', 'budgeting', 'save', 'saving', 'spend', 'spending', 'invest', 'investment', 'stock', 'market', 'trading', 'currency', 'dollar', 'euro', 'pound', 'rewards', 'points', 'cash', 'balance', 'mortgage', 'loan', 'debt', 'insurance'],
  'Business': ['business', 'company', 'corporate', 'enterprise', 'startup', 'entrepreneur', 'market', 'marketing', 'sales', 'selling', 'revenue', 'profit', 'customer', 'client', 'product', 'service', 'meeting', 'project', 'deadline', 'team', 'management', 'manager', 'director', 'ceo', 'founder', 'strategy', 'plan', 'planning', 'office', 'work', 'working', 'job', 'career', 'professional', 'studio', 'agency', 'freelance', 'contract', 'proposal'],
  'Health': ['health', 'healthy', 'fitness', 'fit', 'exercise', 'exercising', 'workout', 'gym', 'training', 'doctor', 'medical', 'hospital', 'clinic', 'medicine', 'medication', 'wellness', 'wellbeing', 'run', 'running', 'jog', 'jogging', 'walk', 'walking', 'yoga', 'stretch', 'stretching', 'strength', 'cardio', 'weight', 'muscle', 'diet', 'nutrition', 'vitamin', 'sleep', 'rest', 'tired', 'energy', 'stress', 'anxiety', 'mental'],
  'Education': ['school', 'university', 'college', 'education', 'educational', 'study', 'studying', 'learn', 'learning', 'teach', 'teaching', 'teacher', 'professor', 'student', 'class', 'classroom', 'course', 'lesson', 'lecture', 'degree', 'diploma', 'certificate', 'exam', 'test', 'homework', 'assignment', 'research', 'academic', 'semester', 'graduate', 'undergraduate', 'major', 'minor', 'skill', 'training', 'workshop', 'conference', 'seminar'],
  'Entertainment': ['movie', 'film', 'cinema', 'show', 'series', 'episode', 'watch', 'watching', 'viewing', 'actor', 'actress', 'director', 'netflix', 'hulu', 'disney', 'streaming', 'stream', 'tv', 'television', 'entertainment', 'video', 'youtube', 'channel', 'podcast', 'music', 'song', 'album', 'artist', 'concert', 'performance', 'game', 'gaming', 'play', 'playing', 'player', 'fun', 'hobby'],
  'Art': ['art', 'artwork', 'artist', 'painting', 'drawing', 'sculpture', 'gallery', 'museum', 'exhibition', 'louvre', 'renaissance', 'modern', 'contemporary', 'creative', 'creativity', 'aesthetic', 'culture', 'cultural', 'history', 'historical', 'vinci', 'picasso', 'monet', 'masterpiece', 'canvas', 'sketch', 'illustration'],
  'Language': ['language', 'speak', 'speaking', 'talk', 'talking', 'conversation', 'communicate', 'communication', 'english', 'spanish', 'french', 'italian', 'japanese', 'chinese', 'german', 'portuguese', 'word', 'vocabulary', 'grammar', 'pronunciation', 'accent', 'fluent', 'fluency', 'practice', 'practicing', 'duolingo', 'translate', 'translation'],
  'Housing': ['house', 'home', 'apartment', 'condo', 'property', 'real', 'estate', 'housing', 'rent', 'rental', 'lease', 'buy', 'buying', 'purchase', 'mortgage', 'loan', 'market', 'price', 'expensive', 'affordable', 'neighborhood', 'area', 'location', 'move', 'moving', 'relocate'],
  'Outdoor': ['outdoor', 'outside', 'nature', 'hiking', 'hike', 'trail', 'mountain', 'hill', 'peak', 'valley', 'forest', 'woods', 'wilderness', 'camping', 'camp', 'adventure', 'explore', 'exploring', 'alps', 'swiss', 'switzerland', 'scenery', 'landscape', 'view', 'beautiful', 'gear', 'equipment', 'backpack', 'rei'],
  'Communication': ['read', 'reading', 'book', 'novel', 'story', 'chapter', 'page', 'author', 'write', 'writing', 'written', 'text', 'message', 'email', 'phone', 'call', 'calling', 'chat', 'social', 'media', 'facebook', 'twitter', 'instagram', 'linkedin', 'post', 'share', 'sharing', 'comment', 'like', 'follow'],
  'Transport': ['transport', 'transportation', 'train', 'railway', 'railroad', 'subway', 'metro', 'bus', 'car', 'vehicle', 'drive', 'driving', 'ride', 'commute', 'commuting', 'route', 'road', 'highway', 'traffic', 'uber', 'lyft', 'taxi', 'ryanair', 'easyjet', 'eurail'],
};

function getSubTopic(text: string, category: string): string | null {
  const lowerText = text.toLowerCase();
  if (category === 'Design') {
    if (lowerText.match(/color|palette|blue|red|green|purple|orange|pink|yellow/)) return 'Color & Branding';
    if (lowerText.match(/typography|font|text|readable|letter|heading/)) return 'Typography';
    if (lowerText.match(/layout|grid|spacing|margin|padding|align|position/)) return 'Layout & Spacing';
    if (lowerText.match(/navigation|menu|tab|button|link|route|navigate/)) return 'Navigation';
    if (lowerText.match(/component|library|reusable|system|token|pattern/)) return 'Component Library';
    if (lowerText.match(/accessibility|wcag|contrast|screen reader|inclusive/)) return 'Accessibility';
    if (lowerText.match(/responsive|mobile|tablet|desktop|breakpoint|device/)) return 'Responsive Design';
    if (lowerText.match(/dark mode|theme|light|appearance/)) return 'Dark Mode';
    if (lowerText.match(/animation|transition|micro|interaction|motion/)) return 'Animation & Interaction';
    return 'Design Discussion';
  }
  if (category === 'Business') {
    if (lowerText.match(/studio|agency|company|firm|start/)) return 'UX Studio';
    if (lowerText.match(/service|offering|provide|deliver|solution/)) return 'Services';
    if (lowerText.match(/client|customer|enterprise|startup|target market/)) return 'Target Market';
    return 'Business Discussion';
  }
  if (category === 'Travel') {
    if (lowerText.match(/flight|airline|plane|airport|fly|ryanair|easyjet/)) return 'Flights';
    if (lowerText.match(/hotel|airbnb|accommodation|stay|rental|apartment/)) return 'Accommodation';
    return 'Travel Planning';
  }
  if (category === 'Technology') {
    if (lowerText.match(/app|application|mobile/)) return 'Mobile Apps';
    if (lowerText.match(/web|website|online/)) return 'Web Development';
    if (lowerText.match(/ai|artificial intelligence|machine learning/)) return 'AI & ML';
    return 'Technology';
  }
  return null;
}

function analyzeSentiment(text: string): { sentiment: 'positive' | 'neutral' | 'negative'; label: string; intensity: number } {
  const lowerText = text.toLowerCase();
  const positiveKeywords = ['love', 'great', 'awesome', 'amazing', 'excellent', 'perfect', 'beautiful', 'wonderful', 'excited', 'happy', 'enjoy', 'fantastic', 'brilliant', 'good', 'nice', 'best', 'incredible', 'outstanding', 'delightful', 'thrilled', 'impressed', 'favorite', 'glad'];
  const negativeKeywords = ['hate', 'bad', 'terrible', 'awful', 'horrible', 'worst', 'poor', 'difficult', 'problem', 'issue', 'frustrat', 'annoying', 'disappointing', 'sad', 'worry', 'concern', 'stress', 'hard', 'struggle', 'tough', 'unfortunate'];
  const excitementKeywords = ['exciting', 'can\'t wait', 'looking forward', 'eager', 'pumped', 'psyched', 'thrilled', 'amazing', 'incredible'];
  const calmKeywords = ['okay', 'fine', 'alright', 'sure', 'consider', 'think', 'maybe', 'probably', 'planning', 'deciding'];
  const positiveCount = positiveKeywords.filter(k => lowerText.includes(k)).length;
  const negativeCount = negativeKeywords.filter(k => lowerText.includes(k)).length;
  const excitementCount = excitementKeywords.filter(k => lowerText.includes(k)).length;
  const calmCount = calmKeywords.filter(k => lowerText.includes(k)).length;
  if (excitementCount > 0) return { sentiment: 'positive', label: 'Excited', intensity: 0.8 + Math.min(excitementCount * 0.1, 0.2) };
  if (positiveCount > negativeCount && positiveCount > 0) return { sentiment: 'positive', label: 'Positive', intensity: 0.6 + Math.min(positiveCount * 0.1, 0.3) };
  if (negativeCount > positiveCount && negativeCount > 0) return { sentiment: 'negative', label: 'Concerned', intensity: 0.5 + Math.min(negativeCount * 0.1, 0.3) };
  if (calmCount > 0) return { sentiment: 'neutral', label: 'Calm', intensity: 0.3 + Math.min(calmCount * 0.05, 0.2) };
  return { sentiment: 'neutral', label: 'Neutral', intensity: 0.5 };
}

function generateTopicName(_keywords: string[], text: string, category: string, subTopic?: string): string {
  if (subTopic) return subTopic;
  const lowerText = text.toLowerCase();
  if (category === 'Design') return lowerText.match(/color|palette|blue|brand/) ? 'Color & Branding' : 'Design Discussion';
  if (category === 'Business') return lowerText.match(/studio|agency|company/) ? 'Company Overview' : 'Business Discussion';
  if (category === 'Travel') return lowerText.match(/flight|airline|airport/) ? 'Flights' : 'Travel Planning';
  if (category === 'Technology') return lowerText.match(/ai|artificial intelligence/) ? 'AI & ML' : 'Technology';
  return category;
}

export function extractTopicsFromMessages(messages: Message[]): Topic[] {
  if (messages.length === 0) return [];
  const topics: Topic[] = [];
  const colors = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#14b8a6', '#f97316'];
  let currentCategory: string | null = null;
  let currentTopic: string | null = null;
  let colorIndex = 0;

  messages.forEach((message, index) => {
    if (message.speaker !== 'user') return;
    const text = message.text.toLowerCase();
    let detectedCategory: string | null = null;
    let maxMatches = 0;
    for (const [category, keywords] of Object.entries(categoryKeywords)) {
      const matches = keywords.filter(keyword => text.includes(keyword)).length;
      if (matches > maxMatches) {
        maxMatches = matches;
        detectedCategory = category;
      }
    }
    if (detectedCategory && maxMatches > 0) {
      const subTopic = getSubTopic(text, detectedCategory);
      const topicName = generateTopicName([], message.text, detectedCategory, subTopic ?? undefined);
      if (currentTopic !== topicName) {
        const matchedKeywords = categoryKeywords[detectedCategory].filter(k => text.includes(k));
        const sentimentData = analyzeSentiment(message.text);
        let aiRole: string | undefined;
        if (index > 0 && messages[index - 1].speaker === 'ai') {
          aiRole = detectAIRole(messages[index - 1].text);
        }
        topics.push({
          id: `topic-${topics.length}`,
          name: topicName,
          timestamp: message.timestamp,
          keywords: matchedKeywords.slice(0, 5),
          parentId: topics.length > 0 ? topics[topics.length - 1].id : undefined,
          color: colors[colorIndex % colors.length],
          category: detectedCategory,
          sentiment: sentimentData.sentiment,
          sentimentLabel: sentimentData.label,
          intensity: sentimentData.intensity,
          speaker: message.speaker,
          aiRole,
        });
        if (currentCategory !== detectedCategory) {
          currentCategory = detectedCategory;
          colorIndex++;
        }
        currentTopic = topicName;
      }
    }
  });
  return topics;
}

export interface TopicNode extends Topic {
  x: number;
  y: number;
  row: number;
}

export function layoutTopics(topics: Topic[]): TopicNode[] {
  if (topics.length === 0) return [];
  const nodes: TopicNode[] = [];
  const rowAssignments: { [category: string]: number } = {};
  let currentRow = 0;
  topics.forEach((topic, index) => {
    if (rowAssignments[topic.category] === undefined) {
      rowAssignments[topic.category] = currentRow;
      currentRow++;
    }
    const row = rowAssignments[topic.category];
    nodes.push({
      ...topic,
      x: index * 150 + 120,
      y: row * 35 + 100,
      row,
    });
  });
  return nodes;
}
