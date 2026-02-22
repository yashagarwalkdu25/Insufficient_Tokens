"""Self-contained HTML export with TripSaathi brand — day tabs and budget."""
from __future__ import annotations

from typing import Any


def export_to_html(trip: dict[str, Any], state: dict[str, Any], vibe_score: dict[str, Any] | None) -> str:
    vibe_score = vibe_score or {}
    dest = trip.get("destination", "Trip")
    start = trip.get("start_date", "")
    end = trip.get("end_date", "")
    total = trip.get("total_cost", 0)
    days = trip.get("days") or []
    score = vibe_score.get("overall_score", "")
    tagline = vibe_score.get("tagline", "")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>TripSaathi — {dest}</title>
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@400;600;700&family=Plus+Jakarta+Sans:wght@300;400;500;600;700&display=swap" rel="stylesheet"/>
<style>
  :root {{ --ts-teal:#1A5653; --ts-saffron:#E8772E; --ts-gold:#C5A55A; --ts-cream:#FAF6F0; --ts-text:#1E2832; --ts-border:#E8E2D8; }}
  * {{ box-sizing: border-box; }}
  body {{ font-family:'Plus Jakarta Sans',system-ui,sans-serif; margin:0; padding:0; background:var(--ts-cream); color:var(--ts-text); }}
  .header {{
    background: linear-gradient(135deg, var(--ts-teal) 0%, #0F3D3B 60%, #2A7A76 100%);
    color:#fff; padding:2rem 2.5rem 1.8rem; margin-bottom:0;
  }}
  .header h1 {{ font-family:'Cormorant Garamond',serif; font-size:2.4rem; margin:0 0 0.1rem 0; letter-spacing:-0.03em; }}
  .header .tagline {{ color:var(--ts-gold); font-family:'Cormorant Garamond',serif; font-style:italic; font-size:1rem; margin:0 0 0.6rem 0; }}
  .header .gold-line {{ width:50px; height:2px; background:var(--ts-gold); margin:0.5rem 0 0.4rem 0; }}
  .header .meta {{ opacity:0.8; font-size:0.9rem; }}
  .container {{ max-width:900px; margin:0 auto; padding:1.5rem; }}
  .tabs {{ display:flex; gap:0; border-bottom:2px solid var(--ts-border); margin-bottom:1rem; flex-wrap:wrap; }}
  .tab {{ padding:0.6rem 1.2rem; cursor:pointer; border-bottom:3px solid transparent; font-weight:500; color:#7A8B8A; transition:all 0.2s; font-size:0.9rem; }}
  .tab:hover {{ color:var(--ts-teal); }}
  .tab.active {{ color:var(--ts-teal); border-bottom-color:var(--ts-saffron); font-weight:600; }}
  .panel {{ display:none; padding:1rem; background:#fff; border-radius:14px; box-shadow:0 2px 16px rgba(26,86,83,0.08); margin-bottom:1rem; }}
  .panel.active {{ display:block; }}
  .item {{ display:flex; gap:0.75rem; padding:0.75rem 0; border-bottom:1px solid var(--ts-border); align-items:flex-start; }}
  .item:last-child {{ border-bottom:none; }}
  .item-time {{ font-weight:600; color:var(--ts-teal); min-width:50px; font-size:0.85rem; }}
  .item-title {{ font-weight:600; }}
  .item-cost {{ margin-left:auto; color:var(--ts-saffron); font-weight:500; white-space:nowrap; }}
  h2 {{ font-family:'Cormorant Garamond',serif; color:var(--ts-teal); margin:0 0 0.5rem 0; }}
  .budget-grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(150px,1fr)); gap:1rem; margin:1rem 0; }}
  .metric-box {{ background:var(--ts-cream); border:1px solid var(--ts-border); border-radius:12px; padding:1rem; text-align:center; }}
  .metric-val {{ font-family:'Cormorant Garamond',serif; font-size:1.5rem; font-weight:700; color:var(--ts-teal); }}
  .metric-label {{ font-size:0.75rem; color:#7A8B8A; text-transform:uppercase; letter-spacing:0.06em; }}
</style>
</head>
<body>
<div class="header">
  <h1>TripSaathi</h1>
  <p class="tagline">Har journey ka intelligent dost.</p>
  <div class="gold-line"></div>
  <p class="meta"><strong>{dest}</strong> &middot; {start} to {end} &middot; &#8377;{total:,.0f}
  {"" if not score else f" &middot; Vibe: {score}/100"}
  {"" if not tagline else f"<br/><em>{tagline}</em>"}
  </p>
</div>
<div class="container">
<div class="tabs" id="tabs"></div>
"""
    for i, day in enumerate(days):
        day_num = day.get("day_number", i + 1)
        day_title = day.get("title", f"Day {day_num}")
        day_date = day.get("date", "")
        day_cost = day.get("day_cost", 0)
        items = day.get("items") or []
        panel_id = f"day-{day_num}"
        html += f'<div class="panel" id="{panel_id}">'
        html += f"<h2>Day {day_num} — {day_date} — {day_title}</h2>"
        html += f"<p>Day total: &#8377;{day_cost:,.0f}</p>"
        for item in items:
            t = item.get("time", "")
            title = item.get("title", "")
            cost = item.get("cost", 0)
            html += (
                f'<div class="item">'
                f'<span class="item-time">{t}</span>'
                f'<span class="item-title">{title}</span>'
                f'<span class="item-cost">&#8377;{cost:,.0f}</span>'
                f'</div>'
            )
        html += "</div>"

    bt = state.get("budget_tracker") or {}
    cats = bt.get("categories") or []
    html += '<div class="panel" id="budget"><h2>Budget</h2><div class="budget-grid">'
    for c in cats:
        cat_name = c.get("category", "").replace("_", " ").title()
        html += f'<div class="metric-box"><div class="metric-val">&#8377;{c.get("spent", 0):,.0f}</div><div class="metric-label">{cat_name}</div></div>'
    html += "</div></div>"

    html += """
<script>
(function() {
  var panels = document.querySelectorAll('.panel');
  var tabs = document.getElementById('tabs');
  for (var i = 0; i < panels.length; i++) {
    var id = panels[i].id;
    var label = id === 'budget' ? 'Budget' : ('Day ' + (i + 1));
    var btn = document.createElement('button');
    btn.className = 'tab' + (i === 0 ? ' active' : '');
    btn.textContent = label;
    btn.onclick = (function(idx) { return function() {
      panels.forEach(function(p, j) { p.classList.toggle('active', j === idx); });
      document.querySelectorAll('.tab').forEach(function(t, j) { t.classList.toggle('active', j === idx); });
    }; })(i);
    tabs.appendChild(btn);
  }
  if (panels[0]) panels[0].classList.add('active');
})();
</script>
</div>
</body>
</html>
"""
    return html
