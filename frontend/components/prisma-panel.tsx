"use client";

import { useEffect, useRef, useState, type ReactNode, type FormEvent, type CSSProperties } from "react";
import { api, ApiError, type Evidence, type HealthResponse, type IndicatorMetadata, type LogResponse, type QuestionResponse, type ReasonCode } from "../lib/api";

function Logo({ ukuran = 28, animasi = false }: { ukuran?: number; animasi?: boolean }) {
  return (
    <svg width={ukuran} height={ukuran} viewBox="0 0 64 64" aria-hidden="true" className={animasi ? "logo-anim" : ""}>
      <defs>
        <linearGradient id="logo-kaca" x1="0.1" y1="0" x2="0.9" y2="1">
          <stop offset="0" stopColor="#FFFFFF" stopOpacity="0.95" />
          <stop offset="0.55" stopColor="#CFDDF5" stopOpacity="0.92" />
          <stop offset="1" stopColor="#A9BEE3" stopOpacity="0.95" />
        </linearGradient>
        <filter id="logo-pendar" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="1.4" /></filter>
      </defs>
      <line className="berkas-masuk" x1="1" y1="40" x2="20" y2="33" stroke="#FFFFFF" strokeWidth="3" strokeLinecap="round" />
      <line className="berkas-masuk" x1="1" y1="40" x2="20" y2="33" stroke="var(--ink)" strokeOpacity="0.55" strokeWidth="2" strokeLinecap="round" />
      <path d="M28.6 13.2 Q32 7 35.4 13.2 L51.6 45 Q55 52 47 52 H17 Q9 52 12.4 45 Z" fill="url(#logo-kaca)" stroke="#FFFFFF" strokeWidth="1.6" strokeLinejoin="round" />
      <path d="M29 18 L22 32" stroke="#FFFFFF" strokeWidth="2.4" strokeLinecap="round" opacity="0.9" />
      <g className="berkas-keluar" strokeLinecap="round">
        <g filter="url(#logo-pendar)" strokeWidth="4.5" opacity="0.6">
          <line x1="43" y1="30" x2="62" y2="22" stroke="var(--jawab)" />
          <line x1="45" y1="34" x2="62" y2="34" stroke="var(--tanya)" />
          <line x1="47" y1="38" x2="62" y2="46" stroke="var(--tahan)" />
        </g>
        <g strokeWidth="2.6">
          <line x1="43" y1="30" x2="62" y2="22" stroke="var(--jawab)" />
          <line x1="45" y1="34" x2="62" y2="34" stroke="var(--tanya)" />
          <line x1="47" y1="38" x2="62" y2="46" stroke="var(--tahan)" />
        </g>
      </g>
    </svg>
  );
}

const TUBUH = "M53.2 26.4 Q60 14 66.8 26.4 Q86.5 52.8 99.2 83.8 Q104.5 96 92 96 Q60 100.5 28 96 Q15.5 96 20.8 83.8 Q33.5 52.8 53.2 26.4 Z";

function Maskot({ ekspresi = "menyapa", ukuran = 96, className = "" }: { ekspresi?: "menyapa" | "berpikir" | "bingung" | "menyesal"; ukuran?: number; className?: string }) {
  const sedih = ekspresi === "menyesal";
  const mata = (cx: number, cy: number, o: { dx?: number; dy?: number; s?: number } = {}) => {
    const { dx = 0, dy = 0, s = 1 } = o;
    return (
      <g className={ekspresi === "menyapa" ? "kedip" : ""} style={{ transformOrigin: `${cx}px ${cy}px` }}>
        <ellipse cx={cx} cy={cy} rx={9.6 * s} ry={11 * s} fill="#FFFFFF" />
        <ellipse cx={cx} cy={cy} rx={9.6 * s} ry={11 * s} fill="none" stroke="#1B2A4A" strokeOpacity="0.12" strokeWidth="1" />
        <circle cx={cx + dx} cy={cy + dy} r={6.9 * s} fill="url(#m-iris)" />
        <circle cx={cx + dx} cy={cy + dy} r={3.1 * s} fill="#0B0E2A" />
        <circle cx={cx + dx + 2.4 * s} cy={cy + dy - 2.9 * s} r={2.4 * s} fill="#FFFFFF" />
        <circle cx={cx + dx - 2.2 * s} cy={cy + dy + 2.6 * s} r={1.1 * s} fill="#FFFFFF" opacity="0.85" />
      </g>
    );
  };
  const garis = { fill: "none", stroke: "#1B2A4A", strokeWidth: 2.6, strokeLinecap: "round", strokeLinejoin: "round" } as const;
  return (
    <svg width={ukuran} height={ukuran} viewBox="0 0 120 120" role="img" aria-label={`Maskot PRISMA sedang ${ekspresi}`}
      className={`shrink-0 overflow-visible ${ekspresi === "menyapa" || ekspresi === "berpikir" ? "melayang" : ""} ${className}`}>
      <defs>
        <linearGradient id="m-tubuh" x1="0.15" y1="0" x2="0.85" y2="1">
          <stop offset="0" stopColor="#F4F9FF" />
          <stop offset="0.5" stopColor="#D3E0F4" />
          <stop offset="1" stopColor="#AFC2E2" />
        </linearGradient>
        <radialGradient id="m-volume" cx="0.42" cy="0.38" r="0.7">
          <stop offset="0.55" stopColor="#FFFFFF" stopOpacity="0" />
          <stop offset="1" stopColor="#2A4F96" stopOpacity="0.28" />
        </radialGradient>
        <radialGradient id="m-iris" cx="0.4" cy="0.35" r="0.75">
          <stop offset="0" stopColor="#5A86D6" />
          <stop offset="0.7" stopColor="#2A4F96" />
          <stop offset="1" stopColor="#13284F" />
        </radialGradient>
        <radialGradient id="m-inti">
          <stop offset="0" stopColor="#FFFFFF" />
          <stop offset="0.5" stopColor="#E6EEFB" stopOpacity="0.8" />
          <stop offset="1" stopColor="#E6EEFB" stopOpacity="0" />
        </radialGradient>
                <clipPath id="m-klip"><path d={TUBUH} /></clipPath>
        <filter id="m-kabur" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="2.2" /></filter>
        <filter id="m-kabur-besar" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="4" /></filter>
      </defs>

      <ellipse cx="60" cy="110" rx="34" ry="4.5" fill="#1B2F57" opacity="0.16" filter="url(#m-kabur-besar)" />

      <path d={TUBUH} fill="url(#m-tubuh)" />
      <g clipPath="url(#m-klip)">
        <circle cx="60" cy="42" r={sedih ? 8 : 13} fill="url(#m-inti)" opacity={sedih ? 0.4 : 1} />
        <path d={TUBUH} fill="url(#m-volume)" />
        <ellipse cx="42" cy="44" rx="5" ry="13" fill="#FFFFFF" opacity="0.85" transform="rotate(32 42 44)" filter="url(#m-kabur)" />
      </g>
      <path d={TUBUH} fill="none" stroke="#FFFFFF" strokeWidth="1.8" strokeOpacity="0.95" />
      <circle cx="33" cy="64" r="1.6" fill="#FFFFFF" />

      {ekspresi === "berpikir" && (
        <g className="putar" style={{ transformOrigin: "60px 42px" }}>
          <circle cx="60" cy="32" r="3" fill="var(--jawab)" />
          <circle cx="68.7" cy="47" r="3" fill="var(--tanya)" />
          <circle cx="51.3" cy="47" r="3" fill="var(--tahan)" />
        </g>
      )}
      {ekspresi === "bingung" && (
        <g strokeWidth="3" strokeLinecap="round">
          <line x1="60" y1="45" x2="50" y2="31" stroke="var(--tanya)" />
          <line x1="60" y1="45" x2="70" y2="31" stroke="var(--tahan)" />
        </g>
      )}

      <g opacity={sedih ? 0.2 : 0.45}>
        <ellipse cx="35.5" cy="80" rx="6.5" ry="4" fill="#E8A3B4" filter="url(#m-kabur)" />
        <ellipse cx="84.5" cy="80" rx="6.5" ry="4" fill="#E8A3B4" filter="url(#m-kabur)" />
      </g>

      {ekspresi === "menyapa" && (
        <>
          {mata(47, 66)}{mata(73, 66)}
          <path d="M52 79 Q60 91 68 79 Z" fill="#1B2A4A" />

        </>
      )}
      {ekspresi === "berpikir" && <>{mata(47, 66, { dx: 2.2, dy: -3 })}{mata(73, 66, { dx: 2.2, dy: -3 })}<path d="M55 84 Q60 82 65 84" {...garis} /></>}
      {ekspresi === "bingung" && (
        <>
          {mata(47, 66, { dx: -1 })}{mata(73, 67, { s: 0.82, dx: 1 })}
          <path d="M65 52 Q72 47 80 51" {...garis} strokeWidth="2.4" />
          <path d="M51 84 q4.5 -3 9 0 t9 0" {...garis} />
        </>
      )}
      {ekspresi === "menyesal" && (
        <>
          {mata(47, 67, { dy: 2.8 })}{mata(73, 67, { dy: 2.8 })}
          <path d="M37 66 A10 10 0 0 1 57 66 Z" fill="#D3E0F4" />
          <path d="M63 66 A10 10 0 0 1 83 66 Z" fill="#D3E0F4" />
          <path d="M38 56 L54 52" {...garis} strokeWidth="2.4" />
          <path d="M66 52 L82 56" {...garis} strokeWidth="2.4" />
          <path d="M52 87 Q60 81 68 87" {...garis} />
        </>
      )}
    </svg>
  );
}

/* --------------------------- Elemen kecil umum --------------------------- */

function Aurora() {
  return (
    <div className="aurora" aria-hidden="true">
      <span className="gumpal g1" /><span className="gumpal g2" /><span className="gumpal g3" />
      <span className="gumpal g4" /><span className="gumpal g5" />
    </div>
  );
}



export function formatCell(value: string | number | null): string {
  if (value === null) return "Nilai tidak tersedia";
  if (typeof value === "string") return value;
  return new Intl.NumberFormat("id-ID", { maximumSignificantDigits: 21 }).format(value);
}
function safeMessage(error: unknown): string {
  return error instanceof ApiError ? error.message : "Permintaan belum dapat diselesaikan. Periksa layanan lalu coba lagi secara manual.";
}
const reasonMessages: Record<ReasonCode, string> = {
  T0: "Jawaban ditahan karena layanan model atau basis data belum dapat menyelesaikan permintaan.",
  T1: "Istilah indikator belum ditemukan pada katalog penelitian.",
  T2: "Periode atau wilayah yang diminta tidak tersedia untuk kandidat indikator.",
  T3: "Operasi yang diminta tidak sesuai dengan satuan indikator.",
  T4: "Sistem belum memperoleh kueri yang lolos pemeriksaan.",
  T5: "Seluruh hasil pencarian data kosong.",
};
function ResultTable({ evidence }: { evidence: Evidence }) {
  const result = evidence.result;
  return <div className="result-scroll" role="region" aria-label={"Hasil " + evidence.candidate.canonical_name} tabIndex={0}>
    <table className="result-table">
      <caption className="sr-only">Hasil {evidence.candidate.canonical_name}; satuan {evidence.candidate.unit}</caption>
      <thead><tr>{result.columns.map((column, index) => <th scope="col" key={index}>{column}</th>)}</tr></thead>
      <tbody>{result.rows.map((row, index) => <tr key={index}>{row.map((cell, column) =>
        <td key={column}>{formatCell(cell)}{typeof cell === "number" && <details className="raw-value"><summary>Nilai asli</summary><code>{String(cell)}</code></details>}</td>)}</tr>)}</tbody>
    </table>
    {!result.rows.length && <p>Tidak ada baris pada respons ini.</p>}
  </div>;
}
function EvidenceCard({ evidence, period }: { evidence: Evidence; period: string | null }) {
  return <div className="kaca-dalam evidence-card">
    <h3>{evidence.candidate.canonical_name}</h3>
    <p className="muted code">{evidence.candidate.code}</p>
    <ResultTable evidence={evidence} />
    <div className="metadata">
      <span className="meta">Satuan: {evidence.candidate.unit || "Belum tersedia"}</span>
      {period && <span className="meta">Periode: <span>{period}</span></span>}
    </div>
    <p className="muted">Sumber rinci belum tersedia pada respons ini.</p>
    <p className="muted">Cakupan wilayah belum tersedia pada respons ini.</p>
  </div>;
}
function LogContent({ data }: { data: LogResponse }) {
  const record = data.record;
  return <div className="log-content">
    <p>Rincian tersedia sebagian. Log ini belum memuat keluaran mentah model, indeks sampel, atau seluruh vektor eksekusi.</p>
    <dl className="log-meta">
      <dt>Keputusan asal</dt><dd>{record.decision?.decision ?? "Tidak tercatat"}</dd>
      <dt>Pertanyaan</dt><dd>{record.question}</dd>
      <dt>Model</dt><dd>{record.model_name ?? "Tidak tercatat"}</dd>
      <dt>Versi prompt</dt><dd>{record.prompt_version ?? "Tidak tercatat"}</dd>
      <dt>Hash kamus</dt><dd className="code">{record.dictionary_hash ?? "Tidak tercatat"}</dd>
      <dt>K</dt><dd>{record.k.join(", ") || "Kosong"}</dd>
      <dt>K′</dt><dd>{record.k_prime.join(", ") || "Kosong"}</dd>
    </dl>
    <h3>Ekstraksi</h3>
    {record.extraction ? <dl className="log-meta">
      <dt>Istilah</dt><dd>{record.extraction.terms.join(", ") || "Kosong"}</dd>
      <dt>Wilayah (kode)</dt><dd>{record.extraction.regions.join(", ") || "Tidak dibatasi pada ekstraksi"}</dd>
      <dt>Periode diminta</dt><dd>{record.extraction.period ?? "Terbaru menurut alur backend"}</dd>
      <dt>Operasi</dt><dd>{record.extraction.operation}</dd>
      <dt>Belum terselesaikan</dt><dd>{record.extraction.unresolved.join(", ") || "Kosong"}</dd>
    </dl> : <p>Tidak tercatat.</p>}
    <h3>Latensi tercatat</h3>
    {Object.keys(record.latency_ms).length ? <ul>{Object.entries(record.latency_ms).map(([step, time]) =>
      <li key={step}>{step}: {formatCell(time)} ms</li>)}</ul> : <p>Tidak tercatat.</p>}
    <h3>Kerangka SQL</h3>
    {!record.skeletons.length && <p>Tidak tercatat.</p>}
    {record.skeletons.map((skeleton, index) => <details key={index}><summary>Kerangka {index + 1} · {skeleton.valid ? "Lolos validasi" : "Ditolak"}</summary>
      <pre>{skeleton.sql}</pre>{skeleton.reject_reason && <p>{skeleton.reject_reason}</p>}</details>)}
    <h3>Voting</h3>
    <p>Entri kandidat berasal dari vektor pemenang yang sama. Jumlah suara ini bukan perbandingan popularitas antarindikator.</p>
    {!record.votes.length && <p>Tidak tercatat.</p>}
    {record.votes.map((vote, index) => <div className="kaca-dalam evidence-card" key={index}>
      <p>{vote.candidate_code}: {formatCell(vote.votes)} suara{vote.tie ? " · Seri" : ""}</p>
      {vote.result.error ? <p>Eksekusi tidak berhasil pada entri ini.</p> :
        <ResultTable evidence={{ candidate: { code: vote.candidate_code, canonical_name: vote.candidate_code, unit: vote.result.unit }, result: vote.result }} />}
    </div>)}
    <details><summary>Identitas log</summary><dl className="log-meta">
      <dt>ID log</dt><dd className="code">{data.id_log}</dd><dt>ID run</dt><dd className="code">{record.run_id}</dd>
    </dl></details>
  </div>;
}
function LogDialog({ idLog, session, onClose }: { idLog: string; session: string; onClose: () => void }) {
  const ref = useRef<HTMLDivElement>(null);
  const [data, setData] = useState<LogResponse | null>(null), [error, setError] = useState<string | null>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    ref.current?.querySelector<HTMLButtonElement>("button")?.focus();
    let active = true;
    api.log(idLog, session).then((value) => { if (active) setData(value); }).catch((err) => { if (active) setError(safeMessage(err)); });
    return () => { active = false; previous?.focus(); };
  }, [idLog, session]);
  return <div className="dialog-backdrop" onClick={(event) => { if (event.target === event.currentTarget) onClose(); }}>
    <div className="kaca-tebal log-dialog" role="dialog" aria-modal="true" aria-labelledby="log-title" ref={ref} onKeyDown={(event) => {
      if (event.key === "Escape") { event.stopPropagation(); onClose(); }
      if (event.key === "Tab") {
        const nodes = Array.from(ref.current?.querySelectorAll<HTMLElement>('button, summary, [tabindex="0"]') ?? []);
        const first = nodes[0], last = nodes[nodes.length - 1];
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
        if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
      }
    }}>
      <div className="section-heading"><h2 id="log-title">Cara PRISMA berpikir</h2><button className="tombol tombol-kaca !h-9 !w-9 !p-0" onClick={onClose} aria-label="Tutup rincian proses"><I n="tutup" className="h-4 w-4" /></button></div>
      {!data && !error && <p role="status">Memuat rincian proses.</p>}
      {error && <p role="alert">{error}</p>}
      {data && <LogContent data={data} />}
    </div>
  </div>;
}
function Catalog({ onUse }: { onUse: (item: IndicatorMetadata) => void }) {
  const [data, setData] = useState<IndicatorMetadata[] | null>(null), [error, setError] = useState<string | null>(null), [search, setSearch] = useState("");
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let active = true; setError(null);
    api.katalog().then((value) => { if (active) setData(value.indikator); }).catch((err) => { if (active) setError(safeMessage(err)); });
    return () => { active = false; };
  }, [attempt]);
  const query = search.toLocaleLowerCase("id-ID").trim();
  const matched = data?.filter((item) => [item.kode, item.nama_kanonik, item.definisi_resmi, item.satuan, item.sumber, ...item.cakupan_wilayah, ...item.periode_tersedia].join(" ").toLocaleLowerCase("id-ID").includes(query));

  return <div className="mx-auto max-w-6xl space-y-6 pb-20">
    <section className="space-y-3 pt-4 sm:pt-6">
      <h1 className="font-display text-[44px] font-bold leading-[1.02] tracking-[-0.03em] text-ink sm:text-[60px]">Katalog <span className="teks-aksen">Data</span></h1>
      <p className="max-w-[60ch] text-[17px] leading-relaxed text-ink-2">Semua indikator dari katalog backend. Cari nama resmi, kode, wilayah, atau periode yang tersedia.</p>
    </section>
    <label htmlFor="cari-istilah" className="kaca-tebal flex items-center gap-3 rounded-full px-5 py-3.5">
      <I n="cari" className="h-5 w-5 shrink-0 text-ink-3" />
      <input id="cari-istilah" aria-label="Cari indikator" value={search} onChange={(event) => setSearch(event.target.value)}
        placeholder="Cari istilah, misalnya pengangguran" className="min-w-0 flex-1 bg-transparent text-[16px] text-ink placeholder:text-ink-3 focus:outline-none" />
      {search && <button onClick={() => setSearch("")} aria-label="Hapus pencarian"><I n="tutup" /></button>}
    </label>
    {error && <div role="alert" className="kaca-tebal rounded-[28px] p-5"><p>{error}</p><button className="tombol tombol-kaca" onClick={() => setAttempt((value) => value + 1)}>Muat ulang katalog</button></div>}
    {!data && !error && <div className="kaca-tebal rounded-[28px] p-5" role="status">Memuat katalog.</div>}
    {data?.length === 0 && <p>Katalog belum memuat indikator.</p>}
    {!!data?.length && !matched?.length && <p>Belum ada indikator yang cocok.</p>}
    {!!matched?.length && <>
      <p className="px-1 text-[14px] font-medium text-ink-2">{matched.length} indikator cocok</p>
      <div className="kaca-tebal overflow-hidden rounded-[28px]">
        <div className="overflow-x-auto" role="region" aria-label="Daftar indikator" tabIndex={0}>
          <table className="w-full min-w-[860px] text-left text-[14px]">
            <thead><tr className="border-b border-line font-display text-[12px] uppercase tracking-[0.08em] text-ink-3">
              {["Indikator", "Definisi", "Satuan", "Periode", "Sumber", "Cakupan wilayah", "Aksi"].map((label) => <th scope="col" className="px-5 py-3.5 font-semibold" key={label}>{label}</th>)}
            </tr></thead>
            <tbody>{matched.map((item) => <tr key={item.kode} className="baris border-b border-line align-top last:border-0">
              <td className="px-5 py-4"><p className="font-bold text-ink">{item.nama_kanonik}</p><p className="mt-0.5 font-mono text-[12px] text-ink-3">{item.kode}</p></td>
              <td className="px-5 py-4 leading-relaxed text-ink-2">{item.definisi_resmi}</td>
              <td className="px-5 py-4"><span className="meta">{item.satuan}</span></td>
              <td className="px-5 py-4 text-[13px]">{item.periode_tersedia.join(", ") || "Belum tersedia"}</td>
              <td className="px-5 py-4 text-[13px] text-ink-2">{item.sumber}</td>
              <td className="px-5 py-4 text-[13px] text-ink-2">{item.cakupan_wilayah.join(", ") || "Belum tersedia"}</td>
              <td className="px-5 py-4"><Tombol onClick={() => onUse(item)} className="!py-1.5 !text-[13px]">Tanyakan</Tombol></td>
            </tr>)}</tbody>
          </table>
        </div>
      </div>
    </>}
  </div>;
}


const DOMAIN = [
  { id: "kemiskinan", label: "Kemiskinan" },
  { id: "ketenagakerjaan", label: "Ketenagakerjaan" },
  { id: "pendidikan", label: "Pendidikan" },
] as const;

const CONTOH = {
  kemiskinan: ["Provinsi mana yang paling miskin?", "Berapa total penduduk miskin di Pulau Jawa?"],
  ketenagakerjaan: ["Berapa tingkat pengangguran terbuka di Jawa Barat?", "Berapa jumlah pengangguran di Banten?"],
  pendidikan: ["Berapa partisipasi sekolah SMA di Jawa Barat?", "Berapa angka partisipasi murni SMA di Aceh?"],
};

const Ikon = {
  kirim: <path d="M5 12h13M13 6l6 6-6 6" />,
  kalender: <><rect x="4" y="5" width="16" height="15" rx="3" /><path d="M4 10h16M9 3v4M15 3v4" /></>,
  sumber: <><path d="M7 3h7l5 5v13H7z" /><path d="M14 3v5h5M10 13h6M10 17h6" /></>,
  satuan: <><path d="M4 16l12-12 4 4-12 12H4z" /><path d="M9 11l2 2M12 8l2 2" /></>,
  langkah: <><circle cx="6" cy="6" r="2" /><circle cx="6" cy="18" r="2" /><path d="M6 8v8M11 6h9M11 18h9M11 12h6" /></>,
  salin: <><rect x="8" y="8" width="12" height="12" rx="3" /><path d="M16 8V6a2 2 0 00-2-2H6a2 2 0 00-2 2v8a2 2 0 002 2h2" /></>,
  cari: <><circle cx="11" cy="11" r="6.5" /><path d="M16 16l4 4" /></>,
  tutup: <path d="M6 6l12 12M18 6L6 18" />,
  cek: <path d="M5 12.5l4.5 4.5L19 7.5" />,
  panah: <path d="M7 17L17 7M9 7h8v8" />,
  info: <><circle cx="12" cy="12" r="9" /><path d="M12 11v5M12 8h.01" /></>,
  kemiskinan: <><path d="M4 11l8-6 8 6" /><path d="M6 10v9h12v-9M10 19v-5h4v5" /></>,
  ketenagakerjaan: <><rect x="3.5" y="7.5" width="17" height="12" rx="2.5" /><path d="M9 7.5V6a2 2 0 012-2h2a2 2 0 012 2v1.5M3.5 12.5h17" /></>,
  pendidikan: <><path d="M2.5 9.5L12 5l9.5 4.5L12 14z" /><path d="M6.5 11.5v4c0 1.5 2.5 3 5.5 3s5.5-1.5 5.5-3v-4" /></>,
};

function I({ n, className = "w-4 h-4" }: { n: keyof typeof Ikon; className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {Ikon[n]}
    </svg>
  );
}

function PilKeputusan({ k }: { k: "JAWAB" | "TANYA" | "TAHAN" }) {
  return (
    <span className={`pil pil-${k.toLowerCase()}`}>
      <span className="pil-titik" />{k}
    </span>
  );
}

function Tombol({ children, onClick, varian = "kaca", disabled, type = "button", className = "" }: { children: ReactNode; onClick?: () => void; varian?: "kaca" | "utama" | "hantu"; disabled?: boolean; type?: "button" | "submit"; className?: string }) {
  return (
    <button type={type} onClick={onClick} disabled={disabled} className={`tombol tombol-${varian} ${className}`}>
      {children}
    </button>
  );
}

function Ubin({ domain, ukuran = "h-10 w-10", ikon = "h-5 w-5" }: { domain: DomainId; ukuran?: string; ikon?: string }) {
  return (
    <span className={`ubin ubin-${domain} ${ukuran}`}>
      <I n={domain} className={`${ikon} text-white`} />
    </span>
  );
}

function Meta({ ikon, label, isi }: { ikon: keyof typeof Ikon; label: string; isi: ReactNode }) {
  return (
    <span className="meta">
      <I n={ikon} className="h-3.5 w-3.5 shrink-0 opacity-60" />
      <span className="text-ink-3">{label}</span>
      <span className="font-semibold text-ink">{isi}</span>
    </span>
  );
}

function AksiKartu({ onLangkah, onSalin }: { onLangkah: () => void; onSalin: () => void }) {
  return (
    <div className="flex flex-wrap gap-2 border-t border-line pt-4">
      <button className="tombol tombol-kaca" aria-label="Lihat rincian proses" onClick={onLangkah}><I n="langkah" />Lihat langkah</button>
      <Tombol varian="hantu" onClick={onSalin}><I n="salin" />Salin jawaban</Tombol>
    </div>
  );
}

function Masuk({ onMasuk, awal }: { onMasuk: (profile: GuestProfile) => void; awal: GuestProfile | null }) {
  const [nama, setNama] = useState(awal?.nama || "");
  const [keperluan, setKeperluan] = useState<string | null>(awal?.keperluan || null);
  const [minat, setMinat] = useState<DomainId[]>(awal?.minat || []);
  const [kode, setKode] = useState(awal?.kode || "");
  const [setuju, setSetuju] = useState(!!awal?.setujuLog);

  const ubahMinat = (id: DomainId) => setMinat((m) => (m.includes(id) ? m.filter((x) => x !== id) : [...m, id]));
  const kirim = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!setuju) return;
    onMasuk({ nama: nama.trim(), keperluan, minat, kode: kode.trim(), setujuLog: true });
  };
  const lewati = () => onMasuk({ nama: "", keperluan: null, minat: [], kode: "", setujuLog: false });

  const label = "mb-2 block font-display text-[14px] font-semibold text-ink";

  return (
    <div className="gutter mx-auto grid min-h-screen max-w-6xl items-center gap-10 py-10 lg:grid-cols-[1fr_minmax(0,480px)] lg:gap-14">
      <div className="space-y-6">
        <div className="kaca inline-flex items-center gap-2.5 rounded-full py-1.5 pl-2 pr-4">
          <Logo ukuran={30} />
          <span className="font-display text-[17px] font-bold tracking-tight text-ink">PRISMA</span>
        </div>
        <Maskot ekspresi="menyapa" ukuran={150} />
        <h1 className="font-display max-w-[15ch] text-[42px] font-bold leading-[1.02] tracking-[-0.03em] text-ink sm:text-[58px]">
          Tanya data BPS, dapat jawaban yang <span className="teks-aksen">jelas asalnya.</span>
        </h1>
        <p className="max-w-[50ch] text-[17px] leading-relaxed text-ink-2">
          PRISMA menjalankan semua tafsir pertanyaanmu, membandingkannya, lalu memutuskan: menjawab, bertanya balik, atau menahan jawaban kalau belum aman.
        </p>
        <div className="flex flex-wrap gap-2">
          <PilKeputusan k="JAWAB" /><PilKeputusan k="TANYA" /><PilKeputusan k="TAHAN" />
        </div>
      </div>

      <form onSubmit={kirim} className="kaca-tebal min-w-0 space-y-5 rounded-[32px] p-6 sm:p-8">
        <div>
          <h2 className="font-display text-[24px] font-bold tracking-tight text-ink">Masuk sebagai tamu</h2>
          <p className="mt-1 text-[14px] text-ink-2">Tidak ada akun. Profil hanya di memori halaman; pertanyaan dan keputusan dicatat di server lokal.</p>
        </div>

        <div>
          <label htmlFor="nama" className={label}>Nama panggilan <span className="font-sans font-medium text-ink-3">(opsional)</span></label>
          <input id="nama" value={nama} onChange={(e) => setNama(e.target.value)} placeholder="misalnya Gigi" className="isian" autoComplete="off" />
        </div>

        <fieldset>
          <legend className={label}>Keperluan</legend>
          <div className="flex flex-wrap gap-2">
            {["Skripsi", "Tugas kuliah", "Sekadar ingin tahu"].map((k) => (
              <button type="button" key={k} onClick={() => setKeperluan(keperluan === k ? null : k)} className={`chip ${keperluan === k ? "chip-on" : ""}`} aria-pressed={keperluan === k}>{k}</button>
            ))}
          </div>
        </fieldset>

        <fieldset>
          <legend className={label}>Domain yang kamu minati</legend>
          <div className="grid grid-cols-3 gap-2">
            {DOMAIN.map((d) => {
              const on = minat.includes(d.id);
              return (
                <button type="button" key={d.id} onClick={() => ubahMinat(d.id)} aria-pressed={on}
                  className={`domain-pilih ${on ? "domain-on" : ""}`}>
                  <Ubin domain={d.id} ukuran="h-10 w-10" />
                  <span className="text-[12.5px] font-bold text-ink">{d.label}</span>
                  {on && <span className="domain-cek"><I n="cek" className="h-3 w-3" /></span>}
                </button>
              );
            })}
          </div>
        </fieldset>

        <div>
          <label htmlFor="kode" className={label}>Kode peserta studi <span className="font-sans font-medium text-ink-3">(opsional)</span></label>
          <input id="kode" value={kode} onChange={(e) => setKode(e.target.value)} placeholder="misalnya PRS-014" className="isian font-mono" autoComplete="off" />
        </div>

        <label htmlFor="setuju" className="kaca-dalam flex cursor-pointer items-start gap-3 rounded-[20px] p-4">
          <input id="setuju" type="checkbox" checked={setuju} onChange={(e) => setSetuju(e.target.checked)} className="mt-0.5 h-5 w-5 shrink-0 accent-[var(--accent)]" />
          <span className="text-[14px] leading-snug text-ink">Saya memahami pertanyaan dan keputusan disimpan pada log lokal. <span className="text-ink-3">(wajib untuk mulai bertanya)</span></span>
        </label>

        <div className="flex flex-wrap items-center gap-3 pt-1">
          <Tombol type="submit" varian="utama" disabled={!setuju} className="!px-7 !py-3 !text-[15px]">Mulai bertanya</Tombol>
          <Tombol varian="hantu" onClick={lewati}>Lewati</Tombol>
        </div>
        <p className="text-[12px] leading-snug text-ink-3">“Lewati” masuk tanpa nama dan tanpa log evaluasi.</p>
      </form>
    </div>
  );
}

function Navbar({ halaman, onPindah, profil, onUbahProfil }: { halaman: PageId; onPindah: (page: PageId) => void; profil: GuestProfile | null; onUbahProfil: () => void }) {
  const item = [["tanya", "Tanya", "Tanya"], ["katalog", "Katalog Data", "Katalog"], ["tentang", "Tentang", "Tentang"]] as const;
  return (
    <header className="gutter sticky z-40 pt-3" style={{ top: "env(safe-area-inset-top, 0px)" }}>
      <div className="kaca mx-auto flex max-w-4xl items-center gap-2 rounded-full p-1.5 pl-3">
        <button onClick={() => onPindah("tanya")} className="mr-auto flex items-center gap-2 rounded-full py-0.5 pr-2" aria-label="PRISMA, ke halaman Tanya">
          <Logo ukuran={28} />
          <span className="hidden font-display text-[17px] font-bold tracking-tight text-ink sm:inline">PRISMA</span>
        </button>
        <nav className="segmen flex items-center gap-0.5 rounded-full p-1" aria-label="Navigasi utama">
          {item.map(([id, l, pendek]) => (
            <button key={id} aria-label={l} onClick={() => onPindah(id)} aria-current={halaman === id ? "page" : undefined}
              className={`segmen-item ${halaman === id ? "segmen-on" : ""}`}>
              <span className="hidden sm:inline">{l}</span><span className="sm:hidden">{pendek}</span>
            </button>
          ))}
        </nav>
        <button onClick={onUbahProfil} className="tombol tombol-hantu ml-1 hidden !py-2 !text-[13px] md:inline-flex prisma-profile-button" title="Ubah profil">
          <span className="pil-titik" style={{ "--c": profil?.setujuLog ? "var(--jawab)" : "var(--tahan)", background: "var(--c)" } as CSSProperties} />
          {profil?.nama || "Tamu"}
        </button>
      </div>
    </header>
  );
}

const KODE_ALASAN = { T0: "Layanan belum dapat menyelesaikan permintaan", T1: "Istilah tidak dikenali", T2: "Periode atau wilayah tidak tersedia", T3: "Operasi tidak sah untuk satuannya", T4: "Tidak ada SQL yang lolos validasi", T5: "Data kosong" };
const TUJUH_LANGKAH = [
  ["Mengenali istilah", "Mencocokkan kata di pertanyaanmu dengan kamus indikator BPS."],
  ["Memilih kandidat indikator", "Menyaring indikator yang mungkin kamu maksud (K) menjadi yang datanya tersedia untuk periode dan wilayah itu (K′)."],
  ["Memeriksa ketersediaan", "Menyaring K menjadi K? menurut periode, wilayah, dan operasi yang sah."],
  ["Menyusun kerangka SQL", "Hanya langkah 4 memakai model lokal. Kerangka diperiksa sebelum dijalankan."],
  ["Menjalankan tafsir", "Setiap kerangka valid dieksekusi untuk seluruh kandidat K? pada basis data lokal."],
  ["Voting vektor hasil", "Vektor hasil yang sama dikelompokkan, lalu dipilih kelompok dengan suara terbanyak."],
  ["Membandingkan dan memutuskan", "Uji kesetaraan semua pasangan hasil: JAWAB, TANYA, atau TAHAN sesuai aturan."],
];

const TIGA_KEPUTUSAN = [
  ["JAWAB", "menyapa", "Semua tafsir setara. Kamu dapat jawaban lengkap dengan indikator, periode, satuan, dan sumber."],
  ["TANYA", "bingung", "Tafsir memberi jawaban berbeda. Semua tafsir ditampilkan berdampingan, kamu yang memilih."],
  ["TAHAN", "menyesal", "Belum aman dijawab. PRISMA menjelaskan alasannya dengan kode T1–T5 dan memberi saran."],
] as const;

function Tentang() {
  return (
    <div className="mx-auto max-w-5xl space-y-14 pb-20">
      <section className="flex flex-col gap-6 pt-4 sm:flex-row sm:items-end sm:pt-6">
        <div className="flex-1 space-y-3">
          <h1 className="font-display text-[44px] font-bold leading-[1.02] tracking-[-0.03em] text-ink sm:text-[60px]">Satu pertanyaan, <span className="teks-aksen">semua tafsir</span> dicoba.</h1>
          <p className="max-w-[60ch] text-[17px] leading-relaxed text-ink-2">
            Seperti prisma yang memecah cahaya, PRISMA memecah pertanyaanmu ke semua kemungkinan tafsirnya, lalu memeriksa apakah jawabannya sepakat. Kamu tidak perlu menulis kueri.
          </p>
        </div>
        <Maskot ekspresi="menyapa" ukuran={130} />
      </section>

      <section className="grid gap-4 md:grid-cols-3">
        {TIGA_KEPUTUSAN.map(([k, e, d]) => (
          <div key={k} className={`kaca-tebal halo-${k.toLowerCase()} space-y-3 rounded-[28px] p-5`}>
            <div className="flex items-center justify-between"><PilKeputusan k={k} /><Maskot ekspresi={e} ukuran={56} /></div>
            <p className="text-[14.5px] leading-relaxed text-ink-2">{d}</p>
          </div>
        ))}
      </section>

      <section className="space-y-5">
        <h2 className="font-display text-[28px] font-bold tracking-tight text-ink">Tujuh langkah di balik setiap jawaban</h2>
        <ol className="grid gap-3 sm:grid-cols-2">
          {TUJUH_LANGKAH.map(([j, d], i) => (
            <li key={j} className={`kaca flex gap-4 rounded-[24px] p-5 ${i === 6 ? "sm:col-span-2" : ""}`}>
              <span className="nomor">{i + 1}</span>
              <div className="min-w-0">
                <p className="font-display text-[16px] font-semibold text-ink">{j}</p>
                <p className="mt-1 text-[14px] leading-relaxed text-ink-2">{d}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>

      <section className="grid gap-4 md:grid-cols-[1.1fr_1fr_1fr]">
        <div className="kaca-tebal rounded-[28px] p-6">
          <h2 className="font-display text-[19px] font-bold text-ink">Kode alasan TAHAN</h2>
          <div className="mt-3 divide-y divide-line">
            {Object.entries(KODE_ALASAN).map(([k, v]) => (
              <div key={k} className="flex items-center gap-3 py-2.5">
                <span className="w-8 font-mono text-[14px] font-bold text-tahan-ink">{k}</span>
                <span className="text-[14.5px] text-ink">{v}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="kaca-tebal space-y-3 rounded-[28px] p-6">
          <h2 className="font-display text-[19px] font-bold text-ink">Batasan</h2>
          <ul className="daftar space-y-2 text-[14.5px] leading-relaxed text-ink-2">
            <li>Tiga domain: kemiskinan, ketenagakerjaan, pendidikan.</li>
            <li>Hanya tingkat provinsi, belum kabupaten/kota.</li>
            <li>Data diperbarui manual oleh tim, bisa tertinggal dari rilis BPS terbaru.</li>
            <li>Model kecil (Qwen2.5-Coder-1.5B-Instruct) bisa keliru, karena itu banyak tafsir dibandingkan.</li>
          </ul>
        </div>
        <div className="kaca-tebal space-y-3 rounded-[28px] p-6">
          <h2 className="font-display text-[19px] font-bold text-ink">Privasi</h2>
          <ul className="daftar space-y-2 text-[14.5px] leading-relaxed text-ink-2">
            <li>Model dan data berjalan lokal di komputer tempat PRISMA dipasang.</li>
            <li>Tidak ada akun, email, atau kata sandi.</li>
            <li>Pertanyaan dan keputusan dicatat pada log lokal untuk setiap permintaan. Profil tamu hanya disimpan di memori halaman.</li>
          </ul>
        </div>
      </section>
    </div>
  );
}


type DomainId = "kemiskinan" | "ketenagakerjaan" | "pendidikan";
type GuestProfile = { nama: string; keperluan: string | null; minat: DomainId[]; kode: string; setujuLog: boolean };
type PageId = "tanya" | "katalog" | "tentang";

function Examples({ profile, compact, disabled, onChoose }: { profile: GuestProfile | null; compact: boolean; disabled: boolean; onChoose: (question: string) => void }) {
  const [expanded, setExpanded] = useState(false);
  const domains = [...DOMAIN].sort((a, b) => Number(profile?.minat.includes(b.id)) - Number(profile?.minat.includes(a.id)));
  return <section className="scroll-mt-28 space-y-3">
    <div className="flex items-center justify-between gap-3 px-1">
      <h2 className="font-display text-[14px] font-semibold uppercase tracking-[0.08em] text-ink-3">Contoh pertanyaan</h2>
      {compact && <button onClick={() => setExpanded((value) => !value)} className="text-[13px] font-bold text-accent hover:underline">{expanded ? "Ringkas" : "Lihat semua"}</button>}
    </div>
    {compact && !expanded ? <div className="-mx-1 flex gap-2 overflow-x-auto px-1 pb-2">
      {domains.flatMap((domain) => CONTOH[domain.id].map((question) => <button key={question} onClick={() => onChoose(question)} disabled={disabled} className="chip shrink-0 !pl-1.5">
        <Ubin domain={domain.id} ukuran="h-7 w-7" ikon="h-3.5 w-3.5" />{question}</button>))}
    </div> : <div className="grid gap-4 md:grid-cols-3">
      {domains.map((domain) => <div key={domain.id} className="kaca min-w-0 space-y-3 rounded-[28px] p-4">
        <div className="flex items-center gap-3 px-1"><Ubin domain={domain.id} /><div className="min-w-0">
          <p className="font-display text-[16px] font-semibold text-ink">{domain.label}</p>
          {profile?.minat.includes(domain.id) && <p className="text-[12px] font-semibold text-ink-3">Minatmu</p>}
        </div></div>
        {CONTOH[domain.id].map((question) => <button key={question} onClick={() => onChoose(question)} disabled={disabled} className="contoh group">
          <span>{question}</span><I n="panah" className="mt-0.5 h-4 w-4 shrink-0 text-ink-3 transition group-hover:text-accent" />
        </button>)}
      </div>)}
    </div>}
  </section>;
}
function Startup({ status, onContinue }: { status: string; onContinue: () => void }) {
  return <div className="gutter flex min-h-screen items-center justify-center py-10">
    <div className="kaca muncul flex w-full max-w-sm flex-col items-center gap-5 rounded-[36px] px-8 py-10 text-center">
      <div className="relative flex items-end"><Logo ukuran={104} animasi /><Maskot ekspresi="menyapa" ukuran={70} className="-ml-3 mb-1" /></div>
      <div className="space-y-1.5"><p className="font-display text-[36px] font-bold tracking-[-0.02em] text-ink">PRISMA</p><p role="status" className="text-[15px] font-medium text-ink-2">{status}</p></div>
      <div className="h-1.5 w-52 overflow-hidden rounded-full bg-line" aria-hidden="true"><div className="startup-activity h-full rounded-full" /></div>
      <Tombol varian="hantu" onClick={onContinue}>Lewati</Tombol>
    </div>
  </div>;
}

export default function PrismaPanel() {
  const [stage, setStage] = useState<"loading" | "masuk" | "app">("loading");
  const [profile, setProfile] = useState<GuestProfile | null>(null);
  const [page, setPage] = useState<"tanya" | "katalog" | "tentang">("tanya");
  const [draft, setDraft] = useState(""), [validation, setValidation] = useState<string | null>(null);
  const [session, setSession] = useState<string | null>(null), [sessionError, setSessionError] = useState<string | null>(null);
  const [health, setHealth] = useState<HealthResponse | null>(null), [healthError, setHealthError] = useState<string | null>(null), [checking, setChecking] = useState(false);
  const [response, setResponse] = useState<QuestionResponse | null>(null), [original, setOriginal] = useState<QuestionResponse | null>(null);
  const [submitted, setSubmitted] = useState(""), [selected, setSelected] = useState<string | null>(null);
  const [pending, setPending] = useState<"question" | "choice" | null>(null), [error, setError] = useState<string | null>(null);
  const [logOpen, setLogOpen] = useState(false), [copyStatus, setCopyStatus] = useState("");
  const requestId = useRef(0), locked = useRef(false), healthId = useRef(0);
  const input = useRef<HTMLTextAreaElement>(null), resultHeading = useRef<HTMLHeadingElement>(null);
  const active = useRef(true), healthLocked = useRef(false);
  const isReady = health?.model.status === "AVAILABLE" && health.database.status === "AVAILABLE";
  const canSubmit = Boolean(session && isReady && !checking && !pending);

  async function checkHealth() {
    if (healthLocked.current) return;
    healthLocked.current = true;
    const version = ++healthId.current;
    setChecking(true); setHealthError(null);
    try { const value = await api.kesehatan(); if (active.current && version === healthId.current) setHealth(value); }
    catch (err) { if (active.current && version === healthId.current) { setHealth(null); setHealthError(safeMessage(err)); } }
    finally { if (active.current && version === healthId.current) { setChecking(false); healthLocked.current = false; } }
  }
  useEffect(() => {
    active.current = true;
    try { setSession(crypto.randomUUID()); } catch { setSessionError("Sesi aman belum dapat dibuat. Buka aplikasi melalui localhost atau HTTPS."); }
    void checkHealth();
    return () => { active.current = false; requestId.current++; healthId.current++; healthLocked.current = false; };
  // A session and optional guest presentation preferences belong to this mounted page.
  }, []);

  useEffect(() => {
    if (stage === "loading" && !checking && (health || healthError)) setStage("masuk");
  }, [stage, checking, health, healthError]);
  useEffect(() => {
    if (input.current) {
      input.current.style.height = "auto";
      input.current.style.height = input.current.scrollHeight + "px";
    }
  }, [draft, stage]);

  function startNew() {
    requestId.current++; locked.current = false; setPending(null); setResponse(null); setOriginal(null); setSelected(null);
    setSubmitted(""); setDraft(""); setError(null); setValidation(null); setLogOpen(false); setCopyStatus(""); setPage("tanya");
    input.current?.focus();
  }
  async function submit(provided?: string) {
    if (locked.current) return;
    const question = (provided ?? draft).trim();
    if (!question) { setValidation("Tulis pertanyaan terlebih dahulu."); input.current?.focus(); return; }
    if (!canSubmit || !session) return;
    const version = ++requestId.current;
    setDraft(question);
    locked.current = true; setPending("question"); setError(null); setValidation(null); setResponse(null); setOriginal(null); setSelected(null); setSubmitted(question); setCopyStatus("");
    try {
      const value = await api.tanya(question, session);
      if (active.current && version === requestId.current) { setResponse(value); setOriginal(value.decision.decision === "TANYA" ? value : null); }
    } catch (err) {
      if (active.current && version === requestId.current) {
        setError(safeMessage(err));
        if (err instanceof ApiError && (err.status === 503 || err.code === "NETWORK_ERROR")) setHealth(null);
      }
    }
    finally { if (active.current && version === requestId.current) { locked.current = false; setPending(null); } }
  }
  async function choose() {
    if (locked.current || !original || !selected || !session) return;
    const evidence = original.decision.evidence.find((item) => item.candidate.code === selected);
    if (!evidence) return;
    const version = ++requestId.current;
    locked.current = true; setPending("choice"); setError(null);
    try {
      const value = await api.klarifikasi(session, original.id_log, selected, original.decision.period_used, evidence);
      if (active.current && version === requestId.current) setResponse(value);
    } catch (err) {
      if (active.current && version === requestId.current) {
        setError(safeMessage(err));
        if (err instanceof ApiError && (err.status === 503 || err.code === "NETWORK_ERROR")) setHealth(null);
      }
    }
    finally { if (active.current && version === requestId.current) { locked.current = false; setPending(null); } }
  }
  // Move focus after an explicit request finishes only while focus is still on
  // its submitting control. Reading or typing elsewhere never loses focus.
  useEffect(() => {
    if (!pending && response && (document.activeElement?.getAttribute("data-submit") === "true")) resultHeading.current?.focus();
  }, [pending, response]);
  async function copyResult() {
    if (!response) return;
    const decision = response.decision;
    const items = decision.answer ? [decision.answer] : decision.evidence;
    const plain = [submitted, decision.decision, decision.period_used ?? "", decision.reason_code ?? "", decision.suggestion ?? "",
      ...items.map((item) => [item.candidate.canonical_name, "Satuan: " + item.candidate.unit, item.result.columns.join("\t"), ...item.result.rows.map((row) => row.map(formatCell).join("\t"))].join("\n"))].filter(Boolean).join("\n");
    try { await navigator.clipboard.writeText(plain); setCopyStatus("Hasil disalin."); } catch { setCopyStatus("Hasil belum dapat disalin. Pilih teks hasil secara manual."); }
  }
  const decision = response?.decision;
  const statusText = (status: string | undefined) => status === "AVAILABLE" ? "Tersedia" : status === "UNAVAILABLE" ? "Tidak tersedia" : "Belum diketahui";
  const announcement = pending === "question" ? "Pertanyaan sedang diproses." : pending === "choice" ? "Pilihan sedang diproses." : error ? "Permintaan belum dapat diselesaikan." : decision ? "Hasil: " + decision.decision : "";

  return <>
    <Aurora />
    {stage === "loading" && <Startup status={checking ? "Memeriksa model dan data lokal…" : "Menyiapkan PRISMA…"} onContinue={() => setStage("masuk")} />}
    {stage === "masuk" && <Masuk awal={profile} onMasuk={(value) => { setProfile(value); setStage("app"); }} />}
    {stage === "app" && <>
      <Navbar halaman={page} onPindah={setPage} profil={profile} onUbahProfil={() => setStage("masuk")} />
      <main className="gutter py-6">
        <div hidden={page !== "tanya"} className="mx-auto max-w-4xl space-y-8">
          <section className="flex items-end justify-between gap-4 pt-4 sm:pt-6">
            <div className="min-w-0 space-y-3">
              <span className="kaca inline-flex items-center gap-2 rounded-full px-3.5 py-1.5 text-[13px] font-semibold text-ink-2">
                <span className="pil-titik bg-jawab" style={{ "--c": "var(--jawab)" } as CSSProperties} />Data BPS · 3 domain · tingkat provinsi
              </span>
              <h1 aria-label={"Halo" + (profile?.nama ? ", " + profile.nama : "") + "!"} className="font-display text-[44px] font-bold leading-[1.02] tracking-[-0.03em] text-ink sm:text-[64px]">
                Halo{profile?.nama ? <>, <span className="teks-aksen">{profile.nama}</span></> : ""}!
              </h1>
              <p className="text-[18px] text-ink-2">Mau cari tahu data apa hari ini?</p>
            </div>
            <Maskot ekspresi="menyapa" ukuran={112} className="hidden sm:block" />
          </section>
          <div>
            <form onSubmit={(event) => { event.preventDefault(); void submit(); }} className="cincin-fokus">
              <div className="kaca-tebal flex items-end gap-3 rounded-[30px] p-3 pl-5">
                <label htmlFor="pertanyaan" className="sr-only">Pertanyaan</label>
                <textarea id="pertanyaan" ref={input} rows={2} value={draft}
                  onChange={(event) => { setDraft(event.target.value); setValidation(null); }} aria-invalid={Boolean(validation)} aria-describedby="question-help question-error"
                  onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); void submit(); } }}
                  placeholder="Tanyakan data kemiskinan, ketenagakerjaan, atau pendidikan…"
                  className="prisma-question min-h-[60px] min-w-0 flex-1 resize-none bg-transparent py-3 text-[18px] leading-snug text-ink placeholder:text-ink-3 focus:outline-none" />
                <button type="submit" data-submit="true" disabled={!canSubmit} aria-label="Kirim pertanyaan" className="tombol tombol-utama !h-12 !w-12 !p-0">
                  <I n="kirim" className="h-5 w-5" />
                </button>
              </div>
            </form>
            <p id="question-error" className="text-[14px] font-semibold text-ink" role={validation ? "alert" : undefined}>{validation}</p>
            <p id="question-help" className="px-1 pt-2 text-[12px] text-ink-3">Enter untuk mengirim, Shift+Enter untuk baris baru. Pertanyaan dan keputusan masuk log lokal; hindari data pribadi.</p>
          </div>
          <Examples profile={profile} compact={Boolean(submitted)} disabled={!canSubmit} onChoose={(question) => void submit(question)} />
          <section className="kaca rounded-[24px] p-4 text-[13px] text-ink-2" aria-label="Status layanan" aria-busy={checking}>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div><p>Model: {statusText(health?.model.status)} · Basis data: {statusText(health?.database.status)}</p>
                {checking ? <p role="status">Memeriksa layanan.</p> : !isReady && <p>{health?.model.status === "UNKNOWN" || health?.database.status === "UNKNOWN" || !health ? "Status layanan belum dapat dipastikan." : "Layanan belum tersedia. Periksa kembali status layanan."}</p>}
              </div><Tombol disabled={checking} onClick={() => void checkHealth()}>Periksa lagi</Tombol>
            </div>
            {health && <details className="pt-2"><summary>Waktu pemeriksaan</summary><p>Model: {health.model.checked_at ?? "Belum tercatat"}</p><p>Basis data: {health.database.checked_at ?? "Belum tercatat"}</p></details>}
            {healthError && <p role="alert">{healthError}</p>}{sessionError && <p role="alert">{sessionError}</p>}
          </section>
          <div className="flex flex-wrap gap-2">
            <Tombol onClick={startNew}>Pertanyaan baru</Tombol>
            <Tombol varian="hantu" onClick={() => setPage("katalog")}>Lihat indikator tersedia</Tombol>
          </div>
          <p className="sr-only" role="status" aria-live="polite" aria-atomic="true">{"Status: " + announcement}</p>
          {(submitted || error || decision) && <section className="space-y-3 pb-20" aria-label="Utas tanya jawab">
            {submitted && <div className="flex justify-end"><p className="gelembung max-w-[85%] px-4 py-2.5 text-[15px] font-medium">{submitted}</p></div>}
            {pending && <div className="kaca-tebal muncul flex items-start gap-3 rounded-[28px] p-5" aria-busy="true">
              <Maskot ekspresi="berpikir" ukuran={60} /><div className="min-w-0 space-y-2.5 pt-1">
                <p className="font-display text-[16px] font-semibold text-ink">{pending === "question" ? "Pertanyaan sedang diproses." : "Pilihan sedang diproses."}</p>
                <p className="text-[13px] text-ink-2">Menunggu hasil dari layanan lokal.</p>
              </div>
            </div>}
            {error && <div className="kaca-tebal rounded-[28px] p-5 text-[15px] text-ink" role="alert"><strong>Permintaan belum dapat diselesaikan.</strong><p>{error}</p></div>}
            {decision && <article className={"kaca-tebal muncul rounded-[28px] p-5 sm:p-7 space-y-4 halo-" + decision.decision.toLowerCase()}>
          <div className="flex items-center gap-3"><Maskot ekspresi={decision.decision === "TANYA" ? "bingung" : decision.decision === "TAHAN" ? "menyesal" : "menyapa"} ukuran={64} />
            <h2 ref={resultHeading} tabIndex={-1} className={"pil pil-" + decision.decision.toLowerCase()}>{decision.decision}</h2></div>
          {decision.decision === "JAWAB" && decision.answer && <>
            <p>Hasil interpretasi: {decision.answer.candidate.canonical_name}</p><EvidenceCard evidence={decision.answer} period={decision.period_used} />
          </>}
          {decision.decision === "TANYA" && <>
            <p className="lead">Pilihan indikator menghasilkan jawaban berbeda. Pilih indikator yang Anda maksud.</p>
            <fieldset disabled={pending === "choice"}><legend className="sr-only">Pilihan indikator</legend>
              <div className={"mt-5 grid gap-3 sm:grid-cols-2 " + (decision.evidence.length === 3 ? "lg:grid-cols-3" : "")}>{decision.evidence.map((item) => <div className={"candidate " + (selected === item.candidate.code ? "candidate-selected" : "")} key={item.candidate.code}>
                <label className="candidate-label"><input type="radio" name="indikator" value={item.candidate.code} checked={selected === item.candidate.code}
                  onChange={() => setSelected(item.candidate.code)} />{item.candidate.canonical_name}</label>
                <EvidenceCard evidence={item} period={decision.period_used} />
              </div>)}</div>
              <div className="question-actions"><button className="tombol tombol-utama" data-submit="true" onClick={() => void choose()} disabled={!selected || pending !== null}>Gunakan pilihan</button>
                <button className="tombol tombol-kaca" onClick={() => setSelected(null)} disabled={!selected}>Batalkan pilihan</button></div>
            </fieldset>
          </>}
          {decision.decision === "TAHAN" && decision.reason_code && <>
            <span className="meta code">{decision.reason_code}</span><p className="lead">{reasonMessages[decision.reason_code]}</p><p>{decision.suggestion}</p>
            {decision.period_used && <p>Periode: {decision.period_used}</p>}
            <div className="question-actions"><button className="tombol tombol-kaca" onClick={() => input.current?.focus()}>Ubah pertanyaan</button><button className="tombol tombol-kaca" onClick={() => setPage("katalog")}>Buka katalog</button></div>
          </>}
          {original && decision.decision === "JAWAB" && <details className="original-evidence"><summary>Lihat bukti klarifikasi asal</summary>
            <div aria-label="Bukti klarifikasi asal">{original.decision.evidence.map((item) => <EvidenceCard key={item.candidate.code} evidence={item} period={original.decision.period_used} />)}</div></details>}
          <AksiKartu onLangkah={() => setLogOpen(true)} onSalin={() => void copyResult()} />
          {copyStatus && <p role="status">{copyStatus}</p>}
        </article>}
          </section>}
        </div>
        {page === "katalog" && <Catalog onUse={(item) => { startNew(); setDraft(item.nama_kanonik); }} />}
        {page === "tentang" && <Tentang />}
      </main>
      {logOpen && response && session && <LogDialog idLog={response.id_log} session={session} onClose={() => setLogOpen(false)} />}
    </>}
  </>;
}
