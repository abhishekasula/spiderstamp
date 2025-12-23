import streamlit as st
from movie_resolve import resolve_movie
from spider_report import build_report

st.set_page_config(page_title="SpiderStamp (Melina)", page_icon="🕷️")

# --- Header ---
st.title("SpiderStamp")
st.markdown("### Hi Melina ❤️")
st.write("What movie are you watching today? Let's see if it has spiders? 🎬")

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
        movie = resolve_movie(movie_title.strip(), year.strip() or None)
        report = build_report(movie)

        st.subheader(f"{movie['title']} ({movie['year']})")
        st.write(f"**🕷️ Spider likelihood:** `{report['confidence']}`  (score={report['score']})")
        st.caption(f"IMDb ID: {movie['imdb_id']}")

        imdb_ev = report["evidence"][0]
        st.markdown("### Evidence (IMDb parental guide)")
        st.write(f"- Available: **{imdb_ev['ok']}**")
        st.write(f"- Hits: **{', '.join(imdb_ev['hits']) if imdb_ev['hits'] else 'None found'}**")
        st.write(f"- Link: {imdb_ev['url']}")
        if imdb_ev["snippet"]:
            st.info(imdb_ev["snippet"])

        st.markdown("### Web mentions")
        if not report["web_mentions"]:
            st.write("No web snippets returned.")
        else:
            for s in report["web_mentions"]:
                st.markdown(f"**{s['title']}**")
                st.write(s["snippet"])
                st.write(s["url"])
                st.divider()

        st.success("Done ✅ Want to check another movie, Melina?")

    except Exception as e:
        st.error(str(e))
