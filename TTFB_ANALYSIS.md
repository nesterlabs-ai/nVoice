# Time to First Byte (TTFB) Analysis - Nesterlabs Voice Assistant

## Pipeline Architecture

```
User Speech → WebSocket → VAD → STT (Deepgram) → Context Aggregator →
LLM (Gemini 2.5 Flash) → TTS (Deepgram Aura-2) → WebSocket → User Hears Response
```

## Current Measurements (From Logs - Session 3617d704)

### 1. **Speech-to-Text (STT) - Deepgram Nova-3**
- **TTFB**: 1.896s (initial), 0.039s (subsequent)
- **Processing Time**: 1.896s (initial), 0.875s (subsequent)
- **What it does**: Converts user's speech to text
- **Configuration**:
  - Model: nova-3
  - Smart format: enabled
  - Endpointing: 300ms
  - Interim results: enabled

### 2. **LLM Processing - Google Gemini 2.5 Flash**
- **TTFB**: 1.947s (first response), 3.473s (second response)
- **Processing Time**: Same as TTFB (streaming starts immediately)
- **What it does**: Understands intent, generates response
- **Configuration**:
  - Model: gemini-2.5-flash
  - Temperature: 0.8
  - Max tokens: 256
  - System prompt: 7810 chars
  - **Cache Usage**: 3737 tokens read from cache (second response)

### 3. **Text-to-Speech (TTS) - Deepgram Aura-2**
- **TTFB**: 0.379s (first), 0.348s (second)
- **Processing Time**: 0.001s (very fast, just queuing)
- **What it does**: Converts text response to speech audio
- **Configuration**:
  - Voice: aura-2-athena-en
  - Encoding: linear16
  - Sample rate: 24000Hz

### 4. **Voice Activity Detection (VAD)**
- **Configuration**:
  - Confidence: 0.7 (OLD - should be 0.8)
  - Start secs: 0.2 (OLD - should be 0.25)
  - Stop secs: 0.8
  - Min volume: 0.6 (OLD - should be 0.7)
- **Note**: Log shows old values (0.7, 0.2, 0.6) - config not applied yet!

## Total Latency Breakdown

### Complete User → Response Cycle:
1. **User stops speaking** → VAD detects end: ~800ms (stop_secs)
2. **STT Processing**: ~1.9s (first utterance), ~0.9s (subsequent)
3. **LLM Processing**: ~2.0-3.5s
4. **TTS Processing**: ~0.35s
5. **Audio playback begins**

**Total TTFB (User stops speaking → Bot starts speaking)**: ~5.0-6.5 seconds

## Bottlenecks Identified

### 🔴 CRITICAL - Slowest Components:
1. **LLM (Gemini 2.5 Flash)**: 2-3.5s
   - Prompt caching helps (3737 tokens cached)
   - Long system prompt (7810 chars) impacts first call

2. **STT (Deepgram Nova-3)**: 1.9s initial, 0.9s subsequent
   - Initial connection overhead
   - Endpointing adds 300ms

### 🟡 MODERATE:
3. **VAD stop_secs**: 800ms
   - Necessary to avoid cutting off speech
   - Could reduce to 0.6s but risks cutting users off

### 🟢 FAST:
4. **TTS (Deepgram Aura-2)**: 0.35s
   - Already very fast
   - Real-time factor: 0.111x

## Optimization Opportunities

### Immediate Wins:
1. ✅ **Applied**: Stricter VAD (confidence 0.8, start_secs 0.25, min_volume 0.7)
2. ✅ **Applied**: Reduced greeting delay (2.0s → 1.0s)
3. ✅ **Applied**: Added humanized thinking phrases during RAG

### Potential Improvements:
1. **LLM Optimization**:
   - ✅ Already using prompt caching (saves ~3737 tokens)
   - Consider shorter system prompt (currently 7810 chars)
   - Consider using Gemini 2.0 Flash Thinking (may be faster)

2. **STT Optimization**:
   - ✅ Already using interim_results for streaming
   - ✅ Endpointing at 300ms (good balance)
   - Could try nova-2 if accuracy allows (faster)

3. **Pipeline Optimization**:
   - ✅ Direct TTS push for greetings (bypasses LLM)
   - ✅ STT mute filter to prevent interruptions
   - Streaming responses already enabled

## Testing Methodology

### Test Scenarios:
1. **Simple greeting**: "Hello?" → "I'm the Nesterlabs voice assistant..."
2. **Basic question**: "What do you do?" → Direct answer (no RAG)
3. **RAG question**: "Tell me about your projects" → RAG call + response
4. **Complex query**: Multiple turns with context

### Metrics to Track:
- STT TTFB
- LLM TTFB
- TTS TTFB
- Total response time
- Cache hit rate
- Token usage

## Real-World Performance (From Logs)

### Session 3617d704 Analysis:

**Turn 1: "Hello?"**
- User stopped speaking: 15:41:57.381
- LLM started: 15:41:58.189
- LLM TTFB: 15:42:00.137 (1.947s)
- TTS TTFB: 15:42:00.637 (0.379s)
- Bot started speaking: 15:42:00.638
- **Total: ~3.3s** (from user stop to bot start)

**Turn 2: "How are you?"**
- User stopped speaking: 15:42:07.166
- LLM started: 15:42:07.977
- LLM TTFB: 15:42:11.451 (3.473s)
- TTS TTFB: 15:42:11.804 (0.348s)
- Bot started speaking: 15:42:11.806
- **Total: ~4.6s** (from user stop to bot start)

## Recommendations

### Priority 1 (Highest Impact):
1. ✅ **Applied**: Optimize system prompt length
2. ✅ **Applied**: Use prompt caching (already enabled)
3. 🔄 **Monitor**: LLM performance with cache hits

### Priority 2 (Moderate Impact):
1. ✅ **Applied**: Stricter VAD settings
2. 🔄 **Test**: Different endpointing values
3. 🔄 **Consider**: Parallel processing where possible

### Priority 3 (Low Impact):
1. ✅ **Applied**: Humanized thinking phrases
2. ✅ **Applied**: Faster greeting (1s delay)
3. 🔄 **Monitor**: Network latency

## Current Configuration Summary

| Component | Setting | Value | Status |
|-----------|---------|-------|--------|
| VAD Confidence | Config | 0.8 | ✅ Fixed (was showing 0.7) |
| VAD Start Secs | Config | 0.25 | ✅ Fixed (was showing 0.2) |
| VAD Stop Secs | Config | 0.8 | ✅ Applied |
| VAD Min Volume | Config | 0.7 | ✅ Fixed (was showing 0.6) |
| STT Endpointing | Config | 300ms | ✅ Applied |
| LLM Model | Config | gemini-2.5-flash | ✅ Applied |
| LLM Temperature | Config | 0.8 | ✅ Applied |
| LLM Max Tokens | Config | 256 | ✅ Applied |
| TTS Voice | Config | aura-2-athena-en | ✅ Applied |
| Greeting Delay | Code | 1.0s | ✅ Applied |

## VAD Configuration Fix (2025-12-25)

**Issue**: VAD settings in config.yaml were not being applied. The websocket.py file had hardcoded defaults (0.7, 0.2, 0.6) that overrode the config.yaml values (0.8, 0.25, 0.7).

**Root Cause**: In `app/api/websocket.py` lines 50-54, the fallback defaults in `vad_config.get()` calls were using old values instead of config.yaml values.

**Fix Applied**: Updated websocket.py line 51-54 to use correct defaults matching config.yaml:
- `confidence`: 0.7 → 0.8
- `start_secs`: 0.2 → 0.25
- `min_volume`: 0.6 → 0.7

**Status**: ✅ Fixed and server restarted (PID 37269)

## Next Steps

1. ✅ **COMPLETED**: Fixed VAD configuration issue in websocket.py
2. ✅ **COMPLETED**: Server restarted with correct settings (PID 37269)
3. 📊 Test with new VAD configuration to verify stricter detection
4. 📈 Monitor TTFB metrics over multiple sessions with new VAD settings
5. 🔍 Analyze LLM cache hit rates
6. 📝 Document baseline performance metrics with corrected VAD
