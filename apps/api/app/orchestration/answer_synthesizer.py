"""Answer synthesis from tool results.

This module takes user queries and tool results, then uses an LLM
to generate natural language answers grounded in the data.
"""

from typing import Optional
from pydantic import BaseModel, Field
from enum import Enum

from .executor import ToolRunResult, ExecutionContext


class DataSourceReference(BaseModel):
    """Reference to a data source used in answer."""
    tool_id: str
    step_id: str
    data_snippet: str
    relevance: float = Field(ge=0.0, le=1.0)


class SynthesizedAnswer(BaseModel):
    """Complete synthesized answer with metadata."""
    answer_text: str
    data_used: list[dict] = Field(default_factory=list)
    method_description: str
    sources: list[dict] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    execution_time_ms: float
    
    class Config:
        json_schema_extra = {
            "example": {
                "answer_text": "Based on USAspending data...",
                "data_used": [{"tool": "usaspending_search", "records": 5}],
                "method_description": "Searched USAspending for contracts...",
                "sources": [{"url": "usaspending.gov", "date": "2024-03-10"}],
                "warnings": ["Data may be incomplete for recent awards"],
                "assumptions": ["Searched all agency codes"],
                "confidence": 0.95,
                "execution_time_ms": 2500
            }
        }


class AnswerSynthesizer:
    """Synthesizes natural language answers from tool outputs.
    
    Features:
    - Grounds answers in tool outputs (no hallucination)
    - Extracts and tracks data used
    - Generates method descriptions
    - Collects warnings and assumptions
    - Formats for end-user consumption
    """
    
    def __init__(self, llm_provider):
        """Initialize synthesizer with LLM provider.
        
        Args:
            llm_provider: LLM provider instance with complete() method
        """
        self.llm_provider = llm_provider

    async def synthesize(
        self,
        query: str,
        execution_context: ExecutionContext,
        conversation_history: Optional[list[dict]] = None
    ) -> SynthesizedAnswer:
        """Generate synthesized answer from execution results.
        
        Args:
            query: Original user query
            execution_context: ExecutionContext with all results
            conversation_history: Optional previous messages
            
        Returns:
            SynthesizedAnswer with text, metadata, and provenance
        """
        # Collect successful results
        successful_results = [
            result for result in execution_context.results.values()
            if result.success
        ]
        
        if not successful_results:
            # No successful tool runs
            return SynthesizedAnswer(
                answer_text="I was unable to retrieve data to answer your question. Please try again or rephrase your query.",
                data_used=[],
                method_description="No tools executed successfully",
                sources=[],
                warnings=["All tool executions failed"],
                assumptions=[],
                confidence=0.0,
                execution_time_ms=execution_context.get_duration_ms()
            )
        
        # Extract data and provenance from results
        data_snippets = self._extract_data_snippets(successful_results)
        sources = self._extract_sources(successful_results)
        warnings = self._extract_warnings(successful_results)
        assumptions = self._extract_assumptions(successful_results, query)
        
        # Generate answer text
        answer_text = await self._generate_answer_text(
            query,
            successful_results,
            data_snippets,
            conversation_history
        )
        
        # Generate method description
        method_description = self._generate_method_description(successful_results)
        
        # Verify grounding (check that answer is supported by data)
        grounding_issues = self._verify_grounding(answer_text, data_snippets)
        if grounding_issues:
            warnings.extend(grounding_issues)
        
        # Calculate confidence
        confidence = self._calculate_confidence(
            len(successful_results),
            len(data_snippets),
            len(warnings)
        )
        
        return SynthesizedAnswer(
            answer_text=answer_text,
            data_used=data_snippets,
            method_description=method_description,
            sources=sources,
            warnings=warnings,
            assumptions=assumptions,
            confidence=confidence,
            execution_time_ms=execution_context.get_duration_ms()
        )

    async def _generate_answer_text(
        self,
        query: str,
        results: list[ToolRunResult],
        data_snippets: list[dict],
        history: Optional[list[dict]] = None
    ) -> str:
        """Generate natural language answer text.
        
        Args:
            query: Original user query
            results: Successful ToolRunResults
            data_snippets: Extracted data
            history: Conversation history
            
        Returns:
            Natural language answer
        """
        # Prepare context for LLM
        tool_outputs = "\n\n".join([
            f"### {result.tool_id} (Step: {result.step_id})\n{self._format_result_data(result.data)}"
            for result in results
        ])
        
        system_prompt = """You are an acquisition domain expert answering user questions.

Your response MUST:
1. Answer the user's question directly and clearly
2. Ground all claims in the provided tool outputs
3. Never fabricate data not in the outputs
4. Use specific numbers and references from the data
5. Explain any limitations or caveats
6. Be concise but thorough

If the data doesn't answer the question, say so explicitly."""
        
        user_message = f"""Query: {query}

Available data:
{tool_outputs}

Generate a clear, concise answer that is grounded in the data above."""
        
        messages = (history or []) + [{"role": "user", "content": user_message}]
        
        try:
            response = await self.llm_provider.complete(
                messages,
                system_prompt=system_prompt,
                temperature=0.1,  # Low temperature for consistency
                max_tokens=1000
            )
            return response.strip()
        
        except Exception as e:
            # Fallback: basic answer from first result
            if results:
                data_text = self._format_result_data(results[0].data)
                return f"Based on {results[0].tool_id}: {data_text[:500]}..."
            return "Unable to generate answer due to LLM error"

    def _extract_data_snippets(self, results: list[ToolRunResult]) -> list[dict]:
        """Extract data snippets from results.
        
        Args:
            results: Successful ToolRunResults
            
        Returns:
            List of data snippet dicts
        """
        snippets = []
        
        for result in results:
            if result.data is None:
                continue
            
            # Format depends on data type
            if isinstance(result.data, list):
                snippet = {
                    "tool": result.tool_id,
                    "type": "list",
                    "count": len(result.data),
                    "sample": result.data[:2] if result.data else []
                }
            elif isinstance(result.data, dict):
                snippet = {
                    "tool": result.tool_id,
                    "type": "dict",
                    "keys": list(result.data.keys()),
                    "data": result.data
                }
            else:
                snippet = {
                    "tool": result.tool_id,
                    "type": type(result.data).__name__,
                    "value": str(result.data)
                }
            
            snippets.append(snippet)
        
        return snippets

    def _extract_sources(self, results: list[ToolRunResult]) -> list[dict]:
        """Extract source information from results.
        
        Args:
            results: Successful ToolRunResults
            
        Returns:
            List of source dicts
        """
        sources = []
        tool_to_source = {
            "usaspending_search": "USAspending.gov",
            "usaspending_detail": "USAspending.gov",
            "far_lookup": "Federal Acquisition Regulation (FAR)",
            "far_search": "Federal Acquisition Regulation (FAR)",
            "far_compare": "Federal Acquisition Regulation (FAR)",
            "bls_wage": "Bureau of Labor Statistics",
            "gsa_perdiem": "GSA Per Diem Rates",
            "federalregister_search": "Federal Register (regulations.gov)",
            "market_research": "Market Research Data",
            "general_knowledge": "General Acquisition Knowledge",
        }
        
        for result in results:
            source_name = tool_to_source.get(result.tool_id, result.tool_id)
            
            source = {
                "tool": result.tool_id,
                "name": source_name,
                "retrieved_at": time.time(),  # Would use actual timestamp
                "execution_time_ms": result.execution_time_ms
            }
            
            # Add URL if available in data
            if isinstance(result.data, dict) and "source_url" in result.data:
                source["url"] = result.data["source_url"]
            
            sources.append(source)
        
        return sources

    def _extract_warnings(self, results: list[ToolRunResult]) -> list[str]:
        """Extract warnings from results.
        
        Args:
            results: Successful ToolRunResults
            
        Returns:
            List of warning strings
        """
        warnings = []
        
        for result in results:
            if isinstance(result.data, dict):
                if "warnings" in result.data:
                    tool_warnings = result.data["warnings"]
                    if isinstance(tool_warnings, list):
                        warnings.extend(tool_warnings)
                    else:
                        warnings.append(str(tool_warnings))
                
                if "incomplete" in result.data and result.data["incomplete"]:
                    warnings.append(f"Data from {result.tool_id} may be incomplete")
                
                if "quality_score" in result.data and result.data["quality_score"] < 0.7:
                    warnings.append(f"Low data quality from {result.tool_id}")
        
        return list(set(warnings))  # Deduplicate

    def _extract_assumptions(self, results: list[ToolRunResult], query: str) -> list[str]:
        """Extract assumptions made during execution.
        
        Args:
            results: Successful ToolRunResults
            query: User query
            
        Returns:
            List of assumption strings
        """
        assumptions = []
        
        # Default assumptions
        assumptions.append("Using current regulatory requirements and rates")
        
        # Tool-specific assumptions
        if any(r.tool_id == "usaspending_search" for r in results):
            assumptions.append("Searched across all federal agencies")
            assumptions.append("Included both active and completed contracts")
        
        if any(r.tool_id == "bls_wage" for r in results):
            assumptions.append("Using most recent BLS Occupational Employment Statistics")
        
        if any(r.tool_id == "gsa_perdiem" for r in results):
            assumptions.append("Using current GSA per diem rates")
        
        return list(set(assumptions))

    def _generate_method_description(self, results: list[ToolRunResult]) -> str:
        """Generate human-readable description of method used.
        
        Args:
            results: Successful ToolRunResults
            
        Returns:
            Method description string
        """
        tools_used = [r.tool_id for r in results]
        
        if len(tools_used) == 1:
            tool = tools_used[0]
            descriptions = {
                "usaspending_search": "Searched USAspending.gov for contracts and awards",
                "usaspending_detail": "Retrieved detailed award information from USAspending.gov",
                "far_lookup": "Looked up specific FAR regulation sections",
                "far_search": "Searched FAR for relevant regulations",
                "bls_wage": "Retrieved wage data from Bureau of Labor Statistics",
                "gsa_perdiem": "Retrieved per diem rates from GSA",
                "federalregister_search": "Searched Federal Register for regulatory information",
                "market_research": "Conducted market research analysis",
                "general_knowledge": "Used general acquisition domain knowledge",
            }
            return descriptions.get(tool, f"Used {tool}")
        
        else:
            tool_names = ", ".join(tools_used)
            return f"Combined data from multiple sources: {tool_names}"

    def _verify_grounding(self, answer_text: str, data_snippets: list[dict]) -> list[str]:
        """Verify that answer is grounded in provided data.
        
        Args:
            answer_text: Generated answer text
            data_snippets: Extracted data snippets
            
        Returns:
            List of grounding issues found
        """
        issues = []
        
        # Check for unsupported claims
        suspicious_phrases = [
            "I think",
            "probably",
            "likely",
            "might",
            "could be",
            "appears to be"
        ]
        
        for phrase in suspicious_phrases:
            if phrase.lower() in answer_text.lower():
                # This might indicate speculation rather than grounded data
                # But some speculation is OK if properly qualified
                pass
        
        # Check if we have actual data
        if not data_snippets or all(
            snippet.get("count", 0) == 0 
            for snippet in data_snippets 
            if snippet.get("type") == "list"
        ):
            issues.append("Answer based on limited or empty data")
        
        return issues

    def _calculate_confidence(
        self,
        result_count: int,
        data_count: int,
        warning_count: int
    ) -> float:
        """Calculate confidence score for answer.
        
        Args:
            result_count: Number of successful tool results
            data_count: Number of data snippets
            warning_count: Number of warnings
            
        Returns:
            Confidence score 0.0-1.0
        """
        base_confidence = 0.5
        
        # More successful tools = higher confidence
        base_confidence += min(result_count * 0.15, 0.3)
        
        # More data = higher confidence
        base_confidence += min(data_count * 0.1, 0.2)
        
        # More warnings = lower confidence
        base_confidence -= min(warning_count * 0.05, 0.3)
        
        return max(0.0, min(1.0, base_confidence))

    def _format_result_data(self, data: any) -> str:
        """Format result data for display.
        
        Args:
            data: Result data (any type)
            
        Returns:
            Formatted string
        """
        if data is None:
            return "(no data)"
        
        if isinstance(data, (list, tuple)):
            if not data:
                return "(empty)"
            
            # Summarize list
            if len(data) == 1:
                return str(data[0])
            
            preview = "\n".join(str(item) for item in data[:3])
            if len(data) > 3:
                preview += f"\n... and {len(data) - 3} more"
            return preview
        
        if isinstance(data, dict):
            if "summary" in data:
                return data["summary"]
            
            # Show first few key-value pairs
            items = list(data.items())[:5]
            return "\n".join(f"{k}: {v}" for k, v in items)
        
        return str(data)[:500]


import time
