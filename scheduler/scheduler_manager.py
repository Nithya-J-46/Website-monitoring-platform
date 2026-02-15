from concurrent.futures import ThreadPoolExecutor
from services.website_checker import check_website


def run_checks(websites):

    # 🔥 Parallel execution
    with ThreadPoolExecutor(max_workers=5) as executor:
        executor.map(check_website, websites)
