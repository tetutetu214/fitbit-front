import { useState } from 'react';
import type { HealthData } from '../types/health';
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from './ui/Card';
import { TRAINER_API_URL, buildTrainerSummary, fetchTrainerAdvice } from '../lib/trainer';

interface TrainerPanelProps {
  data: HealthData;
  index: number;
}

type PanelState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'done'; advice: string }
  | { status: 'error'; message: string };

const IDLE: PanelState = { status: 'idle' };

/**
 * AIトレーナーパネル。
 * その日のヘルスサマリーを Amazon Bedrock (Nova 2) に送り、
 * 状態の解説とアドバイスを表示する。
 */
export function TrainerPanel({ data, index }: TrainerPanelProps) {
  // 日付ごとに状態を保持する。取得済みの解説(done)はそのままキャッシュとして働き、
  // 同じ日を再表示したときに再リクエストしない。
  const [stateByDate, setStateByDate] = useState<Record<string, PanelState>>({});
  const date = index >= 0 && index < data.dates.length ? data.dates[index] : null;
  const state: PanelState = (date && stateByDate[date]) || IDLE;

  if (!TRAINER_API_URL) return null;

  const summary = date ? buildTrainerSummary(data, index) : null;

  const ask = async () => {
    if (!date || !summary || state.status === 'loading') return;
    const update = (s: PanelState) => setStateByDate((prev) => ({ ...prev, [date]: s }));
    update({ status: 'loading' });
    try {
      const advice = await fetchTrainerAdvice(summary);
      update({ status: 'done', advice });
    } catch (err) {
      update({
        status: 'error',
        message: err instanceof Error ? err.message : '解説の取得に失敗しました',
      });
    }
  };

  return (
    <div className="px-8 pt-3.5 max-md:px-4">
      <Card>
        <CardHeader className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <span aria-hidden>💪</span>
            AIトレーナー
          </CardTitle>
          <span className="rounded-full bg-accent/10 px-2 py-0.5 text-[10px] tracking-wide text-accent">
            Amazon Nova 2
          </span>
        </CardHeader>
        <CardContent>
          {!summary && (
            <p className="py-2 text-sm text-text2">この日のデータがないため、解説できません。</p>
          )}

          {summary && state.status === 'idle' && (
            <div className="flex flex-col items-start gap-2 py-1">
              <p className="text-sm text-text2">
                睡眠・心拍・HRV・活動量のデータから、この日の状態をトレーナーが解説します。
              </p>
              <button
                type="button"
                onClick={ask}
                className="rounded-md border border-accent/50 bg-accent/10 px-4 py-2 text-sm font-semibold text-accent transition-colors hover:bg-accent/20"
              >
                この日の状態を解説してもらう
              </button>
            </div>
          )}

          {state.status === 'loading' && (
            <p className="animate-pulse py-3 text-sm text-text2">
              トレーナーがデータを読み込んでいます…
            </p>
          )}

          {state.status === 'done' && (
            <p className="whitespace-pre-line py-1 text-sm leading-relaxed text-text">
              {state.advice}
            </p>
          )}

          {state.status === 'error' && (
            <div className="flex flex-col items-start gap-2 py-1">
              <p className="text-sm text-danger">{state.message}</p>
              <button
                type="button"
                onClick={ask}
                className="rounded-md border border-border px-3 py-1.5 text-xs text-text2 transition-colors hover:border-accent hover:text-accent"
              >
                再試行
              </button>
            </div>
          )}
        </CardContent>
        {state.status === 'done' && (
          <CardFooter>※AIによる解説であり、医学的な診断ではありません</CardFooter>
        )}
      </Card>
    </div>
  );
}
