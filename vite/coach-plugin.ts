import { spawn as nodeSpawn, type ChildProcess } from 'node:child_process';
import { existsSync as nodeExistsSync } from 'node:fs';
import { readFile as nodeReadFile } from 'node:fs/promises';
import path from 'node:path';
import type { Plugin } from 'vite';

const HEADINGS = ['## 今日の一手', '## 昨日の答え合わせ', '## 根拠データ', '## 注意'];
const FAILURE_CACHE_MS = 60_000;
const LOCK_RETRY_MS = 10_000;
const TIMEOUT_MS = 600_000;
const KILL_GRACE_MS = 5_000;
const MAX_LOG_BYTES = 2_048;
const INVALID = Symbol('invalid');

export interface CoachSection { title: string; body: string }
export type CoachResponse =
  | { status: 'ready'; date: string; generatedAt: string; modelId: string; days: number; sections: CoachSection[]; reportPath: string }
  | { status: 'running'; date: string; startedAt: string }
  | { status: 'auth_required'; message: string }
  | { status: 'error'; message: string; retryAfter: number; logTail: string[] };

interface Dependencies {
  cwd: string;
  now: () => Date;
  fileExists: (filename: string) => boolean;
  readFile: (filename: string, encoding: BufferEncoding) => Promise<string>;
  spawn: (command: string, args: string[], options: { stdio: ['ignore', 'pipe', 'pipe']; detached: true }) => ChildProcess;
  killGroup: (pid: number, signal: NodeJS.Signals) => void;
  modelId: () => string | undefined;
}

interface Failure { date: string; at: number; message: string; logTail: string[] }
interface Notice { date: string; startedAt: string }
interface LockNotice extends Notice { at: number }
interface Job extends Notice {
  child: ChildProcess | null;
  stderr: Buffer;
  settled: boolean;
  timedOut: boolean;
  timeout?: NodeJS.Timeout;
  killTimer?: NodeJS.Timeout;
}

const defaults: Dependencies = {
  cwd: process.cwd(),
  now: () => new Date(),
  fileExists: nodeExistsSync,
  readFile: nodeReadFile,
  spawn: (command, args, options) => nodeSpawn(command, args, options),
  killGroup: (pid, signal) => process.kill(-pid, signal),
  modelId: () => process.env.COACH_MODEL_ID,
};

function targetDate(now: Date): string {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: 'Asia/Tokyo', year: 'numeric', month: '2-digit', day: '2-digit',
  }).formatToParts(now);
  const value = (type: Intl.DateTimeFormatPartTypes) => parts.find(part => part.type === type)?.value ?? '';
  return `${value('year')}-${value('month')}-${value('day')}`;
}

function yamlScalar(raw: string): unknown | typeof INVALID {
  const value = raw.trim();
  if (!value) return INVALID;
  if (value.startsWith('"')) {
    try { const parsed: unknown = JSON.parse(value); return typeof parsed === 'string' ? parsed : INVALID; }
    catch { return INVALID; }
  }
  if (value.startsWith("'")) return value.length > 1 && value.endsWith("'") ? value.slice(1, -1).replaceAll("''", "'") : INVALID;
  if (/^-?(?:0|[1-9]\d*)$/.test(value)) return Number(value);
  if (/^-?(?:0|[1-9]\d*)\.\d+(?:[eE][+-]?\d+)?$/.test(value)) return Number(value);
  if (/^(?:null|Null|NULL|~)$/.test(value)) return null;
  if (/^(?:true|True|TRUE)$/.test(value)) return true;
  if (/^(?:false|False|FALSE)$/.test(value)) return false;
  return '[{&*!|>@`'.includes(value[0])
    || value.endsWith('"')
    || value.endsWith("'")
    ? INVALID
    : value;
}

function parseReport(content: string): { generatedAt: string; modelId: string; days: number; sections: CoachSection[] } | null {
  // Python側と同じくLFだけで分割し、frontmatterのキーと値はtrim後に比較する。
  const lines = content.split('\n');
  if (lines[0] !== '---') return null;
  const boundary = lines.indexOf('---', 1);
  if (boundary < 0) return null;
  const metadata = new Map<string, unknown>();
  for (const line of lines.slice(1, boundary)) {
    if (!line.trim() || line.trimStart().startsWith('#')) continue;
    const separator = line.indexOf(':');
    const key = separator >= 0 ? line.slice(0, separator).trim() : '';
    if (!/^[A-Za-z_][A-Za-z0-9_-]*$/.test(key) || metadata.has(key)) return null;
    const value = yamlScalar(line.slice(separator + 1).trim());
    if (value === INVALID) return null;
    metadata.set(key, value);
  }
  const body = lines.slice(boundary + 1).join('\n').trim();
  if ([...body].length > 2_400) return null;
  const bodyLines = body.split('\n');
  const headings = bodyLines.filter(line => line.startsWith('## '));
  if (headings.length !== HEADINGS.length || headings.some((heading, index) => heading !== HEADINGS[index])) return null;
  const sections = HEADINGS.map((heading, index) => {
    const start = bodyLines.indexOf(heading) + 1;
    const end = index + 1 < HEADINGS.length ? bodyLines.indexOf(HEADINGS[index + 1]) : bodyLines.length;
    return { title: heading.slice(3), body: bodyLines.slice(start, end).join('\n').trim() };
  });
  const modelId = metadata.get('model_id');
  const generatedAt = metadata.get('generated_at');
  const days = metadata.get('days');
  const zonedIso = typeof generatedAt === 'string' && /T.*(?:Z|[+-]\d{2}:\d{2})$/.test(generatedAt) && !Number.isNaN(Date.parse(generatedAt));
  if (typeof modelId !== 'string' || !modelId || !zonedIso || !Number.isInteger(days) || (days as number) < 1 || sections.some(section => !section.body)) return null;
  return { modelId, generatedAt: generatedAt as string, days: days as number, sections };
}

function stderrTail(buffer: Buffer): string[] {
  const text = buffer.subarray(Math.max(0, buffer.length - MAX_LOG_BYTES)).toString('utf8').replace(/^\uFFFD+/, '');
  let lines = text.split(/\r?\n/);
  if (lines.at(-1) === '') lines.pop();
  lines = lines.slice(-20);
  while (Buffer.byteLength(lines.join('\n')) > MAX_LOG_BYTES && lines.length > 1) lines.shift();
  while (lines.length === 1 && Buffer.byteLength(lines[0]) > MAX_LOG_BYTES) lines[0] = [...lines[0]].slice(1).join('');
  return lines;
}

export function createCoachApiService(overrides: Partial<Dependencies> = {}) {
  const dependencies = { ...defaults, ...overrides };
  const reportDirectory = path.join(dependencies.cwd, 'data', 'reports', 'coach');
  let inflight: Job | null = null;
  let failure: Failure | null = null;
  let authNotice: Notice | null = null;
  let lockNotice: LockNotice | null = null;

  const reportFile = (date: string) => path.join(reportDirectory, `${date}_coach.md`);
  const reportPath = (date: string) => path.relative(dependencies.cwd, reportFile(date)).split(path.sep).join('/');
  const errorResponse = (item: Failure, now: number): CoachResponse => ({
    status: 'error', message: item.message,
    retryAfter: Math.max(0, Math.ceil((FAILURE_CACHE_MS - (now - item.at)) / 1_000)),
    logTail: item.logTail,
  });
  const runningResponse = (notice: Notice): CoachResponse => ({
    status: 'running', date: notice.date, startedAt: notice.startedAt,
  });
  const signal = (job: Job, name: NodeJS.Signals) => {
    if (job.child?.pid === undefined) return;
    try { dependencies.killGroup(job.child.pid, name); }
    catch (error) { if ((error as NodeJS.ErrnoException).code !== 'ESRCH') throw error; }
  };

  const load = async (date: string): Promise<{ kind: 'missing' | 'invalid' } | { kind: 'ready'; response: CoachResponse }> => {
    let content: string;
    try { content = await dependencies.readFile(reportFile(date), 'utf-8'); }
    catch (error) {
      if ((error as NodeJS.ErrnoException).code === 'ENOENT') return { kind: 'missing' };
      return { kind: 'invalid' };
    }
    const parsed = parseReport(content);
    if (!parsed) return { kind: 'invalid' };
    return { kind: 'ready', response: { status: 'ready', date, ...parsed, reportPath: reportPath(date) } };
  };

  const finish = async (job: Job, code: number | null, processSignal: NodeJS.Signals | null, spawnError?: Error) => {
    if (job.settled) return;
    job.settled = true;
    if (job.timeout) clearTimeout(job.timeout);
    if (job.killTimer) clearTimeout(job.killTimer);
    const tail = stderrTail(job.stderr);
    if (job.timedOut) failure = { date: job.date, at: dependencies.now().getTime(), message: 'timed_out', logTail: tail };
    else if (spawnError) failure = { date: job.date, at: dependencies.now().getTime(), message: `spawn_failed: ${spawnError.message}`, logTail: tail };
    else if (code === 3) authNotice = job;
    else if (code === 4) lockNotice = {
      date: job.date,
      startedAt: job.startedAt,
      at: dependencies.now().getTime(),
    };
    else if (code === 0) {
      // 完成判定には現在日ではなく、spawn時に固定した対象日を使う。
      const result = await load(job.date);
      if (result.kind !== 'ready') failure = { date: job.date, at: dependencies.now().getTime(), message: result.kind === 'missing' ? 'report_missing' : 'report_invalid', logTail: tail };
    } else failure = { date: job.date, at: dependencies.now().getTime(), message: processSignal ? `terminated_by_signal: ${processSignal}` : `process_failed: ${code ?? 'unknown'}`, logTail: tail };
    if (inflight === job) inflight = null;
  };

  const stop = (job: Job, timedOut: boolean) => {
    if (job.settled || job.killTimer) return;
    job.timedOut = timedOut;
    signal(job, 'SIGTERM');
    job.killTimer = setTimeout(() => {
      signal(job, 'SIGKILL');
      void finish(job, null, 'SIGKILL');
    }, KILL_GRACE_MS);
  };

  const start = (date: string, modelId: string): CoachResponse => {
    const startedAt = dependencies.now().toISOString();
    const job: Job = { date, startedAt, child: null, stderr: Buffer.alloc(0), settled: false, timedOut: false };
    inflight = job;
    try {
      const venvPython = path.join(dependencies.cwd, '.venv', 'bin', 'python');
      const pythonBin = dependencies.fileExists(venvPython) ? venvPython : 'python3';
      job.child = dependencies.spawn(pythonBin, ['scripts/coach_daily.py', '--date', date, '--model-id', modelId], { stdio: ['ignore', 'pipe', 'pipe'], detached: true });
    } catch (error) {
      void finish(job, null, null, error as Error);
      return errorResponse({ date, at: dependencies.now().getTime(), message: `spawn_failed: ${(error as Error).message}`, logTail: [] }, dependencies.now().getTime());
    }
    job.child.stdout?.on('data', () => undefined);
    job.child.stderr?.on('data', (chunk: unknown) => {
      const bytes = Buffer.isBuffer(chunk) ? chunk : Buffer.from(String(chunk));
      job.stderr = Buffer.concat([job.stderr, bytes]).subarray(-MAX_LOG_BYTES * 2);
    });
    job.child.once('error', error => { void finish(job, null, null, error); });
    job.child.once('close', (code, processSignal) => { void finish(job, code, processSignal); });
    job.timeout = setTimeout(() => stop(job, true), TIMEOUT_MS);
    return runningResponse(job);
  };

  const get = async (): Promise<CoachResponse> => {
    const now = dependencies.now();
    const date = targetDate(now);
    const report = await load(date);
    if (report.kind === 'ready') return report.response;
    if (report.kind === 'invalid') return { status: 'error', message: 'report_invalid', retryAfter: 60, logTail: [] };
    if (inflight) return runningResponse(inflight);
    if (authNotice?.date === date) { authNotice = null; return { status: 'auth_required', message: '`aws login` を実行してからリロード' }; }
    if (lockNotice?.date === date) {
      if (now.getTime() - lockNotice.at < LOCK_RETRY_MS) return runningResponse(lockNotice);
      lockNotice = null;
    }
    if (failure?.date === date && now.getTime() - failure.at < FAILURE_CACHE_MS) return errorResponse(failure, now.getTime());
    const modelId = dependencies.modelId()?.trim();
    if (!modelId) {
      failure = { date, at: now.getTime(), message: 'COACH_MODEL_ID が未設定', logTail: [] };
      return errorResponse(failure, now.getTime());
    }
    return start(date, modelId);
  };

  return { get, close: () => { if (inflight) stop(inflight, false); } };
}

export function coachApiPlugin(modelId?: string): Plugin {
  const service = createCoachApiService({
    modelId: () => modelId ?? process.env.COACH_MODEL_ID,
  });
  return {
    name: 'coach-api',
    configureServer(server) {
      server.middlewares.use((request, response, next) => {
        if (request.method !== 'GET' || request.url?.split('?')[0] !== '/api/coach') return next();
        void service.get().then(body => {
          response.statusCode = body.status === 'running' ? 202 : 200;
          response.setHeader('Content-Type', 'application/json; charset=utf-8');
          response.end(JSON.stringify(body));
        }).catch(() => {
          response.statusCode = 200;
          response.setHeader('Content-Type', 'application/json; charset=utf-8');
          response.end(JSON.stringify({ status: 'error', message: 'internal_error', retryAfter: 60, logTail: [] }));
        });
      });
      server.httpServer?.on('close', service.close);
    },
  };
}
