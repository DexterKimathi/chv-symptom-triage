// Every call to the backend lives here, so the rest of the app never builds a URL.

import type {
  Assessment,
  AssessmentRequest,
  AssessmentSummary,
  CreateUserRequest,
  Question,
  TokenResponse,
  User,
} from "./types";

const BASE_URL = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");

/** A request the backend answered with an error. */
export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

/** The request never reached the backend: no connection, or the server is down. */
export class NetworkError extends Error {
  constructor() {
    super("No internet connection. Check your data or Wi-Fi and try again.");
  }
}

function readDetail(body: unknown): string {
  // FastAPI sends { detail: "..." } or, for validation errors, { detail: [ {msg}, ... ] }.
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail.map((d) => (d && typeof d === "object" && "msg" in d ? String(d.msg) : String(d))).join("; ");
    }
  }
  return "Something went wrong. Please try again.";
}

async function request<T>(path: string, options: RequestInit & { token?: string | null } = {}): Promise<T> {
  const { token, headers, ...rest } = options;
  let response: Response;
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      ...rest,
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...headers,
      },
    });
  } catch {
    throw new NetworkError();
  }
  const body = await response.json().catch(() => null);
  if (!response.ok) throw new ApiError(response.status, readDetail(body));
  return body as T;
}

export const api = {
  login: (phone: string, password: string) =>
    request<TokenResponse>("/auth/login", { method: "POST", body: JSON.stringify({ phone, password }) }),

  questions: (token: string) => request<Question[]>("/questions", { token }),

  submitAssessment: (token: string, payload: AssessmentRequest) =>
    request<Assessment>("/assessments", { method: "POST", token, body: JSON.stringify(payload) }),

  assessments: (token: string) => request<AssessmentSummary[]>("/assessments", { token }),

  assessment: (token: string, id: number | string) => request<Assessment>(`/assessments/${id}`, { token }),

  createUser: (token: string, payload: CreateUserRequest) =>
    request<User>("/admin/users", { method: "POST", token, body: JSON.stringify(payload) }),
};
