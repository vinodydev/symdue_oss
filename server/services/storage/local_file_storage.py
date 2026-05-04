"""
Local file system storage backend.
"""
from typing import Dict, Any, List, Optional, Union
import os
import json
import hashlib
from pathlib import Path
import mimetypes

from services.storage.base import StorageBackend


class LocalFileStorage(StorageBackend):
    """Local file system storage"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.base_path = config.get("base_path", "/app/storage/files")
        self.base_url = config.get("base_url", "http://localhost:8000/files")
        self._ensure_directory()
    
    def _ensure_directory(self) -> None:
        """Ensure base directory exists"""
        Path(self.base_path).mkdir(parents=True, exist_ok=True)
    
    def initialize(self) -> None:
        """Initialize local file storage"""
        self._ensure_directory()
        self._initialized = True
    
    def store(
        self, 
        key: str, 
        value: Any, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Store value as file"""
        if not self._initialized:
            self.initialize()
        
        file_path = Path(self.base_path) / key
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Convert value to bytes
        if isinstance(value, bytes):
            file_path.write_bytes(value)
        elif isinstance(value, str):
            file_path.write_text(value, encoding='utf-8')
        else:
            # Serialize as JSON
            file_path.write_text(json.dumps(value), encoding='utf-8')
        
        # Store metadata if provided
        if metadata:
            meta_path = file_path.with_suffix(file_path.suffix + '.meta')
            meta_path.write_text(json.dumps(metadata), encoding='utf-8')
        
        return key
    
    def retrieve(self, key: str) -> Optional[Any]:
        """Retrieve value from file"""
        if not self._initialized:
            self.initialize()
        
        file_path = Path(self.base_path) / key
        if not file_path.exists():
            return None
        
        # Try to read as text first, then as bytes
        try:
            return file_path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            return file_path.read_bytes()
    
    def search(
        self, 
        query: Union[str, List[float]], 
        limit: int = 10,
        metadata_filter: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Search files (simple text matching)"""
        if not self._initialized:
            self.initialize()
        
        query_str = str(query).lower()
        results = []
        
        for file_path in Path(self.base_path).rglob("*"):
            if file_path.is_file() and not file_path.name.endswith('.meta'):
                try:
                    content = file_path.read_text(encoding='utf-8', errors='ignore')
                    if query_str in content.lower():
                        key = str(file_path.relative_to(Path(self.base_path)))
                        results.append({
                            "key": key,
                            "value": content,
                            "metadata": {},
                            "score": 1.0
                        })
                        if len(results) >= limit:
                            break
                except Exception:
                    continue
        
        return results
    
    def delete(self, key: str) -> bool:
        """Delete file"""
        if not self._initialized:
            self.initialize()
        
        file_path = Path(self.base_path) / key
        if file_path.exists():
            file_path.unlink()
            # Also delete metadata file if exists
            meta_path = file_path.with_suffix(file_path.suffix + '.meta')
            if meta_path.exists():
                meta_path.unlink()
            return True
        return False
    
    def list_keys(self, prefix: Optional[str] = None) -> List[str]:
        """List all file keys"""
        if not self._initialized:
            self.initialize()
        
        base = Path(self.base_path)
        keys = []
        
        for file_path in base.rglob("*"):
            if file_path.is_file() and not file_path.name.endswith('.meta'):
                key = str(file_path.relative_to(base))
                if prefix is None or key.startswith(prefix):
                    keys.append(key)
        
        return keys
    
    def upload_file(
        self,
        file_data: bytes,
        file_name: str,
        content_type: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Upload a file and return storage key"""
        if not self._initialized:
            self.initialize()
        
        # Generate key from filename and hash
        file_hash = hashlib.md5(file_data).hexdigest()[:8]
        key = f"{file_hash}_{file_name}"
        
        file_path = Path(self.base_path) / key
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(file_data)
        
        # Store metadata
        if metadata:
            metadata['original_filename'] = file_name
            metadata['content_type'] = content_type
            meta_path = file_path.with_suffix(file_path.suffix + '.meta')
            meta_path.write_text(json.dumps(metadata), encoding='utf-8')
        
        return key
    
    def download_file(self, key: str) -> tuple[bytes, str]:
        """Download file by key"""
        if not self._initialized:
            self.initialize()
        
        file_path = Path(self.base_path) / key
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {key}")
        
        file_data = file_path.read_bytes()
        
        # Try to get content type from metadata or guess from extension
        meta_path = file_path.with_suffix(file_path.suffix + '.meta')
        content_type = "application/octet-stream"
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding='utf-8'))
                content_type = meta.get('content_type', content_type)
            except Exception:
                pass
        
        if content_type == "application/octet-stream":
            content_type, _ = mimetypes.guess_type(str(file_path))
            content_type = content_type or "application/octet-stream"
        
        return file_data, content_type
    
    def get_file_url(self, key: str, expires_in: Optional[int] = None) -> str:
        """Get file URL"""
        # For local file storage, return a simple URL
        # In production, you might want to serve files through a web server
        return f"{self.base_url}/{key}"
    
    def close(self) -> None:
        """Close local file storage (no-op)"""
        pass

