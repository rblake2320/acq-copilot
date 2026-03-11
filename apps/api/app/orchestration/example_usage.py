"""
Example usage of the orchestration layer.

This demonstrates the complete flow from query to answer.
"""

import asyncio
from typing import Optional

# Import orchestration components
from router import IntentRouter, IntentCategory
from planner import ExecutionPlanner
from executor import ExecutionEngine, ToolRegistry, ToolRunResult
from answer_synthesizer import AnswerSynthesizer
from citations import CitationAggregator
from guards import (
    SourceGroundingGuard,
    PIIDetectionGuard,
    AcquisitionDisclaimerGuard
)
from providers import get_provider


async def example_basic_spending_query():
    """Example: Simple spending search query."""
    print("\n" + "="*60)
    print("EXAMPLE 1: Basic Spending Search")
    print("="*60)
    
    # Initialize components
    llm_provider = get_provider("anthropic", api_key="your-key-here")
    router = IntentRouter(llm_provider)
    
    # Classify intent
    query = "What contracts did Microsoft win in NAICS 5112?"
    print(f"\nQuery: {query}")
    
    intent = await router.classify(query)
    print(f"Classified as: {intent.category.value}")
    print(f"Confidence: {intent.confidence:.1%}")
    print(f"Tools needed: {intent.tools_needed}")
    print(f"Extracted params: {intent.extracted_params}")


async def example_regulation_lookup():
    """Example: Regulation lookup with keyword matching."""
    print("\n" + "="*60)
    print("EXAMPLE 2: Regulation Lookup (High Confidence)")
    print("="*60)
    
    router = IntentRouter()  # No LLM needed for this
    
    query = "What does FAR 15.404 require for cost analysis?"
    print(f"\nQuery: {query}")
    
    intent = await router.classify(query)
    print(f"Classified as: {intent.category.value}")
    print(f"Confidence: {intent.confidence:.1%}")
    print(f"Tools needed: {intent.tools_needed}")
    print(f"Extracted params: {intent.extracted_params}")
    print(f"Reasoning: {intent.reasoning}")


async def example_igce_build():
    """Example: Complex IGCE build with dependencies."""
    print("\n" + "="*60)
    print("EXAMPLE 3: IGCE Build (Multi-step with Dependencies)")
    print("="*60)
    
    router = IntentRouter()
    planner = ExecutionPlanner()
    
    query = "Build an IGCE for 3 software developers in Washington DC for 6 months"
    print(f"\nQuery: {query}")
    
    intent = await router.classify(query)
    print(f"\nClassified as: {intent.category.value}")
    print(f"Tools needed: {intent.tools_needed}")
    
    plan = await planner.plan(intent)
    print(f"\nExecution Plan:")
    print(f"  Total steps: {len(plan.steps)}")
    print(f"  Execution strategy: {plan.execution_strategy}")
    print(f"  Estimated duration: {plan.estimated_duration_ms}ms")
    print(f"  Parallel groups: {plan.parallel_groups}")
    
    for step in plan.steps:
        deps_str = f" (depends on: {step.depends_on})" if step.depends_on else ""
        print(f"  - {step.step_id}: {step.tool_id}{deps_str}")


async def example_multi_tool_query():
    """Example: Multi-tool query with parallelization."""
    print("\n" + "="*60)
    print("EXAMPLE 4: Multi-tool Query (Parallel Execution)")
    print("="*60)
    
    router = IntentRouter()
    planner = ExecutionPlanner()
    
    query = "Compare FAR 15.404 with FAR 16.401 for cost requirements"
    print(f"\nQuery: {query}")
    
    intent = await router.classify(query)
    print(f"\nClassified as: {intent.category.value}")
    print(f"Tools needed: {intent.tools_needed}")
    
    plan = await planner.plan(intent)
    print(f"\nExecution Plan (Parallelized):")
    print(f"  Total steps: {len(plan.steps)}")
    print(f"  Strategy: {plan.execution_strategy}")
    
    for i, group in enumerate(plan.parallel_groups):
        print(f"\n  Parallel group {i}:")
        for step_id in group:
            step = next(s for s in plan.steps if s.step_id == step_id)
            print(f"    - {step.tool_id} ({step_id})")


async def example_citations():
    """Example: Citation management."""
    print("\n" + "="*60)
    print("EXAMPLE 5: Citation Aggregation")
    print("="*60)
    
    # Create some mock results
    results = [
        ToolRunResult(
            step_id="step_0",
            tool_id="usaspending_search",
            success=True,
            data={"contracts": 5, "source_url": "https://usaspending.gov"},
            execution_time_ms=2000
        ),
        ToolRunResult(
            step_id="step_1",
            tool_id="bls_wage",
            success=True,
            data={"rate": 150000, "source_url": "https://bls.gov/oes"},
            execution_time_ms=1500
        ),
    ]
    
    aggregator = CitationAggregator()
    for result in results:
        ref = aggregator.add_from_result(result, access_date="2024-03-10")
        print(f"Added citation for {result.tool_id}: reference #{ref}")
    
    print("\nFormatted Bibliography:")
    for citation_text in aggregator.get_formatted(style="plain"):
        print(f"  {citation_text}")


async def example_guardrails():
    """Example: Guardrail checks."""
    print("\n" + "="*60)
    print("EXAMPLE 6: Guardrails & Quality Checks")
    print("="*60)
    
    answer_text = """Based on USAspending data, Microsoft received $5,234,000 in contracts 
    in NAICS 5112 during 2023. The FAR requires cost analysis for contracts over $1,000,000.
    Contact John Smith at 555-123-4567 for more information."""
    
    print(f"\nAnswer text:\n{answer_text}")
    
    # PII Detection
    print("\nRunning PII Detection...")
    pii = PIIDetectionGuard.detect(answer_text)
    if pii:
        for detection in pii:
            print(f"  ⚠ Detected {detection.pattern_type}: {detection.value}")
    else:
        print("  ✓ No PII detected")
    
    # Get disclaimer
    print("\nGenerating Disclaimers...")
    tool_ids = ["usaspending_search", "far_lookup"]
    disclaimer = AcquisitionDisclaimerGuard.get_disclaimer(tool_ids)
    print(f"Disclaimer: {disclaimer[:200]}...")


async def example_parameter_extraction():
    """Example: Automatic parameter extraction from queries."""
    print("\n" + "="*60)
    print("EXAMPLE 7: Parameter Extraction")
    print("="*60)
    
    router = IntentRouter()
    
    test_queries = [
        "NAICS 5112 contracts worth between $100,000 and $500,000",
        "Per diem rates in New York, NY",
        "FAR 15.404-1(a)(1) and FAR 15.404-1(b)",
    ]
    
    for query in test_queries:
        print(f"\nQuery: {query}")
        intent = await router.classify(query)
        if intent.extracted_params:
            for key, value in intent.extracted_params.items():
                print(f"  {key}: {value}")
        else:
            print("  (no parameters extracted)")


async def main():
    """Run all examples."""
    print("\n")
    print("█" * 60)
    print("█  ORCHESTRATION LAYER EXAMPLES")
    print("█" * 60)
    
    try:
        await example_regulation_lookup()
        await example_basic_spending_query()
        await example_igce_build()
        await example_multi_tool_query()
        await example_citations()
        await example_guardrails()
        await example_parameter_extraction()
        
        print("\n" + "="*60)
        print("All examples completed successfully!")
        print("="*60 + "\n")
    
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # Note: Some examples require API keys
    # For production use, ensure ANTHROPIC_API_KEY is set
    asyncio.run(main())
