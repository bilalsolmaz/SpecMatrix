"""Compliance Matrix Excel (.xlsx) Export Service using openpyxl."""

import io
from pathlib import Path
from typing import Optional
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from app.models.schemas import AnalysisResponse, ComplianceStatus


class ComplianceExcelExporter:
    """Generates styled, color-coded, audit-grade Technical Specification Compliance Matrices."""

    # Status Color Palettes: (Fill Hex, Font Hex)
    STATUS_COLORS = {
        ComplianceStatus.TAM_UYUMLU: ("D4EDDA", "155724"),      # Light Green / Dark Green
        ComplianceStatus.KISMEN_UYUMLU: ("FFF3CD", "856404"),   # Light Yellow / Dark Gold
        ComplianceStatus.UYUMSUZ: ("F8D7DA", "721C24"),         # Light Red / Dark Red
        ComplianceStatus.BELIRTILMEMIS: ("E2E3E5", "383D41"),   # Light Gray / Dark Gray
    }

    HEADERS = [
        "Şartname Maddesi No",
        "Şartname Tanımı",
        "Kategori",
        "Uyumluluk Durumu",
        "Eşleşen Ürün & Doküman",
        "Sayfa / Bölüm No",
        "Kanıt Metni (Alıntı)",
        "Teknik Açıklama / Notlar"
    ]

    def export(self, analysis: AnalysisResponse) -> io.BytesIO:
        """Create workbook in memory and return BytesIO stream."""
        wb = Workbook()

        # Sheet 1: Uyumluluk Matrisi (Matrix)
        ws = wb.active
        ws.title = "Uyumluluk Matrisi"
        ws.views.sheetView[0].showGridLines = True

        # Styles
        font_family = "Segoe UI"
        title_font = Font(name=font_family, size=14, bold=True, color="1E293B")
        meta_font = Font(name=font_family, size=10, italic=True, color="64748B")
        kpi_title_font = Font(name=font_family, size=9, bold=True, color="475569")
        kpi_val_font = Font(name=font_family, size=13, bold=True, color="0F172A")

        header_font = Font(name=font_family, size=11, bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")

        data_font = Font(name=font_family, size=10, color="0F172A")
        thin_border = Border(
            left=Side(style='thin', color='E2E8F0'),
            right=Side(style='thin', color='E2E8F0'),
            top=Side(style='thin', color='E2E8F0'),
            bottom=Side(style='thin', color='E2E8F0')
        )

        align_center = Alignment(horizontal="center", vertical="center", wrap_text=True)
        align_left = Alignment(horizontal="left", vertical="center", wrap_text=True)

        # 1. Document Title
        ws.merge_cells("A1:H1")
        ws["A1"] = f"SPECMATRIX AI - TEKNİK ŞARTNAME UYUMLULUK MATRİSİ"
        ws["A1"].font = title_font
        ws["A1"].alignment = Alignment(horizontal="left", vertical="center")
        ws.row_dimensions[1].height = 28

        ws.merge_cells("A2:H2")
        ws["A2"] = f"İncelenen Şartname: {analysis.spec_name} | Üretim Standartlarında Otomatik Denetim Raporu"
        ws["A2"].font = meta_font
        ws.row_dimensions[2].height = 18

        # 2. Executive KPI Summary Cards (Row 4 & 5)
        kpi_labels = [
            ("Toplam Madde", f"{analysis.summary.total_clauses}", "F1F5F9", "334155"),
            ("Tam Uyumlu", f"{analysis.summary.tam_uyumlu_count} (%{analysis.summary.tam_uyumlu_pct})", "D4EDDA", "155724"),
            ("Kısmen Uyumlu", f"{analysis.summary.kismen_uyumlu_count} (%{analysis.summary.kismen_uyumlu_pct})", "FFF3CD", "856404"),
            ("Uyumsuz (Gap)", f"{analysis.summary.uyumsuz_count} (%{analysis.summary.uyumsuz_pct})", "F8D7DA", "721C24"),
            ("Belirtilmemiş", f"{analysis.summary.belirtilmemis_count} (%{analysis.summary.belirtilmemis_pct})", "E2E3E5", "383D41"),
        ]

        card_cols = [("A", "B"), ("C", "D"), ("E", "E"), ("F", "F"), ("G", "H")]
        for idx, (label, val, bg_hex, text_hex) in enumerate(kpi_labels):
            start_col, end_col = card_cols[idx]
            cell_ref = f"{start_col}4"
            if start_col != end_col:
                ws.merge_cells(f"{start_col}4:{end_col}4")
            ws[cell_ref] = label.upper()
            ws[cell_ref].font = kpi_title_font
            ws[cell_ref].alignment = Alignment(horizontal="center", vertical="center")
            ws[cell_ref].fill = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")
            ws[cell_ref].border = thin_border

            val_ref = f"{start_col}5"
            if start_col != end_col:
                ws.merge_cells(f"{start_col}5:{end_col}5")
            ws[val_ref] = val
            ws[val_ref].font = Font(name=font_family, size=11, bold=True, color=text_hex)
            ws[val_ref].alignment = Alignment(horizontal="center", vertical="center")
            ws[val_ref].fill = PatternFill(start_color=bg_hex, end_color=bg_hex, fill_type="solid")
            ws[val_ref].border = thin_border

        ws.row_dimensions[4].height = 16
        ws.row_dimensions[5].height = 22

        # 3. Table Headers (Row 7)
        table_start_row = 7
        ws.row_dimensions[table_start_row].height = 26

        for col_idx, header in enumerate(self.HEADERS, start=1):
            cell = ws.cell(row=table_start_row, column=col_idx, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = align_center
            cell.border = thin_border

        # 4. Table Data Rows
        current_row = table_start_row + 1
        for res in analysis.results:
            matched_prod_doc = []
            if res.matched_product:
                matched_prod_doc.append(res.matched_product)
            if res.matched_doc:
                matched_prod_doc.append(f"({res.matched_doc})")
            prod_doc_str = " ".join(matched_prod_doc) if matched_prod_doc else "—"

            row_data = [
                res.clause_id,
                res.clause_text,
                res.category,
                res.status.value,
                prod_doc_str,
                res.page_or_section or "—",
                res.exact_quote or "—",
                res.explanation
            ]

            # Dynamic row height based on content length
            est_lines = max(
                len(res.clause_text) // 40 + 1,
                len(res.explanation) // 40 + 1,
                len(res.exact_quote or "") // 45 + 1,
                2
            )
            ws.row_dimensions[current_row].height = max(38, min(130, est_lines * 17))

            for col_idx, val in enumerate(row_data, start=1):
                cell = ws.cell(row=current_row, column=col_idx, value=val)
                cell.font = data_font
                cell.border = thin_border

                if col_idx in [1, 3, 6]:
                    cell.alignment = align_center
                elif col_idx == 4:
                    # Color code compliance status
                    cell.alignment = align_center
                    fill_hex, text_hex = self.STATUS_COLORS.get(res.status, ("FFFFFF", "000000"))
                    cell.fill = PatternFill(start_color=fill_hex, end_color=fill_hex, fill_type="solid")
                    cell.font = Font(name=font_family, size=10, bold=True, color=text_hex)
                else:
                    cell.alignment = align_left

            current_row += 1

        # 5. Set Automatic Adaptive Column Widths
        col_constraints = {
            1: (15, 22),  # Madde No
            2: (35, 60),  # Şartname Tanımı
            3: (18, 30),  # Kategori
            4: (18, 24),  # Uyumluluk Durumu
            5: (24, 45),  # Eşleşen Ürün & Doküman
            6: (18, 28),  # Sayfa / Bölüm No
            7: (35, 65),  # Kanıt Metni
            8: (35, 60),  # Notlar
        }
        for col_idx, (min_w, max_w) in col_constraints.items():
            # Check maximum text length in this column
            max_len = 0
            for row in range(table_start_row, current_row):
                val_str = str(ws.cell(row=row, column=col_idx).value or "")
                # Find length of longest line if multiple lines
                lines = val_str.split("\n")
                line_len = max(len(l) for l in lines) if lines else len(val_str)
                if line_len > max_len:
                    max_len = line_len

            # Estimate width: text length + margin
            adapted_width = max(min_w, min(max_w, int(max_len * 0.75) + 3))
            col_letter = get_column_letter(col_idx)
            ws.column_dimensions[col_letter].width = adapted_width

        # Save to buffer
        stream = io.BytesIO()
        wb.save(stream)
        stream.seek(0)
        return stream

    def save_file(self, analysis: AnalysisResponse, output_path: str | Path) -> Path:
        """Export matrix and save directly to file."""
        stream = self.export(analysis)
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(stream.getvalue())
        return path
