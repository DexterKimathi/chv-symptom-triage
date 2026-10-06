// Shapes returned by the backend. Kept in step with ucs31-kimathi-backend/docs/api.md.

export type Role = "chv" | "admin";
export type Answer = "yes" | "no" | "unknown";
export type AgeBand = "under_5" | "5_to_14" | "15_to_49" | "50_plus";
export type Sex = "female" | "male";
export type Outcome =
  | "urgent_referral"
  | "likely_condition"
  | "low_confidence"
  | "too_close_to_call";

export interface TokenResponse {
  access_token: string;
  token_type: string;
  role: Role;
}

export interface Question {
  code: string;
  text: string;
  category: string;
  display_order: number;
  is_danger_sign: boolean;
}

export interface RankedCondition {
  code: string;
  name: string;
  probability: number;
}

export interface ExplanationItem {
  question: string;
  answer: Answer;
  weight: number;
}

export interface AssessmentRequest {
  patient_ref: string;
  age_band: AgeBand;
  sex: Sex;
  answers: Record<string, Answer>;
}

export interface Assessment {
  id: number;
  outcome: Outcome;
  headline: string;
  danger_sign_triggered: boolean;
  danger_signs_present: string[];
  top: RankedCondition[];
  top_confidence: number;
  explanation: ExplanationItem[];
  referral_level: string;
  guidance: string;
  disclaimer: string;
  model_version: string;
  created_at: string;
}

export interface AssessmentSummary {
  id: number;
  patient_ref: string;
  outcome: Outcome;
  top_condition: string | null;
  top_confidence: number;
  danger_sign_triggered: boolean;
  created_at: string;
}

export interface CreateUserRequest {
  name: string;
  phone: string;
  password: string;
  area?: string;
  role?: Role;
}

export interface User {
  id: number;
  name: string;
  phone: string;
  role: Role;
  area: string | null;
  is_active: boolean;
}

export const AGE_BANDS: { value: AgeBand; label: string }[] = [
  { value: "under_5", label: "Under 5" },
  { value: "5_to_14", label: "5 to 14" },
  { value: "15_to_49", label: "15 to 49" },
  { value: "50_plus", label: "50 and over" },
];
