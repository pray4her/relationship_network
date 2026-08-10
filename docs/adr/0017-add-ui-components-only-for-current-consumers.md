# UI 原语按当前页面消费者补齐

前端重构不以实现全部 showcase 组件为目标，只新增或接入当前路由已经需要的原语。范围包括新增 Navbar、Avatar、Checkbox、RadioGroup 与 Breadcrumb，使用现有 DropdownMenu 组合成员入口，并全面接入 Empty、Skeleton、Separator、Select、Badge、Button loading 和语义 Table。

Dialog、Tabs、Sonner、Pagination、Slider、Datepicker、Combobox 等只有出现真实交互消费者时才实现或接入，继续遵守 ADR 0003 关于避免无消费者投机组件的决定。
