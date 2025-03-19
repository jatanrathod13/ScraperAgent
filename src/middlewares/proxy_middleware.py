#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Proxy Middleware Module

Provides proxy rotation and management functionality for web crawling:
- Rotate through a list of proxies
- Track proxy health and reliability
- Automatic failover to working proxies
- Support for authenticated proxies
"""

import time
import random
import logging
import threading
import requests
from typing import List, Dict, Optional, Any, Tuple, Set
from collections import defaultdict

# Configure logging
logger = logging.getLogger('proxy_middleware')

class ProxyMiddleware:
    """
    Manages a pool of proxies with automatic rotation and health checking.
    """
    
    def __init__(
        self,
        proxies: Optional[List[str]] = None,
        test_url: str = 'https://httpbin.org/ip',
        max_failures: int = 3,
        health_check_interval: int = 300,  # 5 minutes
        always_test_before_use: bool = False,
        timeout: int = 10,
        retry_delay: int = 60  # 1 minute before retrying a failed proxy
    ):
        """
        Initialize the proxy middleware.
        
        Args:
            proxies: List of proxy URLs (format: "http://user:pass@host:port" or "http://host:port")
            test_url: URL to use for proxy health checks
            max_failures: Maximum number of consecutive failures before marking a proxy as dead
            health_check_interval: Interval between health checks in seconds
            always_test_before_use: Whether to test a proxy before every use
            timeout: Connection timeout for proxy health checks
            retry_delay: Time to wait before retrying a failed proxy
        """
        self.proxies = proxies or []
        self.test_url = test_url
        self.max_failures = max_failures
        self.health_check_interval = health_check_interval
        self.always_test_before_use = always_test_before_use
        self.timeout = timeout
        self.retry_delay = retry_delay
        
        # Proxy states
        self.active_proxies: List[str] = []
        self.dead_proxies: Dict[str, float] = {}  # Proxy -> timestamp when marked dead
        self.failure_counts: Dict[str, int] = defaultdict(int)
        self.last_used: Dict[str, float] = {}
        self.proxy_speeds: Dict[str, float] = {}  # Proxy -> average response time
        
        # Current proxy index for round-robin rotation
        self.current_index = 0
        
        # Thread synchronization
        self.lock = threading.Lock()
        
        # Initialize proxies
        self._initialize_proxies()
        
        # Start health check thread if proxies are provided
        if self.proxies:
            self._start_health_check_thread()
    
    def _initialize_proxies(self) -> None:
        """
        Initialize the proxy list and test all proxies.
        """
        if not self.proxies:
            logger.warning("No proxies provided. Crawling will use direct connections.")
            return
            
        logger.info(f"Initializing {len(self.proxies)} proxies")
        
        # Test all proxies and mark them as active or dead
        for proxy in self.proxies:
            is_working, response_time = self._test_proxy(proxy)
            with self.lock:
                if is_working:
                    self.active_proxies.append(proxy)
                    self.proxy_speeds[proxy] = response_time
                    logger.info(f"Proxy {proxy} is active (response time: {response_time:.2f}s)")
                else:
                    self.dead_proxies[proxy] = time.time()
                    logger.warning(f"Proxy {proxy} is dead")
        
        # Log the results
        log_msg = f"Proxy initialization complete. Active: {len(self.active_proxies)}, Dead: {len(self.dead_proxies)}"
        if self.active_proxies:
            logger.info(log_msg)
        else:
            logger.warning(f"{log_msg}. No working proxies found!")
    
    def _test_proxy(self, proxy: str) -> Tuple[bool, float]:
        """
        Test if a proxy is working.
        
        Args:
            proxy: Proxy URL to test
            
        Returns:
            Tuple of (is_working, response_time)
        """
        proxies = {
            'http': proxy,
            'https': proxy
        }
        
        start_time = time.time()
        try:
            response = requests.get(
                self.test_url,
                proxies=proxies,
                timeout=self.timeout,
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
            )
            response_time = time.time() - start_time
            
            if response.status_code == 200:
                return True, response_time
        except Exception as e:
            logger.debug(f"Proxy test failed for {proxy}: {str(e)}")
        
        return False, time.time() - start_time
    
    def _start_health_check_thread(self) -> None:
        """
        Start a background thread to periodically check proxy health.
        """
        def health_check_loop():
            while True:
                try:
                    self._check_all_proxies()
                    time.sleep(self.health_check_interval)
                except Exception as e:
                    logger.error(f"Error in proxy health check: {str(e)}")
                    time.sleep(60)  # Wait a minute and try again
        
        thread = threading.Thread(target=health_check_loop, daemon=True)
        thread.start()
        logger.info(f"Started proxy health check thread (interval: {self.health_check_interval}s)")
    
    def _check_all_proxies(self) -> None:
        """
        Check the health of all proxies and update their status.
        """
        logger.debug("Starting health check for all proxies")
        
        # Check active proxies
        with self.lock:
            active_proxies = self.active_proxies.copy()
        
        for proxy in active_proxies:
            is_working, response_time = self._test_proxy(proxy)
            with self.lock:
                if not is_working:
                    self.failure_counts[proxy] += 1
                    logger.debug(f"Proxy {proxy} failed health check (failures: {self.failure_counts[proxy]})")
                    
                    if self.failure_counts[proxy] >= self.max_failures:
                        self.active_proxies.remove(proxy)
                        self.dead_proxies[proxy] = time.time()
                        logger.warning(f"Proxy {proxy} marked as dead after {self.failure_counts[proxy]} failures")
                else:
                    # Reset failure count on success
                    self.failure_counts[proxy] = 0
                    # Update speed measurement with exponential moving average
                    if proxy in self.proxy_speeds:
                        self.proxy_speeds[proxy] = 0.7 * self.proxy_speeds[proxy] + 0.3 * response_time
                    else:
                        self.proxy_speeds[proxy] = response_time
        
        # Check if any dead proxies should be retried
        with self.lock:
            dead_to_retry = []
            current_time = time.time()
            
            for proxy, death_time in list(self.dead_proxies.items()):
                if current_time - death_time > self.retry_delay:
                    dead_to_retry.append(proxy)
                    del self.dead_proxies[proxy]
        
        # Retry dead proxies outside the lock
        for proxy in dead_to_retry:
            is_working, response_time = self._test_proxy(proxy)
            with self.lock:
                if is_working:
                    self.active_proxies.append(proxy)
                    self.failure_counts[proxy] = 0
                    self.proxy_speeds[proxy] = response_time
                    logger.info(f"Proxy {proxy} is back online (response time: {response_time:.2f}s)")
                else:
                    self.dead_proxies[proxy] = time.time()
        
        with self.lock:
            logger.debug(f"Health check complete. Active: {len(self.active_proxies)}, Dead: {len(self.dead_proxies)}")
    
    def get_proxy(self, strategy: str = 'round-robin') -> Optional[str]:
        """
        Get a proxy based on the selected strategy.
        
        Args:
            strategy: Selection strategy ('round-robin', 'random', 'fastest')
            
        Returns:
            Proxy URL or None if no proxies are available
        """
        with self.lock:
            # If no active proxies, try to recover dead ones
            if not self.active_proxies:
                self._recover_dead_proxies()
                
                # Still no active proxies
                if not self.active_proxies:
                    logger.warning("No active proxies available")
                    return None
            
            # Select a proxy based on the strategy
            if strategy == 'random':
                proxy = random.choice(self.active_proxies)
            elif strategy == 'fastest':
                # Select the proxy with the lowest response time
                if self.proxy_speeds:
                    proxy = min(
                        [(p, t) for p, t in self.proxy_speeds.items() if p in self.active_proxies],
                        key=lambda x: x[1]
                    )[0]
                else:
                    proxy = self.active_proxies[0]
            else:  # round-robin
                proxy = self.active_proxies[self.current_index]
                self.current_index = (self.current_index + 1) % len(self.active_proxies)
            
            # Test the proxy if required
            should_test = self.always_test_before_use
            if not should_test and proxy in self.last_used:
                # Test if it's been a while since we used this proxy
                time_since_last_use = time.time() - self.last_used[proxy]
                should_test = time_since_last_use > 300  # 5 minutes
            
            # Update last used time
            self.last_used[proxy] = time.time()
            
        # Test outside the lock if needed
        if should_test:
            is_working, _ = self._test_proxy(proxy)
            if not is_working:
                with self.lock:
                    self.failure_counts[proxy] += 1
                    logger.warning(f"Proxy {proxy} failed test (failures: {self.failure_counts[proxy]})")
                    
                    if self.failure_counts[proxy] >= self.max_failures:
                        if proxy in self.active_proxies:
                            self.active_proxies.remove(proxy)
                        self.dead_proxies[proxy] = time.time()
                        logger.warning(f"Proxy {proxy} marked as dead")
                
                # Try another proxy
                return self.get_proxy(strategy)
                
        return proxy
    
    def _recover_dead_proxies(self) -> None:
        """
        Attempt to recover dead proxies.
        """
        # Check if enough time has passed to retry dead proxies
        current_time = time.time()
        recovered = 0
        
        for proxy, death_time in list(self.dead_proxies.items()):
            if current_time - death_time > self.retry_delay:
                # Remove from dead list and test
                del self.dead_proxies[proxy]
                self.failure_counts[proxy] = 0
                is_working, response_time = self._test_proxy(proxy)
                
                if is_working:
                    self.active_proxies.append(proxy)
                    self.proxy_speeds[proxy] = response_time
                    recovered += 1
                    logger.info(f"Recovered proxy {proxy}")
                else:
                    # Still dead, put it back
                    self.dead_proxies[proxy] = current_time
        
        if recovered > 0:
            logger.info(f"Recovered {recovered} proxies")
    
    def report_success(self, proxy: str) -> None:
        """
        Report a successful request with a proxy.
        
        Args:
            proxy: Proxy that was used successfully
        """
        if not proxy:
            return
            
        with self.lock:
            if proxy in self.failure_counts:
                self.failure_counts[proxy] = 0
    
    def report_failure(self, proxy: str) -> None:
        """
        Report a failed request with a proxy.
        
        Args:
            proxy: Proxy that failed
        """
        if not proxy:
            return
            
        with self.lock:
            self.failure_counts[proxy] += 1
            logger.debug(f"Reported failure for proxy {proxy} (failures: {self.failure_counts[proxy]})")
            
            if self.failure_counts[proxy] >= self.max_failures:
                if proxy in self.active_proxies:
                    self.active_proxies.remove(proxy)
                self.dead_proxies[proxy] = time.time()
                logger.warning(f"Proxy {proxy} marked as dead after {self.failure_counts[proxy]} failures")
    
    def add_proxy(self, proxy: str) -> bool:
        """
        Add a new proxy to the pool.
        
        Args:
            proxy: Proxy URL to add
            
        Returns:
            True if the proxy was added successfully
        """
        # Test the proxy first
        is_working, response_time = self._test_proxy(proxy)
        
        with self.lock:
            if proxy in self.active_proxies or proxy in self.dead_proxies:
                logger.warning(f"Proxy {proxy} is already in the pool")
                return False
                
            if is_working:
                self.proxies.append(proxy)
                self.active_proxies.append(proxy)
                self.proxy_speeds[proxy] = response_time
                logger.info(f"Added new proxy {proxy}")
                return True
            else:
                logger.warning(f"Failed to add new proxy {proxy} (not working)")
                return False
                
    def remove_proxy(self, proxy: str) -> bool:
        """
        Remove a proxy from the pool.
        
        Args:
            proxy: Proxy URL to remove
            
        Returns:
            True if the proxy was removed
        """
        with self.lock:
            if proxy in self.proxies:
                self.proxies.remove(proxy)
                
                if proxy in self.active_proxies:
                    self.active_proxies.remove(proxy)
                    
                if proxy in self.dead_proxies:
                    del self.dead_proxies[proxy]
                    
                if proxy in self.failure_counts:
                    del self.failure_counts[proxy]
                    
                if proxy in self.proxy_speeds:
                    del self.proxy_speeds[proxy]
                    
                if proxy in self.last_used:
                    del self.last_used[proxy]
                    
                logger.info(f"Removed proxy {proxy}")
                return True
            else:
                logger.warning(f"Proxy {proxy} not found in the pool")
                return False
    
    def get_proxy_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the proxy pool.
        
        Returns:
            Dictionary with proxy statistics
        """
        with self.lock:
            stats = {
                'total_proxies': len(self.proxies),
                'active_proxies': len(self.active_proxies),
                'dead_proxies': len(self.dead_proxies),
                'fastest_proxy': None,
                'fastest_response_time': float('inf'),
                'slowest_proxy': None,
                'slowest_response_time': 0,
                'average_response_time': 0
            }
            
            # Calculate speed statistics
            if self.proxy_speeds and self.active_proxies:
                active_speeds = {p: t for p, t in self.proxy_speeds.items() if p in self.active_proxies}
                
                if active_speeds:
                    fastest_proxy = min(active_speeds.items(), key=lambda x: x[1])
                    slowest_proxy = max(active_speeds.items(), key=lambda x: x[1])
                    
                    stats['fastest_proxy'] = fastest_proxy[0]
                    stats['fastest_response_time'] = fastest_proxy[1]
                    stats['slowest_proxy'] = slowest_proxy[0]
                    stats['slowest_response_time'] = slowest_proxy[1]
                    stats['average_response_time'] = sum(active_speeds.values()) / len(active_speeds)
            
            return stats 