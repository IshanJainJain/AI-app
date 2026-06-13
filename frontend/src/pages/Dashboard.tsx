import { useEffect, useState } from "react";
import { MessageSquare, BookOpen, Users, Cpu } from "lucide-react";
import { threadsApi, kbApi, authApi } from "../services/api";
import type { Thread } from "../types";

interface Stat {
  label: string;
  value: number | string;
  Icon: React.FC<{ size?: number; className?: string }>;
  color: string;
}

export default function Dashboard() {
  const [threads, setThreads] = useState<Thread[]>([]);
  const [kbFiles, setKbFiles] = useState(0);
  const [username, setUsername] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([threadsApi.list(), kbApi.browse(), authApi.me()])
      .then(([t, kb, me]) => {
        setThreads(t.data.threads);
        setKbFiles(kb.data.files.length);
        setUsername(me.data.username);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const totalMessages = threads.reduce((s, t) => s + (t.message_count ?? 0), 0);

  const stats: Stat[] = [
    { label: "Conversations", value: threads.length, Icon: MessageSquare, color: "text-indigo-400" },
    { label: "Total Messages", value: totalMessages, Icon: Cpu, color: "text-violet-400" },
    { label: "KB Documents", value: kbFiles, Icon: BookOpen, color: "text-emerald-400" },
    { label: "Signed in as", value: username || "—", Icon: Users, color: "text-sky-400" },
  ];

  return (
    <div className="p-8">
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-white">Dashboard</h1>
        <p className="text-sm text-gray-400 mt-1">Overview of your AI workspace</p>
      </div>

      {loading ? (
        <div className="text-gray-500 text-sm">Loading...</div>
      ) : (
        <>
          {/* KPI cards */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
            {stats.map(({ label, value, Icon, color }) => (
              <div
                key={label}
                className="bg-gray-900 border border-gray-800 rounded-xl p-4"
              >
                <div className="flex items-center justify-between mb-3">
                  <span className="text-xs text-gray-400">{label}</span>
                  <Icon size={16} className={color} />
                </div>
                <p className="text-2xl font-semibold text-white">{value}</p>
              </div>
            ))}
          </div>

          {/* Recent threads */}
          <div className="bg-gray-900 border border-gray-800 rounded-xl">
            <div className="px-5 py-3 border-b border-gray-800">
              <h2 className="text-sm font-medium text-gray-200">Recent conversations</h2>
            </div>
            {threads.length === 0 ? (
              <div className="px-5 py-8 text-center text-gray-500 text-sm">
                No conversations yet — go to Chat to start one.
              </div>
            ) : (
              <ul>
                {threads.slice(0, 10).map((t) => (
                  <li
                    key={t.id}
                    className="flex items-center justify-between px-5 py-3 border-b border-gray-800 last:border-0 hover:bg-gray-800/40 transition-colors"
                  >
                    <div>
                      <p className="text-sm text-white">{t.title}</p>
                      <p className="text-xs text-gray-500 mt-0.5">
                        {t.message_count} message{t.message_count !== 1 ? "s" : ""}
                      </p>
                    </div>
                    <span className="text-xs text-gray-600">
                      {new Date(t.updated_at).toLocaleDateString()}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </>
      )}
    </div>
  );
}
