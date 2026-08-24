// 実 Bedrock は課金と待ち時間を伴うため、spawn・時計・ファイルシステムをモックする。

import type { ChildProcess } from 'node:child_process';
import { EventEmitter } from 'node:events';
import { PassThrough } from 'node:stream';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { createCoachApiService, type CoachResponse } from './coach-plugin';

const PROJECT_ROOT = '/project';
const REPORT_PATH = `${PROJECT_ROOT}/data/reports/coach/2026-08-24_coach.md`;
const VENV_PYTHON = `${PROJECT_ROOT}/.venv/bin/python`;

function validReport(generatedAt = '2026-08-24T06:00:00+09:00'): string {
  return `---
model_id: "us.test-model"
generated_at: "${generatedAt}"
end: "2026-08-23"
days: 7
prompt: "prompts/coach_daily.md"
---

## 今日の一手
23時30分に就寝する。

## 昨日の答え合わせ
睡眠時間で確認した。

## 根拠データ
- 2026-08-23: 睡眠 360 分

## 注意
個人差がある。
`;
}

function parityReport(caseName: string): string {
  if (caseName === 'normal') return validReport();
  if (caseName === 'u2028_heading_separator') {
    return validReport().replace('## 今日の一手\n', '## 今日の一手\u2028');
  }
  if (caseName === 'leading_whitespace_key') {
    return validReport().replace('model_id:', '  model_id :');
  }
  if (caseName === 'colon_in_plain_value') {
    return validReport().replace('prompt: "prompts/coach_daily.md"', 'prompt: prompts/coach:daily.md');
  }
  if (caseName === 'japanese_plain_value') {
    return validReport().replace('---\n\n##', 'memo: 日本語の値\n---\n\n##');
  }
  if (caseName === 'crlf') return validReport().replaceAll('\n', '\r\n');
  if (caseName === 'duplicate_trimmed_key') {
    return validReport().replace('model_id: "us.test-model"', 'model_id: "us.test-model"\n model_id : "other"');
  }
  if (caseName === 'blank_trimmed_value') {
    return validReport().replace('prompt: "prompts/coach_daily.md"', 'prompt:   ');
  }
  if (caseName === 'surrounding_value_whitespace') {
    return validReport().replace('days: 7', 'days:   7   ');
  }
  throw new Error(`未知のパリティケースです: ${caseName}`);
}

const REPORT_PARITY_CASES = [
  { caseName: 'normal', isValid: true },
  { caseName: 'u2028_heading_separator', isValid: false },
  { caseName: 'leading_whitespace_key', isValid: true },
  { caseName: 'colon_in_plain_value', isValid: true },
  { caseName: 'japanese_plain_value', isValid: true },
  { caseName: 'crlf', isValid: false },
  { caseName: 'duplicate_trimmed_key', isValid: false },
  { caseName: 'blank_trimmed_value', isValid: false },
  { caseName: 'surrounding_value_whitespace', isValid: true },
] as const;

class FakeChild extends EventEmitter {
  pid = 4_321;
  stdout = new PassThrough();
  stderr = new PassThrough();

  close(code: number | null, signal: NodeJS.Signals | null = null): void {
    this.emit('close', code, signal);
  }

  fail(error: Error): void {
    this.emit('error', error);
  }
}

function createHarness(options: { modelId?: string; venvPython?: boolean } = {}) {
  const files = new Map<string, string>();
  const children: FakeChild[] = [];
  const readFile = vi.fn(async (filename: string) => {
    const content = files.get(filename);
    if (content === undefined) {
      throw Object.assign(new Error('not found'), { code: 'ENOENT' });
    }
    return content;
  });
  const spawn = vi.fn(() => {
    const child = new FakeChild();
    children.push(child);
    return child as unknown as ChildProcess;
  });
  const fileExists = vi.fn((filename: string) => (
    options.venvPython === true && filename === VENV_PYTHON
  ));
  const killGroup = vi.fn();
  const modelId = Object.hasOwn(options, 'modelId')
    ? options.modelId
    : 'us.test-model';
  const service = createCoachApiService({
    cwd: PROJECT_ROOT,
    now: () => new Date(),
    fileExists,
    readFile,
    spawn,
    killGroup,
    modelId: () => modelId,
  });
  return { children, fileExists, files, killGroup, readFile, service, spawn };
}

async function flushAsyncWork(): Promise<void> {
  await Promise.resolve();
  await Promise.resolve();
}

function expectResponseContract(response: CoachResponse): void {
  if (response.status === 'ready') {
    expect(response.date).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(response.generatedAt).toMatch(/(?:Z|[+-]\d{2}:\d{2})$/);
    expect(Number.isInteger(response.days)).toBe(true);
    expect(Array.isArray(response.sections)).toBe(true);
    return;
  }
  if (response.status === 'running') {
    expect(response.date).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(response.startedAt).toMatch(/Z$/);
    return;
  }
  if (response.status === 'error') {
    expect(Number.isInteger(response.retryAfter)).toBe(true);
    expect(Array.isArray(response.logTail)).toBe(true);
    return;
  }
  expect(typeof response.message).toBe('string');
}

describe('coach API service', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-08-24T06:00:00.000Z'));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('対象日のレポートが有効なときは Python を起動せず ready を返す', async () => {
    const harness = createHarness();
    harness.files.set(REPORT_PATH, validReport());

    const response = await harness.service.get();

    expect(response).toMatchObject({
      status: 'ready',
      date: '2026-08-24',
      generatedAt: '2026-08-24T06:00:00+09:00',
      modelId: 'us.test-model',
      days: 7,
      reportPath: 'data/reports/coach/2026-08-24_coach.md',
    });
    expect(harness.spawn).not.toHaveBeenCalled();
  });

  it('対象日のレポートに4見出しが無いときは起動せず error を返す', async () => {
    const harness = createHarness();
    harness.files.set(REPORT_PATH, validReport().replace('## 注意', '## 補足'));

    const response = await harness.service.get();

    expect(response).toMatchObject({ status: 'error', message: 'report_invalid' });
    expect(harness.spawn).not.toHaveBeenCalled();
  });

  it.each(REPORT_PARITY_CASES)(
    'レポート解析のLF・trim共通規則に従う: $caseName',
    async ({ caseName, isValid }) => {
      const harness = createHarness();
      harness.files.set(REPORT_PATH, parityReport(caseName));

      const response = await harness.service.get();

      expect(response.status).toBe(isValid ? 'ready' : 'error');
      expect(harness.spawn).not.toHaveBeenCalled();
    },
  );

  it('frontmatter の生成日時にタイムゾーンが無いときは error を返す', async () => {
    const harness = createHarness();
    harness.files.set(REPORT_PATH, validReport('2026-08-24T06:00:00'));

    const response = await harness.service.get();

    expect(response).toMatchObject({ status: 'error', message: 'report_invalid' });
    expect(harness.spawn).not.toHaveBeenCalled();
  });

  it('同時の冷起動リクエストでは spawn を1回だけ実行する', async () => {
    const harness = createHarness();

    const responses = await Promise.all([
      harness.service.get(),
      harness.service.get(),
    ]);

    expect(responses.map(response => response.status)).toEqual(['running', 'running']);
    expect(harness.spawn).toHaveBeenCalledTimes(1);
  });

  it('.venv の Python があるときはその実行体を使う', async () => {
    const harness = createHarness({ venvPython: true });

    await harness.service.get();

    expect(harness.spawn.mock.calls[0][0]).toBe(VENV_PYTHON);
  });

  it('.venv の Python が無いときは python3 を使う', async () => {
    const harness = createHarness();

    await harness.service.get();

    expect(harness.spawn.mock.calls[0][0]).toBe('python3');
  });

  it('実行中の再リクエストでは spawn を増やさず running を返す', async () => {
    const harness = createHarness();
    const first = await harness.service.get();

    const second = await harness.service.get();

    expect(first.status).toBe('running');
    expect(second).toEqual(first);
    expect(harness.spawn).toHaveBeenCalledTimes(1);
  });

  it('子が exit 3 のとき auth_required を返し次のリクエストで再起動する', async () => {
    const harness = createHarness();
    await harness.service.get();
    harness.children[0].close(3);
    await flushAsyncWork();

    const authResponse = await harness.service.get();
    const retryResponse = await harness.service.get();

    expect(authResponse).toEqual({
      status: 'auth_required',
      message: '`aws login` を実行してからリロード',
    });
    expect(retryResponse.status).toBe('running');
    expect(harness.spawn).toHaveBeenCalledTimes(2);
  });

  it('子が exit 1 のとき stderr 末尾を60秒間キャッシュする', async () => {
    const harness = createHarness();
    await harness.service.get();
    const stderr = Array.from({ length: 25 }, (_, index) => `line-${index + 1}`).join('\n');
    harness.children[0].stderr.write(`${stderr}\n`);
    harness.children[0].close(1);
    await flushAsyncWork();

    const firstError = await harness.service.get();
    vi.advanceTimersByTime(10_000);
    const cachedError = await harness.service.get();

    expect(firstError).toMatchObject({ status: 'error', retryAfter: 60 });
    expect(firstError.status === 'error' ? firstError.logTail : []).toHaveLength(20);
    expect(firstError.status === 'error' ? firstError.logTail.at(-1) : '').toBe('line-25');
    expect(cachedError).toMatchObject({ status: 'error', retryAfter: 50 });
    expect(harness.spawn).toHaveBeenCalledTimes(1);
  });

  it('子が exit 4 のとき10秒間は再 spawn せず running を返す', async () => {
    const harness = createHarness();
    await harness.service.get();
    harness.children[0].close(4);
    await flushAsyncWork();

    const immediate = await harness.service.get();
    for (let poll = 0; poll < 3; poll += 1) {
      vi.advanceTimersByTime(3_000);
      const response = await harness.service.get();
      expect(response).toMatchObject({ status: 'running', date: '2026-08-24' });
    }

    expect(immediate).toMatchObject({ status: 'running', date: '2026-08-24' });
    expect(harness.spawn).toHaveBeenCalledTimes(1);

    vi.advanceTimersByTime(1_000);
    const retried = await harness.service.get();

    expect(retried).toMatchObject({ status: 'running', date: '2026-08-24' });
    expect(harness.spawn).toHaveBeenCalledTimes(2);
  });

  it('600秒を超えるとプロセスグループを止めて inflight を解放する', async () => {
    const harness = createHarness();
    await harness.service.get();

    vi.advanceTimersByTime(600_000);
    expect(harness.killGroup).toHaveBeenCalledWith(4_321, 'SIGTERM');
    vi.advanceTimersByTime(5_000);
    await flushAsyncWork();
    const errorResponse = await harness.service.get();
    vi.advanceTimersByTime(60_000);
    const retriedResponse = await harness.service.get();

    expect(harness.killGroup).toHaveBeenCalledWith(4_321, 'SIGKILL');
    expect(errorResponse).toMatchObject({ status: 'error', message: 'timed_out' });
    expect(retriedResponse.status).toBe('running');
    expect(harness.spawn).toHaveBeenCalledTimes(2);
  });

  it('子が exit 0 でも対象日のファイルが無いときは error を返す', async () => {
    const harness = createHarness();
    await harness.service.get();
    harness.children[0].close(0);
    await flushAsyncWork();

    const response = await harness.service.get();

    expect(response).toMatchObject({ status: 'error', message: 'report_missing' });
  });

  it('23時59分の処理は日付が変わっても起動時の対象日で完成判定する', async () => {
    vi.setSystemTime(new Date('2026-08-24T14:59:00.000Z'));
    const harness = createHarness();
    const started = await harness.service.get();
    harness.files.set(REPORT_PATH, validReport());
    vi.setSystemTime(new Date('2026-08-24T15:01:00.000Z'));
    harness.children[0].close(0);
    await flushAsyncWork();

    const completionReads = harness.readFile.mock.calls
      .map(call => call[0])
      .filter(filename => filename === REPORT_PATH);
    const nextResponse = await harness.service.get();

    expect(started).toMatchObject({ status: 'running', date: '2026-08-24' });
    expect(completionReads).toHaveLength(2);
    expect(nextResponse).toMatchObject({ status: 'running', date: '2026-08-25' });
    expect(harness.spawn.mock.calls[1][1]).toContain('2026-08-25');
  });

  it('COACH_MODEL_ID が未設定のときは spawn せず error を返す', async () => {
    const harness = createHarness({ modelId: undefined });

    const response = await harness.service.get();

    expect(response).toMatchObject({
      status: 'error',
      message: 'COACH_MODEL_ID が未設定',
    });
    expect(harness.spawn).not.toHaveBeenCalled();
  });

  it('全レスポンスが日付・ISO時刻・配列の型契約を満たす', async () => {
    const readyHarness = createHarness();
    readyHarness.files.set(REPORT_PATH, validReport());
    const ready = await readyHarness.service.get();
    const running = await createHarness().service.get();
    const error = await createHarness({ modelId: undefined }).service.get();

    for (const response of [ready, running, error]) {
      expectResponseContract(response);
    }
  });

  it('spawn が同期的に失敗したときは inflight を残さず error を返す', async () => {
    const harness = createHarness();
    harness.spawn.mockImplementationOnce(() => {
      throw new Error('spawn unavailable');
    });

    const response = await harness.service.get();

    expect(response).toMatchObject({ status: 'error', message: 'spawn_failed: spawn unavailable' });
    expect(harness.spawn).toHaveBeenCalledTimes(1);
  });

  it('日付が変わると前日の失敗キャッシュを当日に持ち越さない', async () => {
    vi.setSystemTime(new Date('2026-08-24T14:59:00.000Z'));
    const harness = createHarness();
    await harness.service.get();
    harness.children[0].close(1);
    await flushAsyncWork();
    vi.setSystemTime(new Date('2026-08-24T15:01:00.000Z'));

    const response = await harness.service.get();

    expect(response.status).toBe('running');
    expect(harness.spawn).toHaveBeenCalledTimes(2);
  });

  it('日本語を含む stderr は20行かつ2048バイト以内に切り詰める', async () => {
    const harness = createHarness();
    await harness.service.get();
    harness.children[0].stderr.write(`${'あ'.repeat(1_000)}\n${'い'.repeat(1_000)}\n`);
    harness.children[0].close(1);
    await flushAsyncWork();

    const response = await harness.service.get();
    const logTail = response.status === 'error' ? response.logTail : [];

    expect(logTail.length).toBeLessThanOrEqual(20);
    expect(Buffer.byteLength(logTail.join('\n'))).toBeLessThanOrEqual(2_048);
  });

  it('dev サーバ終了時は残っている子プロセスを停止する', async () => {
    const harness = createHarness();
    await harness.service.get();

    harness.service.close();
    vi.advanceTimersByTime(5_000);
    await flushAsyncWork();

    expect(harness.killGroup.mock.calls).toEqual([
      [4_321, 'SIGTERM'],
      [4_321, 'SIGKILL'],
    ]);
  });
});
