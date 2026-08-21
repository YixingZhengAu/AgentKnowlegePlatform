# web/src/lib/

**职责**:不依赖 React、不依赖后端的纯工具。

| 文件 | 说明 |
| --- | --- |
| `utils.ts` | `cn()`:clsx + tailwind-merge(后写的同族 Tailwind 类覆盖先写的) |
| `format.ts` | 展示格式化:`fmtDate/fmtDateTime`(locale 固定 en-AU)、`fmtMs`、`fmtUsd`、`fmtTokens` |
| `toast.ts` | toast 的模块级 store(push/dismiss/subscribe),渲染在 `components/Toaster.tsx` |

详见 `architect.md`。
