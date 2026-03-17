from apscheduler.schedulers.background import BackgroundScheduler

def start_scheduler(job_fn):
    sch = BackgroundScheduler()
    sch.add_job(job_fn, "cron", minute="0,30", jitter=15)
    sch.start()
    return sch
