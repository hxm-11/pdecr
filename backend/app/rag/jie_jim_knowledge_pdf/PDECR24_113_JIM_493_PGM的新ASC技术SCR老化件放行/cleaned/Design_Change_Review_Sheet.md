# Design Change Review Sheet 设计变更评审表

## 文档信息

| 字段 | 内容 |
|---|---|
| 文件类型 | Design Change Review Sheet / 设计变更评审表 |
| Version | 13 |
| Effective date | 2024-09-29th |
| Design Change Request No. | 24_113 |

---

## 1. Function & Performance / 系统性能影响

| 字段 | 内容 |
|---|---|
| Function & Performance will be influenced? / 系统性能影响？ | [ ] yes / 是；[x] no / 否 |
| If Yes, System impaction evaluation? / 如果是，系统影响评估？（如果是初次样件放行，空白处请说明样件目的） | 否，标定样件 |
| Whether need sample to test? Plan? / 是否需要样件进行验证？计划？ | 否，标定样件 |
| Whether the catalyst information is confirmed? / 催化剂信息是否确认？（物料号、图纸、SPEC） |  |

| 角色 | 签名 |
|---|---|
| System / 系统 | 沈伟波 |
| Catalyst / 催化剂 | 张汉泉 |

---

## 2. Interface & Boundary / 接口&边界影响

| 字段 | 内容 |
|---|---|
| Interface & boundary (internal and customer) will be influenced? / 接口&边界（内部和客户）影响？ | [ ] yes / 是；[x] no / 否 |
| If impact customer, whether get confirm from customer side? / 请说明影响和是否得到客户的确认？ |  |

| 角色 | 签名 |
|---|---|
| Design / 设计 | 卢青松 |

---

## 3. Mechanical Strength & Durability / 机械强度&可靠性影响

| 字段 | 内容 |
|---|---|
| Mechanical strength & Durability will be influenced? / 机械强度&可靠性影响？ | [ ] yes / 是；[x] no / 否 |
| If Yes, How to evaluate? Plan? / 如果是，请说明影响和如何评估，计划？（例如：仿真分析等） | A样无需FEA |
| Whether need sample to test? Plan? / 是否需要样件进行验证？计划？ |  |

| 角色 | 签名 |
|---|---|
| Validation / 验证 | 卢青松 |

---

## 4. Product Document Influenced / 产品文档影响

| 子项 | 是否影响 | 备注 |
|---|---|---|
| 4.1 Interface FMEA-relevant / IFMEA | [x] no / 否；[ ] yes / 是 |  |
| 4.2 Product FMEA-relevant / DFMEA | [x] no / 否；[ ] yes / 是 |  |
| 4.3 Special Characteristics / PSC（针对C Sample） | [x] no / 否；[ ] yes / 是 |  |
| 4.4 IMDS relevant（针对C Sample） | [x] no / 否；[ ] yes / 是 |  |
| 4.5 Offer drawing relevant（针对C Sample） | [x] no / 否；[ ] yes / 是 |  |
| 4.6 TCD relevant | [x] no / 否；[ ] yes / 是 |  |

| 角色 | 签名 |
|---|---|
| Design / 设计 | 卢青松 |

---

## 5. Changed Parts Stock & Treatment / 需要变更零件的库存统计和处理

| 字段 | 内容 |
|---|---|
| 库存处理总体说明 | NA（新零件放行，不涉及库存）（只针对涉及到已经生产过的零件变更，新放行零件和本条不相关） |

### 库存盘点

| 库存地点 | 状态 | 库存数量 |
|---|---|---|
| RBCW RDC（外库）和RBCW仓库 | [x] 无库存；[ ] 有库存 |  |
| 供应商处（已做好，未发货） | [x] 无库存；[ ] 有库存 |  |
| LPN工厂 | [x] 无库存；[ ] 有库存 |  |
| 在途，运输中 | [x] 无库存；[ ] 有库存 |  |

### 实物库存处理指示（设计工程师组织会议讨论）

| 字段 | 内容 |
|---|---|
| 处理方式 | [ ] 可以继续使用完；[ ] 改制后使用；[ ] 报废 |
| 改制费用 / 报废成本 |  |

| 角色 | 签名 |
|---|---|
| PUE | 李奕岑 |

### 已装车件处理方法（SMP组织会议讨论）

| 字段 | 内容 |
|---|---|
| 处理方式 | [ ] 改制；[ ] 更换 |

---

## 6. Influence on Supplier Part / 对供应商零件的影响

| 字段 | 内容 |
|---|---|
| Was this change confirmed with Purchasing (Supplier) for feasibility? Feedback from Supplier? / 变更后的零件，生产可行性供应商是否确认？反馈？ |  |
| Influence on purchasing part delivery time? / 对采购件交货时间的影响？ |  |
| 涉及到变更的零件，博世已出PR，供应商还未来得及生产的订单，是否已经通知供应商取消？ | [ ] no / 否；[ ] yes / 是 |
| Does the change influence on purchasing cost? / 变更对采购成本的影响？ | [ ] increase / 增加，金额____；[ ] decrease / 降低，金额____；[x] no change / 不变 |

| 角色 | 签名 |
|---|---|
| PUE | 方李参、李奕岑（确认） |

---

## 7. DFMA & Sample Production OPL

| 字段 | 内容 |
|---|---|
| DFMA & Sample production OPL? / 必要时附加DFMA文件 | 只更换催化剂，无需DFMA |


| 角色 | 签名 |
|---|---|
| Design | 卢青松 |

---

## 8. Influence on LPN Manufacturing & Assembly Process / 对LPN制造装配的影响

| 字段 | 内容 |
|---|---|
| Feedback from manufacturing engineer? / 产制造装配是否影响，反馈？ |  |
| Influence on project & product delivery time? / 对项目&产品交货时间的影响？ |  |
| Influence on manufacturing cost? / 对产成本的影响？ | [ ] increase / 增加，金额____；[ ] decrease / 降低，金额____；[x] no change / 不变 |

| 角色 | 签名 |
|---|---|
| PUE | 方李参、李奕岑（确认） |

---

## 9. PM Alignment / 项目经理确认

| 字段 | 内容 |
|---|---|
| PM alignment? (Influence on project Timeline? Cost?) / 是否同意对项目时间和成本的影响？ |  |
| 需求样品订单数量 |  |

| 角色 | 签名 |
|---|---|
| PM |  |

---

## 10. TCR3 审核确认

| 字段 | 内容 |
|---|---|
| 如果涉及以下情况需TCR3审核确认。不涉及则 NA |  |
| RBC库存报废，金额 |  |
| 采购成本增加，金额 |  |
| 产成本增加，金额 |  |


---

## 签核信息

| 角色 | 姓名 | 签名 | 日期 |
|---|---|---|---|
| Design Team Leader / 设计团队负责人 |  |  |  |
| ENG-CV1 | (确认) |  |  |
| PUR | 确认 |  | 2024.10.9 |
| TCR3 Department Manager / 部门经理 | 谢友福 |  | 2024.10.15 |
