"""Intent classification and tool routing.

This module classifies user queries into acquisition-specific intents
and determines which tools are needed to answer them.
"""

import json
import re
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class IntentCategory(str, Enum):
    """Categories of user intent in acquisition context."""
    SPENDING_SEARCH = "spending_search"  # USAspending, contract search
    AWARD_DETAIL = "award_detail"  # Detailed award information
    REGULATION_LOOKUP = "regulation_lookup"  # Specific regulation section
    REGULATION_SEARCH = "regulation_search"  # Search regulations by topic
    REGULATION_COMPARE = "regulation_compare"  # Compare multiple regulations
    WAGE_LOOKUP = "wage_lookup"  # Wage/salary/labor rates
    PERDIEM_LOOKUP = "perdiem_lookup"  # Per diem rates
    IGCE_BUILD = "igce_build"  # Build independent government cost estimate
    MARKET_RESEARCH = "market_research"  # Market research queries
    DOCKET_SEARCH = "docket_search"  # Docket/Federal Register search
    GENERAL_QUESTION = "general_question"  # General acquisition knowledge
    MULTI_TOOL = "multi_tool"  # Requires multiple tools


class ClassifiedIntent(BaseModel):
    """Result of intent classification."""
    category: IntentCategory
    confidence: float = Field(ge=0.0, le=1.0)
    tools_needed: list[str]
    extracted_params: dict
    reasoning: str
    requires_llm_synthesis: bool = True


class IntentRouter:
    """Routes user queries to appropriate tools.
    
    Uses a combination of:
    1. Keyword/pattern matching for high-confidence routing
    2. LLM classification for ambiguous queries
    """
    
    # Spending-related keywords and patterns
    SPENDING_PATTERNS = {
        'keywords': [
            'obligation', 'obligated', 'award', 'contract', 'vendor',
            'contractor', 'spending', 'funded', 'allocated', 'budget',
            'procurement', 'purchase', 'supplier', 'transaction'
        ],
        'patterns': [
            r'\bNAICS\s+\d+',
            r'\bPSC\s+[A-Z0-9]{4}',
            r'\bCommodity\s+Code\s+\d+',
            r'\$[\d,]+(?:\.\d{2})?',
        ]
    }
    
    # Regulation-related keywords
    REGULATION_PATTERNS = {
        'keywords': [
            'FAR', 'DFARS', 'CFR', 'regulation', 'statute', 'rule',
            'requirement', 'comply', 'compliance', '48 CFR', '10 CFR',
            'Federal Acquisition Regulation', 'clause', 'provision'
        ],
        'patterns': [
            r'\d+\.\d+(?:\.\d+)?(?:\s*\(.*?\))?',  # Section references like 15.404
            r'(?:FAR|DFARS|CFR)\s+(?:\d+\.)?\d+',
            r'\b(?:Part|Subpart)\s+\d+',
        ]
    }
    
    # Wage/labor rate keywords
    WAGE_PATTERNS = {
        'keywords': [
            'wage', 'salary', 'labor rate', 'OEWS', 'prevailing wage',
            'occupation', 'classification', 'hourly rate', 'annual salary',
            'compensation', 'pay grade', 'GS level', 'fringe benefit'
        ],
        'patterns': [
            r'[0-9]+-[0-9]+(?:\.[0-9]{2})?(?:\s*(?:per hour|per year|/hr|/yr|ph|pa))?',
        ]
    }
    
    # Per diem keywords
    PERDIEM_PATTERNS = {
        'keywords': [
            'per diem', 'M&IE', 'meals', 'incidental', 'lodging', 'hotel',
            'meals and incidental', 'daily rate', 'GSA', 'per diem rate'
        ],
        'patterns': [
            r'(?:city|location|travel|trip)\s+(?:to|in)\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?(?:\s*,\s*[A-Z]{2})?',
        ]
    }
    
    # IGCE-related keywords
    IGCE_PATTERNS = {
        'keywords': [
            'IGCE', 'estimate', 'cost estimate', 'independent government',
            'government estimate', 'price estimate', 'rough order magnitude',
            'ROM', 'budget estimate', 'should cost'
        ],
        'patterns': [
            r'(?:build|create|calculate|develop).*(?:IGCE|estimate|cost)',
        ]
    }
    
    # Federal Register / Docket keywords
    DOCKET_PATTERNS = {
        'keywords': [
            'proposed rule', 'final rule', 'Federal Register', 'FR',
            'docket', 'comment', 'regulations.gov', 'CFR', 'notice',
            'NPRM', 'notice of proposed rulemaking'
        ],
        'patterns': [
            r'(?:docket|RIN)\s+(?:[A-Z0-9-]+)',
        ]
    }
    
    # Market research keywords
    MARKET_PATTERNS = {
        'keywords': [
            'market', 'research', 'supplier', 'vendor', 'available',
            'capability', 'capacity', 'industry', 'competition',
            'benchmark', 'price', 'commercial item'
        ],
        'patterns': []
    }

    def __init__(self, llm_provider=None):
        """Initialize router with optional LLM provider for complex classification.
        
        Args:
            llm_provider: LLM provider instance for fallback classification
        """
        self.llm_provider = llm_provider

    async def classify(
        self,
        query: str,
        conversation_history: Optional[list[dict]] = None
    ) -> ClassifiedIntent:
        """Classify user query into acquisition intent.
        
        Args:
            query: User's natural language query
            conversation_history: Previous messages in conversation
            
        Returns:
            ClassifiedIntent with category, tools, and parameters
        """
        # Try keyword-based classification first (high-confidence)
        keyword_result = self._keyword_classify(query)
        if keyword_result and keyword_result.confidence >= 0.8:
            return keyword_result
        
        # Fall back to LLM classification
        if self.llm_provider:
            return await self._llm_classify(query, conversation_history)
        
        # If no LLM provider and keyword classification failed, return general
        return ClassifiedIntent(
            category=IntentCategory.GENERAL_QUESTION,
            confidence=0.5,
            tools_needed=["general_knowledge"],
            extracted_params={},
            reasoning="Could not classify with high confidence"
        )

    def _keyword_classify(self, query: str) -> Optional[ClassifiedIntent]:
        """Classify using keyword and pattern matching.
        
        Args:
            query: User query string
            
        Returns:
            ClassifiedIntent if high-confidence match found, None otherwise
        """
        query_lower = query.lower()
        scores = {}
        
        # Score each category
        scores[IntentCategory.SPENDING_SEARCH] = self._score_patterns(
            query_lower, self.SPENDING_PATTERNS
        )
        scores[IntentCategory.REGULATION_SEARCH] = self._score_patterns(
            query_lower, self.REGULATION_PATTERNS
        )
        scores[IntentCategory.WAGE_LOOKUP] = self._score_patterns(
            query_lower, self.WAGE_PATTERNS
        )
        scores[IntentCategory.PERDIEM_LOOKUP] = self._score_patterns(
            query_lower, self.PERDIEM_PATTERNS
        )
        scores[IntentCategory.IGCE_BUILD] = self._score_patterns(
            query_lower, self.IGCE_PATTERNS
        )
        scores[IntentCategory.DOCKET_SEARCH] = self._score_patterns(
            query_lower, self.DOCKET_PATTERNS
        )
        scores[IntentCategory.MARKET_RESEARCH] = self._score_patterns(
            query_lower, self.MARKET_PATTERNS
        )
        
        # Find best match
        best_category = max(scores, key=scores.get)
        confidence = scores[best_category]
        
        if confidence < 0.1:
            return None
        
        # Extract parameters based on category
        params = self._extract_parameters(query, best_category)
        tools = self._get_tools_for_category(best_category)
        
        return ClassifiedIntent(
            category=best_category,
            confidence=min(confidence, 1.0),
            tools_needed=tools,
            extracted_params=params,
            reasoning=f"Keyword matching score: {confidence:.2f}",
            requires_llm_synthesis=confidence < 0.7
        )

    def _score_patterns(self, query: str, pattern_dict: dict) -> float:
        """Score query against pattern set.
        
        Args:
            query: Lowercase query string
            pattern_dict: Dict with 'keywords' and 'patterns' lists
            
        Returns:
            Score between 0.0 and 1.0
        """
        score = 0.0
        
        # Score keywords (weight: 0.6)
        keywords = pattern_dict.get('keywords', [])
        if keywords:
            keyword_hits = sum(1 for kw in keywords if kw.lower() in query)
            keyword_score = min(keyword_hits / max(len(keywords), 1), 1.0) * 0.6
            score += keyword_score
        
        # Score regex patterns (weight: 0.4)
        patterns = pattern_dict.get('patterns', [])
        if patterns:
            pattern_hits = sum(
                1 for pattern in patterns
                if re.search(pattern, query, re.IGNORECASE)
            )
            pattern_score = min(pattern_hits / max(len(patterns), 1), 1.0) * 0.4
            score += pattern_score
        
        return score

    def _extract_parameters(self, query: str, category: IntentCategory) -> dict:
        """Extract relevant parameters from query based on category.
        
        Args:
            query: User query
            category: Detected intent category
            
        Returns:
            Dict of extracted parameters
        """
        params = {}
        
        if category == IntentCategory.SPENDING_SEARCH:
            # Extract NAICS
            naics_match = re.search(r'\bNAICS\s+(\d+)', query, re.IGNORECASE)
            if naics_match:
                params['naics_code'] = naics_match.group(1)
            
            # Extract PSC
            psc_match = re.search(r'\bPSC\s+([A-Z0-9]{4})', query, re.IGNORECASE)
            if psc_match:
                params['psc_code'] = psc_match.group(1)
            
            # Extract vendor name
            vendor_patterns = [
                r'(?:from|by)\s+([A-Z][a-zA-Z\s&]+?)(?:\s+(?:in|to|for)|$)',
            ]
            for pattern in vendor_patterns:
                match = re.search(pattern, query)
                if match:
                    params['vendor_name'] = match.group(1).strip()
                    break
            
            # Extract amount ranges
            amount_pattern = r'\$?([\d,]+(?:\.\d{2})?)\s*(?:to|-)\s*\$?([\d,]+(?:\.\d{2})?)'
            amount_match = re.search(amount_pattern, query)
            if amount_match:
                params['amount_min'] = amount_match.group(1)
                params['amount_max'] = amount_match.group(2)
        
        elif category == IntentCategory.REGULATION_LOOKUP:
            # Extract regulation citations
            citation_pattern = r'(?:FAR|DFARS|CFR)\s+(?:[\d.]+(?:\([^)]*\))?)'
            citations = re.findall(citation_pattern, query, re.IGNORECASE)
            if citations:
                params['citations'] = citations
        
        elif category == IntentCategory.WAGE_LOOKUP:
            # Extract occupation
            occ_patterns = [
                r'(?:for|as)\s+(?:a\s+)?([a-z]+(?:\s+[a-z]+)?)',
            ]
            for pattern in occ_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    params['occupation'] = match.group(1).strip()
                    break
        
        elif category == IntentCategory.PERDIEM_LOOKUP:
            # Extract location
            location_pattern = r'(?:in|to|at|for)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?(?:\s*,\s*[A-Z]{2})?)'
            location_match = re.search(location_pattern, query)
            if location_match:
                params['location'] = location_match.group(1).strip()
        
        elif category == IntentCategory.IGCE_BUILD:
            # Will be filled by execution planner
            pass
        
        return params

    def _get_tools_for_category(self, category: IntentCategory) -> list[str]:
        """Get list of tools needed for category.
        
        Args:
            category: Intent category
            
        Returns:
            List of tool IDs
        """
        tool_map = {
            IntentCategory.SPENDING_SEARCH: ["usaspending_search"],
            IntentCategory.AWARD_DETAIL: ["usaspending_detail"],
            IntentCategory.REGULATION_LOOKUP: ["far_lookup"],
            IntentCategory.REGULATION_SEARCH: ["far_search"],
            IntentCategory.REGULATION_COMPARE: ["far_compare"],
            IntentCategory.WAGE_LOOKUP: ["bls_wage"],
            IntentCategory.PERDIEM_LOOKUP: ["gsa_perdiem"],
            IntentCategory.IGCE_BUILD: ["bls_wage", "gsa_perdiem"],
            IntentCategory.MARKET_RESEARCH: ["market_research"],
            IntentCategory.DOCKET_SEARCH: ["federalregister_search"],
            IntentCategory.GENERAL_QUESTION: ["general_knowledge"],
            IntentCategory.MULTI_TOOL: [],  # Determined by planner
        }
        return tool_map.get(category, ["general_knowledge"])

    async def _llm_classify(
        self,
        query: str,
        history: Optional[list[dict]] = None
    ) -> ClassifiedIntent:
        """Use LLM for classification when keyword matching is ambiguous.
        
        Args:
            query: User query
            history: Conversation history for context
            
        Returns:
            ClassifiedIntent from LLM
        """
        if not self.llm_provider:
            raise RuntimeError("LLM provider not configured for classification")
        
        system_prompt = """You are an acquisition domain expert classifier.
        
Classify the user's query into one of these categories:
- spending_search: Search USAspending or contracts by vendor, NAICS, PSC, amount
- award_detail: Get detailed information about a specific award/contract
- regulation_lookup: Look up specific FAR/DFARS/CFR section
- regulation_search: Search for regulations on a topic
- regulation_compare: Compare regulations or requirements
- wage_lookup: Wage rates, labor rates, occupations, OEWS
- perdiem_lookup: Per diem rates, GSA lodging, M&IE
- igce_build: Build independent government cost estimate
- market_research: Market research, supplier capabilities
- docket_search: Federal Register dockets, comments, proposed rules
- general_question: General acquisition knowledge
- multi_tool: Requires multiple tool types

Respond with JSON:
{
  "category": "category_name",
  "confidence": 0.0-1.0,
  "reasoning": "brief explanation",
  "extracted_params": {"key": "value"},
  "detected_intent_complexity": "simple|moderate|complex"
}
"""
        
        messages = [
            {"role": "user", "content": query}
        ]
        
        if history:
            # Add last few messages for context
            messages = history[-4:] + messages
        
        try:
            response = await self.llm_provider.complete_structured(
                messages,
                schema={
                    "type": "object",
                    "properties": {
                        "category": {"type": "string"},
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                        "reasoning": {"type": "string"},
                        "extracted_params": {"type": "object"},
                        "detected_intent_complexity": {
                            "type": "string",
                            "enum": ["simple", "moderate", "complex"]
                        }
                    },
                    "required": ["category", "confidence", "reasoning"]
                },
                system_prompt=system_prompt
            )
            
            # Validate category
            try:
                category = IntentCategory(response.get("category", "general_question"))
            except ValueError:
                category = IntentCategory.GENERAL_QUESTION
            
            tools = self._get_tools_for_category(category)
            
            return ClassifiedIntent(
                category=category,
                confidence=response.get("confidence", 0.5),
                tools_needed=tools,
                extracted_params=response.get("extracted_params", {}),
                reasoning=response.get("reasoning", "LLM classification"),
                requires_llm_synthesis=response.get("detected_intent_complexity") in ["moderate", "complex"]
            )
        
        except Exception as e:
            # Fallback to general question on LLM error
            return ClassifiedIntent(
                category=IntentCategory.GENERAL_QUESTION,
                confidence=0.3,
                tools_needed=["general_knowledge"],
                extracted_params={},
                reasoning=f"LLM classification failed: {str(e)}"
            )
