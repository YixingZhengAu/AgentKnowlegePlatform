/** 三栏骨架 —— 对话工作台的形状在这里定死(S0-PLAN Step 6.2):
 *
 *   [navy 侧栏 220px] [ 顶栏 56px / 内容区 bg-page ] [执行轨迹面板 360px,可折叠]
 *
 * 右侧面板是个"插槽":页面通过 useRightPanel() 往里塞内容(Step 7 塞 trace 面板),
 * 没塞东西时整块不占宽度 —— 这样列表页不会白白让出 360px。
 */

import {
  Bot,
  Library,
  ListChecks,
  MessagesSquare,
  PanelRightClose,
  PanelRightOpen,
  Settings,
} from 'lucide-react'
import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'

import { cn } from '@/lib/utils'

const NAV = [
  { to: '/chat', label: 'Chat', icon: MessagesSquare },
  { to: '/kbs', label: 'Knowledge Bases', icon: Library },
  { to: '/agents', label: 'Agents', icon: Bot },
  { to: '/jobs', label: 'Ingestion', icon: ListChecks },
  { to: '/settings', label: 'Settings', icon: Settings },
]

/** 路由 -> 顶栏标题(前端不从后端拿页面标题) */
const TITLES: { prefix: string; title: string }[] = [
  { prefix: '/chat', title: 'Chat' },
  { prefix: '/kbs', title: 'Knowledge Bases' },
  { prefix: '/agents', title: 'Agents' },
  { prefix: '/jobs', title: 'Ingestion Jobs' },
  { prefix: '/settings', title: 'Settings' },
  { prefix: '/styleguide', title: 'Style Guide' },
]

type PanelSlot = { title: string; content: ReactNode } | null

const RightPanelContext = createContext<{
  setPanel: (slot: PanelSlot) => void
}>({ setPanel: () => {} })

/** 页面调用它把内容挂到右侧面板;依赖变化时自动替换,卸载时自动清空。 */
export function useRightPanel(title: string, content: ReactNode, deps: unknown[] = []) {
  const { setPanel } = useContext(RightPanelContext)
  useEffect(() => {
    setPanel({ title, content })
    return () => setPanel(null)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [title, ...deps])
}

export function AppLayout() {
  const [panel, setPanel] = useState<PanelSlot>(null)
  const [open, setOpen] = useState(true)
  const { pathname } = useLocation()
  const ctx = useMemo(() => ({ setPanel }), [])

  const title = TITLES.find((t) => pathname.startsWith(t.prefix))?.title ?? 'Clenergy Agent'

  return (
    <RightPanelContext.Provider value={ctx}>
      <div className="flex h-screen w-screen overflow-hidden">
        {/* 左侧导航:navy 深底 + 白字,呼应官网导航 */}
        <nav className="bg-primary text-primary-foreground flex w-[220px] shrink-0 flex-col">
          <div className="flex h-14 items-center gap-2 px-5">
            <span className="bg-accent size-2.5 rounded-full" />
            <span className="font-display text-[14px] font-bold tracking-wide">CLENERGY</span>
          </div>
          <div className="flex flex-col gap-0.5 px-2 py-3">
            {NAV.map(({ to, label, icon: Icon }) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) =>
                  cn(
                    'relative flex items-center gap-3 rounded-[var(--radius)] px-3 py-2 text-[14px] transition-colors duration-150',
                    isActive
                      ? 'bg-white/8 font-medium text-white'
                      : 'text-white/70 hover:bg-white/5 hover:text-white',
                  )
                }
              >
                {({ isActive }) => (
                  <>
                    {/* 激活项左侧 3px 黄色竖条(UI-STYLE §3) */}
                    {isActive && (
                      <span className="bg-accent absolute top-1.5 bottom-1.5 -left-2 w-[3px] rounded-r" />
                    )}
                    <Icon className="size-4" strokeWidth={1.75} />
                    {label}
                  </>
                )}
              </NavLink>
            ))}
          </div>
          <div className="mt-auto px-5 py-4 font-mono text-[11px] text-white/40">
            S0 · demo build
          </div>
        </nav>

        <div className="flex min-w-0 flex-1 flex-col">
          {/* 顶栏:白底,只放标题 + 右侧全局动作 */}
          <header className="bg-card flex h-14 shrink-0 items-center justify-between border-b px-6">
            <h1>{title}</h1>
            {panel && (
              <button
                onClick={() => setOpen((v) => !v)}
                className="text-muted-foreground hover:text-foreground flex items-center gap-2 text-[12px]"
              >
                {open ? (
                  <PanelRightClose className="size-4" />
                ) : (
                  <PanelRightOpen className="size-4" />
                )}
                {open ? 'Hide' : 'Show'} {panel.title}
              </button>
            )}
          </header>

          <div className="flex min-h-0 flex-1">
            <main className="bg-background min-w-0 flex-1 overflow-y-auto p-6">
              <Outlet />
            </main>

            {/* 右侧执行轨迹面板:没有内容就不占位 */}
            {panel && open && (
              <aside className="bg-card flex w-[360px] shrink-0 flex-col overflow-y-auto border-l">
                <div className="text-muted-foreground border-b px-5 py-3 font-mono text-[12px] tracking-wide uppercase">
                  {panel.title}
                </div>
                <div className="min-h-0 flex-1">{panel.content}</div>
              </aside>
            )}
          </div>
        </div>
      </div>
    </RightPanelContext.Provider>
  )
}
