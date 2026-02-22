# TASK-10: Export & Sharing System

## PR Title: `feat: PDF export with QR codes, JSON/HTML export, shareable links`

## Priority: P2 (Required deliverable but not blocking core pipeline)

## Summary
Implement the complete export system: PDF itinerary with embedded QR codes, JSON state export, self-contained HTML export, QR code generation, and shareable link functionality.

## Scope

### 1. QR Code Generator (app/export/qr_generator.py)
- `generate_qr_code(data: str, size: int = 200) → bytes` → returns PNG bytes
- `generate_qr_image(data: str) → PIL.Image` → returns PIL image for embedding
- `generate_booking_qr(url: str) → bytes` → QR for individual booking link
- `generate_trip_qr(trip_id: str, base_url: str) → bytes` → QR for shareable trip link
- Uses `qrcode` library with custom colors (brand orange)

### 2. PDF Generator (app/export/pdf_generator.py)
- `PDFGenerator` class
- `generate_pdf(trip, state) → bytes` → returns PDF file bytes
- Template: app/export/templates/itinerary.html (Jinja2)
- Pages:
  1. Cover page: YATRA AI logo, trip title, dates, vibe score, tagline
  2. Trip overview: destination, travelers, budget, style
  3. Day-by-day pages (one per day):
     - Day number, date, theme title
     - Timeline of items with times, descriptions, costs
     - **Travel duration between items** (e.g., "🚗 25 min auto ride")
     - **Contact info** for each bookable item (phone, address)
     - **Opening hours** for activities
     - Local tip of the day
     - Day budget total
  4. Budget summary page:
     - Allocation table (category, allocated, spent)
     - Total estimated cost
  5. Booking links page:
     - Each flight/hotel/activity with name, price, URL
     - **Contact info** (phone, email, address) for each booking
     - QR code next to each booking link
  6. Hidden gems appendix (if any)
  7. Map snapshot (static image rendered from Folium)
- Uses WeasyPrint for HTML→PDF conversion
- Brand styling consistent with Streamlit UI

### 3. JSON Exporter (app/export/json_exporter.py)
- `export_to_json(state) → str` → JSON string of full trip state
- `import_from_json(json_str) → dict` → restore state from JSON
- Handles Pydantic model serialization
- Includes metadata: export_date, app_version

### 4. HTML Exporter (app/export/html_exporter.py)
- `export_to_html(trip, state) → str` → self-contained HTML string
- Single file with embedded CSS and JS
- Interactive elements: day tabs, expandable items
- Map embedded as static image (or inline Folium if size permits)
- Works offline once downloaded

### 5. Shareable Links
- `generate_trip_id(session_id) → str` → unique short ID
- `save_shared_trip(trip_id, state)` → persist to SQLite (new table: shared_trips)
- `load_shared_trip(trip_id) → dict | None` → load for read-only view
- URL format: `app/?id=<trip_id>`
- Streamlit query param handling to detect shared trip view

### 6. PDF Template (app/export/templates/itinerary.html)
- Jinja2 template with all page layouts
- Print-optimized CSS (page breaks, margins)
- Brand colors and typography
- QR code placement

## Acceptance Criteria
- [ ] PDF generates successfully with all pages
- [ ] PDF has correct page breaks between days
- [ ] QR codes in PDF are scannable (verified with phone)
- [ ] Booking link QR codes open correct URLs
- [ ] Trip share QR code opens the app with trip loaded
- [ ] JSON export → import produces identical state
- [ ] HTML export works offline in browser
- [ ] Shareable link loads trip in read-only view
- [ ] PDF file size under 5MB for typical 4-day trip
- [ ] WeasyPrint renders correctly (no CSS issues)

## Dependencies
- TASK-01 (models, database)
- TASK-08 (trip data to export)

## Estimated Files: 6 (+ 1 template)
## Estimated LOC: ~700
