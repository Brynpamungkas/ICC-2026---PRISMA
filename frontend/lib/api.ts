/** Approved D03/D07 transport; no model calls or answer synthesis in the browser. */
export type Cell = string | number | null;
export type Candidate = { code: string; canonical_name: string; unit: string };
export type ExecResult = { candidate_code: string; columns: string[]; rows: Cell[][]; structure: "TEXT" | "NUMBER"; unit: string; error: string | null };
export type Evidence = { candidate: Candidate; result: ExecResult };
export type ReasonCode = "T0" | "T1" | "T2" | "T3" | "T4" | "T5";
export type Decision = { decision: "JAWAB" | "TANYA" | "TAHAN"; answer: Evidence | null; evidence: Evidence[]; reason_code: ReasonCode | null; suggestion: string | null; period_used: string | null };
export type QuestionResponse = { id_sesi: string; id_log: string; decision: Decision };
export type IndicatorMetadata = { kode: string; nama_kanonik: string; definisi_resmi: string; satuan: string; sumber: string; cakupan_wilayah: string[]; periode_tersedia: string[] };
export type CatalogResponse = { indikator: IndicatorMetadata[] };
export type ServiceHealth = { status: "AVAILABLE" | "UNAVAILABLE" | "UNKNOWN"; checked_at: string | null; diagnostic_code: string | null };
export type HealthResponse = { model: ServiceHealth; database: ServiceHealth };
export type Extraction = { raw_question: string; terms: string[]; regions: string[]; period: string | null; operation: "NONE" | "SUM" | "AVG" | "RANK"; rank_direction: "highest" | "lowest" | null; top_n: number; unresolved: string[] };
export type LogRecord = {
  run_id: string; session_id: string; question: string; extraction: Extraction | null; k: string[]; k_prime: string[];
  skeletons: { sql: string; valid: boolean; reject_reason: string | null }[];
  votes: { candidate_code: string; result: ExecResult; votes: number; tie: boolean }[];
  decision: Decision | null; mode: "K1" | "K2" | "K3"; latency_ms: Record<string, number>;
  model_name: string | null; prompt_version: string | null; dictionary_hash: string | null;
};
export type LogResponse = { id_log: string; record: LogRecord };

export class ApiError extends Error {
  constructor(public readonly status: number, public readonly code: string, message: string) { super(message); this.name = "ApiError"; }
}
function invalid(): never { throw new ApiError(0, "INVALID_RESPONSE", "Respons layanan tidak sesuai kontrak. Hasil belum dapat ditampilkan."); }
function object(value: unknown): Record<string, unknown> { if (!value || typeof value !== "object" || Array.isArray(value)) invalid(); return value as Record<string, unknown>; }
function str(value: unknown): string { if (typeof value !== "string") invalid(); return value; }
function text(value: unknown): string { const parsed = str(value); if (!parsed.trim()) invalid(); return parsed; }
function nullable(value: unknown): string | null { return value === null ? null : str(value); }
function array(value: unknown): unknown[] { if (!Array.isArray(value)) invalid(); return value; }
function strings(value: unknown): string[] { return array(value).map(str); }
function finite(value: unknown): number { if (typeof value !== "number" || !Number.isFinite(value)) invalid(); return value; }
function integer(value: unknown): number { const parsed = finite(value); if (!Number.isSafeInteger(parsed) || parsed < 0) invalid(); return parsed; }
function bool(value: unknown): boolean { if (typeof value !== "boolean") invalid(); return value; }
function oneOf<T extends string>(value: unknown, choices: readonly T[]): T { if (typeof value !== "string" || !choices.includes(value as T)) invalid(); return value as T; }
function uuid(value: unknown): string {
  const parsed = str(value);
  if (!/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(parsed)) invalid();
  return parsed;
}
function result(value: unknown, allowError = false): ExecResult {
  const data = object(value); const columns = strings(data.columns); const structure = oneOf(data.structure, ["TEXT", "NUMBER"]);
  if (data.error !== null && !(allowError && typeof data.error === "string")) invalid();
  const rows = array(data.rows).map((row) => {
    const cells = array(row); if (cells.length !== columns.length) invalid();
    return cells.map((cell, i): Cell => {
      if (cell === null) return null;
      if (typeof cell === "number") return finite(cell);
      // wilayah/periode are row labels on NUMBER lookups (Table VII fix, 21 Oct); other text only in TEXT results.
      if (typeof cell === "string" && (structure === "TEXT" || columns[i] === "wilayah" || columns[i] === "periode")) return cell;
      return invalid();
    });
  });
  // Error-bearing executions exist in diagnostic votes, never in answer evidence.
  return { candidate_code: text(data.candidate_code), columns, rows, structure, unit: str(data.unit), error: data.error as string | null };
}
function evidence(value: unknown): Evidence {
  const data = object(value), candidate = object(data.candidate), execution = result(data.result);
  const parsed = { code: text(candidate.code), canonical_name: text(candidate.canonical_name), unit: str(candidate.unit) };
  if (parsed.code !== execution.candidate_code || parsed.unit !== execution.unit || execution.error !== null) invalid();
  return { candidate: parsed, result: execution };
}
function decision(value: unknown): Decision {
  const data = object(value), kind = oneOf(data.decision, ["JAWAB", "TANYA", "TAHAN"]);
  const parsed: Decision = {
    decision: kind, answer: data.answer === null ? null : evidence(data.answer), evidence: array(data.evidence).map(evidence),
    reason_code: data.reason_code === null ? null : oneOf(data.reason_code, ["T0", "T1", "T2", "T3", "T4", "T5"] as const),
    suggestion: nullable(data.suggestion), period_used: nullable(data.period_used),
  };
  if (kind === "JAWAB" && (!parsed.answer || parsed.evidence.length || parsed.reason_code !== null || !parsed.period_used?.trim())) invalid();
  if (kind === "TANYA" && (parsed.answer !== null || parsed.evidence.length < 2 || parsed.reason_code !== null || !parsed.period_used?.trim())) invalid();
  if (kind === "TAHAN" && (parsed.answer !== null || parsed.evidence.length || parsed.reason_code === null || !parsed.suggestion?.trim())) invalid();
  if (new Set(parsed.evidence.map((item) => item.candidate.code)).size !== parsed.evidence.length) invalid();
  return parsed;
}
function question(value: unknown, session: string): QuestionResponse {
  const data = object(value), id_sesi = uuid(data.id_sesi);
  if (id_sesi !== session) invalid();
  return { id_sesi, id_log: uuid(data.id_log), decision: decision(data.decision) };
}
function catalog(value: unknown): CatalogResponse {
  const items = array(object(value).indikator).map((value): IndicatorMetadata => {
    const item = object(value);
    return { kode: text(item.kode), nama_kanonik: text(item.nama_kanonik), definisi_resmi: text(item.definisi_resmi),
      satuan: text(item.satuan), sumber: text(item.sumber), cakupan_wilayah: strings(item.cakupan_wilayah), periode_tersedia: strings(item.periode_tersedia) };
  });
  if (new Set(items.map((item) => item.kode)).size !== items.length) invalid();
  return { indikator: items };
}
function health(value: unknown): HealthResponse {
  const data = object(value);
  function service(value: unknown): ServiceHealth {
    const item = object(value), status = oneOf(item.status, ["AVAILABLE", "UNAVAILABLE", "UNKNOWN"]), checked_at = nullable(item.checked_at);
    if (checked_at !== null && (!/(Z|[+-]\d{2}:\d{2})$/.test(checked_at) || !Number.isFinite(Date.parse(checked_at)))) invalid();
    if (status === "AVAILABLE" && checked_at === null) invalid();
    return { status, checked_at, diagnostic_code: nullable(item.diagnostic_code ?? null) };
  }
  return { model: service(data.model), database: service(data.database) };
}
function logRecord(value: unknown): LogRecord {
  const data = object(value);
  const extraction = data.extraction === null ? null : (() => {
    const item = object(data.extraction);
    return { raw_question: str(item.raw_question), terms: strings(item.terms), regions: strings(item.regions), period: nullable(item.period),
      operation: oneOf(item.operation, ["NONE", "SUM", "AVG", "RANK"]), rank_direction: item.rank_direction === null ? null : oneOf(item.rank_direction, ["highest", "lowest"]),
      top_n: integer(item.top_n), unresolved: strings(item.unresolved) };
  })();
  const latency_ms = Object.fromEntries(Object.entries(object(data.latency_ms)).map(([key, value]) => {
    const time = finite(value); if (time < 0) invalid(); return [key, time];
  }));
  return { run_id: text(data.run_id), session_id: uuid(data.session_id), question: str(data.question), extraction,
    k: strings(data.k), k_prime: strings(data.k_prime), skeletons: array(data.skeletons).map((value) => {
      const item = object(value); return { sql: str(item.sql), valid: bool(item.valid), reject_reason: nullable(item.reject_reason) };
    }), votes: array(data.votes).map((value) => {
      const item = object(value); return { candidate_code: str(item.candidate_code), result: result(item.result, true), votes: integer(item.votes), tie: bool(item.tie) };
    }), decision: data.decision === null ? null : decision(data.decision), mode: oneOf(data.mode, ["K1", "K2", "K3"]), latency_ms,
    model_name: nullable(data.model_name), prompt_version: nullable(data.prompt_version), dictionary_hash: nullable(data.dictionary_hash) };
}
function httpError(status: number): ApiError {
  const messages: Record<number, string> = {
    404: "Log tidak ditemukan atau tidak tersedia untuk sesi ini.",
    409: "Pilihan bertentangan dengan status log atau pilihan yang sudah tersimpan. Bukti asal tetap ditampilkan.",
    422: "Permintaan atau pilihan belum dapat diterima. Periksa kembali isian Anda.",
    503: "Layanan belum tersedia. Periksa kembali status layanan.",
  };
  return new ApiError(status, "HTTP_" + status, messages[status] ?? "Permintaan belum dapat diselesaikan. Periksa layanan lalu coba lagi secara manual.");
}
async function request(path: string, init: RequestInit = {}, healthProbe = false): Promise<unknown> {
  let response: Response;
  try { response = await fetch("/api" + path, { ...init, cache: "no-store", credentials: "same-origin", redirect: "error" }); }
  catch { throw new ApiError(0, "NETWORK_ERROR", "Server lokal belum dapat dihubungi. Periksa layanan lalu coba lagi secara manual."); }
  if (!response.ok && !(healthProbe && response.status === 503)) throw httpError(response.status);
  let payload: unknown;
  try { payload = await response.json(); } catch { return invalid(); }
  if (healthProbe) {
    const checked = health(payload);
    const ready = checked.model.status === "AVAILABLE" && checked.database.status === "AVAILABLE";
    if ((response.status === 200) !== ready) invalid();
    return checked;
  }
  return payload;
}
function post(body: unknown): RequestInit { return { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }; }

export const api = {
  async tanya(pertanyaan: string, id_sesi: string): Promise<QuestionResponse> {
    return question(await request("/tanya", post({ pertanyaan, id_sesi: uuid(id_sesi) })), id_sesi);
  },
  async klarifikasi(id_sesi: string, id_log: string, indikator_pilihan: string, period: string | null, selected: Evidence): Promise<QuestionResponse> {
    const parsed = question(await request("/klarifikasi", post({ id_sesi: uuid(id_sesi), id_log: uuid(id_log), indikator_pilihan })), id_sesi);
    if (parsed.id_log !== id_log || parsed.decision.decision !== "JAWAB" || parsed.decision.answer?.candidate.code !== indikator_pilihan ||
      parsed.decision.period_used !== period || JSON.stringify(parsed.decision.answer) !== JSON.stringify(evidence(selected))) invalid();
    return parsed;
  },
  async katalog(): Promise<CatalogResponse> { return catalog(await request("/katalog")); },
  async kesehatan(): Promise<HealthResponse> { return health(await request("/kesehatan", {}, true)); },
  async log(id_log: string, id_sesi: string): Promise<LogResponse> {
    const data = object(await request("/log/" + uuid(id_log), { headers: { "X-Session-ID": uuid(id_sesi) } }));
    const record = logRecord(data.record);
    if (uuid(data.id_log) !== id_log || record.session_id !== id_sesi) invalid();
    return { id_log, record };
  },
};
