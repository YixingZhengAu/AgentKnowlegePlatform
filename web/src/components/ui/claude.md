# web/src/components/ui/

**职责**:shadcn/ui 风格的原子件(样式直接抄进仓库,不是黑盒依赖)。

| 文件 | 说明 |
| --- | --- |
| `button.tsx` | 5 个 variant:primary / accent(每页至多一个)/ secondary / danger / ghost |
| `card.tsx` | `Card` + `CardHeader/Title/Description/Content` |
| `badge.tsx` | pill 徽标,6 个语义 tone(全站唯一允许全圆的元素) |
| `table.tsx` | `Table/THead/TH/TR/TD`:灰表头 + 行 hover,不用斑马纹 |
| `input.tsx` | 36px 高、聚焦 navy 边框 + 2px 外圈 |
| `skeleton.tsx` | 加载骨架 |

新增原子件优先 `npx shadcn add <name>`(配置在 `web/components.json`),
落地后**立刻按 `documents/UI-STYLE.md` 改样式**,不留默认色。详见 `architect.md`。
