interface HeaderProps {
  lastDate: string;
}

export function Header({ lastDate }: HeaderProps) {
  return (
    <div className="header">
      <h1>Fitbit ヘルスダッシュボード</h1>
      <div className="date">最終更新: {lastDate}</div>
    </div>
  );
}
