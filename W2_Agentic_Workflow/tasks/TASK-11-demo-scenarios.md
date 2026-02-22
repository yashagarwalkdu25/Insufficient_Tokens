# TASK-11: Demo Scenarios & Sample Plans

## PR Title: `feat: 3 demo travel plans and integration testing`

## Priority: P2 (Required deliverable for submission)

## Summary
Create 3 complete sample travel plans (as JSON fixtures) showcasing different travel styles, and an integration test that verifies the full pipeline works end-to-end.

## Scope

### 1. Solo Backpacking - Rishikesh (demo/scenarios/solo_rishikesh.json)
Input query: "Plan a 4-day solo backpacking trip to Rishikesh under ₹15,000. I love adventure sports and spiritual experiences. Traveling from Delhi next weekend."
Expected:
- 4 days, solo, adventure + spiritual
- Budget: ₹15,000 total
- Transport: Bus/train from Delhi (budget-friendly)
- Stay: Hostel/budget hotel (₹500-800/night)
- Activities: Rafting, bungee, yoga, Ganga Aarti, temple visits
- Hidden gems: Neer Garh Waterfall, Kunjapuri Sunrise
- Vibe: Adventure 90%, Spiritual 85%

### 2. Family Vacation - Goa (demo/scenarios/family_goa.json)
Input query: "5-day family vacation to Goa with 2 kids, ₹60,000 budget. Kid-friendly beaches and water sports. Flying from Mumbai."
Expected:
- 5 days, family (2 adults + 2 kids)
- Budget: ₹60,000 total
- Transport: Flights Mumbai→Goa
- Stay: Family-friendly resort (₹2,500-4,000/night)
- Activities: Beach, water sports, Dudhsagar Falls, spice plantation
- Hidden gems: Divar Island
- Vibe: Family Fun 88%, Relaxation 75%

### 3. Weekend Getaway - Jaipur (demo/scenarios/weekend_jaipur.json)
Input query: "Weekend trip to Jaipur from Delhi, mid-range budget ₹20,000 for couple. Love forts, food, and photography."
Expected:
- 2-3 days, couple, cultural + food
- Budget: ₹20,000 total
- Transport: Train from Delhi
- Stay: Heritage hotel (₹1,500-2,500/night)
- Activities: Amber Fort, Hawa Mahal, Nahargarh, Johari Bazaar, local food tour
- Hidden gems: Panna Meena ka Kund stepwell
- Vibe: Culture 92%, Food 85%

### 4. JSON Structure
Each scenario file contains:
```json
{
  "input_query": "...",
  "expected_trip_request": { TripRequest fields },
  "expected_trip": { Trip fields with DayPlan[] },
  "expected_budget": { BudgetTracker fields },
  "expected_vibe_score": { VibeScore fields },
  "booking_links": { verified URLs },
  "local_tips": [ LocalTip objects ],
  "hidden_gems": [ HiddenGem objects ]
}
```

### 5. Integration Test (tests/test_integration.py)
- Test 1: Load solo_rishikesh.json → run through full pipeline → verify output structure
- Test 2: Load family_goa.json → verify budget stays under ₹60K
- Test 3: Load weekend_jaipur.json → verify 2-3 day itinerary
- Test 4: Verify all booking links are valid URLs
- Test 5: Verify no hallucinated data (all source fields set)
- Test 6: Test modification flow: start with solo_rishikesh → "change to luxury" → verify changes

Note: Integration tests may require API keys. Mark as `@pytest.mark.integration` and skip if keys missing.

## Acceptance Criteria
- [ ] All 3 JSON files are valid and parseable
- [ ] Solo Rishikesh plan has 4 days, budget under ₹15K
- [ ] Family Goa plan has 5 days, accounts for 2 kids
- [ ] Weekend Jaipur plan has 2-3 days, couple-focused
- [ ] All booking links are real URLs that resolve
- [ ] All activities exist in real life (verifiable)
- [ ] All hotel price ranges are realistic for the style
- [ ] Integration tests pass with valid API keys
- [ ] Integration tests skip gracefully without API keys

## Dependencies
- All previous tasks (this validates the full system)

## Estimated Files: 3 JSONs + 1 test file
## Estimated LOC: ~800 (JSONs are large)
