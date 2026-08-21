/** 域清单 —— 并行开发的唯一共享落笔点(RESTRUCTURE-PLAN Stage 1)。
 *
 * 加一个知识域 = 这里 import + 数组里加一行,其余(路由/导航/标题/渲染器)全部自动生成。
 * 用显式数组而不是 import 副作用注册:tree-shaking 下副作用不可靠,显式列表一眼可见。
 * 各域文件夹互为兄弟、禁止互相 import,只向上依赖 shared 层(src/{api,components,layouts,lib})。
 */

import { documentDomain } from './document/module'
import { exactQaDomain } from './exact-qa/module'
import { text2sqlDomain } from './text2sql/module'

export type { DomainModule } from './types'

export const DOMAINS = [exactQaDomain, documentDomain, text2sqlDomain]
