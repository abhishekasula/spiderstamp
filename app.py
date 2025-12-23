import streamlit as st
from movie_resolve import resolve_movie
from spider_report import build_report

st.set_page_config(page_title="SpiderStamp (Melina)", page_icon="🕷️")

@st.cache_data(ttl=86400)
def cached_report(title: str, year: str | None):
    movie = resolve_movie(title, year)
    return build_report(movie)

def verdict_block(confidence: str, severity: str, score: int):
    conf = (confidence or "").lower()
    sev = (severity or "").lower()

    if sev.startswith("deceased-only"):
        st.success("🟢 **Likely safe, Melina** ✨")
        st.caption("Spider is mentioned/seen only as deceased (non-moving, non-threatening).")
        st.progress(10, text="Spider energy: very low 🫧")
        return

    if conf == "low":
        st.success("🟢 **Looks spider-safe, Melina** ✨")
        st.caption("No strong spider signals found in our checks. (Not a perfect guarantee, but vibes are good.)")
        st.progress(10, text="Spider energy: low 🫧")
        st.balloons()
        return

    if conf == "medium":
        msg = "🟡 **Proceed with caution, Melina** 👀"
        if "eye-closeups" in sev:
            msg += "  (eye-focused imagery flagged)"
        st.warning(msg)
        st.caption("Some spider evidence showed up. Might be mild, but stay alert.")
        st.progress(55, text="Spider energy: medium ⚠️")
        return

    msg = "🔴 **Spider-heavy likely, Melina** 🚫🕷️"
    if "eye-closeups" in sev:
        msg += "  (eye-focused imagery flagged)"
    st.error(msg)
    st.caption("Multiple sources suggest spiders. Consider skipping or watching with a safety plan.")
    st.progress(90, text="Spider energy: high 🚨")

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
        with st.spinner("Checking the web for spider vibes..."):
            report = cached_report(movie_title.strip(), year.strip() or None)

        movie = report["movie"]
        st.subheader(f"{movie['title']} ({movie['year']})")
        st.write(f"**🕷️ Spider likelihood:** `{report['confidence']}`  (score={report['score']})")
        st.write(f"**Severity:** `{report['severity']}`")
        st.caption(f"IMDb ID: {movie['imdb_id']}")

        verdict_block(report["confidence"], report["severity"], report["score"])

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

st.caption("🕷️ SpiderStamp is a best-effort detector from public text sources. Visual-only spiders may be missed.")
