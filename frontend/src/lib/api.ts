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

// The localhost default is for `npm run dev` only; next.config.ts stops a production build without the variable.
const BASE_URL = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");

/** A request the backend answered with an error. `fields` holds validation messages by field name. */
export class ApiError extends Error {
  constructor(public status: number, message: string, public fields: Record<string, string> = {}) {
    super(message);
  }
}

/** The request never reached the backend: no connection, or the server is down. */
export class NetworkError extends Error {
  constructor() {
    super(connectionMessage());
  }
}

/** The browser cannot tell "no signal" from "server down", except when the phone itself knows it is offline. */
export function connectionMessage() {
  return typeof navigator !== "undefined" && navigator.onLine === false
    ? "No internet connection, please try again."
    : "Couldn't reach the server. Check your connection or try again.";
}

const SERVER_PROBLEM = "The server had a problem with this request. Please try again, and tell your supervisor if it keeps happening.";

/** Whether the backend answers at all. Used to tell a failed request apart from no connection. */
async function serverIsUp(): Promise<boolean> {
  try {
    return (await fetch(`${BASE_URL}/health`, { cache: "no-store" })).ok;
  } catch {
    return false;
  }
}

// Pydantic puts "Value error, " in front of messages from custom validators.
const cleanMessage = (msg: string) => msg.replace(/^Value error, /, "");

function readDetail(body: unknown): { message: string; fields: Record<string, string> } {
  // FastAPI sends { detail: "..." } or, for validation errors,
  // { detail: [ { loc: ["body", "phone"], msg }, ... ] }.
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string") return { message: detail, fields: {} };
    if (Array.isArray(detail)) {
      const fields: Record<string, string> = {};
      const messages = detail.map((d) => {
        const item = (d && typeof d === "object" ? d : {}) as { loc?: unknown; msg?: unknown };
        const message = cleanMessage(String(item.msg ?? d));
        const field = Array.isArray(item.loc) ? item.loc[item.loc.length - 1] : undefined;
        if (typeof field === "string" && !(field in fields)) fields[field] = message;
        return message;
      });
      return { message: messages.join("; "), fields };
    }
  }
  return { message: "Something went wrong. Please try again.", fields: {} };
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
    // A crash on the server can come back without CORS headers, and the browser then reports
    // it exactly like a lost connection. If the server still answers a health check, it was
    // the server, not the signal.
    if (navigator.onLine !== false && (await serverIsUp())) throw new ApiError(500, SERVER_PROBLEM);
    throw new NetworkError();
  }
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const { message, fields } = readDetail(body);
    throw new ApiError(response.status, response.status >= 500 ? SERVER_PROBLEM : message, fields);
  }
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
