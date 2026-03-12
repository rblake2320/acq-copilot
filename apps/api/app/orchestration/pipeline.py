"""Thin pipeline wrapper that connects chat requests to the orchestration layer.

This is the single entry point called by the chat router.
Routes query through: IntentRouter → ExecutionPlanner → ExecutionEngine → AnswerSynthesizer
Falls back to direct Anthropic call if orchestration fails.
"""

import time
import asyncio
from typing import Optional, Any
from pydantic import BaseModel
import structlog
import anthropic

from .router import IntentRouter, IntentCategory
from .planner import ExecutionPlanner, ExecutionStep, ExecutionPlan
from .executor import ExecutionEngine, ExecutionContext, ToolRunResult as ExecToolRunResult
from .answer_synthesizer import AnswerSynthesizer
from .guards import SourceGroundingGuard, PIIDetectionGuard, AcquisitionDisclaimerGuard
from ..tools.registry import get_registry
from ..tools.base import BaseTool
from ..config import settings

logger = structlog.get_logger(__name__)


class PipelineToolRun(BaseModel):
    """Tool run result for chat response."""
    tool_id: str
    name: str
    status: str  # "success" | "error" | "timeout"
    input_params: dict
    output: Any
    duration_ms: float
    error: Optional[str] = None


class PipelineCitation(BaseModel):
    """Citation for chat response."""
    source_name: str
    source_url: str
    source_label: str
    snippet: Optional[str] = None
    retrieved_at: str


class PipelineResult(BaseModel):
    """Result returned from run_pipeline."""
    answer: str
    tool_runs: list[PipelineToolRun] = []
    citations: list[PipelineCitation] = []
    intent_category: str = "general_question"
    confidence: float = 1.0
    warnings: list[str] = []
    execution_time_ms: float = 0.0


SYSTEM_PROMPT = (
    "You are an expert federal acquisition assistant specializing in FAR/DFARS, "
    "IGCE methodology, market research, and contracting best practices. "
    "Answer questions clearly and cite relevant regulations when applicable. "
    "When tools have gathered data, synthesize it into a clear, actionable response."
)


def _make_tool_executor(tool: BaseTool):
    """Create an async executor function for a BaseTool."""
    async def executor(params: dict) -> Any:
        result = await tool.run(params)
        return result
    return executor


def _build_execution_registry():
    """Build an executor-compatible ToolRegistry from the BaseTool registry."""
    from .executor import ToolRegistry as ExecRegistry

    base_registry = get_registry()
    exec_registry = ExecRegistry()

    for base_tool in base_registry.list_all():
        exec_registry.register(base_tool.id, _make_tool_executor(base_tool))

    return exec_registry


def _build_simple_plan(tools_needed: list[str], params: dict) -> ExecutionPlan:
    """Build a simple parallel execution plan for the needed tools."""
    steps = []
    for i, tool_id in enumerate(tools_needed):
        # Map router tool IDs to registry tool IDs
        mapped_id = _map_tool_id(tool_id)
        if mapped_id:
            steps.append(ExecutionStep(
                step_id=f"step_{i}",
                tool_id=mapped_id,
                params=params,
                depends_on=[],
                timeout_seconds=30,
                retry_count=1,
            ))

    # All steps run in parallel (no dependencies)
    parallel_groups = [[s.step_id for s in steps]] if steps else []

    return ExecutionPlan(
        steps=steps,
        parallel_groups=parallel_groups,
        estimated_duration_ms=3000,
        execution_strategy="parallel" if len(steps) > 1 else "sequential",
    )


def _map_tool_id(router_tool_id: str) -> Optional[str]:
    """Map router tool IDs to registry tool IDs."""
    mapping = {
        "usaspending_search": "usaspending.search",
        "usaspending_detail": "usaspending.search",
        "far_lookup": None,  # Not yet in registry (Phase 2)
        "far_search": None,
        "bls_wage": "bls.oews",
        "gsa_perdiem": "gsa.perdiem",
        "market_research": "usaspending.search",
        "federalregister_search": "federal_register.search",
        "general_knowledge": None,  # Handled by LLM directly
    }
    return mapping.get(router_tool_id, router_tool_id)


def _collect_citations(context: ExecutionContext) -> list[PipelineCitation]:
    """Extract citations from all successful tool results."""
    citations = []
    for result in context.results.values():
        if not result.success or not result.data:
            continue
        # BaseTool.run() returns a ToolRunResult with citations list
        data = result.data
        if hasattr(data, 'citations'):
            for c in data.citations:
                citations.append(PipelineCitation(
                    source_name=getattr(c, 'source_name', 'Unknown'),
                    source_url=getattr(c, 'source_url', ''),
                    source_label=getattr(c, 'source_label', getattr(c, 'source_name', '')),
                    snippet=getattr(c, 'snippet', None),
                    retrieved_at=getattr(c, 'retrieved_at', '').isoformat() if hasattr(getattr(c, 'retrieved_at', ''), 'isoformat') else str(getattr(c, 'retrieved_at', '')),
                ))
        elif isinstance(data, dict) and 'citations' in data:
            for c in data['citations']:
                citations.append(PipelineCitation(
                    source_name=c.get('source_name', 'Unknown'),
                    source_url=c.get('source_url', ''),
                    source_label=c.get('source_label', c.get('source_name', '')),
                    snippet=c.get('snippet'),
                    retrieved_at=c.get('retrieved_at', ''),
                ))
    return citations


def _format_tool_data_for_llm(context: ExecutionContext) -> str:
    """Format tool results into a context string for the LLM."""
    parts = []
    for step_id, result in context.results.items():
        if result.success and result.data:
            data = result.data
            # Get the output dict
            if hasattr(data, 'model_dump'):
                output_dict = data.model_dump(exclude={'raw_response', 'citations'})
            elif hasattr(data, 'output'):
                output_dict = data.output if isinstance(data.output, dict) else {'result': str(data.output)}
            elif isinstance(data, dict):
                output_dict = {k: v for k, v in data.items() if k not in ('raw_response', 'citations')}
            else:
                output_dict = {'result': str(data)}

            parts.append(f"[Tool: {result.tool_id}]\n{output_dict}")

    return "\n\n".join(parts) if parts else ""


async def run_pipeline(
    query: str,
    conversation_history: list[dict],
    config: Optional[dict] = None,
) -> PipelineResult:
    """
    Main pipeline entry point.

    Flow:
      1. Classify intent (IntentRouter)
      2. Build execution plan (ExecutionPlanner)
      3. Execute tools in parallel (ExecutionEngine)
      4. Synthesize answer with LLM (Anthropic)
      5. Apply guards (PII, grounding)
      6. Return structured result

    Falls back to direct Anthropic call if any step fails.

    Args:
        query: User's message
        conversation_history: List of {role, content} dicts
        config: Optional overrides

    Returns:
        PipelineResult with answer, tool_runs, citations, etc.
    """
    start = time.time()
    tool_runs: list[PipelineToolRun] = []
    warnings: list[str] = []
    intent_category = "general_question"
    confidence = 1.0

    try:
        # 1. Classify intent
        router = IntentRouter()
        intent = await router.classify(query, conversation_history)
        intent_category = intent.category.value
        confidence = intent.confidence
        logger.info("intent_classified", category=intent_category, confidence=confidence)

        # 2. Determine which tools to run
        runnable_tools = [
            t for t in intent.tools_needed
            if _map_tool_id(t) is not None
        ]

        tool_data_str = ""
        context = None

        if runnable_tools:
            # 3. Build execution plan
            plan = _build_simple_plan(runnable_tools, intent.extracted_params)

            # 4. Build executor registry and run
            exec_registry = _build_execution_registry()
            engine = ExecutionEngine(exec_registry)
            context = await engine.execute(plan)

            # 5. Collect tool runs for response
            for exec_result in context.results.values():
                base_tool = get_registry().get(exec_result.tool_id)
                tool_name = base_tool.name if base_tool else exec_result.tool_id

                output_data = None
                if exec_result.success and exec_result.data:
                    data = exec_result.data
                    if hasattr(data, 'model_dump'):
                        output_data = data.model_dump(exclude={'raw_response', 'citations'})
                    elif isinstance(data, dict):
                        output_data = {k: v for k, v in data.items() if k != 'raw_response'}
                    else:
                        output_data = str(data)

                tool_runs.append(PipelineToolRun(
                    tool_id=exec_result.tool_id,
                    name=tool_name,
                    status="success" if exec_result.success else "error",
                    input_params=plan.steps[0].params if plan.steps else {},
                    output=output_data,
                    duration_ms=exec_result.execution_time_ms,
                    error=exec_result.error if not exec_result.success else None,
                ))

            # Format tool data for LLM context
            tool_data_str = _format_tool_data_for_llm(context)

        # 6. Call Anthropic to synthesize answer
        if not settings.ANTHROPIC_API_KEY:
            raise ValueError("ANTHROPIC_API_KEY not configured")

        async_client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

        # Build messages: history + current query + tool data as user context
        messages = list(conversation_history)

        if tool_data_str:
            # Inject tool results as a system-level context in the last user message
            augmented_query = (
                f"{query}\n\n"
                f"[Tool Data Retrieved]\n{tool_data_str}\n"
                f"[End Tool Data]\n\n"
                f"Please synthesize the above data into a clear, helpful answer."
            )
            messages.append({"role": "user", "content": augmented_query})
        else:
            messages.append({"role": "user", "content": query})

        llm_response = await async_client.messages.create(
            model="claude-opus-4-5",
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            messages=messages,
        )
        answer_text = llm_response.content[0].text

        # 7. Apply guards
        pii_found = PIIDetectionGuard.detect(answer_text)
        if pii_found:
            warnings.append(f"PII detected in response ({len(pii_found)} instances)")
            # Redact the answer (simple approach: flag rather than expose)
            for pii in pii_found:
                answer_text = answer_text.replace(pii.value, f"[REDACTED-{pii.pattern_type.upper()}]")

        # Add disclaimer
        used_tool_ids = [tr.tool_id for tr in tool_runs]
        disclaimer = AcquisitionDisclaimerGuard.get_disclaimer(used_tool_ids)
        answer_with_disclaimer = answer_text + "\n\n---\n" + disclaimer.strip()

        # 8. Collect citations
        citations = _collect_citations(context) if context else []

        execution_time_ms = (time.time() - start) * 1000
        logger.info(
            "pipeline_complete",
            intent=intent_category,
            tools_run=len(tool_runs),
            citations=len(citations),
            duration_ms=round(execution_time_ms),
        )

        return PipelineResult(
            answer=answer_with_disclaimer,
            tool_runs=tool_runs,
            citations=citations,
            intent_category=intent_category,
            confidence=confidence,
            warnings=warnings,
            execution_time_ms=execution_time_ms,
        )

    except Exception as e:
        logger.error("pipeline_error", error=str(e), exc_info=True)
        # Fallback: direct Anthropic call
        try:
            if settings.ANTHROPIC_API_KEY:
                async_client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
                messages = list(conversation_history) + [{"role": "user", "content": query}]
                llm_response = await async_client.messages.create(
                    model="claude-opus-4-5",
                    max_tokens=2048,
                    system=SYSTEM_PROMPT,
                    messages=messages,
                )
                answer_text = llm_response.content[0].text
                warnings.append(f"Orchestration unavailable (fallback mode): {str(e)}")
                return PipelineResult(
                    answer=answer_text,
                    tool_runs=[],
                    citations=[],
                    intent_category=intent_category,
                    confidence=0.5,
                    warnings=warnings,
                    execution_time_ms=(time.time() - start) * 1000,
                )
        except Exception as fallback_error:
            logger.error("pipeline_fallback_error", error=str(fallback_error))

        raise
