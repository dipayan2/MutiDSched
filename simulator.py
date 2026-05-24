import warnings
from enum import Enum


class TaskStatus(Enum):
    NOT_ACTIVE = 0
    ACTIVE = 1
    COMPLETE = 2
    EVICTED = 3


class Job:
    def __init__(self, cpu, gpu, mem, time, previous_job=None, next_job=None):
        # Resource constraints (clamped 0 to 1)
        self.cpu = max(0, min(1, cpu))
        self.gpu = max(0, min(1, gpu))
        self.mem = max(0, min(1, mem))
        self.time = time
        self.start_time = -1
        self.end_time = -1
        self.status = TaskStatus.NOT_ACTIVE
        # Bi-directional links
        self.next_job = next_job
        self.previous_job = previous_job

    def __repr__(self):
        p = "Bound" if self.previous_job else "None"
        n = "Bound" if self.next_job else "None"
        return (
            f"Job(CPU={self.cpu}, GPU={self.gpu}, Mem={self.mem}, "
            f"Time={self.time}s, Prev={p}, Next={n}, Status={self.status})"
        )

    def schedule(self, stime):
        """
        Marks the job as ACTIVE at stime.
        Raises RuntimeError if the previous job in the chain is not yet complete.
        """
        if self.previous_job is not None and self.previous_job.status != TaskStatus.COMPLETE:
            raise RuntimeError(
                f"Cannot schedule job: previous job must be COMPLETE before this job "
                f"can start (previous job status={self.previous_job.status})"
            )
        self.status = TaskStatus.ACTIVE
        self.start_time = stime

    def complete(self, etime):
        if self.status != TaskStatus.ACTIVE:
            return -1
        if etime < self.start_time + self.time:
            return -1
        self.status = TaskStatus.COMPLETE
        self.end_time = self.start_time + self.time
        return self.end_time

    def evict(self, etime):
        """
        Force-terminates a job due to deadline miss.
        Can evict from any state — job may not have even started.
        end_time is set to eviction time if job was running, -1 if never started.
        """
        self.status = TaskStatus.EVICTED
        self.end_time = etime if self.start_time != -1 else -1

    def is_complete_at(self, current_time):
        return (
            self.status == TaskStatus.ACTIVE
            and self.start_time != -1
            and current_time >= self.start_time + self.time
        )

    def tick(self, current_time):
        if self.is_complete_at(current_time):
            self.complete(self.start_time + self.time)


class Application:
    def __init__(self, deadline, arrival_time=0):
        self.deadline = deadline
        self.arrival_time = arrival_time
        self.app_status = TaskStatus.NOT_ACTIVE
        self.active_job_index = 0  # cursor to next unscheduled job
        self.jobs = []

    def add_job(self, job):
        """
        Adds a Job and maintains the doubly-linked chain.
        Warns and stretches deadline if total job time exceeds available window.
        Supports method chaining.
        """
        projected_total = self.total_time() + job.time
        available_window = self.deadline - self.arrival_time

        if projected_total > available_window:
            new_deadline = self.arrival_time + projected_total
            warnings.warn(
                f"Total job time ({projected_total}) exceeds available window "
                f"({available_window}). Updating deadline: "
                f"{self.deadline} → {new_deadline}",
                stacklevel=2
            )
            self.deadline = new_deadline

        if self.jobs:
            prev_job = self.jobs[-1]
            prev_job.next_job = job
            job.previous_job = prev_job
        self.jobs.append(job)
        return self

    def get_schedulable_job(self):
        """
        Returns (job, earliest_start_time) for the next job ready to be scheduled,
        or None if the chain is blocked or all jobs are done.
        Uses active_job_index as an O(1) cursor — no looping.
        """
        if self.active_job_index >= len(self.jobs):
            return None

        job = self.jobs[self.active_job_index]

        # First job in chain: can start any time after application arrival
        if job.previous_job is None:
            return (job, self.arrival_time)

        # Predecessor done: earliest start is when it ended
        if job.previous_job.status == TaskStatus.COMPLETE:
            return (job, job.previous_job.end_time)

        # Predecessor not done: chain is blocked
        return None

    def get_running_jobs(self):
        """Returns a list of currently ACTIVE jobs. Empty list if nothing running.
        EVICTED jobs are excluded — they no longer consume resources."""
        return [job for job in self.jobs if job.status == TaskStatus.ACTIVE]

    def total_time(self):
        """Sum of all job durations."""
        return sum(j.time for j in self.jobs)

    def __repr__(self):
        return (
            f"Application(ArrivalTime={self.arrival_time}, "
            f"Deadline={self.deadline}, "
            f"Jobs={len(self.jobs)}, "
            f"Status={self.app_status})"
        )


class SimulationResult:
    def __init__(self, completed, missed, total_time,
                 cpu_history, gpu_history, mem_history):
        self.completed = completed
        self.missed = missed
        self.total_time = total_time
        self.cpu_history = cpu_history
        self.gpu_history = gpu_history
        self.mem_history = mem_history

    def __repr__(self):
        return (
            f"SimulationResult("
            f"Completed={len(self.completed)}, "
            f"Missed={len(self.missed)}, "
            f"TotalTime={self.total_time})"
        )

    def stats(self):
        n = len(self.cpu_history)
        if n == 0:
            print("No ticks recorded.")
            return

        def _fmt(history):
            avg = sum(history) / n
            peak = max(history)
            idle = sum(1 for v in history if v == 0.0)
            return avg, peak, idle

        cpu_avg,  cpu_peak,  cpu_idle  = _fmt(self.cpu_history)
        gpu_avg,  gpu_peak,  gpu_idle  = _fmt(self.gpu_history)
        mem_avg,  mem_peak,  mem_idle  = _fmt(self.mem_history)

        print(f"\n=== Resource Stats over {n} ticks ===")
        print(f"  {'Resource':<10} {'Avg Usage':>10} {'Peak Usage':>12} {'Idle Ticks':>12}")
        print(f"  {'-'*46}")
        print(f"  {'CPU':<10} {cpu_avg:>9.1%} {cpu_peak:>11.1%} {cpu_idle:>10}t")
        print(f"  {'GPU':<10} {gpu_avg:>9.1%} {gpu_peak:>11.1%} {gpu_idle:>10}t")
        print(f"  {'MEM':<10} {mem_avg:>9.1%} {mem_peak:>11.1%} {mem_idle:>10}t")

    def summary(self):
        print(f"\n=== Simulation Complete at t={self.total_time} ===")
        print(f"\n  Completed ({len(self.completed)}):")
        for app in self.completed:
            print(f"    {app}")
            for i, job in enumerate(app.jobs):
                print(
                    f"      Job {i}: start={job.start_time}, end={job.end_time} "
                    f"| Job(cpu={job.cpu}, gpu={job.gpu}, mem={job.mem}, time={job.time})"
                )
        print(f"\n  Missed deadline ({len(self.missed)}):")
        for app in self.missed:
            print(f"    {app}")
            for i, job in enumerate(app.jobs):
                if job.status == TaskStatus.COMPLETE:
                    timing = f"start={job.start_time}, end={job.end_time}"
                elif job.status == TaskStatus.EVICTED and job.start_time != -1:
                    timing = f"start={job.start_time}, evicted={job.end_time}"
                else:
                    timing = "never scheduled, evicted"
                print(
                    f"      Job {i} [{job.status.name}]: {timing} "
                    f"| Job(cpu={job.cpu}, gpu={job.gpu}, mem={job.mem}, time={job.time})"
                )


class Scheduler:
    def __init__(self, applications, allow_flex_deadline=False):
            self.applications = applications
            self.clock = 0
            self.missed_apps = []
            self.allow_flex_deadline = allow_flex_deadline
            self._original_deadlines = {
                id(app): app.deadline for app in applications
            }
            # Resource usage history: one entry per tick
            self._cpu_history = []
            self._gpu_history = []
            self._mem_history = []


    def _get_active_resource_usage(self):
        """Sum of cpu, gpu, mem across all currently running jobs in all applications."""
        total_cpu = total_gpu = total_mem = 0.0
        for app in self.applications:
            for job in app.get_running_jobs():
                total_cpu += job.cpu
                total_gpu += job.gpu
                total_mem += job.mem
        return total_cpu, total_gpu, total_mem

    def _has_resource_capacity(self, job):
        """Returns True if adding this job would not push any resource over 1.0."""
        total_cpu, total_gpu, total_mem = self._get_active_resource_usage()
        return (
            total_cpu + job.cpu <= 1.0 and
            total_gpu + job.gpu <= 1.0 and
            total_mem + job.mem <= 1.0
        )

    def _get_ready_applications(self):
        """
        Applications that have arrived and are not yet complete,
        sorted by earliest deadline first (EDF).
        """
        return sorted(
            [
                app for app in self.applications
                if app.arrival_time <= self.clock
                and app.app_status != TaskStatus.COMPLETE
                and app.app_status != TaskStatus.EVICTED
            ],
            key=lambda app: app.deadline
        )

    def _mark_missed_applications(self):
        """
        Force-close applications that have blown their deadline so the
        simulation doesn't spin waiting for them, and they free resources.
        Evicts all non-complete jobs so resources are released immediately.
        Uses original deadline if allow_flex_deadline=False.
        """
        for app in self.applications:
            if app.app_status in (TaskStatus.COMPLETE, TaskStatus.EVICTED):
                continue
            if app in self.missed_apps:
                continue

            deadline = (
                app.deadline if self.allow_flex_deadline
                else self._original_deadlines[id(app)]
            )

            if self.clock > deadline:
                # Evict all jobs that haven't completed — releases their resources
                for job in app.jobs:
                    if job.status != TaskStatus.COMPLETE:
                        job.evict(self.clock)
                app.app_status = TaskStatus.EVICTED
                self.missed_apps.append(app)

    def _try_schedule(self, app):
        """
        Schedule the next job in an application if:
          - a schedulable job exists
          - the clock has reached its earliest start time
          - there is enough cpu, gpu, and mem capacity across all active jobs
        Advances active_job_index on successful schedule.
        """
        result = app.get_schedulable_job()
        if result is None:
            return

        job, earliest = result
        if self.clock >= earliest and self._has_resource_capacity(job):
            job.schedule(self.clock)
            app.app_status = TaskStatus.ACTIVE
            app.active_job_index += 1  # advance cursor to next job

    def _try_complete_app(self, app):
        """Mark application complete only if all jobs are COMPLETE (not EVICTED)."""
        if all(j.status == TaskStatus.COMPLETE for j in app.jobs):
            app.app_status = TaskStatus.COMPLETE

    def tick(self):
        self.clock += 1
        self._mark_missed_applications()

        for app in self._get_ready_applications():
            for job in app.get_running_jobs():
                job.tick(self.clock)
            self._try_schedule(app)
            self._try_complete_app(app)

        # Snapshot resource usage after all scheduling decisions this tick
        cpu, gpu, mem = self._get_active_resource_usage()
        self._cpu_history.append(cpu)
        self._gpu_history.append(gpu)
        self._mem_history.append(mem)

    def run(self, until=None):
        while True:
            all_done = all(
                app.app_status in (TaskStatus.COMPLETE, TaskStatus.EVICTED)
                for app in self.applications
            )
            if all_done:
                break
            if until is not None and self.clock >= until:
                break
            self.tick()

        completed = [
            app for app in self.applications
            if app.app_status == TaskStatus.COMPLETE
        ]
        return SimulationResult(
            completed, self.missed_apps, self.clock,
            self._cpu_history, self._gpu_history, self._mem_history
        )


if __name__ == "__main__":
    # app1: two jobs, moderate resources, comfortable deadline
    app1 = Application(deadline=80, arrival_time=0)
    (app1
        .add_job(Job(0.2, 0.1, 0.3, 10))
        .add_job(Job(0.3, 0.2, 0.3, 20)))

    # app2: hogs nearly all resources for 30 ticks
    app2 = Application(deadline=80, arrival_time=0)
    app2.add_job(Job(0.9, 0.8, 0.9, 30))

    # app3: arrives late, light footprint
    app3 = Application(deadline=80, arrival_time=20)
    (app3
        .add_job(Job(0.3, 0.2, 0.2, 10))
        .add_job(Job(0.1, 0.1, 0.1, 5)))

    # app4: blocked by app2, fits after it finishes
    app4 = Application(deadline=80, arrival_time=0)
    app4.add_job(Job(0.5, 0.5, 0.4, 15))

    # app5: job0 schedules immediately (tiny footprint)
    #        job1 needs cpu=0.8 — after job0 finishes at t=11,
    #        app2 (cpu=0.9) is still running until t=31,
    #        then app1/app3/app4 pile on — cpu never drops low enough
    #        deadline=45 expires before job1 ever gets a slot → EVICTED
    app5 = Application(deadline=100, arrival_time=0)
    (app5
        .add_job(Job(0.1, 0.1, 0.1, 10))   # job0: runs fine at t=1
        .add_job(Job(0.8, 0.7, 0.6, 20)))   # job1: never fits before t=45

    sim = Scheduler([app1, app2, app3, app4, app5], allow_flex_deadline=False)
    result = sim.run()
    result.summary()
    result.stats()