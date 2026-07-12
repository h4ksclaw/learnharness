"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Bot, Settings, MessageSquare, BarChart3 } from "lucide-react";

const navItems = [
  { href: "/", label: "Agents", icon: Bot },
  { href: "/chat", label: "Chat", icon: MessageSquare },
  { href: "/mastery", label: "Knowledge", icon: BarChart3 },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex h-screen w-60 flex-col border-r border-white/[0.05] bg-[#0f1011]">
      <div className="flex h-14 items-center gap-2 px-4">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#10b981] text-sm font-bold text-black">
          LH
        </div>
        <span className="text-sm font-semibold text-[#f7f8f8]">
          LearnHarness
        </span>
      </div>

      <nav className="flex-1 space-y-1 px-3 py-4">
        {navItems.map((item) => {
          const Icon = item.icon;
          const active =
            pathname === item.href ||
            (item.href !== "/" && pathname.startsWith(item.href));
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                active
                  ? "border-l-2 border-[#10b981] bg-[#191a1b] text-[#f7f8f8]"
                  : "text-[#8a8f98] hover:bg-white/[0.03] hover:text-[#f7f8f8]"
              }`}
            >
              <Icon className="h-4 w-4" />
              {item.label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
