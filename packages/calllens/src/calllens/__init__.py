"""CallLens — open-source conversation intelligence and behavioral evaluation.

Upload a call. CallLens transcribes it, reconstructs the conversation,
measures deterministic communication metrics, evaluates semantic behaviors
against configurable rubrics, verifies the supporting evidence, and produces
explainable conversation intelligence.
"""

from calllens.domain.metrics import CallMetrics, TalkRatio
from calllens.domain.report import AnalysisRun, CallReport
from calllens.domain.rubric import Rubric, RubricDimension
from calllens.domain.scoring import Evidence, RubricResult, RubricScore
from calllens.domain.transcript import Speaker, Transcript, Utterance
from calllens.sdk.client import CallLens

__version__ = "0.1.0"

__all__ = [
    "AnalysisRun",
    "CallLens",
    "CallMetrics",
    "CallReport",
    "Evidence",
    "Rubric",
    "RubricDimension",
    "RubricResult",
    "RubricScore",
    "Speaker",
    "TalkRatio",
    "Transcript",
    "Utterance",
    "__version__",
]
