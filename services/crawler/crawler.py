import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from collections import deque


class Crawler:
    def fetch(self, url: str) -> str:
        response = requests.get(url, timeout=10)
        response.raise_for_status()

        return response.text

    def parse(self, html: str, base_url: str) -> dict:
        soup = BeautifulSoup(html, "html.parser")

        title = soup.title.string.strip() if soup.title and soup.title.string else ""

        text = soup.get_text(separator=" ", strip=True)

        links = []

        for link in soup.find_all("a", href=True):
            absolute_url = urljoin(base_url, link["href"])
            links.append(absolute_url)

        return {
            "title": title,
            "text": text,
            "links": links,
        }

    def crawl(self, start_url: str, max_pages: int = 10) -> list[dict]:
        queue = deque([start_url])
        visited = set()
        documents = []

        while queue and len(visited) < max_pages:
            url = queue.popleft()

            if url in visited:
                continue

            try:
                html = self.fetch(url)
            except requests.RequestException:
                visited.add(url)
                continue

            visited.add(url)

            document = self.parse(html, url)

            documents.append({
                "url": url,
                "title": document["title"],
                "text": document["text"],
            })

            for link in document["links"]:
                if link not in visited:
                    queue.append(link)

        return documents