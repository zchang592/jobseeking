import Link from "next/link";
import {
  ArrowRight,
  Building2,
  ChevronRight,
  Inbox,
  MapPin,
} from "lucide-react";
import { Job } from "@/lib/types";
export function Title({
  title,
  note,
  children,
}: {
  title: string;
  note?: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="page-title">
      <div>
        <h1>{title}</h1>
        {note && <p>{note}</p>}
      </div>
      {children}
    </div>
  );
}
export function Status({ value }: { value: string }) {
  return (
    <span
      className={
        "pill " +
        ({ 招聘中: "green", 已截止: "gray", 未开始: "blue", 待核实: "amber" }[
          value
        ] || "gray")
      }
    >
      <i />
      {value}
    </span>
  );
}
export function Empty({
  text = "暂无符合条件的岗位",
  href,
  label,
}: {
  text?: string;
  href?: string;
  label?: string;
}) {
  return (
    <div className="empty">
      <Inbox size={28} strokeWidth={1.4} />
      <p>{text}</p>
      {href && (
        <Link className="text-link" href={href}>
          {label || "查看全部职位"}
          <ArrowRight size={14} />
        </Link>
      )}
    </div>
  );
}
export function JobRow({ j }: { j: Job }) {
  return (
    <Link className="job-row" href={"/jobs/" + j.id}>
      <span className="school-icon">
        <Building2 size={21} strokeWidth={1.5} />
      </span>
      <div className="job-copy">
        <strong>{j.title}</strong>
        <div className="job-meta">
          <span>{j.school}</span>
          <span>
            <MapPin size={12} />
            {j.city || "地区待核"}
          </span>
        </div>
      </div>
      <div className="job-states">
        <Status value={j.status} />
        <small>{j.eligibility}</small>
      </div>
      <div className="score">
        <b>{j.score}</b>
        <small>专业匹配</small>
      </div>
      <ChevronRight size={15} className="row-arrow" />
    </Link>
  );
}
export function SectionTitle({
  name,
  href,
  label,
}: {
  name: string;
  href?: string;
  label?: string;
}) {
  return (
    <div className="section-title">
      <h2>{name}</h2>
      {href && (
        <Link className="text-link" href={href}>
          {label || "查看全部"}
          <ArrowRight size={14} />
        </Link>
      )}
    </div>
  );
}
