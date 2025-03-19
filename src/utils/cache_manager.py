#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Cache Manager Module

Provides a cache system for HTTP responses to reduce duplicate requests
and improve crawler performance.
"""

import os
import json
import time
import hashlib
import pickle
import logging
from typing import Optional, Dict, Any, Union
from datetime import datetime, timedelta
import requests
from requests.models import Response

# Configure logging
logger = logging.getLogger('cache_manager')

class CacheManager:
    """
    Manages caching of HTTP responses to prevent duplicate requests.
    """
    
    def __init__(
        self,
        enabled: bool = True,
        expiry: int = 3600,  # Default 1 hour in seconds
        max_size: int = 1000,  # Maximum number of items in cache
        cache_dir: str = '.cache'
    ):
        """
        Initialize the cache manager.
        
        Args:
            enabled: Whether caching is enabled
            expiry: Time in seconds until cache entries expire
            max_size: Maximum number of items in memory cache
            cache_dir: Directory for persistent cache storage
        """
        self.enabled = enabled
        self.expiry = expiry
        self.max_size = max_size
        self.cache_dir = cache_dir
        
        # In-memory cache for faster access
        self.memory_cache: Dict[str, Dict[str, Any]] = {}
        
        # Ensure cache directory exists
        if enabled and cache_dir:
            os.makedirs(cache_dir, exist_ok=True)
            
        logger.info(f"Cache manager initialized. Enabled: {enabled}, Expiry: {expiry}s, Dir: {cache_dir}")
    
    def _get_cache_key(self, url: str) -> str:
        """
        Generate a cache key from a URL.
        
        Args:
            url: URL to generate key for
            
        Returns:
            Cache key string
        """
        # Create a hash of the URL for the cache key
        return hashlib.md5(url.encode()).hexdigest()
    
    def _get_cache_file_path(self, cache_key: str) -> str:
        """
        Get the file path for a cache key.
        
        Args:
            cache_key: Cache key
            
        Returns:
            Path to cache file
        """
        return os.path.join(self.cache_dir, f"{cache_key}.pkl")
    
    def get_response(self, url: str) -> Optional[Response]:
        """
        Get a cached response for a URL if available and not expired.
        
        Args:
            url: URL to get cached response for
            
        Returns:
            Cached response or None if not available
        """
        if not self.enabled:
            return None
        
        cache_key = self._get_cache_key(url)
        
        # Check memory cache first
        if cache_key in self.memory_cache:
            cache_entry = self.memory_cache[cache_key]
            
            # Check if the entry has expired
            if time.time() - cache_entry['timestamp'] <= self.expiry:
                logger.debug(f"Cache hit (memory): {url}")
                return cache_entry['response']
            else:
                # Remove expired entry from memory cache
                del self.memory_cache[cache_key]
        
        # Check disk cache
        cache_file = self._get_cache_file_path(cache_key)
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'rb') as f:
                    cache_entry = pickle.load(f)
                
                # Check if the entry has expired
                if time.time() - cache_entry['timestamp'] <= self.expiry:
                    # Add to memory cache for faster future access
                    self.memory_cache[cache_key] = cache_entry
                    self._manage_cache_size()
                    
                    logger.debug(f"Cache hit (disk): {url}")
                    return cache_entry['response']
                else:
                    # Remove expired cache file
                    os.remove(cache_file)
                    logger.debug(f"Removed expired cache entry: {url}")
            except Exception as e:
                logger.warning(f"Error reading cache for {url}: {e}")
                # Remove corrupted cache file
                if os.path.exists(cache_file):
                    os.remove(cache_file)
        
        return None
    
    def cache_response(self, url: str, response: Response) -> None:
        """
        Cache a response for a URL.
        
        Args:
            url: URL the response is for
            response: Response object to cache
        """
        if not self.enabled:
            return
        
        # Only cache successful responses
        if response.status_code != 200:
            return
        
        # Check cache control headers
        cache_control = response.headers.get('Cache-Control', '').lower()
        if 'no-store' in cache_control or 'no-cache' in cache_control:
            logger.debug(f"Skipping cache due to Cache-Control headers: {url}")
            return
        
        # Create cache entry
        cache_key = self._get_cache_key(url)
        cache_entry = {
            'url': url,
            'timestamp': time.time(),
            'response': response
        }
        
        # Add to memory cache
        self.memory_cache[cache_key] = cache_entry
        self._manage_cache_size()
        
        # Save to disk cache
        cache_file = self._get_cache_file_path(cache_key)
        try:
            with open(cache_file, 'wb') as f:
                pickle.dump(cache_entry, f)
            logger.debug(f"Cached response for: {url}")
        except Exception as e:
            logger.warning(f"Error caching response for {url}: {e}")
    
    def _manage_cache_size(self) -> None:
        """
        Manage the in-memory cache size by removing least recently used entries.
        """
        if len(self.memory_cache) <= self.max_size:
            return
        
        # Remove oldest entries until we're under the limit
        entries = sorted(
            self.memory_cache.items(),
            key=lambda x: x[1]['timestamp']
        )
        
        # Keep only the newest max_size entries
        to_remove = entries[:len(entries) - self.max_size]
        for key, _ in to_remove:
            del self.memory_cache[key]
    
    def clear_cache(self) -> None:
        """
        Clear all cached responses from both memory and disk.
        """
        # Clear memory cache
        self.memory_cache.clear()
        
        # Clear disk cache
        if os.path.exists(self.cache_dir):
            for filename in os.listdir(self.cache_dir):
                if filename.endswith('.pkl'):
                    try:
                        os.remove(os.path.join(self.cache_dir, filename))
                    except Exception as e:
                        logger.warning(f"Error removing cache file {filename}: {e}")
        
        logger.info("Cache cleared")
    
    def clear_expired(self) -> int:
        """
        Clear only expired cache entries.
        
        Returns:
            Number of expired entries removed
        """
        if not self.enabled:
            return 0
        
        count = 0
        current_time = time.time()
        
        # Clear expired entries from memory cache
        for key in list(self.memory_cache.keys()):
            if current_time - self.memory_cache[key]['timestamp'] > self.expiry:
                del self.memory_cache[key]
                count += 1
        
        # Clear expired entries from disk cache
        if os.path.exists(self.cache_dir):
            for filename in os.listdir(self.cache_dir):
                if filename.endswith('.pkl'):
                    file_path = os.path.join(self.cache_dir, filename)
                    try:
                        with open(file_path, 'rb') as f:
                            cache_entry = pickle.load(f)
                        
                        if current_time - cache_entry['timestamp'] > self.expiry:
                            os.remove(file_path)
                            count += 1
                    except Exception as e:
                        # Remove corrupted files
                        logger.warning(f"Error checking cache file {filename}: {e}")
                        try:
                            os.remove(file_path)
                            count += 1
                        except:
                            pass
        
        logger.info(f"Cleared {count} expired cache entries")
        return count
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the cache.
        
        Returns:
            Dictionary with cache statistics
        """
        if not self.enabled:
            return {"enabled": False}
        
        # Count disk cache entries
        disk_count = 0
        disk_size = 0
        if os.path.exists(self.cache_dir):
            for filename in os.listdir(self.cache_dir):
                if filename.endswith('.pkl'):
                    file_path = os.path.join(self.cache_dir, filename)
                    disk_count += 1
                    disk_size += os.path.getsize(file_path)
        
        return {
            "enabled": True,
            "memory_entries": len(self.memory_cache),
            "disk_entries": disk_count,
            "disk_size_bytes": disk_size,
            "max_age_seconds": self.expiry,
            "cache_dir": self.cache_dir
        } 