"""Collect Reddit image-post candidates for human review only."""

import hashlib
import html
import json
import os
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

import requests

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "sources.json"
CANDIDATES_PATH = ROOT / "data" / "candidates.json"
SEEN_PATH = ROOT / "data" / "seen.json"
GALLERY_PATH = ROOT / "docs" / "index.html"
TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
API_ROOT = "https://oauth.reddit.com"


def load_json(path, default):
    try:
        with path.open(encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return default


def save_json(path, value):
    with path.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def utc_now():
    return datetime.now(UTC)


def parse_time(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def is_fresh(item, cutoff):
    try:
        return parse_time(item["first_seen_at"]) >= cutoff
    except (KeyError, TypeError, ValueError):
        return False


def get_token(user_agent):
    client_id = os.environ.get("REDDIT_CLIENT_ID")
    client_secret = os.environ.get("REDDIT_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise RuntimeError("Faltam REDDIT_CLIENT_ID ou REDDIT_CLIENT_SECRET nos Secrets.")
    response = requests.post(
        TOKEN_URL,
        auth=(client_id, client_secret),
        data={"grant_type": "client_credentials"},
        headers={"User-Agent": user_agent},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()["access_token"]


def api_get(path, token, user_agent, params=None):
    response = requests.get(
        API_ROOT + path,
        params=params,
        headers={"Authorization": "bearer " + token, "User-Agent": user_agent},
        timeout=30,
    )
    if response.status_code == 429:
        wait = int(response.headers.get("Retry-After", "30"))
        time.sleep(min(wait, 60))
        response = requests.get(
            API_ROOT + path,
            params=params,
            headers={"Authorization": "bearer " + token, "User-Agent": user_agent},
            timeout=30,
        )
    response.raise_for_status()
    return response.json()


def candidate_from_post(post, config, now):
    if post.get("over_18") or post.get("spoiler") or post.get("stickied"):
        return None
    if post.get("removed_by_category") or post.get("banned_by"):
        return None
    title = (post.get("title") or "").strip()
    source_url = "https://www.reddit.com" + (post.get("permalink") or "")
    media_url = (post.get("url_overridden_by_dest") or post.get("url") or "").strip()
    domain = urlparse(media_url).netloc.lower().removeprefix("www.")
    text = (title + " " + (post.get("link_flair_text") or "")).casefold()
    if not title or not source_url or not media_url:
        return None
    if domain in config["blocked_domains"] or domain not in config["allowed_media_domains"]:
        return None
    if any(term.casefold() in text for term in config["blocked_terms"]):
        return None
    if post.get("is_video"):
        return None
    item_id = hashlib.sha256((source_url + "|" + media_url).encode()).hexdigest()
    return {
        "id": item_id,
        "reddit_post_id": post.get("id"),
        "title": title[:240],
        "subreddit": post.get("subreddit_name_prefixed"),
        "source_url": source_url,
        "media_url": media_url,
        "source_domain": domain,
        "score_at_collection": post.get("score", 0),
        "first_seen_at": now.isoformat().replace("+00:00", "Z"),
        "review_status": "pending",
        "rights_note": "Abrir a fonte e confirmar direitos/licença antes de reutilizar."
    }


def still_available(items, token, user_agent):
    """Retain only posts still returned by Reddit; held data expires within 48h."""
    if not items:
        return []
    ids = ["t3_" + item["reddit_post_id"] for item in items if item.get("reddit_post_id")]
    active = set()
    for start in range(0, len(ids), 100):
        listing = api_get("/api/info", token, user_agent, {"id": ",".join(ids[start:start + 100])})
        for child in listing.get("data", {}).get("children", []):
            data = child.get("data", {})
            if not data.get("removed_by_category") and not data.get("banned_by"):
                active.add(data.get("id"))
    return [item for item in items if item.get("reddit_post_id") in active]


def build_gallery(items, title, generated_at):
    cards = []
    for item in items:
        cards.append("""<article class=\"card\"><img src=\"{media}\" alt=\"Pré-visualização externa\" loading=\"lazy\"><div><p class=\"meta\">{subreddit} · {domain}</p><h2>{name}</h2><p>Estado: <strong>{status}</strong></p><p><a href=\"{source}\" target=\"_blank\" rel=\"noopener noreferrer\">Abrir publicação original</a> · <a href=\"{media}\" target=\"_blank\" rel=\"noopener noreferrer\">Abrir media original</a></p><p class=\"note\">{note}</p></div></article>""".format(
            media=html.escape(item["media_url"], quote=True),
            subreddit=html.escape(item.get("subreddit") or "Reddit"),
            domain=html.escape(item.get("source_domain") or ""),
            name=html.escape(item["title"]),
            status=html.escape(item["review_status"]),
            source=html.escape(item["source_url"], quote=True),
            note=html.escape(item["rights_note"]),
        ))
    page = """<!doctype html><html lang=\"pt-PT\"><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>{title}</title><style>body{{font:16px system-ui;max-width:1100px;margin:2rem auto;padding:0 1rem;background:#fafafa;color:#151515}}.card{{background:#fff;border:1px solid #ddd;border-radius:12px;overflow:hidden;margin:1rem 0;display:grid;grid-template-columns:minmax(180px,300px) 1fr}}img{{width:100%;height:220px;object-fit:cover;background:#eee}}.card div{{padding:1rem}}h2{{margin:.2rem 0;font-size:1.1rem}}.meta,.note{{color:#555;font-size:.9rem}}a{{color:#0759b8}}@media(max-width:620px){{.card{{grid-template-columns:1fr}}}}</style><body><h1>{title}</h1><p>Atualizado: {generated}. Candidatos para revisão humana; nada é aprovado ou publicado automaticamente.</p>{cards}</body></html>""".format(
        title=html.escape(title), generated=html.escape(generated_at), cards="\n".join(cards) or "<p>Sem candidatos pendentes.</p>"
    )
    GALLERY_PATH.write_text(page, encoding="utf-8")


def telegram_notice(count):
    token, chat_id = os.environ.get("TELEGRAM_TOKEN"), os.environ.get("TELEGRAM_ID")
    if not token or not chat_id:
        return
    gallery = os.environ.get("PFI_GALLERY_URL", "")
    text = "PFI: {} candidato(s) pendente(s) para revisão.".format(count)
    if gallery:
        text += "\nGaleria: " + gallery
    requests.post("https://api.telegram.org/bot{}/sendMessage".format(token), data={"chat_id": chat_id, "text": text, "disable_web_page_preview": "true"}, timeout=30).raise_for_status()


def main():
    config = load_json(CONFIG_PATH, {})
    user_agent = os.environ.get("REDDIT_USER_AGENT", "github:prints-from-internet:v1.0 (contact: repository-owner)")
    now, cutoff = utc_now(), utc_now() - timedelta(hours=config["retention_hours"])
    existing = load_json(CANDIDATES_PATH, {"items": []}).get("items", [])
    seen = load_json(SEEN_PATH, {"items": []}).get("items", [])
    token = get_token(user_agent)
    existing = still_available([item for item in existing if is_fresh(item, cutoff)], token, user_agent)
    seen = [item for item in seen if is_fresh(item, cutoff)]
    known = {item["id"] for item in seen} | {item["id"] for item in existing}
    new_items = []
    for subreddit in config["subreddits"]:
        listing = api_get("/r/{}/new".format(subreddit), token, user_agent, {"limit": config["per_subreddit_limit"], "raw_json": 1})
        for child in listing.get("data", {}).get("children", []):
            item = candidate_from_post(child.get("data", {}), config, now)
            if item and item["id"] not in known:
                known.add(item["id"])
                new_items.append(item)
                if len(new_items) >= config["max_candidates_per_run"]:
                    break
        if len(new_items) >= config["max_candidates_per_run"]:
            break
    items = (new_items + existing)[:config["max_candidates_per_run"]]
    save_json(CANDIDATES_PATH, {"generated_at": now.isoformat().replace("+00:00", "Z"), "items": items})
    save_json(SEEN_PATH, {"items": seen + [{"id": item["id"], "first_seen_at": item["first_seen_at"]} for item in new_items]})
    build_gallery(items, config["gallery_title"], now.strftime("%Y-%m-%d %H:%M UTC"))
    telegram_notice(len(items))
    print("PFI concluído: {} novos, {} pendentes.".format(len(new_items), len(items)))


if __name__ == "__main__":
    main()
