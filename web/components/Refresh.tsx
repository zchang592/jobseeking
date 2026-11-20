"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { RefreshCw } from "lucide-react";
import { request } from "@/lib/client";
import { Activity, Task } from "@/lib/types";
export function Refresh({ initial }: { initial?: Task | null }) {
  const router = useRouter(),
    [task, setTask] = useState(initial || null),
    [pending, setPending] = useState(false),
    [error, setError] = useState("");
  const busy = !!task && ["等待中", "采集中"].includes(task.state);
  useEffect(() => {
    if (!busy) return;
    const t = setInterval(async () => {
      try {
        const a = await request<Activity>("/activity");
        setTask(a.latest);
        if (a.latest && !["等待中", "采集中"].includes(a.latest.state))
          router.refresh();
      } catch (e) {
        setError((e as Error).message);
      }
    }, 4500);
    return () => clearInterval(t);
  }, [busy, router]);
  return (
    <div className="refresh-wrap">
      <button
        type="button"
        className="button"
        disabled={busy || pending}
        onClick={async () => {
          setPending(true);
          setError("");
          try {
            await request("/refresh", "POST");
            const a = await request<Activity>("/activity");
            setTask(a.latest);
            router.refresh();
          } catch (e) {
            setError((e as Error).message);
          } finally {
            setPending(false);
          }
        }}
      >
        <RefreshCw size={15} className={busy ? "spin" : ""} />
        {busy ? task?.state : pending ? "正在提交…" : "立即更新"}
      </button>
      {error && (
        <small role="alert" className="error">
          {error}
        </small>
      )}
    </div>
  );
}
