# smart-tariff-api/app/scheduler.py

from apscheduler.schedulers.background import BackgroundScheduler

_scheduler: BackgroundScheduler | None = None

def start_scheduler(job_fn) -> BackgroundScheduler:
    """
    Create (or recreate) a BackgroundScheduler and schedule job_fn
    at :00 and :30 each hour, with a small jitter to avoid thundering herds.
    Returns the active scheduler instance.
    """
    global _scheduler

    # If we already had a scheduler, shut it down cleanly
    if _scheduler is not None:
        try:
            _scheduler.shutdown(wait=False)
        except Exception:
            pass
        _scheduler = None

    sch = BackgroundScheduler()
    # Align with Bright/DCC half-hour slots
    sch.add_job(job_fn, "cron", minute="0,30", jitter=15)
    sch.start()

    _scheduler = sch
    return _scheduler
