import Link from "next/link";
export default function Missing() {
  return (
    <main className="content">
      <h1>未找到这条记录</h1>
      <Link className="text-link" href="/jobs">
        返回招聘职位
      </Link>
    </main>
  );
}
