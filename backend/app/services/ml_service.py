#!/usr/bin/env python3
"""
ML Service for smart routing, predictions, and analytics
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from loguru import logger
import numpy as np
from sqlalchemy.orm import Session

try:
    from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.preprocessing import LabelEncoder
    import joblib
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    logger.warning("⚠️ ML libraries not available - using fallback logic")

from app.models.team import TeamMember, Skill
from app.models.ticket import TicketHistory, TicketCategory, TicketStatus
from app.core.config import settings


class MLPredictionService:
    """Machine Learning service for intelligent ticket routing and predictions"""

    def __init__(self, db: Session):
        self.db = db
        self.models_path = settings.ML_MODELS_PATH
        self.ml_enabled = ML_AVAILABLE and settings.ML_TRAINING_ENABLED

        # Load or initialize models
        self.category_classifier = None
        self.complexity_predictor = None
        self.effort_predictor = None
        self.sla_breach_predictor = None
        self.assignment_recommender = None

        if self.ml_enabled:
            self._load_models()

    def smart_route_ticket(
        self,
        ticket: Dict,
        available_members: List[TeamMember],
        ticket_category: str = None
    ) -> Tuple[TeamMember, float, List[str]]:
        """
        Smart routing with ML-based skill matching, timezone awareness, and workload balancing

        Returns:
            (best_assignee, confidence_score, reasons)
        """
        if not available_members:
            return None, 0.0, ["No available members"]

        if self.ml_enabled and self.assignment_recommender:
            return self._ml_based_routing(ticket, available_members, ticket_category)
        else:
            return self._rule_based_routing(ticket, available_members, ticket_category)

    def _ml_based_routing(
        self,
        ticket: Dict,
        available_members: List[TeamMember],
        ticket_category: str
    ) -> Tuple[TeamMember, float, List[str]]:
        """ML-based intelligent routing"""
        try:
            scores = {}

            for member in available_members:
                # Calculate multi-factor score
                skill_score = self._calculate_skill_match(member, ticket_category)
                timezone_score = self._calculate_timezone_score(member, ticket)
                workload_score = self._calculate_workload_score(member)
                performance_score = self._calculate_performance_score(member, ticket_category)

                # Weighted combination
                combined_score = (
                    skill_score * 0.40 +
                    timezone_score * 0.20 +
                    workload_score * 0.20 +
                    performance_score * 0.20
                )

                scores[member.id] = {
                    'score': combined_score,
                    'member': member,
                    'breakdown': {
                        'skill': skill_score,
                        'timezone': timezone_score,
                        'workload': workload_score,
                        'performance': performance_score
                    }
                }

            # Get best assignee
            best_id = max(scores.keys(), key=lambda k: scores[k]['score'])
            best = scores[best_id]

            # Generate reasons
            reasons = self._generate_assignment_reasons(best['breakdown'], best['member'])

            return best['member'], best['score'], reasons

        except Exception as e:
            logger.error(f"❌ ML routing failed: {e}")
            return self._rule_based_routing(ticket, available_members, ticket_category)

    def _calculate_skill_match(self, member: TeamMember, category: str) -> float:
        """Calculate skill match score (0-1)"""
        if not category:
            return 0.5

        # Check if member has this skill
        member_skills = [skill.name.lower() for skill in member.skills]
        category_lower = category.lower()

        # Exact match
        if category_lower in member_skills:
            # Get proficiency level if available
            return 0.9  # High score for exact match

        # Partial match (related skills)
        related_skills = {
            'kubernetes': ['docker', 'container', 'orchestration'],
            'database': ['sql', 'postgres', 'mysql', 'mongodb'],
            'cicd': ['gitlab', 'jenkins', 'github actions'],
            'messaging': ['rabbitmq', 'kafka', 'redis'],
        }

        if category_lower in related_skills:
            for related in related_skills[category_lower]:
                if related in member_skills:
                    return 0.6  # Medium score for related skill

        return 0.3  # Default low score

    def _calculate_timezone_score(self, member: TeamMember, ticket: Dict) -> float:
        """Calculate timezone compatibility score (0-1)"""
        try:
            import pytz
            from datetime import datetime

            # Get member's current time
            member_tz = pytz.timezone(member.timezone)
            member_time = datetime.now(member_tz)
            member_hour = member_time.hour

            # Check if within working hours
            if member.work_start_hour <= member_hour < member.work_end_hour:
                return 1.0  # Perfect - within working hours

            # Calculate hours until work start
            if member_hour < member.work_start_hour:
                hours_until_work = member.work_start_hour - member_hour
            else:
                hours_until_work = (24 - member_hour) + member.work_start_hour

            # Score decreases as hours increase
            if hours_until_work <= 2:
                return 0.8
            elif hours_until_work <= 4:
                return 0.6
            elif hours_until_work <= 8:
                return 0.4
            else:
                return 0.2

        except Exception as e:
            logger.debug(f"Timezone calculation error: {e}")
            return 0.5

    def _calculate_workload_score(self, member: TeamMember) -> float:
        """Calculate workload availability score (0-1)"""
        try:
            # Get current workload
            current_tickets = self.db.query(TicketHistory).filter(
                TicketHistory.assigned_to_id == member.id,
                TicketHistory.status.in_([TicketStatus.ASSIGNED, TicketStatus.IN_PROGRESS])
            ).count()

            # Calculate availability
            if current_tickets >= member.max_tickets:
                return 0.0  # At capacity
            elif current_tickets == 0:
                return 1.0  # Completely available

            # Linear scaling
            utilization = current_tickets / member.max_tickets
            return 1.0 - utilization

        except Exception as e:
            logger.error(f"Workload calculation error: {e}")
            return 0.5

    def _calculate_performance_score(self, member: TeamMember, category: str) -> float:
        """Calculate historical performance score for this category (0-1)"""
        try:
            # Normalize category to Enum for DB comparison
            category_enum: Optional[TicketCategory] = None

            if isinstance(category, TicketCategory):
                category_enum = category
            elif category:
                normalized = str(category).lower()
                try:
                    category_enum = TicketCategory(normalized)
                except ValueError:
                    logger.debug(f"Unknown category '{category}' for performance score; skipping category filter")

            filters = [
                TicketHistory.assigned_to_id == member.id,
                TicketHistory.resolved_at.isnot(None),
                TicketHistory.created_at >= datetime.now() - timedelta(days=30),
            ]

            if category_enum:
                filters.append(TicketHistory.category == category_enum)

            recent_tickets = self.db.query(TicketHistory).filter(
                *filters
            ).all()

            if not recent_tickets:
                return 0.5  # Neutral for no history

            # Calculate metrics
            total = len(recent_tickets)
            sla_met = sum(1 for t in recent_tickets if not t.sla_breached)
            sla_rate = sla_met / total if total > 0 else 0.5

            avg_resolution_hours = np.mean([
                t.actual_resolution_hours for t in recent_tickets
                if t.actual_resolution_hours
            ])

            # Normalize resolution time (lower is better)
            # Assume 4 hours is good, 8 hours is average, 12+ is poor
            if avg_resolution_hours <= 4:
                resolution_score = 1.0
            elif avg_resolution_hours <= 8:
                resolution_score = 0.7
            else:
                resolution_score = 0.4

            # Combined score
            return (sla_rate * 0.6) + (resolution_score * 0.4)

        except Exception as e:
            logger.error(f"Performance calculation error: {e}")
            return 0.5

    def _rule_based_routing(
        self,
        ticket: Dict,
        available_members: List[TeamMember],
        ticket_category: str
    ) -> Tuple[TeamMember, float, List[str]]:
        """Fallback rule-based routing"""
        # Simple: choose member with lowest workload
        workload_scores = {}
        for member in available_members:
            current_tickets = self.db.query(TicketHistory).filter(
                TicketHistory.assigned_to_id == member.id,
                TicketHistory.status.in_([TicketStatus.ASSIGNED, TicketStatus.IN_PROGRESS])
            ).count()
            workload_scores[member.id] = current_tickets

        best_member = min(available_members, key=lambda m: workload_scores.get(m.id, 0))
        return best_member, 0.7, ["Lowest workload"]

    def _generate_assignment_reasons(self, breakdown: Dict, member: TeamMember) -> List[str]:
        """Generate human-readable reasons for assignment"""
        reasons = []

        if breakdown['skill'] >= 0.8:
            reasons.append("Strong skill match")
        elif breakdown['skill'] >= 0.5:
            reasons.append("Relevant experience")

        if breakdown['timezone'] >= 0.8:
            reasons.append("Currently in working hours")

        if breakdown['workload'] >= 0.7:
            reasons.append("Good availability")

        if breakdown['performance'] >= 0.7:
            reasons.append("Excellent track record")

        if not reasons:
            reasons.append("Best available option")

        return reasons

    def predict_ticket_category(self, ticket: Dict) -> Dict:
        """
        Predict ticket category using trained ML model

        Args:
            ticket: Ticket data dict with 'subject' and 'description'

        Returns:
            {
                "category": str,
                "confidence": float (0-1),
                "probabilities": Dict[str, float],
                "method": "ml" | "fallback"
            }
        """
        try:
            if not self.ml_enabled or not self.category_classifier:
                return self._fallback_category_prediction(ticket)

            # Prepare text input
            text = f"{ticket.get('subject', '')} {ticket.get('description', '')}"

            # Vectorize
            X = self.category_vectorizer.transform([text])

            # Predict
            prediction = self.category_classifier.predict(X)[0]
            probabilities = self.category_classifier.predict_proba(X)[0]

            # Get confidence (max probability)
            confidence = float(max(probabilities))

            # Get all class probabilities
            class_probs = {
                cls: float(prob)
                for cls, prob in zip(self.category_classifier.classes_, probabilities)
            }

            logger.info(
                f"🤖 ML category prediction: {prediction} "
                f"(confidence: {confidence:.2f})"
            )

            return {
                "category": prediction,
                "confidence": confidence,
                "probabilities": class_probs,
                "method": "ml"
            }

        except Exception as e:
            logger.error(f"❌ ML category prediction failed: {e}")
            return self._fallback_category_prediction(ticket)

    def predict_ticket_complexity(self, ticket: Dict) -> Dict:
        """
        Predict ticket complexity using trained ML model

        Args:
            ticket: Ticket data dict with 'subject' and 'description'

        Returns:
            {
                "complexity": str,
                "confidence": float (0-1),
                "probabilities": Dict[str, float],
                "method": "ml" | "fallback"
            }
        """
        try:
            if not self.ml_enabled or not self.complexity_predictor:
                return self._fallback_complexity_prediction(ticket)

            # Prepare text input
            text = f"{ticket.get('subject', '')} {ticket.get('description', '')}"

            # Vectorize
            X = self.complexity_vectorizer.transform([text])

            # Predict
            prediction = self.complexity_predictor.predict(X)[0]
            probabilities = self.complexity_predictor.predict_proba(X)[0]

            # Get confidence
            confidence = float(max(probabilities))

            # Get all class probabilities
            class_probs = {
                cls: float(prob)
                for cls, prob in zip(self.complexity_predictor.classes_, probabilities)
            }

            logger.info(
                f"🤖 ML complexity prediction: {prediction} "
                f"(confidence: {confidence:.2f})"
            )

            return {
                "complexity": prediction,
                "confidence": confidence,
                "probabilities": class_probs,
                "method": "ml"
            }

        except Exception as e:
            logger.error(f"❌ ML complexity prediction failed: {e}")
            return self._fallback_complexity_prediction(ticket)

    def predict_resolution_time(self, ticket: Dict) -> Dict:
        """
        Predict resolution time using trained ML model

        Args:
            ticket: Ticket data dict with 'subject' and 'description'

        Returns:
            {
                "estimated_hours": float,
                "confidence": float (0-1),
                "method": "ml" | "fallback"
            }
        """
        try:
            if not self.ml_enabled or not self.effort_predictor:
                return self._fallback_resolution_time(ticket)

            # Prepare text input
            text = f"{ticket.get('subject', '')} {ticket.get('description', '')}"

            # Vectorize
            X = self.resolution_vectorizer.transform([text])

            # Predict (log-transformed, need to reverse)
            log_prediction = self.effort_predictor.predict(X)[0]
            estimated_hours = float(np.expm1(log_prediction))  # Reverse log1p

            # Estimate confidence based on model's R² score
            # For now, use a fixed confidence of 0.7
            # TODO: Could calculate this from prediction intervals
            confidence = 0.7

            logger.info(
                f"🤖 ML resolution time prediction: {estimated_hours:.1f} hours "
                f"(confidence: {confidence:.2f})"
            )

            return {
                "estimated_hours": round(estimated_hours, 1),
                "confidence": confidence,
                "method": "ml"
            }

        except Exception as e:
            logger.error(f"❌ ML resolution time prediction failed: {e}")
            return self._fallback_resolution_time(ticket)

    def _fallback_category_prediction(self, ticket: Dict) -> Dict:
        """Fallback rule-based category prediction"""
        subject = ticket.get('subject', '').lower()
        description = ticket.get('description', '').lower()
        text = f"{subject} {description}"

        # Simple keyword matching
        if any(kw in text for kw in ['kubernetes', 'k8s', 'pod', 'deployment', 'helm']):
            category = 'kubernetes'
        elif any(kw in text for kw in ['database', 'postgres', 'mysql', 'sql']):
            category = 'database'
        elif any(kw in text for kw in ['cicd', 'pipeline', 'gitlab', 'jenkins']):
            category = 'cicd'
        elif any(kw in text for kw in ['network', 'firewall', 'dns', 'routing']):
            category = 'network'
        else:
            category = 'application'

        return {
            "category": category,
            "confidence": 0.5,
            "probabilities": {category: 0.5},
            "method": "fallback"
        }

    def _fallback_complexity_prediction(self, ticket: Dict) -> Dict:
        """Fallback rule-based complexity prediction"""
        priority = ticket.get('priority', 'P3(Medium)')

        # Simple heuristic based on priority
        if priority == 'P1(Critical)':
            complexity = 'critical'
        elif priority == 'P2(High)':
            complexity = 'complex'
        else:
            complexity = 'moderate'

        return {
            "complexity": complexity,
            "confidence": 0.5,
            "probabilities": {complexity: 0.5},
            "method": "fallback"
        }

    def _fallback_resolution_time(self, ticket: Dict) -> Dict:
        """Fallback rule-based resolution time estimation"""
        priority = ticket.get('priority', 'P3(Medium)')

        # Simple heuristic based on priority
        priority_hours = {
            'P1(Critical)': 2.0,
            'P2(High)': 4.0,
            'P3(Medium)': 8.0,
            'P4(Low)': 16.0,
            'P5(Trivial)': 24.0
        }

        estimated_hours = priority_hours.get(priority, 8.0)

        return {
            "estimated_hours": estimated_hours,
            "confidence": 0.5,
            "method": "fallback"
        }

    def predict_sla_breach_probability(
        self,
        ticket: Dict,
        assignee: TeamMember
    ) -> Dict:
        """
        Predict probability of SLA breach

        Returns:
            {
                "probability": 0.0-1.0,
                "risk_level": "low|medium|high",
                "risk_factors": [...],
                "recommendation": str
            }
        """
        try:
            factors = []
            risk_score = 0.0

            # Priority factor
            priority = ticket.get('priority', 'P3(Medium)')
            if priority == 'P1(Critical)':
                risk_score += 0.3
                factors.append("Critical priority")

            # Assignee workload
            current_tickets = self.db.query(TicketHistory).filter(
                TicketHistory.assigned_to_id == assignee.id,
                TicketHistory.status == TicketStatus.IN_PROGRESS
            ).count()

            if current_tickets >= assignee.max_tickets * 0.8:
                risk_score += 0.2
                factors.append("High assignee workload")

            # Complexity (if available)
            complexity = ticket.get('complexity', 'moderate')
            complexity_risk = {
                'simple': 0.0,
                'moderate': 0.1,
                'complex': 0.2,
                'critical': 0.3
            }
            risk_score += complexity_risk.get(complexity, 0.1)

            # Historical performance
            if assignee.sla_compliance_rate < 85:
                risk_score += 0.2
                factors.append("Below average SLA compliance")

            # Determine risk level
            if risk_score >= 0.7:
                risk_level = "high"
                recommendation = "Consider escalation or additional resources"
            elif risk_score >= 0.4:
                risk_level = "medium"
                recommendation = "Monitor closely, may need support"
            else:
                risk_level = "low"
                recommendation = "Normal processing expected"

            return {
                "probability": min(risk_score, 1.0),
                "risk_level": risk_level,
                "risk_factors": factors,
                "recommendation": recommendation
            }

        except Exception as e:
            logger.error(f"❌ SLA prediction failed: {e}")
            return {
                "probability": 0.5,
                "risk_level": "medium",
                "risk_factors": ["Unable to calculate"],
                "recommendation": "Monitor as normal"
            }

    def forecast_ticket_volume(self, days_ahead: int = 7) -> Dict:
        """
        Forecast ticket volume for capacity planning using exponential smoothing

        Returns:
            {
                "forecast": [{date, predicted_volume, confidence, lower_bound, upper_bound}],
                "busy_periods": [...],
                "recommendations": {...},
                "historical_avg": int,
                "trend": str
            }
        """
        try:
            from sqlalchemy import func, Date

            # Get historical data (last 90 days)
            end_date = datetime.now()
            start_date = end_date - timedelta(days=90)

            # Query daily ticket volumes
            daily_volumes_query = self.db.query(
                func.date(TicketHistory.created_at).label('date'),
                func.count(TicketHistory.id).label('count')
            ).filter(
                TicketHistory.created_at >= start_date
            ).group_by(
                func.date(TicketHistory.created_at)
            ).order_by(
                func.date(TicketHistory.created_at)
            ).all()

            if len(daily_volumes_query) < 14:
                return {
                    "forecast": [],
                    "busy_periods": [],
                    "recommendations": {"note": "Need at least 14 days of data for forecasting"},
                    "historical_avg": 0,
                    "trend": "unknown"
                }

            # Convert to time series
            dates = [row[0] for row in daily_volumes_query]
            volumes = np.array([row[1] for row in daily_volumes_query])

            # Calculate statistics
            avg_volume = np.mean(volumes)
            std_volume = np.std(volumes)

            # Detect trend using linear regression
            X = np.arange(len(volumes)).reshape(-1, 1)
            y = volumes
            from sklearn.linear_model import LinearRegression
            lr = LinearRegression()
            lr.fit(X, y)
            trend_slope = lr.coef_[0]

            # Determine trend direction
            if trend_slope > 0.5:
                trend = "increasing"
            elif trend_slope < -0.5:
                trend = "decreasing"
            else:
                trend = "stable"

            # Triple Exponential Smoothing (Holt-Winters)
            forecast_values = self._exponential_smoothing_forecast(
                volumes,
                days_ahead,
                alpha=0.3,  # Level smoothing
                beta=0.1,   # Trend smoothing
                gamma=0.2   # Seasonality smoothing
            )

            # Calculate confidence intervals (95%)
            # Use last 14 days volatility for confidence bounds
            recent_volatility = np.std(volumes[-14:])
            z_score = 1.96  # 95% confidence

            forecast = []
            for i in range(days_ahead):
                pred_date = end_date + timedelta(days=i+1)
                predicted = max(0, forecast_values[i])

                # Confidence bounds
                lower_bound = max(0, int(predicted - z_score * recent_volatility))
                upper_bound = int(predicted + z_score * recent_volatility)

                forecast.append({
                    "date": pred_date.strftime("%Y-%m-%d"),
                    "count": int(predicted),
                    "predicted": True,
                    "lower_bound": lower_bound,
                    "upper_bound": upper_bound,
                    "confidence": 0.85  # 95% confidence interval
                })

            # Identify busy periods (above mean + 1 std)
            busy_threshold = avg_volume + std_volume
            busy_periods = [
                f for f in forecast
                if f['count'] > busy_threshold
            ]

            # Get current capacity
            current_capacity = self.db.query(TeamMember).filter(
                TeamMember.active == True
            ).count() * 8  # Assume 8 tickets per member

            # Generate recommendations
            recommendations = {}
            max_predicted = max(f['count'] for f in forecast)
            avg_predicted = np.mean([f['count'] for f in forecast])

            if max_predicted > current_capacity * 0.8:
                recommendations['capacity_alert'] = (
                    f"Peak volume ({max_predicted}) may exceed 80% capacity. "
                    f"Consider on-call resources."
                )

            if trend == "increasing":
                recommendations['trend_alert'] = (
                    f"Ticket volume is trending upward. "
                    f"Plan for {int(avg_predicted - avg_volume)} additional tickets/day."
                )

            if len(busy_periods) >= 3:
                recommendations['busy_period_alert'] = (
                    f"{len(busy_periods)} busy days forecasted. "
                    f"Ensure adequate staffing."
                )

            return {
                "historical": [
                    {
                        "date": date.strftime("%Y-%m-%d"),
                        "count": int(count),
                        "predicted": False
                    }
                    for date, count in zip(dates, volumes)
                ],
                "forecast": forecast,
                "busy_periods": busy_periods,
                "historical_avg": int(avg_volume),
                "historical_std": round(float(std_volume), 2),
                "trend": trend,
                "trend_slope": round(float(trend_slope), 3),
                "current_capacity": current_capacity,
                "recommendations": recommendations,
                "method": "triple_exponential_smoothing"
            }

        except Exception as e:
            logger.error(f"❌ Volume forecasting failed: {e}")
            return {"error": str(e)}

    def _exponential_smoothing_forecast(
        self,
        series: np.ndarray,
        steps: int,
        alpha: float = 0.3,
        beta: float = 0.1,
        gamma: float = 0.2,
        seasonality: int = 7  # Weekly seasonality
    ) -> np.ndarray:
        """
        Triple Exponential Smoothing (Holt-Winters) forecast

        Args:
            series: Historical time series data
            steps: Number of steps to forecast
            alpha: Level smoothing parameter (0-1)
            beta: Trend smoothing parameter (0-1)
            gamma: Seasonality smoothing parameter (0-1)
            seasonality: Seasonal period (7 for weekly)

        Returns:
            Array of forecasted values
        """
        n = len(series)

        # Initialize components
        level = np.mean(series[:seasonality])
        trend = (np.mean(series[seasonality:2*seasonality]) - np.mean(series[:seasonality])) / seasonality

        # Initialize seasonal component
        seasonal = np.zeros(seasonality)
        for i in range(seasonality):
            seasonal[i] = series[i] - level

        # Holt-Winters equations
        for t in range(n):
            prev_level = level
            level = alpha * (series[t] - seasonal[t % seasonality]) + (1 - alpha) * (level + trend)
            trend = beta * (level - prev_level) + (1 - beta) * trend
            seasonal[t % seasonality] = gamma * (series[t] - level) + (1 - gamma) * seasonal[t % seasonality]

        # Forecast
        forecast = np.zeros(steps)
        for i in range(steps):
            forecast[i] = level + (i + 1) * trend + seasonal[(n + i) % seasonality]

        return forecast

    def _load_models(self):
        """Load pre-trained ML models"""
        try:
            import os
            models_loaded = 0

            # Load category classifier
            if os.path.exists(f"{self.models_path}/category_classifier.joblib"):
                self.category_classifier = joblib.load(
                    f"{self.models_path}/category_classifier.joblib"
                )
                self.category_vectorizer = joblib.load(
                    f"{self.models_path}/category_vectorizer.joblib"
                )
                models_loaded += 1
                logger.info("✅ Category classifier loaded")

            # Load complexity predictor
            if os.path.exists(f"{self.models_path}/complexity_classifier.joblib"):
                self.complexity_predictor = joblib.load(
                    f"{self.models_path}/complexity_classifier.joblib"
                )
                self.complexity_vectorizer = joblib.load(
                    f"{self.models_path}/complexity_vectorizer.joblib"
                )
                models_loaded += 1
                logger.info("✅ Complexity predictor loaded")

            # Load resolution time predictor
            if os.path.exists(f"{self.models_path}/resolution_regressor.joblib"):
                self.effort_predictor = joblib.load(
                    f"{self.models_path}/resolution_regressor.joblib"
                )
                self.resolution_vectorizer = joblib.load(
                    f"{self.models_path}/resolution_vectorizer.joblib"
                )
                models_loaded += 1
                logger.info("✅ Resolution time predictor loaded")

            # Load assignment recommender (if exists)
            if os.path.exists(f"{self.models_path}/assignment_recommender.joblib"):
                self.assignment_recommender = joblib.load(
                    f"{self.models_path}/assignment_recommender.joblib"
                )
                models_loaded += 1
                logger.info("✅ Assignment recommender loaded")

            if models_loaded > 0:
                logger.info(f"✅ {models_loaded} ML models loaded successfully")
            else:
                logger.warning("⚠️ No ML models found - using rule-based predictions")

        except Exception as e:
            logger.warning(f"⚠️ Could not load ML models: {e}")

    def train_models(self, force_retrain: bool = False) -> Dict:
        """
        Train ML models with historical data

        Args:
            force_retrain: Force retraining even if models exist

        Returns:
            Training results dict with metrics
        """
        if not ML_AVAILABLE:
            logger.warning("⚠️ ML libraries not available - skipping training")
            return {"success": False, "error": "ML libraries not available"}

        try:
            logger.info("🎓 Starting ML model training...")

            # Check if we have enough training data
            total_tickets = self.db.query(TicketHistory).filter(
                TicketHistory.resolved_at.isnot(None)
            ).count()

            if total_tickets < settings.ML_MIN_TRAINING_SAMPLES:
                logger.warning(
                    f"⚠️ Insufficient training data: {total_tickets} < {settings.ML_MIN_TRAINING_SAMPLES}"
                )
                return {
                    "success": False,
                    "error": f"Need at least {settings.ML_MIN_TRAINING_SAMPLES} resolved tickets",
                    "current_count": total_tickets
                }

            # Fetch training data
            logger.info(f"📊 Fetching {total_tickets} resolved tickets for training...")
            tickets = self.db.query(TicketHistory).filter(
                TicketHistory.resolved_at.isnot(None),
                TicketHistory.category.isnot(None),
                TicketHistory.complexity.isnot(None)
            ).limit(10000).all()  # Limit to prevent memory issues

            # Prepare training data
            training_results = {}

            # 1. Train category classifier
            category_result = self._train_category_classifier(tickets)
            training_results['category_classifier'] = category_result

            # 2. Train complexity predictor
            complexity_result = self._train_complexity_predictor(tickets)
            training_results['complexity_predictor'] = complexity_result

            # 3. Train resolution time predictor
            resolution_result = self._train_resolution_time_predictor(tickets)
            training_results['resolution_time_predictor'] = resolution_result

            logger.info("✅ ML model training completed successfully")

            return {
                "success": True,
                "training_samples": len(tickets),
                "models_trained": 3,
                "results": training_results,
                "trained_at": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"❌ ML model training failed: {e}")
            return {"success": False, "error": str(e)}

    def _train_category_classifier(self, tickets: List[TicketHistory]) -> Dict:
        """Train ticket category classification model"""
        try:
            logger.info("🔧 Training category classifier...")

            # Prepare features and labels
            X = []
            y = []

            for ticket in tickets:
                # Combine subject and description as text features
                text = f"{ticket.subject} {ticket.description or ''}"
                X.append(text)
                y.append(ticket.category.value)

            # Split train/test
            from sklearn.model_selection import train_test_split
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42, stratify=y
            )

            # Create TF-IDF vectorizer
            vectorizer = TfidfVectorizer(
                max_features=1000,
                ngram_range=(1, 2),
                stop_words='english',
                min_df=2
            )

            X_train_vec = vectorizer.fit_transform(X_train)
            X_test_vec = vectorizer.transform(X_test)

            # Train Random Forest classifier
            classifier = RandomForestClassifier(
                n_estimators=100,
                max_depth=20,
                min_samples_split=5,
                random_state=42,
                n_jobs=-1
            )

            classifier.fit(X_train_vec, y_train)

            # Evaluate
            train_score = classifier.score(X_train_vec, y_train)
            test_score = classifier.score(X_test_vec, y_test)

            # Save models
            import os
            os.makedirs(self.models_path, exist_ok=True)

            joblib.dump(vectorizer, f"{self.models_path}/category_vectorizer.joblib")
            joblib.dump(classifier, f"{self.models_path}/category_classifier.joblib")

            self.category_classifier = classifier

            logger.info(
                f"✅ Category classifier trained: "
                f"train={train_score:.3f}, test={test_score:.3f}"
            )

            return {
                "train_accuracy": round(train_score, 3),
                "test_accuracy": round(test_score, 3),
                "samples": len(X),
                "classes": len(set(y))
            }

        except Exception as e:
            logger.error(f"❌ Category classifier training failed: {e}")
            return {"error": str(e)}

    def _train_complexity_predictor(self, tickets: List[TicketHistory]) -> Dict:
        """Train ticket complexity prediction model"""
        try:
            logger.info("🔧 Training complexity predictor...")

            X = []
            y = []

            for ticket in tickets:
                text = f"{ticket.subject} {ticket.description or ''}"
                X.append(text)
                y.append(ticket.complexity.value)

            # Split train/test
            from sklearn.model_selection import train_test_split
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42, stratify=y
            )

            # Use same vectorizer approach
            vectorizer = TfidfVectorizer(
                max_features=800,
                ngram_range=(1, 2),
                stop_words='english',
                min_df=2
            )

            X_train_vec = vectorizer.fit_transform(X_train)
            X_test_vec = vectorizer.transform(X_test)

            # Train classifier
            classifier = RandomForestClassifier(
                n_estimators=80,
                max_depth=15,
                random_state=42,
                n_jobs=-1
            )

            classifier.fit(X_train_vec, y_train)

            train_score = classifier.score(X_train_vec, y_train)
            test_score = classifier.score(X_test_vec, y_test)

            # Save models
            joblib.dump(vectorizer, f"{self.models_path}/complexity_vectorizer.joblib")
            joblib.dump(classifier, f"{self.models_path}/complexity_classifier.joblib")

            self.complexity_predictor = classifier

            logger.info(
                f"✅ Complexity predictor trained: "
                f"train={train_score:.3f}, test={test_score:.3f}"
            )

            return {
                "train_accuracy": round(train_score, 3),
                "test_accuracy": round(test_score, 3),
                "samples": len(X),
                "classes": len(set(y))
            }

        except Exception as e:
            logger.error(f"❌ Complexity predictor training failed: {e}")
            return {"error": str(e)}

    def _train_resolution_time_predictor(self, tickets: List[TicketHistory]) -> Dict:
        """Train resolution time prediction model (regression)"""
        try:
            logger.info("🔧 Training resolution time predictor...")

            X = []
            y = []

            for ticket in tickets:
                if ticket.actual_resolution_hours and ticket.actual_resolution_hours > 0:
                    text = f"{ticket.subject} {ticket.description or ''}"
                    X.append(text)
                    # Log transform for better distribution
                    y.append(np.log1p(ticket.actual_resolution_hours))

            if len(X) < 50:
                return {"error": "Insufficient data with resolution times"}

            # Split train/test
            from sklearn.model_selection import train_test_split
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42
            )

            # Vectorize
            vectorizer = TfidfVectorizer(
                max_features=500,
                ngram_range=(1, 2),
                stop_words='english',
                min_df=2
            )

            X_train_vec = vectorizer.fit_transform(X_train)
            X_test_vec = vectorizer.transform(X_test)

            # Train regressor
            regressor = RandomForestRegressor(
                n_estimators=100,
                max_depth=15,
                random_state=42,
                n_jobs=-1
            )

            regressor.fit(X_train_vec, y_train)

            train_score = regressor.score(X_train_vec, y_train)
            test_score = regressor.score(X_test_vec, y_test)

            # Calculate RMSE
            from sklearn.metrics import mean_squared_error
            y_pred = regressor.predict(X_test_vec)
            rmse = np.sqrt(mean_squared_error(y_test, y_pred))

            # Save models
            joblib.dump(vectorizer, f"{self.models_path}/resolution_vectorizer.joblib")
            joblib.dump(regressor, f"{self.models_path}/resolution_regressor.joblib")

            self.effort_predictor = regressor

            logger.info(
                f"✅ Resolution time predictor trained: "
                f"R²={test_score:.3f}, RMSE={rmse:.3f}"
            )

            return {
                "train_r2": round(train_score, 3),
                "test_r2": round(test_score, 3),
                "rmse": round(rmse, 3),
                "samples": len(X)
            }

        except Exception as e:
            logger.error(f"❌ Resolution time predictor training failed: {e}")
            return {"error": str(e)}
