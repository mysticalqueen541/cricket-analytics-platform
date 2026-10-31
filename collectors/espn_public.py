"""Conservative public ESPN page/API adapter.

This adapter intentionally reports access failures. It does not bypass access controls.
Provider response formats change, so discovery parsers must be validated against live samples.
"""
import asyncio, json, re, time
from urllib.parse import urljoin
import aiohttp
from bs4 import BeautifulSoup
from config import REQUEST_TIMEOUT, REQUEST_DELAY_SECONDS, USER_AGENT

BASE = "https://www.espncricinfo.com"
HEADERS = {"User-Agent": USER_AGENT, "Accept": "text/html,application/json,*/*"}

class ProviderError(RuntimeError): pass

async def _get(session, url):
    await asyncio.sleep(REQUEST_DELAY_SECONDS)
    try:
        async with session.get(url, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)) as r:
            if r.status == 403:
                raise ProviderError("ESPN returned HTTP 403. This is a source-access failure, not proof that the match is absent.")
            if r.status == 429:
                raise ProviderError("ESPN rate-limited the request (HTTP 429). Try again later.")
            if r.status >= 400:
                raise ProviderError(f"ESPN returned HTTP {r.status}")
            return await r.text()
    except asyncio.TimeoutError as e:
        raise ProviderError("ESPN request timed out") from e
    except aiohttp.ClientError as e:
        raise ProviderError(f"Network error: {e}") from e

async def fetch_player_search(query):
    """Search public ESPN player pages. Returns candidate identities; never guesses on ambiguity."""
    url = f"{BASE}/search?q={aiohttp.helpers.quote(query)}"
    async with aiohttp.ClientSession() as session:
        html = await _get(session, url)
    soup = BeautifulSoup(html, "lxml")
    found, seen = [], set()
    for a in soup.select('a[href*="/cricketers/"]'):
        href = a.get("href","")
        name = " ".join(a.get_text(" ",strip=True).split())
        m = re.search(r"/cricketers/([^/?#]+)-(\d+)",href)
        if not m or not name or m.group(2) in seen: continue
        seen.add(m.group(2))
        found.append({"player_id":m.group(2),"name":name,"country":None,
                      "profile_url":urljoin(BASE,href)})
    return found

async def fetch_player_profile(player_url):
    async with aiohttp.ClientSession() as session:
        html = await _get(session,player_url)
    soup=BeautifulSoup(html,"lxml")
    name=soup.title.get_text(" ",strip=True).split("|")[0].strip() if soup.title else "Unknown"
    return {"name":name,"profile_url":player_url}

async def discover_matches_by_year(year, fmt):
    """Best-effort public results-page discovery. Returns normalized candidate match links.

    This endpoint is known to be intermittently blocked (403). An error is returned to
    the caller; it is never converted into an empty successful match list.
    """
    format_id={"Test":1,"ODI":2,"T20I":3}.get(fmt)
    if not format_id: raise ValueError("Unsupported format")
    url=f"https://www.espncricinfo.com/live-cricket-match-results?year={year}&type={format_id}"
    async with aiohttp.ClientSession() as session:
        html=await _get(session,url)
    soup=BeautifulSoup(html,"lxml")
    matches=[]
    for a in soup.select('a[href*="/live-cricket-score/"],a[href*="/series/"]'):
        href=a.get("href","")
        m=re.search(r"/([^/]+)-(\d+)(?:\?|$)",href)
        if not m: continue
        title=" ".join(a.get_text(" ",strip=True).split())
        matches.append({"match_id":m.group(2),"match_url":urljoin(BASE,href),
                        "series":None,"title":title,"format":fmt,"date":None,
                        "discovery_source":"ESPN public results page"})
    unique={x["match_id"]:x for x in matches}
    return list(unique.values())
