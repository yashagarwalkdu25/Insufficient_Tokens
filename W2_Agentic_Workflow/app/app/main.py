"""
TripSaathi — Har journey ka intelligent dost.
Streamlit entry point: onboarding, planning progress, dashboard, approval, share.
"""
import os
import sys

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from app.logging_config import setup_logging

setup_logging()

import logging
import streamlit as st

logger = logging.getLogger("app.main")
from app.database import init_db, get_or_create_user, load_shared_trip
from app.graph.runner import GraphRunner
from app.memory.working_memory import WorkingMemoryManager
from app.ui.styles import load_css, load_late_overrides

st.set_page_config(page_title="TripSaathi", page_icon="🌿", layout="wide", initial_sidebar_state="collapsed")
st.markdown(load_css(), unsafe_allow_html=True)

# Force sidebar open via CSS when Modify Trip chat is active
if st.session_state.get("show_modify_sidebar"):
    st.markdown("""<style>
    .stApp [data-testid="stSidebar"] {
        margin-left: 0 !important;
        transform: none !important;
        min-width: 21rem !important;
        width: 21rem !important;
        visibility: visible !important;
        opacity: 1 !important;
        z-index: 999999 !important;
    }
    .stApp [data-testid="stSidebar"] > div:first-child {
        width: 21rem !important;
    }
    </style>""", unsafe_allow_html=True)

init_db()
session_id = st.session_state.get("session_id") or str(id(st))
st.session_state["session_id"] = session_id
user = get_or_create_user(session_id)
st.session_state["user_id"] = user["id"]
memory = WorkingMemoryManager()

if "trip_state" not in st.session_state:
    st.session_state["trip_state"] = memory.load_state(session_id) or {}
if "current_screen" not in st.session_state:
    st.session_state["current_screen"] = "onboarding" if not st.session_state["trip_state"] else "dashboard"

logger.info(
    "Session ready | session_id=%s current_screen=%s has_trip=%s",
    session_id[:8] if len(session_id) >= 8 else session_id,
    st.session_state["current_screen"],
    bool(st.session_state.get("trip_state", {}).get("trip")),
)

if "id" in st.query_params:
    shared_id = st.query_params["id"]
    shared = load_shared_trip(shared_id)
    if shared:
        logger.info("Loaded shared trip | id=%s", shared_id)
        st.session_state["trip_state"] = shared
        st.session_state["current_screen"] = "dashboard"
        st.session_state["read_only_shared"] = True

# Sidebar chat
from app.ui.components.chat_sidebar import render_chat_sidebar
render_chat_sidebar()

# Hero header (only on onboarding / planning, hidden on dashboard)
if st.session_state.get("current_screen") in ("onboarding", "planning", None):
    st.markdown("""
    <div class="ts-hero">
      <h1>TripSaathi</h1>
      <p class="ts-tagline">Har journey ka intelligent dost.</p>
      <div class="ts-gold-line"></div>
      <p class="ts-subtitle">AI-powered travel planning across India — flights, hotels, activities, local secrets & day-by-day itineraries.</p>
    </div>
    """, unsafe_allow_html=True)

# Screen router
if st.session_state["current_screen"] == "onboarding":
    logger.info("Screen: onboarding")
    from app.ui.components.onboarding import render_onboarding
    query = render_onboarding()
    if query:
        logger.info("Query submitted → planning | query_len=%s", len(query))
        st.session_state["current_screen"] = "planning"
        st.session_state["plan_query"] = query
        st.session_state["planning_completed_nodes"] = []
        st.session_state["planning_previews"] = {}
        st.session_state["planning_done"] = False
        st.rerun()

elif st.session_state["current_screen"] == "planning":
    logger.info("Screen: planning")
    from app.ui.components.planning_progress import render_planning_progress
    query = st.session_state.get("plan_query")
    resume_feedback = st.session_state.get("planning_resume_feedback")

    trip_state = st.session_state.get("trip_state") or {}
    if not query and not resume_feedback and trip_state.get("trip_request"):
        logger.info("Resuming after destination approval")
        memory.save_state(session_id, trip_state)
        runner = GraphRunner()
        out = runner.resume(session_id, user_feedback=None, approval=True)
        st.session_state["trip_state"] = out
        if out.get("trip"):
            st.session_state["current_screen"] = "dashboard"
            st.balloons()
            import time as _t; _t.sleep(1.5)
            st.rerun()
        else:
            st.session_state["current_screen"] = "dashboard"
            st.rerun()
    elif resume_feedback:
        logger.info("Resuming with feedback | feedback_len=%s", len(resume_feedback))
        runner = GraphRunner()
        out = runner.resume(session_id, user_feedback=resume_feedback, approval=True)
        st.session_state["trip_state"] = out

        # Store assistant response in chat messages
        conv_response = out.get("conversation_response")
        if conv_response:
            msgs = st.session_state.get("chat_messages") or []
            if not any(m.get("content") == conv_response for m in msgs):
                msgs.append({"role": "assistant", "content": conv_response})
                st.session_state["chat_messages"] = msgs

        st.session_state["current_screen"] = "dashboard"
        st.session_state["planning_resume_feedback"] = None
        st.rerun()
    elif query:
        runner = GraphRunner()
        gen = runner.stream(query, session_id, st.session_state["user_id"])
        done = render_planning_progress(gen)
        if done:
            loaded = memory.load_state(session_id)
            if loaded:
                st.session_state["trip_state"] = loaded
            trip_state = st.session_state.get("trip_state") or {}

            if trip_state.get("requires_approval"):
                approval_type = trip_state.get("approval_type", "")
                logger.info("Planning done → approval required | type=%s", approval_type)
                st.session_state["show_approval"] = True
                st.session_state["current_screen"] = "dashboard"
                st.rerun()
            elif trip_state.get("trip"):
                logger.info("Planning done → dashboard (trip ready)")
                st.session_state["current_screen"] = "dashboard"
                st.balloons()
                import time as _t; _t.sleep(1.5)
                st.rerun()
            else:
                logger.info("Planning done → dashboard (no trip in state)")
                st.session_state["current_screen"] = "dashboard"
                st.rerun()
    if st.button("Go to dashboard", key="goto_dashboard"):
        st.session_state["current_screen"] = "dashboard"
        st.rerun()

elif st.session_state.get("show_share_modal"):
    logger.info("Screen: share_modal")
    from app.ui.components.share_modal import render_share_modal
    render_share_modal(st.session_state["trip_state"])
    if st.button("Close", key="close_share"):
        st.session_state["show_share_modal"] = False
        st.rerun()

elif st.session_state.get("show_approval"):
    logger.info("Screen: approval")
    from app.ui.components.approval_section import render_approval
    state = st.session_state["trip_state"]

    def on_approve():
        approval_type = state.get("approval_type", "")
        if approval_type == "destination":
            logger.info("Action: approve destination → resume planning")
            st.session_state["show_approval"] = False
            st.session_state["current_screen"] = "planning"
            st.session_state["plan_query"] = None
            st.session_state["planning_resume_feedback"] = None
            st.rerun()
        else:
            logger.info("Action: approve itinerary → share_modal")
            st.session_state["show_approval"] = False
            st.session_state["show_share_modal"] = True
            st.rerun()

    def on_modify():
        logger.info("Action: modify → opening chat sidebar")
        st.session_state["show_approval"] = False
        st.session_state["show_modify_sidebar"] = True
        st.session_state["modify_chat_active"] = True
        st.session_state["current_screen"] = "dashboard"
        st.rerun()

    def on_reset():
        logger.info("Action: reset → onboarding")
        st.session_state["show_approval"] = False
        st.session_state["trip_state"] = {}
        st.session_state["current_screen"] = "onboarding"
        st.session_state["chat_messages"] = []
        st.rerun()

    render_approval(state, on_approve, on_modify, on_reset)

else:
    state = st.session_state["trip_state"]
    trip = state.get("trip")
    if trip:
        logger.info("Screen: dashboard | destination=%s", trip.get("destination", "?"))
        from app.ui.components.trip_dashboard import render_trip_dashboard
        render_trip_dashboard(state)
    else:
        logger.info("Screen: dashboard (no trip)")
        st.info("No itinerary yet. Use the form or describe your trip to get started.")
        if st.button("Start a new trip", key="new_trip_btn"):
            logger.info("Action: new trip → onboarding")
            st.session_state["trip_state"] = {}
            st.session_state["current_screen"] = "onboarding"
            st.rerun()

# Input/button overrides injected last so they win over Streamlit theme
st.markdown(load_late_overrides(), unsafe_allow_html=True)

# JS: hide Material Symbol icon elements that render as text
import streamlit.components.v1 as _stc
_stc.html("""<script>
(function(){
  function hideIcons(){
    try {
      var doc = window.parent.document;
      doc.querySelectorAll('[data-testid="stExpander"] summary').forEach(function(s){
        var first = s.querySelector(':scope > span:first-child');
        if(first){
          var txt = first.textContent || '';
          if(txt.indexOf('keyboard') !== -1 || txt.indexOf('expand') !== -1
             || txt.indexOf('chevron') !== -1 || txt.indexOf('arrow') !== -1){
            first.style.setProperty('display','none','important');
          }
        }
      });
      doc.querySelectorAll(
        '[data-testid="stSidebar"] span, [data-testid="stHeader"] span, [data-testid="collapsedControl"] span'
      ).forEach(function(el){
        var t = (el.textContent||'').trim();
        if(t.indexOf('keyboard')!==-1 || t.indexOf('chevron')!==-1
           || t.indexOf('arrow_')!==-1 || t==='close' || t==='menu'){
          el.style.setProperty('display','none','important');
        }
      });
    } catch(e){}
  }
  hideIcons();
  setTimeout(hideIcons, 200);
  setTimeout(hideIcons, 600);
  setTimeout(hideIcons, 1200);
  try {
    var obs = new MutationObserver(function(){ hideIcons(); });
    obs.observe(window.parent.document.body, {childList:true, subtree:true});
    setTimeout(function(){ obs.disconnect(); }, 10000);
  } catch(e){}
})();
</script>""", height=0)
