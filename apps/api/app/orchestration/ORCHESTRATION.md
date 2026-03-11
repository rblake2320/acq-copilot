# Acquisition Copilot Orchestration Layer

## Overview

The orchestration layer is the intelligent core of Acquisition Copilot. It sits between the chat API and tool connectors, handling:

1. **Intent Classification** - Understanding what the user is asking
2. **Tool Routing** - Selecting which tools are needed
3. **Execution Planning** - Determining execution order and parallelization
4. **Result Synthesis** - Generating natural language answers from tool outputs
5. **Quality Guardrails** - Verifying grounding, detecting PII, enforcing disclaimers

## Architecture

```
User Query
    ↓
IntentRouter (classify intent)
    ↓
ExecutionPlanner (plan execution)
    ↓
ExecutionEngine (run tools in parallel)
    ↓
AnswerSynthesizer (generate answer)
    ↓
CitationAggregator (format citations)
    ↓
Guardrails (verify quality/compliance)
    ↓
Response to User
```

## Components

### 1. IntentRouter (router.py)

Classifies user queries into acquisition-specific intents:

- **SPENDING_SEARCH** - Search USAspending or contracts
- **AWARD_DETAIL** - Get detailed award information
- **REGULATION_LOOKUP** - Look up specific regulation sections
- **REGULATION_SEARCH** - Search regulations by topic
- **WAGE_LOOKUP** - Get wage/labor rates
- **PERDIEM_LOOKUP** - Get per diem rates
- **IGCE_BUILD** - Build cost estimates
- **MARKET_RESEARCH** - Market research queries
- **DOCKET_SEARCH** - Federal Register dockets
- **GENERAL_QUESTION** - General acquisition knowledge

**Features:**
- Keyword/pattern matching for high-confidence classification (>0.8)
- LLM-based classification fallback for ambiguous queries
- Automatic parameter extraction from query (NAICS codes, locations, citations, etc.)
- Confidence scoring

**Usage:**
```python
router = IntentRouter(llm_provider=claude_provider)
intent = await router.classify("What is the spending on software contracts in NAICS 5112?")
# Returns: IntentCategory.SPENDING_SEARCH with extracted_params={'naics_code': '5112'}
```

### 2. ExecutionPlanner (planner.py)

Creates execution plans respecting tool dependencies:

- **Dependency Resolution** - Handles inter-tool dependencies
- **Parallelization** - Groups independent steps for concurrent execution
- **Special Workflows** - IGCE needs wages + per diem before calculation
- **Multi-tool Queries** - Combines multiple tools intelligently

**Features:**
- Automatic parallel group detection
- Duration estimation based on tool specs
- Execution strategy determination (sequential/parallel/mixed)
- Timeout and retry configuration

**Usage:**
```python
planner = ExecutionPlanner()
plan = await planner.plan(intent)
# Returns ExecutionPlan with parallel groups and dependencies
```

### 3. ExecutionEngine (executor.py)

Executes plans with parallelization, retries, and error handling:

- **Parallel Execution** - Uses asyncio.gather for concurrent steps
- **Dependency Handling** - Skips steps with failed dependencies
- **Retry Logic** - Exponential backoff on failure
- **Timeout Management** - Configurable per-step timeouts
- **Error Resilience** - Continue on error option

**Features:**
- Tool registry pattern for registration
- Result tracking and context management
- Detailed execution metrics (timing, success/failure)
- Graceful degradation

**Usage:**
```python
engine = ExecutionEngine(tool_registry)
context = await engine.execute(plan, continue_on_error=True)
for step_id, result in context.results.items():
    print(f"{step_id}: {'✓' if result.success else '✗'}")
```

### 4. AnswerSynthesizer (answer_synthesizer.py)

Generates natural language answers from tool outputs:

- **Grounded Answers** - Only claims supported by tool outputs
- **Data Tracking** - Records which data was used
- **Method Description** - Explains how answer was derived
- **Source Attribution** - Links to original data sources
- **Warning Generation** - Flags limitations or caveats
- **Confidence Scoring** - Rates answer confidence

**Features:**
- LLM-based text generation with low temperature (0.1)
- Automatic data extraction and formatting
- Warning inference from tool outputs
- Assumption documentation

**Usage:**
```python
synthesizer = AnswerSynthesizer(llm_provider=claude_provider)
answer = await synthesizer.synthesize(
    "What is the spending on software contracts?",
    execution_context
)
print(answer.answer_text)
print(f"Confidence: {answer.confidence:.1%}")
```

### 5. CitationAggregator (citations.py)

Manages citations from tool outputs:

- **Deduplication** - Removes duplicate sources
- **Reference Numbering** - Assigns sequential numbers
- **Multiple Formats** - Plain text, Chicago style, HTML
- **Bibliography Generation** - Formats complete citations
- **Reference Embedding** - Inserts [1], [2] in text

**Features:**
- Tool-to-source mapping (FAR, BLS, GSA, etc.)
- URL extraction from tool results
- Access date tracking
- Flexible formatting

**Usage:**
```python
aggregator = CitationAggregator()
for result in execution_context.results.values():
    aggregator.add_from_result(result, access_date="2024-03-10")

bibliography = aggregator.format_bibliography(style="plain")
print(bibliography)
```

### 6. Guardrails (guards.py)

Quality assurance and compliance checks:

- **Source Grounding** - Verifies claims are in tool outputs
- **Calculation Verification** - Checks numerical accuracy
- **PII Detection** - Identifies sensitive information
- **Disclaimer Generation** - Adds appropriate warnings
- **Rate Limiting** - Enforces user rate limits

**Features:**
- Speculative claim detection
- Number extraction and verification
- SSN, email, phone, credit card detection
- Tool-specific disclaimer templates

**Usage:**
```python
# Check grounding
issues = SourceGroundingGuard.check(answer_text, tool_outputs)

# Check for PII
pii_detections = PIIDetectionGuard.detect(answer_text)

# Get disclaimer
disclaimer = AcquisitionDisclaimerGuard.get_disclaimer(tool_ids)
```

### 7. LLM Providers (providers.py)

Unified abstraction for LLM providers:

- **Anthropic Claude** - Primary provider (claude-opus-4-6)
- **OpenAI** - GPT-4 Turbo support
- **Azure OpenAI** - Enterprise Azure deployments

**Features:**
- Async/await interface
- Automatic retries with exponential backoff
- Timeout handling
- Structured output support (JSON schema)
- Error recovery and fallbacks

**Usage:**
```python
# Anthropic
provider = AnthropicProvider(api_key=os.getenv("ANTHROPIC_API_KEY"))

# OpenAI
provider = OpenAIProvider(api_key=os.getenv("OPENAI_API_KEY"))

# Azure OpenAI
provider = AzureOpenAIProvider(
    api_key=os.getenv("AZURE_API_KEY"),
    endpoint=os.getenv("AZURE_ENDPOINT"),
    deployment_id="my-deployment"
)

# Generic factory
provider = get_provider("anthropic", api_key)
```

## Complete Workflow Example

```python
from orchestration.router import IntentRouter
from orchestration.planner import ExecutionPlanner
from orchestration.executor import ExecutionEngine, ToolRegistry
from orchestration.answer_synthesizer import AnswerSynthesizer
from orchestration.citations import CitationAggregator
from orchestration.guards import SourceGroundingGuard, PIIDetectionGuard
from orchestration.providers import get_provider

# 1. Setup
llm_provider = get_provider("anthropic", api_key)
router = IntentRouter(llm_provider)
planner = ExecutionPlanner()
engine = ExecutionEngine(tool_registry)
synthesizer = AnswerSynthesizer(llm_provider)
citations = CitationAggregator()

# 2. Classify intent
query = "What is the total spending on IT services in NAICS 5412?"
intent = await router.classify(query)
print(f"Intent: {intent.category}")
print(f"Tools: {intent.tools_needed}")

# 3. Plan execution
plan = await planner.plan(intent)
print(f"Steps: {len(plan.steps)}")
print(f"Parallel groups: {plan.parallel_groups}")

# 4. Execute tools
context = await engine.execute(plan, continue_on_error=True)
print(f"Execution time: {context.get_duration_ms():.0f}ms")

# 5. Synthesize answer
answer = await synthesizer.synthesize(query, context)
print(f"Answer: {answer.answer_text}")
print(f"Confidence: {answer.confidence:.1%}")

# 6. Add citations
for result in context.results.values():
    if result.success:
        citations.add_from_result(result)

# 7. Run guardrails
grounding_issues = SourceGroundingGuard.check(answer.answer_text, answer.data_used)
pii_detections = PIIDetectionGuard.detect(answer.answer_text)

if grounding_issues:
    print(f"Warning: {len(grounding_issues)} grounding issues")
if pii_detections:
    print(f"Warning: {len(pii_detections)} PII detections")

# 8. Format response
response = {
    "answer": answer.answer_text,
    "confidence": answer.confidence,
    "citations": citations.get_formatted(style="plain"),
    "method": answer.method_description,
    "warnings": answer.warnings,
}
```

## Intent Classification Examples

### Spending Search
```
Query: "Show me contracts awarded to Microsoft in Texas"
→ SPENDING_SEARCH
→ tools_needed: ["usaspending_search"]
→ extracted_params: {'vendor_name': 'Microsoft'}
```

### Regulation Lookup
```
Query: "What does FAR 15.404 say about cost analysis?"
→ REGULATION_LOOKUP
→ tools_needed: ["far_lookup"]
→ extracted_params: {'citations': ['FAR 15.404']}
```

### IGCE Build (Multi-step)
```
Query: "Build an IGCE for 3 software engineers in Washington DC for 6 months"
→ IGCE_BUILD
→ tools_needed: ["bls_wage", "gsa_perdiem"]
→ Execution plan: Fetch wages in parallel with per diem, then calculate
```

### Multi-tool
```
Query: "Compare spending on NAICS 5412 with FAR requirements for IT services"
→ REGULATION_COMPARE
→ tools_needed: ["usaspending_search", "far_search"]
→ Execution plan: Run both in parallel
```

## Error Handling

The orchestration layer handles errors gracefully:

1. **Classification Failure** - Falls back to general knowledge
2. **Tool Not Found** - Marks step as failed, continues if allowed
3. **Timeout** - Retries with exponential backoff (up to 3 attempts)
4. **LLM Error** - Graceful degradation to fallback answer
5. **Partial Results** - Synthesizes from available data

Example:
```python
# Execute with error tolerance
context = await engine.execute(plan, continue_on_error=True)

# Synthesize from whatever succeeded
answer = await synthesizer.synthesize(query, context)
# Answer will note: "Some data sources were unavailable"
```

## Performance Characteristics

- **Small single-tool queries**: ~1-2 seconds
- **Medium multi-tool queries**: ~2-4 seconds  
- **Large IGCE builds**: ~4-6 seconds
- **Parallel execution**: Typically 30-50% faster than sequential

Example timings:
```
Query: "What is spending on NAICS 5412?"
┌─ Step 0: usaspending_search → 2000ms
└─ Total execution: 2500ms (with 500ms overhead)

Query: "Compare FAR 15.404 with FAR 16.401"
┌─ Step 0: far_lookup (15.404) → 1000ms ┐
├─ Step 1: far_lookup (16.401) → 1000ms ├─ Parallel
└─ Step 2: far_compare → 1500ms
   Total execution: 3500ms (saved ~1000ms vs sequential)
```

## Configuration

### Tool Registry
```python
registry = ToolRegistry()
registry.register("usaspending_search", search_usaspending_handler)
registry.register("far_lookup", lookup_far_handler)
registry.register("bls_wage", get_wage_data_handler)
```

### Rate Limiting
```python
rate_limiter = RateLimitGuard(limits={"user123": 100})  # 100 req/hour
allowed, msg = await rate_limiter.check("user123", "usaspending_search")
```

### Custom Tool Specs
```python
planner = ExecutionPlanner(tool_registry={
    "custom_tool": {
        "depends_on": ["bls_wage"],
        "estimated_ms": 5000,
        "requires_params": ["query"]
    }
})
```

## Testing

```python
# Test intent classification
assert intent.category == IntentCategory.SPENDING_SEARCH
assert "usaspending_search" in intent.tools_needed

# Test execution planning
assert len(plan.steps) == 1
assert plan.execution_strategy == "sequential"

# Test answer synthesis
assert len(answer.answer_text) > 0
assert answer.confidence > 0.5

# Test guardrails
assert len(grounding_issues) == 0  # Should be grounded
assert len(pii_detections) == 0  # Should have no PII
```

## Future Enhancements

1. **Multi-turn Context** - Track conversation history better
2. **Caching** - Cache tool results for repeated queries
3. **User Preferences** - Personalize tool selection
4. **A/B Testing** - Test different tool combinations
5. **Metrics** - Track confidence, accuracy, latency
6. **Fine-tuning** - Learn from user feedback on answers
