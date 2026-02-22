# TASK-09: Streamlit UI - Interactive Trip Dashboard

## PR Title: `feat: Streamlit UI with onboarding, dashboard, plan editor, and chat sidebar`

## Priority: P1 (User-facing interface)

## Summary
Build the complete Streamlit UI with user-first interactive design: onboarding form, live planning progress, trip dashboard with editable itinerary, interactive map, budget charts, and chat sidebar for modifications.

## Scope

### 1. Main App Entry (app/main.py)
- Page config: title, icon, wide layout
- Session state initialization
- User detection: get_or_create_user from SQLite
- State restoration: load last trip_session if exists
- Route to correct screen: onboarding / planning / dashboard

### 2. Custom CSS (app/ui/styles.py)
- CSS variables for theme colors
- Header styles (gradient)
- Trip header with vibe badge
- Day card styles
- Tip/gem/event card styles
- Vibe score display (bars, breakdown)
- Responsive design (mobile-friendly)
- Button styles with hover effects

### 3. Onboarding Screen (app/ui/components/onboarding.py)
- Destination autocomplete (selectbox with search from india_cities)
- Traveler type cards: Solo / Couple / Family / Group (clickable cards, not dropdown)
- Budget slider: ₹5,000 - ₹5,00,000 with smart defaults by style
- Date picker: start_date and end_date (calendar widgets)
- Interest tags: clickable pill buttons (Adventure, Culture, Food, Spiritual, Beach, Nature, Photography, Nightlife)
- Travel style selector: Backpacker / Midrange / Luxury (visual cards)
- OR: Free-text textarea "Describe your dream trip..."
- "Plan My Trip" button (disabled until minimum fields filled)
- Example query buttons (4 preset queries)
- API status display (which APIs are connected)

### 4. Planning Progress (app/ui/components/planning_progress.py)
- Animated vertical timeline showing each agent
- Each agent: icon + name + status (waiting/running/done/failed)
- Real-time updates as nodes complete
- Preview text when done: "Found 5 flights, cheapest ₹3,200"
- Error display if agent fails (with fallback info)
- Estimated time remaining

### 5. Trip Dashboard (app/ui/components/trip_dashboard.py)
- Top bar: trip title + vibe score badge + share button
- Tab navigation: Itinerary | Map | Budget | Tips | AI Reasoning
- Renders the selected tab component
- Action bar at bottom: Approve | Modify | Export | New Trip

### 6. Itinerary Editor (app/ui/components/itinerary_editor.py)
This is the KEY interactive component:
- Day cards with colored left border (day-wise colors)
- Each day shows: day number, date, title, total cost
- Inside each day: list of ItineraryItems as cards:
  - Time, icon (by type), title, description, cost
  - **Travel duration badge** between items: "🚗 25 min" or "🚶 10 min walk" (from travel_duration_to_next)
  - **Contact info line**: 📞 phone | 📍 address (when available from contact_info field)
  - **Opening hours indicator**: "Open 9AM-6PM" or "⚠️ Closed on Mondays" (from opening_hours)
  - [Book] button → opens booking URL
  - [Swap] button → shows alternatives modal
  - [Remove] button → removes + recalculates budget
  - [Replace] button → shows similar activities
- [+ Add Activity] at end of each day → activity browser
- Activity browser: filtered by destination, shows name/price/duration/rating/**opening hours**
- Swap modal: shows all options from state with scores
- Budget auto-updates on every change

### 7. Interactive Map (app/ui/components/map_view.py)
- Folium map with Streamlit integration
- Day-wise color-coded markers (different color per day)
- Route lines connecting activities per day (dashed polylines)
- Marker popups: activity name, time, cost, **travel time to next stop**, **contact info**
- **Travel duration labels** on route lines between markers (e.g., "25 min drive")
- Day filter dropdown: "All days" / "Day 1" / "Day 2" etc.
- Auto-fit bounds to show all markers
- Legend showing day colors

### 8. Budget View (app/ui/components/budget_view.py)
- Plotly pie chart: Transport / Stay / Food / Activities / Buffer
- Per-day bar chart showing daily spend
- Budget allocation sliders (adjust % per category)
- "Optimize" button → triggers budget optimizer re-run
- Over-budget warning with suggested changes
- Cost comparison: "Your budget ₹15K | Estimated ₹14,200 | Saving ₹800"

### 9. Local Tips View (app/ui/components/local_tips_view.py)
- Sub-tabs: Insider Tips | Hidden Gems | Events
- Tips grouped by category with icons
- Each tip: title, content, source, upvotes, link
- Gems: name, why_special, pro_tip, confidence indicator
- Events: name, dates, impact badge (green/orange/red), recommendation

### 10. Vibe Score View (app/ui/components/vibe_score_view.py)
- Large score display with emoji
- Tagline in italic
- Breakdown bars (category: percentage)
- Perfect matches list
- Considerations list

### 11. Agent Reasoning View (app/ui/components/reasoning_view.py)
- Expandable accordion per agent
- Each: agent name, action, reasoning text, result, tokens used, latency
- Timeline visualization

### 12. Chat Sidebar (app/ui/components/chat_sidebar.py)
- Chat input for natural language modifications
- "Make it cheaper" / "Add more adventure" / "Change hotel"
- Message history display
- Quick action buttons: Export PDF | Share | New Trip

### 13. Approval Section (app/ui/components/approval_section.py)
- HITL checkpoint UI
- Summary of what's being approved
- [Approve] [Modify] [Start Over] buttons
- Feedback textarea (when Modify selected)

### 14. Share Modal (app/ui/components/share_modal.py)
- QR code display (trip overview)
- Download buttons: PDF / JSON / HTML
- Copy shareable link button
- Share via QR modal

## Acceptance Criteria
- [ ] Onboarding form collects all required fields
- [ ] Example queries trigger planning
- [ ] Planning progress shows real-time agent status
- [ ] Trip dashboard displays all tabs correctly
- [ ] Itinerary editor: Swap button shows alternatives
- [ ] Itinerary editor: Remove button removes + updates budget
- [ ] Itinerary editor: Add button shows activity browser
- [ ] **Itinerary editor: Travel duration badges shown between items (e.g., "🚗 25 min")**
- [ ] **Itinerary editor: Contact info (phone/address) displayed for bookable items**
- [ ] **Itinerary editor: Opening hours shown for activities**
- [ ] **Map: Travel duration labels visible on route lines**
- [ ] Map shows day-wise color-coded markers with routes
- [ ] Budget pie chart and bar chart render correctly
- [ ] Budget sliders trigger re-optimization
- [ ] Chat sidebar sends modifications to graph runner
- [ ] Approval buttons correctly route to approve/modify/reset
- [ ] Share modal generates QR code
- [ ] State persists on browser refresh (loaded from SQLite)
- [ ] Mobile-responsive layout
- [ ] Custom CSS loads without errors

## Dependencies
- TASK-01 (config, models)
- TASK-02 (india_cities for autocomplete)
- TASK-05 (graph runner for planning execution)
- TASK-08 (all agent outputs for display)

## Estimated Files: 14
## Estimated LOC: ~1800
