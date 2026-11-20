"use client";
import { useState } from "react";
import { Bookmark } from "lucide-react";
import { useRouter } from "next/navigation";
import { request } from "@/lib/client";
import { Job } from "@/lib/types";
export function Progress({ job }: { job: Job }) {
  const router = useRouter(),
    [busy, setBusy] = useState(false),
    [err, setErr] = useState("");
  async function change(body: object) {
    setBusy(true);
    setErr("");
    try {
      await request("/jobs/" + job.id, "PATCH", body);
      router.refresh();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="progress-controls">
      <button
        className={"button " + (job.saved ? "soft" : "")}
        disabled={busy}
        onClick={() => change({ saved: !job.saved })}
      >
        <Bookmark size={15} fill={job.saved ? "currentColor" : "none"} />
        {job.saved ? "已收藏" : "收藏岗位"}
      </button>
      <label>
        申请进度
        <select
          disabled={busy}
          value={job.flag}
          onChange={(e) => change({ flag: e.target.value })}
        >
          {["未标记", "准备申请", "已申请", "面试中", "已结束", "忽略"].map(
            (x) => (
              <option key={x}>{x}</option>
            ),
          )}
        </select>
      </label>
      {err && (
        <span role="alert" className="error">
          {err}
        </span>
      )}
    </div>
  );
}
