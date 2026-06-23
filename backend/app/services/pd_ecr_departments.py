"""PD-ECR Department and hierarchy definitions.

Defines the organisational departments, their roles in the PD-ECR process,
and the mapping of each of the six V1 modules to responsible departments.

Role convention for User.pd_ecr_role:

    "department_leader"  — 部长：管理本部门所有模块，可分配模块给本部员
    "department_member"  — 部员：只能编辑分配给自己的模块
    "pd_ecr_manager"     — 跨部门管理员：全部权限（不受部门限制）

The User.department field must match a Department enum value.
"""

from __future__ import annotations

from enum import Enum
from typing import Any


class Department(str, Enum):
    """Organisational departments in the PD-ECR process.

    Values match the User.department field convention.
    """

    DESIGN = "design"                # 技术/设计
    SYSTEM = "system"                # 系统
    PURCHASING = "purchasing"        # 采购/PUE
    MANUFACTURING = "manufacturing"  # 生产/MOE
    QUALITY = "quality"              # 质量
    PM = "pm"                        # 项目管理
    CATALYST = "catalyst"            # 催化剂


# User.pd_ecr_role values that indicate department leadership
DEPARTMENT_LEADER_ROLE = "department_leader"
DEPARTMENT_MEMBER_ROLE = "department_member"
CROSS_DEPT_MANAGER_ROLE = "pd_ecr_manager"
REVIEW_ROLE = "reviewer"


# ── Module → responsible departments ──────────────────────────────────────
#
# Each of the six V1 PD-ECR modules maps to one or more responsible
# departments.  A department leader can edit any module their department
# is responsible for.  A department member can only edit modules that are
# both (a) their department's responsibility AND (b) explicitly assigned
# to them via module.assignee_id.
#
# Multi-department modules (e.g. implementation_plan) allow ANY of the
# listed departments to take responsibility — the first department to
# claim ownership effectively manages it.
# ──────────────────────────────────────────────────────────────────────────

MODULE_DEPARTMENT_MAP: dict[str, list[Department]] = {
    "basic_information":             [Department.DESIGN],
    "change_description":            [Department.DESIGN],
    "reason_for_change":             [Department.DESIGN],
    "impact_analysis":               [Department.DESIGN, Department.SYSTEM],
    "implementation_plan":           [
        Department.DESIGN,
        Department.MANUFACTURING,
        Department.PURCHASING,
        Department.QUALITY,
        Department.PM,
    ],
    "approval_signoff_information":  [Department.PM],
}

# Module IDs belonging to each department (derived, for reverse lookup)
DEPARTMENT_MODULE_MAP: dict[Department, list[str]] = {}
for _mod_id, _depts in MODULE_DEPARTMENT_MAP.items():
    for _dept in _depts:
        DEPARTMENT_MODULE_MAP.setdefault(_dept, []).append(_mod_id)


def get_module_departments(module_id: str) -> list[Department]:
    """Return the departments responsible for a given module ID.

    Args:
        module_id: One of the six V1 module IDs
            (basic_information, change_description, etc.)

    Returns:
        List of responsible departments, or empty list if unknown.
    """
    return MODULE_DEPARTMENT_MAP.get(module_id, [])


def get_department_modules(department: Department) -> list[str]:
    """Return all module IDs a department is responsible for."""
    return DEPARTMENT_MODULE_MAP.get(department, [])


def is_department_leader(user: Any) -> bool:
    """Check whether a user has department leader privileges.

    Returns True when User.pd_ecr_role == "department_leader".
    """
    role = _safe_role(user)
    return role == DEPARTMENT_LEADER_ROLE


def is_department_member(user: Any) -> bool:
    """Check whether a user is a regular department member."""
    role = _safe_role(user)
    return role == DEPARTMENT_MEMBER_ROLE


def is_cross_dept_manager(user: Any) -> bool:
    """Check whether a user is a cross-department PD-ECR manager."""
    role = _safe_role(user)
    return role == CROSS_DEPT_MANAGER_ROLE


def user_department(user: Any) -> str:
    """Return the user's department as a lowercase string, or empty string."""
    dept = str(getattr(user, "department", "") or "").strip().lower()
    return dept


def user_is_in_department(user: Any, department: Department) -> bool:
    """Check if a user belongs to a specific department."""
    return user_department(user) == department.value


def module_is_responsible_for(module_id: str, department: Department) -> bool:
    """Check whether a department is responsible for a module."""
    return department in get_module_departments(module_id)


def user_can_lead_module(user: Any, module_id: str) -> bool:
    """Check if a department leader can manage a module.

    A leader can manage a module if:
    - Their role is "department_leader" AND
    - Their department is responsible for the module
    """
    if not is_department_leader(user):
        return False
    dept = user_department(user)
    try:
        department = Department(dept)
    except ValueError:
        return False
    return module_is_responsible_for(module_id, department)


def user_is_assigned_to_module(user: Any, module: Any) -> bool:
    """Check if a user is the explicit assignee of a module.

    Args:
        user: Must have an `id` attribute (UUID).
        module: Must have an `assignee_id` attribute (UUID or None).
    """
    user_id = str(getattr(user, "id", ""))
    assignee_id = str(getattr(module, "assignee_id", "") or "")
    return bool(user_id and assignee_id and user_id == assignee_id)


def _safe_role(user: Any) -> str:
    """Extract pd_ecr_role from a user object safely."""
    return str(getattr(user, "pd_ecr_role", "") or "").strip()


# ── Department labels (for UI display) ────────────────────────────────────

DEPARTMENT_LABELS: dict[Department, str] = {
    Department.DESIGN:         "技术/设计",
    Department.SYSTEM:         "系统",
    Department.PURCHASING:     "采购/PUE",
    Department.MANUFACTURING:  "生产/MOE",
    Department.QUALITY:        "质量",
    Department.PM:             "项目管理",
    Department.CATALYST:       "催化剂",
}


def department_label(department: Department) -> str:
    """Human-readable department name."""
    return DEPARTMENT_LABELS.get(department, department.value)
