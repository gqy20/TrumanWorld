# 贡献指南

> 感谢你为 TrumanWorld 做出贡献！

---

## 📋 目录

- [行为准则](#行为准则)
- [贡献方式](#贡献方式)
- [开发流程](#开发流程)
- [代码规范](#代码规范)
- [提交规范](#提交规范)
- [PR 流程](#pr-流程)

---

## 行为准则

- 尊重他人观点，保持友好合作
- 对事不对人，聚焦技术问题
- 欢迎任何形式的贡献：代码、文档、测试、建议

---

## 贡献方式

### 代码贡献

- 新功能开发
- Bug 修复
- 测试覆盖
- 性能优化

### 非代码贡献

- 文档完善
- 问题报告
- 功能建议
- 翻译工作

---

## 开发流程

### 1. Fork 仓库

```bash
# 在 GitHub 上 Fork 本项目
```

### 2. 克隆仓库

```bash
git clone https://github.com/gqy20/TrumanWorld.git
cd truman-world
```

### 3. 创建分支

```bash
# 从 main 分支创建新分支
git checkout -b feature/your-feature-name
```

分支命名规范：

| 前缀 | 说明 |
|------|------|
| `feature/` | 新功能 |
| `fix/` | Bug 修复 |
| `docs/` | 文档更新 |
| `refactor/` | 重构 |
| `test/` | 测试 |
| `chore/` | 工具/配置 |

### 4. 开发并测试

```bash
# 安装依赖
make install

# 运行测试
make test

# 代码检查
make lint
make format
```

### 5. 提交代码

```bash
git add .
git commit -m "feat: add new feature"
```

### 6. 推送并创建 PR

```bash
git push origin feature/your-feature-name
```

在 GitHub 上创建 Pull Request。

---

## 代码规范

### Python

- 遵循 [PEP 8](https://pep8.org/)
- 使用 4 空格缩进
- 行宽限制 100 字符
- 函数/变量用 `snake_case`
- 类用 `PascalCase`
- 常量用 `UPPER_SNAKE_CASE`

```bash
# 格式化
make format

# 检查
make lint
```

### TypeScript/React

- 使用 2 空格缩进
- 组件用 `PascalCase`
- 函数/变量用 `camelCase`

```bash
cd frontend
npm run lint
npm run test
npm run build
```

### 测试

- 新功能的测试覆盖率应 ≥ 80%
- Python 测试文件命名：`test_*.py`
- 前端测试文件命名：`*.test.ts(x)` 或 `__tests__/*`
- 测试名称应聚焦行为而不是实现细节

```bash
# 运行测试
make test

# 覆盖率报告
cd backend && uv run pytest --cov=app --cov-report=html
```

---

## 提交规范

遵循 [Conventional Commits](https://www.conventionalcommits.org/)

### 格式

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

### Type 类型

| 类型 | 说明 |
|------|------|
| `feat` | 新功能 |
| `fix` | Bug 修复 |
| `docs` | 文档更新 |
| `style` | 格式调整（不影响代码逻辑） |
| `refactor` | 重构 |
| `test` | 测试 |
| `chore` | 构建/工具/配置 |

### 示例

```
feat(agent): add reflection capability

- Add Reflector class
- Add daily reflection logic
- Update agent.yml schema

Closes #123
```

```
fix(sim): resolve tick progression bug

Fixed issue where simulation would hang when agent count is zero.
```

---

## PR 流程

### PR 要求

1. **标题**：使用 Conventional Commits 格式
2. **描述**：简要说明改动内容和目的
3. **关联 Issue**：在描述中引用相关 Issue
4. **测试**：确保测试通过，CI 检查通过
5. **覆盖率**：新功能建议覆盖率 ≥ 80%
6. **代码审查**：至少需要 1 人 review

### PR 模板

```markdown
## 变更说明
<!-- 简要描述本次 PR 的改动 -->

## 关联 Issue
<!-- 如有关联 Issue，请在此引用 -->
Closes #123

## 测试命令
<!-- 列出验证测试的命令 -->
```bash
make test
make lint
```

## 截图（如适用）
<!-- 前端改动请提供截图 -->
```

### Review 流程

1. 维护者会在 48 小时内 review
2. 根据反馈修改后重新提交
3. 审核通过后合并到 main 分支

---

## 发布流程

### 版本号规则

遵循 [Semantic Versioning](https://semver.org/)

- `MAJOR.MINOR.PATCH`
- 例：`v0.1.0`

MVP 阶段使用 `0.x.y` 版本号，正式发布后使用 `1.0.0`

### 发布步骤

1. 更新 `CHANGELOG.md`
2. 创建 git tag
3. 在 GitHub 发布 Release

---

## 问题反馈

### 报告 Bug

使用 Issue 模板报告 Bug：

- 简要描述问题
- 提供复现步骤
- 附上错误日志
- 说明环境信息

### 功能建议

使用 Issue 模板提出建议：

- 说明使用场景
- 描述期望行为
- 解释为什么需要

---

## 许可证

本项目采用 [MIT License](../LICENSE)。贡献代码将采用相同许可。

---

## 感谢

感谢所有为 TrumanWorld 做出贡献的开发者！
