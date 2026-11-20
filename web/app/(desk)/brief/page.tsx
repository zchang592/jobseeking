import { CalendarDays, Mail } from "lucide-react";
import { read } from "@/lib/server";
import { Job } from "@/lib/types";
import { Empty, JobRow, SectionTitle, Title } from "@/components/Common";
export default async function Page() {
  const b = await read<{
    date: string;
    new: Job[];
    high: Job[];
    soon: Job[];
    email_configured: boolean;
    delivery?: string;
  }>("/brief");
  return (
    <>
      <Title title="每日招聘简报" note={b.date + " · 北京时间"} />
      <div className="brief-banner">
        <CalendarDays />
        <strong>今日招聘动态</strong>
        <span>
          <Mail size={15} />
          {b.delivery || (b.email_configured ? "邮件已配置" : "邮件尚未配置")}
        </span>
      </div>
      <div className="vertical">
        {(["high", "soon", "new"] as const).map((k, i) => (
          <section key={k} className="panel">
            <SectionTitle
              name={
                ["高匹配可申请", "七天内截止", "今日新发现"][i] +
                " · " +
                b[k].length
              }
              href={
                "/jobs?view=" +
                { high: "recommended", soon: "soon", new: "new" }[k]
              }
            />
            {b[k].length ? (
              b[k].slice(0, 10).map((j) => <JobRow key={j.id} j={j} />)
            ) : (
              <Empty text="本期暂无此类岗位" />
            )}
          </section>
        ))}
      </div>
    </>
  );
}
