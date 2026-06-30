"""
PressureLab AI - Live Analysis Architecture (Future-Ready)
Clean interfaces for computer vision, event detection, and live feed integration.
Not fully implemented — designed for future extension without refactoring core engines.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import AsyncIterator, Optional


class EventSource(str, Enum):
    STATSBOMB = "statsbomb"
    LIVE_CV = "live_cv"
    MANUAL = "manual"
    API_FEED = "api_feed"


@dataclass
class LiveEvent:
    """Normalized event from any source (StatsBomb, CV, or live feed)."""
    event_type: str
    minute: int
    second: int
    player_name: str
    player_id: int
    team: str
    location_x: Optional[float] = None
    location_y: Optional[float] = None
    outcome: Optional[str] = None
    under_pressure: bool = False
    source: EventSource = EventSource.STATSBOMB
    confidence: float = 1.0
    metadata: dict = field(default_factory=dict)


@dataclass
class FrameAnalysis:
    """Output from computer vision frame processing (future)."""
    timestamp_ms: int
    player_positions: list[dict]
    ball_position: Optional[tuple[float, float]] = None
    detected_events: list[LiveEvent] = field(default_factory=list)
    confidence: float = 0.0


class VideoProcessor(ABC):
    """Future: process match video frames into spatial data."""

    @abstractmethod
    async def process_frame(self, frame_bytes: bytes, timestamp_ms: int) -> FrameAnalysis:
        ...


class EventDetector(ABC):
    """Future: detect football events from video or tracking data."""

    @abstractmethod
    async def detect_events(self, frame_analysis: FrameAnalysis) -> list[LiveEvent]:
        ...


class LiveEventFeed(ABC):
    """Future: connect to live event streams (Opta, StatsPerform, custom)."""

    @abstractmethod
    async def connect(self, feed_url: str, credentials: Optional[dict] = None) -> bool:
        ...

    @abstractmethod
    async def stream_events(self) -> AsyncIterator[LiveEvent]:
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        ...


class LiveAnalysisPipeline:
    """
    Orchestrates live analysis flow:
    Video → CV → Event Detection → Engines → Granite → Dashboard
    """

    def __init__(
        self,
        video_processor: Optional[VideoProcessor] = None,
        event_detector: Optional[EventDetector] = None,
        pressure_engine=None,
        psychology_engine=None,
        prediction_engine=None,
        granite_client=None,
    ):
        self.video_processor = video_processor
        self.event_detector = event_detector
        self.pressure_engine = pressure_engine
        self.psychology_engine = psychology_engine
        self.prediction_engine = prediction_engine
        self.granite = granite_client
        self._events_buffer: list[LiveEvent] = []
        self._active = False

    @property
    def is_live_capable(self) -> bool:
        return self.video_processor is not None or self.event_detector is not None

    async def ingest_event(self, event: LiveEvent) -> dict:
        """Process a single live event through all engines."""
        self._events_buffer.append(event)
        return {
            "event": event,
            "status": "buffered",
            "buffer_size": len(self._events_buffer),
            "live_capable": self.is_live_capable,
        }

    def get_status(self) -> dict:
        return {
            "active": self._active,
            "live_capable": self.is_live_capable,
            "video_processor": self.video_processor is not None,
            "event_detector": self.event_detector is not None,
            "events_buffered": len(self._events_buffer),
            "architecture": "Video → CV → Event Detection → Pressure → Psychology → Prediction → Granite → Dashboard",
        }


class PlaceholderVideoProcessor(VideoProcessor):
    """Stub for future computer vision integration."""

    async def process_frame(self, frame_bytes: bytes, timestamp_ms: int) -> FrameAnalysis:
        return FrameAnalysis(
            timestamp_ms=timestamp_ms,
            player_positions=[],
            confidence=0.0,
        )


class PlaceholderLiveFeed(LiveEventFeed):
    """Stub for future live feed connection."""

    async def connect(self, feed_url: str, credentials: Optional[dict] = None) -> bool:
        return False

    async def stream_events(self) -> AsyncIterator[LiveEvent]:
        if False:
            yield LiveEvent("Pass", 0, 0, "", 0, "")

    async def disconnect(self) -> None:
        pass
