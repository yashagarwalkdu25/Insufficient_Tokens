"""PDF export using fpdf2 — TripSaathi brand."""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# TripSaathi brand colors (RGB)
_TEAL = (26, 86, 83)
_SAFFRON = (232, 119, 46)
_GOLD = (197, 165, 90)
_CREAM = (250, 246, 240)
_TEXT = (30, 40, 50)
_MUTED = (122, 139, 138)


class PDFGenerator:
    """Generate a trip itinerary PDF with TripSaathi branding."""

    def generate_pdf(
        self,
        trip: dict[str, Any],
        state: dict[str, Any],
        vibe_score: dict[str, Any],
        budget_tracker: dict[str, Any],
    ) -> bytes:
        from fpdf import FPDF

        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=20)

        # ── Cover page ───────────────────────────────────────────────
        pdf.add_page()
        pdf.set_fill_color(*_TEAL)
        pdf.rect(0, 0, 210, 55, "F")

        # Gold accent line
        pdf.set_fill_color(*_GOLD)
        pdf.rect(0, 55, 210, 3, "F")

        pdf.set_font("Helvetica", "B", 32)
        pdf.set_text_color(255, 255, 255)
        pdf.set_y(12)
        pdf.cell(0, 16, "TripSaathi", align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "I", 11)
        pdf.set_text_color(*_GOLD)
        pdf.cell(0, 7, "Har journey ka intelligent dost.", align="C", new_x="LMARGIN", new_y="NEXT")

        pdf.set_text_color(*_TEXT)
        pdf.ln(18)

        dest = trip.get("destination", "Trip")
        origin = trip.get("origin", "")
        start = trip.get("start_date", "")
        end = trip.get("end_date", "")
        total_cost = trip.get("total_cost", 0)
        style = trip.get("travel_style", "")
        traveler = trip.get("traveler_type", "")

        pdf.set_font("Helvetica", "B", 24)
        pdf.cell(0, 14, _safe(dest), align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 12)
        if origin:
            pdf.cell(0, 8, _safe(f"From {origin}"), align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 8, _safe(f"{start} to {end}"), align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(5)

        score = vibe_score.get("overall_score") if vibe_score else None
        tagline = vibe_score.get("tagline", "") if vibe_score else ""
        if score is not None:
            pdf.set_font("Helvetica", "B", 16)
            pdf.set_text_color(*_SAFFRON)
            pdf.cell(0, 10, f"Vibe Score: {score}/100", align="C", new_x="LMARGIN", new_y="NEXT")
            if tagline:
                pdf.set_font("Helvetica", "I", 11)
                pdf.set_text_color(*_MUTED)
                pdf.cell(0, 8, _safe(f'"{tagline}"'), align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(*_TEXT)
        pdf.ln(5)

        pdf.set_fill_color(*_CREAM)
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "Trip Overview", new_x="LMARGIN", new_y="NEXT", fill=True)
        pdf.set_font("Helvetica", "", 11)
        for line in [
            f"Style: {style.title()}" if style else None,
            f"Travelers: {traveler.title()}" if traveler else None,
            f"Total Budget: INR {total_cost:,.0f}" if total_cost else None,
        ]:
            if line:
                pdf.cell(0, 7, _safe(line), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(5)

        # ── Day-by-day ───────────────────────────────────────────────
        for day in trip.get("days") or []:
            pdf.add_page()
            day_num = day.get("day_number", "")
            title = day.get("title", f"Day {day_num}")
            day_date = day.get("date", "")
            day_cost = day.get("day_cost", 0)

            pdf.set_fill_color(*_TEAL)
            pdf.set_text_color(255, 255, 255)
            pdf.set_font("Helvetica", "B", 14)
            header_text = f"Day {day_num}: {title}"
            if day_date:
                header_text += f"  ({day_date})"
            pdf.cell(0, 10, _safe(header_text), fill=True, new_x="LMARGIN", new_y="NEXT")

            pdf.set_fill_color(*_GOLD)
            pdf.rect(10, pdf.get_y(), 190, 1.5, "F")
            pdf.set_text_color(*_TEXT)
            pdf.ln(5)

            tip = day.get("tip_of_the_day")
            if tip:
                pdf.set_font("Helvetica", "I", 9)
                pdf.set_text_color(*_SAFFRON)
                pdf.cell(0, 6, _safe(f"Tip: {tip}"), new_x="LMARGIN", new_y="NEXT")
                pdf.set_text_color(*_TEXT)
                pdf.ln(2)

            for item in day.get("items") or []:
                time_str = item.get("time", "")
                end_time = item.get("end_time", "")
                item_title = item.get("title", "")
                item_type = item.get("item_type", "")
                description = item.get("description", "")
                cost = item.get("cost", 0)

                icons = {"transport": "[T]", "hotel": "[H]", "meal": "[M]", "activity": "[A]", "free_time": "[F]"}
                icon = icons.get(item_type, "[*]")

                pdf.set_font("Helvetica", "B", 10)
                time_label = f"{time_str}" + (f"-{end_time}" if end_time else "")
                pdf.cell(28, 6, _safe(time_label))
                pdf.cell(10, 6, icon)
                pdf.cell(120, 6, _safe(item_title[:60]))
                if cost:
                    pdf.set_font("Helvetica", "", 9)
                    pdf.cell(30, 6, f"INR {cost:,.0f}", align="R")
                pdf.ln(6)

                if description:
                    pdf.set_font("Helvetica", "", 9)
                    pdf.set_text_color(*_MUTED)
                    pdf.set_x(48)
                    pdf.multi_cell(140, 5, _safe(description[:200]))
                    pdf.set_text_color(*_TEXT)

                travel_dur = item.get("travel_duration_to_next")
                travel_mode = item.get("travel_mode_to_next")
                if travel_dur:
                    pdf.set_font("Helvetica", "I", 8)
                    pdf.set_text_color(*_MUTED)
                    pdf.set_x(48)
                    pdf.cell(0, 4, _safe(f"~{travel_dur} min by {travel_mode or 'auto'}"), new_x="LMARGIN", new_y="NEXT")
                    pdf.set_text_color(*_TEXT)
                pdf.ln(2)

            if day_cost:
                pdf.ln(3)
                pdf.set_font("Helvetica", "B", 10)
                pdf.cell(0, 6, f"Day Total: INR {day_cost:,.0f}", align="R", new_x="LMARGIN", new_y="NEXT")

        # ── Budget summary ───────────────────────────────────────────
        if budget_tracker:
            pdf.add_page()
            pdf.set_fill_color(*_TEAL)
            pdf.set_text_color(255, 255, 255)
            pdf.set_font("Helvetica", "B", 14)
            pdf.cell(0, 10, "Budget Summary", fill=True, new_x="LMARGIN", new_y="NEXT")
            pdf.set_fill_color(*_GOLD)
            pdf.rect(10, pdf.get_y(), 190, 1.5, "F")
            pdf.set_text_color(*_TEXT)
            pdf.ln(5)

            total_budget = budget_tracker.get("total_budget", 0)
            categories = budget_tracker.get("categories") or []
            cat_list = categories if isinstance(categories, list) else [
                {"category": k, **(v if isinstance(v, dict) else {"allocated": v, "spent": 0})}
                for k, v in categories.items()
            ]
            total_spent = sum(c.get("spent", 0) for c in cat_list) if cat_list else budget_tracker.get("total_spent", 0)
            remaining = total_budget - total_spent

            pdf.set_font("Helvetica", "", 11)
            pdf.cell(0, 7, _safe(f"Total Budget: INR {total_budget:,.0f}"), new_x="LMARGIN", new_y="NEXT")
            pdf.cell(0, 7, _safe(f"Total Spent:  INR {total_spent:,.0f}"), new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "B", 11)
            color = (45, 139, 95) if remaining >= 0 else (196, 77, 77)
            pdf.set_text_color(*color)
            pdf.cell(0, 7, _safe(f"Remaining:    INR {remaining:,.0f}"), new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(*_TEXT)
            pdf.ln(5)

            if cat_list:
                pdf.set_font("Helvetica", "B", 10)
                pdf.set_fill_color(*_CREAM)
                pdf.cell(60, 7, "Category", border=1, fill=True)
                pdf.cell(40, 7, "Allocated", border=1, fill=True, align="R")
                pdf.cell(40, 7, "Spent", border=1, fill=True, align="R")
                pdf.cell(40, 7, "Remaining", border=1, fill=True, align="R")
                pdf.ln(7)
                pdf.set_font("Helvetica", "", 10)
                for cat in cat_list:
                    cat_name = cat.get("category", "Other") if isinstance(cat, dict) else str(cat)
                    alloc = cat.get("allocated", 0) if isinstance(cat, dict) else 0
                    spent = cat.get("spent", 0) if isinstance(cat, dict) else 0
                    rem = cat.get("remaining", alloc - spent) if isinstance(cat, dict) else 0
                    pdf.cell(60, 7, _safe(cat_name.replace("_", " ").title()), border=1)
                    pdf.cell(40, 7, f"{alloc:,.0f}", border=1, align="R")
                    pdf.cell(40, 7, f"{spent:,.0f}", border=1, align="R")
                    pdf.cell(40, 7, f"{rem:,.0f}", border=1, align="R")
                    pdf.ln(7)

        # ── Hidden gems ──────────────────────────────────────────────
        gems = state.get("hidden_gems") or []
        if gems:
            pdf.add_page()
            pdf.set_fill_color(*_GOLD)
            pdf.set_text_color(*_TEXT)
            pdf.set_font("Helvetica", "B", 14)
            pdf.cell(0, 10, "Hidden Gems", fill=True, new_x="LMARGIN", new_y="NEXT")
            pdf.ln(5)
            for gem in gems[:5]:
                if isinstance(gem, dict):
                    name = gem.get("name", "")
                    why = gem.get("why_special", gem.get("description", ""))
                    tip = gem.get("pro_tip", "")
                    pdf.set_font("Helvetica", "B", 11)
                    pdf.cell(0, 7, _safe(name), new_x="LMARGIN", new_y="NEXT")
                    if why:
                        pdf.set_font("Helvetica", "", 10)
                        pdf.multi_cell(0, 5, _safe(why[:200]))
                    if tip:
                        pdf.set_font("Helvetica", "I", 9)
                        pdf.set_text_color(*_SAFFRON)
                        pdf.cell(0, 6, _safe(f"Pro tip: {tip[:150]}"), new_x="LMARGIN", new_y="NEXT")
                        pdf.set_text_color(*_TEXT)
                    pdf.ln(4)

        # ── Footer ───────────────────────────────────────────────────
        pdf.ln(10)
        pdf.set_font("Helvetica", "I", 8)
        pdf.set_text_color(*_MUTED)
        pdf.cell(0, 5, "Generated by TripSaathi - Har journey ka intelligent dost.", align="C")

        return bytes(pdf.output())


def _safe(text: str) -> str:
    if not text:
        return ""
    replacements = {
        "\u20b9": "INR ", "\u2014": " - ", "\u2013": "-",
        "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
        "\u2026": "...", "\u00a0": " ",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text.encode("latin-1", errors="replace").decode("latin-1")
