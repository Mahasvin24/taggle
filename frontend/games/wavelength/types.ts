import type { AxisId } from "./axes";

export type Review = { id: string; text: string; category: string; source: "authored_demo" };
export type Confidence = "sure" | "unsure";
export type AnnotationInput = {
  axis_id?: AxisId;
  submission_id: string;
  session_id: string;
  review_id: string;
  score: number;
  confidence: Confidence;
  elapsed_ms: number;
};
export type PairInput = {
  axis_id?: AxisId;
  submission_id: string;
  session_id: string;
  text: string;
  category: string;
  target: number;
  guess: number;
  elapsed_ms: number;
};
export type SoloResult = {
  saved: true;
  annotation_id: string;
  reference_score: number;
  reference_note: string;
  reference_version: string;
  points: number;
  distance: number;
};
export type PairResult = { saved: true; pair_id: string; target: number; guess: number; points: number; distance: number };
export type SoloState = {
  axisId: AxisId;
  setup: boolean;
  deck: string[];
  index: number;
  guess: number;
  touched: boolean;
  confidence: Confidence;
  results: SoloResult[];
  started: number;
  pending: AnnotationInput | null;
};
export type PairState = {
  scenarioId?: string;
  phase: "intro" | "setup" | "write" | "handoff" | "guess" | "reveal";
  axisId: AxisId;
  target: number;
  text: string;
  guess: number;
  touched: boolean;
  round: number;
  results: PairResult[];
  started: number;
  pending: PairInput | null;
};
export type Dataset = {
  reference_version: string;
  summary: { annotations: number; synthetic_pairs: number; unique_reviews: number; unsure_annotations: number };
  annotations: Array<{ review_id: string; score: number; confidence: Confidence; [key: string]: unknown }>;
  synthetic_pairs: Array<{ text: string; intended_score: number; guessed_score: number; [key: string]: unknown }>;
};
