# src/inventory_app/ui/app_window.py
"""Main Tkinter GUI application window with embedded Matplotlib reporting and threaded AI."""

import queue
import threading
import tkinter as tk
from decimal import Decimal, InvalidOperation
from tkinter import messagebox, ttk
from typing import Dict, Tuple
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from inventory_app.exceptions import InventoryAppError
from inventory_app.models.product import Product
from inventory_app.models.transaction import TransactionType
from inventory_app.services.ai_assistant import InventoryAssistant
from inventory_app.services.api_service import ExchangeRateAPIService
from inventory_app.services.inventory_service import InventoryService
from inventory_app.services.sales_service import SalesService


class InventoryAppWindow(tk.Tk):
    """Root Tkinter window orchestrating Inventory, Sales, Reports, API, and AI tabs."""

    def __init__(
        self,
        inventory_service: InventoryService,
        sales_service: SalesService,
        api_service: ExchangeRateAPIService,
        ai_assistant: InventoryAssistant,
    ) -> None:
        super().__init__()
        self._inventory = inventory_service
        self._sales = sales_service
        self._api = api_service
        self._ai = ai_assistant
        self._ai_queue: queue.Queue[Tuple[bool, str]] = queue.Queue()

        self.title("Group 37 — Smart Inventory Management System")
        self.geometry("1180x740")
        self.minsize(1024, 680)

        self._entries: Dict[str, tk.StringVar] = {}
        self._build_layout()
        self._refresh_all_views()
        self.after(100, self._poll_ai_queue)

    def _build_layout(self) -> None:
        """Construct the top KPI banner and the 4-tab ttk.Notebook interface."""
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        self._kpi_label = ttk.Label(
            self,
            text="Loading Inventory Telemetry...",
            font=("Segoe UI", 11, "bold"),
            padding=(12, 8),
        )
        self._kpi_label.grid(row=0, column=0, sticky="ew")

        self._notebook = ttk.Notebook(self)
        self._notebook.grid(row=1, column=0, sticky="nsew", padx=10, pady=6)

        self._tab_inventory = ttk.Frame(self._notebook, padding=10)
        self._tab_operations = ttk.Frame(self._notebook, padding=10)
        self._tab_reports = ttk.Frame(self._notebook, padding=10)
        self._tab_ai = ttk.Frame(self._notebook, padding=10)

        self._notebook.add(self._tab_inventory, text="1. Products & Inventory")
        self._notebook.add(self._tab_operations, text="2. Stock, Sales & FX API")
        self._notebook.add(self._tab_reports, text="3. Reports & Charts")
        self._notebook.add(self._tab_ai, text="4. AI Inventory Assistant")

        self._build_inventory_tab()
        self._build_operations_tab()
        self._build_reports_tab()
        self._build_ai_tab()

    def _build_inventory_tab(self) -> None:
        """Build Product CRUD form, search bar, and Treeview table."""
        self._tab_inventory.columnconfigure(1, weight=1)
        self._tab_inventory.rowconfigure(1, weight=1)

        # Left Form: Add / Update Product
        form = ttk.LabelFrame(self._tab_inventory, text="Product Registration", padding=10)
        form.grid(row=0, column=0, rowspan=2, sticky="ns", padx=(0, 10))

        fields = [
            ("product_id", "Product ID (e.g. PRD-01):"),
            ("name", "Product Name:"),
            ("category", "Category:"),
            ("supplier_id", "Supplier ID (e.g. SUP-01):"),
            ("quantity", "Initial Quantity:"),
            ("cost_price", "Cost Price ($):"),
            ("selling_price", "Selling Price ($):"),
            ("min_stock", "Min Stock Alert Level:"),
        ]
        for idx, (key, label_text) in enumerate(fields):
            ttk.Label(form, text=label_text).grid(row=idx * 2, column=0, sticky="w", pady=(4, 0))
            var = tk.StringVar()
            self._entries[key] = var
            ttk.Entry(form, textvariable=var, width=26).grid(row=idx * 2 + 1, column=0, sticky="ew")

        ttk.Button(form, text="Add Product", command=self._on_add_product).grid(
            row=16, column=0, sticky="ew", pady=(10, 4)
        )
        ttk.Button(form, text="Update Product", command=self._on_update_product).grid(
            row=17, column=0, sticky="ew", pady=4
        )
        ttk.Button(form, text="Delete Selected", command=self._on_delete_product).grid(
            row=18, column=0, sticky="ew", pady=4
        )

        # Right Top: Search Filter
        search_frame = ttk.Frame(self._tab_inventory)
        search_frame.grid(row=0, column=1, sticky="ew", pady=(0, 6))
        ttk.Label(search_frame, text="Search ID/Name:").pack(side="left")
        self._search_var = tk.StringVar()
        ttk.Entry(search_frame, textvariable=self._search_var, width=30).pack(side="left", padx=6)
        ttk.Button(search_frame, text="Filter", command=self._refresh_product_table).pack(side="left")
        ttk.Button(
            search_frame,
            text="Clear",
            command=lambda: (self._search_var.set(""), self._refresh_product_table()),
        ).pack(side="left", padx=4)

        # Right Table: Product Catalog Treeview
        cols = ("id", "name", "category", "supplier", "qty", "cost", "price", "min", "status")
        self._tree = ttk.Treeview(self._tab_inventory, columns=cols, show="headings", height=18)
        headers = {
            "id": "ID",
            "name": "Name",
            "category": "Category",
            "supplier": "Supplier",
            "qty": "Qty",
            "cost": "Cost ($)",
            "price": "Price ($)",
            "min": "Min",
            "status": "Status",
        }
        for col, text in headers.items():
            self._tree.heading(col, text=text)
            self._tree.column(col, width=90 if col != "name" else 180, anchor="center")
        self._tree.grid(row=1, column=1, sticky="nsew")

    def _build_operations_tab(self) -> None:
        """Build Point-of-Sale, Stock-In/Out adjustment, and Live FX API converter."""
        self._tab_operations.columnconfigure((0, 1), weight=1)

        # Sales & Stock Movement Panel
        ops_box = ttk.LabelFrame(self._tab_operations, text="Record Sale or Stock Movement", padding=12)
        ops_box.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=8)

        self._op_pid = tk.StringVar()
        self._op_qty = tk.StringVar()
        self._op_notes = tk.StringVar()

        ttk.Label(ops_box, text="Product ID:").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Entry(ops_box, textvariable=self._op_pid, width=25).grid(row=0, column=1, pady=4)
        ttk.Label(ops_box, text="Quantity:").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Entry(ops_box, textvariable=self._op_qty, width=25).grid(row=1, column=1, pady=4)
        ttk.Label(ops_box, text="Notes:").grid(row=2, column=0, sticky="w", pady=4)
        ttk.Entry(ops_box, textvariable=self._op_notes, width=25).grid(row=2, column=1, pady=4)

        ttk.Button(ops_box, text="Record Customer Sale", command=self._on_record_sale).grid(
            row=3, column=0, columnspan=2, sticky="ew", pady=(10, 4)
        )
        ttk.Button(
            ops_box,
            text="Stock-In (Supplier Restock)",
            command=lambda: self._on_stock_move(TransactionType.STOCK_IN, 1),
        ).grid(row=4, column=0, columnspan=2, sticky="ew", pady=4)
        ttk.Button(
            ops_box,
            text="Stock-Out (Damage/Write-Off)",
            command=lambda: self._on_stock_move(TransactionType.STOCK_OUT, -1),
        ).grid(row=5, column=0, columnspan=2, sticky="ew", pady=4)

        # External REST API Currency Converter Panel
        api_box = ttk.LabelFrame(
            self._tab_operations, text="External API: Live Supplier Currency Converter", padding=12
        )
        api_box.grid(row=0, column=1, sticky="nsew", padx=(8, 0), pady=8)

        self._fx_amount = tk.StringVar(value="100.00")
        self._fx_from = tk.StringVar(value="USD")
        self._fx_to = tk.StringVar(value="NGN")
        self._fx_result = tk.StringVar(value="Click Convert to query live ExchangeRate API.")

        ttk.Label(api_box, text="Supplier Cost Amount:").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Entry(api_box, textvariable=self._fx_amount, width=20).grid(row=0, column=1, pady=4)
        ttk.Label(api_box, text="From Currency (USD/EUR/GBP):").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Entry(api_box, textvariable=self._fx_from, width=20).grid(row=1, column=1, pady=4)
        ttk.Label(api_box, text="To Local Currency (NGN/USD):").grid(row=2, column=0, sticky="w", pady=4)
        ttk.Entry(api_box, textvariable=self._fx_to, width=20).grid(row=2, column=1, pady=4)

        ttk.Button(api_box, text="Convert via Live API", command=self._on_convert_currency).grid(
            row=3, column=0, columnspan=2, sticky="ew", pady=10
        )
        ttk.Label(api_box, textvariable=self._fx_result, font=("Segoe UI", 10, "bold")).grid(
            row=4, column=0, columnspan=2, sticky="w", pady=6
        )

    def _build_reports_tab(self) -> None:
        """Build Low-Stock & Transaction Reports alongside embedded Matplotlib bar chart."""
        self._tab_reports.columnconfigure(0, weight=1)
        self._tab_reports.columnconfigure(1, weight=1)
        self._tab_reports.rowconfigure(0, weight=1)

        self._report_text = tk.Text(self._tab_reports, wrap="word", width=48, state="disabled")
        self._report_text.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        chart_frame = ttk.Frame(self._tab_reports)
        chart_frame.grid(row=0, column=1, sticky="nsew")
        self._figure = Figure(figsize=(5.5, 4.2), dpi=100)
        self._ax = self._figure.add_subplot(111)
        self._canvas = FigureCanvasTkAgg(self._figure, master=chart_frame)
        self._canvas.get_tk_widget().pack(fill="both", expand=True)

    def _build_ai_tab(self) -> None:
        """Build non-blocking AI Inventory Assistant chat interface with preset questions."""
        self._tab_ai.columnconfigure(0, weight=1)
        self._tab_ai.rowconfigure(1, weight=1)

        preset_frame = ttk.Frame(self._tab_ai)
        preset_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        presets = [
            "Which products need to be restocked?",
            "What were my best-selling products?",
            "Give me a summary of this month's sales.",
            "Which products have experienced declining sales?",
        ]
        for q in presets:
            ttk.Button(
                preset_frame, text=q, command=lambda query=q: self._dispatch_ai_query(query)
            ).pack(side="left", padx=4)

        self._ai_transcript = tk.Text(self._tab_ai, wrap="word", state="disabled")
        self._ai_transcript.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(0, 8))

        self._ai_input = tk.StringVar()
        ttk.Entry(self._tab_ai, textvariable=self._ai_input).grid(
            row=2, column=0, sticky="ew", padx=(0, 8)
        )
        self._ai_btn = ttk.Button(
            self._tab_ai,
            text="Ask AI Assistant",
            command=lambda: self._dispatch_ai_query(self._ai_input.get()),
        )
        self._ai_btn.grid(row=2, column=1, sticky="e")

    def _on_add_product(self) -> None:
        """Validate form fields, construct Product instance, and register in InventoryService."""
        try:
            prod = Product(
                product_id=self._entries["product_id"].get(),
                name=self._entries["name"].get(),
                category=self._entries["category"].get(),
                supplier_id=self._entries["supplier_id"].get(),
                quantity=int(self._entries["quantity"].get()),
                cost_price=Decimal(self._entries["cost_price"].get()),
                selling_price=Decimal(self._entries["selling_price"].get()),
                min_stock_level=int(self._entries["min_stock"].get()),
            )
            self._inventory.add_product(prod)
            self._refresh_all_views()
        except (InventoryAppError, ValueError, InvalidOperation) as exc:
            messagebox.showerror("Product Registration Error", str(exc))

    def _on_update_product(self) -> None:
        """Update an existing product's details from the form inputs."""
        try:
            prod = Product(
                product_id=self._entries["product_id"].get(),
                name=self._entries["name"].get(),
                category=self._entries["category"].get(),
                supplier_id=self._entries["supplier_id"].get(),
                quantity=int(self._entries["quantity"].get()),
                cost_price=Decimal(self._entries["cost_price"].get()),
                selling_price=Decimal(self._entries["selling_price"].get()),
                min_stock_level=int(self._entries["min_stock"].get()),
            )
            self._inventory.update_product(prod)
            self._refresh_all_views()
        except (InventoryAppError, KeyError, ValueError, InvalidOperation) as exc:
            messagebox.showerror("Update Error", str(exc))

    def _on_delete_product(self) -> None:
        """Delete the currently selected product in the Treeview."""
        selected = self._tree.selection()
        if not selected:
            messagebox.showwarning("Selection Required", "Select a product row in the table first.")
            return
        pid = str(self._tree.item(selected[0], "values")[0])
        try:
            self._inventory.delete_product(pid)
            self._refresh_all_views()
        except (InventoryAppError, KeyError) as exc:
            messagebox.showerror("Delete Error", str(exc))

    def _on_record_sale(self) -> None:
        """Execute a customer sale via SalesService and refresh reports."""
        try:
            pid = self._op_pid.get()
            qty = int(self._op_qty.get())
            notes = self._op_notes.get()
            updated = self._sales.record_sale(pid, qty, notes)
            self._refresh_all_views()
            if updated.is_low_stock:
                messagebox.showwarning("LOW STOCK ALERT!", "The quantity of the sold product is below the minimum stock level.")
        except (InventoryAppError, KeyError, ValueError) as exc:
            messagebox.showerror("Sale Error", str(exc))

    def _on_stock_move(self, tx_type: TransactionType, sign: int) -> None:
        """Process a stock-in (+) or stock-out (-) adjustment."""
        try:
            pid = self._op_pid.get()
            qty = abs(int(self._op_qty.get())) * sign
            self._inventory.adjust_stock(pid, qty, tx_type, self._op_notes.get())
            self._refresh_all_views()
        except (InventoryAppError, KeyError, ValueError) as exc:
            messagebox.showerror("Stock Operation Error", str(exc))

    def _on_convert_currency(self) -> None:
        """Query ExchangeRateAPIService to convert supplier pricing."""
        try:
            amt = Decimal(self._fx_amount.get())
            res = self._api.convert_price(amt, self._fx_from.get(), self._fx_to.get())
            self._fx_result.set(
                f"Converted: {amt} {self._fx_from.get().upper()} = {res} {self._fx_to.get().upper()}"
            )
        except (InventoryAppError, ValueError, InvalidOperation) as exc:
            messagebox.showerror("API Error", str(exc))

    def _dispatch_ai_query(self, query: str) -> None:
        """Run AI Assistant query on a background daemon thread so GUI never freezes."""
        cleaned = query.strip()
        if not cleaned:
            return
        self._ai_btn.config(state="disabled")
        self._append_ai_text(f"You: {cleaned}\nAssistant: Analyzing store telemetry...\n")
        self._ai_input.set("")

        def worker() -> None:
            try:
                ans = self._ai.ask(cleaned)
                self._ai_queue.put((True, ans))
            except Exception as exc:
                self._ai_queue.put((False, str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def _poll_ai_queue(self) -> None:
        """Drain background AI responses on the main Tkinter thread."""
        try:
            while True:
                ok, msg = self._ai_queue.get_nowait()
                self._ai_btn.config(state="normal")
                self._append_ai_text(f"{msg}\n" + ("-" * 60) + "\n")
        except queue.Empty:
            pass
        finally:
            self.after(100, self._poll_ai_queue)

    def _append_ai_text(self, text: str) -> None:
        """Unlock, append text, scroll, and relock the AI transcript widget."""
        self._ai_transcript.config(state="normal")
        self._ai_transcript.insert(tk.END, text)
        self._ai_transcript.see(tk.END)
        self._ai_transcript.config(state="disabled")

    def _refresh_all_views(self) -> None:
        """Synchronize KPI banner, product table, reports text, and Matplotlib chart."""
        fin = self._sales.get_financial_summary()
        low_count = len(self._inventory.get_low_stock_products())
        self._kpi_label.config(
            text=(
                f"Total Products: {len(self._inventory.products)}   |   "
                f"Low-Stock Alerts: {low_count}   |   "
                f"Units Sold: {fin.total_units_sold}   |   "
                f"Revenue: ${fin.total_revenue}   |   "
                f"COGS: ${fin.total_cogs}   |   "
                f"Est. Profit: ${fin.estimated_profit}"
            )
        )
        self._refresh_product_table()
        self._refresh_reports_and_chart()

    def _refresh_product_table(self) -> None:
        """Populate the Treeview with filtered products."""
        for row_id in self._tree.get_children():
            self._tree.delete(row_id)
        for prod in self._inventory.search_products(query=self._search_var.get()):
            status = "LOW STOCK" if prod.is_low_stock else "OK"
            self._tree.insert(
                "",
                tk.END,
                values=(
                    prod.product_id,
                    prod.name,
                    prod.category,
                    prod.supplier_id,
                    prod.quantity,
                    str(prod.cost_price),
                    str(prod.selling_price),
                    prod.min_stock_level,
                    status,
                ),
            )

    def _refresh_reports_and_chart(self) -> None:
        """Update text reports and redraw the Matplotlib stock vs min-threshold bar chart."""
        fin = self._sales.get_financial_summary()
        low_items = self._inventory.get_low_stock_products()
        best = self._sales.get_best_selling_products(top_n=5)

        lines = [
            "=== PROFIT & REVENUE SUMMARY ===",
            f"Total Units Sold : {fin.total_units_sold}",
            f"Total Revenue    : ${fin.total_revenue}",
            f"Cost of Goods    : ${fin.total_cogs}",
            f"Estimated Profit : ${fin.estimated_profit}\n",
            "=== LOW-STOCK ALERT REPORT ===",
        ]
        lines.extend(
            [f"- {p.product_id} ({p.name}): {p.quantity} left (Min: {p.min_stock_level})" for p in low_items]
            or ["No low-stock items."]
        )
        lines.append("\n=== BEST-SELLING PRODUCTS ===")
        lines.extend(
            [f"- {pid}: {u} units sold (${rev})" for pid, u, rev in best]
            or ["No sales recorded yet."]
        )
        lines.append("\n=== RECENT STOCK MOVEMENT HISTORY ===")
        for tx in self._inventory.transactions[-8:]:
            lines.append(
                f"[{tx.timestamp.strftime('%Y-%m-%d %H:%M')}] {tx.transaction_type.value} "
                f"| {tx.product_id} | Delta: {tx.quantity_delta}"
            )

        self._report_text.config(state="normal")
        self._report_text.delete("1.0", tk.END)
        self._report_text.insert(tk.END, "\n".join(lines))
        self._report_text.config(state="disabled")

        # Redraw Matplotlib Chart
        self._ax.clear()
        products = self._inventory.products[:8]
        if products:
            ids = [p.product_id for p in products]
            qtys = [p.quantity for p in products]
            colors = ["#d9534f" if p.is_low_stock else "#0275d8" for p in products]
            self._ax.bar(ids, qtys, color=colors)
            self._ax.set_title("Current Stock Levels (Red = Low Stock Alert)")
            self._ax.set_ylabel("Quantity in Stock")
        else:
            self._ax.text(0.5, 0.5, "Add products to view chart", ha="center", va="center")
        self._figure.tight_layout()
        self._canvas.draw()