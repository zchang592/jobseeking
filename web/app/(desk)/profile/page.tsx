import { GraduationCap, ShieldCheck } from "lucide-react";
import { read } from "@/lib/server";
import { SectionTitle, Title } from "@/components/Common";
export default async function Page() {
  const p = await read<{
    highest_degree: string;
    studying: string;
    education: string[];
    skills: string[];
    teaching: string[];
    practice: string[];
    certificates: string[];
    language?: string;
  }>("/profile");
  return (
    <>
      <Title title="求职画像" note="用于专业匹配与资格判断的个人资料" />
      <div className="profile-grid">
        <section className="panel">
          <SectionTitle name="学历与学位" />
          <div className="inset">
            <GraduationCap size={28} />
            <div className="degrees">
              <div>
                <small>最高已获学位</small>
                <strong>{p.highest_degree}</strong>
              </div>
              <div>
                <small>当前就读</small>
                <strong>{p.studying}</strong>
              </div>
            </div>
            {p.education.map((e) => (
              <p key={e}>{e}</p>
            ))}
          </div>
        </section>
        <section className="panel">
          <SectionTitle name="教学与实践" />
          <div className="inset">
            {p.language && <p>{p.language}</p>}
            {[...p.teaching, ...p.practice].map((e) => (
              <p key={e}>{e}</p>
            ))}
          </div>
        </section>
        <section className="panel">
          <SectionTitle name="专业方向" />
          <div className="tags inset">
            {p.skills.map((e) => (
              <span className="tag" key={e}>
                {e}
              </span>
            ))}
          </div>
        </section>
        <section className="panel">
          <SectionTitle name="教师资格与证书" />
          <div className="inset">
            <ShieldCheck size={22} />
            <p>
              {p.certificates.join("、") ||
                "尚未提供证书，相关岗位将提示核实。"}
            </p>
          </div>
        </section>
      </div>
    </>
  );
}
