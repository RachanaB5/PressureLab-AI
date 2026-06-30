"""
PressureLab AI - Granite Client
Event-grounded inference with retry and deterministic fallbacks.
"""

import asyncio
import json
import logging
from typing import Optional

from engine.event_grounding import (
    build_grounded_explanation,
    build_grounded_copilot_answer,
    format_snapshot_for_prompt,
    is_generic_text,
    merge_granite_with_grounding,
)

from .providers.base import LLMProvider
from .prompts import (
    SYSTEM_PROMPT,
    EVENT_EXPLANATION_PROMPT,
    COPILOT_PROMPT,
)

logger = logging.getLogger(__name__)


class GraniteClient:
    """IBM Granite client — all outputs grounded in the selected event."""

    def __init__(self, provider: LLMProvider):
        self.provider = provider
        logger.info("GraniteClient initialized with provider: %s", provider.get_model_name())

    async def _generate_with_retry(
        self,
        prompt: str,
        system_prompt: str = "",
        max_tokens: int = 1024,
        temperature: float = 0.25,
        retries: int = 2,
    ) -> str:
        last = ""
        for attempt in range(retries):
            try:
                text = await self.provider.generate(
                    prompt=prompt,
                    system_prompt=system_prompt or SYSTEM_PROMPT,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                if text and not is_generic_text(text):
                    return text
                last = text or ""
            except Exception as e:
                logger.warning("Granite attempt %s failed: %s", attempt + 1, e)
                last = ""
            if attempt < retries - 1:
                await asyncio.sleep(0.4 * (attempt + 1))
        return last

    async def explain_event(
        self,
        event_type: str,
        minute: int,
        player_name: str,
        team: str,
        outcome: str,
        location_x: float,
        location_y: float,
        under_pressure: bool,
        pressure_score: float,
        pressure_factors: dict,
        score: str,
        team_momentum: float,
        opponent_momentum: float,
        recent_events: str,
        explanation_level: str = "analyst",
        tactical_snapshot: Optional[dict] = None,
    ) -> dict:
        snapshot = tactical_snapshot or {
            "minute": minute,
            "player": player_name,
            "team": team,
            "event_type": event_type,
            "outcome": outcome,
            "score": score,
            "ball_x": location_x,
            "ball_y": location_y,
            "pressure_index": pressure_score,
            "under_pressure": under_pressure,
        }
        grounded = build_grounded_explanation(snapshot)

        prompt = EVENT_EXPLANATION_PROMPT.format(
            tactical_snapshot=format_snapshot_for_prompt(snapshot),
            event_type=event_type,
            minute=minute,
            player_name=player_name,
            team=team,
            outcome=outcome,
            location_x=location_x,
            location_y=location_y,
            under_pressure=under_pressure,
            pressure_score=pressure_score,
            score=score,
            team_momentum=team_momentum,
            opponent_momentum=opponent_momentum,
            recent_events=recent_events,
        )

        response = await self._generate_with_retry(prompt, SYSTEM_PROMPT, max_tokens=900, temperature=0.2)
        if not response:
            return grounded

        parsed = self._parse_json_response(response, grounded)
        return merge_granite_with_grounding(parsed, snapshot)

    async def ask_question(
        self,
        question: str,
        match_context: str,
        tactical_knowledge: str,
        historical_comparisons: str,
        minute: int,
        page_context: str = "",
        tactical_snapshot: Optional[dict] = None,
    ) -> dict:
        snapshot = tactical_snapshot or {"minute": minute, "score": "0-0", "player": "Player", "ball_x": 60, "ball_y": 40}
        grounded = build_grounded_copilot_answer(question, snapshot)

        prompt = COPILOT_PROMPT.format(
            question=question,
            tactical_snapshot=format_snapshot_for_prompt(snapshot) + "\n" + (match_context or "")[:1200],
            page_context=page_context or "",
            minute=snapshot.get("minute", minute),
            score=snapshot.get("score", "?"),
            player=snapshot.get("player", "Player"),
            ball_x=snapshot.get("ball_x", 60),
            ball_y=snapshot.get("ball_y", 40),
        )

        response = await self._generate_with_retry(prompt, SYSTEM_PROMPT, max_tokens=800, temperature=0.2)
        if not response:
            return grounded

        parsed = self._parse_json_response(response, grounded)
        answer = parsed.get("answer") or parsed.get("reasoning", "")
        if is_generic_text(str(answer)):
            return grounded
        parsed["answer"] = answer
        if not parsed.get("bullets"):
            parsed["bullets"] = grounded.get("bullets", [])
        return parsed

    async def generate_text(self, prompt: str, system_prompt: str = "") -> str:
        return await self._generate_with_retry(
            prompt, system_prompt or SYSTEM_PROMPT, max_tokens=1024, temperature=0.25,
        )

    async def generate_explanation(self, prompt: str) -> str:
        return await self.generate_text(prompt)

    def _parse_json_response(self, response: str, fallback: dict) -> dict:
        try:
            cleaned = response.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                json_lines = []
                in_json = False
                for line in lines:
                    if line.strip().startswith("```") and not in_json:
                        in_json = True
                        continue
                    if line.strip().startswith("```") and in_json:
                        break
                    if in_json:
                        json_lines.append(line)
                cleaned = "\n".join(json_lines)

            start = cleaned.find("{")
            end = cleaned.rfind("}") + 1
            if start >= 0 and end > start:
                cleaned = cleaned[start:end]

            parsed = json.loads(cleaned)

            if "answer" not in parsed and parsed.get("reasoning"):
                parsed["answer"] = parsed["reasoning"]
            if "explanation" in parsed and not parsed.get("answer"):
                parsed["answer"] = parsed["explanation"]

            if "confidence" in parsed:
                conf = parsed["confidence"]
                if not isinstance(conf, (int, float)) or conf < 0 or conf > 1:
                    parsed["confidence"] = 0.75

            if "evidence" in parsed and not isinstance(parsed["evidence"], list):
                parsed["evidence"] = [str(parsed["evidence"])]

            for k, v in fallback.items():
                if k not in parsed or (isinstance(parsed.get(k), str) and is_generic_text(parsed[k])):
                    parsed[k] = v

            return parsed

        except (json.JSONDecodeError, ValueError) as e:
            logger.warning("Failed to parse Granite JSON: %s", e)
            result = fallback.copy()
            if response and len(response) > 20 and not is_generic_text(response[:500]):
                result["reasoning"] = response[:600]
                result["answer"] = response[:600]
            return result
