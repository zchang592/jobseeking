"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  ChevronDown,
  ExternalLink,
  FileText,
  Pause,
  Play,
  Plus,
  RadioTower,
  Trash2,
  X,
} from "lucide-react";
import { request } from "@/lib/client";
import { Source, shortTime } from "@/lib/types";
type Notice = {
  id: number;
  url: string;
  title: string;
  checked: string;
  issue?: string;
  files: number;
};
export function SourceManager({ items }: { items: Source[] }) {
  const router = useRouter(),
    [adding, add] = useState(false),
    [filter, setFilter] = useState("全部"),
    [error, err] = useState(""),
    [saving, save] = useState(false);
  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    err("");
    save(true);
    try {
      await request(
        "/sources",
        "POST",
        Object.fromEntries(new FormData(e.currentTarget)),
      );
      add(false);
      router.refresh();
    } catch (ex) {
      err((ex as Error).message);
    } finally {
      save(false);
    }
  }
  const visible = items.filter(
    (s) =>
      filter === "全部" ||
      (filter === "已启用"
        ? s.enabled
        : filter === "待核实"
          ? !!s.issue || !s.succeeded
          : !s.enabled),
  );
  return (
    <>
      <div className="source-tools">
        <div className="tabs compact">
          {["全部", "已启用", "待核实", "已停用"].map((v) => (
            <button
              key={v}
              className={v === filter ? "selected" : ""}
              onClick={() => setFilter(v)}
            >
              {v}
            </button>
          ))}
        </div>
        <button
          className="button primary"
          onClick={() => {
            add(!adding);
            err("");
          }}
        >
          {adding ? <X size={15} /> : <Plus size={15} />}{" "}
          {adding ? "收起" : "添加来源"}
        </button>
      </div>
      {adding && (
        <form className="panel add-source" onSubmit={submit}>
          <h2>添加监控来源</h2>
          <div className="form-grid">
            <label>
              学校或来源名称
              <input name="name" required minLength={2} maxLength={80} />
            </label>
            <label>
              采集方式
              <select name="mode">
                <option value="index">监控招聘栏目</option>
                <option value="article">监控单篇公开公告</option>
              </select>
            </label>
            <label className="full">
              招聘栏目或公告网址
              <input name="url" type="url" placeholder="https://" required />
            </label>
            <label>
              学校官网
              <input name="homepage" type="url" placeholder="https://" />
            </label>
            <label>
              公众号名称
              <input name="wechat" />
            </label>
            <label>
              省份
              <input name="province" />
            </label>
            <label>
              城市
              <input name="city" />
            </label>
            <label>
              学校类型
              <input name="school_type" placeholder="例如：艺术职业学校" />
            </label>
            <label>
              教育学段
              <select name="stage">
                {[
                  "高等教育",
                  "高职",
                  "中职",
                  "高中",
                  "初中",
                  "小学",
                  "其他",
                ].map((x) => (
                  <option key={x}>{x}</option>
                ))}
              </select>
            </label>
          </div>
          {error && (
            <p className="error" role="alert">
              {error}
            </p>
          )}
          <button className="button primary" disabled={saving}>
            保存来源
          </button>
        </form>
      )}
      <div className="panel">
        <div className="section-title">
          <h2>
            来源目录<small className="count">{visible.length}</small>
          </h2>
        </div>
        {visible.map((s) => (
          <SourceRow s={s} key={s.id} />
        ))}
        {!visible.length && <p className="empty">暂无来源</p>}
      </div>
    </>
  );
}
function SourceRow({ s }: { s: Source }) {
  const router = useRouter(),
    [open, setOpen] = useState(false),
    [notes, setNotes] = useState<Notice[]>([]),
    [error, err] = useState(""),
    [busy, setBusy] = useState(false),
    [confirm, setConfirm] = useState(false);
  async function show() {
    setOpen(!open);
    if (!open)
      try {
        setNotes(await request<Notice[]>("/notices?source_id=" + s.id));
      } catch (e) {
        err((e as Error).message);
      }
  }
  async function change(method: string, body?: object) {
    setBusy(true);
    err("");
    try {
      await request("/sources/" + s.id, method, body);
      router.refresh();
    } catch (e) {
      err((e as Error).message);
    } finally {
      setBusy(false);
      setConfirm(false);
    }
  }
  return (
    <article className="source-row">
      <button onClick={show} className="source-main" aria-expanded={open}>
        <span className="school-icon">
          <RadioTower size={19} />
        </span>
        <span className="source-name">
          <strong>{s.name}</strong>
          <small>
            {new URL(s.url).hostname} · {s.city || "地区待核"}
          </small>
        </span>
        <span
          className={
            "pill " +
            (!s.enabled
              ? "gray"
              : s.issue
                ? "amber"
                : s.succeeded
                  ? "green"
                  : "blue")
          }
        >
          {!s.enabled
            ? "已停用"
            : s.issue
              ? "待核实"
              : s.succeeded
                ? "已核验"
                : "待采集"}
        </span>
        <ChevronDown size={15} />
      </button>
      {open && (
        <div className="source-info">
          <a
            href={s.url}
            target="_blank"
            rel="noreferrer"
            className="text-link"
          >
            打开监控栏目 <ExternalLink size={13} />
          </a>
          <p className="muted">
            最近尝试 {shortTime(s.attempted)}　·　最近成功{" "}
            {shortTime(s.succeeded)}
          </p>
          {s.issue && <div className="warning">{s.issue}</div>}
          {notes.length > 0 && (
            <div className="notice-list">
              {notes.slice(0, 10).map((n) => (
                <a key={n.id} href={n.url} target="_blank" rel="noreferrer">
                  <FileText size={14} />
                  <span>{n.title}</span>
                  <small>{n.issue ? "待核实" : n.files + " 个附件"}</small>
                </a>
              ))}
            </div>
          )}
          <div className="actions">
            <button
              className="button"
              disabled={busy}
              onClick={() => change("PATCH", { enabled: !s.enabled })}
            >
              {s.enabled ? <Pause size={14} /> : <Play size={14} />}{" "}
              {s.enabled ? "暂停监控" : "启用监控"}
            </button>
            <button
              className="button danger"
              disabled={busy}
              onClick={() => (confirm ? change("DELETE") : setConfirm(true))}
            >
              <Trash2 size={14} />
              {confirm ? "确认移除来源" : "移除"}
            </button>
            {confirm && (
              <button className="plain" onClick={() => setConfirm(false)}>
                取消
              </button>
            )}
          </div>
        </div>
      )}
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
    </article>
  );
}
