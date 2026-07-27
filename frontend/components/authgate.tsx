"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { isAuthed } from "@/lib/api";

/** Client-side route guard: anything except /login requires a token, or the
 *  user is bounced to /login. (The backend enforces auth for real; this is
 *  just so the UI doesn't render pages that will only 401.) */
export function AuthGate({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (pathname === "/login") { setReady(true); return; }
    if (!isAuthed()) { router.replace("/login"); return; }
    setReady(true);
  }, [pathname, router]);

  if (!ready) return null;
  return <>{children}</>;
}
