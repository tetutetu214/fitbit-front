import { useEffect, useState } from 'react';
import { Dashboard } from './components/Dashboard';
import type { HealthData } from './types/health';

function App() {
  const [data, setData] = useState<HealthData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch('/data/health.json')
      .then(res => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then(json => setData(json as HealthData))
      .catch(() => setError('データの読み込みに失敗しました。node scripts/generate_health_json.mjs を実行してください。'));
  }, []);

  if (error) {
    return (
      <div className="flex h-screen items-center justify-center bg-bg1 text-text2">
        <p>{error}</p>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="flex h-screen items-center justify-center bg-bg1 text-text2">
        <p>読み込み中...</p>
      </div>
    );
  }

  return <Dashboard data={data} />;
}

export default App;
