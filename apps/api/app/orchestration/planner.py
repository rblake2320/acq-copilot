"""Execution planning for classified intents.

This module takes a classified intent and creates an execution plan
that respects tool dependencies and parallelization opportunities.
"""

from typing import Optional
from pydantic import BaseModel, Field
from enum import Enum

from .router import IntentCategory, ClassifiedIntent


class ExecutionStep(BaseModel):
    """Single step in execution plan."""
    step_id: str
    tool_id: str
    params: dict
    depends_on: list[str] = Field(default_factory=list)
    timeout_seconds: int = 30
    retry_count: int = 2
    
    class Config:
        frozen = True


class ExecutionPlan(BaseModel):
    """Complete execution plan with dependencies and parallelization info."""
    steps: list[ExecutionStep]
    parallel_groups: list[list[str]] = Field(default_factory=list)
    estimated_duration_ms: int
    execution_strategy: str  # "sequential", "parallel", "mixed"
    
    class Config:
        frozen = True


class ExecutionPlanner:
    """Plans execution of tools based on classified intent.
    
    Handles:
    - Tool dependency resolution (e.g., IGCE needs BLS + Per Diem)
    - Parallel execution opportunities
    - Multi-tool queries
    - Parameter enrichment and validation
    """
    
    # Tool dependencies and characteristics
    TOOL_SPECS = {
        "usaspending_search": {
            "depends_on": [],
            "estimated_ms": 2000,
            "requires_params": ["query"],
        },
        "usaspending_detail": {
            "depends_on": [],
            "estimated_ms": 1500,
            "requires_params": ["award_id"],
        },
        "far_lookup": {
            "depends_on": [],
            "estimated_ms": 1000,
            "requires_params": ["section"],
        },
        "far_search": {
            "depends_on": [],
            "estimated_ms": 2000,
            "requires_params": ["query"],
        },
        "far_compare": {
            "depends_on": [],
            "estimated_ms": 2500,
            "requires_params": ["sections"],
        },
        "bls_wage": {
            "depends_on": [],
            "estimated_ms": 1500,
            "requires_params": ["occupation"],
        },
        "gsa_perdiem": {
            "depends_on": [],
            "estimated_ms": 1000,
            "requires_params": ["location"],
        },
        "federalregister_search": {
            "depends_on": [],
            "estimated_ms": 2000,
            "requires_params": ["query"],
        },
        "market_research": {
            "depends_on": [],
            "estimated_ms": 3000,
            "requires_params": ["query"],
        },
        "general_knowledge": {
            "depends_on": [],
            "estimated_ms": 500,
            "requires_params": [],
        },
    }

    def __init__(self, tool_registry: Optional[dict] = None):
        """Initialize planner with tool registry.
        
        Args:
            tool_registry: Dict of available tools and their specs
        """
        self.tool_registry = tool_registry or self.TOOL_SPECS

    async def plan(self, intent: ClassifiedIntent) -> ExecutionPlan:
        """Create execution plan from classified intent.
        
        Args:
            intent: ClassifiedIntent from router
            
        Returns:
            ExecutionPlan with ordered steps
        """
        steps = []
        step_id_counter = 0
        params_map = {}
        
        # Handle IGCE specially: needs BLS wages first, then per diem, then computation
        if intent.category == IntentCategory.IGCE_BUILD:
            return self._plan_igce_build(intent)
        
        # Handle regulation comparison: fetch all regulations first
        if intent.category == IntentCategory.REGULATION_COMPARE:
            return self._plan_regulation_compare(intent)
        
        # Handle multi-tool scenarios
        if intent.category == IntentCategory.MULTI_TOOL:
            return self._plan_multi_tool(intent)
        
        # Standard single/dual-tool cases
        for tool_id in intent.tools_needed:
            step_id = f"step_{step_id_counter}"
            
            # Merge tool-specific params with extracted params
            tool_params = intent.extracted_params.copy()
            
            # Validate required params exist
            tool_spec = self.tool_registry.get(tool_id, {})
            required = tool_spec.get("requires_params", [])
            for req_param in required:
                if req_param not in tool_params and req_param != "query":
                    # Try to extract from query or context
                    if req_param == "occupation" and "occupation" not in tool_params:
                        # Will be handled at runtime
                        pass
            
            steps.append(ExecutionStep(
                step_id=step_id,
                tool_id=tool_id,
                params=tool_params,
                depends_on=[],
                timeout_seconds=30,
                retry_count=2
            ))
            params_map[step_id] = tool_params
            step_id_counter += 1
        
        # Determine parallelization
        parallel_groups = self._determine_parallel_groups(steps)
        execution_strategy = self._determine_strategy(steps)
        total_ms = self._estimate_duration(steps)
        
        return ExecutionPlan(
            steps=steps,
            parallel_groups=parallel_groups,
            estimated_duration_ms=total_ms,
            execution_strategy=execution_strategy
        )

    def _plan_igce_build(self, intent: ClassifiedIntent) -> ExecutionPlan:
        """Plan IGCE build which needs wages + per diem data first.
        
        IGCE workflow:
        1. Get wage rates (parallel with per diem lookup)
        2. Get per diem rates
        3. Calculate IGCE using both
        """
        steps = []
        
        # Step 0: Get wage data
        wage_step = ExecutionStep(
            step_id="step_0_wage",
            tool_id="bls_wage",
            params=intent.extracted_params.copy(),
            depends_on=[],
            timeout_seconds=30,
            retry_count=2
        )
        steps.append(wage_step)
        
        # Step 1: Get per diem data (can run in parallel)
        perdiem_params = intent.extracted_params.copy()
        if "location" not in perdiem_params:
            # Try to extract from context
            perdiem_params["location"] = "Washington, DC"  # Default
        
        perdiem_step = ExecutionStep(
            step_id="step_1_perdiem",
            tool_id="gsa_perdiem",
            params=perdiem_params,
            depends_on=[],
            timeout_seconds=30,
            retry_count=2
        )
        steps.append(perdiem_step)
        
        # Step 2: IGCE calculation (depends on both)
        igce_params = intent.extracted_params.copy()
        igce_params["wage_result_ref"] = "step_0_wage"
        igce_params["perdiem_result_ref"] = "step_1_perdiem"
        
        igce_step = ExecutionStep(
            step_id="step_2_igce",
            tool_id="igce_calculator",
            params=igce_params,
            depends_on=["step_0_wage", "step_1_perdiem"],
            timeout_seconds=30,
            retry_count=1
        )
        steps.append(igce_step)
        
        return ExecutionPlan(
            steps=steps,
            parallel_groups=[["step_0_wage", "step_1_perdiem"], ["step_2_igce"]],
            estimated_duration_ms=4000,
            execution_strategy="mixed"
        )

    def _plan_regulation_compare(self, intent: ClassifiedIntent) -> ExecutionPlan:
        """Plan regulation comparison: fetch all regs in parallel.
        
        Args:
            intent: ClassifiedIntent
            
        Returns:
            ExecutionPlan with parallel regulation fetches
        """
        steps = []
        citations = intent.extracted_params.get("citations", [])
        
        parallel_group = []
        for idx, citation in enumerate(citations):
            step_id = f"step_{idx}_far"
            step = ExecutionStep(
                step_id=step_id,
                tool_id="far_lookup",
                params={"section": citation},
                depends_on=[],
                timeout_seconds=30,
                retry_count=2
            )
            steps.append(step)
            parallel_group.append(step_id)
        
        # Synthesis step depends on all fetches
        synthesis_params = intent.extracted_params.copy()
        synthesis_params["regulation_refs"] = parallel_group
        
        synthesis_step = ExecutionStep(
            step_id="step_compare",
            tool_id="far_compare",
            params=synthesis_params,
            depends_on=parallel_group,
            timeout_seconds=30,
            retry_count=1
        )
        steps.append(synthesis_step)
        
        return ExecutionPlan(
            steps=steps,
            parallel_groups=[parallel_group, ["step_compare"]],
            estimated_duration_ms=3500,
            execution_strategy="mixed"
        )

    def _plan_multi_tool(self, intent: ClassifiedIntent) -> ExecutionPlan:
        """Plan multi-tool query by analyzing dependencies.
        
        Args:
            intent: ClassifiedIntent for multi-tool scenario
            
        Returns:
            ExecutionPlan
        """
        # For now, execute all tools in parallel if no explicit dependencies
        steps = []
        
        for idx, tool_id in enumerate(intent.tools_needed):
            step = ExecutionStep(
                step_id=f"step_{idx}",
                tool_id=tool_id,
                params=intent.extracted_params.copy(),
                depends_on=[],
                timeout_seconds=30,
                retry_count=2
            )
            steps.append(step)
        
        parallel_groups = [[step.step_id for step in steps]]
        total_ms = max(
            self.tool_registry.get(step.tool_id, {}).get("estimated_ms", 1000)
            for step in steps
        )
        
        return ExecutionPlan(
            steps=steps,
            parallel_groups=parallel_groups,
            estimated_duration_ms=total_ms,
            execution_strategy="parallel"
        )

    def _determine_parallel_groups(self, steps: list[ExecutionStep]) -> list[list[str]]:
        """Determine which steps can run in parallel.
        
        Args:
            steps: List of execution steps
            
        Returns:
            List of parallel groups (each group is list of step IDs)
        """
        if len(steps) <= 1:
            return [[step.step_id for step in steps]]
        
        # Build dependency graph
        no_deps = [s.step_id for s in steps if not s.depends_on]
        
        if not no_deps:
            # All have dependencies, must be sequential
            return [[s.step_id] for s in steps]
        
        # First group: all steps with no dependencies
        groups = [no_deps]
        
        # Subsequent groups: steps whose dependencies are all in previous groups
        processed = set(no_deps)
        remaining = [s for s in steps if s.step_id not in processed]
        
        while remaining:
            next_group = []
            for step in remaining:
                if all(dep in processed for dep in step.depends_on):
                    next_group.append(step.step_id)
                    processed.add(step.step_id)
            
            if next_group:
                groups.append(next_group)
            else:
                # Circular dependency or missing dependency
                groups.append([step.step_id for step in remaining])
                break
            
            remaining = [s for s in remaining if s.step_id not in processed]
        
        return groups

    def _determine_strategy(self, steps: list[ExecutionStep]) -> str:
        """Determine execution strategy based on steps.
        
        Args:
            steps: List of execution steps
            
        Returns:
            Strategy: "sequential", "parallel", or "mixed"
        """
        has_dependencies = any(step.depends_on for step in steps)
        has_parallelizable = sum(1 for step in steps if not step.depends_on) > 1
        
        if not has_dependencies:
            return "parallel" if has_parallelizable else "sequential"
        
        if has_parallelizable:
            return "mixed"
        
        return "sequential"

    def _estimate_duration(self, steps: list[ExecutionStep]) -> int:
        """Estimate total execution duration in milliseconds.
        
        Args:
            steps: List of execution steps
            
        Returns:
            Estimated duration in milliseconds
        """
        # Conservative estimate: max single tool + 500ms overhead per step
        max_tool_ms = max(
            self.tool_registry.get(step.tool_id, {}).get("estimated_ms", 1000)
            for step in steps
        ) if steps else 0
        
        overhead_ms = 500 * len(steps)
        return max_tool_ms + overhead_ms
