"""Execution engine for orchestrated tool calls.

This module executes plans, respects dependencies, handles parallelization,
collects results, and manages errors gracefully.
"""

import asyncio
import time
from typing import Any, Callable, Optional
from pydantic import BaseModel
from dataclasses import dataclass

from .planner import ExecutionPlan, ExecutionStep


@dataclass
class ToolRunResult:
    """Result from a single tool execution."""
    step_id: str
    tool_id: str
    success: bool
    data: Any = None
    error: str = None
    execution_time_ms: float = 0.0
    start_time: float = None
    end_time: float = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "step_id": self.step_id,
            "tool_id": self.tool_id,
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "execution_time_ms": self.execution_time_ms,
        }


class ExecutionContext:
    """Context during execution: tracks results and state."""
    
    def __init__(self):
        """Initialize execution context."""
        self.results: dict[str, ToolRunResult] = {}
        self.start_time = time.time()
        self.errors: list[tuple[str, str]] = []
    
    def add_result(self, result: ToolRunResult) -> None:
        """Add a tool result.
        
        Args:
            result: ToolRunResult from execution
        """
        self.results[result.step_id] = result
        if not result.success:
            self.errors.append((result.step_id, result.error))
    
    def get_result(self, step_id: str) -> Optional[ToolRunResult]:
        """Get result for a step.
        
        Args:
            step_id: Step identifier
            
        Returns:
            ToolRunResult or None if not executed
        """
        return self.results.get(step_id)
    
    def get_step_data(self, step_id: str) -> Any:
        """Get data from a step result.
        
        Args:
            step_id: Step identifier
            
        Returns:
            Data or None
        """
        result = self.results.get(step_id)
        return result.data if result else None
    
    def all_successful(self) -> bool:
        """Check if all executed steps were successful.
        
        Returns:
            True if no errors
        """
        return len(self.errors) == 0
    
    def get_duration_ms(self) -> float:
        """Get total execution time in milliseconds.
        
        Returns:
            Milliseconds elapsed since context creation
        """
        return (time.time() - self.start_time) * 1000


class ToolRegistry:
    """Registry of available tools."""
    
    def __init__(self):
        """Initialize tool registry."""
        self.tools: dict[str, Callable] = {}
    
    def register(self, tool_id: str, handler: Callable) -> None:
        """Register a tool handler.
        
        Args:
            tool_id: Tool identifier
            handler: Async callable(params: dict) -> Any
        """
        self.tools[tool_id] = handler
    
    def get(self, tool_id: str) -> Optional[Callable]:
        """Get tool handler.
        
        Args:
            tool_id: Tool identifier
            
        Returns:
            Handler callable or None
        """
        return self.tools.get(tool_id)
    
    def has(self, tool_id: str) -> bool:
        """Check if tool exists.
        
        Args:
            tool_id: Tool identifier
            
        Returns:
            True if tool is registered
        """
        return tool_id in self.tools


class ExecutionEngine:
    """Executes orchestration plans using tool handlers.
    
    Features:
    - Respects dependencies between steps
    - Parallelizes independent steps
    - Handles timeouts and retries
    - Collects and tracks all results
    - Provides graceful error handling
    """
    
    def __init__(self, tool_registry: ToolRegistry):
        """Initialize execution engine.
        
        Args:
            tool_registry: ToolRegistry with registered handlers
        """
        self.tool_registry = tool_registry

    async def execute(
        self,
        plan: ExecutionPlan,
        on_step_complete: Optional[Callable[[ToolRunResult], None]] = None,
        continue_on_error: bool = True
    ) -> ExecutionContext:
        """Execute a plan.
        
        Args:
            plan: ExecutionPlan from planner
            on_step_complete: Optional callback when step completes
            continue_on_error: If True, continue executing other steps on failure
            
        Returns:
            ExecutionContext with all results
        """
        context = ExecutionContext()
        
        # Execute in parallel groups
        for group in plan.parallel_groups:
            # Build tasks for this group
            tasks = []
            for step_id in group:
                step = next((s for s in plan.steps if s.step_id == step_id), None)
                if not step:
                    continue
                
                # Check if dependencies are met
                if step.depends_on:
                    all_deps_met = all(
                        dep_id in context.results and context.results[dep_id].success
                        for dep_id in step.depends_on
                    )
                    if not all_deps_met:
                        # Skip this step or mark as failed
                        if not continue_on_error:
                            result = ToolRunResult(
                                step_id=step.step_id,
                                tool_id=step.tool_id,
                                success=False,
                                error="Dependency failed"
                            )
                            context.add_result(result)
                        continue
                
                # Create task
                task = self._execute_step(
                    step, context, on_step_complete, continue_on_error
                )
                tasks.append(task)
            
            # Execute all tasks in group concurrently
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=False)
        
        return context

    async def _execute_step(
        self,
        step: ExecutionStep,
        context: ExecutionContext,
        on_step_complete: Optional[Callable] = None,
        continue_on_error: bool = True
    ) -> None:
        """Execute a single step with retries.
        
        Args:
            step: ExecutionStep to run
            context: ExecutionContext
            on_step_complete: Optional callback
            continue_on_error: Whether to continue on failure
        """
        result = None
        last_error = None
        
        for attempt in range(step.retry_count + 1):
            try:
                result = await self._run_tool(step, context)
                
                if result.success:
                    break
                
                last_error = result.error
                if attempt < step.retry_count:
                    # Exponential backoff
                    await asyncio.sleep(0.5 * (2 ** attempt))
            
            except Exception as e:
                last_error = str(e)
                if attempt < step.retry_count:
                    await asyncio.sleep(0.5 * (2 ** attempt))
        
        # Ensure we have a result
        if result is None:
            result = ToolRunResult(
                step_id=step.step_id,
                tool_id=step.tool_id,
                success=False,
                error=last_error or "Unknown error"
            )
        
        context.add_result(result)
        
        if on_step_complete:
            on_step_complete(result)

    async def _run_tool(
        self,
        step: ExecutionStep,
        context: ExecutionContext
    ) -> ToolRunResult:
        """Run a single tool with timeout.
        
        Args:
            step: ExecutionStep to run
            context: ExecutionContext (for dependency resolution)
            
        Returns:
            ToolRunResult
        """
        start_time = time.time()
        
        # Get tool handler
        handler = self.tool_registry.get(step.tool_id)
        if not handler:
            return ToolRunResult(
                step_id=step.step_id,
                tool_id=step.tool_id,
                success=False,
                error=f"Tool not found: {step.tool_id}",
                start_time=start_time,
                end_time=time.time()
            )
        
        # Prepare parameters: inject dependency results
        params = step.params.copy()
        for key, value in params.items():
            if isinstance(value, str) and value.startswith("$"):
                # Reference to another step's result
                ref_step_id = value[1:]
                ref_result = context.get_result(ref_step_id)
                if ref_result:
                    params[key] = ref_result.data
        
        # Execute with timeout
        try:
            data = await asyncio.wait_for(
                handler(params),
                timeout=step.timeout_seconds
            )
            
            end_time = time.time()
            return ToolRunResult(
                step_id=step.step_id,
                tool_id=step.tool_id,
                success=True,
                data=data,
                execution_time_ms=(end_time - start_time) * 1000,
                start_time=start_time,
                end_time=end_time
            )
        
        except asyncio.TimeoutError:
            end_time = time.time()
            return ToolRunResult(
                step_id=step.step_id,
                tool_id=step.tool_id,
                success=False,
                error=f"Timeout after {step.timeout_seconds}s",
                execution_time_ms=(end_time - start_time) * 1000,
                start_time=start_time,
                end_time=end_time
            )
        
        except Exception as e:
            end_time = time.time()
            return ToolRunResult(
                step_id=step.step_id,
                tool_id=step.tool_id,
                success=False,
                error=f"{type(e).__name__}: {str(e)}",
                execution_time_ms=(end_time - start_time) * 1000,
                start_time=start_time,
                end_time=end_time
            )
