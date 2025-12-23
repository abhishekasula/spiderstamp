import os
import requests
from dotenv import load_dotenv
from config import load_key, save_key

load_dotenv()

def get_api_key() -> str:
    k = os.getenv("OMDB_API_KEY") or load_key()
    if not k:
        raise RuntimeError("Missing OMDB_API_KEY. Set it in Streamlit secrets or environment.")
    return k

def resolve_movie(title: str, year: str | None = None) -> dict:
    api_key = get_api_key()

    params = {"apikey": api_key, "t": title, "type": "movie"}
    if year:
        params["y"] = year

    r = requests.get("https://www.omdbapi.com/", params=params, timeout=20)
    r.raise_for_status()
    data = r.json()

    if data.get("Response") != "True":
        raise RuntimeError(f"OMDb could not resolve '{title}'. Error: {data.get('Error')}")

    return {
        "title": data.get("Title"),
        "year": data.get("Year"),
        "imdb_id": data.get("imdbID"),
        "rated": data.get("Rated"),
        "runtime": data.get("Runtime"),
        "plot": data.get("Plot"),
    }
