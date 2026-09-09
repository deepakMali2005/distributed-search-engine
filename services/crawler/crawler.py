import requests
from bs4 import BeautifulSoup
# from urllib.parse import urljoin
from collections import deque
from urllib.parse import urljoin, urlparse, urldefrag

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

        # Raise an exception for HTTP errors such as:
        # 403 Forbidden, 404 Not Found, 500 Internal Server Error, etc.
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

        # Convert raw HTML into a BeautifulSoup object.
        soup = BeautifulSoup(html, "html.parser")

        # Extract the page title.
        title = (
            soup.title.string.strip()
            if soup.title and soup.title.string
            else ""
        )

        # Try to locate the main content of the webpage.
        #
        # We check several common HTML structures because
        # different websites organize their content differently.
        main_content = (
            soup.find("main")
            or soup.find("article")
            or soup.find(id="mw-content-text")
            or soup.find(id="bodyContent")
            or soup.find(id="content")
            or soup.find(class_="content")
        )

        if main_content:
            # Remove elements that usually contain navigation,
            # scripts, styles, or other non-document content.
            #
            # These elements are not useful for our search index.
            for element in main_content.find_all(
                ["script", "style", "nav", "footer", "header"]
            ):
                element.decompose()

            # Extract text from the selected main content area.
            text = main_content.get_text(
                separator=" ",
                strip=True,
            )

        else:
            # If no main-content container can be identified,
            # fall back to the entire page.
            text = soup.get_text(
                separator=" ",
                strip=True,
            )

        # Extract all links from the original page.
        links = []

        for link in soup.find_all("a", href=True):

            # Convert relative URLs into absolute URLs.
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
    
    # def crawl(self, start_url: str, max_pages: int = 10) -> list[dict]:
    #     queue = deque([start_url])
    #     visited = set()
    #     documents = []

    #     while queue and len(visited) < max_pages:
    #         url = queue.popleft()

    #         if url in visited:
    #             continue

    #         try:
    #             html = self.fetch(url)
    #         except requests.RequestException:
    #             visited.add(url)
    #             continue

    #         visited.add(url)

    #         document = self.parse(html, url)

    #         documents.append({
    #             "url": url,
    #             "title": document["title"],
    #             "text": document["text"],
    #         })

    #         for link in document["links"]:
    #             if link not in visited:
    #                 queue.append(link)

    #     return documents


    def crawl(self, start_url: str, max_pages: int = 10) -> list[dict]:
        """
        Crawl pages starting from `start_url`.

        The crawler:

            1. Starts from the given URL.
            2. Fetches and parses each page.
            3. Extracts links from the page.
            4. Normalizes URLs by removing fragments.
            5. Only follows links belonging to the same domain.
            6. Skips Wikipedia special pages.
            7. Avoids crawling the same URL more than once.
            8. Stops after `max_pages` pages.

        Args:
            start_url:
                URL from which the crawler should start.

            max_pages:
                Maximum number of pages to crawl.

        Returns:
            A list of crawled documents.
        """

        # Remove any fragment from the starting URL.
        #
        # Example:
        #
        # https://example.com/page#section
        #
        # becomes:
        #
        # https://example.com/page
        start_url, _ = urldefrag(start_url)

        queue = deque([start_url])
        visited = set()
        documents = []

        # Extract the domain we are allowed to crawl.
        allowed_domain = urlparse(start_url).netloc

        while queue and len(visited) < max_pages:
            url = queue.popleft()

            # Normalize the URL before checking whether we have
            # already visited it.
            url, _ = urldefrag(url)

            # Skip URLs that have already been visited.
            if url in visited:
                continue

            parsed_url = urlparse(url)

            # Only crawl URLs belonging to the starting domain.
            if parsed_url.netloc != allowed_domain:
                continue

            # Skip Wikipedia special pages.
            #
            # These pages are generally not useful for building
            # our search index.
            if parsed_url.path.startswith("/wiki/Special:"):
                visited.add(url)
                continue

            try:
                html = self.fetch(url)

            except requests.RequestException as e:
                print(f"Failed to fetch {url}")
                print(f"Reason: {e}")

                visited.add(url)
                continue

            visited.add(url)

            # Parse the HTML into structured document data.
            document = self.parse(html, url)

            documents.append({
                "url": url,
                "title": document["title"],
                "text": document["text"],
            })

            # Process links discovered on the page.
            for link in document["links"]:

                # Remove URL fragments before adding links
                # to the queue.
                #
                # This prevents:
                #
                # /wiki/Search_engine
                # /wiki/Search_engine#bodyContent
                #
                # from becoming two separate crawl targets.
                link, _ = urldefrag(link)

                parsed_link = urlparse(link)

                # Only follow links that:
                #
                #   1. belong to the same domain
                #   2. haven't already been visited
                #   3. aren't Wikipedia special pages
                if (
                    parsed_link.netloc == allowed_domain
                    and link not in visited
                    and not parsed_link.path.startswith("/wiki/Special:")
                ):
                    queue.append(link)

        return documents
