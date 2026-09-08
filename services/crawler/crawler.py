import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin


class Crawler:
    def fetch(self, url: str) -> str:
        response = requests.get(url, timeout=10)
        response.raise_for_status()

        return response.text

    def parse(self, html: str, base_url: str) -> dict:
        soup = BeautifulSoup(html, "html.parser")

        title = soup.title.string if soup.title else ""

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

    def crawl(self, url: str) -> dict:
        html = self.fetch(url)

        return self.parse(html, url)