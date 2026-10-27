# 星芽 AI 创作岛｜课程系统 MVP 开发需求

- 状态：In progress
- 版本：v1.0
- 日期：2026-10-24
- 产品：星芽 AI 创作岛
- 本阶段负责人：开发团队

## 当前执行状态

- [x] 教师课程编辑、课件上传和逐字稿编辑
- [x] TXT/MD 逐字稿导入
- [x] 学生课程查看和学习进度
- [x] 教师学习进度和作业查看
- [x] 前端生产构建与课程后端测试
- [x] 课程审核状态和管理员审核接口
- [x] 管理员课程审核页面
- [ ] 章节/课时独立数据模型
- [ ] AI 工具与课时 Token 额度绑定

## 1. 需求概述

本阶段建设星芽 AI 创作岛的课程系统 MVP。教师可以创建课程、上传课件、编辑逐字稿并发布到班级；学生可以查看已发布课程、学习课件、进入 AI 创作、提交作业并记录学习进度；管理员可以审核和管理课程。课程中的 AI 创作消耗现有 Token 积分系统。

学生管理、班级宠物、家长端、支付、排课、教育局端和机构结算不纳入本阶段实现，但数据结构要保留后续接入空间。

## 2. 产品目标

1. 建立“教师备课 → 发布课程 → 学生学习 → AI 创作 → 提交作品/作业 → 教师查看”的闭环。
2. 让课件与教师逐字稿严格分离，逐字稿只对教师和管理员开放。
3. 复用现有 Token 配额系统，确保 AI 工具使用受到额度控制。
4. 为后续班级宠物系统接入预留学生 ID、班级 ID 和课程学习数据接口。

## 3. 非目标

本版本不开发：

- 家长端
- 教育局端
- 机构结算
- 在线支付和退款
- 复杂排课
- 请假审批
- 教师派师
- 赛事报名
- 小组协作
- 公开课程市场
- 复杂积分商城

## 4. 角色与权限

| 角色 | 可执行操作 |
|---|---|
| 学生 | 查看已发布课程、查看课件、学习课时、进入 AI 工具、提交作业、查看自己的进度和教师反馈 |
| 教师 | 创建和编辑自己负责的课程、上传课件、导入/编辑逐字稿、配置学生步骤和 AI 提示词、提交发布、查看学生进度和作业 |
| 组织管理员 | 查看组织内课程、审核课程、发布/撤回课程、管理课程分类、查看课程数据 |
| 平台管理员 | 管理所有组织课程、管理系统配置和 Token 规则 |

权限要求：教师不能编辑其他教师的课程；学生不能访问教师逐字稿；学生只能访问已发布到自己班级的课程；管理员的组织范围必须受到组织权限限制。

## 5. 学生端栏目需求

### 5.1 我的课程 `/courses`

功能：

- 展示当前学生所属班级已发布的课程。
- 显示课程封面、标题、简介、课时数、完成百分比、最近学习时间。
- 按“继续学习、未开始、已完成”分组。
- 没有课程时显示空状态和说明。
- 点击课程进入课程详情。

接口：

- 获取学生所属班级课程。
- 获取学生课程进度。
- 获取课程课件列表。

### 5.2 课程详情

功能：

- 展示课程简介、学习目标、章节/课时列表。
- 标记当前学习课时。
- 显示课时完成状态。
- 展示学生可见的教学内容和课件。
- 不显示教师逐字稿、内部提示和管理信息。
- 提供“继续学习”“上一课”“下一课”按钮。
- 提供“去创作实践”按钮，跳转到课程配置的 AI 工具。

### 5.3 课件查看

支持类型：

- PDF
- PPT/PPTX
- 图片
- 视频
- 音频
- 文档
- 素材包

功能：

- 学生只能下载或查看已发布到自己班级的课件。
- 下载接口必须验证登录身份和班级课程权限。
- 课件不存在或课程未发布时返回 404。
- 课件下载需要记录访问日志。

### 5.4 学习进度

字段：

- studentId
- courseId
- lessonId 或 blockIndex
- percent
- completed
- lastAccessedAt
- completedAt

规则：

- 打开课时可以记录最近访问。
- 点击“完成本课”更新进度。
- 完成最后一个课时后，课程自动标记为完成。
- 重复提交完成请求必须幂等。

### 5.5 作业提交

功能：

- 学生提交文字、作品链接或作品 ID。
- 每个课程允许多次提交，但只显示最新版本和历史记录。
- 提交后状态为“待批改”。
- 教师批改后显示评语和状态。

## 6. 教师端栏目需求

### 6.1 课程列表 `/teacher/courses`

功能：

- 展示教师可管理的课程。
- 显示草稿、待审核、已发布、已下架状态。
- 显示课程标题、章节数、课件数、学生数、完成率。
- 支持新建课程。
- 点击课程进入编辑页。
- 支持按状态筛选。

### 6.2 课程基本信息

字段：

- courseId：系统生成，编辑时不可修改。
- title：必填，长度 1-100。
- summary：课程简介，长度不超过 2000。
- cover：课程封面，可选。
- category：课程分类。
- gradeRange：适用年级或年龄段。
- difficulty：入门、基础、进阶。
- learningObjectives：学习目标。
- estimatedMinutes：预计学习时长。
- status：draft、pending_review、published、offline。

校验：

- 标题不能为空。
- 发布前必须有课程简介和至少一个课时。
- 课程没有课件和教学内容时不能提交审核。

### 6.3 章节与课时

功能：

- 创建章节。
- 创建课时。
- 修改课时标题和说明。
- 拖拽或按钮调整顺序。
- 删除章节和课时。
- 课时可以关联多个课件。
- 课时可以关联一个教师逐字稿。
- 课时可以配置 AI 工具入口。

字段：

- chapterId
- courseId
- title
- description
- sortOrder
- lessonId
- lessonType
- durationMinutes
- required
- status

### 6.4 课件上传

功能：

- 教师上传课程课件。
- 上传前校验扩展名、MIME 类型和文件大小。
- 上传后执行安全扫描。
- 显示上传进度和结果。
- 支持删除课件。
- 支持将课件绑定到具体章节/课时。
- 支持替换课件，但不删除历史学习记录。

默认限制：

- 单个文件不超过 200MB。
- 文件名进行安全清洗。
- 禁止上传可执行文件。
- 上传失败不能产生课程资源记录。

### 6.5 教师逐字稿

功能：

- 教师在编辑器中输入逐字稿。
- 支持导入 TXT、MD、Markdown 文件。
- 支持保存草稿。
- 支持按课时保存逐字稿。
- 支持课堂开场、知识讲解、提问、演示、总结等内容。
- 管理员可以审核和查看逐字稿。

权限：

- 学生 API 不返回 teacherScript。
- 学生下载接口不能下载逐字稿。
- 教师只能查看自己有权限的课程逐字稿。

### 6.6 AI 工具配置

每个课时可以配置：

- capability：text、image、video、music、html。
- workspace：对应的学生创作工作台。
- promptExamples：提示词示例。
- maxUses：单节课使用次数，可为空表示继承上级额度。
- requireTeacherReview：是否需要教师审核后发布。
- allowedOutputTypes：允许的输出类型。

学生点击“去创作实践”后进入对应工作台，并携带课程 ID、课时 ID 和任务上下文。

### 6.7 发布与撤回

状态流程：

```text
draft → pending_review → published → offline
```

教师可以：

- 保存草稿。
- 提交审核。
- 查看审核状态。
- 对自己已发布课程执行撤回申请。

管理员可以：

- 审核通过。
- 驳回并填写原因。
- 发布到指定班级。
- 从班级撤回。
- 下架课程。

发布前检查：

- 有课程标题。
- 有课程简介。
- 至少有一个章节或课时。
- 至少有一个学生可见教学内容。
- 所有课时引用的课件存在。
- AI 工具配置合法。

### 6.8 教师学习数据

展示：

- 已分配学生数。
- 开始学习人数。
- 完成人数。
- 平均进度。
- 作业提交数。
- 待批改数。
- 最近学习时间。

教师只能查看自己课程范围内、且有权限管理的学生数据。

### 6.9 作业批改

功能：

- 查看学生提交内容。
- 查看学生关联作品。
- 输入教师评语。
- 设置待批改、已批改、需修改状态。
- 保存批改记录。
- 学生端可以查看教师反馈。

## 7. 管理员端栏目需求

### 7.1 课程审核

功能：

- 查看待审核课程。
- 预览学生视图。
- 预览教师逐字稿。
- 查看课件和 AI 工具配置。
- 通过或驳回。
- 填写驳回原因。
- 查看审核历史。

### 7.2 课程管理

功能：

- 查看组织内全部课程。
- 按教师、分类、状态筛选。
- 发布到班级。
- 撤回课程。
- 下架课程。
- 删除课程。
- 管理课程分类。

### 7.3 Token/积分管理

沿用现有配额层级：

```text
student → class → organization → platform
```

功能：

- 查看文本、图片、视频、音乐额度。
- 配置组织额度。
- 查看已使用、已预留、剩余额度。
- 查看课程和课时产生的消耗。
- 查询 Token 扣减日志。
- AI 请求失败时释放预留额度。

课程消耗归属：

1. 先使用学生额度；
2. 学生额度未配置时使用班级额度；
3. 班级额度未配置时使用组织额度；
4. 没有可用额度时拒绝请求。

## 8. 数据模型

### courses

- course_id
- organization_id
- author_user_id
- title
- summary
- cover_asset_id
- category_id
- grade_range
- difficulty
- learning_objectives
- estimated_minutes
- status
- version
- created_at
- updated_at
- published_at

### course_chapters

- chapter_id
- course_id
- title
- description
- sort_order

### course_lessons

- lesson_id
- chapter_id
- title
- description
- content
- sort_order
- ai_capability
- workspace_kind
- max_uses
- required

### course_materials

- material_id
- course_id
- lesson_id
- filename
- content_type
- size
- storage_key
- checksum
- uploaded_by
- created_at

### course_scripts

- script_id
- course_id
- lesson_id
- content
- source_filename
- version
- updated_by
- updated_at

### course_classrooms

- course_id
- class_id
- organization_id
- published_at
- unpublished_at

### learning_progress

- student_id
- course_id
- lesson_id
- percent
- completed
- last_accessed_at
- completed_at

### course_submissions

- submission_id
- student_id
- course_id
- lesson_id
- content
- work_id
- status
- teacher_feedback
- reviewed_by
- reviewed_at

## 9. API 需求

### 教师课程接口

- `GET /courses`：获取教师可管理课程。
- `GET /courses/{courseId}`：获取课程详情，教师可见逐字稿。
- `POST /courses`：创建或保存课程。
- `DELETE /courses/{courseId}`：删除课程。
- `POST /courses/{courseId}/materials`：上传课件。
- `GET /courses/{courseId}/materials`：获取教师课件列表。
- `DELETE /courses/materials/{materialId}`：删除课件。
- `POST /courses/{courseId}/publish`：发布到班级。
- `POST /courses/{courseId}/unpublish`：从班级撤回。

### 学生课程接口

- `GET /courses/classrooms/{classId}/published`：获取班级已发布课程。
- `GET /courses/classrooms/{classId}/published/{courseId}/materials`：获取学生可见课件。
- `GET /courses/materials/{materialId}/download`：下载已授权课件。
- `PUT /learning/progress/{courseId}`：更新学习进度。
- `GET /learning/me/progress`：获取自己的学习进度。
- `POST /learning/courses/{courseId}/submissions`：提交作业。
- `GET /learning/me/submissions`：获取自己的作业和反馈。

### 管理员接口

- `GET /admin/courses/review`：获取待审核课程。
- `POST /admin/courses/{courseId}/approve`：审核通过。
- `POST /admin/courses/{courseId}/reject`：驳回课程。
- `GET /usage/summary`：查看 Token 使用汇总。
- `POST /usage/limits`：配置额度。

## 10. Token 扣减要求

- 所有 AI 文本、图片、视频和音乐请求必须通过统一扣费入口。
- 请求开始前预留额度。
- 成功后确认扣除。
- 失败、超时或取消后释放额度。
- 每次扣费记录 userId、organizationId、classId、courseId、lessonId、metric、amount、status。
- 同一个请求重试不能重复扣费。
- 余额不足返回明确中文提示：“本次创作 Token 不足，请联系老师或管理员。”

## 11. 安全要求

- 所有课程接口必须验证 Bearer Token。
- 教师接口必须检查课程作者或组织管理权限。
- 学生接口必须检查学生所属班级。
- 逐字稿不得出现在学生响应数据中。
- 上传文件必须扫描并限制类型和大小。
- 课件下载必须校验课程发布关系。
- 重要操作记录审计日志。

## 12. 验收标准

### 教师验收

- 教师能够创建课程并保存。
- 教师能够创建章节和课时。
- 教师能够上传课件。
- 教师能够导入 TXT/MD 逐字稿。
- 教师能够保存逐字稿。
- 教师能够提交审核和发布课程。
- 教师能够查看学生进度和作业。

### 学生验收

- 学生只能看到自己班级已发布课程。
- 学生可以打开课件。
- 学生看不到逐字稿。
- 学生可以进入 AI 创作工具。
- 学生完成课时后进度被保存。
- 学生可以提交作业并查看教师反馈。

### 管理员验收

- 管理员能够审核和驳回课程。
- 管理员能够发布和撤回课程。
- 管理员能够管理课程分类。
- 管理员能够查看 Token 使用量。
- 管理员能够配置组织额度。

### 技术验收

- 课程后端测试全部通过。
- 前端生产构建通过。
- 学生、教师、管理员权限测试通过。
- 上传文件安全校验测试通过。
- Token 预留、确认和释放测试通过。
- 重复请求不会造成重复扣费。

## 13. 开发阶段

### 阶段一：课程基础

- 课程、章节、课时数据结构。
- 教师课程编辑。
- 课件上传。
- TXT/MD 逐字稿导入。
- 课程草稿和发布状态。

### 阶段二：学生学习

- 我的课程。
- 课程详情。
- 课件查看。
- 学习进度。
- AI 创作入口。
- 作业提交。

### 阶段三：审核和数据

- 管理员课程审核。
- 教师学习数据。
- 作业批改。
- 课程统计。
- Token 使用日志。

### 阶段四：后续扩展

- 班级宠物系统接入。
- 章节级课件绑定完善。
- 排课和考勤。
- 学校和机构端。
- 家长端。
- 赛事和支付。

## 14. 待确认事项

1. 课件单文件大小最终采用 100MB 还是 200MB。
2. 课程发布是否必须经过管理员审核，还是教师可以直接发布到自己的班级。
3. 学生作品提交是否只保存现有作品 ID，还是允许上传文件。
4. Token 是否按一次 AI 请求扣 1 点，还是按模型类型和实际用量计费。
5. 班级宠物系统接入时，学生和班级数据以哪个系统为主。
