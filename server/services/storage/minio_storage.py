# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Symdue contributors
"""
MinIO/S3-compatible storage backend.
"""
from typing import Dict, Any, List, Optional, Union
import boto3
from botocore.exceptions import ClientError
from botocore.config import Config
import json
import hashlib

from services.storage.base import StorageBackend


class MinIOStorage(StorageBackend):
    """MinIO/S3-compatible file storage"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.endpoint = config.get("endpoint")
        self.access_key = config.get("access_key")
        self.secret_key = config.get("secret_key")
        self.bucket_name = config.get("bucket_name", "graphmind-files")
        self.region = config.get("region", "us-east-1")
        self.use_ssl = config.get("use_ssl", False)
        self.client = None
    
    def initialize(self) -> None:
        """Initialize MinIO/S3 client"""
        if self._initialized:
            return
        
        if not self.endpoint or not self.access_key or not self.secret_key:
            raise ValueError("MinIO endpoint, access_key, and secret_key are required")
        
        # Create S3 client
        self.client = boto3.client(
            's3',
            endpoint_url=self.endpoint,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name=self.region,
            use_ssl=self.use_ssl,
            config=Config(signature_version='s3v4')
        )
        
        # Ensure bucket exists
        try:
            self.client.head_bucket(Bucket=self.bucket_name)
        except ClientError:
            # Bucket doesn't exist, create it
            self.client.create_bucket(Bucket=self.bucket_name)
        
        self._initialized = True
    
    def store(
        self, 
        key: str, 
        value: Any, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Store value as file in S3"""
        if not self._initialized:
            self.initialize()
        
        # Convert value to bytes
        if isinstance(value, bytes):
            file_data = value
        elif isinstance(value, str):
            file_data = value.encode('utf-8')
        else:
            file_data = json.dumps(value).encode('utf-8')
        
        # Upload to S3
        extra_args = {}
        if metadata:
            extra_args['Metadata'] = {k: str(v) for k, v in metadata.items()}
        
        self.client.put_object(
            Bucket=self.bucket_name,
            Key=key,
            Body=file_data,
            **extra_args
        )
        
        return key
    
    def retrieve(self, key: str) -> Optional[Any]:
        """Retrieve value from S3"""
        if not self._initialized:
            self.initialize()
        
        try:
            response = self.client.get_object(Bucket=self.bucket_name, Key=key)
            data = response['Body'].read()
            
            # Try to decode as text/JSON
            try:
                return json.loads(data.decode('utf-8'))
            except (json.JSONDecodeError, UnicodeDecodeError):
                return data
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                return None
            raise
    
    def search(
        self, 
        query: Union[str, List[float]], 
        limit: int = 10,
        metadata_filter: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Search files in S3 (simple prefix matching)"""
        if not self._initialized:
            self.initialize()
        
        query_str = str(query)
        results = []
        
        # List objects with prefix
        paginator = self.client.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=self.bucket_name, Prefix=query_str)
        
        for page in pages:
            if 'Contents' not in page:
                continue
            for obj in page['Contents']:
                key = obj['Key']
                value = self.retrieve(key)
                if value:
                    results.append({
                        "key": key,
                        "value": value,
                        "metadata": {},
                        "score": 1.0
                    })
                    if len(results) >= limit:
                        return results
        
        return results
    
    def delete(self, key: str) -> bool:
        """Delete object from S3"""
        if not self._initialized:
            self.initialize()
        
        try:
            self.client.delete_object(Bucket=self.bucket_name, Key=key)
            return True
        except ClientError:
            return False
    
    def list_keys(self, prefix: Optional[str] = None) -> List[str]:
        """List all keys (optionally filtered by prefix)"""
        if not self._initialized:
            self.initialize()
        
        keys = []
        paginator = self.client.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=self.bucket_name, Prefix=prefix or '')
        
        for page in pages:
            if 'Contents' not in page:
                continue
            for obj in page['Contents']:
                keys.append(obj['Key'])
        
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
        
        # Prepare metadata
        s3_metadata = {}
        if metadata:
            s3_metadata = {k: str(v) for k, v in metadata.items()}
        
        # Upload to S3
        self.client.put_object(
            Bucket=self.bucket_name,
            Key=key,
            Body=file_data,
            ContentType=content_type,
            Metadata=s3_metadata
        )
        
        return key
    
    def download_file(self, key: str) -> tuple[bytes, str]:
        """Download file by key"""
        if not self._initialized:
            self.initialize()
        
        try:
            response = self.client.get_object(Bucket=self.bucket_name, Key=key)
            file_data = response['Body'].read()
            content_type = response.get('ContentType', 'application/octet-stream')
            return file_data, content_type
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                raise FileNotFoundError(f"File not found: {key}")
            raise
    
    def get_file_url(self, key: str, expires_in: Optional[int] = None) -> str:
        """Get file URL (with optional expiration for signed URLs)"""
        if not self._initialized:
            self.initialize()
        
        if expires_in:
            # Generate presigned URL
            url = self.client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': key},
                ExpiresIn=expires_in
            )
        else:
            # Public URL (if bucket is public)
            url = f"{self.endpoint}/{self.bucket_name}/{key}"
        
        return url
    
    def close(self) -> None:
        """Close S3 client (no-op)"""
        pass

