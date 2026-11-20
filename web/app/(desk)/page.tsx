import Link from "next/link";
import {
  Activity,
  ArrowRight,
  CalendarDays,
  Clock3,
  Crosshair,
  Database,
  FileSearch,
  Layers3,
  RadioTower,
  ScanLine,
  Timer,
} from "lucide-react";
import { read } from "@/lib/server";
import { Overview, shortTime } from "@/lib/types";
import { Empty, JobRow, SectionTitle, Title } from "@/components/Common";
import { Refresh } from "@/components/Refresh";
export default async function Home() {
  const d = await read<Overview>("/overview");
  const date = new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "long",
    day: "numeric",
    weekday: "long",
    timeZone: "Asia/Shanghai",
  }).format(new Date(d.date + "T12:00:00+08:00"));
  const cards = [
    {
      title: "今日新发现",
      n: d.new,
      icon: ScanLine,
      href: "/jobs?view=new",
      tone: "sage",
      unit: "个岗位",
    },
    {
      title: "正在招聘",
      n: d.open,
      icon: Layers3,
      href: "/jobs?status=招聘中",
      tone: "aqua",
      unit: "个岗位",
    },
    {
      title: "高匹配可申请",
      n: d.high,
      icon: Crosshair,
      href: "/jobs?view=recommended",
      tone: "violet",
      unit: "个岗位",
    },
    {
      title: "七天内截止",
      n: d.soon,
      icon: Timer,
      href: "/jobs?view=soon",
      tone: "sienna",
      unit: "个岗位",
    },
  ];
  return (
    <>
      <Title title="情报概览" note={date + " · 北京时间"}>
        <Refresh initial={d.last_run} />
      </Title>
      <section className="hero">
        <div className="cover-art" />
        <div className="hero-inner">
          <div className="hero-kicker">
            <span className="broadcast" />
            <span>监测工作台</span>
          </div>
          <h2>全国音乐教职监测</h2>
          <div className="hero-data">
            <span>
              <RadioTower size={15} />
              {d.enabled} 个启用来源
            </span>
            <i />
            <span>
              <Clock3 size={15} />
              每日 08:30 采集
            </span>
          </div>
        </div>
      </section>
      <div className="metric-grid">
        {cards.map((c) => (
          <Link href={c.href} key={c.title} className="metric">
            <div className="metric-label">
              <span className={"metric-icon " + c.tone}>
                <c.icon size={19} />
              </span>
              {c.title}
            </div>
            <div className="metric-number">
              {c.n}
              <small>{c.unit}</small>
            </div>
          </Link>
        ))}
      </div>
      <div className="desk-grid">
        <section className="panel main-panel">
          <SectionTitle name="岗位速览" href="/jobs" />
          <div className="subhead">
            <span className="active-tab">综合排序</span>
            <Link href="/jobs?sort=published">最近发布</Link>
            <Link href="/jobs?view=soon">即将截止</Link>
          </div>
          {d.top.length ? (
            d.top.map((j) => <JobRow key={j.id} j={j} />)
          ) : (
            <Empty
              text="首次采集完成后，已识别的岗位会显示在这里"
              href="/sources"
              label="查看监控来源"
            />
          )}
        </section>
        <aside className="right-stack">
          <section className="panel">
            <SectionTitle name="监测状态" href="/sources" label="来源" />
            <div className="monitor-lines">
              <div>
                <span>
                  <Database size={16} />
                  已收录岗位
                </span>
                <b>{d.total} 个</b>
              </div>
              <div>
                <span>
                  <FileSearch size={16} />
                  已核验来源
                </span>
                <b>{d.verified} 个</b>
              </div>
              <div>
                <span>
                  <Activity size={16} />
                  最近任务
                </span>
                <b>{d.last_run?.state || "尚无任务"}</b>
              </div>
              <div className="monitor-time">
                <span>最近成功核验</span>
                <strong>{shortTime(d.last_checked)}</strong>
              </div>
            </div>
          </section>
          <Link href="/brief" className="brief-card">
            <span className="brief-icon">
              <CalendarDays size={20} />
            </span>
            <div>
              <strong>每日招聘简报</strong>
              <small>新增岗位与截止提醒</small>
            </div>
            <ArrowRight size={16} />
          </Link>
        </aside>
      </div>
    </>
  );
}
