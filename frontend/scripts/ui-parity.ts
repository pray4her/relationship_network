/**
 * UI parity 截图工具(PR2 验收):
 * 对每个组件分别截取规格页(showcase/<name>.html)与 React 实现页(/dev/ui/<name>),
 * 输出到 test-results/ui-parity/ 供人工并排比对。
 *
 * 注意:playwright-core 库内 launch 在本机握手超时,故经 playwright CLI 截图。
 * 前置:`next dev` 已在 localhost:3000 运行。
 * 用法:bun run scripts/ui-parity.ts [name ...]   (默认全部已注册组件)
 */
import { spawnSync } from "node:child_process"
import { mkdirSync } from "node:fs"

const port = process.env["DEV_PORT"] ?? "3000"
const outDir = "test-results/ui-parity"
/** impl 目录名:showcase 规格文件名(不同名时显式映射) */
const defaultComponents = [
  "alert",
  "alert-dialog:dialog",
  "avatar",
  "badge",
  "breadcrumb",
  "button",
  "card",
  "checkbox",
  "dialog",
  "dropdown-menu",
  "empty:empty-state",
  "field:form-field",
  "input",
  "label:form-field",
  "navbar",
  "radio-group:radio",
  "select",
  "separator",
  "skeleton",
  "sonner:toast",
  "spinner",
  "table",
  "tabs",
  "textarea",
]

const components = process.argv.slice(2).length > 0 ? process.argv.slice(2) : defaultComponents

mkdirSync(outDir, { recursive: true })

function shoot(url: string, path: string): void {
  const result = spawnSync(
    "bunx",
    [
      "playwright",
      "screenshot",
      "--browser",
      "chromium",
      "--viewport-size",
      "1280,900",
      "--full-page",
      // 等水合完成再截:playwright 截图默认 caret:"hide" 会给 <input> 注入
      // 内联 caret-color,水合进行中注入会被 React 判为 hydration mismatch
      // (dev 浮标 "1 Issue"),与页面本身无关。
      "--wait-for-timeout",
      "1500",
      url,
      path,
    ],
    { stdio: "inherit" },
  )
  if (result.status !== 0) {
    throw new Error(`screenshot failed: ${url}`)
  }
}

for (const entry of components) {
  const [name, specName = name] = entry.split(":")
  shoot(`file://${process.cwd()}/showcase/${specName}.html`, `${outDir}/${name}-spec.png`)
  shoot(`http://localhost:${port}/dev/ui/${name}`, `${outDir}/${name}-impl.png`)
  console.log(`shot ${name}: spec(${specName}) + impl`)
}
