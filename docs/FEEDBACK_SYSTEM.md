# NesterVoiceAI Feedback System

## Overview

The feedback system collects user feedback when they end a voice conversation. Instead of immediately closing the session when a user says "goodbye", the system displays a visual feedback form, collects responses, speaks back the user's selections, and then closes gracefully.

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           FEEDBACK SYSTEM FLOW                               │
└─────────────────────────────────────────────────────────────────────────────┘

     USER                    BACKEND                         FRONTEND
       │                        │                               │
       │  "Goodbye"             │                               │
       ├───────────────────────►│                               │
       │                        │                               │
       │                   ┌────┴────┐                          │
       │                   │ Deepgram │                         │
       │                   │   STT    │                         │
       │                   └────┬────┘                          │
       │                        │                               │
       │                   ┌────┴────┐                          │
       │                   │  Groq   │                          │
       │                   │   LLM   │                          │
       │                   └────┬────┘                          │
       │                        │                               │
       │                        │ calls end_conversation()      │
       │                        ▼                               │
       │              ┌─────────────────────┐                   │
       │              │ ConversationManager │                   │
       │              │ _handle_end_convo() │                   │
       │              └─────────┬───────────┘                   │
       │                        │                               │
       │                        │ 1. TTS: "Before you go..."    │
       │◄───────────────────────┤                               │
       │                        │                               │
       │                        │ 2. Emit feedback_request      │
       │                        ├──────────────────────────────►│
       │                        │                               │
       │                        │                    ┌──────────┴──────────┐
       │                        │                    │  FeedbackRenderer   │
       │                        │                    │  renders form       │
       │                        │                    └──────────┬──────────┘
       │                        │                               │
       │                        │           ┌───────────────────┴───────────────────┐
       │                        │           │                                       │
       │                        │           │  ┌─────────────────────────────────┐  │
       │                        │           │  │      Quick Feedback             │  │
       │                        │           │  │                                 │  │
       │                        │           │  │  1. Overall Experience?         │  │
       │                        │           │  │     [Excellent] [Good] [Okay]   │  │
       │                        │           │  │                                 │  │
       │                        │           │  │  2. Information Helpful?        │  │
       │                        │           │  │     [Very] [Somewhat] [No]      │  │
       │                        │           │  │                                 │  │
       │                        │           │  │  3. Voice Quality?              │  │
       │                        │           │  │     [Clear] [Mostly] [Hard]     │  │
       │                        │           │  │                                 │  │
       │                        │           │  │  4. Use Again?                  │  │
       │                        │           │  │     [Definitely] [Maybe] [No]   │  │
       │                        │           │  │                                 │  │
       │                        │           │  │  Auto-close in 45 seconds       │  │
       │                        │           │  │                                 │  │
       │                        │           │  │  [Skip]     [Submit Feedback]   │  │
       │                        │           │  └─────────────────────────────────┘  │
       │                        │           │                                       │
       │                        │           └───────────────────┬───────────────────┘
       │                        │                               │
       │                        │                               │ User clicks Submit
       │                        │                               │
       │                        │    POST /feedback/submit      │
       │                        │◄──────────────────────────────┤
       │                        │                               │
       │              ┌─────────┴───────────┐                   │
       │              │   feedback_store    │                   │
       │              │   (in-memory dict)  │                   │
       │              └─────────┬───────────┘                   │
       │                        │                               │
       │                        │ 3. close_session()            │
       │                        │                               │
       │                        │ 4. TTS: "You selected         │
       │                        │    [X] for [Y], [Z] for [W]"  │
       │◄───────────────────────┤                               │
       │                        │                               │
       │                        │ 5. EndFrame                   │
       │                        │    (session closes)           │
       │                        │                               │
       ▼                        ▼                               ▼
```

---

## Component Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              BACKEND (Python)                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────────────┐    ┌──────────────────────────────────────┐   │
│  │  app/config/             │    │  app/services/a2ui/                  │   │
│  │  feedback_questions.py   │    │  feedback_generator.py               │   │
│  │                          │    │                                      │   │
│  │  FEEDBACK_QUESTIONS = [  │───►│  generate_feedback_message()         │   │
│  │    {id, question, opts}  │    │  - Creates A2UI-style payload        │   │
│  │    ...                   │    │  - Includes questions + config       │   │
│  │  ]                       │    │                                      │   │
│  └──────────────────────────┘    └──────────────────┬───────────────────┘   │
│                                                      │                       │
│  ┌───────────────────────────────────────────────────┴───────────────────┐  │
│  │  app/services/conversation.py - ConversationManager                   │  │
│  │                                                                        │  │
│  │  State:                         Methods:                               │  │
│  │  - _waiting_for_feedback       - _handle_end_conversation()           │  │
│  │  - _feedback_callback          - _emit_feedback_ui()                  │  │
│  │  - _feedback_timeout_task      - _feedback_timeout_handler()          │  │
│  │  - _llm_ref                    - close_session()                      │  │
│  │  - _session_id                 - is_waiting_for_feedback()            │  │
│  │                                - _build_feedback_response_message()   │  │
│  └───────────────────────────────────────────────────┬───────────────────┘  │
│                                                      │                       │
│  ┌───────────────────────────────────────────────────┴───────────────────┐  │
│  │  app/core/voice_assistant.py - VoiceAssistant                         │  │
│  │                                                                        │  │
│  │  - _emit_feedback_request()  ──► RTVIServerMessageFrame               │  │
│  │  - Sets up feedback callback                                          │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  app/api/routes.py - REST Endpoints                                   │  │
│  │                                                                        │  │
│  │  POST /feedback/submit     - Receive feedback from frontend           │  │
│  │  GET  /feedback/questions  - Get feedback questions config            │  │
│  │  GET  /feedback/{id}       - Get feedback by session ID               │  │
│  │  GET  /feedback            - List all feedback (admin)                │  │
│  │                                                                        │  │
│  │  feedback_store = {}  ◄── In-memory storage (Dict)                    │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                            FRONTEND (TypeScript)                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  client/src/app.ts - VoiceScannerApp                                  │  │
│  │                                                                        │  │
│  │  Message Handler:                                                      │  │
│  │  - case 'feedback_request': handleFeedbackRequest()                   │  │
│  │                                                                        │  │
│  │  Methods:                                                              │  │
│  │  - handleFeedbackRequest()  - Shows feedback form                     │  │
│  │  - submitFeedback()         - POST to /feedback/submit                │  │
│  │  - closeFeedback()          - Removes feedback UI                     │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  client/src/components/FeedbackSelector/                              │  │
│  │                                                                        │  │
│  │  FeedbackRenderer.ts (Vanilla TypeScript)                             │  │
│  │  - render()           - Builds DOM for feedback form                  │  │
│  │  - selectOption()     - Handles option selection                      │  │
│  │  - handleSubmit()     - Triggers submission callback                  │  │
│  │  - handleSkip()       - Triggers skip callback                        │  │
│  │  - handleTimeout()    - Auto-submits on 45s timeout                   │  │
│  │  - showThankYou()     - Shows success + visual summary                │  │
│  │  - buildFeedbackSummary() - Builds HTML for selections                │  │
│  │  - close()            - Removes from DOM                              │  │
│  │                                                                        │  │
│  │  FeedbackSelector.tsx (React - for future use)                        │  │
│  │  FeedbackSelector.css (Styles)                                        │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Sequence Diagram

```
┌─────┐          ┌─────────┐          ┌──────────────────┐          ┌────────────────┐          ┌──────────┐
│User │          │Deepgram │          │ConversationMgr   │          │VoiceAssistant  │          │ Frontend │
└──┬──┘          └────┬────┘          └────────┬─────────┘          └───────┬────────┘          └────┬─────┘
   │                  │                        │                            │                        │
   │ "goodbye"        │                        │                            │                        │
   │─────────────────►│                        │                            │                        │
   │                  │                        │                            │                        │
   │                  │ TranscriptionFrame     │                            │                        │
   │                  │───────────────────────►│                            │                        │
   │                  │                        │                            │                        │
   │                  │                        │ LLM calls end_conversation │                        │
   │                  │                        │◄───────────────────────────│                        │
   │                  │                        │                            │                        │
   │                  │                        │ _handle_end_conversation() │                        │
   │                  │                        │────────────┐               │                        │
   │                  │                        │            │               │                        │
   │                  │                        │◄───────────┘               │                        │
   │                  │                        │                            │                        │
   │◄─────────────────┼────────────────────────┼── TTS: "Before you go..."  │                        │
   │                  │                        │                            │                        │
   │                  │                        │ _emit_feedback_ui()        │                        │
   │                  │                        │───────────────────────────►│                        │
   │                  │                        │                            │                        │
   │                  │                        │                            │ _emit_feedback_request │
   │                  │                        │                            │───────────────────────►│
   │                  │                        │                            │                        │
   │                  │                        │                            │                        │ render()
   │                  │                        │                            │                        │───┐
   │                  │                        │                            │                        │   │
   │                  │                        │ Start 45s timeout          │                        │◄──┘
   │                  │                        │────────────┐               │                        │
   │                  │                        │            │               │                        │
   │                  │                        │◄───────────┘               │                        │
   │                  │                        │                            │                        │
   │                  │                        │      [ User fills form ]   │                        │
   │                  │                        │                            │                        │
   │                  │                        │                            │  POST /feedback/submit │
   │                  │                        │◄───────────────────────────┼────────────────────────│
   │                  │                        │                            │                        │
   │                  │                        │ Store in feedback_store    │                        │
   │                  │                        │────────────┐               │                        │
   │                  │                        │            │               │                        │
   │                  │                        │◄───────────┘               │                        │
   │                  │                        │                            │                        │
   │                  │                        │ close_session(received=T)  │                        │
   │                  │                        │────────────┐               │                        │
   │                  │                        │            │               │                        │
   │◄─────────────────┼────────────────────────┼── TTS: "You selected..."   │                        │
   │                  │                        │            │               │                        │
   │                  │                        │ EndFrame   │               │                        │
   │                  │                        │────────────┴──────────────►│                        │
   │                  │                        │                            │                        │
   │                  │                        │         [ Session Ends ]   │                        │
   │                  │                        │                            │                        │
```

---

## Data Flow

### 1. Feedback Request Message (Backend → Frontend)

```json
{
  "message_type": "feedback_request",
  "a2ui": {
    "template": "feedback-form",
    "title": "Quick Feedback",
    "subtitle": "Help us improve your experience",
    "questions": [
      {
        "id": "overall_experience",
        "question": "How was your overall experience?",
        "options": [
          {"label": "Excellent", "value": "excellent", "emoji": "😊"},
          {"label": "Good", "value": "good", "emoji": "🙂"},
          {"label": "Okay", "value": "okay", "emoji": "😐"},
          {"label": "Poor", "value": "poor", "emoji": "😞"}
        ]
      },
      // ... more questions
    ],
    "config": {
      "submitButtonText": "Submit Feedback",
      "skipButtonText": "Skip",
      "timeoutSeconds": 45
    }
  },
  "session_id": "voice-session-abc123",
  "timestamp": 1707654321.123
}
```

### 2. Feedback Submission (Frontend → Backend)

**Request:**
```json
POST /feedback/submit
{
  "session_id": "voice-session-abc123",
  "responses": {
    "overall_experience": "excellent",
    "information_helpful": "very_helpful",
    "voice_quality": "clear",
    "would_use_again": "definitely"
  },
  "skipped": false
}
```

**Response:**
```json
{
  "success": true,
  "message": "Feedback received",
  "session_id": "voice-session-abc123"
}
```

### 3. Feedback Confirmation (Visual + Audio)

When the user submits feedback, the system provides both **visual** and **audio** confirmation:

**Visual Summary (Frontend):**
```
┌─────────────────────────────────────────┐
│           ✓ Thank You!                  │
│                                         │
│   YOUR FEEDBACK:                        │
│   ─────────────────────────────────     │
│   Overall Experience:      Excellent 😊 │
│   Information Helpful:     Very Helpful │
│   Voice Quality:      Clear & Natural   │
│   Would Use Again:         Definitely   │
│                                         │
└─────────────────────────────────────────┘
```

**Audio TTS (Backend):**
```
"You selected Excellent for overall experience, Very Helpful for information
helpfulness, Clear and Natural for voice quality, and Definitely for likelihood
to use again. Thank you for your feedback. Goodbye!"
```

The visual summary displays for 15 seconds while the bot speaks, then the session closes.

**Label Mappings** (in `app/services/conversation.py`):

```python
# Question ID to readable label
FEEDBACK_QUESTION_LABELS = {
    "overall_experience": "overall experience",
    "information_helpful": "information helpfulness",
    "voice_quality": "voice quality",
    "would_use_again": "likelihood to use again",
}

# Response value to readable text
FEEDBACK_RESPONSE_LABELS = {
    "excellent": "Excellent",
    "good": "Good",
    "okay": "Okay",
    "poor": "Poor",
    "very_helpful": "Very Helpful",
    "somewhat": "Somewhat",
    "not_really": "Not Really",
    "not_at_all": "Not at All",
    "clear": "Clear and Natural",
    "mostly_clear": "Mostly Clear",
    "hard_to_understand": "Hard to Understand",
    "definitely": "Definitely",
    "probably": "Probably",
    "maybe": "Maybe",
    "no": "No",
}
```

### 4. Storage Structure (In-Memory)

```python
feedback_store = {
    "voice-session-abc123": {
        "session_id": "voice-session-abc123",
        "responses": {
            "overall_experience": "excellent",
            "information_helpful": "very_helpful",
            "voice_quality": "clear",
            "would_use_again": "definitely"
        },
        "skipped": False,
        "submitted_at": "2024-02-16T10:30:00.000000"
    },
    # ... more sessions
}
```

---

## File Structure

```
app/
├── config/
│   └── feedback_questions.py      # Feedback questions configuration
├── services/
│   ├── a2ui/
│   │   └── feedback_generator.py  # Generates feedback A2UI payload
│   ├── conversation.py            # ConversationManager with feedback logic
│   └── feedback_store.py          # In-memory feedback storage (shared module)
├── core/
│   └── voice_assistant.py         # VoiceAssistant with feedback callback
└── api/
    └── routes.py                  # REST endpoints (uses feedback_store)

client/src/
├── components/
│   └── FeedbackSelector/
│       ├── FeedbackRenderer.ts    # Vanilla TS renderer (used by app.ts)
│       ├── FeedbackSelector.tsx   # React component (for future use)
│       ├── FeedbackSelector.css   # Styles
│       └── index.ts               # Exports
└── app.ts                         # Main app with feedback handling
```

---

## State Machine

```
                                    ┌─────────────────┐
                                    │                 │
                                    │     ACTIVE      │
                                    │   (Chatting)    │
                                    │                 │
                                    └────────┬────────┘
                                             │
                                             │ User says "goodbye"
                                             │ LLM calls end_conversation()
                                             ▼
                                    ┌─────────────────┐
                                    │                 │
                                    │    FEEDBACK     │
                              ┌────►│    WAITING      │◄────┐
                              │     │                 │     │
                              │     └────────┬────────┘     │
                              │              │              │
                              │     ┌────────┼────────┐     │
                              │     │        │        │     │
                              │     ▼        ▼        ▼     │
                              │  Submit    Skip   Timeout   │
                              │     │        │        │     │
                              │     └────────┼────────┘     │
                              │              │              │
                              │              ▼              │
                              │     ┌─────────────────┐     │
                              │     │                 │     │
                              │     │    CLOSING      │     │
                              │     │  (TTS farewell) │     │
                              │     │                 │     │
                              │     └────────┬────────┘     │
                              │              │              │
                              │              │ 13s wait     │
                              │              ▼              │
                              │     ┌─────────────────┐     │
                              │     │                 │     │
                              │     │     CLOSED      │     │
                              │     │   (EndFrame)    │     │
                              │     │                 │     │
                              │     └─────────────────┘     │
                              │                             │
                              └─────────────────────────────┘
                                     (Error: retry)
```

---

## API Reference

### POST /feedback/submit

Submit feedback from the frontend.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| session_id | string | Yes | Voice session identifier |
| responses | object | Yes | Question ID → selected value mapping |
| skipped | boolean | No | True if user clicked Skip (default: false) |

### GET /feedback/questions

Get the feedback questions configuration.

**Response:**
```json
{
  "questions": [
    {
      "id": "overall_experience",
      "question": "How was your overall experience?",
      "options": [...]
    }
  ]
}
```

### GET /feedback/{session_id}

Get feedback for a specific session.

### GET /feedback

List all feedback (admin/debugging).

---

## Customization

### Adding/Modifying Questions

Edit `app/config/feedback_questions.py`:

```python
FEEDBACK_QUESTIONS = [
    {
        "id": "unique_id",
        "question": "Your question text?",
        "options": [
            {"label": "Option 1", "value": "option_1", "emoji": "🎉"},
            {"label": "Option 2", "value": "option_2"},
        ]
    },
]
```

### Changing Timeout

In `app/services/a2ui/feedback_generator.py`:
```python
"config": {
    "timeoutSeconds": 60,  # Change from 45 to 60
}
```

Also update in `app/services/conversation.py`:
```python
total_timeout = 60  # Change from 45 to 60
```

### Persistent Storage

Replace the in-memory dict in `app/api/routes.py` with database calls:

```python
# Example with MongoDB
from motor.motor_asyncio import AsyncIOMotorClient

db = AsyncIOMotorClient("mongodb://...")["nesterai"]

@router.post("/feedback/submit")
async def submit_feedback(feedback: FeedbackSubmission):
    await db.feedback.insert_one({
        "session_id": feedback.session_id,
        "responses": feedback.responses,
        "skipped": feedback.skipped,
        "submitted_at": datetime.utcnow()
    })
    return {"success": True}
```

---

## Testing

### Manual Testing

1. Start backend: `python app/main.py`
2. Start frontend: `cd client && npm run dev`
3. Open http://localhost:5173
4. Connect to voice assistant
5. Say "goodbye" or "bye"
6. Verify feedback form appears
7. Answer questions and submit

### API Testing

```bash
# Get questions
curl http://localhost:7860/feedback/questions

# Submit feedback
curl -X POST http://localhost:7860/feedback/submit \
  -H "Content-Type: application/json" \
  -d '{"session_id":"test","responses":{"overall_experience":"excellent"},"skipped":false}'

# View all feedback
curl http://localhost:7860/feedback
```

### Expected Backend Logs

```
🔴 End conversation function called by LLM
📢 Pushing feedback prompt to TTS: 'Before you go...'
📝 EMITTING FEEDBACK REQUEST TO FRONTEND
📤 Sent feedback UI for session ...
📝 Waiting for feedback submission or timeout (45s)...
📝 Feedback received for session ...: {...}
📢 Speaking feedback summary: 'You selected Excellent for overall experience...'
🛑 Session ... closed (feedback_received=True)
```

---

## Known Limitations

1. **In-memory storage**: Feedback is lost on server restart
2. **No session-to-ConversationManager mapping**: The API cannot directly trigger `close_session()` - relies on timeout
3. **Single feedback per session**: Overwrites if submitted multiple times
4. **No analytics**: Raw storage only, no aggregation

---

## Future Enhancements

- [ ] Persistent database storage (PostgreSQL/MongoDB)
- [ ] Analytics dashboard
- [ ] A/B testing for questions
- [ ] Sentiment analysis on feedback
- [ ] Email notifications for poor feedback
- [ ] Multi-language support
- [x] ~~Spoken feedback summary~~ (Implemented - bot reads back selections before closing)
- [x] ~~Visual feedback summary~~ (Implemented - shows selections in Thank You screen)
