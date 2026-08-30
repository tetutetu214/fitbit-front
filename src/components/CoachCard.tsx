import { useCallback, useEffect, useState } from 'react';
import { Card } from './ui/Card';

interface CoachSection {
  title: string;
  body: string;
}

type CoachResponse =
  | {
      status: 'ready';
      date: string;
      generatedAt: string;
      modelId: string;
      days: number;
      sections: CoachSection[];
      reportPath: string;
    }
  | { status: 'running'; startedAt: string }
  | { status: 'auth_required'; message: string }
  | {
      status: 'error';
      message: string;
      retryAfter: number;
      logTail: string[];
    };

type CoachState = { status: 'loading' } | CoachResponse;
type BodyBlock =
  | { kind: 'paragraph'; text: string }
  | { kind: 'list'; items: string[] };

const CONNECTION_ERROR: CoachResponse = {
  status: 'error',
  message: 'dev サーバに接続できません',
  retryAfter: 60,
  logTail: [],
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function isSection(value: unknown): value is CoachSection {
  return (
    isRecord(value)
    && typeof value.title === 'string'
    && typeof value.body === 'string'
  );
}

function isCoachResponse(value: unknown): value is CoachResponse {
  if (!isRecord(value) || typeof value.status !== 'string') return false;
  if (value.status === 'ready') {
    return (
      typeof value.date === 'string'
      && /^\d{4}-\d{2}-\d{2}$/.test(value.date)
      && typeof value.generatedAt === 'string'
      && !Number.isNaN(Date.parse(value.generatedAt))
      && typeof value.modelId === 'string'
      && Number.isInteger(value.days)
      && Array.isArray(value.sections)
      && value.sections.every(isSection)
      && typeof value.reportPath === 'string'
    );
  }
  if (value.status === 'running') {
    return (
      typeof value.startedAt === 'string'
      && !Number.isNaN(Date.parse(value.startedAt))
    );
  }
  if (value.status === 'auth_required') {
    return typeof value.message === 'string';
  }
  if (value.status === 'error') {
    return (
      typeof value.message === 'string'
      && Number.isInteger(value.retryAfter)
      && Array.isArray(value.logTail)
      && value.logTail.every(line => typeof line === 'string')
    );
  }
  return false;
}

function bodyBlocks(body: string): BodyBlock[] {
  const blocks: BodyBlock[] = [];
  let paragraph: string[] = [];
  let items: string[] = [];
  const flushParagraph = () => {
    if (paragraph.length > 0) {
      blocks.push({ kind: 'paragraph', text: paragraph.join('\n') });
      paragraph = [];
    }
  };
  const flushList = () => {
    if (items.length > 0) {
      blocks.push({ kind: 'list', items });
      items = [];
    }
  };

  for (const line of body.split('\n')) {
    if (line.startsWith('- ')) {
      flushParagraph();
      items.push(line.slice(2));
    } else if (!line.trim()) {
      flushParagraph();
      flushList();
    } else {
      flushList();
      paragraph.push(line);
    }
  }
  flushParagraph();
  flushList();
  return blocks;
}

function SectionBody({ body }: { body: string }) {
  return bodyBlocks(body).map((block, index) => {
    if (block.kind === 'list') {
      return (
        <ul key={index} className="list-disc space-y-1 pl-5 text-sm leading-6 text-text">
          {block.items.map(item => <li key={item}>{item}</li>)}
        </ul>
      );
    }
    return (
      <p key={index} className="whitespace-pre-line text-sm leading-6 text-text">
        {block.text}
      </p>
    );
  });
}

export function CoachCard() {
  const [state, setState] = useState<CoachState>({ status: 'loading' });
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [retrySeconds, setRetrySeconds] = useState(0);

  const fetchCoach = useCallback(async () => {
    try {
      const response = await fetch('/api/coach');
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const value: unknown = await response.json();
      if (!isCoachResponse(value)) throw new Error('invalid response');
      setState(value);
    } catch {
      setState(CONNECTION_ERROR);
    }
  }, []);

  useEffect(() => {
    void fetchCoach();
  }, [fetchCoach]);

  useEffect(() => {
    if (state.status !== 'running') return;
    const updateElapsed = () => {
      setElapsedSeconds(
        Math.max(0, Math.floor((Date.now() - Date.parse(state.startedAt)) / 1_000)),
      );
    };
    updateElapsed();
    const elapsedTimer = window.setInterval(updateElapsed, 1_000);
    const pollingTimer = window.setInterval(() => void fetchCoach(), 3_000);
    return () => {
      window.clearInterval(elapsedTimer);
      window.clearInterval(pollingTimer);
    };
  }, [fetchCoach, state]);

  useEffect(() => {
    if (state.status !== 'error') return;
    const deadline = Date.now() + state.retryAfter * 1_000;
    const updateRetry = () => {
      setRetrySeconds(Math.max(0, Math.ceil((deadline - Date.now()) / 1_000)));
    };
    updateRetry();
    const timer = window.setInterval(updateRetry, 1_000);
    return () => window.clearInterval(timer);
  }, [state]);

  const reload = () => {
    setState({ status: 'loading' });
    void fetchCoach();
  };

  return (
    <div className="bg-bg px-8 pt-5 max-md:px-4">
      <Card className="border-accent/30 p-5">
        <div className="mb-4 flex items-center justify-between gap-3">
          <h2 className="text-[15px] font-semibold tracking-wide text-text">
            今日のコーチカード
          </h2>
          <span className="text-[11px] uppercase tracking-wider text-accent">
            Daily coach
          </span>
        </div>

        {state.status === 'loading' && (
          <p className="text-sm text-text2">読み込み中...</p>
        )}

        {state.status === 'running' && (
          <p className="text-sm text-text2">解析中… {elapsedSeconds} 秒</p>
        )}

        {state.status === 'ready' && (
          <div className="space-y-5">
            <div className="flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-text3">
              <span>{state.date}</span>
              <span>{state.days} 日分</span>
              <span>{new Date(state.generatedAt).toLocaleString('ja-JP')}</span>
              <span className="break-all">{state.modelId}</span>
            </div>
            {state.sections.map(section => (
              <section key={section.title} className="space-y-2">
                <h3 className="border-l-[3px] border-accent pl-2.5 text-sm text-text2">
                  {section.title}
                </h3>
                <SectionBody body={section.body} />
              </section>
            ))}
          </div>
        )}

        {state.status === 'auth_required' && (
          <div className="flex flex-wrap items-center gap-3">
            <p className="text-sm text-warning">{state.message}</p>
            <button
              type="button"
              onClick={reload}
              className="rounded-lg border border-accent px-3 py-1.5 text-xs text-accent transition-colors hover:bg-accent/10"
            >
              再読み込み
            </button>
          </div>
        )}

        {state.status === 'error' && (
          <div className="space-y-3">
            <p className="text-sm text-danger">{state.message}</p>
            <p className="text-xs text-text2">再試行まで {retrySeconds} 秒</p>
            <details className="text-xs text-text2">
              <summary className="cursor-pointer">ログ末尾</summary>
              <pre className="mt-2 overflow-x-auto whitespace-pre-wrap rounded-lg bg-bg p-3 text-text3">
                {state.logTail.length > 0 ? state.logTail.join('\n') : 'ログはありません'}
              </pre>
            </details>
          </div>
        )}
      </Card>
    </div>
  );
}
