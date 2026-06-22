import argparse
import os
import shutil
import sqlite3
import tkinter as tk
from dataclasses import asdict, dataclass
from tkinter import filedialog, messagebox, ttk
from typing import Callable, Dict, List, Optional, Sequence


DB_FILE = os.path.join(os.path.dirname(__file__), "equipment_management.db")
EQUIPMENT_ARCHIVE_DIR = "equipment_archives"

EQUIPMENT_CATEGORIES = [
    "电子数据取证设备",
    "数据恢复设备",
    "数据恢复",
    "存储介质检验设备",
    "网络与日志分析设备",
    "移动终端取证设备",
    "写保护与复制设备",
    "实验室通用设备",
    "取证软件/许可证",
]

EQUIPMENT_STATUSES = [
    "在使用",
    "停用",
    "维修中",
    "待校准",
    "报废",
]


@dataclass
class Equipment:
    """电子数据实验室设备管理数据模型。"""

    internal_id: str
    device_name: str
    category: str
    room_number: str
    status: str
    calibration_date: Optional[str] = None
    maintenance_notes: Optional[str] = None
    archive_path: Optional[str] = None

    def to_dict(self):
        return asdict(self)


class EquipmentManager:
    def __init__(self, path: str = DB_FILE):
        self.path = path
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.create_table()

    def create_table(self):
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS equipment (
                internal_id TEXT PRIMARY KEY,
                device_name TEXT NOT NULL,
                category TEXT NOT NULL,
                room_number TEXT NOT NULL,
                status TEXT NOT NULL,
                calibration_date TEXT,
                maintenance_notes TEXT,
                archive_path TEXT
            )
            """
        )
        self.conn.commit()
        self._ensure_schema()

    def close(self):
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.close()

    def _ensure_schema(self):
        columns = [row[1] for row in self.conn.execute("PRAGMA table_info(equipment)").fetchall()]
        if "archive_path" not in columns:
            self.conn.execute("ALTER TABLE equipment ADD COLUMN archive_path TEXT")
            self.conn.commit()

    def _base_dir(self) -> str:
        return os.path.dirname(os.path.abspath(self.path))

    def _save_archive_file(self, internal_id: str, source_path: str) -> str:
        if not source_path:
            return ""
        if not os.path.exists(source_path):
            raise ValueError(f"文件不存在：{source_path}")

        ext = os.path.splitext(source_path)[1].lower()
        if ext not in (".doc", ".docx", ".pdf", ".xls", ".xlsx"):
            raise ValueError("设备档案仅支持 Word、PDF 或 Excel 文件")

        target_dir = os.path.join(self._base_dir(), EQUIPMENT_ARCHIVE_DIR)
        os.makedirs(target_dir, exist_ok=True)

        target_path = os.path.join(target_dir, f"{internal_id}_设备档案{ext}")
        counter = 1
        while os.path.exists(target_path):
            target_path = os.path.join(target_dir, f"{internal_id}_设备档案_{counter}{ext}")
            counter += 1

        shutil.copy2(source_path, target_path)
        return os.path.relpath(target_path, self._base_dir())

    def add_equipment(self, equipment: Equipment):
        self._validate_required(equipment)
        if self.get_equipment(equipment.internal_id):
            raise ValueError(f"内部编号已存在：{equipment.internal_id}")

        archive_path = self._save_archive_file(equipment.internal_id, equipment.archive_path) if equipment.archive_path else None
        self.conn.execute(
            """
            INSERT INTO equipment (
                internal_id, device_name, category, room_number, status,
                calibration_date, maintenance_notes, archive_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                equipment.internal_id,
                equipment.device_name,
                equipment.category,
                equipment.room_number,
                equipment.status,
                equipment.calibration_date,
                equipment.maintenance_notes,
                archive_path,
            ),
        )
        self.conn.commit()

    def get_equipment(self, internal_id: str) -> Optional[Equipment]:
        row = self.conn.execute("SELECT * FROM equipment WHERE internal_id = ?", (internal_id,)).fetchone()
        return Equipment(**dict(row)) if row else None

    def update_equipment(self, internal_id: str, **fields):
        current = self.get_equipment(internal_id)
        if not current:
            raise ValueError(f"未找到内部编号：{internal_id}")

        update_fields = {key: value for key, value in fields.items() if value is not None and hasattr(current, key)}
        if "archive_path" in update_fields:
            update_fields["archive_path"] = self._save_archive_file(internal_id, update_fields["archive_path"])

        if not update_fields:
            return

        updated = current.to_dict()
        updated.update(update_fields)
        self._validate_required(Equipment(**updated))

        set_clause = ", ".join(f"{key} = ?" for key in update_fields)
        values = list(update_fields.values()) + [internal_id]
        self.conn.execute(f"UPDATE equipment SET {set_clause} WHERE internal_id = ?", values)
        self.conn.commit()

    def remove_equipment(self, internal_id: str):
        if not self.get_equipment(internal_id):
            raise ValueError(f"未找到内部编号：{internal_id}")
        self.conn.execute("DELETE FROM equipment WHERE internal_id = ?", (internal_id,))
        self.conn.commit()

    def list_equipment(self, keyword: Optional[str] = None):
        if keyword:
            like = f"%{keyword}%"
            rows = self.conn.execute(
                """
                SELECT * FROM equipment
                WHERE internal_id LIKE ?
                   OR device_name LIKE ?
                   OR category LIKE ?
                   OR room_number LIKE ?
                   OR status LIKE ?
                ORDER BY internal_id
                """,
                (like, like, like, like, like),
            ).fetchall()
        else:
            rows = self.conn.execute("SELECT * FROM equipment ORDER BY internal_id").fetchall()
        return [Equipment(**dict(row)) for row in rows]

    def _validate_required(self, equipment: Equipment):
        required = {
            "内部编号": equipment.internal_id,
            "设备名称": equipment.device_name,
            "设备类别": equipment.category,
            "房间号": equipment.room_number,
            "状态": equipment.status,
        }
        missing = [label for label, value in required.items() if not str(value or "").strip()]
        if missing:
            raise ValueError(f"请填写必填项：{', '.join(missing)}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="电子数据实验室 CNAS 设备管理系统")
    subparsers = parser.add_subparsers(dest="command", required=False)

    subparsers.add_parser("gui", help="打开桌面 GUI")

    eq_parser = subparsers.add_parser("equipment", help="电子数据实验室设备管理")
    eq_sub = eq_parser.add_subparsers(dest="action", required=True)

    eq_add = eq_sub.add_parser("add", help="添加设备")
    add_equipment_arguments(eq_add, require_all=True)

    eq_update = eq_sub.add_parser("update", help="更新设备信息")
    eq_update.add_argument("--internal-id", required=True, help="内部编号")
    add_equipment_arguments(eq_update, require_all=False, include_id=False)

    eq_list = eq_sub.add_parser("list", help="列出设备")
    eq_list.add_argument("--keyword", help="按内部编号、名称、类别、房间号或状态搜索")

    eq_remove = eq_sub.add_parser("remove", help="删除设备")
    eq_remove.add_argument("--internal-id", required=True, help="内部编号")

    return parser.parse_args()


def add_equipment_arguments(parser: argparse.ArgumentParser, require_all: bool, include_id: bool = True):
    if include_id:
        parser.add_argument("--internal-id", required=require_all, help="内部编号")
    parser.add_argument("--device-name", required=require_all, help="设备名称")
    parser.add_argument("--category", required=require_all, choices=EQUIPMENT_CATEGORIES, help="设备类别")
    parser.add_argument("--room-number", required=require_all, help="房间号/区域")
    parser.add_argument("--status", required=require_all, choices=EQUIPMENT_STATUSES, help="当前状态")
    parser.add_argument("--calibration-date", help="最近校准/核查日期，例如 2026-06-01")
    parser.add_argument("--maintenance-notes", help="维护、期间核查或状态备注")
    parser.add_argument("--archive-path", help="设备 CNAS 档案文件路径（Word、PDF 或 Excel）")


def print_equipment(equipment: Equipment) -> None:
    print(f"内部编号：{equipment.internal_id}")
    print(f"设备名称：{equipment.device_name}")
    print(f"设备类别：{equipment.category}")
    print(f"房间号/区域：{equipment.room_number}")
    print(f"当前状态：{equipment.status}")
    print(f"校准/核查日期：{equipment.calibration_date or '-'}")
    print(f"维护备注：{equipment.maintenance_notes or '-'}")
    print(f"CNAS 档案：{equipment.archive_path or '-'}")
    print("-" * 40)


def run_gui():
    root = tk.Tk()
    root.title("电子数据实验室 CNAS 设备管理")
    width = 1280
    height = 560
    x = (root.winfo_screenwidth() - width) // 2
    y = (root.winfo_screenheight() - height) // 2
    root.geometry(f"{width}x{height}+{x}+{y}")
    EquipmentApp(root).run()


class EquipmentApp:
    FIELDS = [
        ("internal_id", "内部编号", "entry"),
        ("device_name", "设备名称", "entry"),
        ("category", "设备类别", "category"),
        ("room_number", "房间号/区域", "entry"),
        ("status", "当前状态", "status"),
        ("calibration_date", "校准/核查日期", "entry"),
        ("maintenance_notes", "维护备注", "entry"),
        ("archive_path", "CNAS 设备档案", "file"),
    ]
    COLUMN_WIDTHS = {
        "内部编号": 1,
        "设备名称": 2,
        "设备类别": 2,
        "房间号/区域": 1,
        "当前状态": 1,
        "校准/核查日期": 1,
        "维护备注": 2,
        "CNAS 设备档案": 2,
    }

    def __init__(self, root: tk.Tk):
        self.root = root
        self.manager = EquipmentManager()

        toolbar = ttk.Frame(root)
        toolbar.pack(fill=tk.X, padx=8, pady=8)

        ttk.Label(toolbar, text="搜索").pack(side=tk.LEFT)
        self.keyword_var = tk.StringVar()
        ttk.Entry(toolbar, textvariable=self.keyword_var, width=28).pack(side=tk.LEFT, padx=6)
        ttk.Button(toolbar, text="查询", command=self.refresh_equipment).pack(side=tk.LEFT, padx=4)
        ttk.Button(toolbar, text="重置", command=self.reset_search).pack(side=tk.LEFT, padx=4)

        columns = [label for _, label, _ in self.FIELDS]
        table_frame = ttk.Frame(root)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        y_scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL)
        self.equipment_tree = ttk.Treeview(
            table_frame,
            columns=columns,
            show="headings",
            selectmode="browse",
            yscrollcommand=y_scrollbar.set,
        )
        y_scrollbar.config(command=self.equipment_tree.yview)

        for col in columns:
            self.equipment_tree.heading(col, text=col, anchor=tk.CENTER)
            self.equipment_tree.column(
                col,
                width=120,
                minwidth=60,
                anchor=tk.CENTER,
                stretch=False,
            )
        self.equipment_tree.bind("<Button-1>", self.block_column_resize, add="+")
        table_frame.bind("<Configure>", self.resize_columns_to_table)
        self.equipment_tree.grid(row=0, column=0, sticky="nsew")
        y_scrollbar.grid(row=0, column=1, sticky="ns")
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)

        button_frame = ttk.Frame(root)
        button_frame.pack(fill=tk.X, padx=8, pady=(0, 8))
        ttk.Button(button_frame, text="添加设备", command=self.add_equipment_dialog).pack(side=tk.LEFT, padx=4)
        ttk.Button(button_frame, text="编辑设备", command=self.edit_equipment_dialog).pack(side=tk.LEFT, padx=4)
        ttk.Button(button_frame, text="删除设备", command=self.delete_equipment).pack(side=tk.LEFT, padx=4)
        ttk.Button(button_frame, text="刷新", command=self.refresh_equipment).pack(side=tk.LEFT, padx=4)

    def reset_search(self):
        self.keyword_var.set("")
        self.refresh_equipment()

    def block_column_resize(self, event):
        if self.equipment_tree.identify_region(event.x, event.y) == "separator":
            return "break"
        return None

    def resize_columns_to_table(self, event):
        total_weight = sum(self.COLUMN_WIDTHS.values())
        available_width = max(event.width - 24, 1)
        used_width = 0
        columns = list(self.equipment_tree["columns"])

        for col in columns[:-1]:
            width = max(60, available_width * self.COLUMN_WIDTHS.get(col, 1) // total_weight)
            used_width += width
            self.equipment_tree.column(col, width=width)

        if columns:
            last_col = columns[-1]
            self.equipment_tree.column(last_col, width=max(60, available_width - used_width))

    def refresh_equipment(self):
        self.clear_tree()
        keyword = self.keyword_var.get().strip() or None
        for equipment in self.manager.list_equipment(keyword):
            self.equipment_tree.insert(
                "",
                tk.END,
                values=(
                    equipment.internal_id,
                    equipment.device_name,
                    equipment.category,
                    equipment.room_number,
                    equipment.status,
                    equipment.calibration_date or "",
                    equipment.maintenance_notes or "",
                    equipment.archive_path or "",
                ),
            )

    def clear_tree(self):
        for item in self.equipment_tree.get_children():
            self.equipment_tree.delete(item)

    def get_selected_item(self):
        selected = self.equipment_tree.selection()
        if not selected:
            return None
        return self.equipment_tree.item(selected[0])["values"]

    def add_equipment_dialog(self):
        self.show_form("添加电子数据实验室设备", self.add_equipment)

    def edit_equipment_dialog(self):
        values = self.get_selected_item()
        if not values:
            messagebox.showwarning("提示", "请选择一条设备记录")
            return
        self.show_form("编辑电子数据实验室设备", self.update_equipment, values, readonly_fields={"internal_id"})

    def delete_equipment(self):
        values = self.get_selected_item()
        if not values:
            messagebox.showwarning("提示", "请选择一条设备记录")
            return
        if messagebox.askyesno("确认", "确定删除选中的设备吗？"):
            try:
                self.manager.remove_equipment(values[0])
                self.refresh_equipment()
            except ValueError as exc:
                messagebox.showerror("错误", str(exc))

    def show_form(
        self,
        title: str,
        callback: Callable[[Dict[str, str]], None],
        values=None,
        readonly_fields=None,
    ):
        readonly_fields = readonly_fields or set()
        form = tk.Toplevel(self.root)
        form.title(title)
        form.transient(self.root)
        form.grab_set()

        entries = {}
        for idx, (field_key, field_label, field_type) in enumerate(self.FIELDS):
            ttk.Label(form, text=field_label).grid(row=idx, column=0, padx=8, pady=4, sticky=tk.W)

            if field_type == "category":
                widget = ttk.Combobox(form, values=EQUIPMENT_CATEGORIES, width=43, state="readonly")
            elif field_type == "status":
                widget = ttk.Combobox(form, values=EQUIPMENT_STATUSES, width=43, state="readonly")
            else:
                widget = ttk.Entry(form, width=46)

            widget.grid(row=idx, column=1, padx=8, pady=4, sticky=tk.W)
            if values:
                widget.insert(0, values[idx] if idx < len(values) else "")
            elif field_key == "status":
                widget.insert(0, "在使用")
            elif field_key == "category":
                widget.insert(0, EQUIPMENT_CATEGORIES[0])

            if field_key in readonly_fields:
                widget.config(state="readonly")

            if field_type == "file":
                ttk.Button(form, text="选择文件", command=lambda e=widget: self.choose_archive_file(e)).grid(row=idx, column=2, padx=4, pady=4)
            entries[field_key] = widget

        def on_submit():
            data = {name: entry.get().strip() for name, entry in entries.items()}
            try:
                callback(data)
                form.destroy()
                self.refresh_equipment()
            except (ValueError, sqlite3.IntegrityError) as exc:
                messagebox.showerror("错误", str(exc))

        ttk.Button(form, text="保存", command=on_submit).grid(row=len(self.FIELDS), column=0, columnspan=3, pady=12)
        self.center_window(form)

    def choose_archive_file(self, entry: ttk.Entry):
        file_path = filedialog.askopenfilename(
            title="请选择设备 CNAS 档案文件",
            filetypes=[
                ("档案文件", "*.doc *.docx *.pdf *.xls *.xlsx"),
                ("所有文件", "*.*"),
            ],
        )
        if file_path:
            entry.delete(0, tk.END)
            entry.insert(0, file_path)

    def center_window(self, window: tk.Toplevel):
        window.update_idletasks()
        width = window.winfo_width()
        height = window.winfo_height()
        root_x = self.root.winfo_x()
        root_y = self.root.winfo_y()
        root_w = self.root.winfo_width()
        root_h = self.root.winfo_height()
        x = root_x + (root_w - width) // 2
        y = root_y + (root_h - height) // 2
        window.geometry(f"{width}x{height}+{x}+{y}")

    def add_equipment(self, data):
        self.manager.add_equipment(build_equipment(data))

    def update_equipment(self, data):
        self.manager.update_equipment(
            data["internal_id"],
            device_name=data["device_name"],
            category=data["category"],
            room_number=data["room_number"],
            status=data["status"],
            calibration_date=data["calibration_date"] or None,
            maintenance_notes=data["maintenance_notes"] or None,
            archive_path=data["archive_path"] or None,
        )

    def run(self):
        self.refresh_equipment()
        self.root.mainloop()


def build_equipment(data: Dict[str, str]) -> Equipment:
    return Equipment(
        internal_id=data["internal_id"],
        device_name=data["device_name"],
        category=data["category"],
        room_number=data["room_number"],
        status=data["status"],
        calibration_date=data.get("calibration_date") or None,
        maintenance_notes=data.get("maintenance_notes") or None,
        archive_path=data.get("archive_path") or None,
    )


def main():
    args = parse_args()
    if args.command is None or args.command == "gui":
        run_gui()
        return

    with EquipmentManager() as manager:
        if args.command == "equipment":
            handle_equipment_command(manager, args)


def handle_equipment_command(manager: EquipmentManager, args: argparse.Namespace):
    if args.action == "add":
        manager.add_equipment(
            Equipment(
                internal_id=args.internal_id,
                device_name=args.device_name,
                category=args.category,
                room_number=args.room_number,
                status=args.status,
                calibration_date=args.calibration_date,
                maintenance_notes=args.maintenance_notes,
                archive_path=args.archive_path,
            )
        )
        print(f"已添加设备：{args.internal_id}")
    elif args.action == "update":
        manager.update_equipment(
            args.internal_id,
            device_name=args.device_name,
            category=args.category,
            room_number=args.room_number,
            status=args.status,
            calibration_date=args.calibration_date,
            maintenance_notes=args.maintenance_notes,
            archive_path=args.archive_path,
        )
        print(f"已更新设备：{args.internal_id}")
    elif args.action == "list":
        items = manager.list_equipment(args.keyword)
        if not items:
            print("当前没有设备记录。")
        for equipment in items:
            print_equipment(equipment)
    elif args.action == "remove":
        manager.remove_equipment(args.internal_id)
        print(f"已删除设备：{args.internal_id}")


if __name__ == "__main__":
    main()
