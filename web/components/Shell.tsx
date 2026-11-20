"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import {
  Activity,
  Bookmark,
  BriefcaseBusiness,
  ChevronRight,
  Clock3,
  FileText,
  LayoutDashboard,
  Menu,
  PanelLeft,
  RadioTower,
  UserRound,
  X,
} from "lucide-react";
import { Brand } from "./Brand";
import { Logout } from "./Session";
const nav = [
  { path: "/", name: "情报概览", icon: LayoutDashboard },
  { path: "/jobs", name: "招聘职位", icon: BriefcaseBusiness },
  { path: "/saved", name: "收藏与申请", icon: Bookmark },
  { path: "/sources", name: "监控来源", icon: RadioTower },
  { path: "/brief", name: "每日简报", icon: FileText },
  { path: "/profile", name: "求职画像", icon: UserRound },
];
export function Shell({ children }: { children: React.ReactNode }) {
  const path = usePathname(),
    [open, setOpen] = useState(false);
  const current =
    nav.find((n) =>
      n.path === "/" ? path === "/" : path.startsWith(n.path),
    ) || nav[0];
  return (
    <div className="app">
      {open && (
        <button
          className="scrim"
          aria-label="关闭导航"
          onClick={() => setOpen(false)}
        />
      )}
      <aside className={"sidebar" + (open ? " visible" : "")}>
        <div className="brand-line">
          <Link href="/" onClick={() => setOpen(false)}>
            <Brand />
          </Link>
          <button
            className="mobile icon"
            onClick={() => setOpen(false)}
            aria-label="关闭导航"
          >
            <X />
          </button>
        </div>
        <div className="nav-label">工作空间</div>
        <nav>
          {nav.slice(0, 3).map((n) => (
            <NavItem
              key={n.path}
              n={n}
              active={n === current}
              close={() => setOpen(false)}
            />
          ))}
        </nav>
        <div className="nav-label lower">监测与设置</div>
        <nav>
          {nav.slice(3).map((n) => (
            <NavItem
              key={n.path}
              n={n}
              active={n === current}
              close={() => setOpen(false)}
            />
          ))}
        </nav>
        <div className="side-bottom">
          <div className="schedule">
            <Clock3 size={17} />
            <div>
              <strong>每日自动采集</strong>
              <small>08:30 · 北京时间</small>
            </div>
          </div>
          <div className="userbar">
            <span className="avatar">
              <UserRound size={16} />
            </span>
            <span>个人工作台</span>
            <Logout />
          </div>
        </div>
      </aside>
      <div className="main-area">
        <header className="topbar">
          <div className="crumb">
            <button
              className="icon mobile"
              onClick={() => setOpen(true)}
              aria-label="打开导航"
            >
              <Menu />
            </button>
            <PanelLeft className="desktop-only" size={17} />
            <span>工作空间</span>
            <ChevronRight size={13} />
            <b>{current.name}</b>
          </div>
          <div className="private-label">
            <span className="tiny-dot" />
            个人空间
          </div>
        </header>
        <main className="content" key={current.path}>
          {children}
        </main>
      </div>
    </div>
  );
}
function NavItem({
  n,
  active,
  close,
}: {
  n: (typeof nav)[number];
  active: boolean;
  close: () => void;
}) {
  const Icon = n.icon;
  return (
    <Link
      href={n.path}
      className={"nav-item" + (active ? " active" : "")}
      onClick={close}
      aria-current={active ? "page" : undefined}
    >
      <Icon size={18} strokeWidth={1.8} />
      {n.name}
      {active && <span className="nav-mark" />}
    </Link>
  );
}
