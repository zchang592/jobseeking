"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, Eye, EyeOff, LockKeyhole, LogOut } from "lucide-react";
import { request } from "@/lib/client";
export function Login() {
  const [show, setShow] = useState(false),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const router = useRouter();
  return (
    <form
      className="login-form"
      onSubmit={async (e) => {
        e.preventDefault();
        const value = new FormData(e.currentTarget).get("password");
        setBusy(true);
        setError("");
        try {
          await request("/session", "POST", { password: value });
          router.replace("/");
          router.refresh();
        } catch (err) {
          setError((err as Error).message);
          setBusy(false);
        }
      }}
    >
      <label htmlFor="password">工作台密码</label>
      <div className="password">
        <LockKeyhole size={17} />
        <input
          id="password"
          type={show ? "text" : "password"}
          name="password"
          autoComplete="current-password"
          required
          autoFocus
        />
        <button
          type="button"
          className="plain"
          onClick={() => setShow(!show)}
          aria-label={show ? "隐藏密码" : "显示密码"}
        >
          {show ? <EyeOff size={16} /> : <Eye size={16} />}
        </button>
      </div>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      <button className="button primary wide" disabled={busy}>
        {busy ? "登录中…" : "进入工作台"}
        <ArrowRight size={16} />
      </button>
    </form>
  );
}
export function Logout() {
  const router = useRouter();
  return (
    <button
      className="icon"
      title="退出登录"
      aria-label="退出登录"
      onClick={async () => {
        await request("/session", "DELETE");
        router.replace("/login");
        router.refresh();
      }}
    >
      <LogOut size={16} />
    </button>
  );
}
