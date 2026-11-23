import Link from "next/link";
import { Search, SlidersHorizontal } from "lucide-react";
import { read } from "@/lib/server";
import { Results } from "@/lib/types";
import { Empty, JobRow, Title } from "./Common";
export type SearchParams = Record<string, string | string[] | undefined>;
export async function JobBrowser({
  params,
  saved = false,
}: {
  params: SearchParams;
  saved?: boolean;
}) {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(params))
    if (typeof v === "string" && v) p.set(k, v);
  if (saved) p.set("view", "saved");
  else if (!p.has("category")) p.set("category", "secondary");
  const d = await read<Results>("/jobs?" + p);
  const page = saved ? "/saved" : "/jobs";
  function link(k: string, v: string) {
    const next = new URLSearchParams(p);
    next.delete("page");
    if (v) next.set(k, v);
    else next.delete(k);
    return page + "?" + next;
  }
  const select = (key: string, label: string, choices: string[][]) => (
    <label key={key}>
      {label}
      <select name={key} defaultValue={p.get(key) || ""}>
        <option value="">全部</option>
        {choices.map(([v, l]) => (
          <option key={v} value={v}>
            {l}
          </option>
        ))}
      </select>
    </label>
  );
  const opts = (x: string[]) => x.map((v) => [v, v]);
  const sig = p.toString();
  return (
    <>
      <Title
        title={saved ? "收藏与申请" : "招聘职位"}
        note={
          saved
            ? "跟进已收藏的职位与个人申请进度"
            : "优先查看初中、高中和国际学校音乐教师岗位"
        }
      />
      {!saved && (
        <div className="tabs" aria-label="岗位类别">
          {[
            ["secondary", "中学与国际学校"],
            ["university", "高校与音乐学院"],
            ["primary", "小学与幼教"],
            ["other", "其他 / 学段待核实"],
            ["all", "全部"],
          ].map(([value, label]) => (
            <Link key={value} href={link("category", value)} className={p.get("category") === value ? "selected" : ""}>
              {label}
            </Link>
          ))}
        </div>
      )}
      {!saved && (
        <div className="tabs">
          {[
            ["", "全部职位"],
            ["recommended", "高匹配可申请"],
            ["new", "今日新发现"],
            ["soon", "即将截止"],
          ].map(([v, l]) => (
            <Link
              key={l}
              href={link("view", v)}
              className={(p.get("view") || "") === v ? "selected" : ""}
            >
              {l}
            </Link>
          ))}
        </div>
      )}
      <form key={sig} action={page} className="panel filters">
        <div className="search-line">
          <label className="search-box">
            <Search size={17} />
            <input
              name="q"
              aria-label="搜索岗位、学校或方向"
              placeholder="搜索岗位、学校或专业方向"
              defaultValue={p.get("q") || ""}
            />
          </label>
          <button className="button primary">应用筛选</button>
          <Link href={page} className="text-link">
            重置
          </Link>
        </div>
        {!saved && <input type="hidden" name="category" value={p.get("category") || "secondary"} />}
        {p.has("view") && (
          <input type="hidden" name="view" value={p.get("view")!} />
        )}
        <div className="filter-row">
          {select("city", "城市", opts(d.facets.city))}
          {select("stage", "教育学段", opts(d.facets.stage))}
          {select("direction", "专业方向", opts(d.facets.direction))}
          {select(
            "status",
            "招聘状态",
            opts(["招聘中", "未开始", "待核实", "已截止"]),
          )}
          {select("sort", "排序", [
            ["score", "专业匹配分"],
            ["published", "发布时间"],
            ["deadline", "截止日期"],
            ["first_seen", "发现时间"],
          ])}
        </div>
        <details
          className="more-filters"
          open={[
            "school",
            "min_score",
            "eligibility",
            "flag",
            "published_from",
            "published_to",
            "deadline_from",
            "deadline_to",
          ].some((k) => p.has(k))}
        >
          <summary>
            <SlidersHorizontal size={14} /> 更多筛选
          </summary>
          <div className="filter-row">
            {select("school", "学校", opts(d.facets.school))}
            {select(
              "min_score",
              "最低匹配",
              ["60", "75", "85", "90"].map((x) => [x, x + " 分"]),
            )}
            {select(
              "eligibility",
              "报考资格",
              opts([
                "基本符合",
                "可能符合，需要核实",
                "明确不符合",
                "信息不足",
              ]),
            )}
            {select(
              "flag",
              "申请进度",
              opts([
                "未标记",
                "准备申请",
                "已申请",
                "面试中",
                "已结束",
                "忽略",
              ]),
            )}
          </div>
          <div className="filter-row">
            {[
              ["published_from", "发布起日"],
              ["published_to", "发布止日"],
              ["deadline_from", "截止日期自"],
              ["deadline_to", "截止日期至"],
            ].map(([k, l]) => (
              <label key={k}>
                {l}
                <input type="date" name={k} defaultValue={p.get(k) || ""} />
              </label>
            ))}
          </div>
        </details>
      </form>
      <section className="panel">
        <div className="section-title">
          <h2>
            {saved ? "个人跟进" : "岗位列表"}
            <small className="count">{d.total}</small>
          </h2>
          <span className="muted small-text">
            第 {d.page} / {d.pages} 页
          </span>
        </div>
        {d.items.length ? (
          d.items.map((j) => <JobRow j={j} key={j.id} />)
        ) : (
          <Empty
            text={
              saved
                ? "还没有符合条件的收藏或申请记录"
                : "这个类别暂时没有符合条件的职位，可选择其他类别"
            }
            href="/jobs"
          />
        )}
        {d.pages > 1 && (
          <div className="pagination">
            {d.page > 1 && (
              <Link className="button" href={link("page", String(d.page - 1))}>
                上一页
              </Link>
            )}
            {d.page < d.pages && (
              <Link className="button" href={link("page", String(d.page + 1))}>
                下一页
              </Link>
            )}
          </div>
        )}
      </section>
    </>
  );
}
