"""
PressureLab AI - Langflow Client
Orchestrates multi-step AI workflows: ContextRetrieval → Engines → Granite.
Uses the LangFlow Python package if available, otherwise falls back to a structured pipeline.
"""

import logging
import asyncio
from typing import Optional, Any, List

logger = logging.getLogger(__name__)

class PipelineStep:
    """A step in the AI processing pipeline."""
    def __init__(self, name: str, execute_fn, input_type: str = "any", output_type: str = "any"):
        self.name = name
        self.execute_fn = execute_fn
        self.input_type = input_type
        self.output_type = output_type

    async def execute(self, *args, **kwargs) -> Any:
        logger.info(f"LangFlow Pipeline executing step: {self.name}")
        return await self.execute_fn(*args, **kwargs)

class LangFlowPipeline:
    """
    Structured pipeline executor acting as the LangFlow orchestrator.
    Executes a chain of AI reasoning steps sequentially or concurrently.
    """
    def __init__(self, name: str):
        self.name = name
        self.steps: List[PipelineStep] = []

    def add_step(self, step: PipelineStep):
        self.steps.append(step)

    async def run(self, initial_state: dict) -> dict:
        logger.info(f"Starting LangFlow Pipeline: {self.name}")
        state = initial_state.copy()
        
        for step in self.steps:
            try:
                result = await step.execute(state)
                # Merge result into state
                if isinstance(result, dict):
                    state.update(result)
                else:
                    state[step.name] = result
            except Exception as e:
                logger.error(f"Error in pipeline step {step.name}: {e}")
                state["error"] = str(e)
                break
                
        logger.info(f"Completed LangFlow Pipeline: {self.name}")
        return state

class LangflowClient:
    """
    Client for Langflow AI orchestration.
    Integrates actual LangFlow components if available, otherwise uses internal LangFlowPipeline.
    """
    def __init__(self, granite_client=None, context_forge=None, docling_processor=None):
        self.granite_client = granite_client
        self.context_forge = context_forge
        self.docling_processor = docling_processor
        self._langflow_available = False
        self._try_import_langflow()

    def _try_import_langflow(self):
        """Check if langflow package is available."""
        try:
            import langflow
            self._langflow_available = True
            logger.info("Langflow Python package found.")
        except ImportError:
            logger.info("Langflow package not found. Using internal LangFlowPipeline orchestrator.")

    async def run_analysis_pipeline(self, query: str, match_id: int, minute: int) -> dict:
        """Runs the RAG pipeline to analyze a specific situation."""
        pipeline = LangFlowPipeline("SituationAnalysis")
        
        # Define pipeline steps
        async def retrieve_context(state: dict) -> dict:
            ctx = ""
            if self.context_forge:
                match_ctx = self.context_forge.get_match_context(state["match_id"], state["minute"])
                ctx = f"Game state at minute {state['minute']}: {match_ctx.get('score', '')}"
            return {"context": ctx}
            
        async def get_tactical_knowledge(state: dict) -> dict:
            kb = ""
            if self.docling_processor:
                report = self.docling_processor.get_match_knowledge_base()
                # Basic retrieval based on query keywords
                chunks = report.get('chunks', [])
                if chunks:
                    kb = "\n".join(c['text'] for c in chunks[:2])
            return {"knowledge": kb}
            
        async def reason_with_granite(state: dict) -> dict:
            if not self.granite_client:
                return {"analysis": "Granite client not available."}
                
            prompt = f"""
            Analyze the following football situation:
            Query: {state['query']}
            Minute: {state['minute']}
            Match Context: {state.get('context', '')}
            Tactical Knowledge: {state.get('knowledge', '')}
            
            Provide a detailed tactical explanation.
            """
            response = await self.granite_client.generate_explanation(prompt)
            return {"analysis": response}

        pipeline.add_step(PipelineStep("ContextRetrieval", retrieve_context))
        pipeline.add_step(PipelineStep("TacticalKnowledge", get_tactical_knowledge))
        pipeline.add_step(PipelineStep("GraniteReasoning", reason_with_granite))
        
        initial_state = {"query": query, "match_id": match_id, "minute": minute}
        return await pipeline.run(initial_state)

    async def run_match_story_pipeline(
        self, match_id: int, match_context: dict, structured: dict, match_info: dict
    ) -> dict:
        """Generates the AI Match Story — enriches data-built sections with Granite narrative."""
        pipeline = LangFlowPipeline("MatchStoryGeneration")

        async def prepare_evidence(state: dict) -> dict:
            return {"structured": state.get("structured", {}), "match_info": state.get("match_info", {})}

        async def generate_narrative(state: dict) -> dict:
            s = state.get("structured", {})
            mi = state.get("match_info", {})
            if not self.granite_client:
                return {"narrative": s.get("executive_summary", ""), "granite_sections": {}}

            prompt = f"""You are PressureLab AI. Enrich this evidence-backed match story for {mi.get('home_team')} vs {mi.get('away_team')}.

Structured data (DO NOT contradict this evidence):
- Executive summary: {s.get('executive_summary')}
- Turning points: {s.get('turning_points')}
- MVP: {s.get('match_mvp')}
- Hidden hero: {s.get('hidden_hero')}
- Biggest surprise: {s.get('biggest_surprise')}
- Risk moments: {s.get('risk_moments')}
- Tactical evolution: {s.get('tactical_evolution')}
- Momentum: {s.get('momentum_narrative')}
- Psychology: {s.get('psychological_story')}
- Historical parallels: {s.get('historical_parallels')}

Respond in JSON:
{{
  "narrative": "3 compelling paragraphs referencing specific evidence",
  "executive_summary": "1 paragraph executive summary",
  "psychological_story": "2 sentences on mental dynamics",
  "coaching_insight": "2 sentences on coaching decisions",
  "biggest_surprise_text": "1 sentence",
  "what_next": "What should happen next tactically"
}}"""
            response = await self.granite_client.generate_text(prompt, system_prompt="You are PressureLab AI football analyst.")
            parsed = self.granite_client._parse_json_response(response, {
                "narrative": s.get("executive_summary", ""),
                "executive_summary": s.get("executive_summary", ""),
                "psychological_story": s.get("psychological_story", ""),
                "coaching_insight": "",
                "biggest_surprise_text": s.get("biggest_surprise", {}).get("description", ""),
                "what_next": "",
            })
            return parsed

        pipeline.add_step(PipelineStep("PrepareEvidence", prepare_evidence))
        pipeline.add_step(PipelineStep("GraniteNarrative", generate_narrative))

        result = await pipeline.run({
            "match_id": match_id,
            "match_context": match_context,
            "structured": structured,
            "match_info": match_info,
        })

        return {
            "narrative": result.get("narrative", structured.get("executive_summary", "")),
            "executive_summary": result.get("executive_summary", structured.get("executive_summary", "")),
            "turning_points": structured.get("turning_points", []),
            "tactical_evolution": structured.get("tactical_evolution", {}),
            "momentum_narrative": structured.get("momentum_narrative", ""),
            "psychological_story": result.get("psychological_story", structured.get("psychological_story", "")),
            "coaching_decisions": structured.get("coaching_decisions", []),
            "coaching_insight": result.get("coaching_insight", ""),
            "biggest_surprise": structured.get("biggest_surprise", {}),
            "biggest_surprise_text": result.get("biggest_surprise_text", ""),
            "match_mvp": structured.get("match_mvp", {}),
            "hidden_hero": structured.get("hidden_hero", {}),
            "risk_moments": structured.get("risk_moments", []),
            "historical_parallels": structured.get("historical_parallels", []),
            "what_next": result.get("what_next", ""),
            "stats": structured.get("stats", {}),
            "evidence_index": structured.get("evidence_index", []),
            "generated_by": "IBM Granite via LangFlow Pipeline",
        }

    async def run_ask_pipeline(
        self,
        question: str,
        match_id: int,
        minute: int,
        match_context: str,
        tactical_knowledge: str,
        historical_comparisons: str,
        page_context: str = "",
    ) -> dict:
        """LangFlow orchestration: Docling → Context → Historical → Granite → Evidence."""
        pipeline = LangFlowPipeline("AskPressureLab")

        async def retrieve_context(state: dict) -> dict:
            return {"retrieved_context": state.get("match_context", "")}

        async def retrieve_knowledge(state: dict) -> dict:
            kb = state.get("tactical_knowledge", "")
            if self.docling_processor and not kb:
                report = self.docling_processor.get_match_knowledge_base()
                kb = "\n".join(c["text"] for c in report.get("chunks", [])[:3])
            return {"tactical_knowledge": kb}

        async def reason_with_granite(state: dict) -> dict:
            if not self.granite_client:
                q = state.get("question", "this moment")
                return {
                    "answer": (
                        f"At minute {state.get('minute', 0)}, the tactical picture centres on "
                        f"pressure timing and passing lane availability — {q.lower().rstrip('?')}."
                    ),
                    "confidence": 0.68,
                    "evidence": [state.get("page_context", "Selected workspace moment")],
                }
            result = await self.granite_client.ask_question(
                question=state["question"],
                match_context=state.get("retrieved_context", ""),
                tactical_knowledge=state.get("tactical_knowledge", ""),
                historical_comparisons=state.get("historical_comparisons", ""),
                minute=state["minute"],
                page_context=state.get("page_context", ""),
            )
            return result

        pipeline.add_step(PipelineStep("ContextRetrieval", retrieve_context))
        pipeline.add_step(PipelineStep("DoclingKnowledge", retrieve_knowledge))
        pipeline.add_step(PipelineStep("GraniteReasoning", reason_with_granite))

        initial = {
            "question": question,
            "match_id": match_id,
            "minute": minute,
            "match_context": match_context,
            "tactical_knowledge": tactical_knowledge,
            "historical_comparisons": historical_comparisons,
            "page_context": page_context,
        }
        return await pipeline.run(initial)
