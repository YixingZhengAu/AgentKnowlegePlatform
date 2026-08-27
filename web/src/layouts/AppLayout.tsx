/** 三栏骨架 —— 对话工作台的形状在这里定死(S0-PLAN Step 6.2):
 *
 *   [浅色侧栏 224px] [ 顶栏 64px / 内容区白底 ] [执行轨迹面板 320px,可折叠]
 *
 * 右侧面板是个"插槽":页面通过 useRightPanel() 往里塞内容(Step 7 塞 trace 面板),
 * 没塞东西时整块不占宽度 —— 这样列表页不会白白让出 320px。
 *
 * 侧栏有两个可展开分组,子项清单都在别处、本文件不硬编码:
 *   "How It Works"        → src/pages/how-it-works 的 HOW_IT_WORKS_NAV(总页 + 四种知识各一页)
 *   "Knowledge Ingestion" → 域清单 src/domains/index.ts(结构调整,见 S0-PLAN §5)
 */

import {
  BookOpen,
  Bot,
  ChevronDown,
  ListChecks,
  MessagesSquare,
  PanelRightClose,
  PanelRightOpen,
  Settings,
} from 'lucide-react'
import { useMemo, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'

import { DOMAINS } from '@/domains'
import { RightPanelContext, type PanelSlot } from '@/layouts/rightPanel'
import { cn } from '@/lib/utils'
import { HOW_IT_WORKS_NAV } from '@/pages/how-it-works'

const NAV_MAIN = [
  { to: '/chat', label: 'Chat', icon: MessagesSquare },
  { to: '/agents', label: 'Agents', icon: Bot },
]

const NAV_FOOT = [{ to: '/settings', label: 'Settings', icon: Settings }]

/** 路由 -> 顶栏标题(前端不从后端拿页面标题) */
const TITLES: { prefix: string; title: string }[] = [
  { prefix: '/how-it-works', title: 'How It Works' },
  { prefix: '/chat', title: 'Chat' },
  { prefix: '/agents', title: 'Agents' },
  // 审核台直链 /jobs/{id}/review(任务列表页已删,见 S0-PLAN §5)
  { prefix: '/jobs/', title: 'Review Queue' },
  ...DOMAINS.map((d) => ({ prefix: d.path, title: `${d.label} Ingestion` })),
  { prefix: '/settings', title: 'Settings' },
  { prefix: '/styleguide', title: 'Style Guide' },
]

/** 侧栏顶级项(分组头与普通链接共用的外观):38px 高、10px 圆角、激活=浅蓝底 navy 字 */
const navItemClass = (isActive: boolean) =>
  cn(
    'flex min-h-[38px] w-full items-center gap-3 rounded-[var(--radius-nav)] px-[13px] text-[13.5px] leading-[1.3] transition-all duration-150',
    isActive
      ? 'bg-nav-active text-primary font-semibold'
      : 'text-secondary-foreground hover:bg-hover hover:text-primary font-medium',
  )

/** 侧栏子项(知识域):32px 高、9px 圆角、激活=白卡 + 一层薄投影 */
const subItemClass = (isActive: boolean) =>
  cn(
    'ml-4 flex h-8 items-center gap-2.5 rounded-[var(--radius-subnav)] px-3 text-[12.5px] transition-all duration-150',
    isActive
      ? 'bg-card text-primary font-semibold shadow-[var(--shadow-xs)]'
      : 'text-secondary-foreground hover:bg-hover hover:text-primary',
  )

export function AppLayout() {
  const [panel, setPanel] = useState<PanelSlot>(null)
  const [open, setOpen] = useState(true)
  const { pathname } = useLocation()
  const ctx = useMemo(() => ({ setPanel }), [])
  // 分组展开态:落在本组的任何路由上时默认展开
  const [deckOpen, setDeckOpen] = useState(() => pathname.startsWith('/how-it-works'))
  const [ingestOpen, setIngestOpen] = useState(() => pathname.startsWith('/ingest'))

  const title =
    TITLES.find((t) => pathname.startsWith(t.prefix))?.title ?? 'Enterprise Knowledge Agent'

  return (
    <RightPanelContext.Provider value={ctx}>
      <div className="flex h-screen w-screen overflow-hidden">
        {/* 左侧导航:浅底 + 右边框,靠留白与卡片分层,不靠深色块 */}
        <nav className="bg-nav flex w-[224px] shrink-0 flex-col border-r border-[var(--border)]">
          <div className="flex h-16 items-center gap-2.5 px-[22px]">
            <span className="bg-accent size-2.5 rounded-full" />
            <span className="font-display text-primary text-[13.5px] font-bold tracking-[0.12em]">
              KNOWLEDGE
            </span>
          </div>
          <div className="flex flex-col gap-[3px] px-3.5 pt-2.5">
            {/* How It Works 分组:子项 = 说明页自己的页面清单(总页 + 四种知识各一页),
                清单出处在 pages/how-it-works,本文件不硬编码任何一页 */}
            <button
              onClick={() => setDeckOpen((v) => !v)}
              className={cn(navItemClass(pathname.startsWith('/how-it-works')), 'py-1.5')}
            >
              <BookOpen className="size-[17px] shrink-0" strokeWidth={1.75} />
              <span className="flex-1 text-left">How It Works</span>
              <ChevronDown
                className={cn(
                  'size-3.5 shrink-0 opacity-50 transition-transform duration-150',
                  !deckOpen && '-rotate-90',
                )}
                strokeWidth={1.75}
              />
            </button>
            {deckOpen &&
              HOW_IT_WORKS_NAV.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.end}
                  className={({ isActive }) => subItemClass(isActive)}
                >
                  <span className={cn('size-[7px] shrink-0 rounded-full', item.dotClass)} />
                  {item.label}
                </NavLink>
              ))}

            {NAV_MAIN.map(({ to, label, icon: Icon }, i) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) => cn(navItemClass(isActive), i === 0 && 'mt-0.5')}
              >
                <Icon className="size-[17px] shrink-0" strokeWidth={1.75} />
                {label}
              </NavLink>
            ))}

            {/* Knowledge Ingestion 分组:子项 = 各知识域(末尾 workflow 只有设计预览),识别色圆点区分 */}
            <button
              onClick={() => setIngestOpen((v) => !v)}
              className={cn(navItemClass(pathname.startsWith('/ingest')), 'mt-0.5 py-1.5')}
            >
              <ListChecks className="size-[17px] shrink-0" strokeWidth={1.75} />
              <span className="flex-1 text-left">Knowledge Ingestion</span>
              <ChevronDown
                className={cn(
                  'size-3.5 shrink-0 opacity-50 transition-transform duration-150',
                  !ingestOpen && '-rotate-90',
                )}
                strokeWidth={1.75}
              />
            </button>
            {ingestOpen &&
              DOMAINS.map((d) => (
                <NavLink
                  key={d.key}
                  to={d.path}
                  className={({ isActive }) => subItemClass(isActive)}
                >
                  {/* 域识别色圆点(UI-STYLE §2,色值只在 index.css) */}
                  <span className={cn('size-[7px] shrink-0 rounded-full', d.toneClass)} />
                  {d.label}
                </NavLink>
              ))}

            {NAV_FOOT.map(({ to, label, icon: Icon }) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) => cn(navItemClass(isActive), 'mt-0.5')}
              >
                <Icon className="size-[17px] shrink-0" strokeWidth={1.75} />
                {label}
              </NavLink>
            ))}
          </div>
          <div className="text-fainter mt-auto px-[22px] py-[18px] font-mono text-[10.5px] tracking-[0.06em]">
            S1 · demo build
          </div>
        </nav>

        <div className="bg-card flex min-w-0 flex-1 flex-col">
          {/* 顶栏:与右侧面板标题行同高,只放标题 + 右侧全局动作 */}
          <header className="flex h-16 shrink-0 items-center justify-between border-b border-[var(--border)] px-8">
            <h1>{title}</h1>
            {panel && (
              <button
                onClick={() => setOpen((v) => !v)}
                className="text-secondary-foreground hover:bg-subtle hover:text-foreground flex h-[34px] items-center gap-2 rounded-[var(--radius-pill)] border border-[var(--border-strong)] px-3.5 text-[12.5px] font-medium transition-all duration-150"
              >
                {open ? (
                  <PanelRightClose className="size-[15px]" strokeWidth={1.75} />
                ) : (
                  <PanelRightOpen className="size-[15px]" strokeWidth={1.75} />
                )}
                {open ? 'Hide' : 'Show'} {panel.title}
              </button>
            )}
          </header>

          <div className="flex min-h-0 flex-1">
            <main className="min-w-0 flex-1 overflow-y-auto px-7 pt-6 pb-7">
              <Outlet />
            </main>

            {/* 右侧执行轨迹面板:没有内容就不占位 */}
            {panel && open && (
              <aside className="flex w-[320px] shrink-0 flex-col border-l border-[var(--border)]">
                <div className="flex h-16 shrink-0 items-center px-[26px] text-[13px] font-semibold">
                  {panel.title}
                </div>
                <div className="min-h-0 flex-1 overflow-y-auto">{panel.content}</div>
              </aside>
            )}
          </div>
        </div>
      </div>
    </RightPanelContext.Provider>
  )
}
