import { useEffect, useRef, useState } from 'react';

interface BottomSheetProps {
  title: React.ReactNode;
  onClose: () => void;
  children: React.ReactNode;
  /** シート高さのスナップポイント（dvh%）。[プレビュー, フル] */
  snapPoints?: [number, number];
  /** 初期表示をフルにする場合 1 を指定 */
  initialSnap?: 0 | 1;
}

const DRAG_THRESHOLD = 70;

/**
 * 依存ライブラリなしのボトムシート。
 * ハンドルをドラッグしてプレビュー(40%)⇔フル(85%)を切替、
 * プレビューからさらに下スワイプ・背景タップ・✕・Escで閉じる。
 */
export function BottomSheet({
  title,
  onClose,
  children,
  snapPoints = [40, 85],
  initialSnap = 0,
}: BottomSheetProps) {
  const [snapIdx, setSnapIdx] = useState<0 | 1>(initialSnap);
  const [dragY, setDragY] = useState(0);
  const [dragging, setDragging] = useState(false);
  const dragStart = useRef<number | null>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  const onPointerDown = (e: React.PointerEvent) => {
    dragStart.current = e.clientY;
    setDragging(true);
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
  };
  const onPointerMove = (e: React.PointerEvent) => {
    if (dragStart.current === null) return;
    setDragY(e.clientY - dragStart.current);
  };
  const onPointerUp = () => {
    if (dragStart.current === null) return;
    const dy = dragY;
    dragStart.current = null;
    setDragging(false);
    setDragY(0);
    if (dy > DRAG_THRESHOLD) {
      if (snapIdx === 1) setSnapIdx(0);
      else onClose();
    } else if (dy < -DRAG_THRESHOLD && snapIdx === 0) {
      setSnapIdx(1);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/60"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
    >
      <div
        className="flex w-full max-w-lg flex-col rounded-t-2xl border border-b-0 border-border bg-card"
        style={{
          height: `${snapPoints[snapIdx]}dvh`,
          transform: dragY > 0 ? `translateY(${dragY}px)` : undefined,
          transition: dragging ? 'none' : 'height 0.25s ease, transform 0.2s ease',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div
          className="shrink-0 cursor-grab touch-none px-5 pt-2 active:cursor-grabbing"
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onPointerCancel={onPointerUp}
        >
          <div className="mx-auto h-1 w-10 rounded-full bg-border" />
          <div className="flex items-center justify-between py-3">
            <h3 className="text-base font-semibold text-text">{title}</h3>
            <div className="flex items-center gap-3">
              <button
                onClick={() => setSnapIdx(snapIdx === 0 ? 1 : 0)}
                className="text-xs text-text2 hover:text-text"
                aria-label={snapIdx === 0 ? '拡大' : '縮小'}
              >
                {snapIdx === 0 ? '⌃ 拡大' : '⌄ 縮小'}
              </button>
              <button onClick={onClose} className="text-text2 hover:text-text" aria-label="閉じる">
                ✕
              </button>
            </div>
          </div>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto px-5 pb-6">{children}</div>
      </div>
    </div>
  );
}
