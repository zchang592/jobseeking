import Link from "next/link";
import { notFound } from "next/navigation";
import {
  ArrowLeft,
  CheckCircle2,
  ExternalLink,
  FileText,
  Info,
  MapPin,
  Paperclip,
} from "lucide-react";
import { read } from "@/lib/server";
import { Job, shortDate, shortTime } from "@/lib/types";
import { Status, SectionTitle } from "@/components/Common";
import { Progress } from "@/components/Progress";
export default async function Page({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  if (!/^\d+$/.test(id)) notFound();
  const j = await read<Job>("/jobs/" + id);
  const basics = [
    ["学校类型", j.school_type],
    ["教育学段", j.stage],
    ["学院 / 部门", j.department],
    ["招聘人数", j.count],
    ["岗位代码", j.code],
    ["聘用类型", j.employment],
    ["工作性质", j.workload],
    ["薪资待遇", j.pay],
  ];
  const reqs = [
    ["学历学位", j.degree],
    ["专业方向", j.major],
    ["教师资格", j.certificate],
    ["职称要求", j.rank],
    ["职责", j.duties],
    ["其他条件", j.other],
    ["公告通用资格", j.general],
  ];
  return (
    <>
      <Link href="/jobs" className="back">
        <ArrowLeft size={15} /> 招聘职位
      </Link>
      <div className="detail-title">
        <Status value={j.status} />
        <h1>{j.title}</h1>
        <p>
          {j.school}
          <span>
            <MapPin size={15} />
            {j.province} · {j.city}
          </span>
        </p>
      </div>
      <div className="detail-grid">
        <div className="vertical">
          <section className="panel">
            <SectionTitle name="岗位信息" />
            <dl className="field-grid">
              {basics.map(([k, v]) => (
                <div key={k}>
                  <dt>{k}</dt>
                  <dd>{v || "未公布 / 未提取"}</dd>
                </div>
              ))}
            </dl>
          </section>
          <section className="panel">
            <SectionTitle name="报考条件" />
            <dl className="long-fields">
              {reqs.map(([k, v]) => (
                <div key={k}>
                  <dt>{k}</dt>
                  <dd>{v || "请核对原公告"}</dd>
                </div>
              ))}
            </dl>
          </section>
          <section className="panel">
            <SectionTitle name="来源证据" />
            {j.evidence?.map((e) => (
              <div className="proof" key={e.url}>
                <span className="source-tag">
                  {e.kind === "学校官网"
                    ? "官方来源 · 学校官网"
                    : e.kind + " · 待核实"}
                </span>
                {!e.current && <span className="pill amber">旧版记录</span>}
                <a
                  href={e.url}
                  target="_blank"
                  rel="noreferrer"
                  className="proof-title"
                >
                  {e.title}
                  <ExternalLink size={15} />
                </a>
                <small>
                  {e.source} · 核验 {shortTime(e.checked)}
                </small>
                {e.excerpt && (
                  <blockquote>
                    {e.excerpt}
                    <cite>
                      {e.file_name || "公告正文"} · {e.location}
                    </cite>
                  </blockquote>
                )}
                {e.detail_url && (
                  <a
                    className="attachment"
                    href={e.detail_url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    学校岗位详情 <ExternalLink size={14} />
                  </a>
                )}
                {e.attachments.map((a) => (
                  <a
                    key={a.url}
                    className="attachment"
                    href={a.url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    <Paperclip size={14} />
                    {a.name}
                    {a.error ? " · 待核实" : ""}
                  </a>
                ))}
                {e.issue && (
                  <div className="warning">待人工核实 · {e.issue}</div>
                )}
              </div>
            ))}
          </section>
        </div>
        <aside className="vertical">
          <section className="panel">
            <SectionTitle name="岗位匹配分析" />
            <div className="match-box">
              <div className="match-head">
                <div>
                  <strong>{j.score}</strong>
                  <small>/ 100</small>
                </div>
                <span>专业匹配分</span>
              </div>
              <div className="meter">
                <i style={{ width: j.score + "%" }} />
              </div>
              <div className="verdict">
                <small>报考资格</small>
                <b>{j.eligibility}</b>
              </div>
              {j.reasons.map((r) => (
                <p key={r}>
                  <CheckCircle2 size={15} />
                  {r}
                </p>
              ))}
              {j.checks.map((r) => (
                <p className="caution" key={r}>
                  <Info size={15} />
                  {r}
                </p>
              ))}
              <small className="muted">
                依据当前求职画像与可核验的岗位条件进行规则匹配
              </small>
            </div>
          </section>
          <section className="panel">
            <SectionTitle name="报名与跟进" />
            <div className="inset">
              <dl className="timeline">
                <div>
                  <dt>公告发布</dt>
                  <dd>{shortDate(j.published)}</dd>
                </div>
                <div>
                  <dt>报名开始</dt>
                  <dd>{j.starts?.replace("T", " ") || "未明确"}</dd>
                </div>
                <div>
                  <dt>报名截止</dt>
                  <dd>{j.deadline?.replace("T", " ") || "截止时间未知"}</dd>
                </div>
              </dl>
              {j.apply_url && (
                <a
                  className="button primary wide"
                  href={j.apply_url}
                  target="_blank"
                  rel="noreferrer"
                >
                  官方报名入口
                  <ExternalLink size={14} />
                </a>
              )}
              <Progress job={j} />
            </div>
          </section>
        </aside>
      </div>
    </>
  );
}
