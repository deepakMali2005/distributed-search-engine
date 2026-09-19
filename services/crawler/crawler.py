import requests
from bs4 import BeautifulSoup
from collections import deque
from urllib.parse import urljoin, urlparse, urldefrag

from sqlalchemy.orm import Session

from services.storage.crawl_storage import CrawlStorage


class Crawler:
    def fetch(self, url: str) -> str:
        """
        Fetch the HTML content of a webpage.

        A descriptive User-Agent is sent with the request so that
        websites can identify our crawler instead of treating it
        like an anonymous/default HTTP client.

        Args:
            url:
                URL of the webpage to fetch.

        Returns:
            The raw HTML response body.

        Raises:
            requests.RequestException:
                If the request fails or the server returns an
                unsuccessful HTTP status code.
        """

        headers = {
            "User-Agent": (
                "DistributedSearchEngine/1.0 "
                "(educational project; contact: alwaysinrush05@gmail.com)"
            )
        }

        response = requests.get(
            url,
            headers=headers,
            timeout=10,
        )

        response.raise_for_status()

        return response.text

    def parse(self, html: str, base_url: str) -> dict:
        """
        Parse an HTML page and extract useful document information.

        The parser extracts:

            1. Page title.
            2. Main textual content.
            3. Links found on the page.

        The parser first looks for common main-content containers.
        If none are found, it falls back to extracting text from
        the entire page.

        Args:
            html:
                Raw HTML returned by the web server.

            base_url:
                URL of the page being parsed.

        Returns:
            A dictionary containing:

                {
                    "title": "...",
                    "text": "...",
                    "links": [...]
                }
        """

        soup = BeautifulSoup(
            html,
            "html.parser",
        )

        title = (
            soup.title.string.strip()
            if soup.title and soup.title.string
            else ""
        )

        main_content = (
            soup.find("main")
            or soup.find("article")
            or soup.find(id="mw-content-text")
            or soup.find(id="bodyContent")
            or soup.find(id="content")
            or soup.find(class_="content")
        )

        if main_content:
            for element in main_content.find_all(
                ["script", "style", "nav", "footer", "header"]
            ):
                element.decompose()

            text = main_content.get_text(
                separator=" ",
                strip=True,
            )

        else:
            text = soup.get_text(
                separator=" ",
                strip=True,
            )

        links = []

        for link in soup.find_all("a", href=True):
            absolute_url = urljoin(
                base_url,
                link["href"],
            )

            links.append(absolute_url)

        return {
            "title": title,
            "text": text,
            "links": links,
        }

    def crawl(
        self,
        start_url: str,
        max_pages: int = 10,
        max_depth: int | None = None,
    ) -> list[dict]:
        """
        Crawl pages starting from `start_url`.

        The crawler uses breadth-first traversal.

        Crawl controls:

            max_pages:
                Hard maximum number of successfully crawled pages.

            max_depth:
                Maximum link distance from the starting URL.

                depth 0:
                    Starting URL only.

                depth 1:
                    Starting URL + direct links.

                depth 2:
                    Starting URL + direct links +
                    links discovered from those pages.

                None:
                    No depth restriction.

        The crawler:

            1. Starts from the given URL.
            2. Fetches and parses each page.
            3. Tracks the depth of every queued URL.
            4. Extracts links from each page.
            5. Normalizes URLs by removing fragments.
            6. Only follows links belonging to the same domain.
            7. Skips Wikipedia special pages.
            8. Avoids crawling the same URL more than once.
            9. Stops after `max_pages` pages.
            10. Stops expanding links beyond `max_depth`.

        Args:
            start_url:
                URL from which the crawler should start.

            max_pages:
                Maximum number of pages to crawl.

            max_depth:
                Maximum depth from the starting URL.
                Use None for unlimited depth.

        Returns:
            A list of crawled documents.
        """

        if max_pages <= 0:
            raise ValueError(
                "max_pages must be greater than 0."
            )

        if max_depth is not None and max_depth < 0:
            raise ValueError(
                "max_depth must be greater than or equal to 0."
            )

        start_url, _ = urldefrag(start_url)

        # Each queue entry contains:
        #
        #     (url, depth)
        #
        # This lets the crawler enforce max_depth while
        # retaining breadth-first traversal.
        queue = deque(
            [(start_url, 0)]
        )

        visited = set()

        # Keep track of URLs already placed into the queue.
        #
        # Without this, the same URL can be added many times
        # when multiple pages link to it.
        queued = {
            start_url
        }

        documents = []

        allowed_domain = urlparse(start_url).netloc

        while queue and len(visited) < max_pages:
            url, depth = queue.popleft()

            url, _ = urldefrag(url)

            if url in visited:
                continue

            parsed_url = urlparse(url)

            # Only crawl URLs belonging to the starting domain.
            if parsed_url.netloc != allowed_domain:
                continue

            # Skip Wikipedia special pages.
            if parsed_url.path.startswith("/wiki/Special:"):
                visited.add(url)
                continue

            try:
                html = self.fetch(url)

            except requests.RequestException as e:
                print(
                    f"Failed to fetch {url}"
                )
                print(
                    f"Reason: {e}"
                )

                visited.add(url)
                continue

            visited.add(url)

            document = self.parse(
                html,
                url,
            )

            documents.append(
                {
                    "url": url,
                    "title": document["title"],
                    "text": document["text"],
                }
            )

            # Do not expand this page if we have reached the
            # configured maximum depth.
            if (
                max_depth is not None
                and depth >= max_depth
            ):
                continue

            next_depth = depth + 1

            for link in document["links"]:

                link, _ = urldefrag(link)

                parsed_link = urlparse(link)

                if (
                    parsed_link.netloc == allowed_domain
                    and link not in visited
                    and link not in queued
                    and not parsed_link.path.startswith(
                        "/wiki/Special:"
                    )
                ):
                    queue.append(
                        (
                            link,
                            next_depth,
                        )
                    )

                    queued.add(link)

        return documents

    def crawl_resumable(
    self,
    db: Session,
    start_url: str,
    max_pages: int = 10,
    max_depth: int | None = None,
    max_attempts: int = 3,
) -> list[dict]:
        """
        Crawl using a PostgreSQL-backed persistent frontier.

        Unlike ``crawl()``, the frontier survives process restarts.

        ``max_pages`` applies to this invocation only. Running the
        same crawl again resumes from the persisted frontier.
        """

        if max_pages <= 0:
            raise ValueError(
                "max_pages must be greater than 0."
            )

        if max_depth is not None and max_depth < 0:
            raise ValueError(
                "max_depth must be greater than or equal to 0."
            )

        if max_attempts <= 0:
            raise ValueError(
                "max_attempts must be greater than 0."
            )

        start_url, _ = urldefrag(
            start_url
        )

        allowed_domain = urlparse(
            start_url
        ).netloc

        storage = CrawlStorage()

        session = storage.get_or_create_session(
            db=db,
            seed_url=start_url,
            allowed_domain=allowed_domain,
            max_depth=max_depth,
        )

        # Recover URLs that were being processed if the
        # previous process stopped unexpectedly.
        storage.recover_processing(
            db=db,
            crawl_session_id=session.id,
        )

        # Retry failed URLs while they still have retry capacity.
        storage.retry_failed(
            db=db,
            crawl_session_id=session.id,
            max_attempts=max_attempts,
        )

        # Safe because enqueue_url is idempotent.
        storage.enqueue_url(
            db=db,
            crawl_session_id=session.id,
            url=start_url,
            depth=0,
        )

        documents = []

        while len(documents) < max_pages:
            frontier = storage.claim_next(
                db=db,
                crawl_session_id=session.id,
            )

            if frontier is None:
                break

            url = frontier.url
            depth = frontier.depth

            parsed_url = urlparse(url)

            if parsed_url.netloc != allowed_domain:
                storage.mark_completed(
                    db=db,
                    frontier_id=frontier.id,
                )
                continue

            if parsed_url.path.startswith(
                "/wiki/Special:"
            ):
                storage.mark_completed(
                    db=db,
                    frontier_id=frontier.id,
                )
                continue

            try:
                html = self.fetch(url)

            except requests.RequestException as exc:
                print(
                    f"Failed to fetch {url}"
                )
                print(
                    f"Reason: {exc}"
                )

                storage.mark_failed(
                    db=db,
                    frontier_id=frontier.id,
                    error=str(exc),
                )

                continue

            document = self.parse(
                html,
                url,
            )

            # Expand the frontier only if we have not reached
            # the configured maximum depth.
            if (
                max_depth is None
                or depth < max_depth
            ):
                next_depth = depth + 1

                for link in document["links"]:
                    link, _ = urldefrag(
                        link
                    )

                    parsed_link = urlparse(
                        link
                    )

                    if (
                        parsed_link.netloc
                        == allowed_domain
                        and not parsed_link.path.startswith(
                            "/wiki/Special:"
                        )
                    ):
                        storage.enqueue_url(
                            db=db,
                            crawl_session_id=session.id,
                            url=link,
                            depth=next_depth,
                        )

            documents.append(
                {
                    "url": url,
                    "title": document["title"],
                    "text": document["text"],
                    "_frontier_id": frontier.id,
                    "_crawl_session_id": session.id,
                }
            )

        return documents