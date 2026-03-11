"""LLM provider abstraction and implementations.

This module provides a unified interface for different LLM providers
(Anthropic Claude, OpenAI, Azure OpenAI) with proper error handling,
retry logic, and structured output parsing.
"""

from abc import ABC, abstractmethod
import json
import asyncio
from typing import Optional, Any
from pydantic import BaseModel


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    @abstractmethod
    async def complete(
        self,
        messages: list[dict],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs
    ) -> str:
        """Generate text completion.
        
        Args:
            messages: Chat messages (role/content dicts)
            system_prompt: Optional system prompt
            temperature: Temperature for sampling (0.0-1.0)
            max_tokens: Maximum tokens in response
            **kwargs: Provider-specific parameters
            
        Returns:
            Completed text
        """
        pass
    
    @abstractmethod
    async def complete_structured(
        self,
        messages: list[dict],
        schema: dict,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> dict:
        """Generate structured (JSON) completion.
        
        Args:
            messages: Chat messages
            schema: JSON schema for output
            system_prompt: Optional system prompt
            **kwargs: Provider-specific parameters
            
        Returns:
            Parsed JSON response matching schema
        """
        pass


class AnthropicProvider(LLMProvider):
    """Claude (Anthropic) provider implementation."""
    
    def __init__(
        self,
        api_key: str,
        model: str = "claude-opus-4-6",
        max_retries: int = 3,
        timeout_seconds: int = 60
    ):
        """Initialize Anthropic provider.
        
        Args:
            api_key: Anthropic API key
            model: Model identifier (default: claude-opus-4-6)
            max_retries: Number of retries on failure
            timeout_seconds: Request timeout
        """
        self.api_key = api_key
        self.model = model
        self.max_retries = max_retries
        self.timeout_seconds = timeout_seconds
        
        try:
            import anthropic
            self.client = anthropic.AsyncAnthropic(api_key=api_key)
        except ImportError:
            raise RuntimeError("anthropic package required: pip install anthropic")

    async def complete(
        self,
        messages: list[dict],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs
    ) -> str:
        """Generate completion using Claude.
        
        Args:
            messages: Chat messages
            system_prompt: System prompt
            temperature: Sampling temperature
            max_tokens: Max tokens in response
            **kwargs: Additional parameters
            
        Returns:
            Completion text
        """
        for attempt in range(self.max_retries):
            try:
                response = await asyncio.wait_for(
                    self.client.messages.create(
                        model=self.model,
                        max_tokens=max_tokens,
                        system=system_prompt or "",
                        messages=messages,
                        temperature=temperature,
                    ),
                    timeout=self.timeout_seconds
                )
                
                return response.content[0].text
            
            except asyncio.TimeoutError:
                if attempt == self.max_retries - 1:
                    raise
                await asyncio.sleep(1.0 * (2 ** attempt))
            
            except Exception as e:
                if attempt == self.max_retries - 1:
                    raise RuntimeError(f"Claude completion failed: {str(e)}")
                await asyncio.sleep(1.0 * (2 ** attempt))

    async def complete_structured(
        self,
        messages: list[dict],
        schema: dict,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> dict:
        """Generate structured completion using Claude.
        
        Args:
            messages: Chat messages
            schema: JSON schema
            system_prompt: System prompt
            **kwargs: Additional parameters
            
        Returns:
            Parsed JSON object
        """
        # Add instruction for JSON output
        updated_messages = messages.copy()
        if updated_messages:
            last_msg = updated_messages[-1].copy()
            last_msg["content"] += "\n\nRespond with valid JSON matching this schema:\n" + json.dumps(schema)
            updated_messages[-1] = last_msg
        
        updated_system = system_prompt or ""
        updated_system += "\n\nYou must respond with valid JSON only, no other text."
        
        response_text = await self.complete(
            updated_messages,
            system_prompt=updated_system,
            temperature=0.0,  # Lower temp for structured output
            max_tokens=2000
        )
        
        # Parse JSON response
        try:
            # Try direct parsing
            return json.loads(response_text)
        except json.JSONDecodeError:
            # Try to extract JSON from response
            import re
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            raise ValueError("Could not parse JSON from response")


class OpenAIProvider(LLMProvider):
    """OpenAI provider implementation."""
    
    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4-turbo",
        max_retries: int = 3,
        timeout_seconds: int = 60
    ):
        """Initialize OpenAI provider.
        
        Args:
            api_key: OpenAI API key
            model: Model identifier (default: gpt-4-turbo)
            max_retries: Number of retries on failure
            timeout_seconds: Request timeout
        """
        self.api_key = api_key
        self.model = model
        self.max_retries = max_retries
        self.timeout_seconds = timeout_seconds
        
        try:
            from openai import AsyncOpenAI
            self.client = AsyncOpenAI(api_key=api_key)
        except ImportError:
            raise RuntimeError("openai package required: pip install openai")

    async def complete(
        self,
        messages: list[dict],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs
    ) -> str:
        """Generate completion using OpenAI.
        
        Args:
            messages: Chat messages
            system_prompt: System prompt
            temperature: Sampling temperature
            max_tokens: Max tokens in response
            **kwargs: Additional parameters
            
        Returns:
            Completion text
        """
        # Prepend system message
        all_messages = messages.copy()
        if system_prompt:
            all_messages.insert(0, {"role": "system", "content": system_prompt})
        
        for attempt in range(self.max_retries):
            try:
                response = await asyncio.wait_for(
                    self.client.chat.completions.create(
                        model=self.model,
                        messages=all_messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    ),
                    timeout=self.timeout_seconds
                )
                
                return response.choices[0].message.content
            
            except asyncio.TimeoutError:
                if attempt == self.max_retries - 1:
                    raise
                await asyncio.sleep(1.0 * (2 ** attempt))
            
            except Exception as e:
                if attempt == self.max_retries - 1:
                    raise RuntimeError(f"OpenAI completion failed: {str(e)}")
                await asyncio.sleep(1.0 * (2 ** attempt))

    async def complete_structured(
        self,
        messages: list[dict],
        schema: dict,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> dict:
        """Generate structured completion using OpenAI.
        
        Args:
            messages: Chat messages
            schema: JSON schema
            system_prompt: System prompt
            **kwargs: Additional parameters
            
        Returns:
            Parsed JSON object
        """
        # Try to use response_format if available
        all_messages = messages.copy()
        if system_prompt:
            all_messages.insert(0, {"role": "system", "content": system_prompt})
        
        try:
            response = await asyncio.wait_for(
                self.client.chat.completions.create(
                    model=self.model,
                    messages=all_messages,
                    temperature=0.0,
                    max_tokens=2000,
                    response_format={"type": "json_object"}
                ),
                timeout=self.timeout_seconds
            )
            
            return json.loads(response.choices[0].message.content)
        
        except Exception:
            # Fallback to text completion + parsing
            response_text = await self.complete(
                messages,
                system_prompt=system_prompt,
                temperature=0.0
            )
            
            try:
                return json.loads(response_text)
            except json.JSONDecodeError:
                import re
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group())
                raise ValueError("Could not parse JSON from response")


class AzureOpenAIProvider(LLMProvider):
    """Azure OpenAI provider implementation."""
    
    def __init__(
        self,
        api_key: str,
        endpoint: str,
        deployment_id: str,
        api_version: str = "2024-02-15-preview",
        max_retries: int = 3,
        timeout_seconds: int = 60
    ):
        """Initialize Azure OpenAI provider.
        
        Args:
            api_key: Azure OpenAI API key
            endpoint: Azure endpoint URL
            deployment_id: Deployment ID
            api_version: API version (default: 2024-02-15-preview)
            max_retries: Number of retries on failure
            timeout_seconds: Request timeout
        """
        self.api_key = api_key
        self.endpoint = endpoint
        self.deployment_id = deployment_id
        self.api_version = api_version
        self.max_retries = max_retries
        self.timeout_seconds = timeout_seconds
        
        try:
            from openai import AsyncAzureOpenAI
            self.client = AsyncAzureOpenAI(
                api_key=api_key,
                api_version=api_version,
                azure_endpoint=endpoint,
            )
            self.deployment_id = deployment_id
        except ImportError:
            raise RuntimeError("openai package required: pip install openai")

    async def complete(
        self,
        messages: list[dict],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs
    ) -> str:
        """Generate completion using Azure OpenAI.
        
        Args:
            messages: Chat messages
            system_prompt: System prompt
            temperature: Sampling temperature
            max_tokens: Max tokens in response
            **kwargs: Additional parameters
            
        Returns:
            Completion text
        """
        all_messages = messages.copy()
        if system_prompt:
            all_messages.insert(0, {"role": "system", "content": system_prompt})
        
        for attempt in range(self.max_retries):
            try:
                response = await asyncio.wait_for(
                    self.client.chat.completions.create(
                        engine=self.deployment_id,
                        messages=all_messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    ),
                    timeout=self.timeout_seconds
                )
                
                return response.choices[0].message.content
            
            except asyncio.TimeoutError:
                if attempt == self.max_retries - 1:
                    raise
                await asyncio.sleep(1.0 * (2 ** attempt))
            
            except Exception as e:
                if attempt == self.max_retries - 1:
                    raise RuntimeError(f"Azure OpenAI completion failed: {str(e)}")
                await asyncio.sleep(1.0 * (2 ** attempt))

    async def complete_structured(
        self,
        messages: list[dict],
        schema: dict,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> dict:
        """Generate structured completion using Azure OpenAI.
        
        Args:
            messages: Chat messages
            schema: JSON schema
            system_prompt: System prompt
            **kwargs: Additional parameters
            
        Returns:
            Parsed JSON object
        """
        all_messages = messages.copy()
        if system_prompt:
            all_messages.insert(0, {"role": "system", "content": system_prompt})
        
        try:
            response = await asyncio.wait_for(
                self.client.chat.completions.create(
                    engine=self.deployment_id,
                    messages=all_messages,
                    temperature=0.0,
                    max_tokens=2000,
                    response_format={"type": "json_object"}
                ),
                timeout=self.timeout_seconds
            )
            
            return json.loads(response.choices[0].message.content)
        
        except Exception:
            # Fallback
            response_text = await self.complete(
                messages,
                system_prompt=system_prompt,
                temperature=0.0
            )
            
            try:
                return json.loads(response_text)
            except json.JSONDecodeError:
                import re
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group())
                raise ValueError("Could not parse JSON from response")


def get_provider(
    provider_name: str,
    api_key: str,
    **kwargs
) -> LLMProvider:
    """Factory function to get LLM provider.
    
    Args:
        provider_name: "anthropic", "openai", or "azure"
        api_key: API key for the provider
        **kwargs: Provider-specific configuration
        
    Returns:
        LLMProvider instance
        
    Raises:
        ValueError: If provider name not recognized
    """
    if provider_name.lower() == "anthropic":
        return AnthropicProvider(api_key, **kwargs)
    
    elif provider_name.lower() == "openai":
        return OpenAIProvider(api_key, **kwargs)
    
    elif provider_name.lower() == "azure":
        return AzureOpenAIProvider(api_key, **kwargs)
    
    else:
        raise ValueError(f"Unknown LLM provider: {provider_name}")
