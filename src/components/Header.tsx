interface HeaderProps {
  lastDate: string;
}

export function Header({ lastDate }: HeaderProps) {
  return (
    <div className="flex items-center justify-between border-b border-border px-8 py-5 max-md:px-4">
      <h1 className="text-[22px] font-bold text-accent">Fitbit ヘルスダッシュボード</h1>
      <div className="text-[13px] text-text2">最終更新: {lastDate}</div>
    </div>
  );
}
