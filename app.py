import streamlit as st
from movie_resolve import resolve_movie
from spider_report import build_report

st.set_page_config(page_title="SpiderStamp (Melina)", page_icon="🕷️")
@st.cache_data(ttl=86400)
def cached_report(title: str, year: str | None):
    movie = resolve_movie(title, year)
    return build_report(movie)

# --- Cute helper: verdict + messages ---
def verdict_block(confidence: str, score: int):
    confidence = (confidence or "").lower()

    # You can tweak these thresholds any time
    if confidence == "low":
        st.success("🟢 **Looks spider-safe, Melina** ✨")
        st.caption("No strong spider signals found in our checks. (Still not a 100% guarantee — but vibes are good.)")
        st.progress(10, text="Spider energy: low 🫧")

        st.balloons()
        st.markdown("#### 🍿 Cozy mode activated")
        st.write("Go enjoy your movie, queen. If a spider even *thinks* about showing up, we’ll be offended on your behalf.")

    elif confidence == "medium":
        st.warning("🟡 **Proceed with caution, Melina** 👀")
        st.caption("Some spider-ish evidence showed up. Not necessarily intense — but stay alert.")
        st.progress(55, text="Spider energy: medium ⚠️")

        st.markdown("#### 🧸 Gentle heads-up")
        st.write("You’re probably fine… but keep your finger ready on the pause button like it owes you money.")

    else:  # high
        st.error("🔴 **Spider-heavy likely, Melina** 🚫🕷️")
        st.caption("Multiple sources strongly suggest spiders. Consider skipping or watching with a safety plan.")
        st.progress(90, text="Spider energy: high 🚨")

        st.markdown("#### 🛡️ Safety plan")
        st.write("Okay bestie: lights on, volume down, and be ready to fast-forward like a pro gamer.")

# --- Header ---
st.title("🕷️ SpiderStamp")
st.markdown("### Hi Melina 👋")
st.write("What movie are you watching today? 🎬")

# --- Inputs ---
movie_title = st.text_input("", placeholder="Type a movie title…")
year = st.text_input("Year (optional)", placeholder="e.g., 2000")

col1, col2 = st.columns([1, 1])
with col1:
    check = st.button("Check for spiders", type="primary")
with col2:
    st.caption("Tip: add the year for remakes.")

st.divider()

# --- Run report ---
if check:
    if not movie_title.strip():
        st.warning("Type a movie title first 🙂")
        st.stop()

    try:
        with st.spinner("Checking the web for spider vibes..."):
            report = cached_report(movie_title.strip(), year.strip() or None)
            movie = report["movie"]

        st.subheader(f"{movie['title']} ({movie['year']})")
        st.write(f"**🕷️ Spider likelihood:** `{report['confidence']}`  (score={report['score']})")
        st.caption(f"IMDb ID: {movie['imdb_id']}")

        # ✅ Cute verdict + messages
        verdict_block(report["confidence"], report["score"])

        st.divider()

        # --- Evidence ---
        imdb_ev = report["evidence"][0]
        st.markdown("### 🧾 Evidence (for the receipts)")
        for ev in report["evidence"]:
            st.markdown(f"**{ev['source']}**")
            if ev.get("url"):
                st.write(ev["url"])
            st.write(f"- Available: **{ev.get('ok')}**")
            st.write(f"- Core hits: **{', '.join(ev.get('core_hits', [])) or 'None'}**")
            if ev.get("snippets"):
                for sn in ev["snippets"]:
                    st.info(sn)
            st.divider()

        st.markdown("### 🌐 Web evidence (pages we checked)")
        if not report["web_evidence"]:
            st.write("No fetched pages contained core spider mentions.")
        else:
            for e in report["web_evidence"][:8]:
                st.markdown(f"**{e.get('title','(page)')}**")
                st.write(e["url"])
                st.write(f"Core hits: {', '.join(e['core_hits'])}")
                for sn in e["snippets"]:
                    st.info(sn)
                st.divider()



        st.success("✅ Done! Want to check another movie, Melina?")

    except Exception as e:
        st.error(str(e))

st.caption("🕷️ SpiderStamp is a best-effort detector from public text sources. Visual-only spiders may be missed.")
