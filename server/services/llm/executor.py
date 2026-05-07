# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Symdue contributors
"""
LLM executor for LLM node execution.

Executes LLM calls via LangChain with proper API-key retrieval,
prompt formatting, and error handling.
"""
import asyncio
import logging
import re
import base64
import json
import mimetypes
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
import requests

from database.connection import SessionLocal
from database.models import LLMConfig
from config.settings import get_settings

logger = logging.getLogger(__name__)


def _try_heartbeat(message: str) -> None:
    """Send Temporal activity heartbeat if running inside an activity context."""
    try:
        from temporalio import activity
        activity.heartbeat(message)
    except Exception:
        pass  # Not inside an activity context — safe to ignore


class LLMExecutor:
    """
    Executes LLM nodes with prompt templating and weighted input aggregation.
    """

    def __init__(self):
        self.settings = get_settings()

    async def execute_llm_node(
        self,
        prompt_template: str,
        inputs: Dict[str, Any],
        config_id: Optional[str] = None,
        run_id: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Execute an LLM node.

        Args:
            prompt_template: Prompt text. May contain ``{variable}`` placeholders
                             that will be filled from *inputs*.
            inputs: Upstream node outputs / aggregated inputs.
            config_id: LLM config row ID (UUID).  Falls back to the default
                       config when ``None``.
            run_id: Run history ID (for tracking / logging).
            temperature: Optional temperature override for this call.
                         When ``None`` the config-level temperature is used.

        Returns:
            ``{"output": str, "output_type": "text", "tokens_used": int | None}``
        """
        db = SessionLocal()
        try:
            llm_config = self._load_config(db, config_id)
            api_key = self._resolve_api_key(llm_config)

            if not api_key:
                raise ValueError(
                    f"No API key found for LLM config '{llm_config.name}' "
                    f"(id={llm_config.id}).  Please set the API key in Settings → Model Registry."
                )

            # Create LangChain chat model
            llm = self._create_llm_client(llm_config, api_key, temperature_override=temperature)
            logger.info(
                f"[run={run_id}] LLM node: provider={llm_config.provider}, "
                f"model={llm_config.model}, prompt_len={len(prompt_template)}"
            )

            # Format prompt with type-aware replacement
            format_result = self._format_prompt(prompt_template, inputs)
            parts = format_result["parts"]
            
            logger.debug(
                f"[run={run_id}] Formatted prompt: {len(parts)} parts, "
                f"{sum(1 for t, _ in parts if t == 'image')} images"
            )
            
            # Format message for provider
            from langchain_core.messages import HumanMessage
            message_content = self._format_message_for_provider(parts, llm_config.provider)
            messages = [HumanMessage(content=message_content)]

            # Execute — send heartbeats while waiting
            _try_heartbeat(f"LLM call starting: {llm_config.provider}/{llm_config.model}")

            try:
                llm_task = asyncio.create_task(llm.ainvoke(messages))

                # Send heartbeats every 15s while waiting for the LLM response
                elapsed = 0
                while not llm_task.done():
                    try:
                        response = await asyncio.wait_for(
                            asyncio.shield(llm_task), timeout=15.0
                        )
                        break  # Got the response
                    except asyncio.TimeoutError:
                        elapsed += 15
                        _try_heartbeat(
                            f"LLM call in progress ({elapsed}s): "
                            f"{llm_config.provider}/{llm_config.model}"
                        )
                        logger.debug(f"[run={run_id}] LLM heartbeat ({elapsed}s)")
                else:
                    # Task completed between checks
                    response = llm_task.result()
            except (AttributeError, ValueError) as e:
                # Handle Google provider library bug: finish_reason can be int instead of enum
                # This is a known issue in langchain-google-genai where candidate.finish_reason
                # is an int but the library tries to access .name attribute
                error_str = str(e)
                if llm_config.provider == "google" and (
                    "'int' object has no attribute 'name'" in error_str or
                    "finish_reason" in error_str.lower()
                ):
                    logger.error(
                        f"[run={run_id}] Google provider library bug detected: {e}. "
                        f"This is a known issue in langchain-google-genai. "
                        f"Please update the library or use a different provider."
                    )
                    raise ValueError(
                        f"Google provider error (library bug): {e}. "
                        f"Please update langchain-google-genai to the latest version "
                        f"or use a different provider."
                    ) from e
                # Re-raise if it's a different error
                raise
            except Exception as e:
                # Catch any other exceptions that might contain the Google bug
                error_str = str(e)
                if llm_config.provider == "google" and (
                    "'int' object has no attribute 'name'" in error_str or
                    "finish_reason" in error_str.lower()
                ):
                    logger.error(
                        f"[run={run_id}] Google provider library bug detected: {e}. "
                        f"This is a known issue in langchain-google-genai."
                    )
                    raise ValueError(
                        f"Google provider error (library bug): {e}. "
                        f"Please update langchain-google-genai to the latest version "
                        f"or use a different provider."
                    ) from e
                raise

            # Extract response text
            response_text = response.content if hasattr(response, "content") else str(response)

            # Token usage
            tokens_used = None
            if hasattr(response, "response_metadata"):
                usage = response.response_metadata.get("token_usage", {})
                tokens_used = usage.get("total_tokens")
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                tokens_used = getattr(response.usage_metadata, "total_tokens", tokens_used)

            logger.info(
                f"[run={run_id}] LLM response: {len(response_text)} chars, "
                f"tokens={tokens_used}"
            )

            return {
                "output": response_text,
                "output_type": "text",
                "tokens_used": tokens_used,
                "prompt_text": prompt_template,
                "response_text": response_text,
            }

        except Exception as e:
            logger.error(f"[run={run_id}] LLM execution failed: {e}", exc_info=True)
            raise
        finally:
            db.close()

    # ──────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────

    @staticmethod
    def _load_config(db, config_id: Optional[str]) -> LLMConfig:
        """Load an LLM config from the database."""
        if config_id:
            cfg = (
                db.query(LLMConfig)
                .filter(LLMConfig.id == config_id, LLMConfig.deleted_at.is_(None))
                .first()
            )
            if cfg:
                return cfg
            raise ValueError(f"LLM config '{config_id}' not found or deleted")

        # Fallback: first non-deleted config
        cfg = (
            db.query(LLMConfig)
            .filter(LLMConfig.deleted_at.is_(None))
            .first()
        )
        if cfg:
            return cfg
        raise ValueError(
            "No LLM configurations exist.  "
            "Create one in Settings → Model Registry first."
        )

    @staticmethod
    def _resolve_api_key(config: LLMConfig) -> Optional[str]:
        """
        Resolve the API key from the LLMConfig model.

        The key can live in two places:
        1. ``config.api_key`` — dedicated column on the model.
        2. ``config.config["api_key"]`` — inside the JSONB ``config`` column
           (this is where the frontend Settings page stores it).

        We check both, preferring the dedicated column.
        """
        # Dedicated column
        if config.api_key:
            return config.api_key

        # JSONB config field (frontend sends api_key inside config: {api_key: "..."})
        if config.config and isinstance(config.config, dict):
            return config.config.get("api_key")

        return None

    @staticmethod
    def _format_prompt(template: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format prompt with type-aware placeholder replacement.
        Tracks image positions to insert them at the correct location.
        
        Args:
            template: Prompt template with {placeholders}
            inputs: Input values keyed by node name (supports dot notation)
        
        Returns:
            dict with:
            - parts: List of (type, content) where type is "text" or "image"
            - images: List of (bytes, mime_type) for reference/tracking
        """
        if not template:
            # No template — concatenate all input values as context
            parts = []
            for k, v in inputs.items():
                parts.append(f"{k}: {v}")
            text_content = "\n".join(parts) if parts else "Hello"
            return {
                "parts": [("text", text_content)],
                "images": []
            }
        
        placeholder_pattern = r'\{([^}]+)\}'
        image_attachments = []  # List of (bytes, mime_type) for tracking
        image_ref_counter = 1
        
        # Build parts list with position tracking
        parts = []
        last_end = 0
        
        def replace_placeholder(match):
            nonlocal image_ref_counter, last_end
            
            full_key = match.group(1)  # e.g., "data_source" or "data.items"
            match_start = match.start()
            match_end = match.end()
            
            # Add text before this placeholder
            if match_start > last_end:
                text_before = template[last_end:match_start]
                if text_before:
                    parts.append(("text", text_before))
            
            # Get value (supports dot notation)
            value = LLMExecutor._get_nested_value(full_key, inputs)
            
            if value is None:
                # Not found - keep placeholder
                parts.append(("text", f"{{{full_key}}}"))
                last_end = match_end
                return ""
            
            # Handle placeholder based on type
            if isinstance(value, str):
                if LLMExecutor._is_image_url(value):
                    # Single image
                    try:
                        image_bytes, mime_type = LLMExecutor._download_image(value)
                        image_attachments.append((image_bytes, mime_type))
                        ref = f"[image{image_ref_counter}]"
                        image_ref_counter += 1
                        
                        # Add reference text
                        parts.append(("text", f"See attached image {ref}"))
                        # Add image part
                        parts.append(("image", (image_bytes, mime_type)))
                    except Exception as e:
                        logger.error(f"Failed to download image {value}: {e}")
                        parts.append(("text", f"[ERROR: Failed to load image: {e}]"))
                else:
                    # Regular text
                    parts.append(("text", value))
            
            elif isinstance(value, list):
                if len(value) == 0:
                    # Empty array - add nothing
                    pass
                elif LLMExecutor._is_image_array(value):
                    # Array of images
                    start_ref = image_ref_counter
                    image_parts = []
                    
                    for img_url in value:
                        if isinstance(img_url, str) and LLMExecutor._is_image_url(img_url):
                            try:
                                image_bytes, mime_type = LLMExecutor._download_image(img_url)
                                image_attachments.append((image_bytes, mime_type))
                                image_parts.append((image_bytes, mime_type))
                                image_ref_counter += 1
                            except Exception as e:
                                logger.error(f"Failed to download image {img_url}: {e}")
                    
                    end_ref = image_ref_counter - 1
                    if start_ref == end_ref:
                        ref_text = f"See attached image [image{start_ref}]"
                    else:
                        ref_text = f"See attached images [image{start_ref} to image{end_ref}]"
                    
                    # Add reference text
                    parts.append(("text", ref_text))
                    # Add all image parts
                    for img_part in image_parts:
                        parts.append(("image", img_part))
                else:
                    # Array of text - join with space
                    text_value = " ".join(str(item) for item in value)
                    parts.append(("text", text_value))
            
            elif isinstance(value, dict):
                if value.get("type") == "image":
                    # Image reference dict (from stored image)
                    try:
                        image_bytes, mime_type = LLMExecutor._load_image_from_ref(value)
                        image_attachments.append((image_bytes, mime_type))
                        ref = f"[image{image_ref_counter}]"
                        image_ref_counter += 1
                        
                        parts.append(("text", f"See attached image {ref}"))
                        parts.append(("image", (image_bytes, mime_type)))
                    except Exception as e:
                        logger.error(f"Failed to load image from reference: {e}")
                        parts.append(("text", f"[ERROR: Failed to load image: {e}]"))
                else:
                    # Regular dict - convert to JSON
                    json_text = json.dumps(value, indent=2)
                    parts.append(("text", json_text))
            
            else:
                # Other types (number, bool, etc.)
                parts.append(("text", str(value)))
            
            last_end = match_end
            return ""  # We've handled it, return empty to remove from template
        
        # Replace all placeholders (this builds the parts list)
        re.sub(placeholder_pattern, replace_placeholder, template)
        
        # Add any remaining text after last placeholder
        if last_end < len(template):
            remaining_text = template[last_end:]
            if remaining_text:
                parts.append(("text", remaining_text))
        
        # If no placeholders were found, add entire template as text
        if not parts:
            parts.append(("text", template))
        
        return {
            "parts": parts,  # List of (type, content) tuples
            "images": image_attachments  # For reference/tracking
        }

    @staticmethod
    def _is_image_url(value: str) -> bool:
        """Check if string is an image URL or path."""
        if not isinstance(value, str):
            return False
        
        # Check file extension
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg'}
        value_lower = value.lower()
        
        # Check URL patterns
        if value_lower.startswith(('http://', 'https://', 'data:image/')):
            # Check if URL ends with image extension or contains image indicator
            if any(ext in value_lower for ext in image_extensions):
                return True
            # Check for data URI
            if value_lower.startswith('data:image/'):
                return True
        
        # Check file path
        if any(value_lower.endswith(ext) for ext in image_extensions):
            return True
        
        return False

    @staticmethod
    def _is_image_array(value: list) -> bool:
        """Check if array contains image URLs."""
        if not isinstance(value, list) or len(value) == 0:
            return False
        
        # Check if all items are image URLs
        return all(LLMExecutor._is_image_url(item) for item in value if isinstance(item, str))

    @staticmethod
    def _get_nested_value(full_key: str, inputs: Dict[str, Any]) -> Any:
        """
        Get value from inputs using dot notation.
        
        Supports:
        - Simple key: "data_source" → inputs["data_source"]
        - Dot notation: "data.items" → inputs["data"]["items"]
        - Array indexing: "data.0" → inputs["data"][0]
        """
        # Prepare inputs: extract values but keep structure for dot notation
        flat_inputs: Dict[str, Any] = {}
        for k, v in inputs.items():
            if isinstance(v, dict):
                # If dict has "output" key, extract it but keep structure
                if "output" in v:
                    output_value = v["output"]
                    # Keep the structure (dict/list) for dot notation access
                    flat_inputs[k] = output_value
                else:
                    # Dict without "output" - store as-is for dot notation
                    flat_inputs[k] = v
            elif isinstance(v, list):
                # Store list as-is for potential indexing
                flat_inputs[k] = v
            elif v is None:
                flat_inputs[k] = None
            elif isinstance(v, str):
                flat_inputs[k] = v
            else:
                # Keep original type for potential dot notation
                flat_inputs[k] = v
        
        parts = full_key.split(".")
        current = flat_inputs
        
        for part in parts:
            if current is None:
                return None
            
            if isinstance(current, dict):
                # Simply get the key - no need to check for "output" here
                # because we already extracted it in the preparation step above
                current = current.get(part)
            elif isinstance(current, list):
                try:
                    index = int(part)
                    if 0 <= index < len(current):
                        current = current[index]
                    else:
                        return None
                except ValueError:
                    return None
            else:
                return None
        
        return current

    @staticmethod
    def _download_image(url_or_path: str) -> Tuple[bytes, str]:
        """
        Download image from URL or load from file path.
        
        Returns:
            tuple: (image_bytes, mime_type)
        """
        # Check if it's a URL
        if url_or_path.startswith(('http://', 'https://')):
            response = requests.get(url_or_path, timeout=30)
            response.raise_for_status()
            image_bytes = response.content
            
            # Determine MIME type from Content-Type header or URL
            mime_type = response.headers.get('Content-Type', 'image/jpeg')
            if not mime_type.startswith('image/'):
                # Fallback: guess from URL
                mime_type, _ = mimetypes.guess_type(url_or_path)
                mime_type = mime_type or 'image/jpeg'
        elif url_or_path.startswith('data:image/'):
            # Handle data URI
            header, encoded = url_or_path.split(',', 1)
            mime_type = header.split(';')[0].split(':')[1]
            image_bytes = base64.b64decode(encoded)
        else:
            # Local file path
            path = Path(url_or_path)
            if not path.exists():
                raise FileNotFoundError(f"Image not found: {url_or_path}")
            
            image_bytes = path.read_bytes()
            mime_type, _ = mimetypes.guess_type(str(path))
            mime_type = mime_type or 'image/jpeg'
        
        return image_bytes, mime_type

    @staticmethod
    def _load_image_from_ref(image_ref: dict) -> Tuple[bytes, str]:
        """
        Load image from stored image reference dict.
        
        Image reference format:
        {
            "type": "image",
            "path": "/app/storage/runs/{run_id}/nodes/{node_id}/output.png",
            "url": "/api/files/...",
            "mime_type": "image/png",
            ...
        }
        """
        # If image_ref has a path, load from file
        if "path" in image_ref:
            path = Path(image_ref["path"])
            if not path.exists():
                raise FileNotFoundError(f"Image path not found: {image_ref['path']}")
            image_bytes = path.read_bytes()
            mime_type = image_ref.get("mime_type", "image/jpeg")
            return image_bytes, mime_type
        
        # If image_ref has base64 data
        if "data" in image_ref:
            image_bytes = base64.b64decode(image_ref["data"])
            mime_type = image_ref.get("mime_type", "image/jpeg")
            return image_bytes, mime_type
        
        raise ValueError(f"Cannot load image from reference: {image_ref}")

    @staticmethod
    def _format_message_for_provider(
        parts: List[Tuple[str, Any]],
        provider: str
    ) -> Any:
        """
        Format message parts according to provider-specific requirements.
        
        Args:
            parts: List of (type, content) where type is "text" or "image"
            provider: LLM provider name ("openai", "anthropic", "google", etc.)
        
        Returns:
            Formatted message content for the provider
        """
        if provider == "openai":
            message_content = []
            for part_type, part_content in parts:
                if part_type == "text":
                    message_content.append({
                        "type": "input_text",
                        "text": part_content
                    })
                elif part_type == "image":
                    image_bytes, mime_type = part_content
                    # OpenAI uses base64 string directly, not data URL
                    image_base64 = base64.b64encode(image_bytes).decode("utf-8")
                    message_content.append({
                        "type": "input_image",
                        "image_base64": image_base64,
                    })
            return message_content
        
        elif provider == "anthropic":
            message_content = []
            for part_type, part_content in parts:
                if part_type == "text":
                    message_content.append({
                        "type": "text",
                        "text": part_content
                    })
                elif part_type == "image":
                    image_bytes, mime_type = part_content
                    base64_data = base64.b64encode(image_bytes).decode('utf-8')
                    message_content.append({
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": mime_type,
                            "data": base64_data,
                        },
                    })
            return message_content
        
        elif provider == "google":
            # LangChain's ChatGoogleGenerativeAI expects content as a list
            # where images are represented as dictionaries with base64 data URLs
            # LangChain will handle the conversion to Google's API format internally
            contents = []
            for part_type, part_content in parts:
                if part_type == "text":
                    contents.append(part_content)
                elif part_type == "image":
                    image_bytes, mime_type = part_content
                    # Format as data URL for LangChain's ChatGoogleGenerativeAI
                    # This format is compatible with LangChain's Google integration
                    base64_data = base64.b64encode(image_bytes).decode('utf-8')
                    data_url = f"data:{mime_type};base64,{base64_data}"
                    contents.append({
                        "type": "image_url",
                        "image_url": {"url": data_url}
                    })
            return contents
        
        elif provider in ["perplexity", "local"]:
            # Perplexity and local (Ollama) use OpenAI-compatible format with data URL
            message_content = []
            for part_type, part_content in parts:
                if part_type == "text":
                    message_content.append({
                        "type": "text",
                        "text": part_content
                    })
                elif part_type == "image":
                    image_bytes, mime_type = part_content
                    base64_data = base64.b64encode(image_bytes).decode('utf-8')
                    data_url = f"data:{mime_type};base64,{base64_data}"
                    message_content.append({
                        "type": "image_url",
                        "image_url": {"url": data_url}
                    })
            return message_content
        
        else:
            raise ValueError(f"Unsupported provider: {provider}")

    @staticmethod
    def _create_llm_client(config: LLMConfig, api_key: str, temperature_override: Optional[float] = None):
        """
        Create a LangChain chat model based on provider.

        Args:
            config: LLM configuration row.
            api_key: Resolved API key.
            temperature_override: When not None, overrides the config-level
                                  temperature for this call.
        """
        temperature = 0.7
        if config.config and isinstance(config.config, dict):
            temperature = config.config.get("temperature", temperature)
        if temperature_override is not None:
            temperature = temperature_override

        base_url = config.base_url

        if config.provider == "openai":
            from langchain_openai import ChatOpenAI
            kwargs: Dict[str, Any] = {
                "model": config.model,
                "api_key": api_key,
                "temperature": temperature,
            }
            if base_url:
                kwargs["base_url"] = base_url
            return ChatOpenAI(**kwargs)

        elif config.provider == "anthropic":
            from langchain_anthropic import ChatAnthropic
            kwargs = {
                "model": config.model,
                "api_key": api_key,
                "temperature": temperature,
            }
            if base_url:
                kwargs["anthropic_api_url"] = base_url
            return ChatAnthropic(**kwargs)

        elif config.provider == "google":
            from langchain_google_genai import ChatGoogleGenerativeAI
            return ChatGoogleGenerativeAI(
                model=config.model,
                google_api_key=api_key,
                temperature=temperature,
            )

        elif config.provider == "perplexity":
            # Perplexity uses OpenAI-compatible API
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=config.model,
                api_key=api_key,
                temperature=temperature,
                base_url=base_url or "https://api.perplexity.ai",
            )

        elif config.provider == "local":
            # Ollama / local model via OpenAI-compatible endpoint
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=config.model,
                api_key=api_key or "ollama",  # Ollama doesn't need a real key
                temperature=temperature,
                base_url=base_url or "http://localhost:11434/v1",
            )

        else:
            raise ValueError(f"Unsupported LLM provider: {config.provider}")
