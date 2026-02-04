class Website:
    def __init__(
        self,
        id,
        website_name,
        url,
        interval_seconds,
        search_text,
        status=None,
        checked_at=None
    ):
        self.id = id
        self.website_name = website_name
        self.url = url
        self.interval_seconds = interval_seconds
        self.search_text = search_text
        self.status = status
        self.checked_at = checked_at
