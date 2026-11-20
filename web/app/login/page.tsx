import { Brand } from "@/components/Brand";
import { Login } from "@/components/Session";
import { LockKeyhole } from "lucide-react";
export default function Page() {
  return (
    <main className="login-page">
      <div className="login-art">
        <Brand />
        <div className="login-title">
          <span className="eyebrow light">FACULTY INTELLIGENCE</span>
          <h1>音乐教职雷达</h1>
          <p>全国音乐教育招聘情报工作台</p>
        </div>
        <div className="cover-art" />
      </div>
      <section className="login-panel">
        <div className="intro-icon">
          <LockKeyhole size={22} />
        </div>
        <h2>登录个人工作台</h2>
        <p className="muted">登录后查看岗位匹配与申请进度。</p>
        <Login />
      </section>
    </main>
  );
}
