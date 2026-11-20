import { read } from "@/lib/server";
import { Activity, Source, shortTime } from "@/lib/types";
import { Refresh } from "@/components/Refresh";
import { SectionTitle, Title } from "@/components/Common";
import { SourceManager } from "@/components/SourceManager";
export default async function Page() {
  const [src, act] = await Promise.all([
    read<Source[]>("/sources"),
    read<Activity>("/activity"),
  ]);
  return (
    <>
      <Title title="监控来源" note="管理招聘栏目，查看采集记录与待核实公告">
        <Refresh initial={act.latest} />
      </Title>
      <SourceManager items={src} />
      <section className="panel log-panel">
        <SectionTitle name="最近采集日志" />
        {act.logs.length ? (
          <ul className="logs">
            {act.logs.map((l, i) => (
              <li key={i}>
                <time>{shortTime(l.at)}</time>
                <span>{l.message}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="inset muted">当前数据库还没有任务日志。</p>
        )}
      </section>
    </>
  );
}
