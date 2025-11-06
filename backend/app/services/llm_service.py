#!/usr/bin/env python3
"""
Enhanced LLM Service with improved prompts and multi-stage analysis
"""

from typing import Dict, Optional
from loguru import logger
import requests
import json
import hashlib
import time
import aiohttp
import asyncio
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)

from app.core.config import settings
from app.core.database import get_redis


class EnhancedLLMService:
    """Enhanced AI analysis service with professional structured responses"""

    def __init__(self, db=None):
        self.base_url = settings.LLM_BASE_URL
        self.model = settings.LLM_MODEL
        self.timeout = settings.LLM_TIMEOUT
        self.redis = get_redis()
        self.cache_ttl = 604800  # 7 days in seconds
        self.db = db  # Database session for ML service integration

        # Metrics
        self.cache_hits = 0
        self.cache_misses = 0

    def _generate_cache_key(self, ticket: Dict, stage: str = "full") -> str:
        """Generate cache key from ticket content"""
        # Create hash from subject + description + priority
        content = f"{ticket.get('subject', '')}|{ticket.get('description', '')}|{ticket.get('priority', '')}"
        # Use full SHA-256 hash (64 chars) to prevent collisions
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        return f"llm:cache:{stage}:{content_hash}"

    def _get_cached_analysis(self, cache_key: str) -> Optional[Dict]:
        """Get cached LLM analysis from Redis"""
        try:
            cached = self.redis.get(cache_key)
            if cached:
                self.cache_hits += 1
                logger.debug(f"✅ LLM cache HIT: {cache_key}")
                return json.loads(cached)
            else:
                self.cache_misses += 1
                logger.debug(f"❌ LLM cache MISS: {cache_key}")
                return None
        except Exception as e:
            logger.warning(f"⚠️ Cache read error: {e}")
            return None

    def _cache_analysis(self, cache_key: str, analysis: Dict):
        """Cache LLM analysis in Redis"""
        try:
            self.redis.setex(
                cache_key,
                self.cache_ttl,
                json.dumps(analysis)
            )
            logger.debug(f"💾 Cached LLM response: {cache_key}")
        except Exception as e:
            logger.warning(f"⚠️ Cache write error: {e}")

    def get_cache_stats(self) -> Dict:
        """Get cache performance metrics"""
        total = self.cache_hits + self.cache_misses
        hit_rate = (self.cache_hits / total * 100) if total > 0 else 0
        return {
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "total_requests": total,
            "hit_rate_percent": round(hit_rate, 2)
        }

    def analyze_ticket(self, ticket: Dict, context: Dict = None) -> Dict:
        """
        Multi-stage ticket analysis with Redis caching

        Returns:
            {
                "classification": {...},
                "action_plan": str,
                "initial_response": str,
                "estimated_effort": float,
                "complexity": str,
                "cached": bool
            }
        """
        try:
            # Check cache first
            cache_key = self._generate_cache_key(ticket, "full")
            cached_result = self._get_cached_analysis(cache_key)

            if cached_result:
                cached_result["cached"] = True
                logger.info(f"🚀 Using cached LLM analysis for ticket #{ticket.get('id')}")
                return cached_result

            # Cache miss - perform full analysis
            start_time = time.time()
            logger.info(f"🤖 Performing fresh LLM analysis for ticket #{ticket.get('id')}")

            # Stage 1: Classification
            classification = self._classify_ticket(ticket)

            # Stage 2: Generate action plan
            action_plan = self._generate_action_plan(ticket, classification)

            # Stage 3: Create customer-facing response
            initial_response = self._generate_initial_response(
                ticket,
                classification,
                action_plan
            )

            analysis_time = time.time() - start_time

            result = {
                "classification": classification,
                "action_plan": action_plan,
                "initial_response": initial_response,
                "estimated_effort": classification.get("estimated_hours", 4),
                "complexity": classification.get("complexity", "moderate"),
                "success": True,
                "cached": False,
                "analysis_time": round(analysis_time, 2)
            }

            # Cache the result
            self._cache_analysis(cache_key, result)

            logger.info(f"✅ LLM analysis completed in {analysis_time:.2f}s")
            return result

        except Exception as e:
            logger.error(f"❌ LLM analysis failed: {e}")
            return self._fallback_analysis(ticket)

    def _classify_ticket(self, ticket: Dict) -> Dict:
        """
        Stage 1: Hybrid ML+LLM classification

        Uses ML models for initial prediction, then LLM for validation and enrichment
        """
        from app.services.ml_service import MLPredictionService

        # Step 1: Get ML predictions first (fast, accurate for structured data)
        try:
            ml_service = MLPredictionService(self.db if hasattr(self, 'db') else None)

            # Get ML predictions
            ml_category = ml_service.predict_ticket_category(ticket)
            ml_complexity = ml_service.predict_ticket_complexity(ticket)
            ml_resolution = ml_service.predict_resolution_time(ticket)

            logger.info(
                f"🤖 ML predictions: category={ml_category['category']} "
                f"({ml_category['confidence']:.2f}), "
                f"complexity={ml_complexity['complexity']} "
                f"({ml_complexity['confidence']:.2f}), "
                f"hours={ml_resolution['estimated_hours']}"
            )

            # If ML confidence is high (>0.75), use ML predictions with light LLM validation
            if ml_category['confidence'] > 0.75 and ml_complexity['confidence'] > 0.75:
                logger.info("✨ High ML confidence - using ML predictions with light validation")

                # Quick LLM validation prompt (faster, cheaper)
                prompt = f"""Validate this ML classification and add required skills.

Ticket: {ticket.get('subject', '')}
ML Predictions:
- Category: {ml_category['category']} (confidence: {ml_category['confidence']:.2f})
- Complexity: {ml_complexity['complexity']} (confidence: {ml_complexity['confidence']:.2f})
- Estimated hours: {ml_resolution['estimated_hours']}

Return JSON with:
{{
  "category": "{ml_category['category']}",
  "complexity": "{ml_complexity['complexity']}",
  "estimated_hours": {ml_resolution['estimated_hours']},
  "required_skills": ["skill1", "skill2"],
  "urgency_factors": ["factor1"],
  "similar_patterns": ["pattern1"],
  "ml_confidence_category": {ml_category['confidence']},
  "ml_confidence_complexity": {ml_complexity['confidence']}
}}

Only change category/complexity if ML is clearly wrong. Otherwise, just add skills/factors."""

                try:
                    response = self._call_llm(prompt, temperature=0.2)
                    result = json.loads(response)
                    result['prediction_method'] = 'ml_primary'
                    return result
                except:
                    # If LLM validation fails, use pure ML predictions
                    return {
                        "category": ml_category['category'],
                        "complexity": ml_complexity['complexity'],
                        "estimated_hours": ml_resolution['estimated_hours'],
                        "required_skills": [],
                        "urgency_factors": [],
                        "similar_patterns": [],
                        "ml_confidence_category": ml_category['confidence'],
                        "ml_confidence_complexity": ml_complexity['confidence'],
                        "prediction_method": 'ml_only'
                    }

            # Otherwise, use full LLM classification with ML hints
            else:
                logger.info("📊 Lower ML confidence - using LLM with ML hints")

                prompt = f"""Analyze this DevOps ticket. ML suggests category="{ml_category['category']}" (conf: {ml_category['confidence']:.2f}) and complexity="{ml_complexity['complexity']}" (conf: {ml_complexity['confidence']:.2f}).

Ticket #{ticket.get('id', 'N/A')}
Subject: {ticket.get('subject', '')}
Description: {ticket.get('description', '')}
Environment: {ticket.get('environment', 'unknown')}

Rules:
- category MUST be one of ["kubernetes","database","network","cicd","messaging","storage","application","security","other"]
- complexity MUST be one of ["simple","moderate","complex","critical"]
- Consider ML suggestions but override if clearly wrong
- estimated_hours should be realistic

Return JSON:
{{
  "category": "...",
  "complexity": "...",
  "estimated_hours": <number>,
  "required_skills": ["skill1", "skill2"],
  "urgency_factors": ["factor1"],
  "similar_patterns": ["pattern1"],
  "ml_confidence_category": {ml_category['confidence']},
  "ml_confidence_complexity": {ml_complexity['confidence']}
}}

Respond ONLY with JSON."""

                response = self._call_llm(prompt, temperature=0.3)
                result = json.loads(response)
                result['prediction_method'] = 'llm_primary'
                return result

        except Exception as e:
            logger.warning(f"⚠️ Hybrid classification failed: {e}, falling back to pure LLM")

            # Fallback to original pure LLM approach
            prompt = f"""Analyze this DevOps ticket and provide structured classification.

Ticket #{ticket.get('id', 'N/A')}
Subject: {ticket.get('subject', '')}
Description: {ticket.get('description', '')}
Environment: {ticket.get('environment', 'unknown')}

Rules:
- category MUST be one of ["kubernetes","database","network","cicd","messaging","storage","application","security","other"]
- complexity MUST be one of ["simple","moderate","complex","critical"]
- estimated_hours MUST be positive number

Return JSON:
{{
  "category": "...",
  "complexity": "...",
  "estimated_hours": <number>,
  "required_skills": ["skill1", "skill2"],
  "urgency_factors": ["factor1"],
  "similar_patterns": ["pattern1"]
}}

Respond ONLY with JSON."""

            try:
                response = self._call_llm(prompt, temperature=0.3)
                result = json.loads(response)
                result['prediction_method'] = 'llm_fallback'
                return result
            except:
                # Ultimate fallback
                result = self._rule_based_classification(ticket)
                result['prediction_method'] = 'rule_based'
                return result

    def _generate_action_plan(self, ticket: Dict, classification: Dict) -> str:
        """Stage 2: Generate detailed action plan for engineer"""

        category = classification.get('category', 'other')
        complexity = classification.get('complexity', 'moderate')

        prompt = f"""You are a senior DevOps engineer. Create a detailed action plan for this ticket.

Ticket: #{ticket.get('id')}
Subject: {ticket.get('subject')}
Category: {category}
Complexity: {complexity}
Environment: {ticket.get('environment', 'unknown')}

Generate a professional action plan with:

## 🎯 Immediate Actions (0-15 minutes)
- First 3-5 immediate diagnostic steps

## 🔍 Investigation Steps
- Detailed troubleshooting steps with actual commands
- Expected outputs and what to look for
- Common gotchas

## 📊 Data Collection
- What logs/metrics to gather
- Diagnostic commands to run

## 🛠️ Resolution Approach
- Step-by-step resolution plan
- Rollback strategy if needed

## ⏱️ Time Estimate
- Estimated time with breakdown

Use category-appropriate commands (e.g. kubectl/helm for Kubernetes, gitlab/jenkins CLI for CI/CD, psql/mysql for databases) and never use placeholders.
Close with a brief summary of success criteria.
Format in clear markdown.
"""

        return self._call_llm(prompt, temperature=0.7)

    def _generate_initial_response(
        self,
        ticket: Dict,
        classification: Dict,
        action_plan: str
    ) -> str:
        """Stage 3: Generate customer-facing initial response"""

        prompt = f"""Generate a professional customer-facing initial response for this DevOps ticket.

Ticket: #{ticket.get('id')}
Subject: {ticket.get('subject')}
Category: {classification.get('category')}
Priority: {ticket.get('priority', 'P3(Medium)')}
Requester Name: {ticket.get('requestor_name', 'Valued Customer')}

Create a professional support response with:

1. Begin with 'Dear REQUESTER_NAME,' exactly (replace REQUESTER_NAME with the provided requester name, include the comma).
2. Concise acknowledgment of the request.
3. Initial assessment using information from the ticket.
4. Any additional information needed (only if relevant):
   - Business Impact: Does this affect operations/users/revenue?
   - Error Details: Specific error messages or symptoms
   - Recent Changes: Any recent deployments/changes?
   - Timeline: When did this start?

5. Next steps and expected timeline (without promising exact resolution times unless obvious).
6. Close with exactly:
   Best regards,
   DevOps Automation Team

Formatting rules:
- Do not begin with phrases like "Certainly!" or "Sure!".
- Keep under 280 words.
- Use plain paragraphs or short bullet lists where appropriate.
- Do not include placeholders like [Your Name] or [Contact Information].
- Maintain a confident, supportive tone without sounding scripted.
"""

        return self._call_llm(prompt, temperature=0.7)

    def _call_llm(self, prompt: str, temperature: float = 0.7) -> str:
        """
        Call local LLM API (synchronous)
        Maintained for backward compatibility
        """
        try:
            # Run async version in sync context
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(self._call_llm_async(prompt, temperature))
            loop.close()
            return result
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return ""

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError)),
        before_sleep=before_sleep_log(logger, logger.level("WARNING").no)
    )
    async def _call_llm_async(self, prompt: str, temperature: float = 0.7) -> str:
        """
        Call local LLM API asynchronously with retry logic

        Retries: 3 attempts with exponential backoff (1s, 2s, 4s)
        Retries on: Network errors, timeouts
        """
        try:
            url = f"{self.base_url}/completions"

            payload = {
                "model": self.model,
                "prompt": prompt,
                "temperature": temperature,
                "max_tokens": settings.LLM_MAX_TOKENS,
                "stop": ["Human:", "User:"]
            }

            timeout = aiohttp.ClientTimeout(total=self.timeout)

            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, json=payload) as response:
                    if response.status == 200:
                        result = await response.json()

                        # Extract response based on API format
                        if 'choices' in result:
                            return result['choices'][0]['text'].strip()
                        elif 'response' in result:
                            return result['response'].strip()
                        else:
                            return result.get('text', '').strip()
                    elif response.status >= 500:
                        # Server error - should retry
                        logger.warning(f"LLM API server error: {response.status} - will retry")
                        raise aiohttp.ClientError(f"Server error: {response.status}")
                    else:
                        # Client error (4xx) - don't retry
                        logger.error(f"LLM API client error: {response.status}")
                        return ""

        except asyncio.TimeoutError as e:
            logger.warning(f"LLM API timeout after {self.timeout}s - will retry")
            raise  # Let tenacity handle retry
        except aiohttp.ClientError as e:
            logger.warning(f"LLM network error: {e} - will retry")
            raise  # Let tenacity handle retry
        except Exception as e:
            # Unexpected error - don't retry
            logger.error(f"LLM async call failed with unexpected error: {e}")
            return ""

    async def analyze_ticket_async(self, ticket: Dict, context: Dict = None) -> Dict:
        """
        Async version of analyze_ticket for better performance
        Uses concurrent execution of all 3 stages
        """
        try:
            # Check cache first
            cache_key = self._generate_cache_key(ticket, "full")
            cached_result = self._get_cached_analysis(cache_key)

            if cached_result:
                cached_result["cached"] = True
                logger.info(f"🚀 Using cached LLM analysis for ticket #{ticket.get('id')}")
                return cached_result

            # Cache miss - perform all 3 stages concurrently
            start_time = time.time()
            logger.info(f"🤖 Performing async LLM analysis for ticket #{ticket.get('id')}")

            # Run all stages in parallel
            classification_task = self._classify_ticket_async(ticket)

            # Wait for classification first (needed for other stages)
            classification = await classification_task

            # Now run action plan and response in parallel
            action_plan_task = self._generate_action_plan_async(ticket, classification)
            response_task = self._generate_initial_response_async(
                ticket,
                classification,
                None  # Will be populated after action_plan completes
            )

            action_plan, initial_response = await asyncio.gather(
                action_plan_task,
                response_task
            )

            analysis_time = time.time() - start_time

            result = {
                "classification": classification,
                "action_plan": action_plan,
                "initial_response": initial_response,
                "estimated_effort": classification.get("estimated_hours", 4),
                "complexity": classification.get("complexity", "moderate"),
                "success": True,
                "cached": False,
                "analysis_time": round(analysis_time, 2),
                "async": True
            }

            # Cache the result
            self._cache_analysis(cache_key, result)

            logger.info(f"✅ Async LLM analysis completed in {analysis_time:.2f}s")
            return result

        except Exception as e:
            logger.error(f"❌ Async LLM analysis failed: {e}")
            return self._fallback_analysis(ticket)

    async def _classify_ticket_async(self, ticket: Dict) -> Dict:
        """Async version of _classify_ticket"""
        prompt = f"""Analyze this DevOps ticket and provide structured classification.

Ticket #{ticket.get('id', 'N/A')}
Subject: {ticket.get('subject', '')}
Description: {ticket.get('description', '')}
Environment: {ticket.get('environment', 'unknown')}

Classify into JSON format:
{{
  "category": "kubernetes|database|network|cicd|messaging|storage|application|security|other",
  "complexity": "simple|moderate|complex|critical",
  "estimated_hours": <number>,
  "required_skills": ["skill1", "skill2"],
  "urgency_factors": ["factor1", "factor2"],
  "similar_patterns": ["pattern1"]
}}

Respond ONLY with valid JSON, no markdown.
"""

        try:
            response = await self._call_llm_async(prompt, temperature=0.3)
            result = json.loads(response)
            return result
        except:
            return self._rule_based_classification(ticket)

    async def _generate_action_plan_async(self, ticket: Dict, classification: Dict) -> str:
        """Async version of _generate_action_plan"""
        category = classification.get('category', 'other')
        complexity = classification.get('complexity', 'moderate')

        prompt = f"""You are a senior DevOps engineer. Create a detailed action plan for this ticket.

Ticket: #{ticket.get('id')}
Subject: {ticket.get('subject')}
Category: {category}
Complexity: {complexity}
Environment: {ticket.get('environment', 'unknown')}

Generate a professional action plan with:

## 🎯 Immediate Actions (0-15 minutes)
- First 3-5 immediate diagnostic steps

## 🔍 Investigation Steps
- Detailed troubleshooting steps with actual commands
- Expected outputs and what to look for
- Common gotchas

## 📊 Data Collection
- What logs/metrics to gather
- Diagnostic commands to run

## 🛠️ Resolution Approach
- Step-by-step resolution plan
- Rollback strategy if needed

## ⏱️ Time Estimate
- Estimated time with breakdown

Use category-appropriate commands (e.g. kubectl/helm for Kubernetes, gitlab/jenkins CLI for CI/CD, psql/mysql for databases) and never use placeholders.
Close with a brief summary of success criteria.
Format in clear markdown.
"""

        return await self._call_llm_async(prompt, temperature=0.7)

    async def _generate_initial_response_async(
        self,
        ticket: Dict,
        classification: Dict,
        action_plan: str
    ) -> str:
        """Async version of _generate_initial_response"""
        prompt = f"""Generate a professional customer-facing initial response for this DevOps ticket.

Ticket: #{ticket.get('id')}
Subject: {ticket.get('subject')}
Category: {classification.get('category')}
Priority: {ticket.get('priority', 'P3(Medium)')}
Requester Name: {ticket.get('requestor_name', 'Valued Customer')}

Create a professional support response with:

1. Begin with 'Dear REQUESTER_NAME,' exactly (replace REQUESTER_NAME with the provided requester name, include the comma).
2. Concise acknowledgment of the request.
3. Initial assessment using information from the ticket.
4. Any additional information needed (only if relevant):
   - Business Impact: Does this affect operations/users/revenue?
   - Error Details: Specific error messages or symptoms
   - Recent Changes: Any recent deployments/changes?
   - Timeline: When did this start?

5. Next steps and expected timeline (without promising exact resolution times unless obvious).
6. Close with exactly:
   Best regards,
   DevOps Automation Team

Formatting rules:
- Do not begin with phrases like "Certainly!" or "Sure!".
- Keep under 280 words.
- Use plain paragraphs or short bullet lists where appropriate.
- Do not include placeholders like [Your Name] or [Contact Information].
- Maintain a confident, supportive tone without sounding scripted.
"""

        return await self._call_llm_async(prompt, temperature=0.7)

    def _rule_based_classification(self, ticket: Dict) -> Dict:
        """Fallback rule-based classification"""
        subject = ticket.get('subject', '').lower()
        description = ticket.get('description', '').lower()
        text = subject + ' ' + description

        # Category detection
        category_keywords = {
            'kubernetes': ['kubernetes', 'k8s', 'pod', 'deployment', 'namespace', 'helm'],
            'database': ['database', 'db', 'sql', 'mysql', 'postgres', 'mongo'],
            'network': ['network', 'connectivity', 'firewall', 'dns', 'port'],
            'cicd': ['pipeline', 'build', 'deploy', 'gitlab', 'jenkins'],
            'messaging': ['rabbitmq', 'kafka', 'queue', 'message'],
            'storage': ['storage', 'volume', 'disk', 'nfs', 'pvc'],
            'application': ['application', 'app', 'service', 'api'],
            'security': ['security', 'ssl', 'certificate', 'auth'],
        }

        category = 'other'
        for cat, keywords in category_keywords.items():
            if any(kw in text for kw in keywords):
                category = cat
                break

        # Complexity estimation
        complexity = 'moderate'
        if any(word in text for word in ['critical', 'down', 'outage', 'production']):
            complexity = 'complex'
        elif any(word in text for word in ['simple', 'quick', 'minor']):
            complexity = 'simple'

        # Estimated hours
        complexity_hours = {
            'simple': 1.0,
            'moderate': 4.0,
            'complex': 8.0,
            'critical': 12.0
        }

        return {
            "category": category,
            "complexity": complexity,
            "estimated_hours": complexity_hours[complexity],
            "required_skills": [category],
            "urgency_factors": [],
            "similar_patterns": []
        }

    def _fallback_analysis(self, ticket: Dict) -> Dict:
        """Complete fallback when LLM is unavailable"""
        classification = self._rule_based_classification(ticket)
        requester = ticket.get("requestor_name", "Customer")

        fallback_response = (
            f"Dear {requester},\n\n"
            "Thank you for contacting the DevOps support team. We have received your ticket "
            f"and will investigate the reported {classification['category']} issue immediately.\n\n"
            "To help us move faster, please share any additional error messages, recent changes, or specific impact "
            "details you have observed.\n\n"
            "Next steps: One of our engineers will review the ticket and provide an update shortly. "
            "We’ll keep you informed as we progress.\n\n"
            "Best regards,\n"
            "DevOps Automation Team"
        )

        return {
            "classification": classification,
            "action_plan": "Detailed action plan will be provided by assigned engineer.",
            "initial_response": fallback_response,
            "estimated_effort": classification["estimated_hours"],
            "complexity": classification["complexity"],
            "success": False,
            "fallback": True
        }

    def generate_escalation_summary(self, ticket: Dict, history: list) -> str:
        """Generate escalation summary for L2/L3"""
        prompt = f"""Generate a concise escalation summary for L2/L3 engineer.

Ticket #{ticket.get('id')}: {ticket.get('subject')}

Previous Actions Taken:
{json.dumps(history, indent=2)}

Create a brief summary (150 words) with:
- What's been tried
- Current status
- Why escalation needed
- Recommended next steps

Be concise and technical."""

        summary = self._call_llm(prompt, temperature=0.5)
        return summary or "Escalated for advanced troubleshooting."

    def suggest_similar_resolutions(self, ticket: Dict, similar_tickets: list) -> str:
        """Suggest resolutions based on similar past tickets"""
        if not similar_tickets:
            return ""

        prompt = f"""Based on similar resolved tickets, suggest resolution approach.

Current Ticket: {ticket.get('subject')}

Similar Past Resolutions:
{json.dumps(similar_tickets, indent=2)}

Provide:
- Most likely root cause
- Recommended solution
- Time estimate
- Confidence level

Keep under 200 words."""

        return self._call_llm(prompt, temperature=0.6)
