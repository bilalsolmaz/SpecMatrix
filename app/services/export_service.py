"""Compliance Matrix & Multi-Sheet Tender Package Excel (.xlsx) Export Service using openpyxl."""

import io
from pathlib import Path
from typing import Optional
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from app.models.schemas import AnalysisResponse, ComplianceStatus
from app.services.intelligence_service import ProposalDossierGenerator


class ComplianceExcelExporter:
    """Generates styled, color-coded, 4-sheet audit-grade Technical Specification & Proposal Packages."""

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
        """Create multi-sheet workbook in memory and return BytesIO stream."""
        wb = Workbook()

        # Ensure all clauses are enriched with v4.0 intelligence fields
        for res in analysis.results:
            if not res.proposal_response_text:
                ProposalDossierGenerator.enrich_compliance_result(res)

        # =====================================================================
        # SHEET 1: Uyumluluk Matrisi (Preserves exact layout for test suite)
        # =====================================================================
        ws = wb.active
        ws.title = "Uyumluluk Matrisi"
        ws.views.sheetView[0].showGridLines = True

        font_family = "Segoe UI"
        title_font = Font(name=font_family, size=14, bold=True, color="1E293B")
        meta_font = Font(name=font_family, size=10, italic=True, color="64748B")
        kpi_title_font = Font(name=font_family, size=9, bold=True, color="475569")

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

        ws.merge_cells("A1:H1")
        ws["A1"] = "SPECMATRIX AI - TEKNİK ŞARTNAME UYUMLULUK MATRİSİ"
        ws["A1"].font = title_font
        ws["A1"].alignment = Alignment(horizontal="left", vertical="center")
        ws.row_dimensions[1].height = 28

        ws.merge_cells("A2:H2")
        ws["A2"] = f"İncelenen Şartname: {analysis.spec_name} | Üretim Standartlarında Otomatik Denetim Raporu"
        ws["A2"].font = meta_font
        ws.row_dimensions[2].height = 18

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

        table_start_row = 7
        ws.row_dimensions[table_start_row].height = 26

        for col_idx, header in enumerate(self.HEADERS, start=1):
            cell = ws.cell(row=table_start_row, column=col_idx, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = align_center
            cell.border = thin_border

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
                    cell.alignment = align_center
                    fill_hex, text_hex = self.STATUS_COLORS.get(res.status, ("FFFFFF", "000000"))
                    cell.fill = PatternFill(start_color=fill_hex, end_color=fill_hex, fill_type="solid")
                    cell.font = Font(name=font_family, size=10, bold=True, color=text_hex)
                else:
                    cell.alignment = align_left

            current_row += 1

        col_constraints = {
            1: (15, 22),
            2: (35, 60),
            3: (18, 30),
            4: (18, 24),
            5: (24, 45),
            6: (18, 28),
            7: (35, 65),
            8: (35, 60),
        }
        self._auto_fit_columns(ws, table_start_row, current_row, col_constraints)

        # =====================================================================
        # SHEET 2: Resmi Teklif Cevap Cetveli (Clause-by-Clause Bidder Response)
        # =====================================================================
        ws2 = wb.create_sheet(title="Resmi Teklif Cevap Cetveli")
        ws2.views.sheetView[0].showGridLines = True
        ws2.merge_cells("A1:E1")
        ws2["A1"] = "TEKNİK ŞARTNAMEYE MADDE MADDE RESMİ İSTEKLİ CEVAP CETVELİ"
        ws2["A1"].font = title_font
        ws2.row_dimensions[1].height = 26

        s2_headers = ["Madde No", "Kategori", "İdare Şartname İsteri", "Teklif Edilen Çözüm", "İstekli Firma Resmi Taahhüt ve Cevap Metni"]
        ws2.row_dimensions[3].height = 24
        for idx, h in enumerate(s2_headers, start=1):
            c = ws2.cell(row=3, column=idx, value=h)
            c.font = header_font
            c.fill = header_fill
            c.alignment = align_center
            c.border = thin_border

        r_idx = 4
        for res in analysis.results:
            row_vals = [
                res.clause_id,
                res.category,
                res.clause_text,
                res.matched_product or "Kurumsal Çözüm Paketi",
                res.proposal_response_text or ""
            ]
            ws2.row_dimensions[r_idx].height = 48
            for c_idx, val in enumerate(row_vals, start=1):
                c = ws2.cell(row=r_idx, column=c_idx, value=val)
                c.font = data_font
                c.border = thin_border
                c.alignment = align_center if c_idx in (1, 2, 4) else align_left
            r_idx += 1
        self._auto_fit_columns(ws2, 3, r_idx, {1: (15, 20), 2: (18, 26), 3: (35, 55), 4: (22, 32), 5: (45, 75)})

        # =====================================================================
        # SHEET 3: Gap Kapatma & BOM Reçetesi
        # =====================================================================
        ws3 = wb.create_sheet(title="Gap Kapatma & BOM Reçetesi")
        ws3.views.sheetView[0].showGridLines = True
        ws3.merge_cells("A1:E1")
        ws3["A1"] = "GAP KAPATMA AKSİYON PLANI, BOM PAKETİ VE MALİYET ETKİSİ MATRİSİ"
        ws3["A1"].font = title_font
        ws3.row_dimensions[1].height = 26

        s3_headers = ["Madde No", "Uyumluluk Durumu", "Şartname Özeti", "Gap Kapatma / Mimari Çözüm Reçetesi", "Tahmini Maliyet & Süre Etkisi"]
        ws3.row_dimensions[3].height = 24
        for idx, h in enumerate(s3_headers, start=1):
            c = ws3.cell(row=3, column=idx, value=h)
            c.font = header_font
            c.fill = header_fill
            c.alignment = align_center
            c.border = thin_border

        r_idx = 4
        for res in analysis.results:
            row_vals = [
                res.clause_id,
                res.status.value,
                res.clause_text,
                res.remediation_action or "",
                res.estimated_cost_impact or ""
            ]
            ws3.row_dimensions[r_idx].height = 44
            for c_idx, val in enumerate(row_vals, start=1):
                c = ws3.cell(row=r_idx, column=c_idx, value=val)
                c.font = data_font
                c.border = thin_border
                c.alignment = align_center if c_idx in (1, 2, 5) else align_left
            r_idx += 1
        self._auto_fit_columns(ws3, 3, r_idx, {1: (15, 20), 2: (18, 24), 3: (35, 55), 4: (45, 70), 5: (28, 42)})

        # =====================================================================
        # SHEET 4: Rekabet Kısıtı (Spec-Lock Radar)
        # =====================================================================
        ws4 = wb.create_sheet(title="Rekabet Kısıtı (Spec-Lock)")
        ws4.views.sheetView[0].showGridLines = True
        ws4.merge_cells("A1:E1")
        ws4["A1"] = "ADRESE TESLİM ŞARTNAME & REKABET KISITI ANALİZİ (4734 KİK MADDE 12)"
        ws4["A1"].font = title_font
        ws4.row_dimensions[1].height = 26

        s4_headers = ["Madde No", "Rekabet Kısıt Riski", "Kısıt Skoru (0-100)", "Şartname Maddesi", "Hukuki & Teknik Kısıt Gerekçesi (KİK m.12)"]
        ws4.row_dimensions[3].height = 24
        for idx, h in enumerate(s4_headers, start=1):
            c = ws4.cell(row=3, column=idx, value=h)
            c.font = header_font
            c.fill = header_fill
            c.alignment = align_center
            c.border = thin_border

        r_idx = 4
        for res in analysis.results:
            row_vals = [
                res.clause_id,
                res.vendor_lock_risk or "YOK",
                res.vendor_lock_score or 0,
                res.clause_text,
                res.vendor_lock_reason or "Rekabeti kısıtlayıcı özel bir eşik tespit edilmedi."
            ]
            ws4.row_dimensions[r_idx].height = 42
            for c_idx, val in enumerate(row_vals, start=1):
                c = ws4.cell(row=r_idx, column=c_idx, value=val)
                c.font = data_font
                c.border = thin_border
                c.alignment = align_center if c_idx in (1, 2, 3) else align_left
            r_idx += 1
        self._auto_fit_columns(ws4, 3, r_idx, {1: (15, 20), 2: (18, 24), 3: (18, 22), 4: (35, 55), 5: (45, 75)})

        stream = io.BytesIO()
        wb.save(stream)
        stream.seek(0)
        return stream

    @staticmethod
    def _auto_fit_columns(ws, start_row: int, end_row: int, constraints: dict):
        for col_idx, (min_w, max_w) in constraints.items():
            max_len = 0
            for row in range(start_row, end_row):
                val_str = str(ws.cell(row=row, column=col_idx).value or "")
                lines = val_str.split("\n")
                line_len = max(len(l) for l in lines) if lines else len(val_str)
                if line_len > max_len:
                    max_len = line_len
            adapted_width = max(min_w, min(max_w, int(max_len * 0.75) + 3))
            ws.column_dimensions[get_column_letter(col_idx)].width = adapted_width

    def save_file(self, analysis: AnalysisResponse, output_path: str | Path) -> Path:
        """Export matrix and save directly to file."""
        stream = self.export(analysis)
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(stream.getvalue())
        return path
