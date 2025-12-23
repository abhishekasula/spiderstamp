import streamlit as st
from movie_resolve import resolve_movie
from spider_report import build_report

st.set_page_config(page_title="SpiderStamp (Melina)", page_icon="🕷️")

@st.cache_data(ttl=86400)
def cached_report(title: str, year: str | None):
    movie = resolve_movie(title, year)
    return build_report(movie)

def cute_presence_banner(present: bool, severity: str):
    if present:
        st.error("🕷️ **Spider present:** YES")
        if severity == "deceased-only":
            st.info("🪦 It looks like the spider is referenced/shown only as deceased (non-moving).")
        elif "eye-closeups" in (severity or ""):
            st.warning("👀 Possible eye-focused spider imagery mentioned in sources.")
        else:
            st.info("Spider exists in the movie according to our sources.")
    else:
        st.success("✅ **Spider present:** NO")
        st.caption("No core spider terms found in our sources (best-effort).")

st.title("🕷️ SpiderStamp")
st.markdown("### Hi Melina 👋")
st.write("What movie are you watching today? 🎬")

movie_title = st.text_input("", placeholder="Type a movie title…")
year = st.text_input("Year (optional)", placeholder="e.g., 2009")

check = st.button("Check for spiders", type="primary")
st.divider()

if check:
    if not movie_title.strip():
        st.warning("Type a movie title first 🙂")
        st.stop()

    try:
        with st.spinner("Checking the web for spider presence..."):
            report = cached_report(movie_title.strip(), year.strip() or None)

        movie = report["movie"]
        st.subheader(f"{movie['title']} ({movie['year']})")

        cute_presence_banner(report.get("present", False), report.get("severity", ""))

        st.write(f"**Confidence (presence):** `{report['confidence']}`  (score={report['score']})")
        st.caption(f"IMDb ID: {movie['imdb_id']}")

        st.divider()

        # Evidence (IMDb + Wikipedia)
        st.markdown("### 🧾 Evidence (for the receipts)")
        for ev in report["evidence"]:
            st.markdown(f"**{ev['source']}**")
            if ev.get("url"):
                st.write(ev["url"])
            st.write(f"- Available: **{ev.get('ok')}**")
            st.write(f"- Core hits: **{', '.join(ev.get('core_hits', [])) or 'None'}**")
            if ev.get("deceased"):
                st.info("🪦 Deceased/non-threatening context detected.")
            if ev.get("eye_context") and not ev.get("deceased"):
                st.warning("👀 Eye-focused spider imagery detected.")
            if ev.get("snippets"):
                for sn in ev["snippets"]:
                    st.info(sn)
            st.divider()

        # Web evidence pages
        st.markdown("### 🌐 Web evidence (pages we checked)")
        if not report["web_evidence"]:
            st.write("No fetched pages contained core spider mentions.")
        else:
            for e in report["web_evidence"][:8]:
                st.markdown(f"**{e.get('title','(page)')}**")
                st.write(e["url"])
                st.write(f"- Core hits: {', '.join(e['core_hits'])}")
                if e.get("deceased"):
                    st.info("🪦 Deceased/non-threatening context detected on this page.")
                if e.get("eye_context") and not e.get("deceased"):
                    st.warning("👀 Eye-focused spider imagery detected on this page.")
                for sn in e.get("snippets", []):
                    st.info(sn)
                st.divider()

        st.success("✅ Done! Want to check another movie, Melina?")

    except Exception as e:
        st.error(str(e))

st.caption("🕷️ SpiderStamp is a best-effort presence detector from public text sources. Visual-only spiders may be missed.")
