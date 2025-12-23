import streamlit as st
from movie_resolve import resolve_movie
from spider_report import build_report

st.set_page_config(page_title="SpiderStamp (Melina)", page_icon="🕷️")

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
            movie = resolve_movie(movie_title.strip(), year.strip() or None)
            report = build_report(movie)

        st.subheader(f"{movie['title']} ({movie['year']})")
        st.write(f"**🕷️ Spider likelihood:** `{report['confidence']}`  (score={report['score']})")
        st.caption(f"IMDb ID: {movie['imdb_id']}")

        # ✅ Cute verdict + messages
        verdict_block(report["confidence"], report["score"])

        st.divider()

        # --- Evidence ---
        imdb_ev = report["evidence"][0]
        st.markdown("### 🧾 Evidence (for the receipts)")
        st.write(f"- IMDb parental guide available: **{imdb_ev['ok']}**")
        st.write(f"- Spider-ish terms found: **{', '.join(imdb_ev['hits']) if imdb_ev['hits'] else 'None found'}**")
        st.write(f"- Link: {imdb_ev['url']}")
        if imdb_ev["snippet"]:
            st.info(imdb_ev["snippet"])

        st.markdown("### 🌐 Web mentions")
        if not report["web_mentions"]:
            st.write("No web snippets returned.")
        else:
            for s in report["web_mentions"]:
                st.markdown(f"**{s['title']}**")
                st.write(s["snippet"])
                st.write(s["url"])
                st.divider()

        st.success("✅ Done! Want to check another movie, Melina?")

    except Exception as e:
        st.error(str(e))

st.caption("🕷️ SpiderStamp is a best-effort detector from public text sources. Visual-only spiders may be missed.")
