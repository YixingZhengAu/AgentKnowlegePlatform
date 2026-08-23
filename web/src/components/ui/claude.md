# web/src/components/ui/

**职责**:shadcn/ui 风格的原子件(样式直接抄进仓库,不是黑盒依赖)。

| 文件 | 说明 |
| --- | --- |
| `button.tsx` | 5 个 variant:primary / accent / secondary / danger / ghost;全部 pill。**accent 是历史名,渲染成 navy CTA** —— 新语言里没有黄色按钮 |
| `card.tsx` | `Card` + `CardHeader/Title/Description/Content`,18px 圆角 + 一档极轻阴影 |
| `badge.tsx` | pill 徽标,7 个 tone,每个是「前景 + 浅底」一对 |
| `table.tsx` | `Table/THead/TH/TR/TD`:标签式表头(无灰底)+ 行 hover,不用斑马纹 |
| `input.tsx` | 填充式输入:静息 `subtle` 底 + 透明边,聚焦变白底 + ring 边 + 4px 外圈 |
| `textarea.tsx` | 多行输入,与 `input.tsx` 同一套填充/聚焦态 |
| `kbd.tsx` | 快捷键片(纯展示,不带键盘监听) |
| `segmented.tsx` | 分段控件:浅轨道 + 深色激活 pill;**只有外观,不带行为** |
| `skeleton.tsx` | 加载骨架 |

新增原子件优先 `npx shadcn add <name>`(配置在 `web/components.json`),
落地后**立刻按 `documents/UI-STYLE.md` 改样式**,不留默认色。详见 `architect.md`。
