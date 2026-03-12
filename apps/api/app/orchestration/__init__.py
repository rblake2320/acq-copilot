"""Acquisition Copilot orchestration layer.

This module handles intent classification, tool routing, execution planning,
result synthesis, and guardrails for the acquisition copilot API.
"""

from .pipeline import run_pipeline, PipelineResult, PipelineToolRun, PipelineCitation
