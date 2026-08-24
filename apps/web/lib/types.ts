export interface Utterance {
  speaker_id: string;
  text: string;
  start_time: number;
  end_time: number | null;
}

export interface Speaker {
  id: string;
  label: string | null;
  role: "representative" | "customer" | "unknown";
}

export interface Transcript {
  utterances: Utterance[];
  speakers: Speaker[];
  language: string | null;
  source: string;
  duration: number | null;
}

export interface TalkRatio {
  representative: number;
  customer: number;
  other: number;
}

export interface CallMetrics {
  duration: number;
  total_words: number;
  words_per_minute: number;
  representative_words: number;
  customer_words: number;
  representative_speaking_time: number;
  customer_speaking_time: number;
  talk_ratio: TalkRatio;
  turns: number;
  speaker_transitions: number;
  interruptions: number;
  silence_duration: number;
  longest_monologue: number;
  longest_monologue_speaker: string | null;
  question_count: number;
  open_question_count: number;
}

export interface SentimentSegment {
  speaker_id: string;
  start: number;
  end: number;
  sentiment: string;
  score: number;
  confidence: number;
}

export interface SpeakerSentiment {
  speaker_id: string;
  timeline: SentimentSegment[];
  overall: string;
  average_score: number;
}

export interface SentimentAnalysis {
  customer: SpeakerSentiment | null;
  representative: SpeakerSentiment | null;
  turning_points: { timestamp: number; from_sentiment: string; to_sentiment: string; trigger: string | null }[];
  engagement: number;
  frustration: number;
  enthusiasm: number;
  uncertainty: number;
  objection_intensity: number;
}

export interface Topic {
  topic: string;
  start_time: number;
  end_time: number;
  sentiment: string | null;
  confidence: number;
}

export interface Evidence {
  start_time: number;
  end_time: number | null;
  speaker_id: string;
  transcript_excerpt: string;
  explanation: string;
  kind: string;
}

export interface RubricResult {
  rubric_dimension: string;
  score: number;
  confidence: number;
  reasoning: string;
  positive_evidence: Evidence[];
  negative_evidence: Evidence[];
  missing_behaviors: string[];
  rescore_attempts: number;
}

export interface RubricScore {
  dimension: string;
  label: string;
  weight: number;
  result: RubricResult;
}

export interface Opportunity {
  type: string;
  confidence: number;
  description: string;
  product_context: string | null;
  evidence_timestamps: number[];
}

export interface Risk {
  type: string;
  confidence: number;
  description: string;
  evidence_timestamps: number[];
}

export interface CoachingInsight {
  title: string;
  priority: "high" | "medium" | "low";
  recommendation: string;
  rationale: string;
  evidence_timestamps: number[];
  suggested_phrasing: string | null;
}

export interface CallReport {
  call_id: string;
  status: string;
  overall_score: number;
  summary: string;
  confidence: number;
  metrics: CallMetrics | null;
  sentiment: SentimentAnalysis | null;
  topics: Topic[];
  rubric_scores: RubricScore[];
  opportunities: Opportunity[];
  risks: Risk[];
  coaching: CoachingInsight[];
  model_identity: {
    model_provider: string;
    model_name: string;
    rubric_version: string | null;
    pipeline_version: string;
  } | null;
  analysis_run_id: string | null;
}

export interface CallRecord {
  id: string;
  filename: string | null;
  status: string;
  created_at: string | null;
}

export interface RubricDimension {
  key: string;
  label: string;
  weight: number;
  description: string;
}

export interface Rubric {
  name: string;
  version: string;
  description: string;
  dimensions: RubricDimension[];
}
