"use client";
export default function ErrorPage({ reset }: { reset: () => void }) {
  return (
    <div className="panel inset">
      <h2>暂时无法读取工作台</h2>
      <p>请检查 API 与数据库的运行状态。</p>
      <button className="button" onClick={reset}>
        重新加载
      </button>
    </div>
  );
}
