# 页面由小型组合式布局原语构成

前端新增 Page、PageHeader、PageSection、PageToolbar、DataRegion、DescriptionList、FormSection 与 AuthPanel 等少量页面级原语，统一语义、间距和状态区域。它们只管理结构与组合，不获取业务数据、不执行权限判断，也不通过 `isAdmin`、`hasTable`、`showToolbar` 等布尔属性演化为万能页面组件。

业务页面继续负责数据、权限、字段、文案和操作，并通过明确插槽与 `children` 组合这些原语。该边界使页面层级可统一，同时保留不同领域页面的真实差异。
