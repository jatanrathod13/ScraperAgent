#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Rate Limiter Middleware

Provides rate limiting functionality to prevent overloading servers
with too many requests in a short time period. Supports:
- Global rate limiting
- Per-domain rate limiting
- Adaptive rate limiting based on server response
"""

import time
import random
import logging
import threading
from typing import Dict, Optional, Any, List
from collections import defaultdict

# Configure logging
logger = logging.getLogger('rate_limiter')

class RateLimiter:
    """
    Rate limiter that controls the delay between requests
    to prevent overloading servers and avoid being blocked.
    """
    
    def __init__(
        self,
        base_delay: float = 1.0,
        per_domain_rules: Optional[Dict[str, float]] = None,
        min_delay: float = 0.5,
        max_delay: float = 60.0,
        random_delay_range: float = 0.5,
        adaptive_rate_limiting: bool = True,
        retry_delay_factor: int = 2
    ):
        """
        Initialize the rate limiter.
        
        Args:
            base_delay: Base delay between requests in seconds
            per_domain_rules: Dictionary mapping domains to specific delays
            min_delay: Minimum delay allowed
            max_delay: Maximum delay allowed
            random_delay_range: Random factor to add to delay (0-1.0)
            adaptive_rate_limiting: Whether to adjust delays based on server response
            retry_delay_factor: Factor to increase delay by when retrying
        """
        self.base_delay = max(base_delay, min_delay)
        self.per_domain_rules = per_domain_rules or {}
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.random_delay_range = random_delay_range
        self.adaptive_rate_limiting = adaptive_rate_limiting
        self.retry_delay_factor = retry_delay_factor
        
        # Track last request time for each domain
        self.last_request_time: Dict[str, float] = {}
        
        # Track consecutive failures for adaptive rate limiting
        self.consecutive_failures: Dict[str, int] = defaultdict(int)
        
        # For slow down signals from the server
        self.temporary_delays: Dict[str, float] = {}
        
        # Thread synchronization
        self.lock = threading.Lock()
        
        logger.info(f"Rate limiter initialized with base delay of {base_delay}s")
    
    def wait_for_rate_limit(self, domain: str) -> None:
        """
        Wait an appropriate amount of time before making a request to a domain.
        
        Args:
            domain: Domain to wait for
        """
        with self.lock:
            current_time = time.time()
            
            # Get the appropriate delay for this domain
            delay = self._get_delay_for_domain(domain)
            
            # Add randomization to avoid detection
            if self.random_delay_range > 0:
                randomized_delay = delay * (1 + random.uniform(0, self.random_delay_range))
            else:
                randomized_delay = delay
            
            # Calculate time to wait based on last request
            if domain in self.last_request_time:
                time_since_last_request = current_time - self.last_request_time[domain]
                wait_time = max(0, randomized_delay - time_since_last_request)
            else:
                # First request to this domain
                wait_time = randomized_delay * random.uniform(0.2, 0.5)  # Reduced wait for first request
            
            # Update the last request time before waiting
            self.last_request_time[domain] = current_time + wait_time
        
        # Wait outside the lock to allow other threads to proceed
        if wait_time > 0:
            logger.debug(f"Rate limiting: waiting {wait_time:.2f}s for {domain}")
            time.sleep(wait_time)
    
    def _get_delay_for_domain(self, domain: str) -> float:
        """
        Get the appropriate delay for a domain based on rules and adaptive adjustments.
        
        Args:
            domain: Domain to get delay for
            
        Returns:
            Delay in seconds
        """
        # Start with base delay
        delay = self.base_delay
        
        # Check domain-specific rules
        if domain in self.per_domain_rules:
            delay = self.per_domain_rules[domain]
        
        # Check temporary delays (e.g., from 429 responses)
        if domain in self.temporary_delays:
            delay = max(delay, self.temporary_delays[domain])
        
        # Apply adaptive rate limiting if enabled
        if self.adaptive_rate_limiting and domain in self.consecutive_failures:
            failures = self.consecutive_failures[domain]
            if failures > 0:
                # Exponential backoff based on failures
                adaptive_delay = delay * (self.retry_delay_factor ** min(failures, 4))
                delay = min(adaptive_delay, self.max_delay)
        
        # Ensure delay is within bounds
        return max(self.min_delay, min(delay, self.max_delay))
    
    def report_success(self, domain: str) -> None:
        """
        Report a successful request to a domain, potentially reducing future delays.
        
        Args:
            domain: Domain to report success for
        """
        with self.lock:
            # Reset consecutive failures for this domain
            if domain in self.consecutive_failures and self.consecutive_failures[domain] > 0:
                self.consecutive_failures[domain] = 0
                logger.debug(f"Reset failure count for {domain}")
            
            # Clear any temporary delay
            if domain in self.temporary_delays:
                del self.temporary_delays[domain]
    
    def report_failure(self, domain: str, status_code: Optional[int] = None) -> None:
        """
        Report a failed request to a domain, potentially increasing future delays.
        
        Args:
            domain: Domain to report failure for
            status_code: HTTP status code if available
        """
        with self.lock:
            # Increment consecutive failures
            self.consecutive_failures[domain] += 1
            
            # If rate limited (429), apply a longer temporary delay
            if status_code == 429:
                new_delay = self._get_delay_for_domain(domain) * self.retry_delay_factor * 2
                self.temporary_delays[domain] = min(new_delay, self.max_delay)
                logger.warning(f"Rate limit hit for {domain}. Increased delay to {new_delay:.2f}s")
            else:
                failures = self.consecutive_failures[domain]
                logger.debug(f"Recorded failure for {domain} (consecutive: {failures})")
    
    def set_domain_delay(self, domain: str, delay: float) -> None:
        """
        Set a specific delay for a domain.
        
        Args:
            domain: Domain to set delay for
            delay: Delay in seconds
        """
        with self.lock:
            # Ensure delay is within bounds
            bounded_delay = max(self.min_delay, min(delay, self.max_delay))
            self.per_domain_rules[domain] = bounded_delay
            logger.info(f"Set delay for {domain} to {bounded_delay:.2f}s")
    
    def set_temporary_delay(self, domain: str, delay: float, duration: float = 300) -> None:
        """
        Set a temporary delay for a domain with an expiration.
        
        Args:
            domain: Domain to set delay for
            delay: Temporary delay in seconds
            duration: How long to apply the temporary delay in seconds
        """
        with self.lock:
            bounded_delay = max(self.min_delay, min(delay, self.max_delay))
            self.temporary_delays[domain] = bounded_delay
            logger.info(f"Set temporary delay for {domain} to {bounded_delay:.2f}s for {duration:.0f}s")
            
            # Schedule removal of temporary delay (in a non-blocking way)
            def _remove_temp_delay():
                time.sleep(duration)
                with self.lock:
                    if domain in self.temporary_delays and self.temporary_delays[domain] == bounded_delay:
                        del self.temporary_delays[domain]
                        logger.debug(f"Removed temporary delay for {domain}")
            
            threading.Thread(target=_remove_temp_delay, daemon=True).start()
    
    def reset(self) -> None:
        """
        Reset the rate limiter to its initial state.
        """
        with self.lock:
            self.last_request_time.clear()
            self.consecutive_failures.clear()
            self.temporary_delays.clear()
            logger.info("Rate limiter reset to initial state") 