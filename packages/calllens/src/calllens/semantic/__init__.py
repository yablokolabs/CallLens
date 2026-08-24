"""Semantic intelligence built on the LLM provider abstraction."""

from calllens.semantic.coaching import CoachingGenerator
from calllens.semantic.opportunities import OpportunityDetector
from calllens.semantic.sentiment import SentimentAnalyzer
from calllens.semantic.topics import IntentExtractor, TopicExtractor

__all__ = [
    "CoachingGenerator",
    "IntentExtractor",
    "OpportunityDetector",
    "SentimentAnalyzer",
    "TopicExtractor",
]
