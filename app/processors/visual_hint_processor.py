"""
Visual Hint Processor - Streaming text and content-aware visual hints.

This processor intercepts LLM text output and:
1. Emits streaming_text events word-by-word for animated display
2. Detects content types (contact, services, greeting, pricing, projects)
3. Emits visual_hint events to trigger frontend card templates
"""

import re
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger
from pipecat.frames.frames import Frame, TextFrame, OutputTransportMessageFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor


class VisualHintProcessor(FrameProcessor):
    """Processor that streams text word-by-word and detects content for visual hints."""

    # Content detection patterns with priorities
    CONTENT_PATTERNS: Dict[str, Dict[str, Any]] = {
        "greeting": {
            "patterns": [
                re.compile(r"\b(hello|hi|hey|welcome)\b", re.IGNORECASE),
                re.compile(r"\bgood (morning|afternoon|evening)\b", re.IGNORECASE),
                re.compile(r"\bhow can I (help|assist)\b", re.IGNORECASE),
                re.compile(r"\bI'm (the |here to |happy to )", re.IGNORECASE),
            ],
            "priority": 1,
            "visual_type": "greeting_animation",
            "cooldown": 30.0,
        },
        "contact": {
            "patterns": [
                re.compile(r"[\w\.-]+@[\w\.-]+\.\w+"),  # Email
                re.compile(r"\+?1?\s*\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}"),  # Phone
                re.compile(r"\b(email|phone|call|contact|reach)\s*(us|me|them)?\s*(at|:)?\b", re.IGNORECASE),
                re.compile(r"\bget in touch\b", re.IGNORECASE),
                re.compile(r"\blet's talk\b", re.IGNORECASE),
            ],
            "priority": 2,
            "visual_type": "contact_card",
            "cooldown": 10.0,
        },
        "company": {
            "patterns": [
                re.compile(r"\b(about|tell me about|what is|who is)\s+(nesterlabs|nester labs|the company|us)\b", re.IGNORECASE),
                re.compile(r"\bAI.accelerated\s+(studio|product)\b", re.IGNORECASE),
                re.compile(r"\b85\+?\s*years?\s+(combined\s+)?experience\b", re.IGNORECASE),
                re.compile(r"\bbased in\s+(the\s+)?SF\s*Bay\b", re.IGNORECASE),
            ],
            "priority": 3,
            "visual_type": "company_card",
            "cooldown": 20.0,
        },
        "services": {
            "patterns": [
                re.compile(r"\b(what|describe|tell me about)\s+(your\s+)?(services?|offerings?)\b", re.IGNORECASE),
                re.compile(r"\bfour pillars\b", re.IGNORECASE),
                re.compile(r"\b(HUMAN|INTELLIGENCE|MEMORY|CLOUD)\s+pillar\b", re.IGNORECASE),
                re.compile(r"\bour\s+services?\s+(include|are|cover)\b", re.IGNORECASE),
            ],
            "priority": 4,
            "visual_type": "service_card",
            "cooldown": 15.0,
        },
        "expertise": {
            "patterns": [
                re.compile(r"\b(what|tell me about|describe)\s+(your\s+|the\s+)?(expertise|capabilities|specializations?|technical skills?)\b", re.IGNORECASE),
                re.compile(r"\b(what do you|what does the team)\s+(specialize in|excel at|focus on)\b", re.IGNORECASE),
                re.compile(r"\b(our|the|your)\s+(expertise|specialization)\s+(is|includes?|covers?)\b", re.IGNORECASE),
                re.compile(r"\bexpertise\s+(areas?|in)\s+(voice AI|agentic AI|RAG|NLP|conversational)\b", re.IGNORECASE),
            ],
            "priority": 5,
            "visual_type": "expertise_card",
            "cooldown": 15.0,
        },
        "pricing": {
            "patterns": [
                re.compile(r"\b(what|tell me about|how much)\s+(is|are|does)\s+(your\s+)?(pricing|cost|rate)\b", re.IGNORECASE),
                re.compile(r"\bengagement\s+(models?|options?|types?)\b", re.IGNORECASE),
                re.compile(r"\b(discovery|design sprint|product development)\s+(engagement|model|option)\b", re.IGNORECASE),
                re.compile(r"\bhow do you charge\b", re.IGNORECASE),
                re.compile(r"\bwhat.s (the|your) (pricing|cost|rate)\b", re.IGNORECASE),
            ],
            "priority": 6,
            "visual_type": "pricing_card",
            "cooldown": 15.0,
        },
        "project_visualizing_intelligence": {
            "patterns": [
                re.compile(r"\bvisuali[sz]ing intelligence\b", re.IGNORECASE),
                re.compile(r"\bstrategy,? identity(,| and) web\b", re.IGNORECASE),
            ],
            "priority": 7,
            "visual_type": "project_detail_visualizing_intelligence",
            "cooldown": 12.0,
        },
        "project_natural_conversations": {
            "patterns": [
                re.compile(r"\bnatural conversations( with data)?\b", re.IGNORECASE),
                re.compile(r"\bconversations with data\b", re.IGNORECASE),
                re.compile(r"\bplain language (data|analytics)\b", re.IGNORECASE),
                re.compile(r"\bdata platform\b", re.IGNORECASE),
            ],
            "priority": 7,
            "visual_type": "project_detail_natural_conversations",
            "cooldown": 12.0,
        },
        "project_agentic_intake": {
            "patterns": [
                re.compile(r"\bagentic intake coordinator\b", re.IGNORECASE),
                re.compile(r"\bintake coordinator\b", re.IGNORECASE),
                re.compile(r"\bintake workflow\b", re.IGNORECASE),
                re.compile(r"\bworkflow automation\b", re.IGNORECASE),
            ],
            "priority": 7,
            "visual_type": "project_detail_agentic_intake",
            "cooldown": 12.0,
        },
        "project_ai_first_bank": {
            "patterns": [
                re.compile(r"\bAI[- ]?first bank\b", re.IGNORECASE),
                re.compile(r"\bconversational finance\b", re.IGNORECASE),
                re.compile(r"\bbanking experience\b", re.IGNORECASE),
            ],
            "priority": 7,
            "visual_type": "project_detail_ai_first_bank",
            "cooldown": 12.0,
        },
        "projects": {
            "patterns": [
                re.compile(r"\b(what|tell me about|show me|describe)\s+(your\s+)?(projects?|case studies?|portfolio|work|examples?)\b", re.IGNORECASE),
                re.compile(r"\bour\s+(projects?|case studies?|portfolio)\s+(include|are)\b", re.IGNORECASE),
                re.compile(r"\b(we|we've|we have)\s+(worked on|built|developed|created|delivered|completed)\s+(projects?|case studies?)\b", re.IGNORECASE),
                re.compile(r"\b(past|previous|recent)\s+(projects?|work|case studies?)\b", re.IGNORECASE),
            ],
            "priority": 8,
            "visual_type": "project_card",
            "cooldown": 15.0,
        },
        "next_steps": {
            "patterns": [
                re.compile(r"\b(what are the|what's the|tell me about the)\s+next steps?\b", re.IGNORECASE),
                re.compile(r"\bwhat happens\s+(next|after|when I reach out)\b", re.IGNORECASE),
                re.compile(r"\bhow (do I|to)\s+(start|get started|begin|proceed)\b", re.IGNORECASE),
                re.compile(r"\b(ready to|want to|like to)\s+(start|begin|get started|move forward)\b", re.IGNORECASE),
                re.compile(r"\b(process|timeline|engagement)\s+(for|when)\s+(starting|onboarding|beginning)\b", re.IGNORECASE),
            ],
            "priority": 8,
            "visual_type": "next_steps_card",
            "cooldown": 20.0,
        },
        "location": {
            "patterns": [
                re.compile(r"\b(what is your|where is your|where are you)\s+(location|address|office)\b", re.IGNORECASE),
                re.compile(r"\b(where|how)\s+(can I|do I)\s+(visit|find you|come see you)\b", re.IGNORECASE),
                re.compile(r"\b(based in|located in|office in)\s+(Sunnyvale|Silicon Valley|California|SF Bay)\b", re.IGNORECASE),
                re.compile(r"\b701 Lakeway\b", re.IGNORECASE),
                re.compile(r"\bin.person\s+(meeting|visit)\b", re.IGNORECASE),
            ],
            "priority": 9,
            "visual_type": "location_card",
            "cooldown": 20.0,
        },
    }

    # Patterns for extracting specific content
    EMAIL_PATTERN = re.compile(r"[\w\.-]+@[\w\.-]+\.\w+")
    PHONE_PATTERN = re.compile(r"\+?1?\s*\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}")

    def __init__(
        self,
        enabled: bool = True,
        stream_words: bool = True,
        detect_content: bool = True,
        min_confidence: float = 0.5,  # Increased threshold for more precise triggering
        **kwargs
    ):
        """Initialize the Visual Hint Processor.

        Args:
            enabled: Whether the processor is enabled
            stream_words: Whether to emit streaming text events
            detect_content: Whether to detect content for visual hints
            min_confidence: Minimum confidence for content detection
        """
        super().__init__(**kwargs)
        self.enabled = enabled
        self.stream_words = stream_words
        self.detect_content = detect_content
        self.min_confidence = min_confidence

        # State tracking
        self._current_utterance_id: Optional[str] = None
        self._sequence_counter: int = 0
        self._text_buffer: str = ""
        self._last_hint_times: Dict[str, float] = {}  # Track cooldowns per content type
        self._emitted_hints_this_utterance: set = set()  # Prevent duplicate hints

        logger.info(
            f"VisualHintProcessor initialized: "
            f"enabled={enabled}, stream_words={stream_words}, detect_content={detect_content}"
        )

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        """Process frames, intercepting TextFrames for streaming and content detection."""
        await super().process_frame(frame, direction)

        if not self.enabled:
            await self.push_frame(frame, direction)
            return

        # Only process downstream TextFrames from LLM
        if isinstance(frame, TextFrame) and direction == FrameDirection.DOWNSTREAM:
            text = frame.text if hasattr(frame, 'text') else str(frame)
            logger.info(f"📝 VisualHint received TextFrame: '{text[:50]}...' (direction={direction})")

            if text and text.strip():
                # Start new utterance if needed
                if self._current_utterance_id is None:
                    self._current_utterance_id = str(uuid.uuid4())
                    self._sequence_counter = 0
                    self._text_buffer = ""
                    self._emitted_hints_this_utterance = set()
                    logger.info(f"📝 Started new utterance: {self._current_utterance_id}")

                # Emit streaming text events (word by word)
                if self.stream_words:
                    await self._emit_streaming_text(text)

                # Buffer text for content detection
                self._text_buffer += text

                # Detect content patterns and emit visual hints
                if self.detect_content:
                    await self._detect_and_emit_hints()

        # Always pass frame downstream to TTS
        await self.push_frame(frame, direction)

    async def _emit_streaming_text(self, text: str) -> None:
        """Emit streaming text event for word-by-word display.

        Args:
            text: Text chunk from LLM
        """
        # Split into words, preserving punctuation attached to words
        words = text.split()

        for word in words:
            if word.strip():
                self._sequence_counter += 1

                message = {
                    "label": "rtvi-ai",
                    "type": "server-message",
                    "data": {
                        "message_type": "streaming_text",
                        "text": word,
                        "is_final": False,
                        "sequence_id": self._sequence_counter,
                        "utterance_id": self._current_utterance_id,
                        "timestamp": time.time(),
                    }
                }

                try:
                    data_frame = OutputTransportMessageFrame(message=message)
                    await self.push_frame(data_frame)
                    logger.info(f"📤 Streamed word: '{word}' (seq={self._sequence_counter})")
                except Exception as e:
                    logger.warning(f"Failed to emit streaming text: {e}")

    async def _detect_and_emit_hints(self) -> None:
        """Detect content patterns in buffered text and emit visual hints."""
        current_time = time.time()

        # Check each content type
        detected_types: List[Tuple[str, float, Dict[str, Any]]] = []

        logger.debug(f"🔍 Checking patterns in buffer: '{self._text_buffer[:100]}...'")

        for content_type, config in self.CONTENT_PATTERNS.items():
            # Skip if already emitted this utterance
            if content_type in self._emitted_hints_this_utterance:
                logger.debug(f"⏭️ Skipping {content_type} - already emitted this utterance")
                continue

            # Check cooldown
            last_time = self._last_hint_times.get(content_type, 0)
            if current_time - last_time < config["cooldown"]:
                logger.debug(f"⏭️ Skipping {content_type} - in cooldown")
                continue

            # Check patterns
            match_count = 0
            for pattern in config["patterns"]:
                if pattern.search(self._text_buffer):
                    match_count += 1

            # Calculate confidence based on match count - lowered threshold
            if match_count > 0:
                confidence = min(1.0, match_count * 0.5)  # 0.5 per match, max 1.0
                logger.info(f"📊 {content_type}: {match_count} matches, confidence={confidence:.2f}")

                if confidence >= self.min_confidence:
                    # Extract content specific to this type
                    extracted_content = self._extract_content(content_type, self._text_buffer)
                    detected_types.append((content_type, confidence, extracted_content))
                    logger.info(f"✅ {content_type} added to detected types")

        # Emit highest priority hint
        if detected_types:
            # Sort by priority (lower = higher priority)
            detected_types.sort(
                key=lambda x: self.CONTENT_PATTERNS[x[0]]["priority"]
            )

            content_type, confidence, extracted_content = detected_types[0]
            logger.info(f"🎯 Emitting visual hint: {content_type} (confidence={confidence:.2f})")
            await self._emit_visual_hint(content_type, confidence, extracted_content)

            # Mark as emitted
            self._emitted_hints_this_utterance.add(content_type)
            self._last_hint_times[content_type] = current_time
        else:
            logger.debug(f"❌ No visual hints detected (buffer len={len(self._text_buffer)})")

    def _extract_content(self, content_type: str, text: str) -> Dict[str, Any]:
        """Extract specific content based on content type.

        Args:
            content_type: Type of content to extract
            text: Text to extract from

        Returns:
            Dictionary of extracted content
        """
        content: Dict[str, Any] = {}

        if content_type == "contact":
            # Extract email
            email_match = self.EMAIL_PATTERN.search(text)
            if email_match:
                content["email"] = email_match.group()

            # Extract phone
            phone_match = self.PHONE_PATTERN.search(text)
            if phone_match:
                content["phone"] = phone_match.group()

        elif content_type == "services":
            # Extract mentioned services/capabilities
            services = []
            service_keywords = [
                "AI", "machine learning", "development", "consulting",
                "voice", "chatbot", "automation", "integration"
            ]
            for keyword in service_keywords:
                if keyword.lower() in text.lower():
                    services.append(keyword)
            if services:
                content["services"] = services[:5]  # Max 5 services

        elif content_type == "pricing":
            # Extract dollar amounts
            amounts = re.findall(r"\$[\d,]+(?:\.\d{2})?", text)
            if amounts:
                content["amounts"] = amounts

        elif content_type == "greeting":
            # No specific extraction needed
            content["type"] = "welcome"

        elif content_type.startswith("project_"):
            project_id = content_type.replace("project_", "")
            content["project_id"] = project_id
        elif content_type == "projects":
            # Extract project-related keywords
            content["mentioned"] = True

        return content

    async def _emit_visual_hint(
        self,
        content_type: str,
        confidence: float,
        content: Dict[str, Any]
    ) -> None:
        """Emit a visual hint event to the frontend.

        Args:
            content_type: Type of content detected
            confidence: Detection confidence (0-1)
            content: Extracted content data
        """
        visual_type = self.CONTENT_PATTERNS[content_type]["visual_type"]

        message = {
            "label": "rtvi-ai",
            "type": "server-message",
            "data": {
                "message_type": "visual_hint",
                "hint_type": visual_type,
                "content_type": content_type,
                "content": content,
                "confidence": round(confidence, 2),
                "trigger_text": self._text_buffer[-200:] if len(self._text_buffer) > 200 else self._text_buffer,
                "timestamp": time.time(),
            }
        }

        logger.info(
            f"Emitting visual hint: type={visual_type}, confidence={confidence:.2f}, "
            f"content={content}"
        )

        try:
            data_frame = OutputTransportMessageFrame(message=message)
            await self.push_frame(data_frame)
        except Exception as e:
            logger.warning(f"Failed to emit visual hint: {e}")

    async def finalize_utterance(self) -> None:
        """Finalize the current utterance, emitting is_final=True."""
        if self._current_utterance_id:
            # Emit final marker
            message = {
                "label": "rtvi-ai",
                "type": "server-message",
                "data": {
                    "message_type": "streaming_text",
                    "text": "",
                    "is_final": True,
                    "sequence_id": self._sequence_counter + 1,
                    "utterance_id": self._current_utterance_id,
                    "timestamp": time.time(),
                }
            }

            try:
                data_frame = OutputTransportMessageFrame(message=message)
                await self.push_frame(data_frame)
            except Exception as e:
                logger.warning(f"Failed to emit final marker: {e}")

            logger.debug(
                f"Finalized utterance {self._current_utterance_id} "
                f"with {self._sequence_counter} words"
            )

            # Reset state
            self._current_utterance_id = None
            self._sequence_counter = 0
            self._text_buffer = ""
            self._emitted_hints_this_utterance = set()

    def get_status(self) -> Dict[str, Any]:
        """Get processor status.

        Returns:
            Status dictionary
        """
        return {
            "enabled": self.enabled,
            "stream_words": self.stream_words,
            "detect_content": self.detect_content,
            "current_utterance_id": self._current_utterance_id,
            "sequence_counter": self._sequence_counter,
            "buffer_length": len(self._text_buffer),
            "content_types": list(self.CONTENT_PATTERNS.keys()),
        }
