# scheduler/scheduler_manager.py

from services.website_checker import check_website

def run_checks(websites):
    """
    This function is called by the scheduler.
    It loops through websites and checks their status.
    """
    for site in websites:
        check_website(site)
