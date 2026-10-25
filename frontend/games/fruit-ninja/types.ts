export type Label = "fresh" | "rotten";
export type Asset = {
  asset_id: string;
  url: string;
  width: number;
  height: number;
};
export type Presentation = Asset & {
  id: string;
  ordinal: number;
  section: number;
  spawn_ms: number;
  flight_ms: number;
  lane: number;
  drift: number;
  rotation: number;
  spin: number;
  label?: Label;
  explanation?: string;
};
export type Round = {
  id: string;
  kind: "game" | "calibration" | "demonstration";
  duration_ms: number;
  presentations: Presentation[];
  submitted_sections?: number[];
};
export type Result = {
  id: string;
  kind: string;
  status: string;
  correct: number;
  total: number;
  eligible: boolean;
  passed: boolean;
  score: number;
  review_bonus: number;
  counts: Record<Label, number>;
  exclusion_reason?: string;
};
export type Profile = {
  id: string;
  name: string;
  calibration_required: boolean;
  targets_remaining: number;
  history: {
    id: string;
    kind: string;
    first_pass_correct: number;
    first_pass_total: number;
    score: number;
    eligible: boolean;
  }[];
};
export type Dataset = {
  assets: (Asset & { fresh: number; rotten: number; contributions: number })[];
  total_votes: number;
  attribution: string;
};
export type Judgment = {
  event_id: string;
  presentation_id: string;
  action: "slice" | "pass" | "acknowledge";
  client_timestamp: string;
  elapsed_ms: number;
  exposure_ms: number;
};
