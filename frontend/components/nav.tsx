"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { isAuthed, logout } from "@/lib/api";

export function Nav() {
  const pathname = usePathname();
  const [authed, setAuthed] = useState(false);

  // Read localStorage only after mount to avoid a server/client mismatch.
  useEffect(() => { setAuthed(isAuthed()); }, [pathname]);

  return (
    <nav>
      <Link href="/">Intake</Link>
      <Link href="/history">Case history</Link>
      {authed && (
        <a href="#" onClick={(e) => { e.preventDefault(); logout(); }}>
          Sign out
        </a>
      )}
    </nav>
  );
}
