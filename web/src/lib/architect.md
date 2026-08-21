# web/src/lib/architect.md

## format.ts

- locale 硬编码 `en-AU`(平台面向澳洲用户,无 i18n —— D5/U7),不跟随浏览器设置:
  演示时截图里的日期格式必须稳定
- `fmtUsd` 只做显示:成本在后端是 `numeric(10,6)`,序列化成字符串,
  **前端不对钱做算术**(浮点误差会让"$0.000876"变成难看的尾数)
- 空值统一显示 `—`,不显示 "null" / "Invalid Date"

## toast.ts

模块级 `toasts` 数组 + `listeners` 集合,`pushToast` 后通知订阅者;
`Toaster` 用 `useSyncExternalStore(subscribe, getToasts, getToasts)` 读。
自动消失 6 秒(`AUTO_DISMISS_MS`)。

**为什么放在 lib 而不是 components**:`api/client.ts` / `api/hooks.ts` 要在非组件代码里报错,
store 不能依赖 React 树,否则取数层就得知道自己在哪个组件里跑。
