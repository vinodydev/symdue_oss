# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Symdue contributors
"""
Tests for LLM executor with type-aware prompt formatting.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile
import base64
from services.llm.executor import LLMExecutor


@pytest.mark.unit
class TestLLMExecutorTypeDetection:
    """Test type detection and image handling"""
    
    def test_is_image_url_http(self):
        """Test HTTP image URL detection"""
        assert LLMExecutor._is_image_url("https://example.com/photo.jpg") is True
        assert LLMExecutor._is_image_url("http://example.com/image.png") is True
        assert LLMExecutor._is_image_url("https://example.com/data") is False
    
    def test_is_image_url_data_uri(self):
        """Test data URI image detection"""
        assert LLMExecutor._is_image_url("data:image/png;base64,iVBORw0KGgo") is True
        assert LLMExecutor._is_image_url("data:image/jpeg;base64,/9j/4AAQ") is True
    
    def test_is_image_url_file_path(self):
        """Test file path image detection"""
        assert LLMExecutor._is_image_url("/path/to/image.jpg") is True
        assert LLMExecutor._is_image_url("image.png") is True
        assert LLMExecutor._is_image_url("/path/to/file.txt") is False
    
    def test_is_image_array(self):
        """Test image array detection"""
        assert LLMExecutor._is_image_array(["img1.jpg", "img2.png"]) is True
        assert LLMExecutor._is_image_array(["text1", "text2"]) is False
        assert LLMExecutor._is_image_array([]) is False
        assert LLMExecutor._is_image_array(["https://example.com/img.jpg"]) is True


@pytest.mark.unit
class TestLLMExecutorNestedValue:
    """Test nested value access with dot notation"""
    
    def test_simple_key(self):
        """Test simple key access"""
        inputs = {"data_source": "value"}
        result = LLMExecutor._get_nested_value("data_source", inputs)
        assert result == "value"
    
    def test_dot_notation(self):
        """Test dot notation access"""
        inputs = {"data": {"items": ["x", "y"]}}
        result = LLMExecutor._get_nested_value("data.items", inputs)
        assert result == ["x", "y"]
    
    def test_nested_dot_notation(self):
        """Test nested dot notation"""
        inputs = {"data": {"nested": {"value": 42}}}
        result = LLMExecutor._get_nested_value("data.nested.value", inputs)
        assert result == 42
    
    def test_array_indexing(self):
        """Test array indexing"""
        inputs = {"data": ["first", "second", "third"]}
        result = LLMExecutor._get_nested_value("data.0", inputs)
        assert result == "first"
        result = LLMExecutor._get_nested_value("data.1", inputs)
        assert result == "second"
    
    def test_output_wrapper(self):
        """Test handling of output wrapper"""
        inputs = {"node": {"output": {"items": ["a", "b"]}}}
        result = LLMExecutor._get_nested_value("node.items", inputs)
        assert result == ["a", "b"]


@pytest.mark.unit
class TestLLMExecutorImageDownload:
    """Test image download and loading"""
    
    @patch('services.llm.executor.requests.get')
    def test_download_image_from_url(self, mock_get):
        """Test downloading image from URL"""
        # Mock response
        mock_response = Mock()
        mock_response.content = b'fake_image_data'
        mock_response.headers = {'Content-Type': 'image/jpeg'}
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        image_bytes, mime_type = LLMExecutor._download_image("https://example.com/img.jpg")
        
        assert image_bytes == b'fake_image_data'
        assert mime_type == 'image/jpeg'
        mock_get.assert_called_once_with("https://example.com/img.jpg", timeout=30)
    
    def test_download_image_from_file(self):
        """Test loading image from file path"""
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
            tmp.write(b'fake_image_data')
            tmp_path = tmp.name
        
        try:
            image_bytes, mime_type = LLMExecutor._download_image(tmp_path)
            assert image_bytes == b'fake_image_data'
            assert 'image' in mime_type
        finally:
            Path(tmp_path).unlink()
    
    def test_download_image_data_uri(self):
        """Test loading image from data URI"""
        image_data = b'fake_image_data'
        base64_data = base64.b64encode(image_data).decode('utf-8')
        data_uri = f"data:image/png;base64,{base64_data}"
        
        image_bytes, mime_type = LLMExecutor._download_image(data_uri)
        
        assert image_bytes == image_data
        assert mime_type == 'image/png'
    
    def test_load_image_from_ref_path(self):
        """Test loading image from reference with path"""
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
            tmp.write(b'fake_image_data')
            tmp_path = tmp.name
        
        try:
            image_ref = {
                "type": "image",
                "path": tmp_path,
                "mime_type": "image/png"
            }
            
            image_bytes, mime_type = LLMExecutor._load_image_from_ref(image_ref)
            assert image_bytes == b'fake_image_data'
            assert mime_type == "image/png"
        finally:
            Path(tmp_path).unlink()
    
    def test_load_image_from_ref_base64(self):
        """Test loading image from reference with base64 data"""
        image_data = b'fake_image_data'
        base64_data = base64.b64encode(image_data).decode('utf-8')
        
        image_ref = {
            "type": "image",
            "data": base64_data,
            "mime_type": "image/jpeg"
        }
        
        image_bytes, mime_type = LLMExecutor._load_image_from_ref(image_ref)
        assert image_bytes == image_data
        assert mime_type == "image/jpeg"


@pytest.mark.unit
class TestLLMExecutorPromptFormatting:
    """Test prompt formatting with type-aware replacement"""
    
    def test_text_array_expansion(self):
        """Test text array expansion"""
        template = "Items: {items}"
        inputs = {"items": ["a", "b", "c"]}
        result = LLMExecutor._format_prompt(template, inputs)
        
        assert len(result["parts"]) == 1
        assert result["parts"][0] == ("text", "Items: a b c")
        assert len(result["images"]) == 0
    
    @patch('services.llm.executor.requests.get')
    def test_single_image(self, mock_get):
        """Test single image handling"""
        # Mock image download
        mock_response = Mock()
        mock_response.content = b'fake_image_data'
        mock_response.headers = {'Content-Type': 'image/jpeg'}
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        template = "Analyze: {image}"
        inputs = {"image": "https://example.com/photo.jpg"}
        result = LLMExecutor._format_prompt(template, inputs)
        
        # Should have text reference and image part
        assert len(result["parts"]) == 2
        assert result["parts"][0][0] == "text"
        assert "See attached image" in result["parts"][0][1]
        assert result["parts"][1][0] == "image"
        assert len(result["images"]) == 1
    
    @patch('services.llm.executor.requests.get')
    def test_image_array(self, mock_get):
        """Test image array handling"""
        # Mock image downloads
        mock_response = Mock()
        mock_response.content = b'fake_image_data'
        mock_response.headers = {'Content-Type': 'image/jpeg'}
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        template = "Analyze: {images}"
        inputs = {"images": ["https://example.com/img1.jpg", "https://example.com/img2.jpg"]}
        result = LLMExecutor._format_prompt(template, inputs)
        
        # Should have text reference and multiple image parts
        assert len(result["parts"]) >= 3  # Text + 2 images
        assert result["parts"][0][0] == "text"
        assert "See attached images" in result["parts"][0][1]
        assert len(result["images"]) == 2
    
    def test_mixed_content(self):
        """Test mixed text and image content"""
        template = "Text: {text}, Items: {items}"
        inputs = {
            "text": "Hello",
            "items": ["a", "b", "c"]
        }
        result = LLMExecutor._format_prompt(template, inputs)
        
        # Should have text parts
        assert len(result["parts"]) >= 1
        assert all(part[0] == "text" for part in result["parts"])
        text_content = " ".join(part[1] for part in result["parts"])
        assert "Hello" in text_content
        assert "a b c" in text_content
    
    def test_dot_notation(self):
        """Test dot notation in templates"""
        template = "Data: {data.items}, Value: {data.value}"
        inputs = {
            "data": {
                "items": ["x", "y", "z"],
                "value": 42
            }
        }
        result = LLMExecutor._format_prompt(template, inputs)
        
        # Should format correctly
        assert len(result["parts"]) >= 1
        text_content = " ".join(part[1] for part in result["parts"])
        assert "x y z" in text_content or "x" in text_content
        assert "42" in text_content
    
    def test_empty_template(self):
        """Test empty template handling"""
        inputs = {"key": "value"}
        result = LLMExecutor._format_prompt("", inputs)
        
        assert "parts" in result
        assert len(result["parts"]) > 0
        assert result["parts"][0][0] == "text"


@pytest.mark.unit
class TestLLMExecutorProviderFormatting:
    """Test provider-specific message formatting"""
    
    def test_openai_format(self):
        """Test OpenAI message format"""
        parts = [
            ("text", "Hello"),
            ("image", (b'fake_image', 'image/jpeg')),
            ("text", "World")
        ]
        
        result = LLMExecutor._format_message_for_provider(parts, "openai")
        
        assert len(result) == 3
        assert result[0]["type"] == "input_text"
        assert result[0]["text"] == "Hello"
        assert result[1]["type"] == "input_image"
        assert "image_base64" in result[1]
        assert result[2]["type"] == "input_text"
        assert result[2]["text"] == "World"
    
    def test_anthropic_format(self):
        """Test Anthropic message format"""
        parts = [
            ("text", "Hello"),
            ("image", (b'fake_image', 'image/jpeg'))
        ]
        
        result = LLMExecutor._format_message_for_provider(parts, "anthropic")
        
        assert len(result) == 2
        assert result[0]["type"] == "text"
        assert result[0]["text"] == "Hello"
        assert result[1]["type"] == "image"
        assert "source" in result[1]
        assert result[1]["source"]["type"] == "base64"
        assert result[1]["source"]["media_type"] == "image/jpeg"
    
    def test_perplexity_format(self):
        """Test Perplexity message format"""
        parts = [
            ("text", "Hello"),
            ("image", (b'fake_image', 'image/jpeg'))
        ]
        
        result = LLMExecutor._format_message_for_provider(parts, "perplexity")
        
        assert len(result) == 2
        assert result[0]["type"] == "text"
        assert result[0]["text"] == "Hello"
        assert result[1]["type"] == "image_url"
        assert "image_url" in result[1]
        assert "data:image/jpeg;base64" in result[1]["image_url"]["url"]
    
    def test_local_format(self):
        """Test Local (Ollama) message format"""
        parts = [
            ("text", "Hello"),
            ("image", (b'fake_image', 'image/jpeg'))
        ]
        
        result = LLMExecutor._format_message_for_provider(parts, "local")
        
        assert len(result) == 2
        assert result[0]["type"] == "text"
        assert result[1]["type"] == "image_url"
        assert "data:image/jpeg;base64" in result[1]["image_url"]["url"]
    
    @patch('services.llm.executor.types')
    def test_google_format(self, mock_types):
        """Test Google message format"""
        # Mock types.Part.from_bytes
        mock_part = Mock()
        mock_types.Part.from_bytes = Mock(return_value=mock_part)
        
        parts = [
            ("text", "Hello"),
            ("image", (b'fake_image', 'image/jpeg'))
        ]
        
        result = LLMExecutor._format_message_for_provider(parts, "google")
        
        assert len(result) == 2
        assert result[0] == "Hello"
        assert result[1] == mock_part
        mock_types.Part.from_bytes.assert_called_once_with(
            data=b'fake_image',
            mime_type='image/jpeg'
        )


@pytest.mark.integration
class TestLLMExecutorIntegration:
    """Integration tests for LLM executor (requires mocking LLM calls)"""
    
    @pytest.mark.asyncio
    @patch('services.llm.executor.LLMExecutor._create_llm_client')
    @patch('services.llm.executor.LLMExecutor._load_config')
    @patch('services.llm.executor.LLMExecutor._resolve_api_key')
    async def test_execute_llm_node_text_only(self, mock_resolve_key, mock_load_config, mock_create_client):
        """Test LLM node execution with text-only prompt"""
        # Setup mocks
        mock_config = Mock()
        mock_config.provider = "openai"
        mock_config.model = "gpt-4"
        mock_config.name = "Test Config"
        mock_config.id = "test-id"
        mock_load_config.return_value = mock_config
        mock_resolve_key.return_value = "test-api-key"
        
        # Mock LLM client
        mock_llm = Mock()
        mock_response = Mock()
        mock_response.content = "Test response"
        mock_llm.ainvoke = Mock(return_value=mock_response)
        mock_create_client.return_value = mock_llm
        
        executor = LLMExecutor()
        result = await executor.execute_llm_node(
            prompt_template="Hello {name}",
            inputs={"name": "World"},
            config_id="test-config",
            run_id="test-run"
        )
        
        assert result["output"] == "Test response"
        assert result["output_type"] == "text"
        mock_llm.ainvoke.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('services.llm.executor.LLMExecutor._create_llm_client')
    @patch('services.llm.executor.LLMExecutor._load_config')
    @patch('services.llm.executor.LLMExecutor._resolve_api_key')
    @patch('services.llm.executor.requests.get')
    async def test_execute_llm_node_with_image(self, mock_get, mock_resolve_key, mock_load_config, mock_create_client):
        """Test LLM node execution with image"""
        # Setup mocks
        mock_config = Mock()
        mock_config.provider = "openai"
        mock_config.model = "gpt-4"
        mock_config.name = "Test Config"
        mock_config.id = "test-id"
        mock_load_config.return_value = mock_config
        mock_resolve_key.return_value = "test-api-key"
        
        # Mock image download
        mock_response_img = Mock()
        mock_response_img.content = b'fake_image_data'
        mock_response_img.headers = {'Content-Type': 'image/jpeg'}
        mock_response_img.raise_for_status = Mock()
        mock_get.return_value = mock_response_img
        
        # Mock LLM client
        mock_llm = Mock()
        mock_response = Mock()
        mock_response.content = "Image analyzed"
        mock_llm.ainvoke = Mock(return_value=mock_response)
        mock_create_client.return_value = mock_llm
        
        executor = LLMExecutor()
        result = await executor.execute_llm_node(
            prompt_template="Analyze: {image}",
            inputs={"image": "https://example.com/photo.jpg"},
            config_id="test-config",
            run_id="test-run"
        )
        
        assert result["output"] == "Image analyzed"
        mock_llm.ainvoke.assert_called_once()
        # Verify message content includes image
        call_args = mock_llm.ainvoke.call_args[0][0]
        assert len(call_args) == 1  # One HumanMessage
        message_content = call_args[0].content
        assert any(item.get("type") == "input_image" for item in message_content)

